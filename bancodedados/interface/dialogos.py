# -*- coding: utf-8 -*-
"""Janelinhas de pergunta com a cara do programa.

O `simpledialog` do Tkinter abre uma caixa cinza do Windows, fora do
tema — e o programa abre no modo escuro. Estas aqui são feitas dos
mesmos widgets ttk da janela principal, então nascem pintadas e trocam
de tema junto com ela.

Todas são modais: a janela principal espera a resposta. Devolvem o que
foi respondido, ou None se a pessoa cancelou (ou fechou no X).
"""

import tkinter as tk
from tkinter import ttk


class Dialogo(tk.Toplevel):
    """A base: uma janela modal, centrada sobre a principal, com o
    corpo montado por `montar` e os botões OK/Cancelar embaixo."""

    def __init__(self, app, titulo, ok="OK", cancelar="Cancelar", largura=420):
        super().__init__(app)
        self.app = app
        self.resultado = None
        self._aviso = None
        self.title(titulo)
        self.configure(background=app.cores["fundo"])
        self.resizable(False, False)
        self.transient(app)

        corpo = ttk.Frame(self, padding=(16, 14, 16, 8), style=app.estilo("TFrame"))
        corpo.pack(fill="both", expand=True)
        self.montar(corpo)

        rodape = ttk.Frame(self, padding=(16, 4, 16, 14), style=app.estilo("TFrame"))
        rodape.pack(fill="x")
        self.rodape = rodape
        ttk.Button(rodape, text=cancelar, style=app.estilo("Neutro.TButton"),
                   command=self.cancelar).pack(side="right")
        self.botao_ok = ttk.Button(rodape, text=ok, style=app.estilo("TButton"),
                                   command=self.confirmar)
        self.botao_ok.pack(side="right", padx=(0, 8))

        self.bind("<Return>", lambda _e: self.confirmar())
        self.bind("<Escape>", lambda _e: self.cancelar())
        self.protocol("WM_DELETE_WINDOW", self.cancelar)

        self.update_idletasks()
        largura = max(largura, self.winfo_reqwidth())
        altura = self.winfo_reqheight()
        x = app.winfo_rootx() + (app.winfo_width() - largura) // 2
        y = app.winfo_rooty() + (app.winfo_height() - altura) // 3
        self.geometry("%dx%d+%d+%d" % (largura, altura, max(0, x), max(0, y)))
        self.grab_set()
        self.focar()

    def montar(self, corpo):
        raise NotImplementedError

    def focar(self):
        self.botao_ok.focus_set()

    def responder(self):
        """O que sai do diálogo quando a pessoa confirma. Devolver None
        (ou levantar ValueError com a mensagem) mantém a janela aberta."""
        raise NotImplementedError

    def confirmar(self):
        try:
            resultado = self.responder()
        except ValueError as erro:
            self.avisar(str(erro))
            return
        if resultado is None:
            return
        self.resultado = resultado
        self.destroy()

    def cancelar(self):
        self.resultado = None
        self.destroy()

    def avisar(self, texto):
        if self._aviso is None:
            self._aviso = ttk.Label(self, wraplength=380, padding=(16, 0, 16, 4),
                                    style=self.app.estilo("AvisoFundo.TLabel"))
            self._aviso.pack(fill="x", before=self.rodape)
        self._aviso.config(text=texto)
        self.update_idletasks()
        self.geometry("")  # deixa a janela crescer pro aviso caber

    def esperar(self):
        """Bloqueia até a janela fechar e devolve a resposta."""
        self.wait_window(self)
        return self.resultado


class PerguntaDeTexto(Dialogo):
    """Uma linha de texto: nome novo de aba, de amostra, de categoria."""

    def __init__(self, app, titulo, rotulo, inicial="", ok="OK"):
        self.rotulo, self.inicial = rotulo, inicial
        super().__init__(app, titulo, ok=ok)

    def montar(self, corpo):
        ttk.Label(corpo, text=self.rotulo, wraplength=380,
                  style=self.app.estilo("TLabel")).pack(anchor="w")
        self.var = tk.StringVar(value=self.inicial)
        self.entrada = ttk.Entry(corpo, textvariable=self.var, width=44,
                                 style=self.app.estilo("TEntry"))
        self.entrada.pack(fill="x", pady=(8, 4))

    def focar(self):
        self.entrada.focus_set()
        self.entrada.selection_range(0, "end")

    def responder(self):
        texto = self.var.get().strip()
        if not texto:
            raise ValueError("Escreva alguma coisa — ou cancele.")
        return texto


class Escolha(Dialogo):
    """Uma opção de uma lista: em que banco guardar, por exemplo."""

    def __init__(self, app, titulo, rotulo, opcoes, inicial=None, ok="OK"):
        self.rotulo, self.opcoes, self.inicial = rotulo, list(opcoes), inicial
        super().__init__(app, titulo, ok=ok)

    def montar(self, corpo):
        ttk.Label(corpo, text=self.rotulo, wraplength=380,
                  style=self.app.estilo("TLabel")).pack(anchor="w")
        self.var = tk.StringVar(value=self.inicial or self.opcoes[0])
        self.caixa = ttk.Combobox(corpo, textvariable=self.var, values=self.opcoes,
                                  state="readonly", width=42,
                                  style=self.app.estilo("TCombobox"))
        self.caixa.pack(fill="x", pady=(8, 4))

    def focar(self):
        self.caixa.focus_set()

    def responder(self):
        return self.var.get()


def perguntar_texto(app, titulo, rotulo, inicial="", ok="OK"):
    return PerguntaDeTexto(app, titulo, rotulo, inicial, ok).esperar()


def escolher(app, titulo, rotulo, opcoes, inicial=None, ok="OK"):
    return Escolha(app, titulo, rotulo, opcoes, inicial, ok).esperar()
