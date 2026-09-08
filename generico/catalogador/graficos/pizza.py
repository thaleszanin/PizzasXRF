"""Desenho de uma pizza com rótulos externos e linhas guia.

Este módulo é só o algoritmo de posicionamento dos rótulos — a parte
mais delicada do programa. Ele não escolhe backend do matplotlib nem
sabe o que é uma amostra: recebe um `ax` pronto e valores em %.

O resultado: os rótulos (nome + %) ficam sempre do lado de fora,
ligados à própria fatia por uma linha guia fina, e TODOS à mesma
distância do centro (sem exceção).

O texto e a linha guia são desenhados como dois elementos SEPARADOS
(`ax.text` + `Line2D`) — não com `ax.annotate`, cuja caixa delimitadora
inclui a seta inteira e não só o texto, o que torna qualquer medida de
sobreposição sem sentido. Com o texto isolado, medimos a caixa *real*
dele (em pixels, já considerando fonte/DPI de verdade) e:

1. Agrupamos em "blocos" só os rótulos vizinhos que colidiriam na
   posição natural deles (mais um passo de absorção: um bloco, ao
   crescer, pode "engolir" o espaço de um vizinho que originalmente
   não colidia — sem isso ele ficaria espremido fora da ordem).
2. Um bloco com mais de 2 rótulos é dividido nos dois lados da pizza:
   a metade mais ambígua (mais perto do topo/base, com X natural
   pequeno) vai pro lado com menos membros; a metade que já é
   claramente de um lado fica onde está. Isso reduz pela metade a
   altura que cada lado precisa, deixando o bloco mais compacto — os
   desvios podem ir tanto pra direita quanto pra esquerda, não só no
   sentido horário.
3. Cada metade é redistribuída em Y, simetricamente, em torno do
   próprio centro natural — e, se a pilha ultrapassar o topo/base do
   círculo dos rótulos, o bloco DESLIZA pra dentro dessa faixa (em
   direção ao "equador" da pizza, onde sobra espaço vertical) em vez
   de crescer pra fora. Sem isso, um punhado de fatias minúsculas no
   topo empurrava o raio comum do passo 4 pra longe e afastava TODOS
   os rótulos da pizza junto.
4. Por fim, um raio ÚNICO é calculado — o maior que qualquer lado de
   qualquer bloco precisar — e TODOS os rótulos (mesmo os isolados,
   tipo fatias grandes que não colidem com nada) são projetados nesse
   MESMO raio, mantendo o Y já calculado. Assim toda a pizza tem uma
   "auréola" de rótulos a distância igual do centro, sem exceção, e
   nenhum fica desnecessariamente mais longe que o mínimo que os
   blocos mais cheios exigem.
5. Empurramos cada rótulo horizontalmente (nunca no eixo vertical, que
   é o que garante a separação entre eles) o mínimo necessário pra ele
   nunca ficar por cima da pizza.
6. Uma rede de segurança final, na ORDEM NATURAL das fatias (nunca
   reordenada pela posição já ajustada — isso inverteria a ordem de
   leitura dos rótulos), compara cada rótulo contra TODOS os já
   posicionados antes dele (não só o anterior na lista).
7. Reaplica o passo 5, já que o passo 6 pode ter mexido no Y de novo.
8. Por fim, expande os limites do gráfico se algum rótulo tiver sido
   empurrado pra além da margem padrão — senão ele pode ficar cortado
   fora da figura.
"""

import math

from matplotlib.lines import Line2D

from .estilo import LABEL_FONTSIZE, formatar_pct
from .medicao import escala, renderer_para_medir

# Eixo em que uma pizza é desenhada quando ninguém impõe outro tamanho.
LIMITES_PADRAO = (-1.9, 1.9, -1.5, 1.5)
# Distância (em unidades de dado) do centro até o anel dos rótulos.
RAIO_DOS_ROTULOS = 1.15
# Quantas vezes, no máximo, a checagem de sobreposição roda (passos 6 e 7).
CICLOS_DE_SEGURANCA = 3
# Cor da linha fina que liga cada rótulo à fatia dele.
COR_DA_LINHA_GUIA = "#6B6250"


