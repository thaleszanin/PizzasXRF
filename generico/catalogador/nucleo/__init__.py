"""Núcleo: leitura dos dados e regras de classificação.

É a parte mais importante de entender — a lógica pura, sem nada de
interface gráfica nem de desenho.
"""

from .tabela_periodica import PERIODIC_TABLE
from .leitura import parse_frx_file, parse_mapping
from .classificacao import (
    ALWAYS_EXCLUDED_Z,
    TUBE_OPTIONS,
    apply_exclusions,
    classify,
)

__all__ = [
    "PERIODIC_TABLE",
    "parse_frx_file",
    "parse_mapping",
    "ALWAYS_EXCLUDED_Z",
    "TUBE_OPTIONS",
    "apply_exclusions",
    "classify",
]
