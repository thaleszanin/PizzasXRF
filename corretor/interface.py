"""Janela do corretor: abrir os arquivos de resultado de cada tubo, rodar
a correção elemento a elemento, conferir e salvar o resultado.

Ag, Au e Rh aqui são os TUBOS de raios X usados na medição — cada um dá
sua própria planilha de resultados (sempre na aba "Resultados"), com os
elementos reais que aquele tubo detectou. Dá pra usar só 1 ou 2 tubos, se
for o caso. Como cada tubo pode gerar um código de arquivo diferente para
a mesma amostra física, cada painel tem seu próprio mapeamento
código->nome real, aplicado antes de comparar os tubos entre si.
"""

import os
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk

from catalogador.nucleo.leitura import parse_mapping

from .nucleo import (
    abrir_resultados,
    aplicar_mapeamento,
    detectar_pares,
    processar_por_tubo,
    salvar_tabela,
)

TUBOS = ("Ag", "Au", "Rh")

EXTENSOES = [
    ("Excel", "*.xlsx *.xlsm"),
    ("Todos os arquivos", "*.*"),
]


class PainelDeTubo(ttk.LabelFrame):
    """Um painel por tubo: arquivo de resultados + mapeamento código->nome."""

    def __init__(self, mestre, tubo):
        super().__init__(mestre, text=f"Tubo {tubo}", padding=8)
        self.tubo = tubo
        self.bloco = None  # (cabecalho, linhas), já lido do arquivo
        self.mapeamento = {}

        self.rotulo_arquivo = ttk.Label(self, text="Nenhum arquivo aberto.", wraplength=220)
        self.rotulo_arquivo.pack(fill="x")

        ttk.Button(self, text="Abrir arquivo…", command=self._abrir_arquivo).pack(
            fill="x", pady=(6, 0)
        )

        linha_mapa = ttk.Frame(self)
        linha_mapa.pack(fill="x", pady=(6, 0))
        ttk.Button(linha_mapa, text="Mapeamento…", command=self._carregar_mapeamento).pack(
            side="left"
        )
        self.rotulo_mapeamento = ttk.Label(linha_mapa, text="sem mapeamento")
        self.rotulo_mapeamento.pack(side="left", padx=(6, 0))

    def _abrir_arquivo(self):
        caminho = filedialog.askopenfilename(
            title=f"Resultados do tubo {self.tubo}", filetypes=EXTENSOES
        )
        if not caminho:
            return
        try:
            cabecalho, linhas = abrir_resultados(caminho)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Erro ao abrir arquivo", str(exc))
            return
        if not cabecalho or not linhas:
            messagebox.showerror("Erro ao abrir arquivo", "A aba \"Resultados\" está vazia.")
            return
        self.bloco = (cabecalho, linhas)
        elementos = ", ".join(detectar_pares(cabecalho)) or "nenhum"
        self.rotulo_arquivo.configure(
            text=f"{os.path.basename(caminho)}\n{len(linhas)} amostra(s) — elementos: {elementos}"
        )

    def _carregar_mapeamento(self):
        caminho = filedialog.askopenfilename(
            title=f"Mapeamento código->nome para o tubo {self.tubo}",
            filetypes=[("CSV ou texto", "*.csv *.txt")],
        )
        if not caminho:
            return
        try:
            self.mapeamento = parse_mapping(caminho)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Erro ao ler mapeamento", str(exc))
            return
        self.rotulo_mapeamento.configure(
            text=f"{len(self.mapeamento)} associações ({os.path.basename(caminho)})"
        )

    def dados_mapeados(self):
        """(cabecalho, linhas) com o código já trocado pelo nome real, ou
        None se nenhum arquivo foi aberto."""
        if self.bloco is None:
            return None
        cabecalho, linhas = self.bloco
        return cabecalho, aplicar_mapeamento(linhas, self.mapeamento)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Corretor Ag / Au / Rh")
        self.geometry("1040x680")
        self.minsize(820, 480)

        self.cabecalho_resultado = None
        self.linhas_resultado = None

        self._montar_widgets()

    def _montar_widgets(self):
        instrucao = ttk.Label(
            self,
            padding=(10, 8, 10, 0),
            text=(
                "Abra o arquivo de resultados de cada tubo usado (a aba "
                "\"Resultados\" é lida automaticamente). Pode deixar um tubo "
                "sem arquivo, se não foi usado. Se o código do arquivo for "
                "diferente entre os tubos para a mesma amostra física, "
                "carregue o mapeamento daquele tubo antes de processar."
            ),
            wraplength=1000,
        )
        instrucao.pack(fill="x")

        painéis = ttk.Frame(self, padding=10)
        painéis.pack(fill="x")
        for i in range(3):
            painéis.columnconfigure(i, weight=1)

        self.paineis = {}
        for i, tubo in enumerate(TUBOS):
            painel = PainelDeTubo(painéis, tubo)
            painel.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 6, 0))
            self.paineis[tubo] = painel

        barra = ttk.Frame(self, padding=(10, 0))
        barra.pack(fill="x")
        ttk.Button(barra, text="Processar", command=self.processar).pack(side="left")
        self.botao_salvar = ttk.Button(
            barra, text="Salvar resultado…", command=self.salvar_resultado, state="disabled"
        )
        self.botao_salvar.pack(side="left", padx=(6, 0))

        divisor = ttk.PanedWindow(self, orient="vertical")
        divisor.pack(fill="both", expand=True, padx=10, pady=10)

        quadro_tabela = ttk.Frame(divisor)
        self.tabela = ttk.Treeview(quadro_tabela, show="headings")
        rolagem_v = ttk.Scrollbar(quadro_tabela, orient="vertical", command=self.tabela.yview)
        rolagem_h = ttk.Scrollbar(quadro_tabela, orient="horizontal", command=self.tabela.xview)
        self.tabela.configure(yscrollcommand=rolagem_v.set, xscrollcommand=rolagem_h.set)
        self.tabela.grid(row=0, column=0, sticky="nsew")
        rolagem_v.grid(row=0, column=1, sticky="ns")
        rolagem_h.grid(row=1, column=0, sticky="ew")
        quadro_tabela.rowconfigure(0, weight=1)
        quadro_tabela.columnconfigure(0, weight=1)
        divisor.add(quadro_tabela, weight=3)

        self.log = scrolledtext.ScrolledText(divisor, wrap="word", state="disabled", height=8)
        divisor.add(self.log, weight=1)

    def _escrever_log(self, linhas):
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.insert("end", "\n".join(linhas))
        self.log.configure(state="disabled")

    def _preencher_tabela(self, cabecalho, linhas):
        self.tabela.delete(*self.tabela.get_children())
        self.tabela["columns"] = cabecalho
        for col in cabecalho:
            self.tabela.heading(col, text=col)
            self.tabela.column(col, width=110, anchor="center")
        for linha in linhas:
            valores = ["" if v is None else v for v in linha]
            self.tabela.insert("", "end", values=valores)

    def processar(self):
        blocos = {}
        for tubo, painel in self.paineis.items():
            dados = painel.dados_mapeados()
            if dados is not None:
                blocos[tubo] = dados

        if not blocos:
            messagebox.showwarning(
                "Nada pra processar", "Abra o arquivo de resultados de ao menos um tubo."
            )
            return

        try:
            cabecalho, linhas_corrigidas, relatorio = processar_por_tubo(blocos)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Erro ao processar", str(exc))
            return

        self.cabecalho_resultado = cabecalho
        self.linhas_resultado = linhas_corrigidas
        self._preencher_tabela(cabecalho, linhas_corrigidas)
        self._escrever_log(relatorio.linhas_texto())
        self.botao_salvar.configure(state="normal")

    def salvar_resultado(self):
        if self.linhas_resultado is None:
            return
        caminho = filedialog.asksaveasfilename(
            title="Salvar tabela corrigida",
            initialfile="corrigido.xlsx",
            defaultextension=".xlsx",
            filetypes=[("Excel", "*.xlsx"), ("CSV", "*.csv"), ("Todos os arquivos", "*.*")],
        )
        if not caminho:
            return
        try:
            salvar_tabela(caminho, self.cabecalho_resultado, self.linhas_resultado)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Erro ao salvar", str(exc))
            return
        messagebox.showinfo("Pronto", f"Tabela corrigida salva em:\n{caminho}")


def main():
    App().mainloop()


if __name__ == "__main__":
    main()
