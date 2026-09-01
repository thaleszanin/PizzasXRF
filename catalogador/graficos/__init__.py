"""Camada de desenho (matplotlib), sem nada de Tkinter."""

from .estilo import PALETTE, TRACE_LUMP_COLOR, LABEL_FONTSIZE
from .cores import ELEMENT_COLORS, color_for, colors_for
from .pizza import draw_pie_with_leaders
from .figura import build_sample_figure

__all__ = [
    "PALETTE",
    "TRACE_LUMP_COLOR",
    "LABEL_FONTSIZE",
    "ELEMENT_COLORS",
    "color_for",
    "colors_for",
    "draw_pie_with_leaders",
    "build_sample_figure",
]
