# -*- coding: utf-8 -*-
"""Repinta uma figura já desenhada nas cores do tema da janela.

Por que DEPOIS de desenhar, e não durante: o desenho é a parte cara e
delicada do programa (os rótulos da pizza são posicionados medindo texto
em pixels), e cor nenhuma interfere nessa conta. Separando, o desenho
continua sem saber que existe tema, e esta função é uma passada rápida
por algumas dezenas de artistas do matplotlib.

Quem chama é a interface, e SÓ para a figura que aparece na tela. As
figuras que viram arquivo não passam por aqui: o .png salvo sai sempre
no fundo branco de sempre, esteja a janela clara ou escura — o que se
imprime e o que se cola num relatório não deve depender do tema em que
a janela estava aberta na hora.
"""

from .estilo import COR_DA_CURVA, COR_DA_GRADE
from .pizza import COR_DA_LINHA_GUIA

# Cor com que o matplotlib nasce escrevendo — é assim que reconhecemos o
# texto que ainda não teve cor escolhida por ninguém (o branco dos
# rótulos dentro da barra empilhada, por exemplo, NÃO entra nessa lista,
# e por isso continua branco).
PRETO_PADRAO = ("black", "k", "#000000")

TEMAS = {
    "claro": {
        "fundo": "#FFFFFF",
        "frente": "#1A1A1A",
        "grade": COR_DA_GRADE,
        "curva": COR_DA_CURVA,
        "guia": COR_DA_LINHA_GUIA,
    },
    "escuro": {
        "fundo": "#242424",     # o mesmo painel do cartão, na janela
        "frente": "#E8E6E3",
        "grade": "#3E4148",
        "curva": "#79C08E",     # o verde da curva, clareado pro fundo escuro
        "guia": "#8C8778",
    },
}


def _familia(*cores):
    """As formas que uma mesma cor pode ter na figura: a que o
    matplotlib pôs, mais a que cada tema já pode ter posto ali."""
    return tuple(c.lower() for c in cores)


# Reconhecer as cores de TODOS os temas (e não só a original) é o que
# permite repintar uma figura já pintada — sem isso, a segunda troca de
# tema não encontraria mais nada para mexer.
_FRENTES = _familia(*(PRETO_PADRAO + tuple(t["frente"] for t in TEMAS.values())))
_GRADES = _familia(COR_DA_GRADE, *(t["grade"] for t in TEMAS.values()))
_CURVAS = _familia(COR_DA_CURVA, *(t["curva"] for t in TEMAS.values()))
_GUIAS = _familia(COR_DA_LINHA_GUIA, *(t["guia"] for t in TEMAS.values()))


def _e_uma(cor, familia):
    return isinstance(cor, str) and cor.lower() in familia


def pintar(fig, nome):
    """Passa o tema `nome` ("claro" ou "escuro") numa figura pronta.

    Vale nos dois sentidos e quantas vezes for: a figura pintada de
    escuro volta ao claro exatamente igual, porque cada cor é procurada
    em TODAS as formas que ela pode ter (a original do matplotlib e a
    de cada tema). O que foi pintado de propósito com outra cor — o
    branco dos rótulos dentro da barra empilhada, as fatias — não entra
    em família nenhuma e fica onde está.
    """
    tema = TEMAS[nome]
    frente, grade = tema["frente"], tema["grade"]

    fig.patch.set_facecolor(tema["fundo"])
    for texto in fig.texts:          # o título da amostra, lá em cima
        if _e_uma(texto.get_color(), _FRENTES):
            texto.set_color(frente)

    for ax in fig.axes:
        # o eixo da direita do Pareto é todo da cor da curva; os outros
        # seguem a cor de texto do tema
        da_curva = _e_uma(ax.yaxis.label.get_color(), _CURVAS)
        cor_do_eixo = tema["curva"] if da_curva else frente

        ax.patch.set_facecolor(tema["fundo"])
        ax.title.set_color(frente)
        ax.xaxis.label.set_color(cor_do_eixo)
        ax.yaxis.label.set_color(cor_do_eixo)
        ax.tick_params(colors=cor_do_eixo)
        for lado, borda in ax.spines.items():
            borda.set_color(tema["curva"] if da_curva else grade)
        for linha in ax.get_xgridlines() + ax.get_ygridlines():
            if _e_uma(linha.get_color(), _GRADES):
                linha.set_color(grade)
        for texto in ax.texts:       # rótulos das fatias, % no fim da barra
            if _e_uma(texto.get_color(), _FRENTES):
                texto.set_color(frente)
        for linha in ax.lines:       # linhas guia da pizza e curva do Pareto
            if _e_uma(linha.get_color(), _GUIAS):
                linha.set_color(tema["guia"])
            elif _e_uma(linha.get_color(), _CURVAS):
                linha.set_color(tema["curva"])

        legenda = ax.get_legend()    # a da barra empilhada
        if legenda is not None:
            for texto in legenda.get_texts():
                if _e_uma(texto.get_color(), _FRENTES):
                    texto.set_color(frente)
    return fig
