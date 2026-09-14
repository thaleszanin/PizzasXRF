# -*- coding: utf-8 -*-
"""Leitura de volta dos arquivos que o próprio programa exporta.

O botão "Salvar tabela (TXT)" e a exportação em lote escrevem, para cada
amostra, um bloco assim (`exportacao.bloco_da_amostra`):

    Amostra: M003
    Arquivo: 061025ab
    Tubo de raios X: Prata — Ag
    Limite do grupo traço: 10.0%
    Descartado: Ar, Ag
    Área total (cps): 128047

     Z  Elemento  Área (cps)  % do total  Grupo
    --  --------  ----------  ----------  -----------
    20  Ca             19158      14.96%  majoritário
    ...

Este módulo lê esse bloco de volta — um por arquivo, ou vários no
arquivo compilado — para que uma batelada já exportada entre no banco
sem precisar reabrir os .txt do XRF. O .png de mesmo nome, quando está
ao lado, entra junto como a imagem da medição.

Os valores da tabela saíram formatados (a área sem casa decimal, a
concentração com as casas que couberam), então uma medição importada
daqui pode diferir na última casa da mesma medição guardada direto da
tela — e por isso as duas seriam contadas como medições diferentes.
Guardar direto da tela é o caminho principal; este é o de recuperação.
"""

import os
import re

from .esquema import MAJORITARIO, TRACO

_CABECALHO_VALOR = re.compile(r"^(.+?)\s*\((.+)\)$")   # "Área (cps)"
_LIMITE = re.compile(r"([\d.,]+)\s*%")


def _campo(linhas, rotulo):
    prefixo = rotulo + ":"
    for linha in linhas:
        if linha.startswith(prefixo):
            return linha[len(prefixo):].strip()
    return ""


def _numero(texto):
    return float(texto.replace(",", "."))


def _bloco(texto):
    """Um bloco de amostra -> dicionário, ou None se não for um bloco."""
    linhas = [l.rstrip() for l in texto.strip().splitlines()]
    nome = _campo(linhas, "Amostra")
    if not nome:
        return None
    codigo = _campo(linhas, "Arquivo")
    tubo = _campo(linhas, "Tubo de raios X") or "Nenhum"
    achado = _LIMITE.search(_campo(linhas, "Limite do grupo traço"))
    limite = _numero(achado.group(1)) if achado else 10.0
    descartados = [d.strip() for d in _campo(linhas, "Descartado").split(",") if d.strip()]

    # a tabela começa no cabeçalho que tem "Elemento" e "Grupo"
    inicio = next((i for i, l in enumerate(linhas)
                   if "Elemento" in l and "Grupo" in l), None)
    if inicio is None:
        return None
    colunas = re.split(r"\s{2,}", linhas[inicio].strip())
    grandeza, unidade = "Área", "cps"
    if len(colunas) >= 3:
        achado = _CABECALHO_VALOR.match(colunas[2])
        if achado:
            grandeza, unidade = achado.group(1).strip(), achado.group(2).strip()

    leituras = []
    for linha in linhas[inicio + 2:]:
        partes = re.split(r"\s{2,}", linha.strip())
        if len(partes) < 5:
            continue
        try:
            z, valor = int(partes[0]), _numero(partes[2])
        except ValueError:
            continue
        grupo = partes[4].strip().lower()
        if grupo.startswith("major"):
            grupo = MAJORITARIO
        elif grupo.startswith("tra"):
            grupo = TRACO
        else:
            continue
        leituras.append((z, valor, grupo))
    if not leituras:
        return None

    return {"nome": nome, "codigo": codigo, "tubo": tubo, "limite": limite,
            "descartados": descartados, "grandeza": grandeza, "unidade": unidade,
            "leituras": leituras, "tabela": "\n".join(linhas) + "\n"}


def ler_tabela_exportada(caminho):
    """Todos os blocos de amostra de um .txt exportado — um só, no
    arquivo de uma amostra; vários, no compilado."""
    with open(caminho, encoding="utf-8-sig", errors="ignore") as f:
        texto = f.read()
    # o compilado separa as amostras com uma linha de "="
    pedacos = re.split(r"^=+\s*$", texto, flags=re.MULTILINE)
    blocos = [b for b in (_bloco(p) for p in pedacos) if b is not None]
    if not blocos:
        raise ValueError("Não encontrei nenhuma tabela de amostra em %s."
                         % os.path.basename(caminho))
    return blocos


def imagem_ao_lado(caminho_txt):
    """Os bytes do .png de mesmo nome que o .txt, se ele existir."""
    base = os.path.splitext(caminho_txt)[0]
    for extensao in (".png", ".PNG"):
        caminho = base + extensao
        if os.path.exists(caminho):
            with open(caminho, "rb") as f:
                return f.read()
    return None
