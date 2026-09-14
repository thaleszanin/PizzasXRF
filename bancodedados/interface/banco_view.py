# -*- coding: utf-8 -*-
"""A aba de um banco de amostras: a página de azulejos e a amostra aberta.

Cada arquivo .db aberto ganha uma aba na janela, ao lado da aba do
catalogador. O título da aba é o nome do banco (nasce igual ao do
arquivo e pode ser trocado — dois cliques na aba, ou o botão
"Renomear").

A aba tem duas telas, uma de cada vez:

  * a PÁGINA: um azulejo por amostra, em grade, com o nome, as duas
    primeiras informações da planilha e uma etiqueta por tubo medido
    (Ag, Rh, Au). Clicar num azulejo abre a amostra;
  * a AMOSTRA: as informações dela (uma caixa por categoria, editável
    na hora), a foto, e cada medição com o gráfico e a tabela — o mesmo
    .png e o mesmo .txt que o programa exporta, guardados no banco.

O que entra no banco
--------------------
  * "Adicionar amostras da tela": as amostras abertas no catalogador,
    classificadas com o tubo e o limite que estão valendo lá. Quem faz
    isso é a janela principal (`App.adicionar_ao_banco`), porque é ela
    que tem os dados; esta aba só recebe o resultado;
  * "Importar .txt/.png exportados": os arquivos que o próprio programa
    salvou — o .txt é lido de volta e o .png de mesmo nome entra junto;
  * "Importar planilha": as informações de cada amostra, uma coluna por
    categoria.

Nos dois primeiros casos o MAPEAMENTO precisa estar carregado no
catalogador: é ele que diz o nome da amostra a partir do código do
arquivo, e sem nome a medição não tem onde se pendurar.

Sobre desempenho
----------------
Os azulejos seguem a mesma ideia dos cartões do catalogador: cada um é
um item do canvas, posicionado por nós, e nascem em lotes com o Tk
respirando entre um e outro. Uma lista de 300 amostras aparece
progressivamente em vez de travar a janela por um segundo.
"""

import io
import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from ..banco import (ErroDoBanco, coluna_sugerida,
                     exportar_json, imagem_ao_lado, ler_planilha,
                     ler_tabela_exportada, separar_chave)
from ..exportacao import escrever_texto, nome_de_arquivo
from .dialogos import Dialogo, perguntar_texto

# O azulejo de cada amostra na página.
AZULEJO_LARGURA, AZULEJO_ALTURA = 300, 112
ESPACO, MARGEM = 12, 12
# Quantos azulejos nascem por vez (ver o cabeçalho).
AZULEJOS_POR_LOTE = 24
# Quanto esperar depois do último arrasto da janela pra redistribuir.
ESPERA_REDIMENSIONAR_MS = 150
# A imagem de uma medição, na tela: nunca mais larga que isso.
IMAGEM_LARGURA_MAX = 1100
FOTO_LARGURA_MAX = 360
# Quantos caracteres da linha de informações cabem no azulejo.
RESUMO_MAX = 44


def _resumo(valores, maximo=RESUMO_MAX):
    """"Roxinho · Peltogyne paniculata" — as duas primeiras informações
    preenchidas, cortadas pra caber numa linha do azulejo."""
    partes = [v for v in valores if v][:2]
    texto = " · ".join(partes)
    return texto if len(texto) <= maximo else texto[:maximo - 1].rstrip() + "…"


def _imagem_tk(dados, largura_max):
    """Os bytes de um PNG/JPG como PhotoImage, encolhidos pra caber na
    largura. Devolve (imagem, largura, altura) ou None se não der."""
    try:
        from PIL import Image, ImageTk
        with Image.open(io.BytesIO(dados)) as im:
            im.load()
            if im.width > largura_max:
                altura = max(1, int(im.height * largura_max / im.width))
                im = im.resize((largura_max, altura), Image.LANCZOS)
            foto = ImageTk.PhotoImage(im)
            return foto, foto.width(), foto.height()
    except Exception:
        return None


def _para_png(dados):
    """Qualquer imagem que o PIL abra -> bytes de PNG. É o que a foto da
    amostra vira ao entrar no banco, pra sair como .png no JSON."""
    from PIL import Image
    with Image.open(io.BytesIO(dados)) as im:
        saida = io.BytesIO()
        im.save(saida, format="PNG")
    return saida.getvalue()


# ============================================================
# O azulejo
# ============================================================

