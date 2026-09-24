"""A "razão do tubo": uma conferência da medida, não um resultado.

O elemento do alvo do tubo aparece em todo espectro (é o espalhamento
do próprio tubo) e sai do gráfico. Mas a relação entre as linhas dele
deveria ficar mais ou menos constante de uma amostra para outra; se uma
amostra foge muito da das outras, vale olhar a medida de novo.

  tubo Ag  ->  área da Ag K / área da Ag L
  tubo Au  ->  área do Au / área da Pt
  tubo Rh  ->  área do Rh K / área do Rh L

Função pura, sem interface: recebe os elementos de uma amostra (com as
"linhas" que o parse_xrf_file guarda) e o tubo selecionado.
"""


def _eh_linha_k(z, energia):
    """True se o pico em `energia` (keV) é da camada K do elemento Z.

    A lei de Moseley dá o Kα por volta de 10,2 eV·(Z-1)²; as linhas L
    ficam muito abaixo disso (Ag: K em 22 keV, L em 3 keV), então metade
    do Kα separa as duas camadas com folga para qualquer tubo.
    """
    return energia > 0.5 * 0.0102 * (z - 1) ** 2


def _areas_k_l(elemento):
    """(área K, área L) de um elemento, a partir das linhas do .txt."""
    k = l = 0.0
    for energia, valor in elemento.get("linhas", ()):
        if _eh_linha_k(elemento["z"], energia):
            k += valor
        else:
            l += valor
    return k, l


def razao_do_tubo(elements, tube_z):
    """Devolve (rótulo, razão) para o tubo selecionado, ou None se não há
    tubo. A razão é None quando falta um dos dois lados (o elemento não
    apareceu, ou só apareceu uma das linhas) — o rótulo diz o que seria."""
    if not tube_z:
        return None
    por_z = {e["z"]: e for e in elements}

    if 79 in tube_z:  # ouro: Au contra Pt, as duas áreas inteiras
        rotulo = "Au / Pt"
        au, pt = por_z.get(79), por_z.get(78)
        cima = au["valor"] if au else 0.0
        baixo = pt["valor"] if pt else 0.0
    else:
        z = 47 if 47 in tube_z else 45 if 45 in tube_z else None
        if z is None:
            return None
        simbolo = "Ag" if z == 47 else "Rh"
        rotulo = "%s K / %s L" % (simbolo, simbolo)
        elemento = por_z.get(z)
        cima, baixo = _areas_k_l(elemento) if elemento else (0.0, 0.0)

    if cima <= 0 or baixo <= 0:
        return rotulo, None
    return rotulo, cima / baixo


def texto_da_razao(elements, tube_z):
    """A frase que vai para a tela, ou "" se não há tubo selecionado."""
    resultado = razao_do_tubo(elements, tube_z)
    if resultado is None:
        return ""
    rotulo, razao = resultado
    if razao is None:
        return "Razão do tubo (%s): sem os dois picos" % rotulo
    return "Razão do tubo (%s): %s" % (rotulo, ("%.3f" % razao).replace(".", ","))
