"""Regras de descarte de elementos e separação majoritário/traço.

Funções puras: recebem e devolvem listas de dicionários
{"z": int, "symbol": str, "valor": float}. Sem interface, sem matplotlib.

O "valor" é a grandeza que o gráfico divide: a área do pico quando os
dados vêm dos .txt do XRF, a concentração quando vêm da planilha. As
regras aqui são as mesmas nos dois casos.
"""

# Elemento sempre descartado: Argônio (contaminação do ar — as medidas
# não são feitas a vácuo, então Ar nunca é componente da amostra)
ALWAYS_EXCLUDED_Z = {18}

# Elementos dos tubos de raios X disponíveis no equipamento.
# Quando o tubo é ouro, também removemos o platina (Z=78) para evitar
# que o espectro traga elementos ligados ao material do alvo do tubo.
TUBE_OPTIONS = {
    "Nenhum": None,
    "Prata — Ag": {47},
    "Ouro — Au": {78, 79},
    "Ródio — Rh": {45},
}


def apply_exclusions(elements, tube_z):
    """Remove o Argônio (sempre) e os elementos do tubo selecionado (se
    houver). Devolve (mantidos, removidos)."""
    excluded = set(ALWAYS_EXCLUDED_Z)
    if tube_z is not None:
        if isinstance(tube_z, (set, list, tuple)):
            excluded.update(tube_z)
        else:
            excluded.add(tube_z)
    kept = [e for e in elements if e["z"] not in excluded]
    removed = [e for e in elements if e["z"] in excluded]
    return kept, removed


def classify(elements, threshold_percent):
    """Separa os elementos em majoritário/traço.

    Regra: ordena do menor pro maior; entram no grupo traço um a um
    enquanto a soma acumulada (em % do total) não ultrapassar o limite.
    """
    total = sum(e["valor"] for e in elements)
    if total == 0:
        return [], [], 0

    sorted_elements = sorted(elements, key=lambda e: e["valor"])
    trace = []
    cumulative = 0.0
    for e in sorted_elements:
        would_be = (cumulative + e["valor"]) / total * 100
        if would_be <= threshold_percent:
            trace.append(e)
            cumulative += e["valor"]
        else:
            break

    trace_z = {e["z"] for e in trace}
    major = [e for e in elements if e["z"] not in trace_z]
    return major, trace, total
