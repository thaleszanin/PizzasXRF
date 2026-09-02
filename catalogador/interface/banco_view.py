# -*- coding: utf-8 -*-
"""A janela do banco de amostras: a árvore de pastas e o que mora nelas.

É uma janela separada, que fica de lado da janela principal — abrir o
banco não atrapalha os gráficos que já estão na tela, e dá para ir
arrastando amostras de uma pasta para outra enquanto o catalogador
continua mostrando o que estava mostrando.

O que dá para fazer aqui
------------------------
  * criar, renomear, mover, reordenar e apagar pastas e subpastas, em
    qualquer profundidade (madeira > in natura > pó, carne > cinza, ...);
  * importar .txt do FRX direto para dentro de uma pasta;
  * guardar no banco as amostras que já estão abertas no catalogador;
  * carregar amostras (ou uma pasta inteira, com as subpastas) de volta
    para o catalogador;
  * arrastar e soltar para mover — tanto pasta quanto amostra.

Sobre desempenho
----------------
A árvore é carregada por NÍVEL, e só nos níveis que o usuário abriu: uma
consulta por pasta expandida (`filhas_com_resumo`), nunca a árvore
inteira. Um banco com milhares de amostras abre na mesma velocidade que
um vazio, porque as amostras de uma pasta só são lidas quando ela é
aberta.
"""

import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog

from ..banco import (BancoDeAmostras, ErroDoBanco, RAIZ_ID, RAIZ_NOME,
                     caminho_padrao, lembrar_caminho)
from ..nucleo.classificacao import TUBE_OPTIONS
from ..nucleo.leitura import parse_frx_file

# Prefixos dos identificadores dos itens da árvore. O Tk exige um id de
# texto por item; usar "p:12" / "a:34" deixa óbvio, em qualquer ponto do
# código, se o item selecionado é uma pasta ou uma amostra.
PASTA, AMOSTRA, ESPERA = "p:", "a:", "carregando:"

COR_AMOSTRA = "#3A5A8C"
COR_APAGADO = "#9A927F"


def _id_da_pasta(item):
    return int(item[len(PASTA):]) if item.startswith(PASTA) else None


def _id_da_amostra(item):
    return int(item[len(AMOSTRA):]) if item.startswith(AMOSTRA) else None


