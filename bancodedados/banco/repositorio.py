# -*- coding: utf-8 -*-
"""O banco de amostras: abre o arquivo, guarda e devolve o que há nele.

Esta é a camada de DADOS do banco. Não sabe que existe janela: dá para
usar num script.

    from bancodedados.banco import BancoDeAmostras

    with BancoDeAmostras("madeira.db", criar=True) as banco:
        amostra, _ = banco.obter_ou_criar_amostra("M003")
        banco.guardar_medicao(amostra, tubo="Prata — Ag", codigo="061025ab",
                              leituras=[(26, 15797.0, "majoritário"), ...],
                              limite=10.0, tabela=texto, imagem=png_bytes)
        for a in banco.amostras():
            print(a["nome"], a["tubos"])

Tudo o que mexe em várias linhas de uma vez (importar uma planilha,
apagar uma amostra com as medições) acontece dentro de UMA transação:
ou entra tudo, ou não entra nada.
"""

import hashlib
import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime

from ..nucleo.tabela_periodica import PERIODIC_TABLE
from .esquema import (DESCARTADO, ESQUEMA, MAJORITARIO, TECNICA_NOME,
                      TECNICA_SIGLA, TRACO, VERSAO)

# A ordem em que os tubos aparecem (nas telas e no JSON): a ordem em que
# o laboratório costuma medir.
ORDEM_DOS_TUBOS = ("Ag", "Rh", "Au", "Nenhum")


class ErroDoBanco(Exception):
    """Erro que a interface pode mostrar direto para o usuário: nome
    repetido, arquivo que não é um banco, etc."""


# ============================================================
# Ajudantes
# ============================================================

def simbolo_do_tubo(tubo):
    """"Prata — Ag" -> "Ag"; "Nenhum" -> "Nenhum". É a chave curta que o
    JSON e os cartões usam."""
    if not tubo or tubo == "Nenhum":
        return "Nenhum"
    return tubo.rsplit("—", 1)[-1].strip() or tubo


def ordem_do_tubo(tubo):
    simbolo = simbolo_do_tubo(tubo)
    return (ORDEM_DOS_TUBOS.index(simbolo) if simbolo in ORDEM_DOS_TUBOS
            else len(ORDEM_DOS_TUBOS))


def normalizar_nome(nome):
    """A forma pela qual dois nomes são considerados o mesmo: sem
    maiúscula/minúscula e sem espaço — "MAD 1", "mad1" e "Mad 1 " são a
    mesma amostra na planilha de quem digita à mão."""
    return "".join(str(nome or "").split()).casefold()


def impressao_da_medida(leituras):
    """Um resumo curto e estável dos números de uma medição.

    É o que impede a mesma medida de entrar duas vezes no banco: renomear
    o .txt ou mudar o limite do traço não muda a impressão, porque ela
    olha só para os pares (elemento, valor).
    """
    partes = ";".join("%d=%.6f" % (int(l[0]), float(l[1]))
                      for l in sorted(leituras, key=lambda l: int(l[0])))
    return hashlib.sha1(partes.encode("utf-8")).hexdigest()


def _agora():
    return datetime.now().isoformat(" ", "seconds")


# ============================================================
# Onde o programa anota os bancos abertos
# ============================================================

def pasta_base():
    """A pasta do usuário onde o programa guarda as coisas dele."""
    return os.path.join(os.path.expanduser("~"), "Catalogador XRF")


def _arquivo_de_config():
    return os.path.join(pasta_base(), "config.json")


def bancos_lembrados():
    """Os bancos que estavam abertos da última vez — o programa reabre
    os mesmos. Um que sumiu (pendrive, pasta de rede) só fica de fora."""
    try:
        with open(_arquivo_de_config(), encoding="utf-8") as f:
            caminhos = json.load(f).get("bancos", [])
    except (OSError, ValueError, AttributeError):
        return []
    return [c for c in caminhos if isinstance(c, str) and os.path.exists(c)]


def lembrar_bancos(caminhos):
    """Falhar aqui não é motivo para o programa parar — na pior das
    hipóteses ele abre sem banco nenhum da próxima vez."""
    try:
        os.makedirs(pasta_base(), exist_ok=True)
        with open(_arquivo_de_config(), "w", encoding="utf-8") as f:
            json.dump({"bancos": list(caminhos)}, f, ensure_ascii=False, indent=2)
    except OSError:
        pass


# ============================================================
# O banco
# ============================================================