class RotulosDaPizza:
    """Os rótulos de uma pizza, com o algoritmo que os posiciona.

    Existir como objeto é o que permite POSICIONAR DE NOVO, com outros
    limites de eixo: é assim que `graficos/figura.py` deixa as três
    pizzas de uma amostra exatamente do mesmo tamanho.
    """

    def __init__(self, ax, texts, anchors, radius):
        self.ax = ax
        self.texts = texts
        self.anchors = anchors
        self.radius = radius
        # a posição natural de cada rótulo (na ponta da própria fatia):
        # toda rodada de posicionamento começa daqui, senão a segunda
        # rodada partiria do resultado da primeira
        self._natural = [(t.get_position(), t.get_ha()) for t in texts]
        self._linhas = []

    def _resetar(self):
        for texto, (pos, ha) in zip(self.texts, self._natural):
            texto.set_position(pos)
            texto.set_ha(ha)
        for linha in self._linhas:
            linha.remove()
        self._linhas = []

    def posicionar(self, limites=None):
        """Posiciona os rótulos e desenha as linhas guia.

        `limites` é a tupla (esquerda, direita, baixo, cima) do eixo. Sem
        ela, o eixo cresce só o necessário — o comportamento de sempre.
        Com ela, o eixo fica exatamente com esses limites.

        Devolve, sempre, os limites de que os rótulos PRECISARIAM. O
        algoritmo em si está descrito no cabeçalho deste módulo.
        """
        self._resetar()
        ax = self.ax
        fig = ax.figure
        radius = self.radius
        texts, anchors = self.texts, self.anchors
        label_radius = RAIO_DOS_ROTULOS

        base = LIMITES_PADRAO if limites is None else limites
        ax.set_xlim(base[0], base[1])
        ax.set_ylim(base[2], base[3])


        # `ax.pie` deixa o eixo com aspecto "equal": é o `apply_aspect()` que
        # ajusta a caixa do eixo pra isso valer — normalmente ele roda dentro
        # do desenho, e aqui chamamos direto pra ter as coordenadas finais
        # sem pagar por um desenho completo da figura.
        ax.apply_aspect()
        renderer = renderer_para_medir(fig)
        sx, tx, sy, ty = escala(ax)

        def measure(t):
            bb = t.get_window_extent(renderer)
            data_x, _ = t.get_position()
            return data_x, bb.x0, bb.x1, bb.y1 - bb.y0, (bb.y0 + bb.y1) / 2

        def py_to_data_y(py):
            return (py - ty) / sy

        def data_y_to_py(dy):
            return sy * dy + ty

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

        band_limit = label_radius - 0.03

        def cabe_de_um_lado(cluster):
            """O bloco caberia inteiro no lado pra onde as fatias dele já
            apontam? Se couber, dividir só afasta rótulo da própria fatia.

            A conta é a altura que a pilha precisa contra a altura que
            sobra naquele lado — a faixa vertical dos rótulos menos o que
            os rótulos de fora do bloco já ocupam desse mesmo lado.
            """
            n = len(cluster)
            n_right = sum(1 for it in cluster if it["data_x"] >= 0)
            lado_maioria = 1 if n_right * 2 >= n else -1

            padding = sum(it["height"] for it in cluster) / n * 0.1
            preciso = sum(it["height"] for it in cluster) + padding * (n - 1)

            faixa = abs(data_y_to_py(band_limit) - data_y_to_py(-band_limit))
            no_bloco = {id(it) for it in cluster}
            ocupado = sum(
                it["height"] * 1.2 for it in items
                if id(it) not in no_bloco
                and (1 if it["data_x"] >= 0 else -1) == lado_maioria
            )
            return preciso <= faixa - ocupado

        # 2) divide cada bloco grande entre os dois lados da pizza: a
        #    metade mais ambígua (mais perto do topo/base) vai pro lado com
        #    menos membros; a metade claramente de um lado fica onde está.
        #    Só que dividir tem um custo — o rótulo vai parar do lado oposto
        #    ao da própria fatia, e a linha guia cruza a pizza inteira. Então
        #    só dividimos quando o bloco REALMENTE não cabe de um lado só.
        needs_redraw = False
        for cluster in clusters:
            n = len(cluster)
            if n <= 2:
                continue
            if cabe_de_um_lado(cluster):
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
            # o texto trocou de lado: basta remedir a caixa dele — o
            # `get_window_extent` recalcula na hora, sem redesenhar
            for it in items:
                it["data_x"], it["x0"], it["x1"], it["height"], it["y"] = measure(it["text"])

        min_radius = radius * 1.08

        def push_out_of_pie(it):
            data_y = py_to_data_y(it["y"])
            min_abs_x = math.sqrt(max(0.0, min_radius ** 2 - data_y ** 2))
            if abs(it["data_x"]) < min_abs_x:
                sign = 1.0 if it["data_x"] >= 0 else -1.0
                new_data_x = sign * min_abs_x
                delta = sx * (new_data_x - it["data_x"])
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
                uniform_radius = max(uniform_radius, abs(py_to_data_y(it["y"])) + 0.03)

            for it in items:
                data_y = py_to_data_y(it["y"])
                data_x_mag = math.sqrt(max(0.0, uniform_radius ** 2 - data_y ** 2))
                sign = 1.0 if it["data_x"] >= 0 else -1.0
                new_data_x = sign * data_x_mag
                delta = sx * (new_data_x - it["data_x"])
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
            # 7) o passo 6 mexe no Y, então o passo 5 é reaplicado — e como
            #    ele mexe no X, dois rótulos que não se cruzavam podem passar
            #    a se cruzar. Por isso os dois passos rodam em ciclo, até
            #    ninguém mais precisar sair do lugar. Só desce, nunca sobe,
            #    então o ciclo sempre para.
            for _ in range(CICLOS_DE_SEGURANCA):
                mexeu = False
                placed = []
                for it in items:
                    limit = it["y"]
                    for p in placed:
                        if it["x0"] < p["x1"] and it["x1"] > p["x0"]:
                            min_gap = (p["height"] + it["height"]) / 2 * 1.2
                            limit = min(limit, p["y"] - min_gap)
                    if limit != it["y"]:
                        it["y"] = limit
                        mexeu = True
                    placed.append(it)

                for it in items:
                    push_out_of_pie(it)

                if not mexeu:
                    break

            return uniform_radius

        def leader_cuts_pie():
            """A linha guia é uma reta da fatia até o rótulo. Ela só passa
            por fora da pizza se, saindo da fatia, apontar pra fora — ou
            seja, se (rótulo - fatia) · fatia >= 0. Quanto mais o rótulo se
            afasta angularmente da própria fatia, mais essa reta vira uma
            corda que corta o miolo; é isso que limita o quanto os blocos
            podem deslizar pra perto da pizza."""
            for it in items:
                data_y = py_to_data_y(it["y"])
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
            new_x, new_y = it["data_x"], py_to_data_y(it["y"])
            it["text"].set_position((new_x, new_y))
            data_ys.append(new_y)
            linha = Line2D(
                [it["anchor"][0], new_x], [it["anchor"][1], new_y],
                color=COR_DA_LINHA_GUIA, linewidth=0.6, zorder=1,
            )
            ax.add_line(linha)
            self._linhas.append(linha)

        # De quanto o eixo precisa pra caber tudo. Sem limites impostos, a
        # pizza se acomoda no menor eixo que couber (o de sempre); com
        # limites impostos, quem manda são eles — e o valor calculado aqui
        # volta como resposta, pra quem estiver procurando um eixo que sirva
        # às três pizzas da amostra.
        bottom, top = ax.get_ylim()
        if data_ys:
            margin = 0.18
            bottom = min(bottom, min(data_ys) - margin)
            top = max(top, max(data_ys) + margin)
        if limites is None:
            ax.set_ylim(bottom, top)

        # E o mesmo no eixo X: como o rótulo cresce pra fora (pra direita nos
        # do lado direito, pra esquerda nos do outro), uma fonte maior pode
        # jogar a ponta do texto pra além da margem padrão e cortá-lo. Aqui
        # medimos a caixa REAL de cada texto já na posição final e abrimos o
        # eixo o quanto for preciso.
        # o `set_ylim` acima mudou a caixa do eixo (aspecto "equal"), então
        # a conversão dados <-> pixels precisa ser recalculada antes de medir
        ax.apply_aspect()
        sx, tx, sy, ty = escala(ax)
        left, right = ax.get_xlim()
        for it in items:
            bb = it["text"].get_window_extent(renderer)
            x0 = (bb.x0 - tx) / sx
            x1 = (bb.x1 - tx) / sx
            left = min(left, x0 - 0.08)
            right = max(right, x1 + 0.08)
        if limites is None:
            ax.set_xlim(left, right)

        return left, right, bottom, top


