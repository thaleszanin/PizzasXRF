"""Cores e tamanhos usados nos gráficos. Mexa aqui para mudar a aparência."""

# Paleta de cores fixa para as fatias das pizzas
PALETTE = [
    '#7A4E2D', '#39533F', '#B8792E', '#6B8F71', '#A85C32',
    '#8C6B3F', '#4E6E52', '#C99A4A', '#5A3720', '#95724A',
    '#3E5A45', '#D2A85E', '#82603C', '#4A6B4E', '#BF8A47',
]
# Cor da fatia agrupada "Traço" no gráfico do meio. Não é um elemento,
# por isso não mora em cores.py — é o 119 da lista de cores.
TRACE_LUMP_COLOR = '#82BBD8'

# Tamanho da fonte dos rótulos das fatias (nome do elemento + %).
# Se precisar de rótulos maiores/menores, mexa só aqui: o algoritmo
# de posicionamento mede o texto de verdade (em pixels) e se ajusta
# sozinho ao novo tamanho.
LABEL_FONTSIZE = 9.0
