# -*- coding: utf-8 -*-
"""Banco central das amostras: as pastas editáveis e as medidas nelas.

Camada de dados pura (SQLite pelo módulo `sqlite3` da biblioteca padrão),
sem nada de Tkinter e sem nada de matplotlib — a janela do banco fica em
`catalogador/interface/banco_view.py`.
"""

from .esquema import ARVORE_INICIAL, RAIZ_ID, RAIZ_NOME, VERSAO
from .repositorio import (BancoDeAmostras, ErroDoBanco, caminho_lembrado,
                          caminho_padrao, impressao_da_medida, lembrar_caminho,
                          pasta_base)

__all__ = [
    "ARVORE_INICIAL",
    "BancoDeAmostras",
    "ErroDoBanco",
    "RAIZ_ID",
    "RAIZ_NOME",
    "VERSAO",
    "caminho_lembrado",
    "caminho_padrao",
    "impressao_da_medida",
    "lembrar_caminho",
    "pasta_base",
]
