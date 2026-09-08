# -*- coding: utf-8 -*-
"""A janela da pré-análise (Tkinter): a batelada, o slider e os logs.

Toda a regra mora em `preanalise.nucleo` e a planilha em
`preanalise.planilha`; esta camada só amarra as duas coisas na tela. As
CORES estão em `interface/tema.py`, nos dois modos — aqui os widgets só
dizem de que estilo são ("Erro.TLabel", "Cartao.TButton"…).

O que a tela mostra
-------------------
Em cima, os controles e o slider do limite de erro. Embaixo dele, o
RESUMO DO CONJUNTO — o log inicial, falando de todas as amostras de uma
vez. E daí pra baixo, um cartão por amostra: a tabela dos elementos,
ordenada do pior erro pro melhor, com as linhas reprovadas em vermelho e
negrito, e ao lado dela o log daquela amostra. É a mesma coisa que sai
no .xlsx, e de propósito: o que você confere na tela é o que o arquivo
vai ter.

Sobre desempenho
----------------
Uma batelada tem dezenas de amostras, e cada uma vira uma tabela com uma
linha por elemento. Encher uma tabela dessas custa pouco em Python e
custa caro no Tk, que redesenha o widget inteiro. Por isso:

  * cada cartão é um ITEM do canvas, com a posição calculada por nós.
    Num quadro único, toda rolagem arrastaria uma janela do tamanho da
    lista inteira; em itens separados, o canvas desmapeia sozinho o que
    sai da tela;
  * o cartão nasce como um retângulo vazio, só com a altura que ele vai
    ter. Os widgets de verdade (cabeçalho, tabela, log) só são montados
    quando ele chega perto da área visível — e essa altura é palpite bem
    dado: a altura de uma linha de tabela é MEDIDA no primeiro cartão
    que nasce, então a lista não dá pulinho quando os outros nascem;
  * mexer no slider não recria widget nenhum e não repinta a lista
    inteira: recalcula os números de todas as amostras (isso é conta em
    Python, é barato) e repinta só as tabelas que estão na tela. As
    outras ficam com a marca de sujas e se refazem quando você rolar
    até lá;
  * um cartão só é repintado quando muda algo que ele MOSTRA — é o que a
    chave em `CartaoDeAmostra.mostrado` compara. Rolar pra frente e pra
    trás, ou soltar o slider no mesmo valor, não custa nada;
  * e cartão minimizado não tem tabela preenchida, então minimizar tudo
    deixa uma batelada grande leve de rolar.
"""

import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from catalogador.nucleo.leitura import parse_mapping

from ..nucleo import (
    LIMITE_MAXIMO,
    LIMITE_MINIMO,
    LIMITE_PADRAO,
    avaliar,
    codigo_do_arquivo,
    formatar_pct,
    ler_espectro,
    linhas_do_resumo,
    log_da_amostra,
    plural,
    resumo_da_amostra,
)
from ..planilha import exportar
from .tema import FONTE, TEMA_PADRAO, outro, pintar_janela, preparar, trocar

# A margem entre o cartão e a borda da lista, e entre um cartão e outro.
MARGEM_X_PX, MARGEM_Y_PX, ESPACO_ENTRE_CARTOES_PX = 10, 8, 14
# Quanto o log ao lado da tabela ocupa. É largura de parágrafo: mais
# estreito vira uma coluna de duas palavras, mais largo rouba a tabela.
LARGURA_DO_LOG_PX = 340
# Largura mínima do cartão, pra tabela e log não se espremerem numa
# janela estreita (aí a lista ganha barra de rolagem horizontal).
LARGURA_MINIMA_PX = 900

# Quanto, além da janela, já conta como "visível" — montar um pouco à
# frente evita ver o espaço vazio ao rolar devagar.
MARGEM_VISIVEL_PX = 500
# Quanto esperar, depois da última rolagem, pra montar o que apareceu.
ESPERA_ROLAGEM_MS = 60
# Quanto esperar, depois do último passo do slider, pra refazer as
# tabelas. O slider dispara a cada pixel; sem isso, arrastá-lo de ponta
# a ponta repintaria a lista umas cem vezes.
ESPERA_SLIDER_MS = 120
# Quantos cartões nascem por vez ao carregar uma batelada. Todos de uma
# vez fazem o Tk parar por um instante; em lotes, a lista vai aparecendo
# e dá pra usar o programa enquanto o resto chega.
CARTOES_POR_LOTE = 12
# Setas do botão que minimiza/expande cada cartão.
SETA_ABERTO, SETA_FECHADO = "▼", "►"

