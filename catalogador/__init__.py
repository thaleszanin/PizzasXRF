"""Catalogador de Espectros FRX.

O pacote está dividido em camadas:

  nucleo/        lê os arquivos e aplica as regras (dados puros)
  graficos/      transforma esses dados em figuras matplotlib
  exportacao.py  monta o conteúdo dos arquivos que o programa salva
  interface/     a janela Tkinter que amarra tudo

A dependência é sempre num sentido só:
interface -> exportacao -> graficos -> nucleo. O núcleo não sabe que
existe gráfico, o gráfico não sabe que existe janela, e a exportação não
sabe onde os arquivos vão parar — dá para usar qualquer uma das camadas
de baixo sozinha, sem abrir janela nenhuma.
"""

__version__ = "1.0.0"
