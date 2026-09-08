# -*- coding: utf-8 -*-
"""Núcleo da pré-análise: ler o arquivo, medir o erro, escrever o log.

A lógica pura — nenhuma janela, nenhuma planilha. Dá pra rodar a
pré-análise inteira de dentro de um script:

    from preanalise.nucleo import avaliar, ler_espectro, log_da_amostra

    elementos = ler_espectro("081025af.txt")
    resultado = avaliar(elementos, limite=50.0)
    print(log_da_amostra("Madeira 123", resultado, 50.0))

O caminho é sempre o mesmo: `leitura.py` transforma o .txt numa lista de
elementos com área e erro, `avaliacao.py` diz quais deles passaram do
limite, e `relatorio.py` põe isso em português.
"""

from .leitura import codigo_do_arquivo, ler_espectro
from .avaliacao import (
    LIMITE_MAXIMO,
    LIMITE_MINIMO,
    LIMITE_PADRAO,
    SEM_AREA,
    avaliar,
    erro_percentual,
    formatar_pct,
)
from .relatorio import (
    linhas_do_resumo,
    log_da_amostra,
    plural,
    resumo_da_amostra,
    texto_do_resumo,
)

__all__ = [
    "codigo_do_arquivo",
    "ler_espectro",
    "LIMITE_MAXIMO",
    "LIMITE_MINIMO",
    "LIMITE_PADRAO",
    "SEM_AREA",
    "avaliar",
    "erro_percentual",
    "formatar_pct",
    "linhas_do_resumo",
    "log_da_amostra",
    "plural",
    "resumo_da_amostra",
    "texto_do_resumo",
]
