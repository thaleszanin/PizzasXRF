# -*- coding: utf-8 -*-
"""Leitura do .mca — o espectro bruto que o detector grava.

É o arquivo do Amptek (formato "PMCA SPECTRUM"): um cabeçalho com os
tempos, os pontos de calibração e depois uma contagem por linha, um
canal por linha:

    <<PMCA SPECTRUM>>
    LIVE_TIME - 96.230000
    REAL_TIME - 100.000000
    START_TIME - 01/04/2009 00:12:37
    <<CALIBRATION>>
    LABEL - Channel
    207 2.957            <- canal 207 = 2,957 keV
    441 6.403
    <<DATA>>
    0
    73
    92                   <- 2048 linhas, uma por canal
    ...
    <<END>>

O .mca tem o MESMO nome que o .txt da mesma medida (061025ab.mca e
061025ab.txt), então o mapeamento que dá nome ao .txt dá nome a ele
também — é assim que o espectro encontra a amostra no banco.

Nada aqui sabe da interface nem do desenho.
"""

import os
import re
import zlib

import numpy as np

_NUMERO = re.compile(r"[-+]?\d+(?:[.,]\d+)?")


def parse_mca_file(path):
    """Lê um .mca e devolve um dicionário:

        contagens   array numpy de inteiros, um por canal
        calibracao  [(canal, keV)], os pontos do cabeçalho (pode ser vazio)
        tempo_vivo  segundos (None se não houver)
        tempo_real  segundos (None se não houver)
        inicio      a data/hora de início, como texto
    """
    with open(path, encoding="latin-1", errors="ignore") as f:
        linhas = f.read().splitlines()

    secao = None
    contagens, calibracao = [], []
    cabecalho = {}
    for bruta in linhas:
        linha = bruta.strip()
        if not linha:
            continue
        if linha.startswith("<<"):
            nome = linha.strip("<>").strip().upper()
            secao = {"PMCA SPECTRUM": "cabecalho", "CALIBRATION": "calibracao",
                     "DATA": "dados"}.get(nome, "outra")
            continue
        if secao == "dados":
            try:
                contagens.append(int(float(linha.split()[0])))
            except (ValueError, IndexError):
                continue
        elif secao == "calibracao":
            partes = linha.replace(",", ".").split()
            if len(partes) >= 2:
                try:
                    calibracao.append((float(partes[0]), float(partes[1])))
                except ValueError:
                    continue   # a linha "LABEL - Channel"
        elif secao == "cabecalho" and " - " in linha:
            chave, valor = linha.split(" - ", 1)
            cabecalho[chave.strip().upper()] = valor.strip()

    if not contagens:
        raise ValueError('Não encontrei a seção "<<DATA>>" com as contagens em %s'
                         % os.path.basename(path))

    def segundos(chave):
        achado = _NUMERO.search(cabecalho.get(chave, ""))
        return float(achado.group().replace(",", ".")) if achado else None

    return {"contagens": np.asarray(contagens, dtype=np.int64),
            "calibracao": calibracao,
            "tempo_vivo": segundos("LIVE_TIME"),
            "tempo_real": segundos("REAL_TIME"),
            "inicio": cabecalho.get("START_TIME", "")}


def energias_por_canal(calibracao, canais):
    """A energia (keV) de cada canal, pela reta ajustada aos pontos de
    calibração. Devolve (energias, calibrado): sem dois pontos não há
    reta, e aí as "energias" são os próprios números dos canais."""
    canais_idx = np.arange(canais, dtype=float)
    pontos = [(c, e) for c, e in calibracao if e > 0]
    if len(pontos) < 2:
        return canais_idx, False
    xs, ys = zip(*pontos)
    b, a = np.polyfit(xs, ys, 1)   # keV = a + b * canal
    return a + b * canais_idx, True


# ---------- como as contagens ficam no banco ----------
#
# 2048 canais de 4 bytes são 8 kB; comprimidos, uns 3 kB. É um blob
# pequeno o bastante pra entrar em toda medição sem pensar.

def empacotar_contagens(contagens):
    return zlib.compress(np.asarray(contagens, dtype="<u4").tobytes(), 6)


def desempacotar_contagens(blob):
    return np.frombuffer(zlib.decompress(blob), dtype="<u4").astype(np.int64)
