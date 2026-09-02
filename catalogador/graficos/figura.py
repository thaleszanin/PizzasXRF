"""Monta a figura completa de uma amostra: as três pizzas lado a lado."""

from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure

from .estilo import TRACE_LUMP_COLOR
from .cores import colors_for
from .pizza import passos_da_pizza


FIG_SIZE = (14, 4.4)
# Pontos por polegada da figura. Fixo (em vez de herdar o padrão do
# matplotlib) porque o tamanho em PIXELS entra na conta: é o espaço que o
# cartão reserva na tela e o tamanho de cada faixa da imagem compilada.
FIG_DPI = 100
# Quantas vezes, no máximo, o eixo comum das três pizzas é recalculado.
RODADAS_DE_AJUSTE = 3
# Crescimento (em unidades de dado) abaixo do qual o eixo já é "o mesmo".
TOLERANCIA = 0.005


def build_sample_figure(elements, major, trace, total, title):
    """Devolve uma figura matplotlib NOVA com os três gráficos da
    amostra: total, majoritários (com a fatia "Traço" agrupada) e traço
    renormalizado a 100%."""
    # `Figure` direto em vez de `plt.subplots`: o pyplot guardaria a
    # figura numa lista global (vazando memória a cada redesenho) e, com
    # o backend TkAgg, ainda criaria uma janela Tk escondida por figura.
    # O canvas Agg aqui é só pra medir texto; a interface troca por um
    # FigureCanvasTkAgg depois.
    fig = Figure(figsize=FIG_SIZE, dpi=FIG_DPI)
    FigureCanvasAgg(fig)
    return draw_sample_figure(fig, elements, major, trace, total, title)


def draw_sample_figure(fig, elements, major, trace, total, title):
    """Igual ao `build_sample_figure`, mas desenha numa figura que já
    existe (limpando o que havia nela) em vez de criar outra.

    É o que a interface usa: reaproveitar a mesma `Figure` deixa o
    widget Tk do cartão de pé — recriar o canvas a cada mudança de
    slider custava muito mais caro que o desenho em si.
    """
    for _ in passos_do_desenho(fig, elements, major, trace, total, title):
        pass
    return fig


def passos_do_desenho(fig, elements, major, trace, total, title):
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
    yield

    # ---- gráfico 1: TOTAL (todos os elementos, sem distinção de grupo) ----
    all_sorted = sorted(elements, key=lambda e: -e["area"])
    labels = [e["symbol"] for e in all_sorted]
    sizes = [e["area"] / total * 100 for e in all_sorted]
    colors = colors_for(all_sorted)
    rotulos = [(yield from passos_da_pizza(axes[0], sizes, labels, colors))]
    axes[0].set_title("Total", fontsize=9)
    yield

    # ---- gráfico 2: MAJORITÁRIOS (individuais + fatia "traço" agrupada) ----
    labels = [e["symbol"] for e in major]
    sizes = [e["area"] / total * 100 for e in major]
    colors = colors_for(major)
    if trace:
        trace_sum = sum(e["area"] for e in trace)
        labels.append("Traço")
        sizes.append(trace_sum / total * 100)
        colors.append(TRACE_LUMP_COLOR)
    rotulos.append((yield from passos_da_pizza(axes[1], sizes, labels, colors)))
    axes[1].set_title("Majoritários", fontsize=9)
    yield

    # ---- gráfico 3: TRAÇO renormalizado a 100% ----
    if trace:
        trace_total = sum(e["area"] for e in trace)
        t_labels = [e["symbol"] for e in trace]
        t_sizes = [e["area"] / trace_total * 100 for e in trace]
        t_colors = colors_for(trace)
        rotulos.append((yield from passos_da_pizza(axes[2], t_sizes, t_labels, t_colors)))
    axes[2].set_title("Traço", fontsize=9)

    yield

    fig.tight_layout(w_pad=2.0)
    yield

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
