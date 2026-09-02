# -*- coding: utf-8 -*-
"""O conteúdo dos arquivos que o programa salva: tabelas em .txt e a
imagem compilada da batelada.

Esta camada fica entre o desenho e a janela: sabe MONTAR o conteúdo dos
arquivos, mas não sabe onde eles vão parar — quem escolhe pasta e nome é
a interface. Assim dá pra exportar uma batelada inteira de dentro de um
script, sem abrir janela nenhuma:

    import matplotlib
    matplotlib.use("Agg")
    from catalogador.nucleo import parse_frx_file, apply_exclusions, classify
    from catalogador.exportacao import bloco_da_amostra, linhas_da_tabela

    elementos = parse_frx_file("amostra.txt")
    mantidos, fora = apply_exclusions(elementos, tube_z={78, 79})
    maj, tracos, total = classify(mantidos, 10.0)
    texto = bloco_da_amostra("Amostra", "081025af",
                             linhas_da_tabela(maj, tracos, total),
                             total, 10.0, "Ouro — Au",
                             [e["symbol"] for e in fora])
    open("amostra.txt", "w", encoding="utf-8").write(texto)

A dependência continua andando num sentido só:
interface -> exportacao -> graficos -> nucleo.
"""

import os
from datetime import date

# Cabeçalho da tabela e o alinhamento de cada coluna ("<" à esquerda,
# ">" à direita). É a mesma tabela que aparece na tela.
CABECALHO = ("Z", "Elemento", "Área (cps)", "% do total", "Grupo")
ALINHAMENTO = (">", "<", ">", ">", "<")


def linhas_da_tabela(major, trace, total):
    """As linhas da tabela de uma amostra, da maior área pra menor.

    Devolve tuplas de texto já formatado (Z, símbolo, área, %, grupo) —
    as MESMAS que a tabela da tela mostra, pra tela e arquivo nunca
    discordarem.
    """
    if total <= 0:
        return []
    linhas = [(e["z"], e["symbol"], e["area"], grupo)
              for grupo, elementos in (("majoritário", major), ("traço", trace))
              for e in elementos]
    linhas.sort(key=lambda l: -l[2])
    return [(str(z), simbolo, f"{area:.0f}", f"{area / total * 100:.2f}%", grupo)
            for z, simbolo, area, grupo in linhas]


def _tabela_alinhada(linhas):
    """A tabela em colunas de largura fixa, pra ficar legível no Bloco de
    Notas (e ainda dar pra importar como largura fixa numa planilha)."""
    colunas = list(zip(CABECALHO, *linhas)) if linhas else [(c,) for c in CABECALHO]
    larguras = [max(len(valor) for valor in coluna) for coluna in colunas]

    def formata(valores):
        return "  ".join(f"{v:{a}{w}}" for v, a, w in
                         zip(valores, ALINHAMENTO, larguras)).rstrip()

    saida = [formata(CABECALHO), "  ".join("-" * w for w in larguras)]
    saida.extend(formata(linha) for linha in linhas)
    return saida


def bloco_da_amostra(nome, codigo, linhas, total, limite, tubo, descartados,
                     pasta=None):
    """O texto completo da tabela de UMA amostra: um cabeçalho dizendo em
    que condições ela foi classificada, e a tabela em si.

    O cabeçalho não é enfeite — sem o limite do traço e o tubo, a coluna
    "Grupo" não quer dizer nada seis meses depois. A `pasta` só aparece
    quando a amostra veio do banco: é o caminho dela na árvore
    ("Madeira / In natura / Pó"), que diz de que material é a medida.
    """
    cabecalho = [
        f"Amostra: {nome}",
        f"Arquivo: {codigo}",
    ]
    if pasta:
        cabecalho.append(f"Pasta no banco: {pasta}")
    cabecalho += [
        f"Tubo de raios X: {tubo}",
        f"Limite do grupo traço: {limite:.1f}%",
    ]
    if descartados:
        cabecalho.append("Descartado: " + ", ".join(descartados))
    cabecalho.append(f"Área total (cps): {total:.0f}")
    return "\n".join(cabecalho + [""] + _tabela_alinhada(linhas)) + "\n"


