"""
Catalogador de Espectros FRX — versão Python
==============================================

O que esse programa faz:
  1. Lê os arquivos .txt de saída do FRX (formato WinQXAS: cabeçalho +
     linhas "Z, energia, área, erro, chi2" depois de "Photopeaks:").
  2. Soma áreas de linhas repetidas do mesmo elemento (Kα e Lα, por ex.).
  3. Descarta sempre o Argônio (Z=18) e, se você selecionar um tubo de
     raios X (Ag/Au/Rh), descarta também o elemento desse tubo.
  4. Separa os elementos restantes em "majoritário" e "traço": ordena do
     menor pro maior e vai somando no grupo traço enquanto a soma
     acumulada não ultrapassar o limite escolhido no slider.
  5. Desenha 3 gráficos de pizza por amostra: total, majoritários, traço.
  6. Permite carregar um arquivo de mapeamento (código do arquivo -> nome
     real da amostra) e processar a batelada inteira de uma vez.

Como rodar:
  1. Precisa de Python 3 instalado.
  2. Instale a única dependência externa:  pip install matplotlib
     (o Tkinter já vem junto do Python na maioria dos sistemas; no Linux,
     se der erro, instale com: sudo apt install python3-tk)
  3. Rode:  python catalogador_frx.py

O código está dividido em duas partes:
  - Funções "puras" (parse_frx_file, classify, etc.) — a lógica de dados,
    sem nada de interface. É a parte mais importante para entender.
  - A classe App — a janela e os botões (Tkinter). Chama as funções acima.
"""

import math
import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.lines import Line2D


# ============================================================
# TABELA PERIÓDICA (Z -> símbolo)
# O .txt só traz o número atômico (Z); esse dicionário serve pra
# transformar 19 em "K", 26 em "Fe", etc.
# ============================================================
_SYMBOLS = [
    None, 'H', 'He', 'Li', 'Be', 'B', 'C', 'N', 'O', 'F', 'Ne',
    'Na', 'Mg', 'Al', 'Si', 'P', 'S', 'Cl', 'Ar', 'K', 'Ca',
    'Sc', 'Ti', 'V', 'Cr', 'Mn', 'Fe', 'Co', 'Ni', 'Cu', 'Zn',
    'Ga', 'Ge', 'As', 'Se', 'Br', 'Kr', 'Rb', 'Sr', 'Y', 'Zr',
    'Nb', 'Mo', 'Tc', 'Ru', 'Rh', 'Pd', 'Ag', 'Cd', 'In', 'Sn',
    'Sb', 'Te', 'I', 'Xe', 'Cs', 'Ba', 'La', 'Ce', 'Pr', 'Nd',
    'Pm', 'Sm', 'Eu', 'Gd', 'Tb', 'Dy', 'Ho', 'Er', 'Tm', 'Yb',
    'Lu', 'Hf', 'Ta', 'W', 'Re', 'Os', 'Ir', 'Pt', 'Au', 'Hg',
    'Tl', 'Pb', 'Bi', 'Po', 'At', 'Rn', 'Fr', 'Ra', 'Ac', 'Th',
    'Pa', 'U',
]
PERIODIC_TABLE = {z: sym for z, sym in enumerate(_SYMBOLS) if sym}

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

# Paleta de cores fixa para as fatias das pizzas
PALETTE = [
    '#7A4E2D', '#39533F', '#B8792E', '#6B8F71', '#A85C32',
    '#8C6B3F', '#4E6E52', '#C99A4A', '#5A3720', '#95724A',
    '#3E5A45', '#D2A85E', '#82603C', '#4A6B4E', '#BF8A47',
]
TRACE_LUMP_COLOR = '#C9BFA0'


