# -*- coding: utf-8 -*-
"""A regra da pré-análise: qual elemento tem erro alto demais.

O erro que vem do XRF é absoluto, na mesma unidade da área. Sozinho ele
não diz nada — 200 cps de erro é ótimo num pico de 80 000 e é um
desastre num pico de 300. O que interessa é o erro RELATIVO:

    erro % = erro / área × 100

O limite acima do qual o elemento é considerado ruim é escolhido na
janela (o padrão é 50%): passou disso, a recomendação é refazer a
análise sem aquele elemento, porque o ajuste não conseguiu separar o
pico dele do fundo.

Funções puras: entram e saem listas de dicionários, sem interface, sem
Excel e sem matplotlib.
"""

# O limite em que o programa abre, em porcentagem. É o valor de bancada:
# acima de 50% o pico praticamente não se distingue do fundo.
LIMITE_PADRAO = 50.0
LIMITE_MINIMO, LIMITE_MAXIMO = 1.0, 100.0

# O que o erro relativo vale quando a área é zero ou negativa: o ajuste
# não achou pico nenhum ali, então o elemento é sempre suspeito.
SEM_AREA = float("inf")


def erro_percentual(elemento):
    """O erro relativo do elemento, em porcentagem do valor dele."""
    area = elemento["area"]
    if area > 0:
        return elemento["erro"] / area * 100.0
    return SEM_AREA


def avaliar(elementos, limite):
    """Confere os elementos de UMA amostra contra o limite.

    Devolve um dicionário com tudo o que a tela, o log e a planilha
    precisam — os três olham para os mesmos números, então nunca
    discordam entre si:

        {"linhas": [...],   os elementos, do pior erro pro melhor, cada
                            um com "pct" (o erro relativo) e "alto"
         "altos":  [...],   só os que passaram do limite, na mesma ordem
         "total":  int      quantos elementos a amostra tem
        }
    """
    linhas = []
    for elemento in elementos:
        pct = erro_percentual(elemento)
        item = dict(elemento)
        item["pct"] = pct
        item["alto"] = pct > limite
        linhas.append(item)

    # do pior erro pro melhor: quem for reprovado aparece primeiro, na
    # tela e na planilha. O símbolo desempata pra ordem não dançar entre
    # duas amostras com os mesmos erros.
    linhas.sort(key=lambda e: (-e["pct"], e["symbol"]))

    return {
        "linhas": linhas,
        "altos": [e for e in linhas if e["alto"]],
        "total": len(linhas),
    }


def formatar_pct(pct):
    """O erro relativo como texto: "12.4%". Área zero não vira número
    nenhum — vira o aviso de que não havia pico ali."""
    if pct == SEM_AREA:
        return "sem área"
    return "%.1f%%" % pct
