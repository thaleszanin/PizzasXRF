# -*- coding: utf-8 -*-
"""Cor fixa por elemento químico (paleta CPK/Jmol).

A ideia: o Ferro é SEMPRE da mesma cor — na pizza "Total", na
"Majoritários", na "Traço", e em todas as amostras da batelada. Antes a
cor era posicional (a 1ª fatia pegava a 1ª cor da paleta), então o mesmo
elemento mudava de cor de um gráfico pro outro.

Para mexer numa cor, é só editar o hex em ELEMENT_COLORS. As chaves
aceitam as duas formas, misturadas à vontade:

    "Fe": "#E06633"     <- pelo símbolo
    26:   "#E06633"     <- pelo número atômico (Z)

Elemento que não estiver na lista cai no comportamento antigo (uma cor
da PALETTE conforme a posição), então nada quebra por esquecimento.

A cor da fatia agrupada "Traço" não mora aqui — ela não é um elemento.
Está em estilo.py, como TRACE_LUMP_COLOR.
"""

from .estilo import PALETTE
from ..nucleo.tabela_periodica import PERIODIC_TABLE

# ============================================================
# Paleta CPK/Jmol — a convenção padrão de cores de elementos.
# Uma linha por elemento, do H (Z=1) ao Og (Z=118).
# ============================================================
ELEMENT_COLORS = {
    "H":  "#FFFFFF",  #   1  Hidrogênio
    "He": "#D9FFFF",  #   2  Hélio
    "Li": "#CC80FF",  #   3  Lítio
    "Be": "#C2FF00",  #   4  Berílio
    "B":  "#FFB5B5",  #   5  Boro
    "C":  "#909090",  #   6  Carbono
    "N":  "#3050F8",  #   7  Nitrogênio
    "O":  "#FF0D0D",  #   8  Oxigênio
    "F":  "#90E050",  #   9  Flúor
    "Ne": "#B3E3F5",  #  10  Neônio
    "Na": "#AB5CF2",  #  11  Sódio
    "Mg": "#8AFF00",  #  12  Magnésio
    "Al": "#BFA6A6",  #  13  Alumínio
    "Si": "#F0C8A0",  #  14  Silício
    "P":  "#FF8000",  #  15  Fósforo
    "S":  "#FFFF30",  #  16  Enxofre
    "Cl": "#1FF01F",  #  17  Cloro
    "Ar": "#80D1E3",  #  18  Argônio
    "K":  "#8F40D4",  #  19  Potássio
    "Ca": "#50FF00",  #  20  Cálcio
    "Sc": "#E6E6E6",  #  21  Escândio
    "Ti": "#BFC2C7",  #  22  Titânio
    "V":  "#A6A6AB",  #  23  Vanádio
    "Cr": "#8A8A8F",  #  24  Cromo
    "Mn": "#9C7AC7",  #  25  Manganês
    "Fe": "#E06633",  #  26  Ferro
    "Co": "#F090A0",  #  27  Cobalto
    "Ni": "#50D050",  #  28  Níquel
    "Cu": "#C88033",  #  29  Cobre
    "Zn": "#7D80B0",  #  30  Zinco
    "Ga": "#C28F8F",  #  31  Gálio
    "Ge": "#668F8F",  #  32  Germânio
    "As": "#BD80E3",  #  33  Arsênio
    "Se": "#FFA100",  #  34  Selênio
    "Br": "#A62929",  #  35  Bromo
    "Kr": "#5CB8D1",  #  36  Criptônio
    "Rb": "#702EB8",  #  37  Rubídio
    "Sr": "#00FF00",  #  38  Estrôncio
    "Y":  "#94FFFF",  #  39  Ítrio
    "Zr": "#94E0E0",  #  40  Zircônio
    "Nb": "#73C2C9",  #  41  Nióbio
    "Mo": "#54B5B5",  #  42  Molibdênio
    "Tc": "#3B9E9E",  #  43  Tecnécio
    "Ru": "#248F8F",  #  44  Rutênio
    "Rh": "#0A7D8C",  #  45  Ródio
    "Pd": "#006985",  #  46  Paládio
    "Ag": "#C0C0C0",  #  47  Prata
    "Cd": "#FFD98F",  #  48  Cádmio
    "In": "#A67573",  #  49  Índio
    "Sn": "#668080",  #  50  Estanho
    "Sb": "#9E63B5",  #  51  Antimônio
    "Te": "#D47A00",  #  52  Telúrio
    "I":  "#940094",  #  53  Iodo
    "Xe": "#3B9EB2",  #  54  Xenônio
    "Cs": "#5A1D99",  #  55  Césio
    "Ba": "#00C200",  #  56  Bário
    "La": "#70D4FF",  #  57  Lantânio
    "Ce": "#FFFFC7",  #  58  Cério
    "Pr": "#D9FFC7",  #  59  Praseodímio
    "Nd": "#C7FFC7",  #  60  Neodímio
    "Pm": "#A3FFC7",  #  61  Promécio
    "Sm": "#8FFFC7",  #  62  Samário
    "Eu": "#61FFC7",  #  63  Európio
    "Gd": "#45FFC7",  #  64  Gadolínio
    "Tb": "#30FFC7",  #  65  Térbio
    "Dy": "#1FFFC7",  #  66  Disprósio
    "Ho": "#00FF9C",  #  67  Hólmio
    "Er": "#00E675",  #  68  Érbio
    "Tm": "#00D452",  #  69  Túlio
    "Yb": "#00BF38",  #  70  Itérbio
    "Lu": "#00AB24",  #  71  Lutécio
    "Hf": "#4DC2FF",  #  72  Háfnio
    "Ta": "#4DA6FF",  #  73  Tântalo
    "W":  "#2194D6",  #  74  Tungstênio
    "Re": "#267DAB",  #  75  Rênio
    "Os": "#266696",  #  76  Ósmio
    "Ir": "#175487",  #  77  Irídio
    "Pt": "#D0D0E0",  #  78  Platina
    "Au": "#FFD700",  #  79  Ouro
    "Hg": "#B8B8D0",  #  80  Mercúrio
    "Tl": "#A6544D",  #  81  Tálio
    "Pb": "#575961",  #  82  Chumbo
    "Bi": "#9E4FB5",  #  83  Bismuto
    "Po": "#AB5C00",  #  84  Polônio
    "At": "#754F45",  #  85  Astato
    "Rn": "#267B8A",  #  86  Radônio
    "Fr": "#3D0F6B",  #  87  Frâncio
    "Ra": "#008A00",  #  88  Rádio
    "Ac": "#70ABFA",  #  89  Actínio
    "Th": "#00BAFF",  #  90  Tório
    "Pa": "#00A1FF",  #  91  Protactínio
    "U":  "#008FFF",  #  92  Urânio
    "Np": "#0080FF",  #  93  Neptúnio
    "Pu": "#006BFF",  #  94  Plutônio
    "Am": "#005CE6",  #  95  Amerício
    "Cm": "#0047B3",  #  96  Cúrio
    "Bk": "#003380",  #  97  Berquélio
    "Cf": "#00204D",  #  98  Califórnio
    "Es": "#001133",  #  99  Einstênio
    "Fm": "#000A1A",  # 100  Férmio
    "Md": "#2F8A90",  # 101  Mendelévio
    "No": "#991717",  # 102  Nobélio
    "Lr": "#84995D",  # 103  Laurêncio
    "Rf": "#D44123",  # 104  Rutherfordium
    "Db": "#B0187F",  # 105  Dúbnio
    "Sg": "#84C8A4",  # 106  Seabórgio
    "Bh": "#0EC075",  # 107  Bóhrio
    "Hs": "#2080A1",  # 108  Hássio
    "Mt": "#E1FF61",  # 109  Meitnério
    "Ds": "#118DCC",  # 110  Darmstádio
    "Rg": "#AE9FBB",  # 111  Roentgênio
    "Cn": "#C1257C",  # 112  Copernício
    "Nh": "#67CD57",  # 113  Nihônio
    "Fl": "#4526A1",  # 114  Fleróvio
    "Mc": "#F6CE9C",  # 115  Moscóvio
    "Lv": "#00FAFF",  # 116  Livermório
    "Ts": "#F8FF39",  # 117  Tenessino
    "Og": "#000000",  # 118  Oganessônio
}