# Medidas de palpite do cartão, usadas só até o primeiro cartão de
# verdade existir: daí as medidas reais entram no lugar (veja
# `App.medir_alturas`). São o cabeçalho, a moldura da tabela e a altura
# de uma linha dela.
CABECALHO_PX, TABELA_BASE_PX, LINHA_DA_TABELA_PX = 30, 26, 22
# O recheio e a borda do cartão, e o espaço entre o cabeçalho e o corpo.
RECHEIO_PX, ESPACO_PX = 22, 8
# Quantos caracteres cabem numa linha do log e quanto ela ocupa — é o
# que dá a altura do cartão quando o log é mais alto que a tabela.
CARACTERES_POR_LINHA, ALTURA_DA_LINHA_PX = 46, 16

# As colunas da tabela de cada amostra: (chave, título, largura, âncora).
COLUNAS = (
    ("z", "Z", 50, "center"),
    ("elemento", "Elemento", 90, "center"),
    ("area", "Área (cps)", 130, "e"),
    ("erro", "Erro (cps)", 130, "e"),
    ("pct", "Erro Percentual (%)", 160, "e"),
    ("situacao", "Situação", 120, "center"),
)
SITUACAO_ALTA, SITUACAO_OK = "ERRO ALTO", "ok"

# Quantas linhas o resumo mostra sem precisar rolar.
LINHAS_DO_RESUMO = 7


def _formatar_valor(valor):
    """Área e erro na tela: número inteiro, que é como o ajuste os dá."""
    return "%.0f" % valor


