"""Catalogador de Espectros FRX.

O pacote está dividido em camadas:

  nucleo/        lê os arquivos e aplica as regras (dados puros)
  banco/         o banco central das amostras: pastas editáveis (SQLite)
  graficos/      transforma esses dados em figuras matplotlib
  exportacao.py  monta o conteúdo dos arquivos que o programa salva
  interface/     a janela Tkinter que amarra tudo

A dependência é sempre num sentido só:
interface -> exportacao -> graficos -> nucleo, com `banco/` pendurado
direto no núcleo (ele só precisa da tabela periódica). O núcleo não sabe
que existe gráfico, o gráfico não sabe que existe janela, o banco não
sabe que existe gráfico nem janela, e a exportação não sabe onde os
arquivos vão parar — dá para usar qualquer uma das camadas de baixo
sozinha, sem abrir janela nenhuma.

Existe ainda uma SEGUNDA versão do programa, em `generico/`, congelada
como estava antes do banco de amostras: é o catalogador genérico, que faz
a distinção majoritário/traço de qualquer tipo de amostra sem saber de
commodity nem de pastas. As duas são independentes.
"""

__version__ = "2.0.0"
