# -*- coding: utf-8 -*-
"""As cores da janela, nos dois modos: escuro e claro.

Esta é a mesma camada de aparência do catalogador genérico
(`generico/catalogador/interface/tema.py`), copiada para cá com os
papéis a mais que a pré-análise usa — o vermelho do erro alto, o verde
do "ok" e o texto do log. Ela é copiada, e não importada, porque os
programas deste repositório rodam soltos, cada um com o seu pacote.

Um lugar só pra aparência. Nenhuma regra do programa mora aqui — trocar
de tema não muda nada do que o programa faz, só a cor das coisas.

Como a troca é instantânea
--------------------------
O caminho óbvio seria ter um jogo de estilos ("TButton", "TLabel"…) e
reconfigurá-lo a cada troca. Só que mexer num estilo que já está em uso
marca TODOS os widgets daquele estilo como sujos de uma vez, e o Tk
refaz o layout da janela inteira: medido nesta janela, com uma amostra
na lista, isso custava 1,2 SEGUNDO por troca — o bastante pra parecer
que o programa travou.

Então aqui é ao contrário: os estilos dos DOIS temas são criados uma vez
só, no começo, com o nome do tema na frente —

    Escuro.TButton   Escuro.Titulo.TLabel   Escuro.Cartao.TFrame …
    Claro.TButton    Claro.Titulo.TLabel    Claro.Cartao.TFrame  …

— e trocar de tema é só mandar cada widget usar o estilo do outro tema.
Nenhum estilo é modificado, nada além dos widgets em si é invalidado, e
a troca sai em poucos milissegundos.

Os papéis (o nome do estilo sem o tema na frente):

    TFrame / Cartao.TFrame        o fundo e o cartão de cada amostra
    Painel.TFrame                 o que fica dentro do cartão
    TLabel / Titulo.TLabel        texto normal e o nome da amostra
    Fraco.TLabel / Aviso.TLabel   o cinza dos detalhes e o do descarte
    FracoFundo.TLabel             o mesmo cinza, mas fora do cartão
    Secao.TLabel                  os rótulos em negrito dos controles
    Erro.TLabel / Ok.TLabel       o veredito de cada amostra: vermelho
                                  em negrito quando algum elemento
                                  estourou o limite, verde quando não
    Log.TLabel                    o texto do log ao lado da tabela
    TButton                       o botão azul, o padrão
    Sucesso.TButton               o verde (salvar a batelada)
    Perigo.TButton                o vermelho (remover todas)
    Neutro.TButton                o discreto (minimizar, trocar de tema)
    Cartao.TButton                os mesmos, para dentro do cartão
    Cartao.Neutro.TButton         (muda só a cor que fica atrás deles)
    TCombobox / TSpinbox / Horizontal.TScale / Treeview / TScrollbar

Os estilos de botão têm o canto levemente arredondado, o que o ttk não
faz sozinho: quem cuida disso é `cantos.py`, que troca o fundo do botão
por uma imagem gerada na hora.
"""

from tkinter import font as tkfont
from tkinter import ttk

from .cantos import arredondar