class CartaoDeAmostra:
    """Os widgets de UMA amostra: cabeçalho, tabela e log.

    Nasce como um retângulo vazio, só com a altura que ele vai ter; o
    recheio é montado quando o cartão chega perto da área visível. Um
    retângulo vazio custa 2 ms, a tabela cheia custa bem mais — e numa
    batelada de 60 amostras você olha três por vez.
    """

    def __init__(self, app, amostra, nome):
        self.app = app
        self.amostra = amostra
        self.nome = nome
        self.avaliacao = amostra["avaliacao"]
        self.montado = False
        self.minimizado = False
        self.mostrado = None      # o estado JÁ pintado na tabela e no log

        self.altura = self.altura_estimada()
        self.y = 0
        self.frame = ttk.Frame(app.scroll_canvas,
                               style=app.estilo("Cartao.TFrame"),
                               borderwidth=1, height=self.altura)
        self.frame.pack_propagate(False)  # enquanto vazio, a altura é a de palpite
        self.item = app.criar_item(self)

    # ---------- quanto espaço o cartão ocupa ----------

    def log_texto(self):
        return log_da_amostra(self.nome, self.avaliacao, self.app.limite)

    def altura_estimada(self):
        """O espaço que o cartão vai pedir, antes de ele existir.

        É palpite, mas palpite bom: a altura de uma linha da tabela é
        fixa e medida, e o log tem largura fixa, então dá pra contar as
        linhas dos dois. O que sobrar de erro é corrigido no primeiro
        cartão que for montado de verdade.
        """
        cabecalho, base, linha = self.app.alturas
        if self.minimizado:
            return RECHEIO_PX + cabecalho + self.app.correcao_minimizado
        tabela = base + linha * self.avaliacao["total"]
        texto = len(self.log_texto())
        log = ALTURA_DA_LINHA_PX * (texto // CARACTERES_POR_LINHA + 2)
        return (RECHEIO_PX + cabecalho + ESPACO_PX + max(tabela, log)
                + self.app.correcao)

    # ---------- o recheio, montado só quando o cartão se aproxima ----------

    def montar(self):
        """Cria os widgets de verdade. Uma vez por cartão."""
        if self.montado:
            return
        self.montado = True
        app = self.app

        self.frame.configure(padding=10)
        cabecalho = ttk.Frame(self.frame, style=app.estilo("Painel.TFrame"))
        cabecalho.pack(fill="x")
        self.botao_minimizar = ttk.Button(
            cabecalho, width=3, command=self.alternar,
            style=app.estilo("Cartao.Neutro.TButton"),
            text=SETA_FECHADO if self.minimizado else SETA_ABERTO)
        self.botao_minimizar.pack(side="left", padx=(0, 6))
        self.rotulo_nome = ttk.Label(cabecalho, text=self.nome,
                                     style=app.estilo("Titulo.TLabel"))
        self.rotulo_nome.pack(side="left")
        ttk.Label(cabecalho, text="   arquivo: %s" % self.amostra["codigo"],
                  style=app.estilo("Fraco.TLabel")).pack(side="left")
        self.rotulo_veredito = ttk.Label(cabecalho, text="",
                                         style=app.estilo("Ok.TLabel"))
        self.rotulo_veredito.pack(side="left", padx=(12, 0))
        ttk.Button(cabecalho, text="Remover",
                   style=app.estilo("Cartao.Neutro.TButton"),
                   command=lambda: app.remover(self)).pack(side="right")

        self.corpo = ttk.Frame(self.frame, style=app.estilo("Painel.TFrame"))
        if not self.minimizado:
            self.corpo.pack(fill="both", expand=True, pady=(ESPACO_PX, 0))

        # o log vem primeiro no `pack` pra ficar com a largura dele: o
        # `wraplength` já diz onde o texto quebra, então o rótulo pede
        # essa largura e a tabela fica com todo o resto
        self.rotulo_log = ttk.Label(self.corpo, style=app.estilo("Log.TLabel"),
                                    wraplength=LARGURA_DO_LOG_PX,
                                    justify="left", anchor="nw")
        self.rotulo_log.pack(side="right", fill="y", padx=(14, 0))

        self.tabela = ttk.Treeview(
            self.corpo, columns=[c[0] for c in COLUNAS], show="headings",
            selectmode="none", style=app.estilo("Treeview"), height=1)
        for chave, titulo, largura, ancora in COLUNAS:
            self.tabela.heading(chave, text=titulo)
            self.tabela.column(chave, width=largura, anchor=ancora,
                               minwidth=largura, stretch=True)
        self.tabela.pack(side="left", fill="both", expand=True)
        self.repintar()

        # montado, o cartão passa a ter a altura do próprio conteúdo: o
        # palpite não vale mais nada
        self.frame.pack_propagate(True)
        self.frame.configure(height=0)
        app.medir_alturas(self)
        self.aplicar()
        app.medir(self)

    # ---------- o conteúdo ----------

    def atualizar(self, nome, avaliacao):
        """Novos números (o slider mudou) ou novo nome (o mapeamento
        chegou). Só guarda: quem repinta é `aplicar`, e só nos cartões
        que estão na tela."""
        self.nome = nome
        self.avaliacao = avaliacao

    def aplicar(self):
        """Põe na tela o que a amostra tem agora.

        A chave compara o que MUDA o que se vê; se nada mudou, sai sem
        tocar em widget nenhum.
        """
        if not self.montado:
            return
        chave = (self.nome, round(self.app.limite, 4), self.minimizado)
        if chave == self.mostrado:
            return
        self.mostrado = chave

        altos = self.avaliacao["altos"]
        self.rotulo_nome.configure(text=self.nome)
        self.rotulo_veredito.configure(
            text=resumo_da_amostra(self.avaliacao),
            style=self.app.estilo("Erro.TLabel" if altos else "Ok.TLabel"))
        if self.minimizado:
            return   # minimizado, o corpo nem está na tela

        self.rotulo_log.configure(
            text=self.log_texto(),
            style=self.app.estilo("Erro.TLabel" if altos else "Log.TLabel"))
        self.tabela.delete(*self.tabela.get_children())
        for elemento in self.avaliacao["linhas"]:
            self.tabela.insert(
                "", "end",
                values=(elemento["z"], elemento["symbol"],
                        _formatar_valor(elemento["area"]),
                        _formatar_valor(elemento["erro"]),
                        formatar_pct(elemento["pct"]),
                        SITUACAO_ALTA if elemento["alto"] else SITUACAO_OK),
                tags=("alto",) if elemento["alto"] else ())
        self.tabela.configure(height=max(1, self.avaliacao["total"]))
        # o log pode ter ficado mais alto ou mais baixo que a tabela
        self.app.medir(self)

    def alternar(self):
        """Minimiza ou reabre o cartão."""
        self.minimizado = not self.minimizado
        self.botao_minimizar.configure(
            text=SETA_FECHADO if self.minimizado else SETA_ABERTO)
        if self.minimizado:
            self.corpo.pack_forget()
        else:
            self.corpo.pack(fill="both", expand=True, pady=(ESPACO_PX, 0))
        self.aplicar()
        self.app.medir(self)

    def repintar(self):
        """Depois de trocar de tema: o que não passa por estilo ttk.

        A cor da linha reprovada é uma TAG do Treeview, e tag não é
        estilo — ela sobrevive à troca de tema e precisa ser refeita.
        """
        if self.montado:
            self.tabela.tag_configure("alto", foreground=self.app.cores["vermelho"],
                                      font=(FONTE, 9, "bold"))


class App(tk.Tk):
    """A janela."""

    def __init__(self):
        super().__init__()
        self.title("Pré-análise XRF")
        # larga de propósito: a tabela tem seis colunas e o log ainda
        # ocupa uma faixa à direita dela
        self.geometry("1400x820")

        # o tema é a PRIMEIRA coisa: os widgets nascem já pintados, e os
        # estilos dos DOIS temas são criados agora — é o que faz a troca
        # depois ser imediata
        self.style = ttk.Style(self)
        preparar(self, self.style)
        self.tema = TEMA_PADRAO
        self.cores = pintar_janela(self, self.tema)

        # -------- estado --------
        self.amostras = []        # [{"codigo", "elements", "avaliacao"}]
        self.cards = []           # um cartão por amostra, na mesma ordem
        self.falhas = []          # [(arquivo, motivo)] — os que não abriram
        self.mapeamento = {}      # {"081025af": "Madeira 123", ...}
        self.limite = LIMITE_PADRAO
        # as medidas do cartão: de palpite agora, medidas no primeiro
        # cartão que nascer
        self.alturas = (CABECALHO_PX, TABELA_BASE_PX, LINHA_DA_TABELA_PX)
        self._alturas_medidas = False
        self.correcao = 0             # o quanto o palpite de altura erra
        self.correcao_minimizado = 0
        self._job_slider = None       # o debounce do slider
        self._job_rolagem = None      # o debounce da rolagem
        self._job_lote = None         # a criação dos cartões, em lotes

        self._montar_controles()
        self._montar_resumo()
        self._montar_acoes()
        self._montar_lista()
        self._atualizar_resumo()

    # ---------- construção ----------

    def estilo(self, papel):
        """O estilo do tema de agora para um papel ("Titulo.TLabel").

        Todo widget desta janela nasce com um destes: é assim que a
        troca de tema sabe o que cada um é, e é assim que um cartão
        criado DEPOIS de trocar já nasce na cor certa.
        """
        return "%s.%s" % (self.tema, papel)

    def destroy(self):
        # fechar a janela com trabalho agendado fazia o Tk rodar os
        # callbacks depois que os widgets já não existiam, e o programa
        # terminava cuspindo erro no terminal
        for pendente in self.tk.call("after", "info"):
            try:
                self.after_cancel(pendente)
            except tk.TclError:
                pass
        super().destroy()

    def _montar_controles(self):
        frame = ttk.Frame(self, padding=12, style=self.estilo("TFrame"))
        frame.pack(fill="x")
        frame.columnconfigure(1, weight=1)

        linha0 = ttk.Frame(frame, style=self.estilo("TFrame"))
        linha0.grid(row=0, column=0, columnspan=2, sticky="we")
        ttk.Button(linha0, text="1. Carregar amostras (.txt)",
                   style=self.estilo("TButton"),
                   command=self.carregar_amostras).pack(side="left")
        ttk.Button(linha0, text="2. Carregar mapeamento (.csv/.txt)",
                   style=self.estilo("TButton"),
                   command=self.carregar_mapeamento).pack(side="left", padx=6)
        self.rotulo_mapeamento = ttk.Label(
            linha0, text="Nenhum mapeamento carregado.",
            style=self.estilo("FracoFundo.TLabel"))
        self.rotulo_mapeamento.pack(side="left", padx=(6, 0))

        # no canto oposto da mesma linha, longe dos botões de trabalho
        self.botao_tema = ttk.Button(linha0, style=self.estilo("Neutro.TButton"),
                                     text="Modo %s" % outro(self.tema).lower(),
                                     command=self.trocar_tema)
        self.botao_tema.pack(side="right")

        ttk.Label(frame, text="Erro aceitável por elemento:",
                  style=self.estilo("Secao.TLabel")).grid(row=1, column=0,
                                                          sticky="w", pady=(12, 0))
        linha1 = ttk.Frame(frame, style=self.estilo("TFrame"))
        linha1.grid(row=1, column=1, sticky="w", pady=(12, 0))
        self.limite_var = tk.DoubleVar(value=LIMITE_PADRAO)
        slider = ttk.Scale(linha1, from_=LIMITE_MINIMO, to=LIMITE_MAXIMO,
                           orient="horizontal", variable=self.limite_var,
                           length=260, command=self.ao_arrastar_slider,
                           style=self.estilo("Horizontal.TScale"))
        slider.pack(side="left")
        slider.bind("<ButtonRelease-1>", self.ao_soltar_slider)

        self.limite_entry_var = tk.StringVar(value="%.1f" % LIMITE_PADRAO)
        entrada = ttk.Spinbox(linha1, from_=LIMITE_MINIMO, to=LIMITE_MAXIMO,
                              increment=0.5, width=6,
                              textvariable=self.limite_entry_var,
                              command=self.ao_digitar_limite,
                              style=self.estilo("TSpinbox"))
        entrada.pack(side="left", padx=(8, 0))
        entrada.bind("<Return>", self.ao_digitar_limite)
        entrada.bind("<FocusOut>", self.ao_digitar_limite)

        self.rotulo_limite = ttk.Label(linha1, text="%.1f%%" % LIMITE_PADRAO,
                                       style=self.estilo("Secao.TLabel"))
        self.rotulo_limite.pack(side="left", padx=(8, 0))

    def _montar_resumo(self):
        """O log inicial: o que o conjunto inteiro tem, em cima de tudo.

        É um Text, e não um Label, porque cada linha tem a sua cor —
        vermelho o que precisa ser refeito, verde o que passou.
        """
        frame = ttk.Frame(self, padding=(12, 0, 12, 8), style=self.estilo("TFrame"))
        frame.pack(fill="x")
        cartao = ttk.Frame(frame, style=self.estilo("Cartao.TFrame"),
                           borderwidth=1, padding=10)
        cartao.pack(fill="x")

        cabecalho = ttk.Frame(cartao, style=self.estilo("Painel.TFrame"))
        cabecalho.pack(fill="x")
        ttk.Label(cabecalho, text="Resumo do conjunto",
                  style=self.estilo("Titulo.TLabel")).pack(side="left")
        self.rotulo_veredito_geral = ttk.Label(cabecalho, text="",
                                               style=self.estilo("Ok.TLabel"))
        self.rotulo_veredito_geral.pack(side="left", padx=(12, 0))

        corpo = ttk.Frame(cartao, style=self.estilo("Painel.TFrame"))
        corpo.pack(fill="both", expand=True, pady=(6, 0))
        self.resumo = tk.Text(corpo, height=LINHAS_DO_RESUMO, wrap="word",
                              borderwidth=0, highlightthickness=0,
                              font=(FONTE, 9), state="disabled", cursor="arrow")
        barra = ttk.Scrollbar(corpo, orient="vertical",
                              command=self.resumo.yview,
                              style=self.estilo("Vertical.TScrollbar"))
        self.resumo.configure(yscrollcommand=barra.set)
        self.resumo.pack(side="left", fill="both", expand=True)
        barra.pack(side="right", fill="y")
        self._pintar_resumo()

    def _montar_acoes(self):
        """A faixa que vale pra batelada inteira."""
        frame = ttk.Frame(self, padding=(12, 0, 12, 10),
                          style=self.estilo("TFrame"))
        frame.pack(fill="x")

        self.botao_minimizar_todas = ttk.Button(
            frame, text="Minimizar todas", style=self.estilo("Neutro.TButton"),
            command=self.alternar_todas)
        self.botao_minimizar_todas.pack(side="left")

        ttk.Button(frame, text="Exportar planilha (.xlsx)",
                   style=self.estilo("Sucesso.TButton"),
                   command=self.exportar_planilha).pack(side="left", padx=(24, 0))
        self.rotulo_exportacao = ttk.Label(frame, text="",
                                           style=self.estilo("FracoFundo.TLabel"))
        self.rotulo_exportacao.pack(side="left", padx=10)

        # sozinho no canto direito: é o único botão daqui que faz perder
        # trabalho, e encostado nos outros era clique errado esperando
        # pra acontecer
        ttk.Button(frame, text="Remover todas",
                   style=self.estilo("Perigo.TButton"),
                   command=self.remover_todas).pack(side="right")

    def _montar_lista(self):
        """A área rolável, com um item de canvas por amostra."""
        container = ttk.Frame(self, style=self.estilo("TFrame"))
        container.pack(fill="both", expand=True)

        canvas = tk.Canvas(container, borderwidth=0, highlightthickness=0,
                           background=self.cores["fundo"])
        self.scroll_canvas = canvas
        barra = ttk.Scrollbar(container, orient="vertical",
                              command=self._ao_rolar_barra,
                              style=self.estilo("Vertical.TScrollbar"))
        canvas.configure(yscrollcommand=barra.set)
        canvas.bind("<Configure>", self._ao_redimensionar)
        canvas.pack(side="left", fill="both", expand=True)
        barra.pack(side="right", fill="y")
        canvas.bind_all("<MouseWheel>", self._ao_rolar_roda)

        self.rotulo_vazio = ttk.Label(
            canvas, style=self.estilo("FracoFundo.TLabel"), padding=24,
            text="Nenhuma amostra carregada ainda.")
        self._item_vazio = canvas.create_window(MARGEM_X_PX, MARGEM_Y_PX,
                                                window=self.rotulo_vazio,
                                                anchor="nw")

    # ---------- a posição de cada cartão ----------

    def largura_do_cartao(self):
        return max(LARGURA_MINIMA_PX,
                   self.scroll_canvas.winfo_width() - 2 * MARGEM_X_PX)

    def criar_item(self, card):
        """Põe o cartão no canvas, logo abaixo do último. Devolve o id do
        item, que é por onde a posição e a largura dele são mexidas."""
        anterior = self.cards[-1] if self.cards else None
        card.y = (anterior.y + anterior.altura + ESPACO_ENTRE_CARTOES_PX
                  if anterior is not None else MARGEM_Y_PX)
        return self.scroll_canvas.create_window(
            MARGEM_X_PX, card.y, window=card.frame, anchor="nw",
            width=self.largura_do_cartao())

    def medir_alturas(self, card):
        """Tira do primeiro cartão montado as medidas de verdade.

        A altura de uma linha da tabela e a da moldura dela saem de uma
        conta: com 1 linha e com 11, a diferença dividida por 10 é a
        linha, e o que sobra é a moldura. Daí em diante o palpite dos
        cartões que ainda não nasceram é quase exato, e a lista para de
        dar aquele pulinho quando um deles é montado.
        """
        if self._alturas_medidas or not card.montado:
            return
        self._alturas_medidas = True
        tabela = card.tabela
        tabela.configure(height=1)
        uma = tabela.winfo_reqheight()
        tabela.configure(height=11)
        onze = tabela.winfo_reqheight()
        tabela.configure(height=1)
        linha = (onze - uma) / 10.0
        self.alturas = (card.botao_minimizar.winfo_reqheight(),
                        int(round(uma - linha)), int(round(linha)))

    def medir(self, card):
        """Mede o cartão montado e acerta a lista se ele mudou de altura.

        Só é chamada quando algo que MUDA a altura acontece (montar,
        minimizar, o log encompridar), nunca ao rolar. De quebra,
        aprende o quanto o palpite ainda erra — os cartões que não
        nasceram passam a reservar o espaço certo.
        """
        if not card.montado:
            return
        self.update_idletasks()
        real = card.frame.winfo_reqheight()
        residuo = real - card.altura_estimada()
        if card.minimizado:
            self.correcao_minimizado += residuo
        else:
            self.correcao += residuo
        self.definir_altura(card, real)

    def definir_altura(self, card, altura):
        """O cartão passou a ocupar outra altura: empurra os de baixo."""
        if altura == card.altura:
            return
        card.altura = altura
        self._reposicionar(self.cards.index(card) + 1)

    def _reposicionar(self, inicio=0):
        """Reempilha os cartões a partir do índice dado e acerta a região
        rolável. É conta de somar: as posições são nossas, então saber
        onde cada cartão está não custa uma passada de geometria do Tk."""
        y = (MARGEM_Y_PX if inicio == 0 else
             self.cards[inicio - 1].y + self.cards[inicio - 1].altura
             + ESPACO_ENTRE_CARTOES_PX)
        for card in self.cards[inicio:]:
            if card.y != y:
                card.y = y
                self.scroll_canvas.coords(card.item, MARGEM_X_PX, y)
            y = y + card.altura + ESPACO_ENTRE_CARTOES_PX
        self.scroll_canvas.configure(
            scrollregion=(0, 0, self.largura_do_cartao() + 2 * MARGEM_X_PX, y))
        self._agendar_montagem()

    # ---------- quem está na tela ----------

    def _ao_rolar_roda(self, event):
        self.scroll_canvas.yview_scroll(int(-event.delta / 120), "units")
        self._agendar_montagem()

    def _ao_rolar_barra(self, *args):
        self.scroll_canvas.yview(*args)
        self._agendar_montagem()

    def _ao_redimensionar(self, event=None):
        largura = self.largura_do_cartao()
        for card in self.cards:
            self.scroll_canvas.itemconfigure(card.item, width=largura)
        self._agendar_montagem()

    def _agendar_montagem(self):
        """Adia a montagem até a rolagem parar: passar rápido por cima de
        vinte cartões não deve montar os vinte."""
        if self._job_rolagem is not None:
            self.after_cancel(self._job_rolagem)
        self._job_rolagem = self.after(ESPERA_ROLAGEM_MS, self._montar_visiveis)

    def _montar_visiveis(self):
        """Monta (e repinta) os cartões que estão na área visível."""
        self._job_rolagem = None
        if not self.cards:
            return
        topo = self.scroll_canvas.canvasy(0) - MARGEM_VISIVEL_PX
        base = topo + self.scroll_canvas.winfo_height() + 2 * MARGEM_VISIVEL_PX
        for card in self.cards:
            if card.y > base:
                break
            if card.y + card.altura >= topo:
                if card.montado:
                    card.aplicar()
                else:
                    card.montar()

    # ---------- carregar ----------

    def carregar_amostras(self):
        caminhos = filedialog.askopenfilenames(
            title="Selecione os arquivos .txt da batelada",
            filetypes=[("Arquivos de texto", "*.txt"),
                       ("Todos os arquivos", "*.*")])
        if not caminhos:
            return

        novas, falhas = [], []
        for caminho in caminhos:
            try:
                elementos = ler_espectro(caminho)
            except Exception as erro:            # noqa: BLE001
                falhas.append((os.path.basename(caminho), str(erro)))
                continue
            novas.append({"codigo": codigo_do_arquivo(caminho),
                          "elements": elementos})

        self.amostras.extend(novas)
        self.falhas.extend(falhas)
        if falhas and not novas:
            messagebox.showerror("Nenhum arquivo lido",
                                 "\n".join("%s: %s" % f for f in falhas))
        self._recalcular()
        self._sincronizar_cartoes()

    def carregar_mapeamento(self):
        caminho = filedialog.askopenfilename(
            title="Selecione o arquivo de mapeamento (código,nome)",
            filetypes=[("Mapeamento", "*.csv *.txt"),
                       ("Todos os arquivos", "*.*")])
        if not caminho:
            return
        try:
            self.mapeamento = parse_mapping(caminho)
        except Exception as erro:                # noqa: BLE001
            messagebox.showerror("Erro ao ler o mapeamento", str(erro))
            return
        self.rotulo_mapeamento.configure(
            text="%s — %d nome(s)." % (os.path.basename(caminho),
                                       len(self.mapeamento)))
        self._recalcular()

    def nome_da_amostra(self, amostra):
        """O nome real, se o mapeamento tiver um; senão, o código."""
        return self.mapeamento.get(amostra["codigo"].lower(), amostra["codigo"])

    # ---------- os números ----------

    def _recalcular(self):
        """Refaz a avaliação de todas as amostras e o resumo.

        É a parte barata: contas em Python, sem tocar em widget. Quem
        toca na tela é o `aplicar` de cada cartão, e só nos que estão
        na área visível.
        """
        for amostra in self.amostras:
            amostra["avaliacao"] = avaliar(amostra["elements"], self.limite)
        for card in self.cards:
            card.atualizar(self.nome_da_amostra(card.amostra),
                           card.amostra["avaliacao"])
        self._atualizar_resumo()
        self._montar_visiveis()

    def _amostras_do_relatorio(self):
        """As amostras como o núcleo e a planilha esperam ver."""
        return [{"nome": self.nome_da_amostra(a), "codigo": a["codigo"],
                 "avaliacao": a["avaliacao"]} for a in self.amostras]

    def _atualizar_resumo(self):
        self.resumo.configure(state="normal")
        self.resumo.delete("1.0", "end")
        for papel, texto in linhas_do_resumo(self._amostras_do_relatorio(),
                                             self.limite, self.falhas):
            self.resumo.insert("end", texto + "\n", papel)
        self.resumo.configure(state="disabled")

        ruins = sum(1 for a in self.amostras if a["avaliacao"]["altos"])
        if not self.amostras:
            texto, papel = "", "Ok.TLabel"
        elif ruins:
            texto = "%d de %s a refazer" % (
                ruins, plural(len(self.amostras), "amostra", "amostras"))
            papel = "Erro.TLabel"
        else:
            texto = "%s, nenhuma a refazer" % plural(len(self.amostras),
                                                     "amostra", "amostras")
            papel = "Ok.TLabel"
        self.rotulo_veredito_geral.configure(text=texto, style=self.estilo(papel))

    def _pintar_resumo(self):
        """As cores do resumo: um Text não é widget ttk, então não tem
        estilo — quem pinta é a janela, aqui e a cada troca de tema."""
        self.resumo.configure(background=self.cores["painel"],
                              foreground=self.cores["corpo"],
                              selectbackground=self.cores["azul"],
                              selectforeground=self.cores["botao_texto"],
                              inactiveselectbackground=self.cores["azul"])
        self.resumo.tag_configure("titulo", foreground=self.cores["texto"],
                                  font=(FONTE, 10, "bold"))
        self.resumo.tag_configure("problema", foreground=self.cores["vermelho"],
                                  font=(FONTE, 9, "bold"))
        self.resumo.tag_configure("ok", foreground=self.cores["verde"])
        self.resumo.tag_configure("normal", foreground=self.cores["corpo"])

    # ---------- os cartões ----------

    def _sincronizar_cartoes(self):
        """Cria os cartões que faltam, em lotes, pra janela não travar."""
        if self._job_lote is not None:
            self.after_cancel(self._job_lote)
            self._job_lote = None

        primeiro_novo = len(self.cards)
        for amostra in self.amostras[primeiro_novo:
                                     primeiro_novo + CARTOES_POR_LOTE]:
            self.cards.append(
                CartaoDeAmostra(self, amostra, self.nome_da_amostra(amostra)))
        self._reposicionar(primeiro_novo)

        self.scroll_canvas.itemconfigure(
            self._item_vazio, state="hidden" if self.cards else "normal")
        if len(self.cards) < len(self.amostras):
            self._job_lote = self.after(1, self._sincronizar_cartoes)

    def remover(self, card):
        self.amostras.remove(card.amostra)
        self.cards.remove(card)
        self.scroll_canvas.delete(card.item)
        card.frame.destroy()
        self._reposicionar()
        self.scroll_canvas.itemconfigure(
            self._item_vazio, state="hidden" if self.cards else "normal")
        self._recalcular()

    def remover_todas(self):
        if not self.amostras:
            return
        if not messagebox.askyesno(
                "Remover todas",
                "Remover a amostra carregada?" if len(self.amostras) == 1
                else "Remover as %d amostras carregadas?" % len(self.amostras)):
            return
        for card in self.cards:
            self.scroll_canvas.delete(card.item)
            card.frame.destroy()
        self.amostras, self.cards, self.falhas = [], [], []
        self.botao_minimizar_todas.configure(text="Minimizar todas")
        self._reposicionar()
        self.scroll_canvas.itemconfigure(self._item_vazio, state="normal")
        self._recalcular()

    def alternar_todas(self):
        """Minimiza tudo — ou reabre tudo, se já estava minimizado."""
        if not self.cards:
            return
        minimizar = any(not c.minimizado for c in self.cards)
        for card in self.cards:
            if card.minimizado == minimizar:
                continue
            if card.montado:
                card.alternar()
            else:
                # ainda é um retângulo vazio: basta reservar outro espaço
                card.minimizado = minimizar
                self.definir_altura(card, card.altura_estimada())
        self.botao_minimizar_todas.configure(
            text="Expandir todas" if minimizar else "Minimizar todas")

    # ---------- o slider ----------

    def ao_arrastar_slider(self, valor):
        # chamado a cada pixel que o slider anda: aqui só o número muda
        # na hora. As tabelas esperam o arrasto parar — por um tempinho
        # (ESPERA_SLIDER_MS) ou até soltar o botão do mouse.
        self.limite = float(valor)
        self.rotulo_limite.configure(text="%.1f%%" % self.limite)
        self.limite_entry_var.set("%.1f" % self.limite)
        if self._job_slider is not None:
            self.after_cancel(self._job_slider)
        self._job_slider = self.after(ESPERA_SLIDER_MS, self._aplicar_limite)

    def ao_soltar_slider(self, event=None):
        if self._job_slider is not None:
            self.after_cancel(self._job_slider)
        self._aplicar_limite()

    def ao_digitar_limite(self, event=None):
        """O valor digitado (ou clicado) na caixinha ao lado do slider."""
        bruto = self.limite_entry_var.get().strip().replace(",", ".")
        try:
            valor = float(bruto)
        except ValueError:
            self.limite_entry_var.set("%.1f" % self.limite)
            return
        valor = min(max(valor, LIMITE_MINIMO), LIMITE_MAXIMO)
        self.limite_var.set(valor)     # sincroniza a posição do slider
        self.limite = valor
        self.rotulo_limite.configure(text="%.1f%%" % valor)
        self.limite_entry_var.set("%.1f" % valor)
        self._aplicar_limite()

    def _aplicar_limite(self):
        self._job_slider = None
        self._recalcular()

    # ---------- o tema ----------

    def trocar_tema(self):
        novo = outro(self.tema)
        trocar(self, self.tema, novo)
        self.tema = novo
        self.cores = pintar_janela(self, novo)
        self.botao_tema.configure(text="Modo %s" % outro(novo).lower())
        # o que não é widget ttk fica de fora do `trocar` e é pintado aqui
        self.scroll_canvas.configure(background=self.cores["fundo"])
        self._pintar_resumo()
        for card in self.cards:
            card.repintar()

    # ---------- exportar ----------

    def exportar_planilha(self):
        if not self.amostras:
            messagebox.showinfo("Nada para exportar",
                                "Carregue as amostras antes de exportar.")
            return
        caminho = filedialog.asksaveasfilename(
            title="Salvar a pré-análise",
            defaultextension=".xlsx",
            initialfile="Pré-análise XRF.xlsx",
            filetypes=[("Planilha do Excel", "*.xlsx")])
        if not caminho:
            return

        self.rotulo_exportacao.configure(text="Exportando…")
        self.update_idletasks()
        try:
            exportar(caminho, self._amostras_do_relatorio(), self.limite,
                     mapeamento_usado=bool(self.mapeamento), falhas=self.falhas)
        except Exception as erro:                # noqa: BLE001
            self.rotulo_exportacao.configure(text="")
            messagebox.showerror("Erro ao exportar", str(erro))
            return
        self.rotulo_exportacao.configure(
            text="Planilha salva: %s" % os.path.basename(caminho))
