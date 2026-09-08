# -*- coding: utf-8 -*-
"""Os textos dos logs: o de cada amostra e o resumo da batelada.

São dois:

  * o log INDIVIDUAL, que fica ao lado da tabela de cada amostra (na
    tela e na planilha) e diz, em uma frase, o que aquela amostra tem —
    ou um "ok" quando não tem nada;

  * o RESUMO DO CONJUNTO, que abre a tela e abre a planilha, falando
    das amostras todas de uma vez: quantas estão limpas e quais
    precisam ser refeitas.

O texto é montado aqui, e não na janela nem na planilha, porque os dois
precisam exatamente do mesmo — quem lê o .xlsx meses depois tem que ver
a mesma frase que estava na tela.

As linhas do resumo saem como pares (papel, texto), onde o papel é
"titulo", "problema", "ok" ou "normal". Quem mostra decide o que fazer
com isso: a janela pinta de vermelho, a planilha põe em negrito.
"""

from .avaliacao import formatar_pct

# Quantas amostras problemáticas o resumo lista uma a uma antes de
# resumir o resto num "e mais N". Uma batelada de 200 amostras toda
# ruim viraria um resumo que ninguém lê.
MAX_AMOSTRAS_LISTADAS = 40


def plural(quantidade, singular, plural_):
    """"1 amostra", "3 amostras" — o número junto com a palavra certa.

    Está aqui, e não em cada texto, porque "1 de 1 elementos passaram"
    é o tipo de coisa que faz quem lê desconfiar do resto do relatório.
    """
    return "%d %s" % (quantidade, singular if quantidade == 1 else plural_)


def _lista(itens):
    """"a", "a e b", "a, b e c" — a enumeração como se escreve."""
    itens = list(itens)
    if len(itens) <= 1:
        return "".join(itens)
    return "%s e %s" % (", ".join(itens[:-1]), itens[-1])


def _com_erro(elementos):
    """Os elementos com o erro deles entre parênteses: "Cr (312.0%)"."""
    return [f"{e['symbol']} ({formatar_pct(e['pct'])})" for e in elementos]


def log_da_amostra(nome, avaliacao, limite):
    """A frase que fica ao lado da tabela de uma amostra."""
    altos, total = avaliacao["altos"], avaliacao["total"]
    if not altos:
        if total == 1:
            return "OK — o único elemento ficou abaixo de %.1f%% de erro." % limite
        return ("OK — nenhum dos %d elementos passou de %.1f%% de erro."
                % (total, limite))

    um = len(altos) == 1
    return ("Na amostra %s, %d de %s %s de %.1f%% de erro: %s. "
            "Refaça a análise sem %s."
            % (nome, len(altos), plural(total, "elemento", "elementos"),
               "passou" if um else "passaram", limite, _lista(_com_erro(altos)),
               "ele" if um else "esses elementos"))


def resumo_da_amostra(avaliacao):
    """O veredito curto, do tamanho de um selo, pro cabeçalho do cartão:
    "3 elementos com erro alto" ou "OK"."""
    quantos = len(avaliacao["altos"])
    if not quantos:
        return "OK"
    return ("1 elemento com erro alto" if quantos == 1
            else "%d elementos com erro alto" % quantos)


def linhas_do_resumo(amostras, limite, falhas=()):
    """O log inicial, falando de todas as amostras.

    `amostras` é a lista de {"nome", "codigo", "avaliacao"} e `falhas`,
    os arquivos que nem chegaram a ser lidos: [(arquivo, motivo)].

    Devolve [(papel, texto)] — veja o cabeçalho do módulo.
    """
    ruins = [a for a in amostras if a["avaliacao"]["altos"]]
    boas = [a for a in amostras if not a["avaliacao"]["altos"]]

    linhas = [("titulo", "Pré-análise de %s — limite de erro: %.1f%%"
               % (plural(len(amostras), "amostra", "amostras"), limite))]

    if not amostras:
        linhas.append(("normal", "Nenhuma amostra carregada ainda."))
    elif not ruins:
        linhas.append(("ok", "%s: nenhum elemento acima de %.1f%% de erro. "
                             "Nada a refazer."
                             % ("A amostra passou" if len(amostras) == 1
                                else "Todas as %d amostras passaram" % len(amostras),
                                limite)))
    else:
        uma = len(ruins) == 1
        linhas.append(("problema",
                       "%d de %s %s elemento acima do limite e %s ser %s:"
                       % (len(ruins), plural(len(amostras), "amostra", "amostras"),
                          "tem" if uma else "têm",
                          "precisa" if uma else "precisam",
                          "refeita" if uma else "refeitas")))
        for amostra in ruins[:MAX_AMOSTRAS_LISTADAS]:
            linhas.append(("problema", "    • %s: %s"
                           % (amostra["nome"],
                              ", ".join(_com_erro(amostra["avaliacao"]["altos"])))))
        sobrando = len(ruins) - MAX_AMOSTRAS_LISTADAS
        if sobrando > 0:
            linhas.append(("problema", "    • … e mais %s — a lista completa "
                                       "está ao lado de cada uma."
                           % plural(sobrando, "amostra", "amostras")))

        if boas:
            linhas.append(("ok", "%s sem nenhum ajuste: %s."
                           % ("Passou" if len(boas) == 1 else "Passaram",
                              _lista(a["nome"] for a in boas))))

    for arquivo, motivo in falhas:
        linhas.append(("problema", "Não consegui ler %s: %s" % (arquivo, motivo)))

    return linhas


def texto_do_resumo(amostras, limite, falhas=()):
    """O mesmo resumo, num texto só — pra quem não liga pros papéis."""
    return "\n".join(texto for _, texto in linhas_do_resumo(amostras, limite, falhas))
