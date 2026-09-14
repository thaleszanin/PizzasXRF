# -*- coding: utf-8 -*-
"""O banco inteiro como um .json (mais a pasta `dados/` com as imagens).

É o formato que o site/catálogo consome. Uma entrada por amostra:

    {
        "id": "FRXM-0003",
        "filename": "061025ab",
        "tecnica": {"sigla": "FRX", "nome": "Espectroscopia de ..."},
        "nome": "M003",
        "rotulo": "M003",
        "Nome popular": "Roxinho",              <- as categorias DESTE banco,
        "Nome científico": "Peltogyne paniculata",  com o nome que têm nele
        "Latitude": "-9.366127996",
        ...
        "elementos": {
            "Ag": {"Majoritários": {"Ca": 19158, ...}, "Traço": {"P": 992, ...}},
            "Rh": {...},
            "Au": {...}
        },
        "arquivos": {"Ag": "061025ab", "Rh": "150725ab", "Au": "220725ab"},
        "imagem": "dados/imagem-madeira/M003.png",
        "espectros": {
            "Ag": "dados/espectros/frx/agv/061025ab_agv.png",
            "Rh": "dados/espectros/frx/rhv/150725ab_rhv.png",
            "Au": "dados/espectros/frx/auv/220725ab_auv.png"
        },
        "graficos": {
            "Ag": "dados/graficos/frx/agv/061025ab_agv.png",
            ...
        }
    }

As chaves fixas (id, filename, tecnica, nome, rotulo, elementos,
arquivos, imagem, espectros, graficos) são as mesmas em qualquer banco; o que
muda de um banco para outro são as categorias, que entram entre
"rotulo" e "elementos" com o nome que têm na planilha.

  * `id` é a sigla da técnica + a inicial do banco + o número da
    amostra na lista ("FRXM-0003" para a 3ª amostra do banco Madeira);
  * `filename` é o código do .txt da primeira medição (na ordem Ag, Rh,
    Au); `arquivos` traz o código de cada tubo;
  * `imagem` é a foto da amostra, se houver — senão, o gráfico da
    primeira medição, como no exemplo que serviu de modelo;
  * `espectros` é o desenho do ESPECTRO (o .mca) de cada tubo, quando
    ele está no banco; sem .mca, entra o gráfico da medição no lugar.
    `graficos` traz sempre o gráfico (pizza/barras) de cada tubo;
  * os PNGs são gravados ao lado do .json, nos caminhos que o JSON cita.
    Uma amostra sem medição sai com `elementos` e `espectros` vazios.
"""

import json
import os
import re
import unicodedata

from ..exportacao import nome_de_arquivo

# A subpasta do espectro de cada tubo, como no catálogo de origem.
PASTA_DO_TUBO = {"Ag": "agv", "Rh": "rhv", "Au": "auv"}


def slug(texto):
    """"Madeira Amazônica" -> "madeira-amazonica": o pedaço do nome do
    banco que entra no caminho das imagens."""
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    limpo = re.sub(r"[^a-z0-9]+", "-", sem_acento.lower()).strip("-")
    return limpo or "banco"


def _pasta_do_tubo(simbolo):
    return PASTA_DO_TUBO.get(simbolo, slug(simbolo))


def _valor_para_json(valor, grandeza):
    """Área sai inteira (é contagem); concentração fica com as casas."""
    if grandeza.lower().startswith("área") or grandeza.lower().startswith("area"):
        return int(round(valor))
    return valor


