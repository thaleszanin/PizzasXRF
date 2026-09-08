# -*- coding: utf-8 -*-
"""Pré-análise dos espectros de XRF.

O programa que roda ANTES do catalogador: lê a batelada de .txt, mede o
erro de cada elemento e diz quais amostras precisam ser medidas de novo
sem aquele elemento.

O pacote está dividido em camadas, e a dependência anda sempre num
sentido só — interface -> planilha -> nucleo:

  nucleo/      lê o .txt (com a coluna do erro), calcula o erro relativo
               e escreve os logs. Dados puros, sem interface nenhuma
  planilha.py  monta o .xlsx: a batelada empilhada, com as linhas
               reprovadas em destaque e o log ao lado de cada amostra
  interface/   a janela Tkinter que amarra as duas coisas

O núcleo não sabe que existe Excel e a planilha não sabe onde o arquivo
vai parar, então dá pra rodar a pré-análise inteira de um script, sem
abrir janela nenhuma.
"""

__version__ = "1.0.0"
