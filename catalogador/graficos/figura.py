"""Monta a figura completa de uma amostra: os três gráficos lado a lado.

Os três painéis são sempre os mesmos — Total, Majoritários (com o traço
agrupado numa fatia só) e Traço renormalizado a 100% —, e o TIPO de
gráfico usado neles é escolhido de fora: pizza, rosca, barras, barra
empilhada ou Pareto. Quem tem a lista é `graficos/tipos.py`.
"""

from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure

from .estilo import TRACE_LUMP_COLOR
from .cores import colors_for
from .tipos import TIPO_PADRAO, desenhador


FIG_SIZE = (14, 4.4)
# Pontos por polegada da figura. Fixo (em vez de herdar o padrão do
# matplotlib) porque o tamanho em PIXELS entra na conta: é o espaço que o
# cartão reserva na tela e o tamanho de cada faixa da imagem compilada.
FIG_DPI = 100
# Quantas vezes, no máximo, o eixo comum das três pizzas é recalculado.
RODADAS_DE_AJUSTE = 3
# Crescimento (em unidades de dado) abaixo do qual o eixo já é "o mesmo".
TOLERANCIA = 0.005


def build_sample_figure(elements, major, trace, total, title, tipo=TIPO_PADRAO):
    """Devolve uma figura matplotlib NOVA com os três gráficos da
    amostra: total, majoritários (com o grupo "Traço" agrupado) e traço
    renormalizado a 100%. `tipo` é um dos nomes de `graficos/tipos.py`."""
    # `Figure` direto em vez de `plt.subplots`: o pyplot guardaria a
    # figura numa lista global (vazando memória a cada redesenho) e, com
    # o backend TkAgg, ainda criaria uma janela Tk escondida por figura.
    # O canvas Agg aqui é só pra medir texto; a interface troca por um
    # FigureCanvasTkAgg depois.
    fig = Figure(figsize=FIG_SIZE, dpi=FIG_DPI)
    FigureCanvasAgg(fig)
    return draw_sample_figure(fig, elements, major, trace, total, title, tipo)


def draw_sample_figure(fig, elements, major, trace, total, title, tipo=TIPO_PADRAO):
    """Igual ao `build_sample_figure`, mas desenha numa figura que já
    existe (limpando o que havia nela) em vez de criar outra.

    É o que a interface usa: reaproveitar a mesma `Figure` deixa o
    widget Tk do cartão de pé — recriar o canvas a cada mudança de
    slider custava muito mais caro que o desenho em si.
    """
    for _ in passos_do_desenho(fig, elements, major, trace, total, title, tipo):
        pass
    return fig


def paineis(elements, major, trace, total):
    """Os três painéis de uma amostra, cada um como
    (título, valores em %, rótulos, cores).

    É a única parte que sabe o que os três gráficos SIGNIFICAM; o tipo
    de gráfico escolhido só recebe listas de números.
    """
    todos = sorted(elements, key=lambda e: -e["valor"])
    total_painel = ("Total",
                    [e["valor"] / total * 100 for e in todos],
                    [e["symbol"] for e in todos],
                    colors_for(todos))

    # os majoritários um a um, mais UMA fatia com todo o traço somado
    sizes = [e["valor"] / total * 100 for e in major]
    labels = [e["symbol"] for e in major]
    colors = colors_for(major)
    if trace:
        sizes.append(sum(e["valor"] for e in trace) / total * 100)
        labels.append("Traço")
        colors.append(TRACE_LUMP_COLOR)
    maiores = ("Majoritários", sizes, labels, colors)

    # o traço sozinho, renormalizado: aqui 100% é o traço inteiro, senão
    # todas as fatias seriam finas demais pra enxergar
    if trace:
        soma = sum(e["valor"] for e in trace)
        tracos = ("Traço",
                  [e["valor"] / soma * 100 for e in trace],
                  [e["symbol"] for e in trace],
                  colors_for(trace))
    else:
        tracos = ("Traço", [], [], [])

    return [total_painel, maiores, tracos]


