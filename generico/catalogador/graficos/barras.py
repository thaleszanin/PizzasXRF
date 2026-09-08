# -*- coding: utf-8 -*-
"""Os gráficos de barra: barras, barra empilhada e Pareto.

Todos recebem exatamente o mesmo que a pizza — um `ax` pronto e três
listas paralelas (valores em %, rótulos e cores) — e são desenhados em
pedaços, com `yield` entre uma etapa e outra, pela mesma razão que a
pizza: a interface precisa respirar entre um pedaço e outro (veja
`passos_do_desenho` em `graficos/figura.py`).

Diferença de peso: a pizza gasta quase todo o tempo dela RESOLVENDO a
posição dos rótulos (medida em pixels, com sobreposição a evitar).
Aqui os rótulos moram cada um na sua linha (ou na legenda), então não
há nada a resolver — estes gráficos saem em uma fração do tempo.

Quem escolhe qual desenhar é `graficos/tipos.py`.
"""

from matplotlib.patches import Patch
from matplotlib.ticker import PercentFormatter

from .estilo import COR_DA_CURVA, COR_DA_GRADE, LABEL_FONTSIZE, formatar_pct

# Folga à direita da barra mais comprida, pra caber o texto da % no fim
# dela (fração do maior valor).
FOLGA_DO_ROTULO = 0.18
# Espessura da barra, em fração do espaço de uma linha.
ESPESSURA = 0.72
# Largura da barra única do gráfico empilhado, em unidades do eixo.
LARGURA_EMPILHADA = 0.55
# A partir de que fatia (%) o nome do elemento cabe DENTRO do bloco, na
# barra empilhada. Abaixo disso o texto ficaria maior que o bloco.
FATIA_COM_TEXTO_DENTRO = 7.0
# A partir de quantos itens a legenda da barra empilhada vira duas
# colunas, pra não passar da altura do gráfico.
LEGENDA_EM_DUAS_COLUNAS = 16
# Com mais elementos que isso, os nomes no eixo x do Pareto ficam em pé.
PARETO_NOMES_EM_PE = 22


def _decrescente(sizes, labels, colors):
    """Os mesmos dados, do maior valor pro menor.

    A pizza pode se dar ao luxo de manter a ordem do arquivo (a fatia
    fala por si), mas uma barra fora de ordem é ilegível.
    """
    trios = sorted(zip(sizes, labels, colors), key=lambda t: -t[0])
    return [list(coluna) for coluna in zip(*trios)]


def _limpar_moldura(ax, eixo_da_grade):
    """Tira a caixa em volta do gráfico e põe uma grade discreta atrás
    das barras, só no eixo dos valores."""
    for lado in ("top", "right"):
        ax.spines[lado].set_visible(False)
    ax.grid(axis=eixo_da_grade, color=COR_DA_GRADE, linewidth=0.6)
    ax.set_axisbelow(True)
    ax.tick_params(labelsize=LABEL_FONTSIZE - 1, length=0)


def passos_das_barras(ax, sizes, labels, colors):
    """Barras deitadas, a maior em cima, com a % no fim de cada uma.

    É a leitura mais direta quando a amostra tem muitos elementos: numa
    pizza com 20 fatias, as menores viram riscos e os rótulos brigam
    por espaço; aqui cada elemento tem a sua linha.
    """
    sizes, labels, colors = _decrescente(sizes, labels, colors)
    posicoes = list(range(len(sizes)))
    ax.barh(posicoes, sizes, height=ESPESSURA, color=colors,
            edgecolor="white", linewidth=0.6)
    ax.set_yticks(posicoes)
    ax.set_yticklabels(labels, fontsize=LABEL_FONTSIZE)
    ax.set_ylim(len(sizes) - 0.5, -0.5)   # a maior em cima
    yield

    maior = max(sizes)
    for y, valor in zip(posicoes, sizes):
        ax.text(valor + maior * 0.02, y, formatar_pct(valor),
                va="center", ha="left", fontsize=LABEL_FONTSIZE)
    ax.set_xlim(0, maior * (1.0 + FOLGA_DO_ROTULO))
    ax.xaxis.set_major_formatter(PercentFormatter(xmax=100, decimals=0))
    ax.spines["left"].set_visible(False)
    _limpar_moldura(ax, "x")
    return None