class BancoView(tk.Toplevel):
    """A janela. Recebe o `App` para poder mandar amostras para a tela e
    pegar de volta as que já estão abertas nela."""

    def __init__(self, app, banco):
        super().__init__(app)
        self.app = app
        self.banco = banco
        self.title("Banco de amostras")
        self.geometry("820x640")
        self.minsize(620, 420)

        self._numero = {}      # item da árvore -> "1.1.2"
        self._arrasto = None   # o item que está sendo arrastado

        self._montar()
        self.recarregar_tudo()
        self.protocol("WM_DELETE_WINDOW", self.fechar)

    # ============================================================
    # Montagem da janela
    # ============================================================

    def _montar(self):
        topo = ttk.Frame(self, padding=(10, 8, 10, 4))
        topo.pack(fill="x")
        ttk.Label(topo, text="Banco:").pack(side="left")
        self.caminho_label = ttk.Label(topo, foreground="#6B6250")
        self.caminho_label.pack(side="left", padx=(4, 0))
        ttk.Button(topo, text="Abrir outro…", command=self.abrir_outro).pack(side="right")
        ttk.Button(topo, text="Novo banco…", command=self.criar_outro).pack(side="right", padx=6)

        busca = ttk.Frame(self, padding=(10, 0, 10, 6))
        busca.pack(fill="x")
        ttk.Label(busca, text="Procurar amostra:").pack(side="left")
        self.busca_var = tk.StringVar()
        entrada = ttk.Entry(busca, textvariable=self.busca_var, width=28)
        entrada.pack(side="left", padx=6)
        entrada.bind("<Return>", lambda _e: self.procurar())
        ttk.Button(busca, text="Buscar", command=self.procurar).pack(side="left")
        ttk.Button(busca, text="Limpar", command=self.limpar_busca).pack(side="left", padx=6)

        corpo = ttk.Frame(self, padding=(10, 0))
        corpo.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(corpo, columns=("detalhe",), selectmode="extended")
        self.tree.heading("#0", text="Pastas e amostras", anchor="w")
        self.tree.heading("detalhe", text="", anchor="w")
        self.tree.column("#0", width=430, stretch=True)
        self.tree.column("detalhe", width=300, stretch=True, anchor="w")
        self.tree.tag_configure("amostra", foreground=COR_AMOSTRA)
        self.tree.tag_configure("vazio", foreground=COR_APAGADO)

        barra = ttk.Scrollbar(corpo, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=barra.set)
        self.tree.pack(side="left", fill="both", expand=True)
        barra.pack(side="right", fill="y")

        self.tree.bind("<<TreeviewOpen>>", self._ao_abrir)
        self.tree.bind("<<TreeviewSelect>>", self._ao_selecionar)
        self.tree.bind("<Double-1>", self._ao_dar_dois_cliques)
        # arrastar e soltar: o Tk não traz isso pronto, então marcamos de
        # onde o arrasto saiu e, ao soltar, olhamos em cima de quem parou
        self.tree.bind("<ButtonPress-1>", self._arrasto_comeca, add="+")
        self.tree.bind("<B1-Motion>", self._arrasto_anda, add="+")
        self.tree.bind("<ButtonRelease-1>", self._arrasto_termina, add="+")

        self._montar_botoes()

        self.status = ttk.Label(self, padding=(10, 4, 10, 8), foreground="#6B6250")
        self.status.pack(fill="x")

    def _montar_botoes(self):
        pastas = ttk.Frame(self, padding=(10, 8, 10, 0))
        pastas.pack(fill="x")
        ttk.Label(pastas, text="Pasta:").pack(side="left", padx=(0, 6))
        for texto, acao in (("Nova aqui dentro", self.nova_subpasta),
                            ("Renomear", self.renomear),
                            ("Excluir", self.excluir),
                            ("↑", lambda: self.reordenar(-1)),
                            ("↓", lambda: self.reordenar(1))):
            largura = {"↑": 3, "↓": 3}.get(texto)
            ttk.Button(pastas, text=texto, command=acao,
                       **({"width": largura} if largura else {})).pack(side="left", padx=3)

        amostras = ttk.Frame(self, padding=(10, 6, 10, 0))
        amostras.pack(fill="x")
        ttk.Label(amostras, text="Amostras:").pack(side="left", padx=(0, 6))
        ttk.Button(amostras, text="Importar .txt para esta pasta",
                   command=self.importar_txt).pack(side="left", padx=3)
        ttk.Button(amostras, text="Guardar as que estão na tela",
                   command=self.guardar_da_tela).pack(side="left", padx=3)
        ttk.Button(amostras, text="Carregar no catalogador",
                   command=self.carregar_no_catalogador).pack(side="left", padx=3)

    # ============================================================
    # Desenho da árvore
    # ============================================================

    def recarregar_tudo(self, abrir=()):
        """Refaz a árvore do zero, reabrindo os caminhos pedidos."""
        self.caminho_label.config(text=self.banco.caminho)
        self.tree.delete(*self.tree.get_children(""))
        self._numero.clear()
        raiz = PASTA + str(RAIZ_ID)
        self.tree.insert("", "end", iid=raiz, text=RAIZ_NOME, open=True,
                         values=("",))
        self._numero[raiz] = ""
        self._carregar_filhos(raiz)
        for item in abrir:
            self._abrir_ate(item)
        self._atualizar_status()

    def _carregar_filhos(self, item_pai):
        """Põe na tela as subpastas e as amostras de uma pasta.

        Cada subpasta que tenha conteúdo ganha um filho de mentira, só
        para o Tk desenhar a setinha de expandir — o conteúdo de verdade
        só é lido quando ela for aberta.
        """
        self.tree.delete(*self.tree.get_children(item_pai))
        pasta_id = _id_da_pasta(item_pai)
        prefixo = self._numero.get(item_pai, "")

        for indice, filha in enumerate(self.banco.filhas_com_resumo(pasta_id), 1):
            numero = "%s%d" % (prefixo + "." if prefixo else "", indice)
            item = PASTA + str(filha["id"])
            detalhe = ("%d amostra(s)" % filha["n_amostras"]) if filha["n_amostras"] else ""
            self.tree.insert(item_pai, "end", iid=item,
                             text="%s>  %s" % (numero, filha["nome"]),
                             values=(detalhe,))
            self._numero[item] = numero
            if filha["n_subpastas"] or filha["n_amostras"]:
                self.tree.insert(item, "end", iid=ESPERA + item, text="…")

        for amostra in self.banco.amostras(pasta_id):
            self._inserir_amostra(item_pai, amostra)

    def _inserir_amostra(self, item_pai, amostra):
        detalhes = [amostra["codigo"], amostra["tubo"], amostra["criado_em"][:10]]
        self.tree.insert(item_pai, "end", iid=AMOSTRA + str(amostra["id"]),
                         text="    " + amostra["nome"], tags=("amostra",),
                         values=(" · ".join(d for d in detalhes if d),))

    def _ao_abrir(self, _evento=None):
        item = self.tree.focus()
        filhos = self.tree.get_children(item)
        if len(filhos) == 1 and filhos[0].startswith(ESPERA):
            self._carregar_filhos(item)

    def _recarregar_pasta(self, pasta_id):
        """Refaz só o conteúdo de uma pasta (e reabre o caminho até ela),
        em vez de redesenhar a árvore inteira."""
        item = PASTA + str(pasta_id)
        if not self.tree.exists(item):
            self.recarregar_tudo()
            return
        self._abrir_ate(item)
        self._carregar_filhos(item)
        self.tree.item(item, open=True)
        self._atualizar_status()

    def _abrir_ate(self, item):
        """Deixa um item visível, carregando os níveis que faltarem.

        Não dá para subir pela árvore do Tk aqui: o item pode nem existir
        nela ainda, porque as pastas acima dele nunca foram abertas (e o
        que está fechado não foi lido). Quem sabe o caminho é o banco.
        """
        if item.startswith(PASTA):
            pasta_id = _id_da_pasta(item)
        elif item.startswith(AMOSTRA):
            try:
                pasta_id = self.banco.amostra(_id_da_amostra(item))["pasta_id"]
            except ErroDoBanco:
                return
        else:
            return  # item de resultado de busca: não tem caminho na árvore

        for pasta in self.banco.ancestrais(pasta_id):
            no = PASTA + str(pasta)
            if not self.tree.exists(no):
                return  # a árvore na tela está velha; quem chamou recarrega
            filhos = self.tree.get_children(no)
            if len(filhos) == 1 and filhos[0].startswith(ESPERA):
                self._carregar_filhos(no)
            self.tree.item(no, open=True)
        if self.tree.exists(item):
            self.tree.see(item)

    # ============================================================
    # Seleção
    # ============================================================

    def _selecao(self):
        return list(self.tree.selection())

    def _pasta_selecionada(self, exigir=True):
        """A pasta em que a ação deve acontecer.

        Com uma amostra selecionada, vale a pasta em que ela está — é o
        que a pessoa espera ao clicar numa amostra e pedir "importar
        aqui".
        """
        for item in self._selecao():
            if item.startswith(PASTA):
                return _id_da_pasta(item)
            pai = self.tree.parent(item)
            if pai.startswith(PASTA):
                return _id_da_pasta(pai)
        if exigir:
            messagebox.showinfo("Escolha uma pasta",
                                "Clique antes na pasta onde a ação deve acontecer.",
                                parent=self)
        return None

    def _amostras_selecionadas(self):
        """Os ids das amostras escolhidas. Pasta selecionada conta como
        TODAS as amostras dela e das subpastas."""
        ids, vistas = [], set()
        for item in self._selecao():
            if item.startswith(AMOSTRA):
                escolhidas = [_id_da_amostra(item)]
            else:
                escolhidas = [a["id"] for a in
                              self.banco.amostras(_id_da_pasta(item), recursivo=True)]
            for amostra_id in escolhidas:
                if amostra_id not in vistas:
                    vistas.add(amostra_id)
                    ids.append(amostra_id)
        return ids

    def _ao_selecionar(self, _evento=None):
        self._atualizar_status()

    def _atualizar_status(self):
        selecao = self._selecao()
        if len(selecao) == 1 and selecao[0].startswith(PASTA):
            pasta_id = _id_da_pasta(selecao[0])
            subpastas, amostras = self.banco.resumo(pasta_id)
            self.status.config(text="%s — %d subpasta(s), %d amostra(s) no total"
                               % (self.banco.caminho_da_pasta(pasta_id),
                                  subpastas, amostras))
            return
        if len(selecao) == 1 and selecao[0].startswith(AMOSTRA):
            amostra = self.banco.amostra(_id_da_amostra(selecao[0]))
            texto = "%s — %s" % (self.banco.caminho_da_pasta(amostra["pasta_id"]),
                                 amostra["nome"])
            if amostra["observacoes"]:
                texto += " · " + amostra["observacoes"]
            self.status.config(text=texto)
            return
        if len(selecao) > 1:
            self.status.config(text="%d itens selecionados" % len(selecao))
            return
        self.status.config(text="%d amostra(s) no banco"
                           % self.banco.total_de_amostras())

    # ============================================================
    # Ações de pasta
    # ============================================================

    def nova_subpasta(self):
        pasta_id = self._pasta_selecionada()
        if pasta_id is None:
            return
        nome = simpledialog.askstring(
            "Nova pasta",
            "Nome da pasta dentro de \"%s\":" % self.banco.caminho_da_pasta(pasta_id),
            parent=self)
        if not nome:
            return
        if self._tentar(self.banco.criar_pasta, pasta_id, nome) is not False:
            self._recarregar_pasta(pasta_id)

    def renomear(self):
        selecao = self._selecao()
        if len(selecao) != 1:
            messagebox.showinfo("Escolha um item",
                                "Selecione uma pasta ou uma amostra para renomear.",
                                parent=self)
            return
        item = selecao[0]
        if item.startswith(PASTA):
            pasta_id = _id_da_pasta(item)
            atual = self.banco.pasta(pasta_id)["nome"]
            novo = simpledialog.askstring("Renomear pasta", "Novo nome:",
                                          initialvalue=atual, parent=self)
            if novo and self._tentar(self.banco.renomear_pasta, pasta_id, novo) is not False:
                pai = self.tree.parent(item)
                self._recarregar_pasta(_id_da_pasta(pai))
        else:
            self.editar_amostra(_id_da_amostra(item))

    def excluir(self):
        selecao = self._selecao()
        if not selecao:
            return
        pastas = [_id_da_pasta(i) for i in selecao if i.startswith(PASTA)]
        amostras = [_id_da_amostra(i) for i in selecao if i.startswith(AMOSTRA)]

        for pasta_id in pastas:
            try:
                self.banco.pasta(pasta_id)
            except ErroDoBanco:
                continue  # já sumiu junto com uma pasta acima dela
            subpastas, quantas = self.banco.resumo(pasta_id)
            caminho = self.banco.caminho_da_pasta(pasta_id)
            if quantas or subpastas:
                if not messagebox.askyesno(
                        "Excluir pasta",
                        "\"%s\" tem %d subpasta(s) e %d amostra(s).\n\n"
                        "Excluir a pasta apaga TUDO isso do banco, e não dá "
                        "para desfazer.\n\nQuer excluir mesmo assim?"
                        % (caminho, subpastas, quantas), parent=self):
                    continue
            elif not messagebox.askyesno("Excluir pasta",
                                         "Excluir a pasta \"%s\"?" % caminho,
                                         parent=self):
                continue
            self._tentar(self.banco.excluir_pasta, pasta_id, True)

        if amostras and messagebox.askyesno(
                "Excluir amostras",
                "Excluir %d amostra(s) do banco? Não dá para desfazer."
                % len(amostras), parent=self):
            for amostra_id in amostras:
                self.banco.excluir_amostra(amostra_id)

        # apagar mexe em pai e filhos ao mesmo tempo (uma pasta some com
        # a sub-árvore inteira): mais seguro refazer a árvore do que
        # remendar item por item
        self.recarregar_tudo()

    def reordenar(self, direcao):
        selecao = self._selecao()
        if len(selecao) != 1 or not selecao[0].startswith(PASTA):
            messagebox.showinfo("Escolha uma pasta",
                                "Selecione UMA pasta para mudar a posição dela.",
                                parent=self)
            return
        pasta_id = _id_da_pasta(selecao[0])
        if pasta_id == RAIZ_ID:
            return
        if self.banco.trocar_ordem(pasta_id, direcao):
            pai = self.tree.parent(selecao[0])
            self._carregar_filhos(pai)
            self.tree.selection_set(selecao[0])
            self.tree.see(selecao[0])

    # ============================================================
    # Ações de amostra
    # ============================================================

    def importar_txt(self):
        pasta_id = self._pasta_selecionada()
        if pasta_id is None:
            return
        caminhos = filedialog.askopenfilenames(
            title="Arquivos .txt do FRX para guardar em \"%s\""
                  % self.banco.caminho_da_pasta(pasta_id),
            filetypes=[("Arquivos de texto", "*.txt")], parent=self)
        if not caminhos:
            return

        tubo = self.app.tube_var.get()
        novas = repetidas = 0
        problemas = []
        for caminho in caminhos:
            codigo = os.path.splitext(os.path.basename(caminho))[0]
            try:
                elementos = parse_frx_file(caminho)
                _, entrou = self.banco.adicionar_amostra(
                    pasta_id, self.app.display_name_for({"code": codigo}),
                    elementos, codigo=codigo, tubo=tubo, origem=caminho)
            except (ValueError, ErroDoBanco, OSError) as erro:
                problemas.append("%s: %s" % (codigo, erro))
                continue
            novas += entrou
            repetidas += not entrou

        self._recarregar_pasta(pasta_id)
        self._avisar_importacao(novas, repetidas, problemas)

    def guardar_da_tela(self):
        """Guarda no banco as amostras que já estão abertas no catalogador."""
        pasta_id = self._pasta_selecionada()
        if pasta_id is None:
            return
        if not self.app.samples:
            messagebox.showinfo("Nada para guardar",
                                "Não há amostras abertas no catalogador.",
                                parent=self)
            return
        novas = repetidas = 0
        problemas = []
        for sample in self.app.samples:
            try:
                _, entrou = self.banco.adicionar_amostra(
                    pasta_id, self.app.display_name_for(sample), sample["elements"],
                    codigo=sample.get("code", ""),
                    tubo=sample.get("tubo") or self.app.tube_var.get())
            except ErroDoBanco as erro:
                problemas.append(str(erro))
                continue
            novas += entrou
            repetidas += not entrou
        self._recarregar_pasta(pasta_id)
        self._avisar_importacao(novas, repetidas, problemas)

    def _avisar_importacao(self, novas, repetidas, problemas):
        partes = ["%d amostra(s) guardada(s)." % novas]
        if repetidas:
            partes.append("%d já estavam no banco (medida idêntica) e foram "
                          "ignoradas." % repetidas)
        if problemas:
            partes.append("Não deu para ler:\n" + "\n".join(problemas[:10]))
        messagebox.showinfo("Banco de amostras", "\n\n".join(partes), parent=self)

    def carregar_no_catalogador(self):
        ids = self._amostras_selecionadas()
        if not ids:
            messagebox.showinfo("Nada selecionado",
                                "Escolha amostras (ou uma pasta inteira) para "
                                "abrir no catalogador.", parent=self)
            return
        carregadas = []
        for amostra_id in ids:
            amostra = self.banco.amostra(amostra_id)
            carregadas.append({
                "code": amostra["codigo"] or ("#%d" % amostra_id),
                "elements": self.banco.elementos(amostra_id),
                "nome": amostra["nome"],
                "tubo": amostra["tubo"],
                "pasta": self.banco.caminho_da_pasta(amostra["pasta_id"]),
                "banco_id": amostra_id,
            })
        quantas = self.app.carregar_do_banco(carregadas)
        if quantas == 0:
            messagebox.showinfo("Banco de amostras",
                                "Essas amostras já estão abertas no catalogador.",
                                parent=self)
        elif quantas < len(carregadas):
            messagebox.showinfo(
                "Banco de amostras",
                "%d amostra(s) aberta(s) no catalogador; as outras %d já "
                "estavam lá." % (quantas, len(carregadas) - quantas), parent=self)

    def editar_amostra(self, amostra_id):
        amostra = self.banco.amostra(amostra_id)
        dialogo = _DialogoDaAmostra(self, amostra)
        if dialogo.resultado is None:
            return
        if self._tentar(self.banco.atualizar_amostra, amostra_id,
                        **dialogo.resultado) is not False:
            self._recarregar_pasta(amostra["pasta_id"])

    def _ao_dar_dois_cliques(self, evento):
        item = self.tree.identify_row(evento.y)
        if item.startswith(AMOSTRA):
            self.editar_amostra(_id_da_amostra(item))
            return "break"

    # ============================================================
    # Arrastar e soltar
    # ============================================================

    def _arrasto_comeca(self, evento):
        item = self.tree.identify_row(evento.y)
        # só o nome do item arrasta; clicar na setinha continua abrindo
        if item and self.tree.identify_element(evento.x, evento.y) != "Treeitem.indicator":
            self._arrasto = item
        else:
            self._arrasto = None

    def _arrasto_anda(self, evento):
        if self._arrasto is None:
            return
        destino = self.tree.identify_row(evento.y)
        pode = destino.startswith(PASTA) if destino else False
        self.tree.configure(cursor="hand2" if pode else "no")

    def _arrasto_termina(self, evento):
        origem, self._arrasto = self._arrasto, None
        self.tree.configure(cursor="")
        if origem is None:
            return
        destino = self.tree.identify_row(evento.y)
        if not destino or not destino.startswith(PASTA) or destino == origem:
            return

        # arrastar UM item que faz parte de uma seleção maior move a
        # seleção inteira — é como o Explorer se comporta
        itens = self._selecao() if origem in self._selecao() else [origem]
        destino_id = _id_da_pasta(destino)
        pais = {self.tree.parent(i) for i in itens}
        mexeu = False
        for item in itens:
            if item.startswith(AMOSTRA):
                self.banco.mover_amostra(_id_da_amostra(item), destino_id)
                mexeu = True
            elif item.startswith(PASTA) and _id_da_pasta(item) != RAIZ_ID:
                if self._tentar(self.banco.mover_pasta,
                                _id_da_pasta(item), destino_id) is not False:
                    mexeu = True
        if not mexeu:
            return
        for pai in pais:
            if pai and self.tree.exists(pai):
                self._carregar_filhos(pai)
        self._recarregar_pasta(destino_id)

    # ============================================================
    # Busca
    # ============================================================

    def procurar(self):
        texto = self.busca_var.get().strip()
        if not texto:
            self.limpar_busca()
            return
        achadas = self.banco.procurar(texto)
        self.tree.delete(*self.tree.get_children(""))
        self._numero.clear()
        raiz = "busca"
        self.tree.insert("", "end", iid=raiz, open=True,
                         text="Resultados de \"%s\"" % texto,
                         values=("%d amostra(s)" % len(achadas),))
        for amostra in achadas:
            self._inserir_amostra(raiz, amostra)
            item = AMOSTRA + str(amostra["id"])
            self.tree.set(item, "detalhe",
                          "%s · %s" % (self.banco.caminho_da_pasta(amostra["pasta_id"]),
                                       amostra["codigo"] or "sem código"))
        self.status.config(text="%d amostra(s) encontrada(s). "
                                "Limpe a busca para voltar à árvore." % len(achadas))

    def limpar_busca(self):
        self.busca_var.set("")
        self.recarregar_tudo()

    # ============================================================
    # Trocar de banco
    # ============================================================

    def abrir_outro(self):
        caminho = filedialog.askopenfilename(
            title="Abrir banco de amostras", parent=self,
            filetypes=[("Banco de amostras", "*.db"), ("Todos os arquivos", "*.*")])
        if caminho:
            self._trocar(caminho)

    def criar_outro(self):
        caminho = filedialog.asksaveasfilename(
            title="Criar um banco novo", parent=self, defaultextension=".db",
            initialfile="amostras.db", initialdir=os.path.dirname(caminho_padrao()),
            filetypes=[("Banco de amostras", "*.db")])
        if caminho:
            self._trocar(caminho)

    def _trocar(self, caminho):
        try:
            novo = BancoDeAmostras(caminho)
        except Exception as erro:
            messagebox.showerror("Não deu para abrir",
                                 "%s\n\n%s" % (caminho, erro), parent=self)
            return
        self.banco.fechar()
        self.banco = novo
        self.app.banco = novo
        lembrar_caminho(caminho)
        self.limpar_busca()

    # ============================================================
    # Utilidades
    # ============================================================

    def _tentar(self, funcao, *args, **kwargs):
        """Roda uma operação do banco mostrando o erro numa caixinha em
        vez de deixar a exceção subir e derrubar o clique.

        Devolve `False` quando o banco recusou; o que a função devolver,
        quando deu certo.
        """
        try:
            resultado = funcao(*args, **kwargs)
        except ErroDoBanco as erro:
            messagebox.showwarning("Banco de amostras", str(erro), parent=self)
            return False
        return True if resultado is None else resultado

    def fechar(self):
        self.app.banco_view = None
        self.destroy()


