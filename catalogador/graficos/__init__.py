"""Camada de desenho (matplotlib), sem nada de Tkinter."""

from .estilo import PALETTE, TRACE_LUMP_COLOR, LABEL_FONTSIZE
from .cores import ELEMENT_COLORS, color_for, colors_for
from .pizza import draw_pie_with_leaders, passos_da_pizza
from .figura import (build_sample_figure, draw_sample_figure,
                     passos_da_rasterizacao, passos_do_desenho)

__all__ = [
    "PALETTE",
    "TRACE_LUMP_COLOR",
    "LABEL_FONTSIZE",
    "ELEMENT_COLORS",
    "color_for",
    "colors_for",
    "draw_pie_with_leaders",
    "passos_da_pizza",
    "build_sample_figure",
    "draw_sample_figure",
    "passos_do_desenho",
    "passos_da_rasterizacao",
]