# O tema também escolhe as cores DO GRÁFICO na tela; a tradução para o
# matplotlib está em graficos/tema.py, e o nome dela vem daqui.
TEMAS = {
    "Escuro": {
        "grafico": "escuro",
        "fundo": "#1B1B1B",        # a janela toda
        "painel": "#242424",       # o cartão de cada amostra
        "campo": "#2E3238",        # dentro de caixinha e tabela
        "borda": "#3A3A3A",
        "texto": "#FFFFFF",
        "corpo": "#D8D8D8",
        "fraco": "#9A9A9A",
        "aviso": "#E0A040",
        "azul": "#2C6BD4",
        "azul_claro": "#3B7DE8",
        "azul_escuro": "#2559B0",
        "verde": "#1F9E45",
        "verde_claro": "#27B451",
        "vermelho": "#E62727",
        "vermelho_claro": "#F53C3C",
        "neutro": "#3A3F45",
        "neutro_claro": "#4A5058",
        "botao_texto": "#FFFFFF",
        "apagado": "#5F6469",
        "barra": "#4A4A4A",
    },
    "Claro": {
        "grafico": "claro",
        "fundo": "#F2F0EB",
        "painel": "#FFFFFF",
        "campo": "#FFFFFF",
        "borda": "#D8D3C7",
        "texto": "#22201C",
        "corpo": "#3A362F",
        "fraco": "#6B6250",        # o cinza quente que a janela já usava
        "aviso": "#B8792E",        # e o laranja do aviso de descarte
        "azul": "#2C6BD4",
        "azul_claro": "#3B7DE8",
        "azul_escuro": "#2559B0",
        "verde": "#1F9E45",
        "verde_claro": "#27B451",
        "vermelho": "#E62727",
        "vermelho_claro": "#F53C3C",
        "neutro": "#E4E0D6",
        "neutro_claro": "#D6D1C4",
        "botao_texto": "#FFFFFF",
        "apagado": "#A9A399",
        "barra": "#C4BFB2",
    },
}

# O tema em que o programa abre.
TEMA_PADRAO = "Escuro"

FONTE = "Segoe UI"
RECHEIO_DO_BOTAO = (14, 7)
# Raio do canto, em pixels. Leve de propósito: o suficiente pra tirar o
# canto vivo sem virar pílula.
RAIO_DO_BOTAO = 6


def outro(nome):
    """O nome do outro tema — é o que o botão de alternar precisa."""
    return "Claro" if nome == "Escuro" else "Escuro"


def estilo(tema, papel):
    """O nome completo de um estilo: o papel com o tema na frente."""
    return "%s.%s" % (tema, papel)


# A altura já medida de cada recheio de botão.
_ALTURAS = {}


def altura_do_botao(root, style, recheio):
    """Quantos pixels de altura um botão com esse recheio vai ter.

    A imagem de fundo precisa nascer com exatamente essa altura — é o
    que dispensa o Tk de esticá-la na vertical, que é a parte cara (o
    porquê está no cabeçalho de `cantos.py`). Dois pixels de diferença
    já bastam pra jogar o desenho no caminho lento, então a altura é
    MEDIDA, e não calculada: um botão de mentira, com o mesmo desenho
    dos de verdade menos a imagem, diz o número exato.
    """
    if recheio not in _ALTURAS:
        molde = "Molde%d.TButton" % len(_ALTURAS)
        style.layout(molde, [("Button.padding", {"sticky": "nsew", "children": [
            ("Button.label", {"sticky": "nsew"})]})])
        style.configure(molde, padding=recheio, font=(FONTE, 9, "bold"))
        provisorio = ttk.Button(root, style=molde, text="Ag")
        _ALTURAS[recheio] = provisorio.winfo_reqheight()
        provisorio.destroy()
    return _ALTURAS[recheio]


def _botao(root, style, tema, papel, cor, cor_ativa, cor_pressionada, cores,
           atras, recheio=RECHEIO_DO_BOTAO, texto=None):
    """Um estilo de botão: fundo chapado, canto arredondado, sem borda.

    `atras` é a cor do que está ATRÁS do botão — a janela ou o cartão.
    Ela aparece duas vezes: é com ela que o canto arredondado da imagem
    é misturado, e é ela que o widget usa de fundo, porque o ttk pinta
    o fundo do widget antes de desenhar a imagem em cima.
    """
    nome = estilo(tema, papel)
    style.configure(nome, background=atras,
                    foreground=texto or cores["botao_texto"],
                    borderwidth=0, relief="flat", anchor="center",
                    font=(FONTE, 9, "bold"))
    # o realce de passar o mouse e o de clicar vêm da imagem, não daqui:
    # o fundo do widget é sempre o de trás, em todo estado
    style.map(nome,
              background=[("disabled", atras), ("pressed", atras),
                          ("active", atras)],
              foreground=[("disabled", cores["apagado"])],
              relief=[("pressed", "flat"), ("active", "flat")])

    arredondar(root, style, nome,
               {"normal": cor, "active": cor_ativa, "pressed": cor_pressionada,
                "disabled": cores["neutro"]},
               nome.replace(".", "_"), RAIO_DO_BOTAO, recheio,
               atras, altura_do_botao(root, style, recheio))


