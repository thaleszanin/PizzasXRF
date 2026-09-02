"""Interface gráfica em Tkinter.

O backend do matplotlib é escolhido AQUI, e não lá no módulo de
gráficos: assim `catalogador.graficos` continua utilizável fora da
janela (por exemplo, gerando PNGs num script com o backend "Agg"),
enquanto quem importa a interface já recebe o TkAgg configurado antes
de qualquer figura ser criada.
"""

import matplotlib

matplotlib.use("TkAgg")

from .app import App

__all__ = ["App"]
