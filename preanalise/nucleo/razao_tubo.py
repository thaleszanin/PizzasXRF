# -*- coding: utf-8 -*-
"""A "razão do tubo": uma conferência da medida, não um resultado.

É a mesma conta que o banco de dados mostra embaixo de cada amostra
(bancodedados/nucleo/razao_tubo.py). O elemento do alvo do tubo aparece
em todo espectro (é o espalhamento do próprio tubo), mas a relação entre
as linhas dele deveria ficar mais ou menos constante de uma amostra para
outra; se uma amostra foge muito da das outras, vale olhar a medida de
novo.

  tubo Ag  ->  área da Ag K / área da Ag L
  tubo Au  ->  área do Au / área da Pt
  tubo Rh  ->  área do Rh K / área do Rh L

A cópia existe porque o pacote do banco puxa o numpy ao ser importado,
e a pré-análise é empacotada sem ele. Aqui os elementos são os do
`ler_espectro`: a área em "area" e cada pico em "picos".
"""

# As opções da caixa do tubo, iguais às do banco de dados. Quando o tubo
# é ouro, a platina (Z=78) vem junto: é dela que sai a razão Au / Pt.
TUBOS = {
    "Nenhum": None,
    "Prata — Ag": {47},
    "Ouro — Au": {78, 79},
    "Ródio — Rh": {45},
}
TUBO_PADRAO = "Nenhum"

# O texto da dica que aparece em cima da razão, nos dois programas.
DICA_DA_RAZAO = ("Razão entre as linhas do elemento do tubo: Ag K/Ag L, "
                 "Au/Pt ou Rh K/Rh L. Serve para conferir se ela fica "
                 "constante entre as amostras.")


def _eh_linha_k(z, energia):
    """True se o pico em `energia` (keV) é da camada K do elemento Z.

    A lei de Moseley dá o Kα por volta de 10,2 eV·(Z-1)²; as linhas L
    ficam muito abaixo disso (Ag: K em 22 keV, L em 3 keV), então metade
    do Kα separa as duas camadas com folga para qualquer tubo.
    """
    return energia > 0.5 * 0.0102 * (z - 1) ** 2


def _areas_k_l(elemento):
    """(área K, área L) de um elemento, a partir dos picos do .txt."""
    k = l = 0.0
    for energia, area in elemento.get("picos", ()):
        if _eh_linha_k(elemento["z"], energia):
            k += area
        else:
            l += area
    return k, l


def razao_do_tubo(elementos, tubo_z):
    """Devolve (rótulo, razão) para o tubo selecionado, ou None se não há
    tubo. A razão é None quando falta um dos dois lados (o elemento não
    apareceu, ou só apareceu uma das linhas) — o rótulo diz o que seria."""
    if not tubo_z:
        return None
    por_z = {e["z"]: e for e in elementos}

    if 79 in tubo_z:  # ouro: Au contra Pt, as duas áreas inteiras
        rotulo = "Au / Pt"
        au, pt = por_z.get(79), por_z.get(78)
        cima = au["area"] if au else 0.0
        baixo = pt["area"] if pt else 0.0
    else:
        z = 47 if 47 in tubo_z else 45 if 45 in tubo_z else None
        if z is None:
            return None
        simbolo = "Ag" if z == 47 else "Rh"
        rotulo = "%s K / %s L" % (simbolo, simbolo)
        elemento = por_z.get(z)
        cima, baixo = _areas_k_l(elemento) if elemento else (0.0, 0.0)

    if cima <= 0 or baixo <= 0:
        return rotulo, None
    return rotulo, cima / baixo


def texto_da_razao(elementos, tubo_z):
    """A frase que vai para a tela, ou "" se não há tubo selecionado."""
    resultado = razao_do_tubo(elementos, tubo_z)
    if resultado is None:
        return ""
    rotulo, razao = resultado
    if razao is None:
        return "Razão do tubo (%s): sem os dois picos" % rotulo
    return "Razão do tubo (%s): %s" % (rotulo, ("%.3f" % razao).replace(".", ","))