def passos_da_barra_empilhada(ax, sizes, labels, colors):
    """Uma barra só, de 0 a 100%, com um bloco por elemento.

    Serve pra ver a composição como um todo — a mesma informação da
    pizza, mas comparável de bater o olho entre uma amostra e outra
    (duas barras lado a lado se comparam na altura; duas pizzas, não).
    """
    sizes, labels, colors = _decrescente(sizes, labels, colors)
    base = 0.0
    for valor, cor in zip(sizes, colors):
        ax.bar(0, valor, bottom=base, width=LARGURA_EMPILHADA, color=cor,
               edgecolor="white", linewidth=0.6)
        base += valor
    yield

    # o nome vai DENTRO do bloco só quando o bloco é alto o bastante;
    # todo mundo aparece na legenda, então nada se perde
    altura = 0.0
    for valor, label in zip(sizes, labels):
        if valor >= FATIA_COM_TEXTO_DENTRO:
            ax.text(0, altura + valor / 2.0, "%s  %s" % (label, formatar_pct(valor)),
                    ha="center", va="center", fontsize=LABEL_FONTSIZE,
                    color="white")
        altura += valor

    # o eixo é bem mais largo que a barra: a metade da direita é o
    # espaço da legenda, que sem isso ficaria por cima dos blocos
    ax.set_xlim(-0.45, 1.15)
    ax.set_ylim(0, max(100.0, base))
    ax.set_xticks([])
    ax.yaxis.set_major_formatter(PercentFormatter(xmax=100, decimals=0))
    # quadradinhos lisos, sem a borda branca que separa um bloco do
    # outro na barra: nesse tamanho ela comeria o quadrado inteiro
    ax.legend(handles=[Patch(facecolor=cor, label="%s  %s" % (label, formatar_pct(valor)))
                       for valor, label, cor in zip(sizes, labels, colors)],
              loc="center left", bbox_to_anchor=(0.52, 0.5), frameon=False,
              fontsize=LABEL_FONTSIZE, handlelength=1.1, handleheight=1.1,
              labelspacing=0.4, borderaxespad=0.0,
              ncol=2 if len(sizes) > LEGENDA_EM_DUAS_COLUNAS else 1)
    for lado in ("top", "right", "bottom"):
        ax.spines[lado].set_visible(False)
    ax.grid(axis="y", color=COR_DA_GRADE, linewidth=0.6)
    ax.set_axisbelow(True)
    ax.tick_params(labelsize=LABEL_FONTSIZE - 1, length=0)
    return None


def passos_do_pareto(ax, sizes, labels, colors):
    """Barras em pé, da maior pra menor, mais a curva do acumulado.

    A curva responde "quantos elementos respondem por quase tudo?" — é
    a mesma pergunta que o limite do grupo traço faz, vista do outro
    lado: onde a curva encosta no topo, o resto é traço.
    """
    sizes, labels, colors = _decrescente(sizes, labels, colors)
    posicoes = list(range(len(sizes)))
    ax.bar(posicoes, sizes, width=ESPESSURA, color=colors,
           edgecolor="white", linewidth=0.6)
    ax.set_xticks(posicoes)
    ax.set_xticklabels(labels, fontsize=LABEL_FONTSIZE,
                       rotation=90 if len(sizes) > PARETO_NOMES_EM_PE else 0)
    ax.set_xlim(-0.7, len(sizes) - 0.3)
    ax.set_ylim(0, max(sizes) * 1.08)
    ax.yaxis.set_major_formatter(PercentFormatter(xmax=100, decimals=0))
    _limpar_moldura(ax, "y")
    yield

    total = sum(sizes)
    acumulado, soma = [], 0.0
    for valor in sizes:
        soma += valor
        acumulado.append(soma / total * 100.0)

    # o eixo da direita é dessa curva, e só dela: os dois eixos medem
    # coisas diferentes (a fatia de cada um x o que já foi somado)
    curva = ax.twinx()
    curva.plot(posicoes, acumulado, color=COR_DA_CURVA, linewidth=1.3,
               marker="o", markersize=3.0, zorder=3)
    curva.set_ylim(0, 105)
    curva.yaxis.set_major_formatter(PercentFormatter(xmax=100, decimals=0))
    curva.set_ylabel("acumulado", fontsize=LABEL_FONTSIZE - 1,
                     color=COR_DA_CURVA)
    curva.tick_params(labelsize=LABEL_FONTSIZE - 1, length=0,
                      colors=COR_DA_CURVA)
    for lado in ("top", "left"):
        curva.spines[lado].set_visible(False)
    curva.spines["right"].set_color(COR_DA_CURVA)
    return None
