# -*- coding: utf-8 -*-
"""De onde vêm os números que o gráfico divide.

São duas fontes, e a escolha é a PRIMEIRA coisa da janela porque muda o
que precisa ser carregado:

  ÁREAS          os .txt do XRF (um por amostra, obrigatórios) e, se
                 quiser, o arquivo de mapeamento. O valor de cada
                 elemento é a área do pico, em contagens por segundo.

  CONCENTRAÇÕES  a planilha .xlsx exportada pelo programa de
                 concentrações (uma só, obrigatória) e, se quiser, o
                 mesmo arquivo de mapeamento. O valor de cada elemento é
                 a concentração, na unidade que estiver no cabeçalho da
                 planilha (normalmente mg/kg).

Daí pra frente é tudo igual: a mesma separação entre majoritário e
traço, os mesmos gráficos, as mesmas tabelas. O que muda é só o rótulo
da coluna e quantas casas decimais fazem sentido mostrar — uma área vale
milhares de contagens e não precisa de casa nenhuma; uma concentração
pode ser 0,065 mg/kg, e arredondar isso pra "0" apagaria o número.

As duas fontes NÃO se misturam numa mesma tela: meia lista em cps e
meia em mg/kg daria uma pizza sem significado. Por isso a janela limpa
as amostras ao trocar de fonte.
"""

AREAS = "areas"
CONCENTRACOES = "concentracoes"


def _formatar_area(valor):
    """Área: milhares de contagens, casa decimal nenhuma."""
    return "%.0f" % valor


def _formatar_concentracao(valor):
    """Concentração: o que for preciso pro número não sumir.

    Na mesma planilha convivem 2986 mg/kg de cálcio e 0,065 mg/kg de
    cromo; um formato fixo perderia um dos dois. Número redondo sai sem
    casa decimal, que é como ele estava na planilha.
    """
    if valor >= 100 or valor == int(valor):
        return "%.0f" % valor
    if valor >= 1:
        return "%.1f" % valor
    return "%.3g" % valor


FONTES = {
    "1 — Áreas (.txt do XRF)": {
        "tipo": AREAS,
        "grandeza": "Área",
        "unidade": "cps",
        "formatar": _formatar_area,
        "botao": "1. Carregar amostras (.txt)",
        "dialogo": "Selecione os arquivos .txt da batelada",
        "filtros": [("Arquivos de texto", "*.txt")],
        "varios": True,       # uma amostra por arquivo
    },
    "2 — Concentrações (planilha .xlsx)": {
        "tipo": CONCENTRACOES,
        "grandeza": "Concentração",
        "unidade": "mg/kg",   # trocada pela que vier no cabeçalho
        "formatar": _formatar_concentracao,
        "botao": "1. Carregar planilha (.xlsx)",
        "dialogo": "Selecione a planilha exportada pelo programa de concentrações",
        "filtros": [("Planilha do Excel", "*.xlsx *.xlsm")],
        "varios": False,      # todas as amostras vêm de um arquivo só
    },
}

# A fonte em que o programa abre: a de sempre.
FONTE_PADRAO = next(iter(FONTES))


def rotulo_da_coluna(fonte, unidade=None):
    """O cabeçalho da coluna de valores: "Área (cps)", "Concentração
    (mg/kg)". A unidade pode vir de fora — a planilha diz a dela."""
    return "%s (%s)" % (fonte["grandeza"], unidade or fonte["unidade"])
