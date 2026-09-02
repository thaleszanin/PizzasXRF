"""A janela do programa (Tkinter): botões, slider, cards e tabelas.

Toda a lógica de dados vive em `catalogador.nucleo` e todo o desenho em
`catalogador.graficos`. Esta camada só amarra as duas coisas na tela.

Sobre desempenho
----------------
A parte cara do programa é desenhar as três pizzas de uma amostra. Por
isso esta camada foi montada pra refazer esse trabalho o mínimo
possível:

  * cada amostra tem um cartão (`SampleCard`) que nasce UMA vez e é
    reaproveitado — carregar mais arquivos, mexer no slider ou trocar o
    tubo não destrói nem recria widget nenhum, só atualiza o conteúdo;
  * o gráfico E a tabela só são montados nos cartões que estão (ou estão
    quase) na área visível; quem está fora da tela espera você rolar até
    lá — repopular a tabela de uma amostra fora da tela custa quase nada
    em Python, mas obriga o Tk a redesenhar o widget inteiro;
  * a fila de desenho anda um cartão por vez, devolvendo o controle pro
    Tk entre um e outro, então a janela não "congela" no meio de uma
    batelada grande;
  * um cartão só é redesenhado quando muda algo que ele MOSTRA — é o que
    a chave em `SampleCard.state_key` compara;
  * cartão minimizado não é desenhado nem tem tabela preenchida, então
    minimizar tudo deixa uma batelada grande leve de rolar.

O conteúdo dos arquivos que os botões de salvar geram não está aqui, e
sim em `catalogador/exportacao.py` — esta camada só escolhe o destino e
cuida da fila, um arquivo por vez, pra janela não congelar.
"""

import os
import time
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from ..nucleo.leitura import parse_frx_file, parse_mapping
from ..nucleo.classificacao import TUBE_OPTIONS, apply_exclusions, classify
from ..graficos.figura import (FIG_DPI, FIG_SIZE, build_sample_figure,
                              passos_da_rasterizacao, passos_do_desenho)
from ..exportacao import (PilhaDeImagens, bloco_da_amostra, caminho_livre,
                          documento_compilado, escrever_texto, linhas_da_tabela,
                          nome_de_arquivo, pasta_da_exportacao)

# Altura reservada pro gráfico dentro do cartão. É fixa de propósito: o
# cartão ocupa o mesmo espaço antes e depois de ser desenhado, então a
# barra de rolagem não "pula" quando um gráfico entra na tela.
FIG_ALTURA_PX = int(FIG_SIZE[1] * FIG_DPI)
# O que o cartão consome de largura em volta do gráfico: 10px de margem
# de cada lado, mais 10px de recheio e 1px de borda de cada lado.
MARGEM_DO_CARTAO_PX = 42
# Largura mínima do gráfico, pra ele não virar um risco numa janela
# muito estreita (aí a lista ganha barra de rolagem horizontal).
LARGURA_MINIMA_PX = 700
# Quanto esperar, depois do último arrasto da janela, pra refazer os
# gráficos na largura nova.
ESPERA_REDIMENSIONAR_MS = 150

# Quanto, além da janela, já conta como "visível" — desenhar um pouco à
# frente evita ver o espaço vazio ao rolar devagar.
MARGEM_VISIVEL_PX = 400
# Quanto esperar, depois da última rolagem, pra começar a desenhar.
ESPERA_ROLAGEM_MS = 120
# ...e o teto dessa espera. Cada clique da roda adia o desenho; sem um
# teto, quem rola sem parar fica olhando pra cartões vazios o tempo todo.
# Passado esse tempo desde o primeiro pedido, desenha mesmo com a roda
# girando (um cartão por vez, o que estiver mais no meio da tela).
TETO_DE_ESPERA_MS = 350
# Quanto tempo a fila de desenho pode segurar a janela de cada vez. O
# desenho de um cartão é fatiado em pedaços de uns 25 ms; a fila enfia
# pedaços até estourar esse orçamento e devolve o controle ao Tk.
ORCAMENTO_MS = 12
# Quantos cartões nascem por vez ao carregar uma batelada. Criar 100 de
# uma vez faz o Tk remontar o layout de tudo numa tacada só e a janela
# congela; em lotes, a lista vai aparecendo e dá pra usar o programa.
CARTOES_POR_LOTE = 8
# Setas do botão que minimiza/expande cada cartão.
SETA_ABERTO, SETA_FECHADO = "▼", "►"
# A partir de quantas amostras a imagem compilada merece um aviso: ela é
# uma faixa única, com todos os gráficos empilhados.
MAX_AMOSTRAS_COMPILADO = 40

# Altura de palpite de um cartão que ainda não foi montado. Vale só até
# o primeiro cartão de verdade existir: daí as medidas reais entram no
# lugar (veja `App.medir_alturas`).
ALTURA_CHUTE_PX = FIG_ALTURA_PX + 300
# O que o cartão gasta em volta do conteúdo: 10px de recheio e 1px de
# borda de cada lado, mais 8px entre o gráfico e a tabela e 4px acima do
# aviso de descarte. São os mesmos números usados no `pack` do cartão.
RECHEIO_PX, ESPACO_TABELA_PX, ESPACO_AVISO_PX = 22, 8, 4

COLUNAS = ("z", "elemento", "area", "pct", "grupo")
CABECALHOS = {"z": "Z", "elemento": "Elemento", "area": "Área (cps)",
              "pct": "% do total", "grupo": "Grupo"}


def _tube_key(tube_z):
    """Chave comparável pro tubo selecionado (o valor é um set)."""
    return None if tube_z is None else tuple(sorted(tube_z))


