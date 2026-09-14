"""Camada de desenho (matplotlib), sem nada de Tkinter."""

from .estilo import (COR_DA_CURVA, COR_DA_GRADE, LABEL_FONTSIZE, PALETTE,
                     TRACE_LUMP_COLOR, formatar_pct)
from .cores import ELEMENT_COLORS, color_for, colors_for
from .pizza import passos_da_pizza
from .barras import (passos_da_barra_empilhada, passos_das_barras,
                     passos_do_pareto)
from .tipos import TIPO_PADRAO, TIPOS, desenhador
from .tema import pintar
from .figura import (build_sample_figure, draw_sample_figure, paineis,
                     passos_da_rasterizacao, passos_do_desenho)

__all__ = [
    "PALETTE",
    "TRACE_LUMP_COLOR",
    "COR_DA_GRADE",
    "COR_DA_CURVA",
    "LABEL_FONTSIZE",
    "formatar_pct",
    "ELEMENT_COLORS",
    "color_for",
    "colors_for",
    "passos_da_pizza",
    "passos_das_barras",
    "passos_da_barra_empilhada",
    "passos_do_pareto",
    "TIPOS",
    "TIPO_PADRAO",
    "desenhador",
    "pintar",
    "paineis",
    "build_sample_figure",
    "draw_sample_figure",
    "passos_do_desenho",
    "passos_da_rasterizacao",
]