def draw_pie_with_leaders(ax, sizes, labels, colors, radius=1.0):
    """Desenha uma pizza com rótulos (nome + %) sempre do lado de fora,
    ligados à própria fatia por uma linha guia fina, e TODOS à mesma
    distância do centro (sem exceção).

    O texto e a linha guia são desenhados como dois elementos SEPARADOS
    (`ax.text` + `Line2D`) — não com `ax.annotate`, cuja caixa delimitadora
    inclui a seta inteira e não só o texto, o que torna qualquer medida
    de sobreposição sem sentido. Com o texto isolado, medimos a caixa
    *real* dele (em pixels, já considerando fonte/DPI de verdade) e:

    1. Agrupamos em "blocos" só os rótulos vizinhos que colidiriam na
       posição natural deles (mais um passo de absorção: um bloco, ao
       crescer, pode "engolir" o espaço de um vizinho que originalmente
       não colidia — sem isso ele ficaria espremido fora da ordem).
    2. Um bloco com mais de 2 rótulos é dividido nos dois lados da
       pizza: a metade mais ambígua (mais perto do topo/base, com X
       natural pequeno) vai pro lado com menos membros; a metade que já
       é claramente de um lado fica onde está. Isso reduz pela metade a
       altura que cada lado precisa, deixando o bloco mais compacto —
       os desvios podem ir tanto pra direita quanto pra esquerda, não
       só no sentido horário.
    3. Cada metade é redistribuída em Y, simetricamente, em torno do
       próprio centro natural — e, se a pilha ultrapassar o topo/base
       do círculo dos rótulos, o bloco DESLIZA pra dentro dessa faixa
       (em direção ao "equador" da pizza, onde sobra espaço vertical)
       em vez de crescer pra fora. Sem isso, um punhado de fatias
       minúsculas no topo empurrava o raio comum do passo 4 pra longe
       e afastava TODOS os rótulos da pizza junto.
    4. Por fim, um raio ÚNICO é calculado — o maior que qualquer lado de
       qualquer bloco precisar — e TODOS os rótulos (mesmo os isolados,
       tipo fatias grandes que não colidem com nada) são projetados
       nesse MESMO raio, mantendo o Y já calculado. Assim toda a pizza
       tem uma "auréola" de rótulos a distância igual do centro, sem
       exceção, e nenhum fica desnecessariamente mais longe que o
       mínimo que os blocos mais cheios exigem.
    5. Empurramos cada rótulo horizontalmente (nunca no eixo vertical,
       que é o que garante a separação entre eles) o mínimo necessário
       pra ele nunca ficar por cima da pizza.
    6. Uma rede de segurança final, na ORDEM NATURAL das fatias (nunca
       reordenada pela posição já ajustada — isso inverteria a ordem de
       leitura dos rótulos), compara cada rótulo contra TODOS os já
       posicionados antes dele (não só o anterior na lista).
    7. Reaplica o passo 5, já que o passo 6 pode ter mexido no Y de novo.
    8. Por fim, expande os limites verticais do gráfico se algum rótulo
       tiver sido empurrado pra além da margem padrão — senão ele pode
       ficar cortado fora da figura.
    """
    if not sizes:
        return

    fig = ax.figure
    wedges, _ = ax.pie(
        sizes, colors=colors, startangle=90, radius=radius,
        wedgeprops=dict(edgecolor="white", linewidth=0.6),
    )
    ax.set_xlim(-1.9, 1.9)
    ax.set_ylim(-1.5, 1.5)

    label_radius = 1.15
    texts, anchors = [], []
    for wedge, label, size in zip(wedges, labels, sizes):
        mid_angle = math.radians((wedge.theta1 + wedge.theta2) / 2)
        x, y = math.cos(mid_angle), math.sin(mid_angle)
        ha = "left" if x >= 0 else "right"
        t = ax.text(
            x * label_radius, y * label_radius, f"{label} {size:.1f}%",
            fontsize=6.0, ha=ha, va="center",
        )
        texts.append(t)
        anchors.append((x * radius, y * radius))

    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    inv = ax.transData.inverted()

    def measure(t):
        bb = t.get_window_extent(renderer)
        data_x, _ = t.get_position()
        return data_x, bb.x0, bb.x1, bb.y1 - bb.y0, (bb.y0 + bb.y1) / 2

    def py_to_data_y(py):
        return inv.transform((0.0, py))[1]

    def data_y_to_py(dy):
        return ax.transData.transform((0.0, dy))[1]

    items = []
    for t, anchor in zip(texts, anchors):
        data_x, x0, x1, height, y = measure(t)
        items.append({
            "text": t, "anchor": anchor, "data_x": data_x,
            "x0": x0, "x1": x1, "height": height, "y": y,
        })
    items.sort(key=lambda it: -it["y"])

    def collide(a, b, padding_factor=0.5):
        if a["x0"] >= b["x1"] or a["x1"] <= b["x0"]:
            return False
        min_gap = (a["height"] + b["height"]) / 2 * (1 + padding_factor)
        return (a["y"] - b["y"]) < min_gap

    # 1) agrupa quem colidiria na posição natural
    clusters, current = [], [items[0]] if items else []
    for it in items[1:]:
        if collide(current[-1], it):
            current.append(it)
        else:
            clusters.append(current)
            current = [it]
    if current:
        clusters.append(current)

    # 1b) absorve vizinhos que cairiam dentro do intervalo que um bloco
    #     vai ocupar, mesmo sem colidir na posição original
    def cluster_span(cluster, padding_factor=0.1):
        n = len(cluster)
        if n == 1:
            return cluster[0]["y"], cluster[0]["y"]
        padding = sum(it["height"] for it in cluster) / n * padding_factor
        total_height = sum(it["height"] for it in cluster) + padding * (n - 1)
        center = (cluster[0]["y"] + cluster[-1]["y"]) / 2
        return center - total_height / 2, center + total_height / 2

    changed = True
    while changed:
        changed = False
        merged = []
        i = 0
        while i < len(clusters):
            cur = clusters[i]
            while i + 1 < len(clusters):
                lo, hi = cluster_span(cur)
                nxt = clusters[i + 1]
                same_side = (cur[-1]["data_x"] >= 0) == (nxt[0]["data_x"] >= 0)
                if same_side and lo - 0.02 <= nxt[0]["y"] <= hi + 0.02:
                    cur = cur + nxt
                    del clusters[i + 1]
                    changed = True
                else:
                    break
            merged.append(cur)
            i += 1
        clusters = merged

    # 2) divide cada bloco grande entre os dois lados da pizza: a
    #    metade mais ambígua (mais perto do topo/base) vai pro lado com
    #    menos membros; a metade claramente de um lado fica onde está
    needs_redraw = False
    for cluster in clusters:
        n = len(cluster)
        if n <= 2:
            continue
        n_right = sum(1 for it in cluster if it["data_x"] >= 0)
        minority_negative = (n - n_right) <= n_right
        half = n // 2
        head_absx = sum(abs(it["data_x"]) for it in cluster[:half]) / max(half, 1)
        tail_absx = sum(abs(it["data_x"]) for it in cluster[n - half:]) / max(half, 1)
        ambiguous = cluster[:half] if head_absx <= tail_absx else cluster[n - half:]
        for it in ambiguous:
            is_negative = it["data_x"] < 0
            if minority_negative != is_negative:
                it["text"].set_ha("right" if minority_negative else "left")
                magnitude = abs(it["data_x"]) or label_radius * 0.3
                new_data_x = -magnitude if minority_negative else magnitude
                it["text"].set_position((new_data_x, it["text"].get_position()[1]))
                needs_redraw = True

    if needs_redraw:
        fig.canvas.draw()
        for it in items:
            it["data_x"], it["x0"], it["x1"], it["height"], it["y"] = measure(it["text"])

    min_radius = radius * 1.08
    band_limit = label_radius - 0.03

    def push_out_of_pie(it):
        px_x, _ = ax.transData.transform((it["data_x"], 0))
        _, data_y = inv.transform((px_x, it["y"]))
        min_abs_x = math.sqrt(max(0.0, min_radius ** 2 - data_y ** 2))
        if abs(it["data_x"]) < min_abs_x:
            sign = 1.0 if it["data_x"] >= 0 else -1.0
            new_data_x = sign * min_abs_x
            new_px_x, _ = ax.transData.transform((new_data_x, 0))
            delta = new_px_x - px_x
            it["x0"] += delta
            it["x1"] += delta
            it["data_x"] = new_data_x

    snapshot = [(it["data_x"], it["x0"], it["x1"], it["y"]) for it in items]

    def place(slide):
        """Posiciona todos os rótulos. `slide` vai de 0 a 1: 0 deixa cada
        bloco centrado na posição natural (o raio comum cresce pra caber
        a pilha, afastando os rótulos); 1 encosta o bloco na faixa do
        raio base (rótulos o mais perto possível da pizza). Devolve o
        raio comum resultante."""
        for it, snap in zip(items, snapshot):
            it["data_x"], it["x0"], it["x1"], it["y"] = snap

        # 3) redistribui cada METADE (lado direito / esquerdo) de cada
        #    bloco em Y, simetricamente, em torno do próprio centro
        #    natural, e desliza pra dentro da faixa conforme `slide`
        for cluster in clusters:
            if len(cluster) <= 1:
                continue
            for side_items in ([it for it in cluster if it["data_x"] >= 0],
                                [it for it in cluster if it["data_x"] < 0]):
                n = len(side_items)
                if n <= 1:
                    continue
                side_items.sort(key=lambda it: -it["y"])
                padding = sum(it["height"] for it in side_items) / n * 0.1
                total_height = sum(it["height"] for it in side_items) + padding * (n - 1)
                center = sum(it["y"] for it in side_items) / n
                cursor = center + total_height / 2
                for it in side_items:
                    it["y"] = cursor - it["height"] / 2
                    cursor -= it["height"] + padding

                # o limite é sobre o CENTRO do texto (não sobre a borda
                # de cima): deixar o texto passar um pouco além do
                # círculo é inofensivo — ele está fora da pizza de
                # qualquer jeito — e é o que permite a pilha encostar de
                # fato no topo, fechando o "buraco" entre os dois lados.
                top_data = py_to_data_y(side_items[0]["y"])
                bottom_data = py_to_data_y(side_items[-1]["y"])
                if (top_data + bottom_data) / 2 >= 0:
                    shift_data = band_limit - top_data
                else:
                    shift_data = -band_limit - bottom_data
                shift_data *= slide
                if shift_data:
                    shift_px = data_y_to_py(shift_data) - data_y_to_py(0.0)
                    for it in side_items:
                        it["y"] += shift_px

        # 4) raio ÚNICO pra pizza inteira — o maior que qualquer rótulo
        #    precisar — e TODOS os rótulos vão pra esse mesmo raio
        uniform_radius = label_radius
        for it in items:
            px_x, _ = ax.transData.transform((it["data_x"], 0))
            _, data_y = inv.transform((px_x, it["y"]))
            uniform_radius = max(uniform_radius, abs(data_y) + 0.03)

        for it in items:
            px_x, _ = ax.transData.transform((it["data_x"], 0))
            _, data_y = inv.transform((px_x, it["y"]))
            data_x_mag = math.sqrt(max(0.0, uniform_radius ** 2 - data_y ** 2))
            sign = 1.0 if it["data_x"] >= 0 else -1.0
            new_data_x = sign * data_x_mag
            new_px_x, _ = ax.transData.transform((new_data_x, 0))
            delta = new_px_x - px_x
            it["x0"] += delta
            it["x1"] += delta
            it["data_x"] = new_data_x

        # 5) empurra X (mantendo o Y) o mínimo pra sair do raio da pizza
        for it in items:
            push_out_of_pie(it)

        # 6) rede de segurança final, contra TODOS os já posicionados —
        #    em ORDEM NATURAL (a mesma de items, nunca reordenada pela
        #    posição já ajustada), pra nunca inverter a ordem de leitura
        #    dos rótulos: cada um só pode ser empurrado pra BAIXO dos
        #    que vieram antes dele, nunca pra cima.
        placed = []
        for it in items:
            limit = it["y"]
            for p in placed:
                if it["x0"] < p["x1"] and it["x1"] > p["x0"]:
                    min_gap = (p["height"] + it["height"]) / 2 * 1.2
                    limit = min(limit, p["y"] - min_gap)
            it["y"] = limit
            placed.append(it)

        # 7) o passo 6 pode ter mexido no Y de novo — reaplica o passo 5
        for it in items:
            push_out_of_pie(it)

        return uniform_radius

    def leader_cuts_pie():
        """A linha guia é uma reta da fatia até o rótulo. Ela só passa
        por fora da pizza se, saindo da fatia, apontar pra fora — ou
        seja, se (rótulo - fatia) · fatia >= 0. Quanto mais o rótulo se
        afasta angularmente da própria fatia, mais essa reta vira uma
        corda que corta o miolo; é isso que limita o quanto os blocos
        podem deslizar pra perto da pizza."""
        for it in items:
            px_x, _ = ax.transData.transform((it["data_x"], 0))
            _, data_y = inv.transform((px_x, it["y"]))
            ax_x, ax_y = it["anchor"]
            if ax_x * (it["data_x"] - ax_x) + ax_y * (data_y - ax_y) < 0:
                return True
        return False

    # Busca o maior deslize (rótulos mais perto da pizza) que ainda
    # deixa todas as linhas retas passarem por fora dela.
    place(1.0)
    if leader_cuts_pie():
        lo, hi = 0.0, 1.0
        for _ in range(16):
            mid = (lo + hi) / 2
            place(mid)
            if leader_cuts_pie():
                hi = mid
            else:
                lo = mid
        place(lo)

    data_ys = []
    for it in items:
        px_x, _ = ax.transData.transform((it["data_x"], 0))
        new_x, new_y = inv.transform((px_x, it["y"]))
        it["text"].set_position((new_x, new_y))
        data_ys.append(new_y)
        ax.add_line(Line2D(
            [it["anchor"][0], new_x], [it["anchor"][1], new_y],
            color="#6B6250", linewidth=0.6, zorder=1,
        ))

    if data_ys:
        margin = 0.18
        cur_bottom, cur_top = ax.get_ylim()
        ax.set_ylim(min(cur_bottom, min(data_ys) - margin), max(cur_top, max(data_ys) + margin))