def montar_entradas(banco):
    """As entradas do JSON e a lista de arquivos a gravar.

    Devolve (entradas, imagens), onde `imagens` é [(caminho relativo,
    bytes)] — separado do JSON para quem só quer os dados não precisar
    escrever arquivo nenhum.
    """
    tecnica = banco.tecnica()
    sigla = tecnica["sigla"]
    inicial = (banco.nome.strip()[:1] or "X").upper()
    pasta_imagem = "dados/imagem-%s" % slug(banco.nome)
    entradas, imagens = [], []

    for numero, resumo in enumerate(banco.amostras(), start=1):
        amostra_id, nome = resumo["id"], resumo["nome"]
        medicoes = banco.medicoes(amostra_id)

        elementos, arquivos, espectros, graficos = {}, {}, {}, {}
        # os .mca da amostra, pelo código do arquivo: é assim que cada
        # um encontra a medição (o .txt) da mesma medida
        mcas = {e["codigo"].lower(): e for e in banco.espectros(amostra_id)}
        for m in medicoes:
            chave = m["simbolo"]
            if chave in elementos:
                # duas medições no mesmo tubo: a segunda entra com o
                # código junto, pra nenhuma se perder
                chave = "%s (%s)" % (m["simbolo"], m["codigo"] or m["id"])
            grupos = banco.elementos_por_grupo(m["id"])
            elementos[chave] = {
                grupo: {simbolo: _valor_para_json(v, m["grandeza"])
                        for simbolo, v in valores.items()}
                for grupo, valores in grupos.items()}
            arquivos[chave] = m["codigo"]
            base = nome_de_arquivo(m["codigo"] or "%s-%d" % (nome, m["id"]))
            pasta = _pasta_do_tubo(m["simbolo"])
            if m["tem_imagem"]:
                caminho = "dados/graficos/%s/%s/%s_%s.png" % (sigla.lower(), pasta, base, pasta)
                graficos[chave] = caminho
                imagens.append((caminho, banco.imagem_da_medicao(m["id"])))
            mca = mcas.pop(m["codigo"].lower(), None)
            if mca is not None and mca["tem_imagem"]:
                caminho = "dados/espectros/%s/%s/%s_%s.png" % (sigla.lower(), pasta, base, pasta)
                espectros[chave] = caminho
                imagens.append((caminho, banco.imagem_do_espectro(mca["id"])))
            elif chave in graficos:
                espectros[chave] = graficos[chave]
        # .mca sem .txt correspondente: entra pelo tubo que ele diz
        for mca in mcas.values():
            if not mca["tem_imagem"]:
                continue
            chave = mca["simbolo"]
            if chave in espectros:
                chave = "%s (%s)" % (mca["simbolo"], mca["codigo"])
            pasta = _pasta_do_tubo(mca["simbolo"])
            caminho = "dados/espectros/%s/%s/%s_%s.png" % (
                sigla.lower(), pasta, nome_de_arquivo(mca["codigo"]), pasta)
            espectros[chave] = caminho
            arquivos.setdefault(chave, mca["codigo"])
            imagens.append((caminho, banco.imagem_do_espectro(mca["id"])))

        foto = banco.foto(amostra_id)
        if foto:
            imagem = "%s/%s.png" % (pasta_imagem, nome_de_arquivo(nome))
            imagens.append((imagem, foto))
        else:
            imagem = next(iter(graficos.values()), "")

        entrada = {
            "id": "%s%s-%04d" % (sigla, inicial, numero),
            "filename": medicoes[0]["codigo"] if medicoes else "",
            "tecnica": dict(tecnica),
            "nome": nome,
            "rotulo": nome,
        }
        for categoria, valor in banco.atributos_por_nome(amostra_id).items():
            # uma categoria com o nome de uma chave fixa não pode
            # atropelá-la: ganha um sufixo
            chave = categoria
            while chave in entrada or chave in ("elementos", "arquivos", "imagem",
                                                "espectros", "graficos"):
                chave += " (categoria)"
            entrada[chave] = valor
        entrada["elementos"] = elementos
        entrada["arquivos"] = arquivos
        entrada["imagem"] = imagem
        entrada["espectros"] = espectros
        entrada["graficos"] = graficos
        entradas.append(entrada)

    return entradas, imagens


def exportar_json(banco, caminho_json):
    """Grava o .json e, ao lado dele, a pasta `dados/` com as imagens.
    Devolve (quantas amostras, quantas imagens)."""
    entradas, imagens = montar_entradas(banco)
    pasta = os.path.dirname(os.path.abspath(caminho_json))
    os.makedirs(pasta, exist_ok=True)
    with open(caminho_json, "w", encoding="utf-8") as f:
        json.dump(entradas, f, ensure_ascii=False, indent=4)
    for relativo, dados in imagens:
        destino = os.path.join(pasta, *relativo.split("/"))
        os.makedirs(os.path.dirname(destino), exist_ok=True)
        with open(destino, "wb") as f:
            f.write(dados)
    return len(entradas), len(imagens)