def _estilos_do_tema(root, style, tema):
    """Cria os estilos de UM tema, todos com o nome dele na frente."""
    cores = TEMAS[tema]

    def E(papel):
        return estilo(tema, papel)

    style.configure(E("TFrame"), background=cores["fundo"])
    style.configure(E("Cartao.TFrame"), background=cores["painel"],
                    bordercolor=cores["borda"], relief="solid", borderwidth=1)
    style.configure(E("Painel.TFrame"), background=cores["painel"])

    style.configure(E("TLabel"), background=cores["fundo"],
                    foreground=cores["corpo"])
    style.configure(E("Titulo.TLabel"), background=cores["painel"],
                    foreground=cores["texto"], font=(FONTE, 12, "bold"))
    style.configure(E("Fraco.TLabel"), background=cores["painel"],
                    foreground=cores["fraco"])
    style.configure(E("FracoFundo.TLabel"), background=cores["fundo"],
                    foreground=cores["fraco"])
    style.configure(E("Aviso.TLabel"), background=cores["painel"],
                    foreground=cores["aviso"])
    style.configure(E("Secao.TLabel"), background=cores["fundo"],
                    foreground=cores["texto"], font=(FONTE, 9, "bold"))
    style.configure(E("Erro.TLabel"), background=cores["painel"],
                    foreground=cores["vermelho"], font=(FONTE, 9, "bold"))
    style.configure(E("Ok.TLabel"), background=cores["painel"],
                    foreground=cores["verde"], font=(FONTE, 9, "bold"))
    style.configure(E("Log.TLabel"), background=cores["painel"],
                    foreground=cores["corpo"])

    # dois grupos de botão: os da janela e os de dentro do cartão. A
    # diferença é só o que está atrás deles, e é isso que aparece no
    # canto arredondado.
    fundo, painel = cores["fundo"], cores["painel"]
    for atras, prefixo in ((fundo, ""), (painel, "Cartao.")):
        _botao(root, style, tema, prefixo + "TButton", cores["azul"],
               cores["azul_claro"], cores["azul_escuro"], cores, atras)
        _botao(root, style, tema, prefixo + "Neutro.TButton", cores["neutro"],
               cores["neutro_claro"], cores["neutro_claro"], cores, atras,
               recheio=(8, 5), texto=cores["corpo"])
    _botao(root, style, tema, "Sucesso.TButton", cores["verde"],
           cores["verde_claro"], cores["verde"], cores, fundo)
    _botao(root, style, tema, "Perigo.TButton", cores["vermelho"],
           cores["vermelho_claro"], cores["vermelho"], cores, fundo)

    style.configure(E("TCombobox"), fieldbackground=cores["campo"],
                    background=cores["campo"], foreground=cores["corpo"],
                    arrowcolor=cores["corpo"], bordercolor=cores["borda"],
                    lightcolor=cores["campo"], darkcolor=cores["campo"],
                    selectbackground=cores["campo"],
                    selectforeground=cores["corpo"], padding=4)
    style.map(E("TCombobox"),
              fieldbackground=[("readonly", cores["campo"])],
              background=[("readonly", cores["campo"])],
              foreground=[("disabled", cores["apagado"])])

    style.configure(E("TSpinbox"), fieldbackground=cores["campo"],
                    background=cores["campo"], foreground=cores["corpo"],
                    arrowcolor=cores["corpo"], bordercolor=cores["borda"],
                    lightcolor=cores["campo"], darkcolor=cores["campo"],
                    insertcolor=cores["corpo"], padding=3)

    style.configure(E("Horizontal.TScale"), background=cores["fundo"],
                    troughcolor=cores["campo"], bordercolor=cores["borda"],
                    darkcolor=cores["azul"], lightcolor=cores["azul"])
    style.map(E("Horizontal.TScale"), background=[("active", cores["fundo"])])

    style.configure(E("Treeview"), background=cores["campo"],
                    fieldbackground=cores["campo"], foreground=cores["corpo"],
                    bordercolor=cores["borda"], borderwidth=0, rowheight=22)
    style.map(E("Treeview"), background=[("selected", cores["azul"])],
              foreground=[("selected", cores["botao_texto"])])
    style.configure(E("Treeview.Heading"), background=cores["neutro"],
                    foreground=cores["texto"], relief="flat",
                    font=(FONTE, 9, "bold"), padding=4)
    style.map(E("Treeview.Heading"),
              background=[("active", cores["neutro_claro"])])

    for barra in ("Vertical.TScrollbar", "Horizontal.TScrollbar"):
        style.configure(E(barra), background=cores["barra"],
                        troughcolor=cores["fundo"], bordercolor=cores["fundo"],
                        arrowcolor=cores["corpo"], darkcolor=cores["barra"],
                        lightcolor=cores["barra"])
        style.map(E(barra), background=[("active", cores["neutro_claro"])])

    style.configure(E("TSeparator"), background=cores["borda"])


