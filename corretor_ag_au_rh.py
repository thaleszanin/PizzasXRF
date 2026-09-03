"""Corretor de resultados de FRX medidos pelos tubos Ag/Au/Rh — ponto de entrada.

Abre os arquivos de resultado de cada tubo (aba "Resultados"), reconcilia
elemento a elemento pelo fator Au/Ag e Au/Rh e os testes de consistência
(ver `corretor/nucleo.py`), e salva uma tabela corrigida e unificada.

Uso:
    python corretor_ag_au_rh.py
"""

from corretor.interface import main

if __name__ == "__main__":
    main()
