"""A janela do programa (Tkinter): botões, slider, cards e tabelas.

Toda a lógica de dados vive em `catalogador.nucleo` e todo o desenho em
`catalogador.graficos`. Esta camada só amarra as duas coisas na tela.
"""

import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from ..nucleo.leitura import parse_frx_file, parse_mapping
from ..nucleo.classificacao import TUBE_OPTIONS, apply_exclusions, classify
from ..graficos.figura import build_sample_figure


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Pizzas XRF")
        self.geometry("1180x780")

        # -------- estado da aplicação --------
        self.samples = []          # [{"code": str, "elements": [...]}]
        self.name_mapping = {}     # {"081025af": "Madeira 123", ...}
        self.threshold = 10.0
        self.tube_z = None
        self._active_figures = []  # figuras matplotlib abertas no momento
        self._render_after_id = None  # controla o "debounce" do slider (ver on_threshold_change)

        self._build_top_controls()
        self._build_scroll_area()
        self.render_all()

    # ---------- construção da UI ----------

    def _build_top_controls(self):
        frame = ttk.Frame(self, padding=12)
        frame.pack(fill="x")

        ttk.Button(frame, text="1. Carregar amostras (.txt)",
                   command=self.load_samples).grid(row=0, column=0, padx=4, pady=4, sticky="w")
        ttk.Button(frame, text="2. Carregar mapeamento (.csv/.txt)",
                   command=self.load_mapping).grid(row=0, column=1, padx=4, pady=4, sticky="w")
        self.mapping_label = ttk.Label(frame, text="Nenhum mapeamento carregado.")
        self.mapping_label.grid(row=0, column=2, padx=10, sticky="w")

        ttk.Label(frame, text="Tubo de raios X utilizado:").grid(row=1, column=0, sticky="w", pady=(12, 0))
        self.tube_var = tk.StringVar(value="Nenhum")
        tube_combo = ttk.Combobox(frame, textvariable=self.tube_var, values=list(TUBE_OPTIONS.keys()),
                                   state="readonly", width=18)
        tube_combo.grid(row=1, column=1, sticky="w", pady=(12, 0))
        tube_combo.bind("<<ComboboxSelected>>", self.on_tube_change)

        ttk.Label(frame, text="Limite do grupo traço:").grid(row=2, column=0, sticky="w", pady=(12, 0))
        self.threshold_var = tk.DoubleVar(value=10.0)
        slider = ttk.Scale(frame, from_=1, to=50, orient="horizontal",
                            variable=self.threshold_var, command=self.on_threshold_change, length=320)
        slider.grid(row=2, column=1, sticky="w", pady=(12, 0))
        slider.bind("<ButtonRelease-1>", self.on_slider_release)

        self.threshold_entry_var = tk.StringVar(value="10.0")
        threshold_entry = ttk.Spinbox(
            frame, from_=1, to=50, increment=0.5, width=6,
            textvariable=self.threshold_entry_var, command=self.on_threshold_entry_commit,
        )
        threshold_entry.grid(row=2, column=2, sticky="w", pady=(12, 0), padx=(8, 0))
        threshold_entry.bind("<Return>", self.on_threshold_entry_commit)
        threshold_entry.bind("<FocusOut>", self.on_threshold_entry_commit)

        self.threshold_label = ttk.Label(frame, text="10.0%")
        self.threshold_label.grid(row=2, column=3, sticky="w", pady=(12, 0))

    def _build_scroll_area(self):
        """Cria uma área rolável, já que podemos ter muitas amostras
        carregadas de uma vez (processamento em batelada)."""
        container = ttk.Frame(self)
        container.pack(fill="both", expand=True)

        canvas = tk.Canvas(container, borderwidth=0, highlightthickness=0)
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        self.cards_frame = ttk.Frame(canvas)

        self.cards_frame.bind(
            "<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.create_window((0, 0), window=self.cards_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # rolar com a roda do mouse
        canvas.bind_all("<MouseWheel>", lambda e: canvas.yview_scroll(int(-e.delta / 120), "units"))

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
        self.render_all()

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
        self.render_all()

    def on_tube_change(self, event=None):
        self.tube_z = TUBE_OPTIONS[self.tube_var.get()]
        self.render_all()

    def on_threshold_change(self, value):
        # Isso é chamado a cada pixel que o slider se move, então só
        # atualizamos o texto na hora (é barato). O redesenho pesado dos
        # gráficos (render_all) reconstrói todas as pizzas/tabelas de
        # todas as amostras, então NÃO rola a cada movimento — só quando
        # o usuário solta o botão do mouse (on_slider_release) ou para de
        # arrastar por um tempo (debounce, como rede de segurança para
        # quem usa o teclado/setas).
        self.threshold = float(value)
        self.threshold_label.config(text=f"{self.threshold:.1f}%")
        self.threshold_entry_var.set(f"{self.threshold:.1f}")

        if self._render_after_id is not None:
            self.after_cancel(self._render_after_id)
        self._render_after_id = self.after(400, self._debounced_render)

    def _debounced_render(self):
        self._render_after_id = None
        self.render_all()

    def on_slider_release(self, event=None):
        if self._render_after_id is not None:
            self.after_cancel(self._render_after_id)
            self._render_after_id = None
        self.render_all()

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
        self.render_all()

    def remove_sample(self, index):
        del self.samples[index]
        self.render_all()

    def save_figure(self, fig, name):
        path = filedialog.asksaveasfilename(
            defaultextension=".png",
            initialfile=f"{name}.png",
            filetypes=[("Imagem PNG", "*.png")],
        )
        if path:
            fig.savefig(path, dpi=200, bbox_inches="tight")
            messagebox.showinfo("Salvo", f"Imagem salva em:\n{path}")

    # ---------- montagem de nomes ----------

    def display_name_for(self, sample):
        return self.name_mapping.get(sample["code"].lower(), sample["code"])

    # ---------- renderização ----------

    def render_all(self):
        # fecha as figuras matplotlib da renderização anterior, senão
        # elas ficam acumulando na memória a cada mudança de slider
        for fig in self._active_figures:
            plt.close(fig)
        self._active_figures = []

        for widget in self.cards_frame.winfo_children():
            widget.destroy()

        if not self.samples:
            ttk.Label(self.cards_frame, text="Nenhuma amostra carregada ainda.", padding=24).pack()
            return

        for index, sample in enumerate(self.samples):
            self._render_sample_card(sample, index)

    def _render_sample_card(self, sample, index):
        kept, removed = apply_exclusions(sample["elements"], self.tube_z)
        major, trace, total = classify(kept, self.threshold)
        display_name = self.display_name_for(sample)

        card = ttk.Frame(self.cards_frame, relief="groove", borderwidth=1, padding=10)
        card.pack(fill="x", padx=10, pady=8)

        fig = build_sample_figure(kept, major, trace, total, display_name)
        self._active_figures.append(fig)

        header = ttk.Frame(card)
        header.pack(fill="x")
        ttk.Label(header, text=display_name, font=("Segoe UI", 12, "bold")).pack(side="left")
        ttk.Label(header, text=f"   arquivo: {sample['code']}", foreground="#6B6250").pack(side="left")
        ttk.Button(header, text="Remover", command=lambda i=index: self.remove_sample(i)).pack(side="right")
        ttk.Button(header, text="Salvar imagem (PNG)",
                   command=lambda f=fig, n=display_name: self.save_figure(f, n)).pack(side="right", padx=6)

        canvas_widget = FigureCanvasTkAgg(fig, master=card)
        canvas_widget.draw()
        canvas_widget.get_tk_widget().pack(fill="x")

        if removed:
            removed_syms = ", ".join(e["symbol"] for e in removed)
            ttk.Label(
                card,
                text=f"Descartado nesta amostra: {removed_syms} (Ar e/ou elemento do tubo — não fazem parte da madeira)",
                foreground="#B8792E",
            ).pack(anchor="w", pady=(4, 0))

        self._build_table(card, major, trace, total)

    def _build_table(self, parent, major, trace, total):
        columns = ("z", "elemento", "area", "pct", "grupo")
        headers = {"z": "Z", "elemento": "Elemento", "area": "Área (cps)", "pct": "% do total", "grupo": "Grupo"}

        rows = (
            [(e["z"], e["symbol"], f"{e['area']:.0f}", f"{e['area']/total*100:.2f}%", "majoritário") for e in major]
            + [(e["z"], e["symbol"], f"{e['area']:.0f}", f"{e['area']/total*100:.2f}%", "traço") for e in trace]
        )
        rows.sort(key=lambda r: -float(r[2]))

        height = max(1, min(10, len(rows)))
        tree = ttk.Treeview(parent, columns=columns, show="headings", height=height)
        for col in columns:
            tree.heading(col, text=headers[col])
            tree.column(col, width=110, anchor="center")
        for row in rows:
            tree.insert("", "end", values=row)
        tree.pack(fill="x", pady=(8, 0))