# ============================================================
# LEITURA E PROCESSAMENTO DOS DADOS
# ============================================================

def parse_frx_file(path):
    """Lê um .txt do FRX e devolve uma lista de dicionários, um por
    elemento (Z), já com as áreas de linhas repetidas somadas.

    Cada item: {"z": int, "symbol": str, "area": float}
    """
    with open(path, encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()

    # 1. Acha a linha "Photopeaks:, N" — os dados começam depois dela
    header_index = None
    for i, line in enumerate(lines):
        if "photopeaks" in line.lower():
            header_index = i
            break
    if header_index is None:
        raise ValueError(f'Não encontrei "Photopeaks" em {os.path.basename(path)}')

    data_lines = [l for l in lines[header_index + 1:] if l.strip()]

    # 2. Soma áreas de linhas com o mesmo Z (ex: linhas Kα e Lα do mesmo
    #    elemento aparecendo em linhas separadas)
    by_z = {}
    for line in data_lines:
        parts = [p.strip() for p in line.split(",") if p.strip()]
        if len(parts) < 5:
            continue
        try:
            z = int(float(parts[0]))
            area = float(parts[2])
        except ValueError:
            continue  # linha não numérica, ignora

        if z in by_z:
            by_z[z]["area"] += area
        else:
            by_z[z] = {"z": z, "symbol": PERIODIC_TABLE.get(z, f"Z{z}"), "area": area}

    return list(by_z.values())


def parse_mapping(path):
    """Lê um .csv/.txt de mapeamento "código,nome real" (aceita vírgula,
    ponto-e-vírgula ou tab como separador) e devolve um dicionário
    {código_minúsculo: nome real}."""
    mapping = {}
    with open(path, encoding="utf-8", errors="ignore") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line:
                continue
            parts = [p.strip() for p in line.replace(";", ",").replace("\t", ",").split(",")]
            if len(parts) < 2:
                continue
            code = parts[0].lower()
            name = ",".join(parts[1:]).strip()
            if code in ("codigo", "código", "code"):
                continue  # linha de cabeçalho, pula
            if code and name:
                mapping[code] = name
    return mapping


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
    total = sum(e["area"] for e in elements)
    if total == 0:
        return [], [], 0

    sorted_elements = sorted(elements, key=lambda e: e["area"])
    trace = []
    cumulative = 0.0
    for e in sorted_elements:
        would_be = (cumulative + e["area"]) / total * 100
        if would_be <= threshold_percent:
            trace.append(e)
            cumulative += e["area"]
        else:
            break

    trace_z = {e["z"] for e in trace}
    major = [e for e in elements if e["z"] not in trace_z]
    return major, trace, total


# ============================================================
# INTERFACE GRÁFICA (Tkinter)
# ============================================================

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Pizzas XRF")
        self.geometry("1180x780")

        # -------- estado da aplicação --------
        self.samples = []          # [{"code": str, "elements": [...]}]
        self.name_mapping = {}     # {"081025af": "Madeira 123", ...}
        self.threshold = 10.0
        self.tube_z = None
        self._active_figures = []  # figuras matplotlib abertas no momento
        self._render_after_id = None  # controla o "debounce" do slider (ver on_threshold_change)

        self._build_top_controls()
        self._build_scroll_area()
        self.render_all()

    # ---------- construção da UI ----------

    def _build_top_controls(self):
        frame = ttk.Frame(self, padding=12)
        frame.pack(fill="x")

        ttk.Button(frame, text="1. Carregar amostras (.txt)",
                   command=self.load_samples).grid(row=0, column=0, padx=4, pady=4, sticky="w")
        ttk.Button(frame, text="2. Carregar mapeamento (.csv/.txt)",
                   command=self.load_mapping).grid(row=0, column=1, padx=4, pady=4, sticky="w")
        self.mapping_label = ttk.Label(frame, text="Nenhum mapeamento carregado.")
        self.mapping_label.grid(row=0, column=2, padx=10, sticky="w")

        ttk.Label(frame, text="Tubo de raios X utilizado:").grid(row=1, column=0, sticky="w", pady=(12, 0))
        self.tube_var = tk.StringVar(value="Nenhum")
        tube_combo = ttk.Combobox(frame, textvariable=self.tube_var, values=list(TUBE_OPTIONS.keys()),
                                   state="readonly", width=18)
        tube_combo.grid(row=1, column=1, sticky="w", pady=(12, 0))
        tube_combo.bind("<<ComboboxSelected>>", self.on_tube_change)

        ttk.Label(frame, text="Limite do grupo traço:").grid(row=2, column=0, sticky="w", pady=(12, 0))
        self.threshold_var = tk.DoubleVar(value=10.0)
        slider = ttk.Scale(frame, from_=1, to=50, orient="horizontal",
                            variable=self.threshold_var, command=self.on_threshold_change, length=320)
        slider.grid(row=2, column=1, sticky="w", pady=(12, 0))
        slider.bind("<ButtonRelease-1>", self.on_slider_release)

        self.threshold_entry_var = tk.StringVar(value="10.0")
        threshold_entry = ttk.Spinbox(
            frame, from_=1, to=50, increment=0.5, width=6,
            textvariable=self.threshold_entry_var, command=self.on_threshold_entry_commit,
        )
        threshold_entry.grid(row=2, column=2, sticky="w", pady=(12, 0), padx=(8, 0))
        threshold_entry.bind("<Return>", self.on_threshold_entry_commit)
        threshold_entry.bind("<FocusOut>", self.on_threshold_entry_commit)

        self.threshold_label = ttk.Label(frame, text="10.0%")
        self.threshold_label.grid(row=2, column=3, sticky="w", pady=(12, 0))

    def _build_scroll_area(self):
        """Cria uma área rolável, já que podemos ter muitas amostras
        carregadas de uma vez (processamento em batelada)."""
        container = ttk.Frame(self)
        container.pack(fill="both", expand=True)

        canvas = tk.Canvas(container, borderwidth=0, highlightthickness=0)
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        self.cards_frame = ttk.Frame(canvas)

        self.cards_frame.bind(
            "<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.create_window((0, 0), window=self.cards_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # rolar com a roda do mouse
        canvas.bind_all("<MouseWheel>", lambda e: canvas.yview_scroll(int(-e.delta / 120), "units"))

    # ---------- ações dos botões / controles ----------

    def load_samples(self):
        paths = filedialog.askopenfilenames(
            title="Selecione os arquivos .txt da batelada",
            filetypes=[("Arquivos de texto", "*.txt")],
        )
        if not paths:
            return
        for path in paths:
            try:
                elements = parse_frx_file(path)
            except ValueError as err:
                messagebox.showerror("Erro ao ler arquivo", str(err))
                continue
            code = os.path.splitext(os.path.basename(path))[0]
            self.samples.append({"code": code, "elements": elements})
        self.render_all()

    def load_mapping(self):
        path = filedialog.askopenfilename(
            title="Selecione o arquivo de mapeamento",
            filetypes=[("CSV ou texto", "*.csv *.txt")],
        )
        if not path:
            return
        self.name_mapping = parse_mapping(path)
        self.mapping_label.config(
            text=f"{len(self.name_mapping)} associações carregadas de {os.path.basename(path)}."
        )
        self.render_all()

    def on_tube_change(self, event=None):
        self.tube_z = TUBE_OPTIONS[self.tube_var.get()]
        self.render_all()

    def on_threshold_change(self, value):
        # Isso é chamado a cada pixel que o slider se move, então só
        # atualizamos o texto na hora (é barato). O redesenho pesado dos
        # gráficos (render_all) reconstrói todas as pizzas/tabelas de
        # todas as amostras, então NÃO rola a cada movimento — só quando
        # o usuário solta o botão do mouse (on_slider_release) ou para de
        # arrastar por um tempo (debounce, como rede de segurança para
        # quem usa o teclado/setas).
        self.threshold = float(value)
        self.threshold_label.config(text=f"{self.threshold:.1f}%")
        self.threshold_entry_var.set(f"{self.threshold:.1f}")

        if self._render_after_id is not None:
            self.after_cancel(self._render_after_id)
        self._render_after_id = self.after(400, self._debounced_render)

    def _debounced_render(self):
        self._render_after_id = None
        self.render_all()

    def on_slider_release(self, event=None):
        if self._render_after_id is not None:
            self.after_cancel(self._render_after_id)
            self._render_after_id = None
        self.render_all()

    def on_threshold_entry_commit(self, event=None):
        # Chamado quando o usuário digita um número na caixinha e aperta
        # Enter, sai do campo (Tab/clique fora), ou usa as setinhas do
        # Spinbox. Valida o valor, sincroniza o slider e redesenha na hora.
        raw = self.threshold_entry_var.get().strip().replace(",", ".")
        try:
            value = float(raw)
        except ValueError:
            self.threshold_entry_var.set(f"{self.threshold:.1f}")
            return

        value = max(1.0, min(50.0, value))
        self.threshold_var.set(value)  # sincroniza a posição do slider
        self.threshold = value
        self.threshold_label.config(text=f"{self.threshold:.1f}%")
        self.threshold_entry_var.set(f"{self.threshold:.1f}")

        if self._render_after_id is not None:
            self.after_cancel(self._render_after_id)
            self._render_after_id = None
        self.render_all()

    def remove_sample(self, index):
        del self.samples[index]
        self.render_all()

    def save_figure(self, fig, name):
        path = filedialog.asksaveasfilename(
            defaultextension=".png",
            initialfile=f"{name}.png",
            filetypes=[("Imagem PNG", "*.png")],
        )
        if path:
            fig.savefig(path, dpi=200, bbox_inches="tight")
            messagebox.showinfo("Salvo", f"Imagem salva em:\n{path}")

    # ---------- montagem de nomes ----------

    def display_name_for(self, sample):
        return self.name_mapping.get(sample["code"].lower(), sample["code"])

    # ---------- renderização ----------

    def render_all(self):
        # fecha as figuras matplotlib da renderização anterior, senão
        # elas ficam acumulando na memória a cada mudança de slider
        for fig in self._active_figures:
            plt.close(fig)
        self._active_figures = []

        for widget in self.cards_frame.winfo_children():
            widget.destroy()

        if not self.samples:
            ttk.Label(self.cards_frame, text="Nenhuma amostra carregada ainda.", padding=24).pack()
            return

        for index, sample in enumerate(self.samples):
            self._render_sample_card(sample, index)

    def _render_sample_card(self, sample, index):
        kept, removed = apply_exclusions(sample["elements"], self.tube_z)
        major, trace, total = classify(kept, self.threshold)
        display_name = self.display_name_for(sample)

        card = ttk.Frame(self.cards_frame, relief="groove", borderwidth=1, padding=10)
        card.pack(fill="x", padx=10, pady=8)

        fig = self._build_figure(kept, major, trace, total, display_name)
        self._active_figures.append(fig)

        header = ttk.Frame(card)
        header.pack(fill="x")
        ttk.Label(header, text=display_name, font=("Segoe UI", 12, "bold")).pack(side="left")
        ttk.Label(header, text=f"   arquivo: {sample['code']}", foreground="#6B6250").pack(side="left")
        ttk.Button(header, text="Remover", command=lambda i=index: self.remove_sample(i)).pack(side="right")
        ttk.Button(header, text="Salvar imagem (PNG)",
                   command=lambda f=fig, n=display_name: self.save_figure(f, n)).pack(side="right", padx=6)

        canvas_widget = FigureCanvasTkAgg(fig, master=card)
        canvas_widget.draw()
        canvas_widget.get_tk_widget().pack(fill="x")

        if removed:
            removed_syms = ", ".join(e["symbol"] for e in removed)
            ttk.Label(
                card,
                text=f"Descartado nesta amostra: {removed_syms} (Ar e/ou elemento do tubo — não fazem parte da madeira)",
                foreground="#B8792E",
            ).pack(anchor="w", pady=(4, 0))

        self._build_table(card, major, trace, total)

    def _build_figure(self, elements, major, trace, total, title):
        fig, axes = plt.subplots(1, 3, figsize=(14, 4.4))
        fig.suptitle(title, fontsize=10)

        # ---- gráfico 1: TOTAL (todos os elementos, sem distinção de grupo) ----
        all_sorted = sorted(elements, key=lambda e: -e["area"])
        labels = [e["symbol"] for e in all_sorted]
        sizes = [e["area"] / total * 100 for e in all_sorted]
        colors = [PALETTE[i % len(PALETTE)] for i in range(len(all_sorted))]
        draw_pie_with_leaders(axes[0], sizes, labels, colors)
        axes[0].set_title("Total", fontsize=9)

        # ---- gráfico 2: MAJORITÁRIOS (individuais + fatia "traço" agrupada) ----
        labels = [e["symbol"] for e in major]
        sizes = [e["area"] / total * 100 for e in major]
        colors = [PALETTE[i % len(PALETTE)] for i in range(len(major))]
        if trace:
            trace_sum = sum(e["area"] for e in trace)
            labels.append("Traço")
            sizes.append(trace_sum / total * 100)
            colors.append(TRACE_LUMP_COLOR)
        draw_pie_with_leaders(axes[1], sizes, labels, colors)
        axes[1].set_title("Majoritários", fontsize=9)

        # ---- gráfico 3: TRAÇO renormalizado a 100% ----
        if trace:
            trace_total = sum(e["area"] for e in trace)
            t_labels = [e["symbol"] for e in trace]
            t_sizes = [e["area"] / trace_total * 100 for e in trace]
            t_colors = [PALETTE[i % len(PALETTE)] for i in range(len(trace))]
            draw_pie_with_leaders(axes[2], t_sizes, t_labels, t_colors)
        axes[2].set_title("Traço", fontsize=9)

        fig.tight_layout(w_pad=2.0)
        return fig

    def _build_table(self, parent, major, trace, total):
        columns = ("z", "elemento", "area", "pct", "grupo")
        headers = {"z": "Z", "elemento": "Elemento", "area": "Área (cps)", "pct": "% do total", "grupo": "Grupo"}

        rows = (
            [(e["z"], e["symbol"], f"{e['area']:.0f}", f"{e['area']/total*100:.2f}%", "majoritário") for e in major]
            + [(e["z"], e["symbol"], f"{e['area']:.0f}", f"{e['area']/total*100:.2f}%", "traço") for e in trace]
        )
        rows.sort(key=lambda r: -float(r[2]))

        height = max(1, min(10, len(rows)))
        tree = ttk.Treeview(parent, columns=columns, show="headings", height=height)
        for col in columns:
            tree.heading(col, text=headers[col])
            tree.column(col, width=110, anchor="center")
        for row in rows:
            tree.insert("", "end", values=row)
        tree.pack(fill="x", pady=(8, 0))


if __name__ == "__main__":
    app = App()
    app.mainloop()
