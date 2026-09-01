"""Catalogador de Espectros FRX.

O pacote está dividido em três camadas, uma pasta cada:

  nucleo/     lê os arquivos e aplica as regras (dados puros)
  graficos/   transforma esses dados em figuras matplotlib
  interface/  a janela Tkinter que amarra as duas coisas

A dependência é sempre num sentido só: interface -> graficos -> nucleo.
O núcleo não sabe que existe gráfico, e o gráfico não sabe que existe
janela — dá para usar qualquer uma das camadas de baixo sozinha.
"""

__version__ = "1.0.0"
