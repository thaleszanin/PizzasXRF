"""Corretor de resultados de FRX medidos por 3 tubos de raios X (Ag, Au, Rh)."""

from .nucleo import (
    abrir_resultados,
    aplicar_mapeamento,
    processar_por_tubo,
    salvar_tabela,
)

__all__ = [
    "abrir_resultados",
    "aplicar_mapeamento",
    "processar_por_tubo",
    "salvar_tabela",
]
