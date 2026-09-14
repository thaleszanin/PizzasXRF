# -*- coding: utf-8 -*-
"""O banco de amostras: o arquivo .db e tudo o que entra e sai dele.

  esquema.py          as tabelas (amostras, categorias, medições, leituras)
  repositorio.py      abre o arquivo e faz as operações — sem janela
  planilha.py         lê a planilha de informações (categorias por coluna)
  importacao.py       lê de volta os .txt/.png que o programa exporta
  exportacao_json.py  o banco inteiro como .json + pasta de imagens

A dependência continua num sentido só: interface -> banco -> nucleo.
"""

from .esquema import DESCARTADO, MAJORITARIO, TRACO, VERSAO
from .repositorio import (BancoDeAmostras, ErroDoBanco, ORDEM_DOS_TUBOS,
                          bancos_lembrados, lembrar_bancos,
                          leituras_classificadas, normalizar_nome,
                          ordem_do_tubo, simbolo_do_tubo)
from .planilha import coluna_sugerida, ler_planilha, separar_chave
from .importacao import imagem_ao_lado, ler_tabela_exportada
from .exportacao_json import exportar_json, montar_entradas

__all__ = [
    "DESCARTADO", "MAJORITARIO", "TRACO", "VERSAO",
    "BancoDeAmostras", "ErroDoBanco", "ORDEM_DOS_TUBOS",
    "bancos_lembrados", "lembrar_bancos", "leituras_classificadas",
    "normalizar_nome", "ordem_do_tubo", "simbolo_do_tubo",
    "coluna_sugerida", "ler_planilha", "separar_chave",
    "imagem_ao_lado", "ler_tabela_exportada",
    "exportar_json", "montar_entradas",
]