def _normalizar(tabela):
    """Deixa tudo indexado por símbolo, aceitando chaves por Z ou por
    símbolo (em qualquer caixa: "fe", "Fe" e "FE" valem o mesmo)."""
    normalizado = {}
    for chave, cor in tabela.items():
        if isinstance(chave, int):
            simbolo = PERIODIC_TABLE.get(chave)
            if simbolo is None:
                raise ValueError("Z desconhecido em ELEMENT_COLORS: %r" % (chave,))
        else:
            simbolo = str(chave).strip()
        normalizado[simbolo.lower()] = cor
    return normalizado


_POR_SIMBOLO = _normalizar(ELEMENT_COLORS)


def color_for(element, fallback_index=0):
    """Cor de um elemento (o dicionário {"z", "symbol", "valor"}).

    Sem entrada na lista, devolve a cor posicional de antes — daí o
    `fallback_index`, que é a posição da fatia no gráfico.
    """
    simbolo = str(element.get("symbol", "")).lower()
    if simbolo in _POR_SIMBOLO:
        return _POR_SIMBOLO[simbolo]
    return PALETTE[fallback_index % len(PALETTE)]


def colors_for(elements):
    """Lista de cores, na mesma ordem dos elementos recebidos."""
    return [color_for(e, i) for i, e in enumerate(elements)]