def passos_do_desenho(fig, elements, major, trace, total, title, tipo=TIPO_PADRAO):
    """O MESMO desenho, só que em pedaços: um `yield` entre uma etapa e
    outra.

    A figura inteira leva uns 100 ms pra ficar pronta, e 100 ms de
    janela parada se sente na hora de rolar a lista. Fatiada, cada
    pedaço custa uns 25 ms e a interface respira entre um e outro —
    quem cuida disso é a fila de desenho em `interface/app.py`.
    """
    fig.clear()
    axes = fig.subplots(1, 3)
    fig.suptitle(title, fontsize=10)
    desenha = desenhador(tipo)
    yield

    rotulos = []
    for ax, (titulo, sizes, labels, colors) in zip(axes, paineis(elements, major, trace, total)):
        if sizes:
            rotulos.append((yield from desenha(ax, sizes, labels, colors)))
        else:
            # painel sem nada (amostra sem traço): sem eixo nem grade,
            # senão sobra uma caixa vazia com números de 0 a 1 dentro
            ax.set_axis_off()
        ax.set_title(titulo, fontsize=9)
        yield

    fig.tight_layout(w_pad=2.0)
    yield

    # só os tipos redondos devolvem rótulos pra igualar; os de barra
    # devolvem None, e aí não há tamanho comum a acertar
    yield from _igualar_pizzas([r for r in rotulos if r is not None])


def passos_da_rasterizacao(fig):
    """Transforma a figura em pixels, também em pedaços: primeiro o
    fundo, depois um gráfico por vez.

    É exatamente o que o `canvas.draw()` faz de uma vez (conferido pixel
    a pixel), só que dividido — o desenho de uma figura inteira leva uns
    55 ms, e cada eixo, uns 20.
    """
    renderer = fig.canvas.get_renderer()
    renderer.clear()
    # o fundo vem SEMPRE primeiro; ordenar tudo junto por zorder pintaria
    # o branco por cima dos gráficos
    fig.patch.draw(renderer)
    artistas = sorted((a for a in fig.get_children() if a is not fig.patch),
                      key=lambda a: a.get_zorder())
    for artista in artistas:
        if artista.get_visible():
            artista.draw(renderer)
            yield


def _uniao(limites):
    """O menor eixo que contém todos os eixos recebidos."""
    return (min(l[0] for l in limites), max(l[1] for l in limites),
            min(l[2] for l in limites), max(l[3] for l in limites))


def _igualar_pizzas(rotulos):
    """Deixa as três pizzas exatamente do mesmo tamanho. (Gerador: dá um
    `yield` a cada rodada, veja `passos_do_desenho`.)

    Sozinha, cada pizza se acomoda no menor eixo em que os rótulos dela
    cabem. Como o gráfico "Total" costuma ter bem mais rótulos que os
    outros dois, ele pedia um eixo maior — e, com o mesmo espaço na
    figura pra um eixo maior, a pizza dele saía menor (nos testes, até
    30% menor que a do lado).

    A correção é dar às três o MESMO eixo: o maior que qualquer uma
    delas pediu. Mesmos limites e mesma caixa levam ao mesmo raio.

    Só que trocar o eixo obriga a refazer o posicionamento dos rótulos:
    eles são colocados em pixels, e num eixo maior a pizza encolhe
    enquanto o texto (de tamanho fixo, em pontos) continua igual —
    posições calculadas no eixo antigo se sobreporiam no novo. E, pelo
    mesmo motivo, o texto passa a ocupar mais espaço de dados e pode
    pedir um pouco mais de margem, então repetimos enquanto o eixo comum
    crescer. Cada rodada cresce uma fração da anterior, então duas ou
    três já estabilizam.
    """
    if len(rotulos) < 2:
        return

    comum = _uniao([tuple(r.ax.get_xlim()) + tuple(r.ax.get_ylim()) for r in rotulos])
    for _ in range(RODADAS_DE_AJUSTE):
        pedidos = []
        for rotulo in rotulos:
            pedidos.append(rotulo.posicionar(comum))
            yield          # um eixo por vez: cada um custa uns 7 ms
        novo = _uniao(pedidos + [comum])
        if all(abs(n - c) <= TOLERANCIA for n, c in zip(novo, comum)):
            break
        comum = novo
