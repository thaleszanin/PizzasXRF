# -*- coding: utf-8 -*-
"""A lista de tipos de gráfico que o programa sabe desenhar.

Todo tipo é uma função com a MESMA cara:

    def desenha(ax, sizes, labels, colors) -> gerador

Ela desenha um painel (um dos três de uma amostra) em pedaços, dando um
`yield` entre uma etapa e outra, e devolve no fim ou um `RotulosDaPizza`
— quando o tipo é redondo e os três painéis precisam ficar do mesmo
tamanho — ou `None`, quando não há nada a igualar.

Para acrescentar um tipo novo: escreva a função (em `pizza.py` ou
`barras.py`, ou num módulo novo) e ponha uma linha em `TIPOS`. Ela
aparece sozinha na caixinha da janela, na ordem em que está escrita
aqui — por isso a Pizza vem primeiro: é a que abre por padrão.
"""

from .barras import (passos_da_barra_empilhada, passos_das_barras,
                     passos_do_pareto)
from .pizza import passos_da_pizza

# Quanto do raio fica vazio no meio da rosca.
BURACO_DA_ROSCA = 0.45


def _pizza(ax, sizes, labels, colors):
    return (yield from passos_da_pizza(ax, sizes, labels, colors))


def _rosca(ax, sizes, labels, colors):
    return (yield from passos_da_pizza(ax, sizes, labels, colors,
                                       buraco=BURACO_DA_ROSCA))


# A ORDEM importa: é a ordem da caixinha na janela, e a primeira é a
# que o programa abre selecionada.
TIPOS = {
    "Pizza": _pizza,
    "Rosca": _rosca,
    "Barras": passos_das_barras,
    "Barra empilhada": passos_da_barra_empilhada,
    "Pareto": passos_do_pareto,
}

TIPO_PADRAO = next(iter(TIPOS))


def desenhador(tipo):
    """A função de desenho de um tipo. Nome desconhecido cai no padrão,
    pra uma configuração velha nunca deixar a tela vazia."""
    return TIPOS.get(tipo, TIPOS[TIPO_PADRAO])
