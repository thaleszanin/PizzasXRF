# -*- coding: utf-8 -*-
"""Leitura dos .txt do XRF — agora com a coluna do erro.

O catalogador lê esses mesmos arquivos, mas só precisa da área do pico e
joga fora o resto da linha. A pré-análise vive justamente da coluna que
ele descarta: o erro do ajuste, na mesma unidade da área.

O formato é o do WinQXAS — um cabeçalho, a linha "Photopeaks:, N" e daí
pra baixo uma linha por pico ajustado:

    Photopeaks:, 12
    19, 3.31, 128450.0, 1180.5, 1.04      <- Z, energia, área, erro, chi²
    20, 3.69,  84210.0,  920.0, 1.02
    26, 6.40,  15234.5, 8210.3, 1.31      <- 54% de erro: elemento suspeito

Linhas do mesmo elemento (a Kα e a Lα, por exemplo) chegam separadas e
são juntadas numa só, como no catalogador: as áreas somam, e os erros
somam em quadratura — sqrt(e1² + e2²) —, que é como se combina a
incerteza de duas medidas independentes. Somar os erros direto inflaria
o erro do elemento e faria a pré-análise acusar problema onde não tem.

Nada aqui sabe da interface gráfica nem do Excel.
"""

import math
import os

from catalogador.nucleo.tabela_periodica import PERIODIC_TABLE

# Quantos campos a linha de um pico precisa ter pra ser lida: Z, energia,
# área, erro e chi². É o mesmo corte que o catalogador faz.
CAMPOS_DO_PICO = 5


def ler_espectro(caminho):
    """Lê um .txt do XRF e devolve uma lista de dicionários, um por
    elemento (Z), com as linhas repetidas já juntadas.

    Cada item:

        {"z": int, "symbol": str, "area": float, "erro": float,
         "linhas": int}

    `linhas` é quantos picos daquele elemento entraram na conta — 1 na
    maioria das vezes, 2 quando o elemento apareceu com duas linhas de
    emissão. O erro relativo não é calculado aqui: quem faz isso é
    `avaliacao.py`, porque depende do limite escolhido na janela.
    """
    with open(caminho, encoding="utf-8", errors="ignore") as f:
        linhas = f.readlines()

    inicio = None
    for i, linha in enumerate(linhas):
        if "photopeaks" in linha.lower():
            inicio = i
            break
    if inicio is None:
        raise ValueError('Não encontrei "Photopeaks" em %s'
                         % os.path.basename(caminho))

    por_z = {}
    for linha in linhas[inicio + 1:]:
        if not linha.strip():
            continue
        partes = [p.strip() for p in linha.split(",") if p.strip()]
        if len(partes) < CAMPOS_DO_PICO:
            continue
        try:
            z = int(float(partes[0]))
            area = float(partes[2])
            erro = abs(float(partes[3]))
        except ValueError:
            continue  # linha de texto no meio dos números, ignora

        elemento = por_z.get(z)
        if elemento is None:
            por_z[z] = {"z": z, "symbol": PERIODIC_TABLE.get(z, "Z%d" % z),
                        "area": area, "erro": erro, "linhas": 1}
        else:
            elemento["area"] += area
            # erros independentes se somam em quadratura, não direto
            elemento["erro"] = math.hypot(elemento["erro"], erro)
            elemento["linhas"] += 1

    if not por_z:
        raise ValueError('Nenhum pico depois de "Photopeaks" em %s'
                         % os.path.basename(caminho))

    return list(por_z.values())


def codigo_do_arquivo(caminho):
    """O nome do arquivo sem a extensão — é o código que o arquivo de
    mapeamento traduz para o nome real da amostra."""
    return os.path.splitext(os.path.basename(caminho))[0]
