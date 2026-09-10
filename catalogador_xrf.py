"""
Catalogador de Espectros XRF — versão Python
==============================================

O que esse programa faz:
  0. Pergunta, antes de tudo, por qual grandeza calcular os gráficos:
     ÁREAS (os .txt do XRF, obrigatórios) ou CONCENTRAÇÕES (a planilha
     .xlsx do programa de concentrações, obrigatória). Nos dois casos o
     arquivo de mapeamento é opcional. Daí pra frente é tudo igual — a
     mesma separação majoritário/traço, os mesmos gráficos, as mesmas
     tabelas —, muda só o rótulo da coluna de valores.
  1. Lê os arquivos .txt de saída do XRF (formato WinQXAS: cabeçalho +
     linhas "Z, energia, área, erro, chi2" depois de "Photopeaks:") ou a
     aba "Resultados" da planilha de concentrações.
  2. Soma áreas de linhas repetidas do mesmo elemento (Kα e Lα, por ex.).
  3. Descarta sempre o Argônio (Z=18) e, se você selecionar um tubo de
     raios X (Ag/Au/Rh), descarta também o elemento desse tubo.
  4. Separa os elementos restantes em "majoritário" e "traço": ordena do
     menor pro maior e vai somando no grupo traço enquanto a soma
     acumulada não ultrapassar o limite escolhido no slider.
  5. Desenha 3 gráficos por amostra: total, majoritários e traço. O TIPO
     é escolhido na janela — pizza (o padrão), rosca, barras, barra
     empilhada ou Pareto — e vale tanto para a tela quanto para o que é
     salvo. As pizzas e roscas saem sempre do mesmo tamanho, as três.
  6. Permite carregar um arquivo de mapeamento (código do arquivo -> nome
     real da amostra) e processar a batelada inteira de uma vez.
  7. Salva o gráfico (.png) e a tabela (.txt) de cada amostra — uma a uma,
     a batelada inteira em arquivos separados, ou tudo compilado num
     arquivo só. O arquivo sai sempre com o fundo branco, mesmo com a
     janela no modo escuro.
  8. Abre no modo escuro; o botão no canto de cima à direita alterna
     para o claro (a escolha vale só enquanto o programa está aberto).

Como rodar:
  1. Precisa de Python 3 instalado.
  2. Instale a dependência externa:  pip install matplotlib
     (o Tkinter já vem junto do Python na maioria dos sistemas; no Linux,
     se der erro, instale com: sudo apt install python3-tk)
     Para calcular por concentrações, também:  pip install openpyxl
     — só pra isso; quem só usa os .txt do XRF não precisa dela.
  3. Rode:  python catalogador_xrf.py

Onde está cada coisa
--------------------
Este arquivo é só a porta de entrada. O código de verdade está no
pacote `catalogador/`, dividido por seção:

  catalogador/
    nucleo/        <- os DADOS (nenhuma interface, nenhum gráfico)
      tabela_periodica.py   Z -> símbolo ("26" vira "Fe")
      leitura.py            parse_xrf_file, parse_mapping
      planilha.py           parse_planilha (a aba "Resultados" do .xlsx)
      fontes.py             as duas grandezas: áreas e concentrações
      classificacao.py      descarte de Ar/tubo e majoritário vs. traço

    graficos/      <- o DESENHO (matplotlib, nenhum Tkinter)
      estilo.py             paleta de cores e tamanho da fonte
      medicao.py            medir texto e converter dados -> pixels
      pizza.py              uma pizza (ou rosca) com rótulos externos
      barras.py             barras, barra empilhada e Pareto
      tipos.py              a LISTA de tipos de gráfico disponíveis
      figura.py             os três gráficos de uma amostra, lado a lado
      tema.py               repinta a figura da TELA no modo claro/escuro

    exportacao.py  <- o CONTEÚDO DOS ARQUIVOS salvos (.txt e .png
                      compilado), sem saber onde eles vão parar

    interface/     <- a JANELA (Tkinter)
      tema.py               as cores da janela: modo escuro e claro
      app.py                botões, slider, cards e tabelas

A dependência anda sempre num sentido só — interface -> exportacao ->
graficos -> nucleo — então dá pra usar as camadas de baixo sozinhas.
Para gerar imagens num script, sem abrir janela nenhuma:

    import matplotlib
    matplotlib.use("Agg")
    from catalogador.nucleo import parse_xrf_file, apply_exclusions, classify
    from catalogador.graficos import build_sample_figure

    elementos = parse_xrf_file("amostra.txt")
    mantidos, _ = apply_exclusions(elementos, tube_z={78, 79})
    maj, tracos, total = classify(mantidos, threshold_percent=10.0)
    fig = build_sample_figure(mantidos, maj, tracos, total, "Amostra")
    fig.savefig("saida.png")

Trocando só a primeira linha, o mesmo script trabalha por concentrações
— o resto não muda, porque as duas leituras devolvem a mesma coisa:

    from catalogador.nucleo import parse_planilha

    amostras, unidade, _ = parse_planilha("amostras.xlsx")
    elementos = amostras[0]["elements"]

O último argumento do `build_sample_figure` é o tipo de gráfico; sem ele
sai pizza. Os nomes aceitos estão em `catalogador.graficos.TIPOS`:

    from catalogador.graficos import TIPOS, build_sample_figure

    for nome in TIPOS:          # "Pizza", "Rosca", "Barras", ...
        fig = build_sample_figure(mantidos, maj, tracos, total, "Amostra", nome)
        fig.savefig("saida - %s.png" % nome)
"""

from catalogador.interface import App


if __name__ == "__main__":
    app = App()
    app.mainloop()
