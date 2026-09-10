# -*- coding: utf-8 -*-
"""
Pré-análise de Espectros XRF
============================

O programa que roda ANTES do catalogador. Ele responde uma pergunta só:
"essa batelada está boa, ou tem elemento que precisa sair e a análise
ser refeita?"

O que ele faz:
  1. Lê a batelada de .txt do XRF (formato WinQXAS, os mesmos arquivos
     do catalogador) — mas aqui a coluna que interessa é o ERRO do
     ajuste, aquela que o catalogador joga fora.
  2. Calcula o erro RELATIVO de cada elemento — erro ÷ área × 100. O
     erro que vem no arquivo é absoluto, na mesma unidade da área, e
     sozinho não diz nada: 200 cps de erro é ótimo num pico de 80 000 e
     é um desastre num pico de 300.
  3. Marca os elementos que passaram do limite. O padrão é 50%, e o
     slider da janela muda esse valor — o mesmo slider do catalogador
     genérico.
  4. Mostra a batelada empilhada, uma amostra embaixo da outra, com as
     linhas reprovadas em vermelho e negrito e, ao lado de cada uma, um
     log dizendo o que fazer ("na amostra X os elementos Cr e Ni têm
     erro alto…") — ou um "ok", quando não tem nada a fazer.
  5. Em cima de tudo, o log inicial: o resumo do conjunto, falando de
     TODAS as amostras de uma vez.
  6. Exporta tudo isso numa planilha .xlsx, com o mesmo destaque e os
     mesmos logs da tela.
  7. Aceita o arquivo de mapeamento (código do arquivo -> nome real da
     amostra), igual aos outros programas.
  8. Deixa escolher uma AMOSTRA PADRÃO e mostra, ao lado de cada
     amostra, o Fator de Normalização — a área do pico de argônio do
     padrão dividida pela da amostra. O argônio vem do ar entre o tubo e
     o detector, é o mesmo em toda a batelada, e por isso serve de
     régua: uma amostra que rendeu metade do padrão tem fator 2. O fator
     aparece na tela e na planilha.
  9. Abre no modo escuro; o botão no canto de cima à direita alterna
     para o claro.

Como rodar:
  1. Precisa de Python 3 instalado.
  2. Instale a dependência externa:  pip install openpyxl
     (o Tkinter já vem junto do Python na maioria dos sistemas; no
     Linux, se der erro: sudo apt install python3-tk)
  3. Rode:  python pre_analise_xrf.py

Onde está cada coisa
--------------------
Este arquivo é só a porta de entrada. O código de verdade está no
pacote `preanalise/`:

  preanalise/
    nucleo/        <- os DADOS (nenhuma interface, nenhum Excel)
      leitura.py        ler_espectro: o .txt COM a coluna do erro
      avaliacao.py      o erro relativo e quem passou do limite
      normalizacao.py   o fator: o argônio do padrão sobre o da amostra
      relatorio.py      os textos: o log de cada amostra e o resumo

    planilha.py    <- o .xlsx: a batelada empilhada, o destaque das
                      linhas reprovadas e os logs ao lado

    interface/     <- a JANELA (Tkinter)
      tema.py           as cores da janela: modo escuro e claro
      cantos.py         os cantos arredondados dos botões
      app.py            os controles, o slider, o resumo e os cartões

A dependência anda sempre num sentido só — interface -> planilha ->
nucleo —, então dá pra rodar a pré-análise de dentro de um script, sem
abrir janela nenhuma:

    from preanalise.nucleo import (area_do_argonio, avaliar,
                                   fator_de_normalizacao, ler_espectro,
                                   log_da_amostra)
    from preanalise.planilha import exportar

    padrao = ler_espectro("081025af.txt")
    area_padrao = area_do_argonio(padrao)

    amostras = []
    for arquivo, nome in (("081025af.txt", "Madeira 123"),
                          ("081025ag.txt", "Madeira 124")):
        elementos = ler_espectro(arquivo)
        avaliacao = avaliar(elementos, limite=50.0)
        print(log_da_amostra(nome, avaliacao, 50.0))
        amostras.append({
            "nome": nome, "codigo": arquivo[:-4], "avaliacao": avaliacao,
            "fator": fator_de_normalizacao(area_padrao,
                                           area_do_argonio(elementos))})

    exportar("pre-analise.xlsx", amostras, limite=50.0, padrao="Madeira 123")

O mapeamento código->nome é o mesmo dos outros programas, e vem de lá:

    from catalogador.nucleo.leitura import parse_mapping
"""

from preanalise.interface import App


if __name__ == "__main__":
    app = App()
    app.mainloop()