def documento_compilado(blocos, limite, tubo, mapeamento_usado):
    """Um arquivo só com a tabela de todas as amostras, uma embaixo da
    outra."""
    separador = "=" * 74
    cabecalho = [
        separador,
        "Catalogador de Espectros FRX — %d amostra(s)" % len(blocos),
        separador,
        f"Tubo de raios X: {tubo}",
        f"Limite do grupo traço: {limite:.1f}%",
        "Nomes das amostras: %s" % ("do arquivo de mapeamento" if mapeamento_usado
                                    else "código do arquivo (sem mapeamento carregado)"),
        "",
    ]
    corpo = ("\n" + separador + "\n\n").join(blocos)
    return "\n".join(cabecalho) + "\n" + corpo


# ============================================================
# Nomes de arquivo
# ============================================================

_INVALIDOS = '<>:"/\\|?*'


def nome_de_arquivo(nome):
    """Transforma o nome da amostra em algo que o Windows aceite como
    nome de arquivo (o mapeamento pode trazer barra, dois-pontos, etc.)."""
    limpo = "".join("-" if c in _INVALIDOS or ord(c) < 32 else c for c in nome)
    return limpo.strip(" .") or "amostra"


def caminho_livre(pasta, base, extensao):
    """Um caminho que ainda não existe — nunca sobrescreve o que já está
    na pasta; se precisar, vai numerando: "Madeira (2).png"."""
    caminho = os.path.join(pasta, base + extensao)
    numero = 2
    while os.path.exists(caminho):
        caminho = os.path.join(pasta, "%s (%d)%s" % (base, numero, extensao))
        numero += 1
    return caminho


def pasta_da_exportacao(destino):
    """Cria e devolve a subpasta que vai receber os arquivos de uma
    exportação amostra por amostra.

    Sem isso, uma batelada de 60 amostras espalharia 120 arquivos soltos
    dentro da pasta escolhida, misturados com o que já estivesse lá.
    """
    base = "Amostras FRX %s" % date.today().isoformat()
    caminho = os.path.join(destino, base)
    numero = 2
    while os.path.exists(caminho):
        caminho = os.path.join(destino, "%s (%d)" % (base, numero))
        numero += 1
    os.makedirs(caminho)
    return caminho


def escrever_texto(caminho, texto):
    """Grava em UTF-8 com BOM: é o que faz o Bloco de Notas e o Excel do
    Windows mostrarem os acentos certos."""
    with open(caminho, "w", encoding="utf-8-sig", newline="\r\n") as f:
        f.write(texto)
    return caminho


# ============================================================
# Imagem compilada
# ============================================================

class PilhaDeImagens:
    """Junta as figuras das amostras numa imagem só, empilhadas.

    Guarda o desenho já rasterizado de cada figura (e não as figuras
    inteiras) porque a batelada pode ser grande e a figura do matplotlib
    é bem mais pesada que os pixels dela.
    """

    def __init__(self):
        self._partes = []

    def adicionar(self, fig):
        import numpy as np

        fig.canvas.draw()
        # sem o canal alfa: o fundo já é branco e assim a imagem final
        # ocupa 3/4 da memória
        self._partes.append(np.asarray(fig.canvas.buffer_rgba())[:, :, :3].copy())

    def __len__(self):
        return len(self._partes)

    def salvar(self, caminho):
        import numpy as np
        from matplotlib.image import imsave

        if not self._partes:
            return None
        largura = max(parte.shape[1] for parte in self._partes)
        if any(parte.shape[1] != largura for parte in self._partes):
            # figuras de larguras diferentes: completa com branco à direita
            self._partes = [
                np.pad(p, ((0, 0), (0, largura - p.shape[1]), (0, 0)), constant_values=255)
                for p in self._partes
            ]
        imsave(caminho, np.vstack(self._partes))
        return caminho
