"""Núcleo: leitura dos dados e regras de classificação.

É a parte mais importante de entender — a lógica pura, sem nada de
interface gráfica nem de desenho.

Os dados podem entrar por dois caminhos (veja `fontes.py`): os .txt do
XRF, e aí o valor de cada elemento é a ÁREA do pico, ou a planilha do
programa de concentrações, e aí é a CONCENTRAÇÃO. Os dois caminhos
devolvem a mesma coisa — amostras com uma lista de
{"z", "symbol", "valor"} —, então tudo daí pra frente é igual.
"""

from .tabela_periodica import PERIODIC_TABLE
from .leitura import parse_xrf_file, parse_mapping
from .planilha import parse_planilha
from .fontes import (
    AREAS,
    CONCENTRACOES,
    FONTES,
    FONTE_PADRAO,
    rotulo_da_coluna,
)
from .classificacao import (
    ALWAYS_EXCLUDED_Z,
    TUBE_OPTIONS,
    apply_exclusions,
    classify,
)

__all__ = [
    "PERIODIC_TABLE",
    "parse_xrf_file",
    "parse_mapping",
    "parse_planilha",
    "AREAS",
    "CONCENTRACOES",
    "FONTES",
    "FONTE_PADRAO",
    "rotulo_da_coluna",
    "ALWAYS_EXCLUDED_Z",
    "TUBE_OPTIONS",
    "apply_exclusions",
    "classify",
]
