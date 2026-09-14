# -*- coding: utf-8 -*-
"""Botões de canto arredondado no Tkinter.

O ttk não tem "raio da borda": o botão é desenhado pelo tema, e o tema
clam só sabe fazer retângulo. O jeito de fugir disso — o mesmo que os
temas prontos por aí usam — é trocar o DESENHO do fundo do botão por uma
imagem, com o elemento "image" do ttk.

A imagem é pequena e é esticada em três pedaços: as duas pontas (com os
cantos redondos) ficam intactas e só o miolo estica, na horizontal. É o
que o parâmetro `border` do `element_create` liga — sem ele, o canto
esticaria junto e viraria uma elipse.

Duas escolhas aqui são por DESEMPENHO, e não por gosto — as duas foram
medidas nesta janela, cronometrando o redesenho de um botão:

  * a imagem nasce já com a ALTURA que o botão vai ter, e o `sticky` só
    autoriza esticar na largura. Esticar nos dois eixos custava 110 ms
    por botão a cada redesenho; esticando só na largura, 4 ms. Era daí
    que vinha mais de um segundo de espera ao trocar de tema;
  * e o miolo dela é largo. O Tk estica repetindo a faixa do meio, e
    repetir uma faixa de 2 px até cobrir um botão de 280 px custava
    69 ms; com um miolo de 144 px, 3 ms. Gerar a imagem larga não custa
    quase nada porque só as pontas precisam da conta da curva — o meio
    é cor chapada;
  * a imagem é opaca: em vez de deixar o canto transparente, o pixel da
    curva já vem misturado com a cor do que fica ATRÁS do botão. Fica
    igualzinho (o fundo é uma cor chapada) e o Tk não precisa compor
    transparência a cada desenho — o que custava mais uns 5 ms por
    botão.

O botão continua sendo um `ttk.Button` comum: quem usa não muda nada, e
`state(["disabled"])`, texto, largura e comando seguem iguais.
"""

import base64
import struct
import tkinter as tk
import zlib

# Quantos pontos por pixel entram na conta da suavização: 4x4 = 16
# amostras já deixam a curva lisa e a imagem é pequena demais pra isso
# custar tempo perceptível.
AMOSTRAS = 4

# Largura do miolo da imagem — a parte que o Tk repete pra cobrir a
# largura do botão. Ver o cabeçalho: miolo estreito sai caro.
MIOLO = 144

# As imagens precisam de alguém que segure a referência: o Tk descarta a
# imagem no instante em que o Python solta o último nome dela, e o botão
# fica sem fundo. Este dicionário é esse alguém.
_IMAGENS = {}


def _cor(texto):
    """"#RRGGBB" -> (r, g, b)."""
    texto = texto.lstrip("#")
    return tuple(int(texto[i:i + 2], 16) for i in (0, 2, 4))


def _opacidade(x, y, largura, altura, raio):
    """Quanto do pixel (x, y) está dentro do retângulo arredondado, de 0
    a 1. É a suavização: o pixel do meio da curva sai meio misturado com
    o fundo, em vez de dentro ou fora."""
    dentro = 0
    for sy in range(AMOSTRAS):
        py = y + (sy + 0.5) / AMOSTRAS
        for sx in range(AMOSTRAS):
            px = x + (sx + 0.5) / AMOSTRAS
            # o ponto do canto mais próximo: fora dos cantos, a distância
            # dá zero e o pixel está sempre dentro
            cx = min(max(px, raio), largura - raio)
            cy = min(max(py, raio), altura - raio)
            if (px - cx) ** 2 + (py - cy) ** 2 <= raio * raio:
                dentro += 1
    return dentro / float(AMOSTRAS * AMOSTRAS)


def _png(altura, raio, cor, atras):
    """Um PNG opaco com o retângulo arredondado da cor pedida sobre o
    fundo `atras`, já em base64 — que é como o Tk aceita imagem binária.

    A largura é a das duas pontas mais o MIOLO. Só as pontas passam pela
    conta da curva; o meio é cor chapada, e a ponta direita é a esquerda
    espelhada.
    """
    r, g, b = _cor(cor)
    fr, fg, fb = _cor(atras)
    ponta = raio + 2
    largura = 2 * ponta + MIOLO
    cheio = bytes((r, g, b))
    linhas = []
    for y in range(altura):
        esquerda = []
        for x in range(ponta):
            a = _opacidade(x, y, largura, altura, raio)
            esquerda.append(bytes((int(round(r * a + fr * (1 - a))),
                                   int(round(g * a + fg * (1 - a))),
                                   int(round(b * a + fb * (1 - a))))))
        linha = bytearray()
        linha.append(0)                      # filtro "nenhum" da linha
        linha += b"".join(esquerda)
        linha += cheio * MIOLO
        linha += b"".join(reversed(esquerda))
        linhas.append(bytes(linha))

    def pedaco(tipo, dados):
        corpo = tipo + dados
        return (struct.pack(">I", len(dados)) + corpo
                + struct.pack(">I", zlib.crc32(corpo) & 0xFFFFFFFF))

    # tipo de cor 2 = RGB sem canal alfa
    cabecalho = struct.pack(">IIBBBBB", largura, altura, 8, 2, 0, 0, 0)
    arquivo = (b"\x89PNG\r\n\x1a\n"
               + pedaco(b"IHDR", cabecalho)
               + pedaco(b"IDAT", zlib.compress(b"".join(linhas), 9))
               + pedaco(b"IEND", b""))
    return base64.b64encode(arquivo)


def arredondar(root, style, estilo, cores_por_estado, chave, raio, recheio,
               atras, altura):
    """Faz o estilo de botão `estilo` ser desenhado com cantos de `raio`.

    `cores_por_estado` é {"normal": cor, "active": cor, "pressed": cor,
    "disabled": cor}; `atras` é a cor de trás do botão (é ela que o
    canto recebe) e `altura` é a altura que o botão vai ter, em pixels.
    `chave` identifica esse conjunto, pra imagem e elemento serem
    criados uma vez só — o ttk recusa criar dois elementos com o mesmo
    nome.
    """
    elemento = "fundo_%s" % chave
    if chave not in _IMAGENS:
        imagens = {estado: tk.PhotoImage(
            master=root, data=_png(altura, raio, cor, atras))
            for estado, cor in cores_por_estado.items()}
        _IMAGENS[chave] = imagens
        style.element_create(
            elemento, "image", imagens["normal"],
            ("disabled", imagens["disabled"]),
            ("pressed", imagens["pressed"]),
            ("active", imagens["active"]),
            # "ew": estica só na largura. Ver o cabeçalho do módulo —
            # autorizar o esticamento vertical aqui custa 110 ms por
            # botão a cada redesenho.
            border=raio + 1, sticky="ew", padding=0,
            # A imagem é larga (o miolo é o que o Tk repete), mas o
            # botão não deve nascer com essa largura toda: `width` diz
            # o mínimo que o elemento pede, e sem ele todo botão ficava
            # do tamanho da imagem.
            width=2 * (raio + 2), height=altura)

    # o desenho do botão passa a ser: a imagem por fora, o recheio e o
    # texto por dentro. Sai a borda e o relevo que o clam punha ali.
    style.layout(estilo, [
        (elemento, {"sticky": "nsew", "children": [
            ("Button.padding", {"sticky": "nsew", "children": [
                ("Button.label", {"sticky": "nsew"})]})]})])
    style.configure(estilo, padding=recheio)
