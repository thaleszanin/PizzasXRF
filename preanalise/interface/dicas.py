# -*- coding: utf-8 -*-
"""As dicas dos botões: o balãozinho que aparece com o mouse parado.

O Tk não traz isso pronto. Aqui é uma janela sem moldura
(`overrideredirect`) com um rótulo dentro, que a janela principal
mostra perto do ponteiro depois de ESPERA_MS parado em cima do widget
e esconde ao sair, ao clicar ou ao rolar. É UMA janela pra aplicação
inteira, criada na primeira dica e reaproveitada — cada dica é só um
par de `bind`s no widget.

    app.dicas.registrar(botao, "Guarda as amostras da tela no banco.")

O rótulo usa o estilo "Dica.TLabel" do tema de agora, então a dica
troca de cor junto com o resto.
"""

import tkinter as tk
from tkinter import ttk

# Quanto o mouse precisa ficar parado em cima do widget.
ESPERA_MS = 600
# Onde o balão aparece em relação ao ponteiro.
DESLOCAMENTO = (12, 18)
# Largura máxima do texto antes de quebrar linha.
LARGURA_PX = 340


class Dicas:
    def __init__(self, app):
        self.app = app
        self._janela = None
        self._rotulo = None
        self._agendada = None
        self._widget = None

    def registrar(self, widget, texto):
        """Faz `widget` mostrar `texto` quando o mouse parar em cima."""
        widget.bind("<Enter>", lambda e, t=texto: self._entrou(e.widget, t), add="+")
        widget.bind("<Leave>", lambda _e: self.esconder(), add="+")
        widget.bind("<ButtonPress>", lambda _e: self.esconder(), add="+")
        return widget

    # ---------- mostrar e esconder ----------

    def _entrou(self, widget, texto):
        self.esconder()
        self._widget = widget
        self._agendada = self.app.after(ESPERA_MS, lambda: self._mostrar(widget, texto))

    def _mostrar(self, widget, texto):
        self._agendada = None
        try:
            if not widget.winfo_viewable():
                return
            x = widget.winfo_pointerx() + DESLOCAMENTO[0]
            y = widget.winfo_pointery() + DESLOCAMENTO[1]
        except tk.TclError:
            return  # o widget morreu enquanto a dica esperava
        janela = self._garantir()
        # a moldura de 1 px é o fundo da janela aparecendo em volta do rótulo
        janela.configure(background=self.app.cores["borda"])
        self._rotulo.configure(text=texto, style=self.app.estilo("Dica.TLabel"))
        janela.update_idletasks()
        # não deixa o balão sair da tela pela direita ou por baixo
        largura, altura = janela.winfo_reqwidth(), janela.winfo_reqheight()
        x = min(x, janela.winfo_screenwidth() - largura - 4)
        y = min(y, janela.winfo_screenheight() - altura - 4)
        janela.geometry("+%d+%d" % (x, y))
        janela.deiconify()
        janela.lift()

    def esconder(self):
        if self._agendada is not None:
            self.app.after_cancel(self._agendada)
            self._agendada = None
        self._widget = None
        if self._janela is not None:
            self._janela.withdraw()

    def _garantir(self):
        if self._janela is None:
            self._janela = tk.Toplevel(self.app)
            self._janela.withdraw()
            self._janela.overrideredirect(True)
            # fica por cima da janela principal, mas não rouba o foco
            self._janela.attributes("-topmost", True)
            self._rotulo = ttk.Label(self._janela, wraplength=LARGURA_PX,
                                     justify="left", padding=(8, 5),
                                     style=self.app.estilo("Dica.TLabel"))
            self._rotulo.pack(padx=1, pady=1)
        return self._janela
