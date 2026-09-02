# -*- coding: utf-8 -*-
"""O banco de amostras: pastas editáveis e as medidas guardadas nelas.

Esta é a camada de DADOS do banco — abre o arquivo, cria/move/apaga
pasta, guarda e devolve amostra. Não sabe que existe janela: dá para usar
num script.

    from catalogador.banco import BancoDeAmostras, caminho_padrao

    banco = BancoDeAmostras(caminho_padrao())
    madeira = banco.criar_pasta(banco.RAIZ_ID, "Madeira")
    cinza = banco.criar_pasta(madeira, "Cinza")
    banco.adicionar_amostra(cinza, nome="Cinza 12",
                            elementos=parse_frx_file("081025af.txt"))
    for amostra in banco.amostras(madeira, recursivo=True):
        print(amostra["nome"], banco.elementos(amostra["id"]))

Tudo o que mexe em várias linhas de uma vez (apagar uma sub-árvore,
importar uma batelada) acontece dentro de UMA transação: ou entra tudo,
ou não entra nada. Um travamento no meio da importação não deixa meia
amostra no banco.
"""

import hashlib
import json
import os
import sqlite3
from datetime import datetime

from ..nucleo.tabela_periodica import PERIODIC_TABLE
from .esquema import ARVORE_INICIAL, ESQUEMA, RAIZ_ID, RAIZ_NOME, VERSAO


class ErroDoBanco(Exception):
    """Erro que a interface pode mostrar direto para o usuário: nome
    repetido, pasta que não pode ser apagada, etc."""


# ============================================================
# Onde mora o banco
# ============================================================

def pasta_base():
    """A pasta do usuário onde o programa guarda as coisas dele."""
    return os.path.join(os.path.expanduser("~"), "Catalogador FRX")


def caminho_padrao():
    """O banco que o programa abre sozinho quando ninguém escolheu outro."""
    return os.path.join(pasta_base(), "amostras.db")


def _arquivo_de_config():
    return os.path.join(pasta_base(), "config.json")


def caminho_lembrado():
    """O último banco aberto — para o programa reabrir o mesmo amanhã.

    Se o arquivo de configuração sumiu, veio corrompido, ou aponta para
    um banco que não existe mais (um pendrive que saiu, uma pasta de rede
    fora do ar), cai no banco padrão em vez de dar erro na abertura.
    """
    try:
        with open(_arquivo_de_config(), encoding="utf-8") as f:
            caminho = json.load(f).get("banco")
    except (OSError, ValueError, AttributeError):
        return caminho_padrao()
    if caminho and os.path.exists(caminho):
        return caminho
    return caminho_padrao()


def lembrar_caminho(caminho):
    """Anota qual banco está aberto. Falhar aqui não é motivo para o
    programa parar — na pior das hipóteses ele reabre no banco padrão."""
    try:
        os.makedirs(pasta_base(), exist_ok=True)
        with open(_arquivo_de_config(), "w", encoding="utf-8") as f:
            json.dump({"banco": caminho}, f, ensure_ascii=False, indent=2)
    except OSError:
        pass


# ============================================================
# O banco
# ============================================================

def impressao_da_medida(elementos):
    """Um resumo curto e estável dos números de uma medida.

    É o que impede a mesma amostra de entrar duas vezes no banco: renomear
    o .txt não muda a impressão, porque ela olha só para os pares
    (elemento, área). Duas medidas de verdade nunca batem na sexta casa
    decimal de todos os elementos ao mesmo tempo.
    """
    partes = ";".join("%d=%.6f" % (int(e["z"]), float(e["area"]))
                      for e in sorted(elementos, key=lambda e: int(e["z"])))
    return hashlib.sha1(partes.encode("utf-8")).hexdigest()


