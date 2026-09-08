# -*- coding: utf-8 -*-
"""Duas medidas que todo desenho com rótulo precisa.

Ficam num módulo à parte porque a pizza e as barras usam as mesmas
duas: um renderer só pra MEDIR texto (sem desenhar) e os coeficientes
da conversão dados -> pixels de um eixo.
"""

from matplotlib.backends.backend_agg import FigureCanvasAgg


def renderer_para_medir(fig):
    """Devolve um renderer só pra MEDIR texto, sem desenhar nada.

    Medir a caixa de um `ax.text` precisa de um renderer, não de um
    desenho pronto. Antes isso era feito com `fig.canvas.draw()`, que
    redesenhava as TRÊS pizzas da figura inteira a cada medição — era
    de longe a parte mais cara do programa.
    """
    canvas = fig.canvas
    if canvas is None or not hasattr(canvas, "get_renderer"):
        canvas = FigureCanvasAgg(fig)
    return canvas.get_renderer()


def escala(ax):
    """Coeficientes da conversão dados -> pixels: px = sx*x + tx e
    py = sy*y + ty.

    `ax.transData` é afim e alinhada aos eixos, então esses quatro
    números descrevem a transformação inteira. Fazer a conta na mão
    evita milhares de chamadas a `transform()`/`inverted()` (cada uma
    monta e desmonta arrays do numpy) durante a busca binária do
    layout dos rótulos.
    """
    (x0, y0), (x1, y1) = ax.transData.transform([(0.0, 0.0), (1.0, 1.0)])
    return x1 - x0, x0, y1 - y0, y0
