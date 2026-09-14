# -*- coding: utf-8 -*-
"""A oficina: os gráficos de uma batelada desenhados em vários processos.

O gráfico de uma amostra custa uns 300 ms de processador — o cálculo
da posição dos rótulos, a rasterização a 200 dpi, a compressão do
png — e nada disso dá pra encurtar. O que dá é fazer vários ao mesmo
tempo: uma batelada de 60 amostras leva 18 s num núcleo e uns 3 s em
oito. Threads não servem, porque o matplotlib segura o GIL quase o
tempo todo; processos, sim.

    oficina = OficinaDeGraficos()
    futuros = [oficina.pedir_png(kept, maj, tr, total, "M003", "Pizza") ...]
    for futuro in futuros:
        png = futuro.result()

Cada pedido devolve um `Future` do `concurrent.futures`: quem pediu
confere `done()` de vez em quando (a fila da janela faz isso entre um
pedaço e outro) e pega o resultado quando está pronto. Os pedidos são
atendidos na ordem em que chegam.

Os processos só nascem no primeiro pedido — e demoram um segundo ou
dois pra nascer, porque cada um importa o matplotlib. `aquecer` manda
esse trabalho acontecer antes da hora, assim que há amostras na tela,
pra batelada não pagar por ele.

Se os processos não subirem (um Python empacotado sem
`freeze_support`, uma máquina que proíbe), `disponivel` fica False e
quem chamou faz o trabalho no próprio processo — mais devagar, mas
faz.
"""

import os
import threading
from concurrent.futures import ProcessPoolExecutor
from concurrent.futures.process import BrokenProcessPool

# Quantos processos: sobra pelo menos um núcleo pra janela e pro
# resto do sistema; acima de oito o ganho já não paga a memória (cada
# processo com matplotlib são uns 80 MB).
MAXIMO_DE_PROCESSOS = 8


def quantos_processos():
    return max(1, min(MAXIMO_DE_PROCESSOS, (os.cpu_count() or 2) - 2))


# ---------- o que roda DENTRO de cada processo ----------

def _preparar():
    """Importa o matplotlib no processo filho (é o que custa)."""
    import matplotlib
    matplotlib.use("Agg")
    from . import figura  # noqa: F401  (só pra carregar)
    return True


def _png(args):
    from .figura import png_da_figura
    return png_da_figura(*args)


def _pixels(args):
    from .figura import pixels_da_figura
    return pixels_da_figura(*args)


def _espectro(args):
    from .espectro import png_do_espectro
    return png_do_espectro(*args)


# ---------- o lado de cá ----------

class OficinaDeGraficos:
    def __init__(self, processos=None):
        self.processos = processos or quantos_processos()
        self._pool = None
        self._tranca = threading.Lock()
        self._aquecida = False
        self.disponivel = True   # vira False se os processos não subirem

    def _obter(self):
        with self._tranca:
            if self._pool is None and self.disponivel:
                try:
                    self._pool = ProcessPoolExecutor(max_workers=self.processos)
                except (OSError, ValueError, RuntimeError):
                    self.disponivel = False
            return self._pool

    def aquecer(self):
        """Faz os processos nascerem e importarem o matplotlib agora, pra
        estarem prontos quando a batelada vier.

        Numa thread, e não aqui: o `submit` que faz um processo nascer
        é uma chamada de sistema de uns 15 ms, e oito delas seguidas
        na thread da janela eram um engasgo de 140 ms bem na hora em
        que os cartões estão sendo desenhados.
        """
        if self._aquecida or not self.disponivel:
            return
        self._aquecida = True
        threading.Thread(target=self._aquecer, daemon=True).start()

    def _aquecer(self):
        pool = self._obter()
        if pool is None:
            return
        try:
            for _ in range(self.processos):
                pool.submit(_preparar)
        except (BrokenProcessPool, RuntimeError):
            self._quebrou()

    def pedir_png(self, kept, major, trace, total, nome, tipo):
        """Um pedido: os bytes do .png da amostra. Devolve um Future, ou
        None se a oficina não está disponível."""
        return self._pedir(_png, (kept, major, trace, total, nome, tipo))

    def pedir_pixels(self, kept, major, trace, total, nome, tipo):
        """Idem, mas os pixels da figura da tela (pra imagem compilada)."""
        return self._pedir(_pixels, (kept, major, trace, total, nome, tipo))

    def pedir_espectro(self, contagens, energias, titulo, marcas, calibrado, tempo_vivo,
                       escala="log"):
        """Idem, mas o desenho de um espectro (.mca)."""
        return self._pedir(_espectro, (contagens, energias, titulo, marcas,
                                       calibrado, tempo_vivo, escala))

    def _pedir(self, funcao, args):
        pool = self._obter()
        if pool is None:
            return None
        try:
            return pool.submit(funcao, args)
        except (BrokenProcessPool, RuntimeError):
            self._quebrou()
            return None

    def _quebrou(self):
        """Um processo morreu (ou nem nasceu): a oficina fecha e quem
        chamou passa a trabalhar no próprio processo."""
        self.disponivel = False
        self.fechar()

    def fechar(self):
        with self._tranca:
            pool, self._pool = self._pool, None
        if pool is not None:
            pool.shutdown(wait=False, cancel_futures=True)