class BancoDeAmostras:
    """Um arquivo `.db` aberto. Crie um por banco e feche no final."""

    def __init__(self, caminho, criar=False):
        self.caminho = os.path.abspath(caminho)
        if not criar and not os.path.exists(self.caminho):
            raise ErroDoBanco("O arquivo não existe:\n%s" % self.caminho)
        destino = os.path.dirname(self.caminho)
        if destino:
            os.makedirs(destino, exist_ok=True)
        self.con = sqlite3.connect(self.caminho)
        self.con.row_factory = sqlite3.Row
        self._transacoes = 0   # quantos `transacao()` estão abertos
        self.con.execute("PRAGMA foreign_keys = ON")
        try:
            self._preparar()
        except sqlite3.DatabaseError:
            self.con.close()
            raise ErroDoBanco("Este arquivo não é um banco de amostras:\n%s"
                              % self.caminho)

    # ---------- abertura ----------

    def _preparar(self):
        versao = self.con.execute("PRAGMA user_version").fetchone()[0]
        if versao == 0 and not self._ja_tem_tabelas():
            self._criar_do_zero()
        elif versao == 0:
            raise ErroDoBanco(
                "Este arquivo é um banco SQLite, mas não foi criado por este "
                "programa (as tabelas dele são outras).")
        elif versao > VERSAO:
            raise ErroDoBanco(
                "Este banco foi criado por uma versão mais nova do programa "
                "(formato %d, este entende até o %d). Atualize o programa "
                "antes de abri-lo." % (versao, VERSAO))
        elif versao < VERSAO:
            self._migrar(versao)

    def _migrar(self, versao):
        """Traz um banco de formato antigo para o de agora, um degrau
        por vez, numa transação só."""
        with self.con:  # (antes de `transacao()` valer)
            if versao < 2:
                self.con.execute(
                    "ALTER TABLE amostras ADD COLUMN chave TEXT NOT NULL DEFAULT ''")
                self.con.executemany(
                    "UPDATE amostras SET chave = ? WHERE id = ?",
                    [(normalizar_nome(l["nome"]), l["id"])
                     for l in self.con.execute("SELECT id, nome FROM amostras")])
                self.con.execute(
                    "CREATE UNIQUE INDEX IF NOT EXISTS ux_amostras_chave ON amostras (chave)")
            if versao < 3:
                self.con.execute("ALTER TABLE leituras ADD COLUMN energia REAL")
                # a tabela nova, tal como está no esquema
                inicio = ESQUEMA.index("CREATE TABLE espectros")
                self.con.executescript(ESQUEMA[inicio:])
            self.con.execute("PRAGMA user_version = %d" % VERSAO)

    def _ja_tem_tabelas(self):
        return self.con.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table'").fetchone() is not None

    def _criar_do_zero(self):
        nome = os.path.splitext(os.path.basename(self.caminho))[0]
        with self.con:  # (antes de `transacao()` valer)
            self.con.executescript(ESQUEMA)
            self.con.executemany(
                "INSERT INTO meta (chave, valor) VALUES (?, ?)",
                [("nome", nome), ("tecnica_sigla", TECNICA_SIGLA),
                 ("tecnica_nome", TECNICA_NOME), ("criado_em", _agora())])
            self.con.execute("PRAGMA user_version = %d" % VERSAO)

    def fechar(self):
        self.con.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.fechar()

    @contextmanager
    def transacao(self):
        """Junta várias operações numa transação só.

            with banco.transacao():
                for bloco in blocos:
                    banco.guardar_medicao(...)

        Cada operação do banco já é atômica sozinha; o que isto muda é
        o CUSTO: cada commit é uma escrita sincronizada no disco, e
        importar 60 medições com 60 commits demorava mais que com um.
        Pode aninhar — só a transação de fora é que grava (ou desfaz
        tudo, se algo der errado).
        """
        if self._transacoes:
            self._transacoes += 1
            try:
                yield
            finally:
                self._transacoes -= 1
            return
        self._transacoes = 1
        try:
            with self.con:
                yield
        finally:
            self._transacoes = 0

    def salvar_copia(self, caminho):
        """Grava uma cópia íntegra do banco em outro arquivo — é o
        "baixar o .db". Usa o backup do próprio SQLite, que copia o
        banco consistente mesmo com transação no meio."""
        caminho = os.path.abspath(caminho)
        if caminho == self.caminho:
            raise ErroDoBanco("Esse já é o arquivo do banco aberto.")
        if os.path.exists(caminho):
            os.remove(caminho)
        destino = sqlite3.connect(caminho)
        try:
            with destino:
                self.con.backup(destino)
        finally:
            destino.close()
        return caminho

    # ---------- meta ----------

    def meta(self, chave, padrao=""):
        linha = self.con.execute("SELECT valor FROM meta WHERE chave = ?",
                                 (chave,)).fetchone()
        return padrao if linha is None else linha[0]

    def definir_meta(self, chave, valor):
        with self.transacao():
            self.con.execute(
                "INSERT INTO meta (chave, valor) VALUES (?, ?) "
                "ON CONFLICT(chave) DO UPDATE SET valor = excluded.valor",
                (chave, str(valor)))

    @property
    def nome(self):
        """O título da aba. Nasce igual ao nome do arquivo."""
        return self.meta("nome") or os.path.splitext(os.path.basename(self.caminho))[0]

    @nome.setter
    def nome(self, valor):
        valor = (valor or "").strip()
        if not valor:
            raise ErroDoBanco("O banco precisa de um nome.")
        self.definir_meta("nome", valor)

    def tecnica(self):
        return {"sigla": self.meta("tecnica_sigla", TECNICA_SIGLA),
                "nome": self.meta("tecnica_nome", TECNICA_NOME)}

    # ============================================================
    # Categorias
    # ============================================================

    def categorias(self):
        """[{"id", "nome", "ordem"}], na ordem em que aparecem."""
        return [dict(l) for l in self.con.execute(
            "SELECT id, nome, ordem FROM categorias ORDER BY ordem, id")]

    def categoria_por_nome(self, nome):
        linha = self.con.execute(
            "SELECT id FROM categorias WHERE nome = ? COLLATE NOCASE",
            ((nome or "").strip(),)).fetchone()
        return None if linha is None else linha[0]

    def criar_categoria(self, nome):
        """Cria a categoria (ou devolve a que já existe com esse nome)."""
        nome = (nome or "").strip()
        if not nome:
            raise ErroDoBanco("A categoria precisa de um nome.")
        existente = self.categoria_por_nome(nome)
        if existente is not None:
            return existente
        proxima = self.con.execute(
            "SELECT COALESCE(MAX(ordem), -1) + 1 FROM categorias").fetchone()[0]
        with self.transacao():
            cur = self.con.execute(
                "INSERT INTO categorias (nome, ordem) VALUES (?, ?)", (nome, proxima))
        return cur.lastrowid

    def renomear_categoria(self, categoria_id, nome):
        nome = (nome or "").strip()
        if not nome:
            raise ErroDoBanco("A categoria precisa de um nome.")
        try:
            with self.transacao():
                self.con.execute("UPDATE categorias SET nome = ? WHERE id = ?",
                                 (nome, categoria_id))
        except sqlite3.IntegrityError:
            raise ErroDoBanco('Já existe uma categoria "%s".' % nome)

    def mover_categoria(self, categoria_id, direcao):
        """Sobe (-1) ou desce (+1) a categoria na lista."""
        lista = self.categorias()
        posicao = next((i for i, c in enumerate(lista) if c["id"] == categoria_id), None)
        if posicao is None:
            return False
        vizinha = posicao + direcao
        if not 0 <= vizinha < len(lista):
            return False
        lista[posicao], lista[vizinha] = lista[vizinha], lista[posicao]
        with self.transacao():
            self.con.executemany("UPDATE categorias SET ordem = ? WHERE id = ?",
                                 [(i, c["id"]) for i, c in enumerate(lista)])
        return True

    def excluir_categoria(self, categoria_id):
        """Apaga a categoria e os valores dela em todas as amostras.
        Devolve quantas amostras tinham algo escrito nela."""
        quantas = self.con.execute(
            "SELECT COUNT(*) FROM atributos WHERE categoria_id = ? AND valor <> ''",
            (categoria_id,)).fetchone()[0]
        with self.transacao():
            self.con.execute("DELETE FROM categorias WHERE id = ?", (categoria_id,))
        return quantas

    # ============================================================
    # Amostras
    # ============================================================

    def amostras(self, busca=None):
        """Todas as amostras, com um resumo de cada: quantas medições e
        com que tubos, se tem foto. `busca` filtra por nome, código do
        .txt ou qualquer valor de categoria."""
        condicao, valores = "", []
        if busca:
            alvo = "%%%s%%" % busca.strip()
            condicao = """
             WHERE a.nome LIKE ?
                OR EXISTS (SELECT 1 FROM medicoes m
                            WHERE m.amostra_id = a.id AND m.codigo LIKE ?)
                OR EXISTS (SELECT 1 FROM espectros e
                            WHERE e.amostra_id = a.id AND e.codigo LIKE ?)
                OR EXISTS (SELECT 1 FROM atributos t
                            WHERE t.amostra_id = a.id AND t.valor LIKE ?)"""
            valores = [alvo, alvo, alvo, alvo]
        linhas = self.con.execute("""
            SELECT a.id, a.nome, a.criado_em, (a.foto IS NOT NULL) AS tem_foto,
                   (SELECT GROUP_CONCAT(tubo, '|') FROM medicoes m
                     WHERE m.amostra_id = a.id) AS tubos,
                   (SELECT COUNT(*) FROM espectros e
                     WHERE e.amostra_id = a.id) AS espectros
              FROM amostras a %s
             ORDER BY a.nome COLLATE NOCASE
        """ % condicao, valores).fetchall()
        saida = []
        for l in linhas:
            tubos = sorted({simbolo_do_tubo(t) for t in (l["tubos"] or "").split("|") if t},
                           key=ordem_do_tubo)
            saida.append({"id": l["id"], "nome": l["nome"], "criado_em": l["criado_em"],
                          "tem_foto": bool(l["tem_foto"]), "tubos": tubos,
                          "espectros": l["espectros"]})
        return saida

    def amostra(self, amostra_id):
        linha = self.con.execute(
            "SELECT id, nome, criado_em, (foto IS NOT NULL) AS tem_foto "
            "FROM amostras WHERE id = ?", (amostra_id,)).fetchone()
        if linha is None:
            raise ErroDoBanco("Essa amostra não está mais no banco.")
        return dict(linha)

    def amostra_por_nome(self, nome):
        """O id da amostra com esse nome (ignorando maiúsculas e
        espaços), ou None. É uma busca pelo índice da chave."""
        alvo = normalizar_nome(nome)
        if not alvo:
            return None
        linha = self.con.execute("SELECT id FROM amostras WHERE chave = ?",
                                 (alvo,)).fetchone()
        return None if linha is None else linha[0]

    def criar_amostra(self, nome):
        nome = (nome or "").strip()
        if not nome:
            raise ErroDoBanco("A amostra precisa de um nome.")
        try:
            with self.transacao():
                cur = self.con.execute(
                    "INSERT INTO amostras (nome, chave, criado_em) VALUES (?, ?, ?)",
                    (nome, normalizar_nome(nome), _agora()))
        except sqlite3.IntegrityError:
            raise ErroDoBanco('Já existe uma amostra "%s" neste banco.' % nome)
        return cur.lastrowid

    def obter_ou_criar_amostra(self, nome):
        """Devolve (id, criada_agora)."""
        existente = self.amostra_por_nome(nome)
        if existente is not None:
            return existente, False
        return self.criar_amostra(nome), True

    def renomear_amostra(self, amostra_id, nome):
        nome = (nome or "").strip()
        if not nome:
            raise ErroDoBanco("A amostra precisa de um nome.")
        outra = self.amostra_por_nome(nome)
        if outra is not None and outra != amostra_id:
            raise ErroDoBanco('Já existe uma amostra "%s" neste banco.' % nome)
        with self.transacao():
            self.con.execute("UPDATE amostras SET nome = ?, chave = ? WHERE id = ?",
                             (nome, normalizar_nome(nome), amostra_id))

    def excluir_amostra(self, amostra_id):
        # atributos, medições e leituras somem junto (ON DELETE CASCADE)
        with self.transacao():
            self.con.execute("DELETE FROM amostras WHERE id = ?", (amostra_id,))

    def total_de_amostras(self):
        return self.con.execute("SELECT COUNT(*) FROM amostras").fetchone()[0]

    def total_de_medicoes(self):
        return self.con.execute("SELECT COUNT(*) FROM medicoes").fetchone()[0]

    # ---------- foto ----------

    def foto(self, amostra_id):
        linha = self.con.execute("SELECT foto FROM amostras WHERE id = ?",
                                 (amostra_id,)).fetchone()
        return None if linha is None else linha[0]

    def definir_foto(self, amostra_id, dados):
        """`dados` são os bytes da imagem, ou None para tirar a foto."""
        with self.transacao():
            self.con.execute("UPDATE amostras SET foto = ? WHERE id = ?",
                             (dados, amostra_id))

    # ---------- atributos (os valores das categorias) ----------

    def atributos(self, amostra_id):
        """{categoria_id: valor} — só o que está preenchido."""
        return {l["categoria_id"]: l["valor"] for l in self.con.execute(
            "SELECT categoria_id, valor FROM atributos WHERE amostra_id = ?",
            (amostra_id,))}

    def atributos_por_nome(self, amostra_id):
        """{nome da categoria: valor}, na ordem das categorias, com ""
        onde não há nada — é a forma que o JSON usa."""
        valores = self.atributos(amostra_id)
        return {c["nome"]: valores.get(c["id"], "") for c in self.categorias()}

    def atributos_de_todas(self):
        """{amostra_id: [valores na ordem das categorias]} de uma vez —
        é o que a página com os azulejos precisa, e uma consulta só é
        bem mais barata que uma por amostra."""
        ordem = {c["id"]: i for i, c in enumerate(self.categorias())}
        vazio = [""] * len(ordem)
        saida = {}
        for l in self.con.execute(
                "SELECT amostra_id, categoria_id, valor FROM atributos"):
            posicao = ordem.get(l["categoria_id"])
            if posicao is None:
                continue
            saida.setdefault(l["amostra_id"], list(vazio))[posicao] = l["valor"]
        return saida

    def definir_atributo(self, amostra_id, categoria_id, valor):
        valor = "" if valor is None else str(valor).strip()
        with self.transacao():
            self._definir_atributo(amostra_id, categoria_id, valor)

    def _definir_atributo(self, amostra_id, categoria_id, valor):
        if valor == "":
            self.con.execute(
                "DELETE FROM atributos WHERE amostra_id = ? AND categoria_id = ?",
                (amostra_id, categoria_id))
        else:
            self.con.execute(
                "INSERT INTO atributos (amostra_id, categoria_id, valor) VALUES (?, ?, ?) "
                "ON CONFLICT(amostra_id, categoria_id) DO UPDATE SET valor = excluded.valor",
                (amostra_id, categoria_id, valor))

    def importar_atributos(self, categorias, linhas, criar_amostras=True):
        """Junta uma planilha inteira ao banco, numa transação só.

        `categorias` são os títulos das colunas (sem a coluna chave) e
        `linhas` é [(nome da amostra, [valor por categoria])]. Categoria
        que não existe é criada; amostra que não existe é criada se
        `criar_amostras`, senão a linha é ignorada. Célula vazia não
        apaga o que já estava escrito na amostra.

        Devolve (amostras atualizadas, amostras criadas, linhas ignoradas).
        """
        atualizadas, criadas, ignoradas = 0, 0, []
        with self.transacao():
            ids = [self.criar_categoria(c) for c in categorias]
            # uma consulta pra todas as amostras, e todos os valores numa
            # inserção só: 300 linhas entram em milissegundos
            existentes = {l["chave"]: l["id"] for l in
                          self.con.execute("SELECT id, chave FROM amostras")}
            agora = _agora()
            valores_novos = []
            for nome, valores in linhas:
                chave = normalizar_nome(nome)
                amostra_id = existentes.get(chave)
                if amostra_id is None:
                    if not criar_amostras:
                        ignoradas.append(nome)
                        continue
                    amostra_id = self.con.execute(
                        "INSERT INTO amostras (nome, chave, criado_em) VALUES (?, ?, ?)",
                        (nome.strip(), chave, agora)).lastrowid
                    existentes[chave] = amostra_id
                    criadas += 1
                else:
                    atualizadas += 1
                for categoria_id, valor in zip(ids, valores):
                    valor = "" if valor is None else str(valor).strip()
                    if valor:
                        valores_novos.append((amostra_id, categoria_id, valor))
            self.con.executemany(
                "INSERT INTO atributos (amostra_id, categoria_id, valor) VALUES (?, ?, ?) "
                "ON CONFLICT(amostra_id, categoria_id) DO UPDATE SET valor = excluded.valor",
                valores_novos)
        return atualizadas, criadas, ignoradas

    # ============================================================
    # Outro banco inteiro
    # ============================================================

    def importar_banco(self, outro):
        """Junta a este banco tudo o que há em `outro` (um
        BancoDeAmostras aberto): categorias, amostras, informações,
        fotos e medições — numa transação só.

        As amostras se encontram pelo nome, as categorias pelo nome, e
        as medições pela impressão/arquivo, como sempre. O que já está
        escrito AQUI não é sobrescrito: uma informação do outro banco
        só entra onde a nossa está vazia, e a foto só se não houver.
        As medições, sim, são atualizadas se já existirem — vale o que
        veio por último, como no "adicionar da tela".

        Devolve um dicionário com as contagens.
        """
        if outro.caminho == self.caminho:
            raise ErroDoBanco("Esse é o próprio banco aberto.")
        contagem = {"categorias": 0, "amostras_novas": 0, "amostras_existentes": 0,
                    "medicoes_novas": 0, "medicoes_atualizadas": 0, "fotos": 0,
                    "espectros_novos": 0, "espectros_atualizados": 0}
        with self.transacao():
            categorias = {}
            for categoria in outro.categorias():
                antes = self.categoria_por_nome(categoria["nome"])
                categorias[categoria["id"]] = self.criar_categoria(categoria["nome"])
                contagem["categorias"] += antes is None
            for resumo in outro.amostras():
                amostra_id, criada = self.obter_ou_criar_amostra(resumo["nome"])
                contagem["amostras_novas" if criada else "amostras_existentes"] += 1
                minhas = self.atributos(amostra_id)
                for cid, valor in outro.atributos(resumo["id"]).items():
                    if valor and not minhas.get(categorias[cid]):
                        self._definir_atributo(amostra_id, categorias[cid], valor)
                if resumo["tem_foto"] and self.foto(amostra_id) is None:
                    self.definir_foto(amostra_id, outro.foto(resumo["id"]))
                    contagem["fotos"] += 1
                for e in outro.espectros(resumo["id"]):
                    _, nova = self.guardar_espectro(
                        amostra_id, e["codigo"], e["tubo"], e["canais"],
                        outro.contagens_do_espectro(e["id"]), e["calibracao"],
                        e["tempo_vivo"], e["tempo_real"], e["inicio"],
                        outro.imagem_do_espectro(e["id"]))
                    contagem["espectros_novos" if nova else "espectros_atualizados"] += 1
                for m in outro.medicoes(resumo["id"]):
                    leituras = [(l["z"], l["valor"], l["grupo"], l["energia"])
                                for l in outro.leituras(m["id"])]
                    _, nova = self.guardar_medicao(
                        amostra_id, m["tubo"], m["codigo"], leituras, m["limite"],
                        tabela=m["tabela"], imagem=outro.imagem_da_medicao(m["id"]),
                        grandeza=m["grandeza"], unidade=m["unidade"],
                        tipo_grafico=m["tipo_grafico"], descartados=m["descartados"])
                    contagem["medicoes_novas" if nova else "medicoes_atualizadas"] += 1
        return contagem

    # ============================================================
    # Medições
    # ============================================================

    def medicoes(self, amostra_id):
        """As medições de uma amostra, sem os blobs (a imagem pode ter
        centenas de kB; quem quiser pede por `imagem_da_medicao`)."""
        linhas = [dict(l) for l in self.con.execute("""
            SELECT id, amostra_id, tubo, codigo, grandeza, unidade, limite,
                   tipo_grafico, descartados, tabela, criado_em,
                   (imagem IS NOT NULL) AS tem_imagem
              FROM medicoes WHERE amostra_id = ?""", (amostra_id,))]
        linhas.sort(key=lambda m: (ordem_do_tubo(m["tubo"]), m["codigo"]))
        for m in linhas:
            m["simbolo"] = simbolo_do_tubo(m["tubo"])
            m["tem_imagem"] = bool(m["tem_imagem"])
        return linhas

    def medicao(self, medicao_id):
        linha = self.con.execute("""
            SELECT id, amostra_id, tubo, codigo, grandeza, unidade, limite,
                   tipo_grafico, descartados, tabela, criado_em,
                   (imagem IS NOT NULL) AS tem_imagem
              FROM medicoes WHERE id = ?""", (medicao_id,)).fetchone()
        if linha is None:
            raise ErroDoBanco("Essa medição não está mais no banco.")
        m = dict(linha)
        m["simbolo"] = simbolo_do_tubo(m["tubo"])
        m["tem_imagem"] = bool(m["tem_imagem"])
        return m

    def imagem_da_medicao(self, medicao_id):
        linha = self.con.execute("SELECT imagem FROM medicoes WHERE id = ?",
                                 (medicao_id,)).fetchone()
        return None if linha is None else linha[0]

    def leituras(self, medicao_id):
        """[{"z", "symbol", "valor", "grupo", "energia"}], do maior valor
        pro menor. A energia (keV) pode ser None: medições da planilha
        de concentrações não têm."""
        return [{"z": z, "symbol": PERIODIC_TABLE.get(z, "Z%d" % z),
                 "valor": valor, "grupo": grupo, "energia": energia}
                for z, valor, grupo, energia in self.con.execute(
                    "SELECT z, valor, grupo, energia FROM leituras WHERE medicao_id = ? "
                    "ORDER BY valor DESC, z", (medicao_id,))]

    def marcas(self, medicao_id):
        """[(energia, símbolo)] dos elementos que ficaram no gráfico —
        as etiquetas dos picos no espectro."""
        return [(l["energia"], l["symbol"]) for l in self.leituras(medicao_id)
                if l["energia"] and l["grupo"] != DESCARTADO]

    def guardar_medicao(self, amostra_id, tubo, codigo, leituras, limite,
                        tabela="", imagem=None, grandeza="Área", unidade="cps",
                        tipo_grafico="", descartados=()):
        """Guarda uma medição. Devolve (id, entrou_agora).

        `leituras` é [(z, valor, grupo)] ou [(z, valor, grupo, energia)]
        com TODOS os elementos lidos — os descartados também, com o
        grupo "descartado". A energia (keV) é opcional.

        Se a mesma medida já estiver no banco, ela é ATUALIZADA — tubo,
        limite, tabela, imagem, grupos — e passa a pertencer a esta
        amostra. É o que deixa reexportar uma batelada depois de mexer no
        limite sem duplicar nada. "A mesma medida" é: os mesmos números
        (a impressão, que sobrevive a renomear o arquivo) ou o mesmo
        arquivo de origem no mesmo tubo (que sobrevive aos números terem
        sido arredondados na tabela exportada e lidos de volta).
        """
        if not leituras:
            raise ErroDoBanco("A medição não tem nenhum elemento lido.")
        self.amostra(amostra_id)
        impressao = impressao_da_medida(leituras)
        if not isinstance(descartados, str):
            descartados = ", ".join(descartados)
        campos = (amostra_id, tubo or "Nenhum", codigo or "", grandeza, unidade,
                  float(limite), tipo_grafico or "", descartados, tabela or "", imagem)
        ja = self.con.execute("SELECT id FROM medicoes WHERE impressao = ?",
                              (impressao,)).fetchone()
        if ja is None and codigo:
            ja = self.con.execute(
                "SELECT id FROM medicoes WHERE codigo = ? COLLATE NOCASE AND tubo = ?",
                (codigo, tubo or "Nenhum")).fetchone()
        with self.transacao():
            if ja is None:
                cur = self.con.execute("""
                    INSERT INTO medicoes (amostra_id, tubo, codigo, grandeza, unidade,
                        limite, tipo_grafico, descartados, tabela, imagem, impressao,
                        criado_em) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    campos + (impressao, _agora()))
                medicao_id, nova = cur.lastrowid, True
            else:
                medicao_id, nova = ja[0], False
                self.con.execute("""
                    UPDATE medicoes SET amostra_id = ?, tubo = ?, codigo = ?,
                        grandeza = ?, unidade = ?, limite = ?, tipo_grafico = ?,
                        descartados = ?, tabela = ?, imagem = ?, impressao = ?
                    WHERE id = ?""", campos + (impressao, medicao_id))
                self.con.execute("DELETE FROM leituras WHERE medicao_id = ?",
                                 (medicao_id,))
            self.con.executemany(
                "INSERT INTO leituras (medicao_id, z, valor, grupo, energia) "
                "VALUES (?, ?, ?, ?, ?)",
                [(medicao_id, int(l[0]), float(l[1]), l[2],
                  float(l[3]) if len(l) > 3 and l[3] is not None else None)
                 for l in leituras])
        return medicao_id, nova

    def excluir_medicao(self, medicao_id):
        with self.transacao():
            self.con.execute("DELETE FROM medicoes WHERE id = ?", (medicao_id,))

    # ============================================================
    # Espectros (os .mca)
    # ============================================================

    def espectros(self, amostra_id):
        """Os espectros de uma amostra, sem os blobs."""
        linhas = [dict(l) for l in self.con.execute("""
            SELECT id, amostra_id, codigo, tubo, canais, calibracao, tempo_vivo,
                   tempo_real, inicio, criado_em, (imagem IS NOT NULL) AS tem_imagem
              FROM espectros WHERE amostra_id = ?""", (amostra_id,))]
        for e in linhas:
            e["simbolo"] = simbolo_do_tubo(e["tubo"])
            e["tem_imagem"] = bool(e["tem_imagem"])
            e["calibracao"] = json.loads(e["calibracao"] or "[]")
        linhas.sort(key=lambda e: (ordem_do_tubo(e["tubo"]), e["codigo"]))
        return linhas

    def espectro(self, espectro_id):
        linha = self.con.execute("""
            SELECT id, amostra_id, codigo, tubo, canais, calibracao, tempo_vivo,
                   tempo_real, inicio, criado_em, (imagem IS NOT NULL) AS tem_imagem
              FROM espectros WHERE id = ?""", (espectro_id,)).fetchone()
        if linha is None:
            raise ErroDoBanco("Esse espectro não está mais no banco.")
        e = dict(linha)
        e["simbolo"] = simbolo_do_tubo(e["tubo"])
        e["tem_imagem"] = bool(e["tem_imagem"])
        e["calibracao"] = json.loads(e["calibracao"] or "[]")
        return e

    def espectro_por_codigo(self, codigo):
        linha = self.con.execute(
            "SELECT id FROM espectros WHERE codigo = ? COLLATE NOCASE",
            (codigo or "",)).fetchone()
        return None if linha is None else linha[0]

    def imagem_do_espectro(self, espectro_id):
        linha = self.con.execute("SELECT imagem FROM espectros WHERE id = ?",
                                 (espectro_id,)).fetchone()
        return None if linha is None else linha[0]

    def contagens_do_espectro(self, espectro_id):
        """O blob das contagens (ver `nucleo.mca.desempacotar_contagens`)."""
        linha = self.con.execute("SELECT contagens FROM espectros WHERE id = ?",
                                 (espectro_id,)).fetchone()
        return None if linha is None else linha[0]

    def guardar_espectro(self, amostra_id, codigo, tubo, canais, contagens, calibracao,
                         tempo_vivo=None, tempo_real=None, inicio="", imagem=None):
        """Guarda um .mca (já lido e com as contagens empacotadas).
        Devolve (id, entrou_agora). O mesmo código de arquivo é o mesmo
        espectro: ele é atualizado, e passa a ser desta amostra."""
        codigo = (codigo or "").strip()
        if not codigo:
            raise ErroDoBanco("O espectro precisa do código do arquivo.")
        self.amostra(amostra_id)
        campos = (amostra_id, tubo or "Nenhum", int(canais), contagens,
                  json.dumps(list(calibracao)), tempo_vivo, tempo_real, inicio or "", imagem)
        ja = self.espectro_por_codigo(codigo)
        with self.transacao():
            if ja is None:
                cur = self.con.execute("""
                    INSERT INTO espectros (amostra_id, tubo, canais, contagens, calibracao,
                        tempo_vivo, tempo_real, inicio, imagem, codigo, criado_em)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", campos + (codigo, _agora()))
                return cur.lastrowid, True
            self.con.execute("""
                UPDATE espectros SET amostra_id = ?, tubo = ?, canais = ?, contagens = ?,
                    calibracao = ?, tempo_vivo = ?, tempo_real = ?, inicio = ?, imagem = ?
                WHERE id = ?""", campos + (ja,))
            return ja, False

    def definir_imagem_do_espectro(self, espectro_id, imagem):
        with self.transacao():
            self.con.execute("UPDATE espectros SET imagem = ? WHERE id = ?",
                             (imagem, espectro_id))

    def excluir_espectro(self, espectro_id):
        with self.transacao():
            self.con.execute("DELETE FROM espectros WHERE id = ?", (espectro_id,))

    def total_de_espectros(self):
        return self.con.execute("SELECT COUNT(*) FROM espectros").fetchone()[0]

    # ---------- o que o JSON precisa ----------

    def elementos_por_grupo(self, medicao_id):
        """{"Majoritários": {símbolo: valor}, "Traço": {...}} — os
        descartados ficam de fora, como no gráfico."""
        grupos = {"Majoritários": {}, "Traço": {}}
        for leitura in self.leituras(medicao_id):
            if leitura["grupo"] == MAJORITARIO:
                grupos["Majoritários"][leitura["symbol"]] = leitura["valor"]
            elif leitura["grupo"] == TRACO:
                grupos["Traço"][leitura["symbol"]] = leitura["valor"]
        return grupos


def leituras_classificadas(kept, removed, major, trace):
    """Monta a lista [(z, valor, grupo)] que `guardar_medicao` espera a
    partir do que `apply_exclusions` e `classify` devolvem."""
    tracos = {e["z"] for e in trace}
    saida = []
    for e in kept:
        saida.append((e["z"], e["valor"], TRACO if e["z"] in tracos else MAJORITARIO,
                      e.get("energia")))
    for e in removed:
        saida.append((e["z"], e["valor"], DESCARTADO, e.get("energia")))
    return saida