class _DialogoDaAmostra(simpledialog.Dialog):
    """Caixinha de editar uma amostra: nome, tubo e observações."""

    def __init__(self, pai, amostra):
        self.amostra = amostra
        self.resultado = None
        super().__init__(pai, title="Amostra: %s" % amostra["nome"])

    def body(self, master):
        ttk.Label(master, text="Nome:").grid(row=0, column=0, sticky="w", pady=4)
        self.nome_var = tk.StringVar(value=self.amostra["nome"])
        entrada = ttk.Entry(master, textvariable=self.nome_var, width=40)
        entrada.grid(row=0, column=1, sticky="we", pady=4)

        ttk.Label(master, text="Tubo de raios X:").grid(row=1, column=0, sticky="w", pady=4)
        self.tubo_var = tk.StringVar(value=self.amostra["tubo"])
        ttk.Combobox(master, textvariable=self.tubo_var, state="readonly",
                     values=list(TUBE_OPTIONS.keys())).grid(row=1, column=1,
                                                            sticky="we", pady=4)

        ttk.Label(master, text="Observações:").grid(row=2, column=0, sticky="nw", pady=4)
        self.obs = tk.Text(master, width=40, height=5, wrap="word")
        self.obs.insert("1.0", self.amostra["observacoes"])
        self.obs.grid(row=2, column=1, sticky="we", pady=4)

        ttk.Label(master, foreground="#6B6250",
                  text="Arquivo de origem: %s" % (self.amostra["origem"] or "—")
                  ).grid(row=3, column=0, columnspan=2, sticky="w", pady=(8, 0))
        return entrada

    def apply(self):
        self.resultado = {
            "nome": self.nome_var.get().strip(),
            "tubo": self.tubo_var.get(),
            "observacoes": self.obs.get("1.0", "end").strip(),
        }
