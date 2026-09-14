# -*- coding: utf-8 -*-
"""O desenho de um espectro: contagens por energia, com os picos nomeados.

É o gráfico do .mca — a curva bruta que o detector registrou, em
escala logarítmica (é a única em que o pico de 200 contagens do cromo
aparece ao lado do de 20 000 do cálcio). Os elementos que o ajuste
achou no .txt entram como marcas na energia da linha deles: o nome do
elemento em cima do pico.

    png = png_do_espectro(contagens, energias, "M021 — tubo Ag",
                          marcas=[(3.691, "Ca"), (5.895, "Mn")])

O eixo de energia é fixo, de 0 a LIMITE_KEV, em todos os espectros. O
das contagens tem duas escalas: log (a guardada no banco) e linear (a
tela desenha na hora quando pedem).

Como o resto da camada de desenho: matplotlib e mais nada.
"""

import io

import numpy as np
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure

from .figura import FIG_DPI, PNG_DPI

FIG_SIZE_ESPECTRO = (14, 4)
# O eixo de energia vai sempre de 0 a este valor: acima de 25 keV não
# há linha de interesse nas amostras, e um eixo igual em todos os
# espectros deixa um comparável com o outro.
LIMITE_KEV = 25.0
# As duas escalas do eixo das contagens.
LOG, LINEAR = "log", "linear"
COR_DA_CURVA = "#2C6BD4"
COR_DO_PREENCHIMENTO = "#2C6BD4"
COR_DAS_MARCAS = "#333333"
FONTE_DAS_MARCAS = 8
# Canais a partir do último com contagem que ainda entram no eixo, pra
# curva não terminar colada na borda direita.
FOLGA_DE_CANAIS = 40


def desenhar_espectro(fig, contagens, energias, titulo, marcas=(), calibrado=True,
                      tempo_vivo=None, escala=LOG):
    """Desenha o espectro na figura (limpando o que havia nela).

    `escala` é LOG (o padrão: é a única em que o pico de 200 contagens
    aparece ao lado do de 20 000) ou LINEAR.
    """
    fig.clear()
    ax = fig.add_subplot(1, 1, 1)
    contagens = np.asarray(contagens, dtype=float)
    energias = np.asarray(energias, dtype=float)
    log = escala != LINEAR

    if calibrado:
        # o eixo é sempre 0–25 keV; o que passa disso fica de fora
        fim = int(np.searchsorted(energias, LIMITE_KEV, side="right"))
        x0, x1 = 0.0, LIMITE_KEV
    else:
        # sem calibração o eixo é em canais, até o último com sinal
        com_sinal = np.nonzero(contagens > 0)[0]
        fim = min(len(contagens), (int(com_sinal[-1]) if len(com_sinal) else len(contagens))
                  + FOLGA_DE_CANAIS)
        x0, x1 = energias[0], energias[max(0, fim - 1)]
    fim = max(fim, 2)
    x, y = energias[:fim], contagens[:fim]
    # em escala log o zero não existe: o chão é meia contagem
    chao = 0.5 if log else 0.0
    y_log = np.maximum(y, 0.5) if log else y

    ax.fill_between(x, chao, y_log, color=COR_DO_PREENCHIMENTO, alpha=0.12, linewidth=0)
    ax.plot(x, y_log, color=COR_DA_CURVA, linewidth=0.8)
    if log:
        ax.set_yscale("log")
        ax.set_ylim(0.5, max(2.0, y_log.max()) * 4)   # espaço pros nomes dos picos
    else:
        ax.set_ylim(0, max(1.0, y_log.max()) * 1.12)
    ax.set_xlim(x0, x1)
    ax.set_xlabel("Energia (keV)" if calibrado else "Canal", fontsize=9)
    ax.set_ylabel("Contagens", fontsize=9)
    ax.tick_params(labelsize=8)
    ax.grid(True, which="major", linewidth=0.4, alpha=0.4)
    if log:
        ax.grid(True, which="minor", axis="y", linewidth=0.2, alpha=0.2)
    for lado in ("top", "right"):
        ax.spines[lado].set_visible(False)

    subtitulo = titulo
    if tempo_vivo:
        subtitulo += "   (%.0f s de tempo vivo)" % tempo_vivo
    ax.set_title(subtitulo, fontsize=10)

    # as marcas: o nome do elemento em cima do pico. A altura é a do
    # espectro naquela energia (o máximo numa vizinhança de 3 canais,
    # pra marca não cair no vale se a calibração estiver um fio fora)
    if calibrado and len(x) > 1:
        for energia, rotulo in sorted(marcas):
            if not x0 <= energia <= min(x1, x[-1]):
                continue
            canal = int(np.searchsorted(x, energia))
            vizinhos = y_log[max(0, canal - 3):canal + 4]
            altura = vizinhos.max() if len(vizinhos) else 1.0
            ax.annotate(rotulo, (energia, altura), xytext=(0, 4),
                        textcoords="offset points", ha="center", va="bottom",
                        fontsize=FONTE_DAS_MARCAS, color=COR_DAS_MARCAS)
    fig.tight_layout()
    return fig


def png_do_espectro(contagens, energias, titulo, marcas=(), calibrado=True,
                    tempo_vivo=None, escala=LOG, dpi=PNG_DPI):
    """Os bytes do .png do espectro — o que fica guardado no banco (em
    log) e o que a tela pede na hora (em linear)."""
    fig = Figure(figsize=FIG_SIZE_ESPECTRO, dpi=FIG_DPI)
    FigureCanvasAgg(fig)
    try:
        desenhar_espectro(fig, contagens, energias, titulo, marcas, calibrado, tempo_vivo,
                          escala)
        saida = io.BytesIO()
        fig.savefig(saida, format="png", dpi=dpi)
        return saida.getvalue()
    finally:
        fig.clear()
