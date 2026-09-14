# -*- coding: utf-8 -*-
"""Leitura da planilha de informações do banco (a "lista de amostras").

É uma planilha qualquer, com UMA regra de forma:

    ┌──────────────────┬──────────────┬─────────────────┬──────────┐
    │ Código           │ Nome popular │ Nome científico │ Estado   │  <- 1ª linha: as categorias
    ├──────────────────┼──────────────┼─────────────────┼──────────┤
    │ M001             │ Muiracatiara │ Astronium lec.  │ Rondônia │  <- uma amostra por linha
    │ M003             │ Roxinho      │ Peltogyne pan.  │ Rondônia │
    └──────────────────┴──────────────┴─────────────────┴──────────┘

A primeira linha diz o nome das categorias; uma das colunas — a
primeira, normalmente — traz o nome da amostra, o MESMO nome que o
mapeamento dá aos .txt do XRF. É por esse nome que a planilha se junta
às medições que já estão no banco.

Cada banco tem a sua planilha, com categorias diferentes (a de madeira
tem nome científico e coordenadas; a de carne teria outras coisas), e o
programa não precisa conhecer nenhuma delas de antemão: as categorias
que aparecerem aqui viram as categorias do banco.
"""

import os

from .repositorio import normalizar_nome


def _texto(celula):
    """A célula como texto, do jeito que aparece na planilha: número
    inteiro sem ".0", decimal com o ponto, data só a data."""
    if celula is None:
        return ""
    if isinstance(celula, float):
        return "%d" % celula if celula == int(celula) and abs(celula) < 1e15 else repr(celula)
    if hasattr(celula, "isoformat"):
        texto = celula.isoformat()
        return texto[:10] if texto.endswith("T00:00:00") else texto
    return " ".join(str(celula).split())


def ler_planilha(caminho):
    """Lê a primeira aba e devolve (categorias, linhas).

    `categorias` são os títulos da primeira linha (as colunas sem
    título ficam de fora) e `linhas` é uma lista de listas de texto, na
    mesma ordem das categorias. Linhas inteiramente vazias são puladas.
    """
    try:
        import openpyxl
    except ImportError:
        raise ValueError(
            "Para ler planilhas falta a biblioteca openpyxl.\n\n"
            "Instale com:  pip install openpyxl")

    if os.path.splitext(caminho)[1].lower() not in (".xlsx", ".xlsm"):
        raise ValueError("Escolha uma planilha .xlsx.")

    livro = openpyxl.load_workbook(caminho, data_only=True, read_only=True)
    try:
        aba = livro.worksheets[0]
        grade = [list(linha) for linha in aba.iter_rows(values_only=True)]
    finally:
        livro.close()

    if not grade:
        raise ValueError("A planilha está vazia.")

    cabecalho = [_texto(c) for c in grade[0]]
    colunas = [i for i, titulo in enumerate(cabecalho) if titulo]
    if not colunas:
        raise ValueError("A primeira linha da planilha precisa ter os nomes "
                         "das categorias.")
    categorias = [cabecalho[i] for i in colunas]

    linhas = []
    for bruta in grade[1:]:
        valores = [_texto(bruta[i]) if i < len(bruta) else "" for i in colunas]
        if any(valores):
            linhas.append(valores)
    if not linhas:
        raise ValueError("A planilha só tem a linha de cabeçalho.")
    return categorias, linhas


def coluna_sugerida(linhas, nomes_conhecidos):
    """Em que coluna estão os nomes das amostras?

    A regra é "a primeira coluna", mas a planilha pode ter o código
    antigo na primeira e o nome que o mapeamento usa na segunda. Então,
    se já houver nomes conhecidos (os do mapeamento carregado, os das
    amostras do banco), a coluna com mais nomes que batem ganha; sem
    nenhum nome conhecido, ou sem coluna alguma que bata, fica a
    primeira.
    """
    alvos = {normalizar_nome(n) for n in nomes_conhecidos if n}
    alvos.discard("")
    if not alvos or not linhas:
        return 0
    melhor, acertos = 0, 0
    for coluna in range(len(linhas[0])):
        quantos = sum(1 for linha in linhas
                      if normalizar_nome(linha[coluna]) in alvos)
        if quantos > acertos:
            melhor, acertos = coluna, quantos
    return melhor


def separar_chave(categorias, linhas, coluna_chave):
    """Tira a coluna chave do meio das outras.

    Devolve (categorias sem a chave, [(nome, [valores])], linhas sem
    nome): uma linha cuja célula chave está vazia não tem como entrar
    no banco, e é devolvida à parte para a janela avisar.
    """
    outras = [i for i in range(len(categorias)) if i != coluna_chave]
    prontas, sem_nome = [], 0
    for linha in linhas:
        nome = linha[coluna_chave].strip()
        if not nome:
            sem_nome += 1
            continue
        prontas.append((nome, [linha[i] for i in outras]))
    return [categorias[i] for i in outras], prontas, sem_nome