def _criar_pizza(ax, sizes, labels, colors, radius, buraco=0.0):
    """Desenha as fatias e cria os rótulos na posição natural de cada
    uma (na ponta da própria fatia). Ninguém foi posicionado ainda.

    `buraco` é a fração do raio que fica vazia no meio (0 = pizza
    cheia, 0.45 = rosca). O anel dos rótulos não muda: eles continuam
    pendurados na BORDA DE FORA, que é onde a linha guia começa.
    """
    if not sizes:
        return None

    fatias = dict(edgecolor="white", linewidth=0.6)
    if buraco > 0:
        fatias["width"] = radius * (1.0 - buraco)
    wedges, _ = ax.pie(
        sizes, colors=colors, startangle=90, radius=radius,
        wedgeprops=fatias,
    )

    label_radius = RAIO_DOS_ROTULOS
    texts, anchors = [], []
    for wedge, label, size in zip(wedges, labels, sizes):
        mid_angle = math.radians((wedge.theta1 + wedge.theta2) / 2)
        x, y = math.cos(mid_angle), math.sin(mid_angle)
        ha = "left" if x >= 0 else "right"
        t = ax.text(
            x * label_radius, y * label_radius, "%s %s" % (label, formatar_pct(size)),
            fontsize=LABEL_FONTSIZE, ha=ha, va="center",
        )
        texts.append(t)
        anchors.append((x * radius, y * radius))

    return RotulosDaPizza(ax, texts, anchors, radius)


def passos_da_pizza(ax, sizes, labels, colors, radius=1.0, buraco=0.0):
    """Desenha a pizza em dois pedaços: primeiro as fatias e a criação
    dos rótulos, depois o POSICIONAMENTO deles (que é a parte cara), com
    um `yield` no meio. Devolve o `RotulosDaPizza` no fim.

    Partir em dois é o que deixa a interface desenhar sem travar; veja
    `passos_do_desenho` em `graficos/figura.py`.

    Com `buraco` > 0 sai uma ROSCA em vez de uma pizza — o resto
    (rótulos, linhas guia, tamanho comum entre os três gráficos) é
    exatamente o mesmo.
    """
    rotulos = _criar_pizza(ax, sizes, labels, colors, radius, buraco)
    yield
    if rotulos is not None:
        rotulos.posicionar()
    return rotulos
