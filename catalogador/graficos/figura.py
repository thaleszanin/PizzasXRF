"""Monta a figura completa de uma amostra: as três pizzas lado a lado."""

import matplotlib.pyplot as plt

from .estilo import TRACE_LUMP_COLOR
from .cores import colors_for
from .pizza import draw_pie_with_leaders


def build_sample_figure(elements, major, trace, total, title):
    """Devolve a figura matplotlib com os três gráficos da amostra:
    total, majoritários (com a fatia "Traço" agrupada) e traço
    renormalizado a 100%."""
    fig, axes = plt.subplots(1, 3, figsize=(14, 4.4))
    fig.suptitle(title, fontsize=10)

    # ---- gráfico 1: TOTAL (todos os elementos, sem distinção de grupo) ----
    all_sorted = sorted(elements, key=lambda e: -e["area"])
    labels = [e["symbol"] for e in all_sorted]
    sizes = [e["area"] / total * 100 for e in all_sorted]
    colors = colors_for(all_sorted)
    draw_pie_with_leaders(axes[0], sizes, labels, colors)
    axes[0].set_title("Total", fontsize=9)

    # ---- gráfico 2: MAJORITÁRIOS (individuais + fatia "traço" agrupada) ----
    labels = [e["symbol"] for e in major]
    sizes = [e["area"] / total * 100 for e in major]
    colors = colors_for(major)
    if trace:
        trace_sum = sum(e["area"] for e in trace)
        labels.append("Traço")
        sizes.append(trace_sum / total * 100)
        colors.append(TRACE_LUMP_COLOR)
    draw_pie_with_leaders(axes[1], sizes, labels, colors)
    axes[1].set_title("Majoritários", fontsize=9)

    # ---- gráfico 3: TRAÇO renormalizado a 100% ----
    if trace:
        trace_total = sum(e["area"] for e in trace)
        t_labels = [e["symbol"] for e in trace]
        t_sizes = [e["area"] / trace_total * 100 for e in trace]
        t_colors = colors_for(trace)
        draw_pie_with_leaders(axes[2], t_sizes, t_labels, t_colors)
    axes[2].set_title("Traço", fontsize=9)

    fig.tight_layout(w_pad=2.0)
    return fig