class Azulejo:
    """Uma amostra na página. Um quadro fixo, posicionado no canvas pela
    aba; o realce ao passar o mouse é só troca de estilo."""

    def __init__(self, aba, resumo, informacoes):
        self.aba = aba
        self.amostra_id = resumo["id"]
        self.x = self.y = 0
        self.largura = AZULEJO_LARGURA
        app = aba.app
        self.frame = ttk.Frame(aba.canvas, style=app.estilo("Item.TFrame"),
                               padding=10, width=AZULEJO_LARGURA, height=AZULEJO_ALTURA)
        self.frame.pack_propagate(False)

        nome = ttk.Label(self.frame, text=resumo["nome"], anchor="w",
                         style=app.estilo("Titulo.TLabel"))
        nome.pack(fill="x")
        texto = _resumo(informacoes) or "sem informações da planilha"
        detalhe = ttk.Label(self.frame, text=texto, anchor="w",
                            style=app.estilo("Fraco.TLabel"))
        detalhe.pack(fill="x", pady=(2, 0))

        etiquetas = ttk.Frame(self.frame, style=app.estilo("Painel.TFrame"))
        etiquetas.pack(fill="x", side="bottom")
        self._realcaveis = [(self.frame, "Item.TFrame", "ItemRealce.TFrame"),
                            (nome, "Titulo.TLabel", "Realce.Titulo.TLabel"),
                            (detalhe, "Fraco.TLabel", "Realce.Fraco.TLabel"),
                            (etiquetas, "Painel.TFrame", "Realce.TFrame")]
        if resumo["tubos"]:
            for tubo in resumo["tubos"]:
                ttk.Label(etiquetas, text=tubo,
                          style=app.estilo("Chip.TLabel")).pack(side="left", padx=(0, 4))
        else:
            ttk.Label(etiquetas, text="sem medição",
                      style=app.estilo("ChipFraco.TLabel")).pack(side="left")
        if resumo["tem_foto"]:
            ttk.Label(etiquetas, text="foto",
                      style=app.estilo("ChipFraco.TLabel")).pack(side="left")

        for widget in self._todos(self.frame):
            widget.bind("<Button-1>", self._clique)
            widget.bind("<Enter>", self._entrou)
            widget.bind("<Leave>", self._saiu)
        self.item = aba.canvas.create_window(0, 0, window=self.frame, anchor="nw")

    @staticmethod
    def _todos(widget):
        lista = [widget]
        for filho in widget.winfo_children():
            lista.extend(Azulejo._todos(filho))
        return lista

    def _clique(self, _evento=None):
        self.aba.abrir_amostra(self.amostra_id)

    def _entrou(self, _evento=None):
        self._realcar(True)

    def _saiu(self, _evento=None):
        # sair de um rótulo pro quadro também é "Leave": só apaga o
        # realce quando o mouse saiu do azulejo inteiro
        self.frame.after_idle(self._conferir)

    def _conferir(self):
        try:
            x = self.frame.winfo_pointerx() - self.frame.winfo_rootx()
            y = self.frame.winfo_pointery() - self.frame.winfo_rooty()
        except tk.TclError:
            return
        dentro = 0 <= x < self.frame.winfo_width() and 0 <= y < self.frame.winfo_height()
        self._realcar(dentro)

    def _realcar(self, sim):
        estilo = self.aba.app.estilo
        for widget, normal, realce in self._realcaveis:
            widget.configure(style=estilo(realce if sim else normal))

    def mover(self, x, y, largura):
        if (x, y) != (self.x, self.y):
            self.x, self.y = x, y
            self.aba.canvas.coords(self.item, x, y)
        if largura != self.largura:
            self.largura = largura
            self.aba.canvas.itemconfigure(self.item, width=largura)

    def destruir(self):
        self.aba.canvas.delete(self.item)
        self.frame.destroy()


# ============================================================
# A aba
# ============================================================

