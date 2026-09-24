"""Leitura dos arquivos de entrada.

Duas fontes:
  - o .txt de saída do XRF (formato WinQXAS);
  - o .csv/.txt de mapeamento "código do arquivo -> nome real da amostra".

Nada aqui sabe da interface gráfica.
"""

import os

from .tabela_periodica import PERIODIC_TABLE


def parse_xrf_file(path):
    """Lê um .txt do XRF e devolve uma lista de dicionários, um por
    elemento (Z), já com as áreas de linhas repetidas somadas.

    Cada item: {"z": int, "symbol": str, "valor": float, "energia": float}
    — aqui o valor é a ÁREA do pico. A planilha de concentrações
    (nucleo/planilha.py) devolve a mesma forma, com a concentração no
    lugar (e sem energia). A "energia" (keV) é a da linha mais forte
    do elemento: é onde o pico dele fica no espectro, e é com ela que
    o espectro do .mca ganha o nome de cada pico. As "linhas" guardam
    cada pico separado, [(energia, área), ...] — é o que permite dizer
    quanto do elemento veio da linha K e quanto da L (nucleo/razao_tubo.py).
    """
    with open(path, encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()

    # 1. Acha a linha "Photopeaks:, N" — os dados começam depois dela
    header_index = None
    for i, line in enumerate(lines):
        if "photopeaks" in line.lower():
            header_index = i
            break
    if header_index is None:
        raise ValueError(f'Não encontrei "Photopeaks" em {os.path.basename(path)}')

    data_lines = [l for l in lines[header_index + 1:] if l.strip()]

    # 2. Soma áreas de linhas com o mesmo Z (ex: linhas Kα e Lα do mesmo
    #    elemento aparecendo em linhas separadas)
    by_z = {}
    for line in data_lines:
        parts = [p.strip() for p in line.split(",") if p.strip()]
        if len(parts) < 5:
            continue
        try:
            z = int(float(parts[0]))
            energia = float(parts[1])
            valor = float(parts[2])
        except ValueError:
            continue  # linha não numérica, ignora

        if z in by_z:
            by_z[z]["valor"] += valor
            by_z[z]["linhas"].append((energia, valor))
            if valor > by_z[z]["_maior"]:
                by_z[z]["_maior"], by_z[z]["energia"] = valor, energia
        else:
            by_z[z] = {"z": z, "symbol": PERIODIC_TABLE.get(z, f"Z{z}"),
                       "valor": valor, "energia": energia, "_maior": valor,
                       "linhas": [(energia, valor)]}

    for e in by_z.values():
        del e["_maior"]
    return list(by_z.values())


def parse_mapping(path):
    """Lê um .csv/.txt de mapeamento "código,nome real" (aceita vírgula,
    ponto-e-vírgula ou tab como separador) e devolve um dicionário
    {código_minúsculo: nome real}."""
    mapping = {}
    with open(path, encoding="utf-8", errors="ignore") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line:
                continue
            parts = [p.strip() for p in line.replace(";", ",").replace("\t", ",").split(",")]
            if len(parts) < 2:
                continue
            code = parts[0].lower()
            name = ",".join(parts[1:]).strip()
            if code in ("codigo", "código", "code"):
                continue  # linha de cabeçalho, pula
            if code and name:
                mapping[code] = name
    return mapping