class BancoDeAmostras:
    """Um arquivo `.db` aberto. Crie um por banco e feche no final."""

    RAIZ_ID = RAIZ_ID

    def __init__(self, caminho):
        self.caminho = caminho
        destino = os.path.dirname(os.path.abspath(caminho))
        if destino:
            os.makedirs(destino, exist_ok=True)
        self.con = sqlite3.connect(caminho)
        self.con.row_factory = sqlite3.Row
        self.con.execute("PRAGMA foreign_keys = ON")
        # WAL deixa ler enquanto outro escreve. Em pasta de rede o SQLite
        # não consegue usá-lo (precisa de memória compartilhada entre os
        # processos) e recusa — aí seguimos no modo normal, que funciona
        # em qualquer lugar.
        try:
            self.con.execute("PRAGMA journal_mode = WAL")
        except sqlite3.DatabaseError:
            pass
        self._preparar()

    # ---------- abertura e migração ----------

    def _preparar(self):
        versao = self.con.execute("PRAGMA user_version").fetchone()[0]
        if versao == 0 and not self._ja_tem_tabelas():
            self._criar_do_zero()
        elif versao > VERSAO:
            raise ErroDoBanco(
                "Este banco foi criado por uma versão mais nova do programa "
                "(formato %d, este entende até o %d). Atualize o programa "
                "antes de abri-lo." % (versao, VERSAO))
        # (quando o formato mudar, as migrações de versão entram aqui)

    def _ja_tem_tabelas(self):
        return self.con.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='pastas'"
        ).fetchone() is not None

    def _criar_do_zero(self):
        with self.con:
            self.con.executescript(ESQUEMA)
            self.con.execute(
                "INSERT INTO pastas (id, pai_id, nome, ordem) VALUES (?, NULL, ?, 0)",
                (RAIZ_ID, RAIZ_NOME))
            self._semear(RAIZ_ID, ARVORE_INICIAL)
            self.con.execute("PRAGMA user_version = %d" % VERSAO)

    def _semear(self, pai_id, ramos):
        for ordem, (nome, filhos) in enumerate(ramos):
            cur = self.con.execute(
                "INSERT INTO pastas (pai_id, nome, ordem) VALUES (?, ?, ?)",
                (pai_id, nome, ordem))
            self._semear(cur.lastrowid, filhos)

    def fechar(self):
        self.con.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.fechar()

    # ============================================================
    # Pastas
    # ============================================================

    def pasta(self, pasta_id):
        linha = self.con.execute(
            "SELECT id, pai_id, nome, ordem FROM pastas WHERE id = ?",
            (pasta_id,)).fetchone()
        if linha is None:
            raise ErroDoBanco("Essa pasta não existe mais no banco.")
        return dict(linha)

    def filhas(self, pai_id):
        """As subpastas diretas de uma pasta, na ordem em que devem
        aparecer. Uma consulta por nível — é o que faz a árvore poder ser
        carregada só onde o usuário abriu, sem ler o banco inteiro."""
        return [dict(l) for l in self.con.execute(
            "SELECT id, pai_id, nome, ordem FROM pastas WHERE pai_id = ? "
            "ORDER BY ordem, nome COLLATE NOCASE", (pai_id,))]

    def filhas_com_resumo(self, pai_id):
        """As subpastas diretas já com quantas subpastas e quantas
        amostras cada uma tem DIRETAMENTE dentro.

        É o que a árvore da janela precisa para saber quem tem conteúdo
        (e portanto merece a setinha de expandir) sem uma consulta por
        pasta: uma consulta por NÍVEL, e só nos níveis que o usuário
        abriu. As duas subconsultas caem nos índices `ix_pastas_pai` e
        `ix_amostras_pasta`.
        """
        return [dict(l) for l in self.con.execute("""
            SELECT p.id, p.pai_id, p.nome, p.ordem,
                   (SELECT COUNT(*) FROM pastas f WHERE f.pai_id = p.id)
                       AS n_subpastas,
                   (SELECT COUNT(*) FROM amostras a WHERE a.pasta_id = p.id)
                       AS n_amostras
              FROM pastas p
             WHERE p.pai_id = ?
             ORDER BY p.ordem, p.nome COLLATE NOCASE
        """, (pai_id,))]

    def criar_pasta(self, pai_id, nome):
        nome = (nome or "").strip()
        if not nome:
            raise ErroDoBanco("A pasta precisa de um nome.")
        self.pasta(pai_id)  # confere que o pai existe
        proxima = self.con.execute(
            "SELECT COALESCE(MAX(ordem), -1) + 1 FROM pastas WHERE pai_id = ?",
            (pai_id,)).fetchone()[0]
        try:
            with self.con:
                cur = self.con.execute(
                    "INSERT INTO pastas (pai_id, nome, ordem) VALUES (?, ?, ?)",
                    (pai_id, nome, proxima))
        except sqlite3.IntegrityError:
            raise ErroDoBanco('Já existe uma pasta "%s" aqui dentro.' % nome)
        return cur.lastrowid

    def renomear_pasta(self, pasta_id, nome):
        nome = (nome or "").strip()
        if not nome:
            raise ErroDoBanco("A pasta precisa de um nome.")
        if pasta_id == RAIZ_ID:
            raise ErroDoBanco("A pasta raiz não pode ser renomeada.")
        try:
            with self.con:
                self.con.execute("UPDATE pastas SET nome = ? WHERE id = ?",
                                 (nome, pasta_id))
        except sqlite3.IntegrityError:
            raise ErroDoBanco('Já existe uma pasta "%s" nesse mesmo lugar.' % nome)

    def mover_pasta(self, pasta_id, novo_pai_id):
        """Pendura a pasta (com tudo o que tem dentro) em outro lugar.

        É UM update: a sub-árvore inteira acompanha sozinha, porque
        ninguém guarda o caminho completo.
        """
        if pasta_id == RAIZ_ID:
            raise ErroDoBanco("A pasta raiz não pode ser movida.")
        if pasta_id == novo_pai_id:
            raise ErroDoBanco("Uma pasta não pode ser guardada dentro dela mesma.")
        if novo_pai_id in self.descendentes(pasta_id):
            raise ErroDoBanco("Uma pasta não pode ser guardada dentro de uma "
                              "subpasta dela mesma.")
        if self.pasta(pasta_id)["pai_id"] == novo_pai_id:
            return
        proxima = self.con.execute(
            "SELECT COALESCE(MAX(ordem), -1) + 1 FROM pastas WHERE pai_id = ?",
            (novo_pai_id,)).fetchone()[0]
        try:
            with self.con:
                self.con.execute(
                    "UPDATE pastas SET pai_id = ?, ordem = ? WHERE id = ?",
                    (novo_pai_id, proxima, pasta_id))
        except sqlite3.IntegrityError:
            raise ErroDoBanco("O destino já tem uma pasta com esse nome. "
                              "Renomeie uma das duas antes de mover.")

    def trocar_ordem(self, pasta_id, direcao):
        """Sobe (-1) ou desce (+1) a pasta entre as irmãs dela. É o que
        define a numeração 1.1, 1.2, 1.3… que aparece na janela."""
        atual = self.pasta(pasta_id)
        irmas = self.filhas(atual["pai_id"])
        posicao = next(i for i, p in enumerate(irmas) if p["id"] == pasta_id)
        vizinha = posicao + direcao
        if not 0 <= vizinha < len(irmas):
            return False
        irmas[posicao], irmas[vizinha] = irmas[vizinha], irmas[posicao]
        with self.con:
            self.con.executemany("UPDATE pastas SET ordem = ? WHERE id = ?",
                                 [(i, p["id"]) for i, p in enumerate(irmas)])
        return True

    def descendentes(self, pasta_id, incluir_a_propria=False):
        """Os ids de tudo o que está pendurado nesta pasta, em qualquer
        profundidade. Quem desce a árvore é o SQLite (WITH RECURSIVE), não
        o Python: uma consulta só, independente do tamanho."""
        linhas = self.con.execute("""
            WITH RECURSIVE sub(id) AS (
                SELECT id FROM pastas WHERE pai_id = ?
                UNION ALL
                SELECT p.id FROM pastas p JOIN sub ON p.pai_id = sub.id
            )
            SELECT id FROM sub
        """, (pasta_id,)).fetchall()
        ids = {l[0] for l in linhas}
        if incluir_a_propria:
            ids.add(pasta_id)
        return ids

    def ancestrais(self, pasta_id):
        """Os ids das pastas da raiz até esta, nessa ordem.

        É o caminho que a janela precisa percorrer para deixar uma pasta
        visível: as pastas acima dela podem nunca ter sido abertas, então
        não adianta procurar na árvore que está na tela — quem sabe o
        caminho é o banco.
        """
        return [l[0] for l in self.con.execute("""
            WITH RECURSIVE acima(id, pai_id, nivel) AS (
                SELECT id, pai_id, 0 FROM pastas WHERE id = ?
                UNION ALL
                SELECT p.id, p.pai_id, acima.nivel + 1
                  FROM pastas p JOIN acima ON p.id = acima.pai_id
            )
            SELECT id FROM acima ORDER BY nivel DESC
        """, (pasta_id,))]

    def caminho_da_pasta(self, pasta_id, separador=" / "):
        """"Madeira / In natura / Pó" — o caminho legível, para mostrar na
        tela e escrever no cabeçalho das tabelas exportadas."""
        nomes = [l[0] for l in self.con.execute("""
            WITH RECURSIVE acima(id, pai_id, nome, nivel) AS (
                SELECT id, pai_id, nome, 0 FROM pastas WHERE id = ?
                UNION ALL
                SELECT p.id, p.pai_id, p.nome, acima.nivel + 1
                  FROM pastas p JOIN acima ON p.id = acima.pai_id
            )
            SELECT nome FROM acima WHERE id <> ? ORDER BY nivel DESC
        """, (pasta_id, RAIZ_ID))]
        return separador.join(nomes) if nomes else RAIZ_NOME

    def resumo(self, pasta_id):
        """(quantas subpastas, quantas amostras) contando tudo o que está
        pendurado abaixo — é o "(12)" que aparece ao lado do nome."""
        sub = self.descendentes(pasta_id, incluir_a_propria=True)
        marcadores = ",".join("?" * len(sub))
        amostras = self.con.execute(
            "SELECT COUNT(*) FROM amostras WHERE pasta_id IN (%s)" % marcadores,
            tuple(sub)).fetchone()[0]
        return len(sub) - 1, amostras

    def contagem_direta(self, pasta_id):
        return self.con.execute(
            "SELECT COUNT(*) FROM amostras WHERE pasta_id = ?",
            (pasta_id,)).fetchone()[0]

    def excluir_pasta(self, pasta_id, com_amostras=False):
        """Apaga a pasta e tudo o que está dentro dela.

        Com `com_amostras=False` (o padrão), recusa se houver qualquer
        amostra na sub-árvore: apagar 40 medidas sem querer, por um clique
        errado, não é um acidente que dá para desfazer.
        """
        if pasta_id == RAIZ_ID:
            raise ErroDoBanco("A pasta raiz não pode ser apagada.")
        sub = self.descendentes(pasta_id, incluir_a_propria=True)
        marcadores = ",".join("?" * len(sub))
        quantas = self.con.execute(
            "SELECT COUNT(*) FROM amostras WHERE pasta_id IN (%s)" % marcadores,
            tuple(sub)).fetchone()[0]
        if quantas and not com_amostras:
            raise ErroDoBanco(
                "Essa pasta (ou uma subpasta dela) ainda tem %d amostra(s)." % quantas)
        with self.con:
            if quantas:
                self.con.execute(
                    "DELETE FROM amostras WHERE pasta_id IN (%s)" % marcadores,
                    tuple(sub))
            # as subpastas somem junto (ON DELETE CASCADE)
            self.con.execute("DELETE FROM pastas WHERE id = ?", (pasta_id,))
        return quantas

    # ============================================================
    # Amostras
    # ============================================================

    def adicionar_amostra(self, pasta_id, nome, elementos, codigo="",
                          tubo="Nenhum", observacoes="", origem=""):
        """Guarda uma medida. Devolve (id, entrou_agora).

        Se a mesma medida já estiver no banco, não duplica: devolve o id
        de quem já estava e `False` — é o que deixa reimportar uma pasta
        inteira de .txt sem medo.
        """
        if not elementos:
            raise ErroDoBanco("A amostra %s não tem nenhum elemento lido." % nome)
        self.pasta(pasta_id)
        impressao = impressao_da_medida(elementos)
        ja = self.con.execute("SELECT id FROM amostras WHERE impressao = ?",
                              (impressao,)).fetchone()
        if ja is not None:
            return ja[0], False
        with self.con:
            cur = self.con.execute(
                "INSERT INTO amostras (pasta_id, nome, codigo, tubo, observacoes,"
                " origem, impressao, criado_em) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (pasta_id, nome.strip() or codigo or "amostra", codigo, tubo,
                 observacoes, origem, impressao,
                 datetime.now().isoformat(" ", "seconds")))
            amostra_id = cur.lastrowid
            self.con.executemany(
                "INSERT INTO leituras (amostra_id, z, area) VALUES (?, ?, ?)",
                [(amostra_id, int(e["z"]), float(e["area"])) for e in elementos])
        return amostra_id, True

    def amostra(self, amostra_id):
        linha = self.con.execute("SELECT * FROM amostras WHERE id = ?",
                                 (amostra_id,)).fetchone()
        if linha is None:
            raise ErroDoBanco("Essa amostra não está mais no banco.")
        return dict(linha)

    def amostras(self, pasta_id, recursivo=False, busca=None):
        """As amostras de uma pasta — só as dela, ou as da sub-árvore
        inteira. `busca` filtra por nome ou por código do arquivo."""
        condicoes, valores = [], []
        if recursivo:
            sub = self.descendentes(pasta_id, incluir_a_propria=True)
            condicoes.append("a.pasta_id IN (%s)" % ",".join("?" * len(sub)))
            valores.extend(sub)
        else:
            condicoes.append("a.pasta_id = ?")
            valores.append(pasta_id)
        if busca:
            condicoes.append("(a.nome LIKE ? OR a.codigo LIKE ?)")
            valores.extend(["%%%s%%" % busca] * 2)
        return [dict(l) for l in self.con.execute(
            "SELECT a.* FROM amostras a WHERE %s "
            "ORDER BY a.nome COLLATE NOCASE, a.id" % " AND ".join(condicoes),
            valores)]

    def procurar(self, texto, limite=500):
        """Busca por nome/código no banco inteiro, venha de que pasta vier."""
        alvo = "%%%s%%" % texto
        return [dict(l) for l in self.con.execute(
            "SELECT * FROM amostras WHERE nome LIKE ? OR codigo LIKE ? "
            "ORDER BY nome COLLATE NOCASE LIMIT ?", (alvo, alvo, limite))]

    def elementos(self, amostra_id):
        """Os elementos de uma amostra, no mesmo formato que sai do .txt
        — `[{"z", "symbol", "area"}]` —, para as camadas de cima não
        precisarem saber de onde a amostra veio."""
        return [{"z": z, "symbol": PERIODIC_TABLE.get(z, "Z%d" % z), "area": area}
                for z, area in self.con.execute(
                    "SELECT z, area FROM leituras WHERE amostra_id = ? ORDER BY z",
                    (amostra_id,))]

    def atualizar_amostra(self, amostra_id, **campos):
        """Muda nome, tubo e/ou observações de uma amostra."""
        permitidos = [c for c in ("nome", "tubo", "observacoes") if c in campos]
        if not permitidos:
            return
        if "nome" in permitidos and not (campos["nome"] or "").strip():
            raise ErroDoBanco("A amostra precisa de um nome.")
        with self.con:
            self.con.execute(
                "UPDATE amostras SET %s WHERE id = ?"
                % ", ".join("%s = ?" % c for c in permitidos),
                [campos[c] for c in permitidos] + [amostra_id])

    def mover_amostra(self, amostra_id, pasta_id):
        self.pasta(pasta_id)
        with self.con:
            self.con.execute("UPDATE amostras SET pasta_id = ? WHERE id = ?",
                             (pasta_id, amostra_id))

    def excluir_amostra(self, amostra_id):
        # as leituras somem junto (ON DELETE CASCADE)
        with self.con:
            self.con.execute("DELETE FROM amostras WHERE id = ?", (amostra_id,))

    def total_de_amostras(self):
        return self.con.execute("SELECT COUNT(*) FROM amostras").fetchone()[0]