class AbaDoBanco(ttk.Frame):
    """Uma aba da janela: um banco aberto."""

    def __init__(self, app, banco):
        super().__init__(app.notebook, style=app.estilo("TFrame"))
        self.app = app
        self.banco = banco
        self.azulejos = []
        self._resumos = []          # o que a página mostra (já filtrado)
        self._informacoes = {}      # amostra_id -> valores das categorias
        self._lote_job = None
        self._resize_job = None
        self._largura = 0
        self.amostra_aberta = None  # id da amostra na tela de detalhe
        self._imagens = []          # (rótulo, bytes, largura máx) na tela
        self._fotos_tk = []         # as PhotoImage vivas (o Tk não segura)

        self._montar_barra()
        self._montar_pagina()
        self._montar_detalhe()
        self.recarregar()

    # ------------------------------------------------------------
    # Montagem
    # ------------------------------------------------------------

    def _montar_barra(self):
        app = self.app
        barra = ttk.Frame(self, padding=(12, 10, 12, 0), style=app.estilo("TFrame"))
        barra.pack(fill="x")

        # linha 1: quem é este banco
        linha1 = ttk.Frame(barra, style=app.estilo("TFrame"))
        linha1.pack(fill="x")
        self.titulo = ttk.Label(linha1, text=self.banco.nome,
                                style=app.estilo("Secao.TLabel"), font=("Segoe UI", 12, "bold"))
        self.titulo.pack(side="left")
        ttk.Button(linha1, text="Renomear", style=app.estilo("Neutro.TButton"),
                   command=self.renomear).pack(side="left", padx=(10, 0))
        self.caminho_label = ttk.Label(linha1, text=self.banco.caminho,
                                       style=app.estilo("FracoFundo.TLabel"))
        self.caminho_label.pack(side="left", padx=(12, 0))
        ttk.Button(linha1, text="Fechar aba", style=app.estilo("Neutro.TButton"),
                   command=self.fechar).pack(side="right")

        # linha 2: o que entra e o que sai
        linha2 = ttk.Frame(barra, style=app.estilo("TFrame"))
        linha2.pack(fill="x", pady=(10, 0))
        ttk.Label(linha2, text="Entrada:",
                  style=app.estilo("Secao.TLabel")).pack(side="left", padx=(0, 6))
        ttk.Button(linha2, text="Adicionar amostras da tela", style=app.estilo("TButton"),
                   command=lambda: app.adicionar_ao_banco(self)).pack(side="left", padx=3)
        ttk.Button(linha2, text="Importar .txt/.png exportados…",
                   style=app.estilo("TButton"),
                   command=self.importar_exportados).pack(side="left", padx=3)
        ttk.Button(linha2, text="Importar planilha (.xlsx)…", style=app.estilo("TButton"),
                   command=self.importar_planilha).pack(side="left", padx=3)
        ttk.Label(linha2, text="Saída:",
                  style=app.estilo("Secao.TLabel")).pack(side="left", padx=(18, 6))
        ttk.Button(linha2, text="Salvar cópia (.db)…", style=app.estilo("Sucesso.TButton"),
                   command=self.salvar_copia).pack(side="left", padx=3)
        ttk.Button(linha2, text="Exportar JSON…", style=app.estilo("Sucesso.TButton"),
                   command=self.exportar_json).pack(side="left", padx=3)

        # linha 3: procurar, categorias e o resumo
        linha3 = ttk.Frame(barra, style=app.estilo("TFrame"))
        linha3.pack(fill="x", pady=(10, 8))
        ttk.Label(linha3, text="Procurar:",
                  style=app.estilo("Secao.TLabel")).pack(side="left", padx=(0, 6))
        self.busca_var = tk.StringVar()
        busca = ttk.Entry(linha3, textvariable=self.busca_var, width=30,
                          style=app.estilo("TEntry"))
        busca.pack(side="left")
        busca.bind("<Return>", lambda _e: self.recarregar())
        ttk.Button(linha3, text="Buscar", style=app.estilo("Neutro.TButton"),
                   command=self.recarregar).pack(side="left", padx=(6, 0))
        ttk.Button(linha3, text="Limpar", style=app.estilo("Neutro.TButton"),
                   command=self.limpar_busca).pack(side="left", padx=(4, 0))
        ttk.Button(linha3, text="Categorias…", style=app.estilo("Neutro.TButton"),
                   command=self.gerenciar_categorias).pack(side="left", padx=(18, 0))
        self.status = ttk.Label(linha3, text="", style=app.estilo("FracoFundo.TLabel"))
        self.status.pack(side="right")

    def _montar_pagina(self):
        app = self.app
        self.pagina = ttk.Frame(self, style=app.estilo("TFrame"))
        self.pagina.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(self.pagina, borderwidth=0, highlightthickness=0,
                                background=app.cores["fundo"])
        barra = ttk.Scrollbar(self.pagina, orient="vertical", command=self.canvas.yview,
                              style=app.estilo("Vertical.TScrollbar"))
        self.canvas.configure(yscrollcommand=barra.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        barra.pack(side="right", fill="y")
        self.canvas.bind("<Configure>", self._on_configure)
        app.registrar_rolagem(self.pagina, self.canvas)

        self.vazio = ttk.Label(self.canvas, padding=24,
                               style=app.estilo("FracoFundo.TLabel"))
        self._item_vazio = self.canvas.create_window(MARGEM, MARGEM, window=self.vazio,
                                                     anchor="nw", state="hidden")

    def _montar_detalhe(self):
        """A tela de UMA amostra. Fica escondida até um azulejo ser
        clicado; o conteúdo é montado na hora, pra amostra aberta."""
        app = self.app
        self.detalhe = ttk.Frame(self, style=app.estilo("TFrame"))
        self.canvas_detalhe = tk.Canvas(self.detalhe, borderwidth=0, highlightthickness=0,
                                        background=app.cores["fundo"])
        barra = ttk.Scrollbar(self.detalhe, orient="vertical",
                              command=self.canvas_detalhe.yview,
                              style=app.estilo("Vertical.TScrollbar"))
        self.canvas_detalhe.configure(yscrollcommand=barra.set)
        self.canvas_detalhe.pack(side="left", fill="both", expand=True)
        barra.pack(side="right", fill="y")
        app.registrar_rolagem(self.detalhe, self.canvas_detalhe)

        self.miolo = ttk.Frame(self.canvas_detalhe, style=app.estilo("TFrame"),
                               padding=(MARGEM, MARGEM, MARGEM, 24))
        self._item_miolo = self.canvas_detalhe.create_window(0, 0, window=self.miolo,
                                                             anchor="nw")
        self.miolo.bind("<Configure>", lambda _e: self._ajustar_rolagem_do_detalhe())
        self.canvas_detalhe.bind("<Configure>", self._on_configure_detalhe)

    # ------------------------------------------------------------
    # A página de azulejos
    # ------------------------------------------------------------

    def recarregar(self):
        """Relê o banco e refaz a página. É o que acontece depois de
        qualquer coisa entrar ou sair do banco."""
        if self._lote_job is not None:
            self.after_cancel(self._lote_job)
            self._lote_job = None
        for azulejo in self.azulejos:
            azulejo.destruir()
        self.azulejos = []

        busca = self.busca_var.get().strip()
        try:
            self._resumos = self.banco.amostras(busca or None)
            self._informacoes = self.banco.atributos_de_todas()
            total_a, total_m = self.banco.total_de_amostras(), self.banco.total_de_medicoes()
        except ErroDoBanco as erro:
            messagebox.showerror("Banco de amostras", str(erro))
            return

        texto = "%d amostra(s) · %d medição(ões)" % (total_a, total_m)
        if busca:
            texto = "%d de %s" % (len(self._resumos), texto)
        self.status.config(text=texto)

        if not self._resumos:
            self.vazio.config(text=("Nenhuma amostra bate com a busca."
                                    if busca else
                                    "Banco vazio. Carregue amostras e o mapeamento na aba "
                                    "Catalogador e use \"Adicionar amostras da tela\", ou "
                                    "importe a planilha de informações."))
            self.canvas.itemconfigure(self._item_vazio, state="normal")
            self.canvas.configure(scrollregion=(0, 0, 0, 0))
        else:
            self.canvas.itemconfigure(self._item_vazio, state="hidden")
        self._criar_lote()

    def _criar_lote(self):
        self._lote_job = None
        inicio = len(self.azulejos)
        for resumo in self._resumos[inicio:inicio + AZULEJOS_POR_LOTE]:
            self.azulejos.append(Azulejo(self, resumo,
                                         self._informacoes.get(resumo["id"], [])))
        self._dispor()
        if len(self.azulejos) < len(self._resumos):
            self._lote_job = self.after(1, self._criar_lote)

    def _grade(self):
        """(quantas colunas cabem, a largura de cada azulejo): o azulejo
        tem uma largura mínima, e o que sobrar na linha é dividido entre
        os que couberam, pra grade encostar nas duas bordas."""
        largura = self.canvas.winfo_width()
        if largura <= 1:
            largura = self.app.winfo_width() or 1400
        util = largura - 2 * MARGEM
        colunas = max(1, (util + ESPACO) // (AZULEJO_LARGURA + ESPACO))
        return colunas, max(AZULEJO_LARGURA, (util - (colunas - 1) * ESPACO) // colunas)

    def _dispor(self):
        """Coloca cada azulejo no lugar: uma grade com quantas colunas
        couberem na largura. Aritmética, sem layout do Tk."""
        colunas, largura = self._grade()
        for i, azulejo in enumerate(self.azulejos):
            linha, coluna = divmod(i, colunas)
            azulejo.mover(MARGEM + coluna * (largura + ESPACO),
                          MARGEM + linha * (AZULEJO_ALTURA + ESPACO), largura)
        linhas = (len(self.azulejos) + colunas - 1) // colunas
        altura = MARGEM + linhas * (AZULEJO_ALTURA + ESPACO)
        self.canvas.configure(scrollregion=(0, 0, self.canvas.winfo_width(),
                                            max(altura, self.canvas.winfo_height())))

    def _on_configure(self, evento):
        if abs(evento.width - self._largura) <= 4:
            return
        self._largura = evento.width
        if self._resize_job is not None:
            self.after_cancel(self._resize_job)
        self._resize_job = self.after(ESPERA_REDIMENSIONAR_MS, self._redistribuir)

    def _redistribuir(self):
        self._resize_job = None
        self._dispor()

    def limpar_busca(self):
        self.busca_var.set("")
        self.recarregar()

    # ------------------------------------------------------------
    # A tela de uma amostra
    # ------------------------------------------------------------

    def abrir_amostra(self, amostra_id):
        try:
            amostra = self.banco.amostra(amostra_id)
        except ErroDoBanco as erro:
            messagebox.showerror("Banco de amostras", str(erro))
            self.recarregar()
            return
        self.amostra_aberta = amostra_id
        self.pagina.pack_forget()
        self.detalhe.pack(fill="both", expand=True)
        self._montar_detalhe_de(amostra)
        self.canvas_detalhe.yview_moveto(0)

    def voltar(self):
        self.amostra_aberta = None
        self._limpar_detalhe()
        self.detalhe.pack_forget()
        self.pagina.pack(fill="both", expand=True)
        self.recarregar()

    def _limpar_detalhe(self):
        for filho in self.miolo.winfo_children():
            filho.destroy()
        self._imagens = []
        self._fotos_tk = []

    def _largura_do_detalhe(self):
        largura = self.canvas_detalhe.winfo_width()
        if largura <= 1:
            largura = self.app.winfo_width() or 1400
        return largura

    def _largura_das_imagens(self):
        # o miolo tem MARGEM de cada lado e cada seção tem 12 de recheio
        return max(300, min(IMAGEM_LARGURA_MAX, self._largura_do_detalhe() - 2 * MARGEM - 26))

    def _secao(self, titulo, botoes=()):
        """Um cartão com título e, no canto, os botões que agem sobre
        ele. Devolve o quadro onde o conteúdo entra."""
        app = self.app
        cartao = ttk.Frame(self.miolo, style=app.estilo("Cartao.TFrame"), padding=12)
        cartao.pack(fill="x", pady=(0, 12))
        cabecalho = ttk.Frame(cartao, style=app.estilo("Painel.TFrame"))
        cabecalho.pack(fill="x")
        ttk.Label(cabecalho, text=titulo,
                  style=app.estilo("Subtitulo.TLabel")).pack(side="left")
        for texto, comando, papel in reversed(botoes):
            ttk.Button(cabecalho, text=texto, style=app.estilo(papel),
                       command=comando).pack(side="right", padx=(6, 0))
        corpo = ttk.Frame(cartao, style=app.estilo("Painel.TFrame"))
        corpo.pack(fill="x", pady=(8, 0))
        return corpo

    def _montar_detalhe_de(self, amostra):
        self._limpar_detalhe()
        app, banco = self.app, self.banco
        amostra_id = amostra["id"]

        # o cabeçalho: voltar, o nome, e o que age sobre a amostra inteira
        topo = ttk.Frame(self.miolo, style=app.estilo("TFrame"))
        topo.pack(fill="x", pady=(0, 12))
        ttk.Button(topo, text="\u2190 Voltar à lista", style=app.estilo("Neutro.TButton"),
                   command=self.voltar).pack(side="left")
        ttk.Label(topo, text=amostra["nome"], style=app.estilo("Secao.TLabel"),
                  font=("Segoe UI", 14, "bold")).pack(side="left", padx=(14, 0))
        ttk.Button(topo, text="Excluir amostra", style=app.estilo("Perigo.TButton"),
                   command=lambda: self.excluir_amostra(amostra_id)).pack(side="right")
        ttk.Button(topo, text="Renomear amostra", style=app.estilo("Neutro.TButton"),
                   command=lambda: self.renomear_amostra(amostra_id)).pack(side="right", padx=6)

        # as informações: uma caixa por categoria
        corpo = self._secao("Informações", [
            ("Nova categoria…", lambda: self.nova_categoria(amostra_id), "Cartao.Neutro.TButton"),
            ("Gerenciar categorias…", self.gerenciar_categorias, "Cartao.Neutro.TButton")])
        categorias = banco.categorias()
        valores = banco.atributos(amostra_id)
        if not categorias:
            ttk.Label(corpo, style=app.estilo("Fraco.TLabel"),
                      text="Este banco ainda não tem categorias. Importe a planilha "
                           "de informações ou crie uma em \"Nova categoria…\".").pack(anchor="w")
        corpo.columnconfigure(1, weight=1)
        for linha, categoria in enumerate(categorias):
            ttk.Label(corpo, text=categoria["nome"], style=app.estilo("Corpo.TLabel")
                      ).grid(row=linha, column=0, sticky="w", padx=(0, 12), pady=2)
            var = tk.StringVar(value=valores.get(categoria["id"], ""))
            entrada = ttk.Entry(corpo, textvariable=var, style=app.estilo("TEntry"))
            entrada.grid(row=linha, column=1, sticky="we", pady=2)

            def guardar(_evento=None, cid=categoria["id"], v=var):
                self._guardar_atributo(amostra_id, cid, v)
            entrada.bind("<FocusOut>", guardar)
            entrada.bind("<Return>", guardar)

        # a foto
        corpo = self._secao("Foto", [
            ("Escolher foto…", lambda: self.escolher_foto(amostra_id), "Cartao.Neutro.TButton"),
            ("Remover foto", lambda: self.remover_foto(amostra_id), "Cartao.Neutro.TButton")])
        foto = banco.foto(amostra_id)
        if foto:
            self._mostrar_imagem(corpo, foto, FOTO_LARGURA_MAX)
        else:
            ttk.Label(corpo, text="Sem foto. A foto é opcional: no JSON, sem ela, a "
                                  "imagem da amostra é o gráfico da primeira medição.",
                      style=app.estilo("Fraco.TLabel")).pack(anchor="w")

        # as medições
        medicoes = banco.medicoes(amostra_id)
        titulo = "Medições (%d)" % len(medicoes) if medicoes else "Medições"
        corpo = self._secao(titulo)
        if not medicoes:
            ttk.Label(corpo, wraplength=900, style=app.estilo("Fraco.TLabel"),
                      text="Nenhuma medição ainda. Carregue os .txt do XRF e o mapeamento "
                           "na aba Catalogador, escolha o tubo e use \"Adicionar amostras "
                           "da tela\" — a medição entra aqui pelo nome que o mapeamento "
                           "dá ao arquivo.").pack(anchor="w")
        for medicao in medicoes:
            self._montar_medicao(corpo, medicao)
        self._ajustar_rolagem_do_detalhe()

    def _montar_medicao(self, pai, medicao):
        app, banco = self.app, self.banco
        quadro = ttk.Frame(pai, style=app.estilo("Painel.TFrame"))
        quadro.pack(fill="x", pady=(0, 14))

        cabecalho = ttk.Frame(quadro, style=app.estilo("Painel.TFrame"))
        cabecalho.pack(fill="x")
        ttk.Label(cabecalho, text=medicao["simbolo"],
                  style=app.estilo("Chip.TLabel")).pack(side="left")
        partes = ["tubo %s" % medicao["tubo"], "arquivo %s" % (medicao["codigo"] or "—"),
                  "limite do traço %.1f%%" % medicao["limite"]]
        if medicao["tipo_grafico"]:
            partes.append(medicao["tipo_grafico"])
        if medicao["descartados"]:
            partes.append("descartado: %s" % medicao["descartados"])
        partes.append("guardada em %s" % medicao["criado_em"])
        ttk.Label(cabecalho, text="   " + " · ".join(partes),
                  style=app.estilo("Fraco.TLabel")).pack(side="left")
        mid = medicao["id"]
        ttk.Button(cabecalho, text="Excluir medição", style=app.estilo("Cartao.Neutro.TButton"),
                   command=lambda: self.excluir_medicao(mid)).pack(side="right")
        ttk.Button(cabecalho, text="Salvar tabela (TXT)", style=app.estilo("Cartao.TButton"),
                   command=lambda: self.salvar_tabela(mid)).pack(side="right", padx=6)
        if medicao["tem_imagem"]:
            ttk.Button(cabecalho, text="Salvar imagem (PNG)", style=app.estilo("Cartao.TButton"),
                       command=lambda: self.salvar_imagem(mid)).pack(side="right")

        if medicao["tem_imagem"]:
            self._mostrar_imagem(quadro, banco.imagem_da_medicao(mid))

        leituras = banco.leituras(mid)
        mostradas = [l for l in leituras if l["grupo"] != "descartado"]
        total = sum(l["valor"] for l in mostradas) or 1.0
        colunas = ("z", "elemento", "valor", "pct", "grupo")
        tabela = ttk.Treeview(quadro, columns=colunas, show="headings",
                              height=max(1, min(12, len(mostradas))),
                              style=app.estilo("Treeview"))
        titulos = ("Z", "Elemento", "%s (%s)" % (medicao["grandeza"], medicao["unidade"]),
                   "% do total", "Grupo")
        for coluna, titulo in zip(colunas, titulos):
            tabela.heading(coluna, text=titulo)
            tabela.column(coluna, width=110, anchor="center")
        area = medicao["grandeza"].lower().startswith(("área", "area"))
        for l in mostradas:
            valor = "%.0f" % l["valor"] if area else ("%g" % l["valor"])
            pct = l["valor"] / total * 100
            tabela.insert("", "end", values=(
                l["z"], l["symbol"], valor,
                "%.2f%%" % pct if pct >= 0.005 else "<0.01%", l["grupo"]))
        tabela.pack(fill="x", pady=(8, 0))

    def _mostrar_imagem(self, pai, dados, largura_max=None):
        """Põe a imagem na tela. Sem `largura_max`, ela acompanha a
        largura da janela (é o caso dos gráficos); com, fica fixa (a
        foto)."""
        rotulo = ttk.Label(pai, style=self.app.estilo("Fraco.TLabel"), anchor="w")
        rotulo.pack(anchor="w", pady=(8, 0))
        self._imagens.append((rotulo, dados, largura_max))
        self._pintar_imagem(rotulo, dados, largura_max)

    def _pintar_imagem(self, rotulo, dados, largura_max):
        pronta = _imagem_tk(dados, largura_max or self._largura_das_imagens())
        if pronta is None:
            rotulo.config(text="(não consegui abrir esta imagem)")
            return
        foto, _, _ = pronta
        self._fotos_tk.append(foto)
        rotulo.config(image=foto, text="")

    def _on_configure_detalhe(self, evento):
        self.canvas_detalhe.itemconfigure(self._item_miolo, width=evento.width)
        if self._imagens:
            if self._resize_job is not None:
                self.after_cancel(self._resize_job)
            self._resize_job = self.after(ESPERA_REDIMENSIONAR_MS, self._reescalar)

    def _reescalar(self):
        """A janela mudou de largura: os gráficos acompanham (a foto,
        que tem largura fixa, só é repintada no mesmo tamanho)."""
        self._resize_job = None
        self._fotos_tk = []
        for rotulo, dados, largura_max in self._imagens:
            self._pintar_imagem(rotulo, dados, largura_max)

    def _ajustar_rolagem_do_detalhe(self):
        self.canvas_detalhe.configure(scrollregion=self.canvas_detalhe.bbox("all"))

    # ------------------------------------------------------------
    # Ações na amostra aberta
    # ------------------------------------------------------------

    def _guardar_atributo(self, amostra_id, categoria_id, var):
        try:
            self.banco.definir_atributo(amostra_id, categoria_id, var.get())
        except ErroDoBanco as erro:
            messagebox.showerror("Banco de amostras", str(erro))

    def _reabrir(self):
        """Refaz a tela da amostra aberta (depois de algo mudar nela)."""
        if self.amostra_aberta is not None:
            self.abrir_amostra(self.amostra_aberta)

    def nova_categoria(self, amostra_id=None):
        nome = perguntar_texto(self.app, "Nova categoria",
                               "Nome da categoria (vira uma coluna em todas as "
                               "amostras deste banco):", ok="Criar")
        if not nome:
            return
        try:
            self.banco.criar_categoria(nome)
        except ErroDoBanco as erro:
            messagebox.showerror("Banco de amostras", str(erro))
            return
        self._reabrir() if amostra_id is not None else self.recarregar()

    def gerenciar_categorias(self):
        DialogoDeCategorias(self.app, self.banco).esperar()
        self._reabrir() if self.amostra_aberta is not None else self.recarregar()

    def renomear_amostra(self, amostra_id):
        atual = self.banco.amostra(amostra_id)["nome"]
        nome = perguntar_texto(self.app, "Renomear amostra",
                               "Novo nome (é por ele que o mapeamento e a planilha "
                               "encontram a amostra):", atual)
        if not nome or nome == atual:
            return
        try:
            self.banco.renomear_amostra(amostra_id, nome)
        except ErroDoBanco as erro:
            messagebox.showerror("Banco de amostras", str(erro))
            return
        self._reabrir()

    def excluir_amostra(self, amostra_id):
        amostra = self.banco.amostra(amostra_id)
        quantas = len(self.banco.medicoes(amostra_id))
        if not messagebox.askyesno(
                "Excluir amostra",
                "Excluir \"%s\" do banco, com as informações e %d medição(ões) dela?\n\n"
                "Isso não tem desfazer." % (amostra["nome"], quantas),
                icon=messagebox.WARNING, default=messagebox.NO):
            return
        self.banco.excluir_amostra(amostra_id)
        self.voltar()

    def excluir_medicao(self, medicao_id):
        medicao = self.banco.medicao(medicao_id)
        if not messagebox.askyesno(
                "Excluir medição",
                "Excluir a medição do tubo %s (arquivo %s)?" % (medicao["simbolo"],
                                                                 medicao["codigo"] or "—"),
                icon=messagebox.WARNING, default=messagebox.NO):
            return
        self.banco.excluir_medicao(medicao_id)
        self._reabrir()

    def escolher_foto(self, amostra_id):
        caminho = filedialog.askopenfilename(
            title="Escolha a foto da amostra",
            filetypes=[("Imagens", "*.png *.jpg *.jpeg *.bmp *.gif *.tif *.tiff"),
                       ("Todos os arquivos", "*.*")])
        if not caminho:
            return
        try:
            with open(caminho, "rb") as f:
                dados = _para_png(f.read())
        except Exception as erro:
            messagebox.showerror("Foto", "Não consegui abrir a imagem:\n%s" % erro)
            return
        self.banco.definir_foto(amostra_id, dados)
        self._reabrir()

    def remover_foto(self, amostra_id):
        if self.banco.foto(amostra_id) is None:
            return
        self.banco.definir_foto(amostra_id, None)
        self._reabrir()

    def salvar_imagem(self, medicao_id):
        medicao = self.banco.medicao(medicao_id)
        nome = self.banco.amostra(medicao["amostra_id"])["nome"]
        caminho = filedialog.asksaveasfilename(
            defaultextension=".png", filetypes=[("Imagem PNG", "*.png")],
            initialfile="%s.png" % nome_de_arquivo("%s - %s" % (nome, medicao["simbolo"])))
        if not caminho:
            return
        with open(caminho, "wb") as f:
            f.write(self.banco.imagem_da_medicao(medicao_id))
        messagebox.showinfo("Salvo", "Imagem salva em:\n%s" % caminho)

    def salvar_tabela(self, medicao_id):
        medicao = self.banco.medicao(medicao_id)
        nome = self.banco.amostra(medicao["amostra_id"])["nome"]
        caminho = filedialog.asksaveasfilename(
            defaultextension=".txt", filetypes=[("Arquivo de texto", "*.txt")],
            initialfile="%s.txt" % nome_de_arquivo("%s - %s" % (nome, medicao["simbolo"])))
        if not caminho:
            return
        escrever_texto(caminho, medicao["tabela"] or "(esta medição não tem tabela guardada)\n")
        messagebox.showinfo("Salvo", "Tabela salva em:\n%s" % caminho)

    # ------------------------------------------------------------
    # Ações da aba
    # ------------------------------------------------------------

    def renomear(self):
        nome = perguntar_texto(self.app, "Renomear banco",
                               "Nome do banco (é o título da aba e entra no "
                               "id das amostras no JSON):", self.banco.nome)
        if not nome:
            return
        try:
            self.banco.nome = nome
        except ErroDoBanco as erro:
            messagebox.showerror("Banco de amostras", str(erro))
            return
        self.titulo.config(text=nome)
        self.app.notebook.tab(self, text=nome)

    def fechar(self):
        self.app.fechar_banco(self)

    def salvar_copia(self):
        caminho = filedialog.asksaveasfilename(
            title="Salvar uma cópia do banco", defaultextension=".db",
            filetypes=[("Banco de amostras", "*.db")],
            initialfile="%s.db" % nome_de_arquivo(self.banco.nome))
        if not caminho:
            return
        try:
            self.banco.salvar_copia(caminho)
        except (ErroDoBanco, OSError) as erro:
            messagebox.showerror("Salvar cópia", str(erro))
            return
        messagebox.showinfo("Salvo", "Cópia do banco salva em:\n%s" % caminho)

    def exportar_json(self):
        caminho = filedialog.asksaveasfilename(
            title="Exportar o banco como JSON", defaultextension=".json",
            filetypes=[("JSON", "*.json")],
            initialfile="%s.json" % nome_de_arquivo(self.banco.nome))
        if not caminho:
            return
        try:
            amostras, imagens = exportar_json(self.banco, caminho)
        except (ErroDoBanco, OSError) as erro:
            messagebox.showerror("Exportar JSON", str(erro))
            return
        messagebox.showinfo(
            "Pronto", "%d amostra(s) exportada(s) para:\n%s\n\n%d imagem(ns) na pasta "
            "\"dados\" ao lado do arquivo." % (amostras, caminho, imagens))

    def importar_exportados(self):
        """Os .txt que o programa exportou (com o .png de mesmo nome ao
        lado) entram como medições. O nome da amostra vem do mapeamento,
        pelo código do arquivo de origem escrito no .txt."""
        mapeamento = self.app.name_mapping
        if not mapeamento:
            messagebox.showwarning(
                "Falta o mapeamento",
                "Carregue o mapeamento na aba Catalogador (botão 2) antes: é ele "
                "que diz a que amostra cada arquivo pertence.")
            return
        caminhos = filedialog.askopenfilenames(
            title="Selecione os .txt exportados pelo programa",
            filetypes=[("Tabelas exportadas (.txt)", "*.txt")])
        if not caminhos:
            return

        novas, atualizadas, sem_nome, erros = 0, 0, [], []
        for caminho in caminhos:
            try:
                blocos = ler_tabela_exportada(caminho)
            except (ValueError, OSError) as erro:
                erros.append(str(erro))
                continue
            # o .png ao lado só vale quando o .txt é de UMA amostra: no
            # compilado a imagem é a faixa com todas juntas
            imagem = imagem_ao_lado(caminho) if len(blocos) == 1 else None
            for bloco in blocos:
                nome = mapeamento.get(bloco["codigo"].lower())
                if not nome:
                    sem_nome.append(bloco["codigo"] or bloco["nome"])
                    continue
                try:
                    amostra_id, _ = self.banco.obter_ou_criar_amostra(nome)
                    _, nova = self.banco.guardar_medicao(
                        amostra_id, bloco["tubo"], bloco["codigo"], bloco["leituras"],
                        bloco["limite"], tabela=bloco["tabela"], imagem=imagem,
                        grandeza=bloco["grandeza"], unidade=bloco["unidade"],
                        descartados=bloco["descartados"])
                except ErroDoBanco as erro:
                    erros.append("%s: %s" % (bloco["codigo"], erro))
                    continue
                novas += nova
                atualizadas += not nova

        self.recarregar()
        texto = "%d medição(ões) nova(s), %d atualizada(s)." % (novas, atualizadas)
        if sem_nome:
            texto += ("\n\nFicaram de fora, por não estarem no mapeamento: %s."
                      % ", ".join(sem_nome))
        if erros:
            texto += "\n\nErros:\n" + "\n".join(erros)
        messagebox.showinfo("Importação", texto)

    def importar_planilha(self):
        caminho = filedialog.askopenfilename(
            title="Selecione a planilha de informações das amostras",
            filetypes=[("Planilha do Excel", "*.xlsx *.xlsm")])
        if not caminho:
            return
        try:
            categorias, linhas = ler_planilha(caminho)
        except ValueError as erro:
            messagebox.showerror("Erro ao ler a planilha", str(erro))
            return
        except Exception as erro:
            messagebox.showerror("Erro ao ler a planilha",
                                 "%s:\n%s" % (os.path.basename(caminho), erro))
            return

        conhecidos = list(self.app.name_mapping.values())
        conhecidos += [a["nome"] for a in self.banco.amostras()]
        sugerida = coluna_sugerida(linhas, conhecidos)
        resposta = DialogoDaPlanilha(self.app, os.path.basename(caminho),
                                     categorias, linhas, sugerida).esperar()
        if resposta is None:
            return
        coluna, criar = resposta
        outras, prontas, sem_nome = separar_chave(categorias, linhas, coluna)
        try:
            atualizadas, criadas, ignoradas = self.banco.importar_atributos(
                outras, prontas, criar_amostras=criar)
        except ErroDoBanco as erro:
            messagebox.showerror("Importar planilha", str(erro))
            return
        self._reabrir() if self.amostra_aberta is not None else self.recarregar()

        texto = ("%d categoria(s): %s.\n\n%d amostra(s) atualizada(s), %d criada(s)."
                 % (len(outras), ", ".join(outras), atualizadas, criadas))
        if ignoradas:
            texto += ("\n\n%d linha(s) ignorada(s) por não estarem no banco (a opção "
                      "de criar estava desligada)." % len(ignoradas))
        if sem_nome:
            texto += ("\n\n%d linha(s) puladas por estarem com a coluna \"%s\" vazia."
                      % (sem_nome, categorias[coluna]))
        messagebox.showinfo("Planilha importada", texto)

    # ------------------------------------------------------------
    # Tema
    # ------------------------------------------------------------

    def repintar(self):
        """Os widgets ttk já trocaram de estilo (quem faz é `tema.trocar`);
        aqui entram só os do tk puro, que não têm estilo."""
        cores = self.app.cores
        self.canvas.configure(background=cores["fundo"])
        self.canvas_detalhe.configure(background=cores["fundo"])


# ============================================================
# Os diálogos da aba
# ============================================================

class DialogoDaPlanilha(Dialogo):
    """Antes de importar: em que coluna está o nome da amostra, e se as
    amostras que ainda não existem devem ser criadas."""

    def __init__(self, app, arquivo, categorias, linhas, sugerida):
        self.arquivo, self.categorias, self.linhas = arquivo, categorias, linhas
        self.sugerida = sugerida
        super().__init__(app, "Importar planilha", ok="Importar", largura=560)

    def montar(self, corpo):
        app = self.app
        ttk.Label(corpo, wraplength=520, style=app.estilo("TLabel"),
                  text="%s: %d linha(s), %d coluna(s) — %s."
                       % (self.arquivo, len(self.linhas), len(self.categorias),
                          ", ".join(self.categorias))).pack(anchor="w")
        ttk.Label(corpo, wraplength=520, style=app.estilo("TLabel"),
                  text="Cada coluna vira uma categoria do banco, menos a que traz o "
                       "NOME da amostra — o mesmo nome que o mapeamento dá aos "
                       "arquivos do XRF:").pack(anchor="w", pady=(10, 4))
        self.coluna_var = tk.StringVar(value=self.categorias[self.sugerida])
        ttk.Combobox(corpo, textvariable=self.coluna_var, values=self.categorias,
                     state="readonly", width=40,
                     style=app.estilo("TCombobox")).pack(anchor="w")

        # uma amostrinha da coluna escolhida, pra conferir sem abrir o Excel
        self.exemplo = ttk.Label(corpo, style=app.estilo("FracoFundo.TLabel"),
                                 wraplength=520)
        self.exemplo.pack(anchor="w", pady=(4, 0))
        self.coluna_var.trace_add("write", lambda *_: self._mostrar_exemplo())
        self._mostrar_exemplo()

        self.criar_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(corpo, variable=self.criar_var, style=app.estilo("TCheckbutton"),
                        text="Criar as amostras que ainda não estão no banco "
                             "(desligado: só preenche as que já têm medição)"
                        ).pack(anchor="w", pady=(12, 4))

    def _mostrar_exemplo(self):
        coluna = self.categorias.index(self.coluna_var.get())
        valores = [l[coluna] for l in self.linhas if l[coluna]][:6]
        self.exemplo.config(text="Por exemplo: %s" % ", ".join(valores)
                            if valores else "Essa coluna está vazia.")

    def responder(self):
        return self.categorias.index(self.coluna_var.get()), self.criar_var.get()


class DialogoDeCategorias(tk.Toplevel):
    """Criar, renomear, reordenar e apagar as categorias do banco. Cada
    mudança vale na hora; fechar a janela só volta pra aba."""

    def __init__(self, app, banco):
        super().__init__(app)
        self.app, self.banco = app, banco
        self.title("Categorias do banco")
        self.configure(background=app.cores["fundo"])
        self.transient(app)
        self.resizable(False, False)

        corpo = ttk.Frame(self, padding=16, style=app.estilo("TFrame"))
        corpo.pack(fill="both", expand=True)
        ttk.Label(corpo, wraplength=420, style=app.estilo("TLabel"),
                  text="As categorias são as colunas da planilha de informações. "
                       "Apagar uma leva embora o que está escrito nela em todas "
                       "as amostras.").pack(anchor="w", pady=(0, 8))

        lista = ttk.Frame(corpo, style=app.estilo("TFrame"))
        lista.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(lista, columns=("nome",), show="headings", height=10,
                                 selectmode="browse", style=app.estilo("Treeview"))
        self.tree.heading("nome", text="Categoria")
        self.tree.column("nome", width=320, anchor="w")
        barra = ttk.Scrollbar(lista, orient="vertical", command=self.tree.yview,
                              style=app.estilo("Vertical.TScrollbar"))
        self.tree.configure(yscrollcommand=barra.set)
        self.tree.pack(side="left", fill="both", expand=True)
        barra.pack(side="right", fill="y")

        botoes = ttk.Frame(corpo, style=app.estilo("TFrame"))
        botoes.pack(fill="x", pady=(10, 0))
        for texto, comando, papel in (("Nova…", self.nova, "TButton"),
                                      ("Renomear…", self.renomear, "Neutro.TButton"),
                                      ("Excluir", self.excluir, "Perigo.TButton"),
                                      ("\u2191", lambda: self.mover(-1), "Neutro.TButton"),
                                      ("\u2193", lambda: self.mover(1), "Neutro.TButton")):
            ttk.Button(botoes, text=texto, style=app.estilo(papel), command=comando,
                       **({"width": 3} if len(texto) == 1 else {})).pack(side="left", padx=(0, 6))
        ttk.Button(botoes, text="Fechar", style=app.estilo("Neutro.TButton"),
                   command=self.destroy).pack(side="right")

        self.recarregar()
        self.update_idletasks()
        x = app.winfo_rootx() + (app.winfo_width() - self.winfo_reqwidth()) // 2
        y = app.winfo_rooty() + (app.winfo_height() - self.winfo_reqheight()) // 3
        self.geometry("+%d+%d" % (max(0, x), max(0, y)))
        self.grab_set()

    def recarregar(self, selecionar=None):
        self.tree.delete(*self.tree.get_children(""))
        for categoria in self.banco.categorias():
            self.tree.insert("", "end", iid=str(categoria["id"]), values=(categoria["nome"],))
        if selecionar is not None and self.tree.exists(str(selecionar)):
            self.tree.selection_set(str(selecionar))
            self.tree.see(str(selecionar))

    def _selecionada(self):
        selecao = self.tree.selection()
        return int(selecao[0]) if selecao else None

    def _erro(self, erro):
        messagebox.showerror("Categorias", str(erro), parent=self)

    def nova(self):
        nome = perguntar_texto(self.app, "Nova categoria", "Nome da categoria:", ok="Criar")
        self.grab_set()  # a pergunta levou o "grab" embora ao fechar
        if not nome:
            return
        try:
            novo = self.banco.criar_categoria(nome)
        except ErroDoBanco as erro:
            return self._erro(erro)
        self.recarregar(novo)

    def renomear(self):
        cid = self._selecionada()
        if cid is None:
            return
        atual = self.tree.item(str(cid), "values")[0]
        nome = perguntar_texto(self.app, "Renomear categoria", "Novo nome:", atual)
        self.grab_set()
        if not nome or nome == atual:
            return
        try:
            self.banco.renomear_categoria(cid, nome)
        except ErroDoBanco as erro:
            return self._erro(erro)
        self.recarregar(cid)

    def excluir(self):
        cid = self._selecionada()
        if cid is None:
            return
        nome = self.tree.item(str(cid), "values")[0]
        if not messagebox.askyesno(
                "Excluir categoria",
                "Excluir \"%s\" e o que está escrito nela em todas as amostras?" % nome,
                icon=messagebox.WARNING, default=messagebox.NO, parent=self):
            return
        self.banco.excluir_categoria(cid)
        self.recarregar()

    def mover(self, direcao):
        cid = self._selecionada()
        if cid is None:
            return
        self.banco.mover_categoria(cid, direcao)
        self.recarregar(cid)

    def esperar(self):
        self.wait_window(self)
