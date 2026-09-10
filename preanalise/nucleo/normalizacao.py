# -*- coding: utf-8 -*-
"""O fator de normalização pelo argônio.

O argônio não está na amostra: ele está no AR entre o tubo e o detector.
Como o caminho é o mesmo em toda a batelada, o pico dele (Z = 18)
funciona como uma régua — se numa medida ele saiu menor, foi a medida
inteira que rendeu menos, não a amostra que tem menos argônio.

Daí o fator: escolhe-se uma amostra como PADRÃO e compara-se o argônio
dela com o de cada uma das outras:

    fator = área do Ar do padrão ÷ área do Ar da amostra

Uma amostra que rendeu METADE do padrão tem fator 2 — é por 2 que as
áreas dela precisam ser multiplicadas pra ficarem na mesma escala do
padrão. O padrão comparado consigo mesmo dá 1, que é a conferência
mais barata de que a conta está certa.

Sem padrão escolhido, sem argônio no padrão ou sem argônio na amostra
não existe fator nenhum, e é isso que o `None` quer dizer — cada um
desses casos tem o seu texto em `motivo_sem_fator`, porque "—" na tela
sem explicação é o tipo de coisa que vira pergunta na bancada.

Funções puras: entram e saem números, sem interface e sem Excel.
"""

# O argônio do ar. É o pico que serve de régua entre uma medida e outra.
Z_ARGONIO = 18
SIMBOLO_ARGONIO = "Ar"

# O nome do número, escrito uma vez só: a tela e a planilha usam este.
NOME_DO_FATOR = "Fator de Normalização"

# Fora desta faixa o "%.4f" vira 0.0000 ou um número comprido demais
# pra caber ao lado do nome da amostra; aí o fator sai em notação
# científica. Um fator assim já é sinal de medida estranha, mas quem
# olha a tela tem que conseguir LER que ele é estranho.
FATOR_MINIMO_LEGIVEL, FATOR_MAXIMO_LEGIVEL = 0.001, 10000.0


def area_do_argonio(elementos):
    """A área do pico de Ar de uma amostra, ou None se não houver.

    `elementos` é a lista que `ler_espectro` devolve. Área zero ou
    negativa conta como ausência: o ajuste não achou pico ali, e dividir
    por isso não daria número nenhum.
    """
    for elemento in elementos:
        if elemento["z"] == Z_ARGONIO:
            area = elemento["area"]
            return area if area > 0 else None
    return None


def fator_de_normalizacao(area_padrao, area_amostra):
    """(área do Ar do padrão) ÷ (área do Ar da amostra).

    None quando falta o argônio de um dos dois lados — é o mesmo None
    que `area_do_argonio` devolve, então dá pra encadear as duas sem
    conferir nada no meio.
    """
    if not area_padrao or not area_amostra:
        return None
    return area_padrao / area_amostra


def motivo_sem_fator(tem_padrao, area_padrao, area_amostra):
    """Por que esta amostra ficou sem fator — ou None, se ela tem um.

    A ordem importa: sem padrão escolhido não adianta falar de argônio,
    e um padrão sem argônio deixa a batelada INTEIRA sem fator, então
    esse é o primeiro aviso que quem olha precisa ver.
    """
    if not tem_padrao:
        return "escolha a amostra padrão"
    if not area_padrao:
        return "o padrão não tem pico de %s" % SIMBOLO_ARGONIO
    if not area_amostra:
        return "esta amostra não tem pico de %s" % SIMBOLO_ARGONIO
    return None


def formatar_fator(fator):
    """O fator como texto: "1.0342". Sem fator, um travessão."""
    if fator is None:
        return "—"
    if FATOR_MINIMO_LEGIVEL <= fator <= FATOR_MAXIMO_LEGIVEL:
        return "%.4f" % fator
    return "%.3e" % fator