class SampleCard:
    """Os widgets de UMA amostra na lista.

    Nasce como um retângulo vazio, só com a altura que ele vai ter. O
    recheio (cabeçalho, botões, área do gráfico, tabela) é montado quando
    o cartão chega perto da área visível, e as pizzas são desenhadas
    depois disso — três estágios, do mais barato pro mais caro.

    O motivo é o Tk: montar os widgets de 120 cartões custa meio segundo,
    e calcular o layout deles, mais um segundo e meio. Um retângulo vazio
    custa 2 ms.
    """

    def __init__(self, master, app, sample):
        self.app = app
        self.sample = sample
        self.state_key = None    # o estado JÁ CALCULADO (nome/avisos/dados)
        self.drawn_key = None    # o estado já DESENHADO (as pizzas)
        self.table_key = None    # o estado já MOSTRADO na tabela
        self.canvas = None       # FigureCanvasTkAgg, criado sob demanda
        self.display_name = sample["code"]
        self._dados = ([], [], [], 0.0)  # kept, major, trace, total
        self._descartados = []
        self.collapsed = False
        self._aviso = ""
        self._layout_key = None
        self._altura_tabela = 1
        self._altura_reservada = None

        self.montado = False
        self._altura_reservada = app.altura_estimada(1, False)
        self.frame = ttk.Frame(master, relief="groove", borderwidth=1,
                               height=self._altura_reservada)
        self.frame.pack(fill="x", padx=10, pady=8)
        self.frame.pack_propagate(False)  # enquanto vazio, a altura é a de palpite

    # ---------- o recheio, montado só quando o cartão se aproxima ----------

    def montar(self):
        """Cria os widgets de verdade. Uma vez por cartão."""
        if self.montado:
            return
        self.montado = True
        app, sample = self.app, self.sample

        self.frame.configure(padding=10)
        header = ttk.Frame(self.frame)
        header.pack(fill="x")
        self.toggle_btn = ttk.Button(
            header, width=3, command=self.toggle,
            text=SETA_FECHADO if self.collapsed else SETA_ABERTO)
        self.toggle_btn.pack(side="left", padx=(0, 6))
        self.name_label = ttk.Label(header, text=self.display_name,
                                    font=("Segoe UI", 12, "bold"))
        self.name_label.pack(side="left")
        ttk.Label(header, text=f"   arquivo: {sample['code']}",
                  foreground="#6B6250").pack(side="left")
        ttk.Button(header, text="Remover",
                   command=lambda: app.remove_sample(self)).pack(side="right")
        ttk.Button(header, text="Salvar tabela (TXT)",
                   command=self.save_table).pack(side="right", padx=6)
        ttk.Button(header, text="Salvar imagem (PNG)",
                   command=self.save_figure).pack(side="right")

        # o espaço do gráfico já nasce do tamanho exato da figura: assim o
        # cartão não muda de tamanho quando o gráfico aparece, e o widget
        # do matplotlib não precisa redesenhar tudo pra se ajustar
        # a ALTURA é fixa (o cartão ocupa o mesmo espaço antes e depois de
        # ser desenhado, então a rolagem não pula); a LARGURA acompanha a
        # janela, senão o terceiro gráfico fica cortado quando a janela é
        # menor que a figura
        self.plot_area = ttk.Frame(self.frame, height=FIG_ALTURA_PX)
        self.plot_area.pack_propagate(False)
        self.placeholder = ttk.Label(self.plot_area, anchor="center",
                                     foreground="#9A927F",
                                     text="Gráfico desenhado ao rolar até aqui…")
        self.placeholder.pack(expand=True)

        self.fig = Figure(figsize=FIG_SIZE, dpi=FIG_DPI)

        self.warn_label = ttk.Label(self.frame, foreground="#B8792E", wraplength=1100)

        self.tree = ttk.Treeview(self.frame, columns=COLUNAS, show="headings",
                                 height=self._altura_tabela)
        for col in COLUNAS:
            self.tree.heading(col, text=CABECALHOS[col])
            self.tree.column(col, width=110, anchor="center")

        if self._aviso:
            self.warn_label.config(text=self._aviso)
        self._layout_key = None
        self._aplicar_layout()
        # montado, o cartão passa a ter a altura do próprio conteúdo: o
        # palpite não vale mais nada
        self.frame.pack_propagate(True)
        self.frame.configure(height=0)
        app.medir_alturas(self)

    # ---------- minimizar / expandir ----------

    def toggle(self):
        self.set_collapsed(not self.collapsed)
        if not self.collapsed:
            self.app._schedule_draw()

    def set_collapsed(self, collapsed):
        """Minimiza (ou expande) o cartão, deixando só o cabeçalho.

        Minimizado, o cartão não entra na fila de desenho — é o que faz
        uma lista grande ficar leve de rolar.
        """
        if collapsed == self.collapsed:
            return
        self.collapsed = collapsed
        self.app._geometria_suja = True
        if not self.montado:
            self._reservar_altura()
            return
        self.toggle_btn.config(text=SETA_FECHADO if collapsed else SETA_ABERTO)
        self._aplicar_layout()

    def _aplicar_layout(self):
        """(Re)empacota o corpo do cartão. Só mexe quando algo mudou de
        verdade: cada pack/pack_forget obriga o Tk a refazer o layout da
        lista inteira."""
        chave = (self.collapsed, bool(self._aviso))
        if chave == self._layout_key:
            return
        self._layout_key = chave
        self.app._geometria_suja = True
        for widget in (self.plot_area, self.warn_label, self.tree):
            widget.pack_forget()
        if self.collapsed:
            return
        self.plot_area.pack(fill="x")
        if self._aviso:
            self.warn_label.pack(anchor="w", pady=(4, 0))
        self.tree.pack(fill="x", pady=(8, 0))

    # ---------- parte barata: nome, avisos e tabela ----------

    def update_data(self, tube_z, threshold, display_name):
        """Recalcula a parte barata do cartão: os grupos, o nome, o aviso
        de descarte e a ALTURA da tabela (pra lista não mudar de tamanho
        depois). Sai na hora se nada mudou — é o que faz rolar a tela, ou
        soltar o slider no mesmo valor, não custar nada."""
        key = (_tube_key(tube_z), round(threshold, 4), display_name)
        if key == self.state_key:
            return
        self.state_key = key

        kept, removed = apply_exclusions(self.sample["elements"], tube_z)
        major, trace, total = classify(kept, threshold)
        self._dados = (kept, major, trace, total)

        if display_name != self.display_name:
            self.display_name = display_name
            if self.montado:
                self.name_label.config(text=display_name)

        self._descartados = [e["symbol"] for e in removed]
        self._aviso = ""
        if removed:
            self._aviso = "Descartado nesta amostra: %s" % ", ".join(self._descartados)
        if self.montado:
            if self._aviso:
                self.warn_label.config(text=self._aviso)
            self._aplicar_layout()

        # a altura é ajustada agora (é o que define o tamanho do cartão),
        # mas as LINHAS só entram quando o cartão for desenhado. Mexer na
        # altura invalida o layout da lista inteira no Tk — e mudar o
        # limite do traço não muda a quantidade de linhas, então quase
        # sempre isso aqui não faz nada.
        altura = max(1, min(10, len(major) + len(trace)))
        if altura != self._altura_tabela:
            self._altura_tabela = altura
            if self.montado:
                self.tree.configure(height=altura)
                self.app._geometria_suja = True
        if not self.montado:
            self._reservar_altura()

    def _reservar_altura(self):
        """Ajusta a altura do retângulo vazio pro tamanho que o cartão
        vai ter quando for montado.

        Só mexe quando o número muda: cada `configure` obriga o Tk a
        recalcular o layout da lista inteira, e trocar o limite do traço
        não muda a altura de cartão nenhum."""
        nova = self.app.altura_estimada(self._altura_tabela, bool(self._aviso),
                                        self.collapsed)
        if nova != self._altura_reservada:
            self._altura_reservada = nova
            self.frame.configure(height=nova)
            self.app._geometria_suja = True

    def _fill_table(self, major, trace, total):
        # as MESMAS linhas que vão pro arquivo .txt (catalogador/exportacao.py),
        # pra tela e arquivo nunca discordarem
        linhas = linhas_da_tabela(major, trace, total)

        # apaga tudo numa tacada só: linha a linha, o Treeview refaz o
        # layout a cada remoção
        filhos = self.tree.get_children("")
        if filhos:
            self.tree.delete(*filhos)
        for linha in linhas:
            self.tree.insert("", "end", values=linha)

    # ---------- parte cara: as pizzas e a tabela ----------

    @property
    def needs_draw(self):
        return self.drawn_key != self.state_key

    def montar_tabela(self):
        """Põe as linhas na tabela. É barato (milissegundos), e por isso
        acontece separado do gráfico: ao rolar a lista, os números
        aparecem na hora enquanto o desenho ainda está na fila."""
        if self.table_key == self.state_key or self.collapsed or not self.montado:
            return
        self.table_key = self.state_key
        self._fill_table(*self._dados[1:])

    def render(self):
        """Desenha o cartão inteiro de uma vez (usado fora da fila)."""
        for _ in self.iniciar_desenho():
            pass

    def iniciar_desenho(self):
        """Devolve um gerador que desenha o cartão em pedaços — cada
        `next()` faz um pedaço.

        Até o último pedaço, o cartão continua mostrando o que já
        mostrava (a imagem anterior, ou o aviso de que o gráfico ainda
        vem). Quem toca o gerador é a fila em `App._draw_next`.
        """
        if not self.needs_draw:
            return iter(())
        self.montar()
        self.montar_tabela()

        # Os rótulos são posicionados em PIXELS, então a figura precisa
        # estar na largura final antes de ser desenhada — desenhar em
        # 1400 e deixar o Tk espremer pra 1150 embaralharia tudo.
        self._ajustar_largura(self.app.largura_do_grafico())

        if self.canvas is None:
            self.canvas = FigureCanvasTkAgg(self.fig, master=self.plot_area)
            widget = self.canvas.get_tk_widget()
            # O matplotlib escuta mouse/teclado no widget dele pra dar
            # zoom, "pick" e coordenadas — nada disso é usado aqui, e
            # cada evento desses vira chamada Python. Ao rolar a lista, o
            # ponteiro atravessa os gráficos e dispara Motion/Enter/Leave
            # e MouseWheel (que a janela já trata por conta própria), o
            # que só deixava a rolagem pesada.
            # o <Configure> entra na lista: quem decide quando a figura
            # muda de tamanho é o `_ajustar_largura`, não o Tk
            for evento in ("<Configure>", "<Motion>", "<Enter>", "<Leave>", "<MouseWheel>",
                           "<Button-1>", "<Button-2>", "<Button-3>",
                           "<ButtonRelease-1>", "<ButtonRelease-2>", "<ButtonRelease-3>",
                           "<Key>", "<KeyRelease>"):
                widget.unbind(evento)
            # o espaço reservado tem exatamente o tamanho da figura, então
            # o widget já nasce do tamanho certo. Se o cartão ainda está
            # com o aviso de "gráfico vem aí", o widget só entra na tela
            # quando a imagem estiver pronta — senão o aviso sumiria e
            # ficaria um retângulo branco no lugar.
            if self.placeholder is None:
                widget.pack(fill="both", expand=True)

        return self._passos_do_cartao(self.state_key, *self._dados)

    def _passos_do_cartao(self, chave, kept, major, trace, total):
        yield from passos_do_desenho(self.fig, kept, major, trace, total,
                                     self.display_name)
        yield from passos_da_rasterizacao(self.fig)
        # `blit` só copia os pixels prontos pro Tk: é a única parte que
        # precisa mesmo acontecer na linha do tempo da janela
        self.canvas.blit()
        if self.placeholder is not None:
            self.placeholder.destroy()
            self.placeholder = None
            self.canvas.get_tk_widget().pack(fill="both", expand=True)
        self.drawn_key = chave

    def save_figure(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".png",
            initialfile="%s.png" % nome_de_arquivo(self.display_name),
            filetypes=[("Imagem PNG", "*.png")],
        )
        if not path:
            return
        # figura NOVA, no tamanho padrão: a imagem salva não pode depender
        # da largura que a janela tinha na hora (a do cartão acompanha a
        # janela). É exatamente a mesma que a exportação em lote gera.
        fig = self.app.figura_para_arquivo(self.sample)
        try:
            fig.savefig(path, dpi=200, bbox_inches="tight")
        finally:
            fig.clear()
        messagebox.showinfo("Salvo", "Imagem salva em:\n%s" % path)

    def _ajustar_largura(self, largura_px):
        """Põe a figura (e o retrato dela dentro do Tk) na largura pedida.

        O widget do matplotlib faria isso sozinho ao receber o
        <Configure> do Tk — só que aí TODO gráfico já desenhado se
        redesenha quando a janela muda de tamanho, inclusive os que estão
        fora da tela (eram dezenas de segundos de trava num arrasto de
        borda). Por isso aquele <Configure> fica desligado e a troca de
        tamanho acontece aqui, só pra quem vai ser desenhado agora.
        """
        if int(round(self.fig.get_figwidth() * FIG_DPI)) == largura_px:
            return
        self.fig.set_size_inches(largura_px / FIG_DPI, FIG_SIZE[1], forward=False)
        if self.canvas is not None:
            # o retrato da figura dentro do Tk ficou do tamanho velho.
            # Pedir pro matplotlib se redimensionar resolveria, só que
            # ele já emenda um desenho inteiro de uma vez — justamente o
            # que a fila em pedaços evita. Joga fora e refaz: o desenho
            # vem logo em seguida.
            self.canvas.get_tk_widget().destroy()
            self.canvas = None

    def save_table(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            initialfile="%s.txt" % nome_de_arquivo(self.display_name),
            filetypes=[("Arquivo de texto", "*.txt")],
        )
        if path:
            escrever_texto(path, self.app.bloco_de_texto(self.sample))
            messagebox.showinfo("Salvo", "Tabela salva em:\n%s" % path)

    def destroy(self):
        if not self.montado:
            self.frame.destroy()
            return
        if self.canvas is not None:
            self.canvas.get_tk_widget().destroy()
            self.canvas = None
        self.fig.clear()
        self.frame.destroy()


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Pizzas XRF")
        # A janela nasce larga porque o gráfico ocupa a largura toda: os
        # rótulos têm tamanho fixo, então quanto mais estreita a janela,
        # menor sobra pra pizza. Dá pra redimensionar à vontade — os
        # gráficos se refazem na largura nova.
        self.geometry("1400x820")

        # -------- estado da aplicação --------
        self.samples = []          # [{"code": str, "elements": [...]}]
        self.cards = []            # um SampleCard por amostra, na ordem
        self.name_mapping = {}     # {"081025af": "Madeira 123", ...}
        self.threshold = 10.0
        self.tube_z = None
        self._render_after_id = None  # debounce do slider
        self._draw_job = None         # próximo passo da fila de desenho
        self._draw_queue = None       # cartões visíveis do lote atual
        self._draw_limite = None      # até quando dá pra adiar o desenho
        self._geometria_suja = True   # a lista mudou de forma?
        self._alturas = None          # medidas tiradas de um cartão real
        self._passos = None           # desenho em andamento (gerador)
        self._card_em_desenho = None
        self._sync_job = None         # criação dos cartões em lotes
        self._export = None           # exportação em lote em andamento
        self._resize_job = None       # redesenho depois de mudar a janela
        self._largura_anterior = 0

        self._build_top_controls()
        self._build_export_controls()
        self._build_scroll_area()
        self._sync_cards()

    # ---------- construção da UI ----------

    def destroy(self):
        # Fechar a janela com desenho/exportação agendados fazia o Tk
        # tentar rodar esses callbacks depois que os widgets já não
        # existiam, e o programa terminava cuspindo erro no terminal.
        for pendente in self.tk.call("after", "info"):
            try:
                self.after_cancel(pendente)
            except tk.TclError:
                pass
        super().destroy()

    def _build_top_controls(self):
        frame = ttk.Frame(self, padding=12)
        frame.pack(fill="x")

        # Cada linha é uma faixa própria: os controles (e o rótulo que
        # explica cada um) ficam encostados uns nos outros. Numa grade
        # única, a coluna do slider empurrava o "10.0%" e o aviso do
        # mapeamento pra longe, do outro lado da janela.
        linha0 = ttk.Frame(frame)
        linha0.grid(row=0, column=0, columnspan=2, sticky="w", pady=4)
        ttk.Button(linha0, text="1. Carregar amostras (.txt)",
                   command=self.load_samples).pack(side="left")
        ttk.Button(linha0, text="2. Carregar mapeamento (.csv/.txt)",
                   command=self.load_mapping).pack(side="left", padx=6)
        self.mapping_label = ttk.Label(linha0, text="Nenhum mapeamento carregado.")
        self.mapping_label.pack(side="left", padx=(6, 0))

        ttk.Label(frame, text="Tubo de raios X utilizado:").grid(row=1, column=0, sticky="w", pady=(12, 0))
        linha1 = ttk.Frame(frame)
        linha1.grid(row=1, column=1, sticky="w", pady=(12, 0))
        self.tube_var = tk.StringVar(value="Nenhum")
        tube_combo = ttk.Combobox(linha1, textvariable=self.tube_var, values=list(TUBE_OPTIONS.keys()),
                                   state="readonly", width=18)
        tube_combo.pack(side="left")
        tube_combo.bind("<<ComboboxSelected>>", self.on_tube_change)

        ttk.Label(frame, text="Limite do grupo traço:").grid(row=2, column=0, sticky="w", pady=(12, 0))
        linha2 = ttk.Frame(frame)
        linha2.grid(row=2, column=1, sticky="w", pady=(12, 0))
        self.threshold_var = tk.DoubleVar(value=10.0)
        slider = ttk.Scale(linha2, from_=1, to=50, orient="horizontal",
                            variable=self.threshold_var, command=self.on_threshold_change, length=260)
        slider.pack(side="left")
        slider.bind("<ButtonRelease-1>", self.on_slider_release)

        self.threshold_entry_var = tk.StringVar(value="10.0")
        threshold_entry = ttk.Spinbox(
            linha2, from_=1, to=50, increment=0.5, width=6,
            textvariable=self.threshold_entry_var, command=self.on_threshold_entry_commit,
        )
        threshold_entry.pack(side="left", padx=(8, 0))
        threshold_entry.bind("<Return>", self.on_threshold_entry_commit)
        threshold_entry.bind("<FocusOut>", self.on_threshold_entry_commit)

        self.threshold_label = ttk.Label(linha2, text="10.0%")
        self.threshold_label.pack(side="left", padx=(8, 0))

    def _build_export_controls(self):
        """A faixa de baixo: minimizar tudo e salvar a batelada inteira."""
        frame = ttk.Frame(self, padding=(12, 0, 12, 10))
        frame.pack(fill="x")

        self.toggle_all_btn = ttk.Button(frame, text="Minimizar todas",
                                         command=self.toggle_all)
        self.toggle_all_btn.pack(side="left")

        ttk.Label(frame, text="Salvar todas as amostras:").pack(side="left", padx=(24, 6))
        self.export_buttons = [
            ttk.Button(frame, text="Num arquivo só",
                       command=lambda: self.export_all("compilado")),
            ttk.Button(frame, text="Um arquivo por amostra",
                       command=lambda: self.export_all("individuais")),
        ]
        for botao in self.export_buttons:
            botao.pack(side="left", padx=3)

        self.export_label = ttk.Label(frame, text="", foreground="#6B6250")
        self.export_label.pack(side="left", padx=10)

    def _build_scroll_area(self):
        """Cria uma área rolável, já que podemos ter muitas amostras
        carregadas de uma vez (processamento em batelada)."""
        container = ttk.Frame(self)
        container.pack(fill="both", expand=True)

        canvas = tk.Canvas(container, borderwidth=0, highlightthickness=0)
        self.scroll_canvas = canvas
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=self._on_scrollbar)
        self.cards_frame = ttk.Frame(canvas)

        self.cards_frame.bind("<Configure>", self._on_cards_configure)
        self._window_id = canvas.create_window((0, 0), window=self.cards_frame, anchor="nw")
        canvas.bind("<Configure>", self._on_canvas_configure)
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # rolar com a roda do mouse
        canvas.bind_all("<MouseWheel>", self._on_mousewheel)

        self.empty_label = ttk.Label(self.cards_frame,
                                     text="Nenhuma amostra carregada ainda.", padding=24)

    def _on_canvas_configure(self, event):
        """A janela mudou de tamanho.

        Aqui NÃO se mexe em nada: mudar a largura dos cartões faz o Tk
        remontar o layout da lista inteira, e arrastar a borda da janela
        dispara isso dezenas de vezes por segundo. Só anota o tamanho
        novo e marca a hora — quem age é o `_refazer_graficos`, quando o
        arrasto para.
        """
        largura = max(LARGURA_MINIMA_PX + MARGEM_DO_CARTAO_PX, event.width)
        if abs(largura - self._largura_anterior) <= 4:
            return
        self._largura_anterior = largura
        if self._resize_job is not None:
            self.after_cancel(self._resize_job)
        self._resize_job = self.after(ESPERA_REDIMENSIONAR_MS, self._refazer_graficos)

    def _refazer_graficos(self):
        """O arrasto parou: agora sim os cartões vão pra largura nova."""
        self._resize_job = None
        self._geometria_suja = True
        self._abandonar_desenho()  # o que estava sendo desenhado é da largura velha
        self.scroll_canvas.itemconfigure(self._window_id, width=self._largura_anterior)
        for card in self.cards:
            card.drawn_key = None   # a largura mudou: todo mundo venceu
        self._schedule_draw()

    def largura_do_grafico(self):
        """Quantos pixels de largura o gráfico tem dentro do cartão."""
        return max(LARGURA_MINIMA_PX,
                   self.scroll_canvas.winfo_width() - MARGEM_DO_CARTAO_PX)

    def _on_cards_configure(self, event):
        # a região rolável é exatamente o tamanho do frame dos cartões —
        # mais barato (e mais estável) que pedir `bbox("all")` ao canvas
        self.scroll_canvas.configure(scrollregion=(0, 0, event.width, event.height))

    def _on_mousewheel(self, event):
        self.scroll_canvas.yview_scroll(int(-event.delta / 120), "units")
        self._schedule_draw(ESPERA_ROLAGEM_MS)

    def _on_scrollbar(self, *args):
        self.scroll_canvas.yview(*args)
        self._schedule_draw(ESPERA_ROLAGEM_MS)

    # ---------- ações dos botões / controles ----------

    def load_samples(self):
        paths = filedialog.askopenfilenames(
            title="Selecione os arquivos .txt da batelada",
            filetypes=[("Arquivos de texto", "*.txt")],
        )
        if not paths:
            return
        for path in paths:
            try:
                elements = parse_frx_file(path)
            except ValueError as err:
                messagebox.showerror("Erro ao ler arquivo", str(err))
                continue
            code = os.path.splitext(os.path.basename(path))[0]
            self.samples.append({"code": code, "elements": elements})
        # só os cartões novos são criados; os que já estavam na tela
        # continuam de pé, com o gráfico deles intacto
        self._sync_cards()

    def load_mapping(self):
        path = filedialog.askopenfilename(
            title="Selecione o arquivo de mapeamento",
            filetypes=[("CSV ou texto", "*.csv *.txt")],
        )
        if not path:
            return
        self.name_mapping = parse_mapping(path)
        self.mapping_label.config(
            text=f"{len(self.name_mapping)} associações carregadas de {os.path.basename(path)}."
        )
        self.refresh()

    def on_tube_change(self, event=None):
        self.tube_z = TUBE_OPTIONS[self.tube_var.get()]
        self.refresh()

    def on_threshold_change(self, value):
        # Isso é chamado a cada pixel que o slider se move, então só
        # atualizamos o texto na hora (é barato). O redesenho dos
        # gráficos não rola a cada movimento — só quando o usuário solta
        # o botão do mouse (on_slider_release) ou para de arrastar por um
        # tempo (debounce, como rede de segurança para quem usa o
        # teclado/setas).
        self.threshold = float(value)
        self.threshold_label.config(text=f"{self.threshold:.1f}%")
        self.threshold_entry_var.set(f"{self.threshold:.1f}")

        if self._render_after_id is not None:
            self.after_cancel(self._render_after_id)
        self._render_after_id = self.after(200, self._debounced_render)

    def _debounced_render(self):
        self._render_after_id = None
        self.refresh()

    def on_slider_release(self, event=None):
        if self._render_after_id is not None:
            self.after_cancel(self._render_after_id)
            self._render_after_id = None
        self.refresh()

    def on_threshold_entry_commit(self, event=None):
        # Chamado quando o usuário digita um número na caixinha e aperta
        # Enter, sai do campo (Tab/clique fora), ou usa as setinhas do
        # Spinbox. Valida o valor, sincroniza o slider e redesenha na hora.
        raw = self.threshold_entry_var.get().strip().replace(",", ".")
        try:
            value = float(raw)
        except ValueError:
            self.threshold_entry_var.set(f"{self.threshold:.1f}")
            return

        value = max(1.0, min(50.0, value))
        self.threshold_var.set(value)  # sincroniza a posição do slider
        self.threshold = value
        self.threshold_label.config(text=f"{self.threshold:.1f}%")
        self.threshold_entry_var.set(f"{self.threshold:.1f}")

        if self._render_after_id is not None:
            self.after_cancel(self._render_after_id)
            self._render_after_id = None
        self.refresh()

    def toggle_all(self):
        """Minimiza todos os cartões — ou expande todos, se já estiverem
        minimizados."""
        minimizar = any(not card.collapsed for card in self.cards)
        for card in self.cards:
            card.set_collapsed(minimizar)
        self.toggle_all_btn.config(text="Expandir todas" if minimizar else "Minimizar todas")
        # nos dois sentidos: minimizado, o cartão ainda precisa do
        # cabeçalho montado (nome e botões), e é a fila quem monta
        self._schedule_draw()

    def remove_sample(self, card):
        self._geometria_suja = True
        if card is self._card_em_desenho:
            self._abandonar_desenho()
        self.samples.remove(card.sample)
        self.cards.remove(card)
        card.destroy()
        self._sync_cards()

    # ---------- montagem de nomes ----------

    def display_name_for(self, sample):
        return self.name_mapping.get(sample["code"].lower(), sample["code"])

    # ---------- exportação ----------

    def _dados_da_amostra(self, sample):
        """Classifica uma amostra com o tubo e o limite que estão valendo
        agora. É barato (milissegundos), então quem exporta recalcula em
        vez de depender do que o cartão tem guardado."""
        kept, removed = apply_exclusions(sample["elements"], self.tube_z)
        major, trace, total = classify(kept, self.threshold)
        return kept, removed, major, trace, total

    def figura_para_arquivo(self, sample):
        """A figura de uma amostra no tamanho padrão (14 polegadas), pra
        imagem salva ficar sempre igual — a do cartão acompanha a largura
        da janela, esta não."""
        kept, _, major, trace, total = self._dados_da_amostra(sample)
        return build_sample_figure(kept, major, trace, total,
                                   self.display_name_for(sample))

    def bloco_de_texto(self, sample):
        """A tabela de uma amostra como texto — a mesma no botão do
        cartão e na exportação em lote."""
        _, removed, major, trace, total = self._dados_da_amostra(sample)
        return bloco_da_amostra(
            self.display_name_for(sample), sample["code"],
            linhas_da_tabela(major, trace, total), total,
            self.threshold, self.tube_var.get(),
            [e["symbol"] for e in removed])

    def export_all(self, modo):
        """Salva a batelada inteira. O `modo` diz o quê:

          "compilado"   -> um .txt e um .png com TODAS as amostras juntas,
                           direto na pasta escolhida;
          "individuais" -> um .txt e um .png para CADA amostra, dentro de
                           uma pasta nova criada na hora.

        Os nomes saem do mapeamento, quando ele está carregado.
        """
        if self._export is not None:
            return  # já tem uma exportação rodando
        if not self.samples:
            messagebox.showinfo("Nada para salvar",
                                "Carregue as amostras primeiro (botão 1).")
            return

        compilado = modo == "compilado"
        if compilado and len(self.samples) > MAX_AMOSTRAS_COMPILADO:
            altura = len(self.samples) * FIG_ALTURA_PX
            if not messagebox.askyesno(
                    "Imagem compilada muito grande",
                    "O PNG compilado é uma faixa única com os %d gráficos "
                    "empilhados: %d pixels de altura. Alguns programas não "
                    "abrem uma imagem desse tamanho.\n\nQuer continuar mesmo "
                    "assim?" % (len(self.samples), altura)):
                return

        pasta = filedialog.askdirectory(title="Escolha a pasta onde salvar")
        if not pasta:
            return
        if not compilado:
            # a batelada ganha uma pasta só dela, pra não espalhar dois
            # arquivos por amostra no meio do que já estava ali
            try:
                pasta = pasta_da_exportacao(pasta)
            except OSError as erro:
                messagebox.showerror("Erro ao salvar",
                                     "Não consegui criar a pasta:\n%s" % erro)
                return

        self._export = {
            "pasta": pasta,
            # a lista é congelada aqui: remover uma amostra no meio da
            # exportação não pode bagunçar a numeração
            "amostras": list(self.samples),
            "individuais": not compilado,
            "compilado": compilado,
            "indice": 0,
            "blocos": [],
            "pilha": PilhaDeImagens() if compilado else None,
            "usados": set(),
            "arquivos": [],
        }
        for botao in self.export_buttons:
            botao.state(["disabled"])
        self.export_label.config(text="Salvando\u2026")
        self.after(1, self._export_step)

    def _export_step(self):
        """Salva UMA amostra e devolve o controle ao Tk.

        Uma batelada grande leva alguns segundos (o gráfico é o caro), e
        a janela não pode congelar enquanto isso."""
        estado = self._export
        if estado is None:
            return
        amostras = estado["amostras"]
        indice = estado["indice"]
        if indice >= len(amostras):
            self._export_finish()
            return

        sample = amostras[indice]
        nome = self.display_name_for(sample)
        try:
            kept, removed, major, trace, total = self._dados_da_amostra(sample)
            bloco = bloco_da_amostra(
                nome, sample["code"], linhas_da_tabela(major, trace, total), total,
                self.threshold, self.tube_var.get(), [e["symbol"] for e in removed])

            fig = build_sample_figure(kept, major, trace, total, nome)
            try:
                if estado["individuais"]:
                    base = self._nome_livre(nome, sample["code"], estado["usados"])
                    estado["arquivos"].append(escrever_texto(
                        caminho_livre(estado["pasta"], base, ".txt"), bloco))
                    caminho = caminho_livre(estado["pasta"], base, ".png")
                    fig.savefig(caminho, dpi=200, bbox_inches="tight")
                    estado["arquivos"].append(caminho)
                if estado["compilado"]:
                    estado["blocos"].append(bloco)
                    estado["pilha"].adicionar(fig)
            finally:
                fig.clear()
        except Exception as erro:
            self._export_abort("a amostra %s" % nome, erro)
            return

        estado["indice"] += 1
        self.export_label.config(
            text="Salvando\u2026 %d de %d" % (estado["indice"], len(amostras)))
        self.after(1, self._export_step)

    def _export_finish(self):
        estado = self._export
        try:
            if estado["compilado"]:
                texto = documento_compilado(estado["blocos"], self.threshold,
                                            self.tube_var.get(), bool(self.name_mapping))
                estado["arquivos"].append(escrever_texto(
                    caminho_livre(estado["pasta"], "todas as amostras", ".txt"), texto))
                estado["arquivos"].append(estado["pilha"].salvar(
                    caminho_livre(estado["pasta"], "todas as amostras", ".png")))
        except Exception as erro:
            self._export_abort("o arquivo compilado", erro)
            return

        quantos, pasta = len(estado["arquivos"]), estado["pasta"]
        self._export_end()
        messagebox.showinfo("Pronto", "%d arquivo(s) salvo(s) em:\n%s" % (quantos, pasta))

    def _export_abort(self, o_que, erro):
        salvos = len(self._export["arquivos"])
        self._export_end()
        messagebox.showerror(
            "Erro ao salvar",
            "Parei em %s:\n%s\n\n%d arquivo(s) já tinham sido salvos."
            % (o_que, erro, salvos))

    def _export_end(self):
        self._export = None
        self.export_label.config(text="")
        for botao in self.export_buttons:
            botao.state(["!disabled"])

    @staticmethod
    def _nome_livre(nome, codigo, usados):
        """Nome de arquivo único dentro desta exportação: duas amostras
        podem ter o mesmo nome no mapeamento, e aí o código do arquivo
        entra pra desempatar."""
        base = nome_de_arquivo(nome)
        if base.lower() in usados:
            base = nome_de_arquivo("%s - %s" % (nome, codigo))
        usados.add(base.lower())
        return base

    # ---------- renderização ----------

    def altura_estimada(self, linhas, com_aviso, minimizado=False):
        """Quanto um cartão VAI medir depois de montado.

        Serve pra reservar o espaço certo enquanto ele ainda é um
        retângulo vazio; se o palpite estivesse longe, a barra de
        rolagem daria um pulo quando o cartão nascesse de verdade.
        """
        if self._alturas is None:
            return ALTURA_CHUTE_PX
        cabecalho, aviso, tabela_base, tabela_linha = self._alturas
        altura = RECHEIO_PX + cabecalho
        if minimizado:
            return altura
        altura += FIG_ALTURA_PX + ESPACO_TABELA_PX
        altura += tabela_base + tabela_linha * max(linhas, 1)
        if com_aviso:
            altura += aviso + ESPACO_AVISO_PX
        return altura

    def medir_alturas(self, card):
        """Tira as medidas do primeiro cartão montado.

        Só widgets "folha" servem aqui (botão, aviso, tabela): a altura
        pedida por um quadro depende do layout, que só é calculado
        depois — a desses aqui já vale na hora em que são criados.
        """
        if self._alturas is not None:
            return
        tree, original = card.tree, card._altura_tabela
        tree.configure(height=1)
        uma = tree.winfo_reqheight()
        tree.configure(height=11)
        onze = tree.winfo_reqheight()
        tree.configure(height=original)
        linha = (onze - uma) / 10.0
        self._alturas = (card.toggle_btn.winfo_reqheight(),
                         card.warn_label.winfo_reqheight(),
                         int(round(uma - linha)), int(round(linha)))

    def _sync_cards(self):
        """Garante um cartão por amostra, criando só os que faltam — e
        em lotes, devolvendo o controle ao Tk entre um lote e outro."""
        if self._sync_job is not None:
            self.after_cancel(self._sync_job)
            self._sync_job = None

        for sample in self.samples[len(self.cards):len(self.cards) + CARTOES_POR_LOTE]:
            self.cards.append(SampleCard(self.cards_frame, self, sample))
            self._geometria_suja = True

        if self.samples:
            self.empty_label.pack_forget()
        else:
            self.empty_label.pack()

        # No meio de uma batelada não adianta desenhar: os cartões que
        # ainda vão nascer mudam a posição de todo mundo, e conferir
        # quem está visível obriga o Tk a remontar o layout da lista
        # inteira. Desenha no primeiro lote (pra tela não ficar vazia) e
        # de novo quando o último chegar.
        falta = len(self.cards) < len(self.samples)
        self.refresh(desenhar=not falta or len(self.cards) <= CARTOES_POR_LOTE)
        if falta:
            self._sync_job = self.after(1, self._sync_cards)

    def refresh(self, desenhar=True):
        """Atualiza a parte barata de todos os cartões (nome, avisos,
        altura da tabela) e agenda o desenho dos que ficaram vencidos."""
        for card in self.cards:
            card.update_data(self.tube_z, self.threshold, self.display_name_for(card.sample))
        if desenhar:
            self._schedule_draw()

    def _schedule_draw(self, delay=0):
        """Agenda a fila de desenho daqui a `delay` ms.

        Cada rolagem adia o desenho — desenhar no meio do movimento trava
        a roda —, mas o adiamento tem TETO_DE_ESPERA_MS de teto. Sem esse
        teto, rolar sem parar adiava o desenho indefinidamente e a tela
        ficava só com cartões vazios.
        """
        self._draw_queue = None  # rolou ou mudou algo: refaz a lista
        if self._draw_job is not None:
            self.after_cancel(self._draw_job)
            self._draw_job = None
        if not any(card.needs_draw or card.table_key != card.state_key
                   for card in self.cards):
            self._draw_limite = None
            return
        agora = time.monotonic()
        if self._draw_limite is None:
            self._draw_limite = agora + TETO_DE_ESPERA_MS / 1000.0
        espera = min(delay, max(0.0, self._draw_limite - agora) * 1000.0)
        self._draw_job = self.after(int(espera), self._draw_next)

    def _visible_cards(self):
        """Cartões que estão (ou estão quase) na área visível.

        A passada de geometria do Tk só acontece quando a lista mudou de
        FORMA (cartão novo, removido, minimizado, largura nova). Rolar
        não move cartão nenhum — move a janela sobre eles —, então o
        `canvasy` já basta, e pedir a passada a cada clique da roda
        custava uns 30 ms à toa.
        """
        if self._geometria_suja:
            self.cards_frame.update_idletasks()
            self._geometria_suja = False
        topo = self.scroll_canvas.canvasy(0) - MARGEM_VISIVEL_PX
        base = topo + self.scroll_canvas.winfo_height() + 2 * MARGEM_VISIVEL_PX
        meio = (topo + base) / 2
        visiveis = []
        for card in self.cards:
            y = card.frame.winfo_y()
            if y > base:
                break  # a lista está em ordem: daqui pra baixo é tudo fora
            altura = card.frame.winfo_reqheight()
            if y + altura >= topo:
                visiveis.append((abs(y + altura / 2 - meio), card))
        # o que está mais no meio da tela primeiro: rolando rápido, é o
        # cartão que a pessoa está olhando que ganha a vez
        visiveis.sort(key=lambda par: par[0])

        prontos = []
        for _, card in visiveis:
            # montar vale pra todo cartão que aparece — mesmo minimizado,
            # ele precisa mostrar o cabeçalho com o nome e os botões
            if not card.montado:
                card.montar()
                self._geometria_suja = True  # o cartão real tem outra altura
            if not card.collapsed:
                prontos.append(card)  # minimizado não tem o que desenhar
        return prontos

    def _draw_next(self):
        """Desenha UM cartão visível que esteja vencido e devolve o
        controle ao Tk.

        Um de cada vez, com uma volta ao laço de eventos entre eles, é o
        que mantém a janela respondendo: dá pra rolar a tela ou mexer no
        slider no meio de uma batelada grande.
        """
        self._draw_job = None
        if self._draw_queue is None:
            self._draw_queue = self._visible_cards()
            # as tabelas de TODOS os visíveis de uma vez: são baratas, e
            # assim os números já aparecem enquanto os gráficos vêm vindo
            for card in self._draw_queue:
                card.montar_tabela()
            # descobrir quem está visível já custou o tempo desta rodada
            # (é uma passada de geometria do Tk): os pedaços de desenho
            # ficam pra próxima, senão essa chamada dobra de tamanho
            self._draw_job = self.after(1, self._draw_next)
            return

        # Enfia pedaços de desenho até estourar o orçamento e devolve o
        # controle ao Tk. Um cartão inteiro leva uns 150 ms; em pedaços
        # de ~25 ms, a roda do mouse continua respondendo no meio.
        limite = time.monotonic() + ORCAMENTO_MS / 1000.0
        while True:
            if self._passos is None and not self._comecar_cartao():
                return  # nada visível pra desenhar
            try:
                next(self._passos)
            except StopIteration:
                self._passos = None
                self._card_em_desenho = None
                self._draw_limite = None  # desenhou: a espera recomeça
            if time.monotonic() >= limite:
                break
        self._draw_job = self.after(1, self._draw_next)

    def _comecar_cartao(self):
        """Pega o próximo cartão da fila que ainda precisa de desenho."""
        while self._draw_queue:
            card = self._draw_queue.pop(0)
            if card.needs_draw:
                self._passos = card.iniciar_desenho()
                self._card_em_desenho = card
                return True
        return False

    def _abandonar_desenho(self):
        """Larga o desenho pela metade (o cartão sumiu, ou o que ele
        mostraria mudou). O cartão continua marcado como vencido, então
        será desenhado de novo do começo."""
        self._passos = None
        self._card_em_desenho = None