def preparar(root, style):
    """Cria os estilos dos DOIS temas. Uma vez só, ao abrir a janela.

    Sai um pouco mais caro no começo (as imagens de canto redondo dos
    oito botões) e é justamente isso que deixa a troca instantânea
    depois: na hora de trocar, está tudo pronto.
    """
    # clam é o único tema que vem junto com o Tk em que dá pra mandar na
    # cor de fundo de botão, tabela e barra de rolagem. Os temas nativos
    # ("vista" no Windows, "aqua" no Mac) desenham com as cores do
    # sistema e ignoram o que a gente pedir.
    style.theme_use("clam")
    # o estilo raiz leva só o que NÃO muda com o tema: mexer nele depois
    # invalidaria a janela inteira, que é exatamente o que evitamos aqui
    style.configure(".", font=(FONTE, 9))
    for tema in TEMAS:
        _estilos_do_tema(root, style, tema)


def pintar_janela(root, tema):
    """O punhado de coisas que não passa por estilo: o fundo da janela e
    a listinha que a caixa de seleção abre (um Listbox do tk puro, fora
    do alcance do ttk). Devolve as cores do tema."""
    cores = TEMAS[tema]
    root.configure(background=cores["fundo"])
    root.option_add("*TCombobox*Listbox.background", cores["campo"])
    root.option_add("*TCombobox*Listbox.foreground", cores["corpo"])
    root.option_add("*TCombobox*Listbox.selectBackground", cores["azul"])
    root.option_add("*TCombobox*Listbox.selectForeground", cores["botao_texto"])
    return cores


def trocar(raiz, velho, novo):
    """Passa todo widget do tema `velho` para o `novo`.

    É a troca em si: cada widget só passa a apontar para outro estilo,
    que já existe e já está pronto, então o Tk repinta o que mudou e
    mais nada. Devolve quantos widgets mudaram, que é o que os testes
    conferem.
    """
    trocados = 0
    for widget in _todos(raiz):
        papel = str(widget.cget("style") or widget.winfo_class())
        if papel.startswith(velho + "."):
            papel = papel[len(velho) + 1:]
        widget.configure(style=estilo(novo, papel))
        trocados += 1
    return trocados


def _todos(widget, encontrados=None):
    """Os widgets ttk da janela, em qualquer profundidade.

    Os do tk puro (o canvas da rolagem, o do matplotlib) ficam de fora:
    não têm estilo, e quem pinta esses é a janela.
    """
    if encontrados is None:
        encontrados = []
    if isinstance(widget, ttk.Widget):
        encontrados.append(widget)
    for filho in widget.winfo_children():
        _todos(filho, encontrados)
    return encontrados
