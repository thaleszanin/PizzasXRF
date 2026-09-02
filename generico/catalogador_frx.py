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
  5. Desenha 3 gráficos de pizza por amostra: total, majoritários, traço,
     os três sempre do mesmo tamanho.
  6. Permite carregar um arquivo de mapeamento (código do arquivo -> nome
     real da amostra) e processar a batelada inteira de uma vez.
  7. Salva o gráfico (.png) e a tabela (.txt) de cada amostra — uma a uma,
     a batelada inteira em arquivos separados, ou tudo compilado num
     arquivo só.

Como rodar:
  1. Precisa de Python 3 instalado.
  2. Instale a única dependência externa:  pip install matplotlib
     (o Tkinter já vem junto do Python na maioria dos sistemas; no Linux,
     se der erro, instale com: sudo apt install python3-tk)
  3. Rode:  python catalogador_frx.py

Onde está cada coisa
--------------------
Este arquivo é só a porta de entrada. O código de verdade está no
pacote `catalogador/`, dividido por seção:

  catalogador/
    nucleo/        <- os DADOS (nenhuma interface, nenhum gráfico)
      tabela_periodica.py   Z -> símbolo ("26" vira "Fe")
      leitura.py            parse_frx_file, parse_mapping
      classificacao.py      descarte de Ar/tubo e majoritário vs. traço

    graficos/      <- o DESENHO (matplotlib, nenhum Tkinter)
      estilo.py             paleta de cores e tamanho da fonte
      pizza.py              uma pizza com rótulos externos + linhas guia
      figura.py             as três pizzas de uma amostra, lado a lado

    exportacao.py  <- o CONTEÚDO DOS ARQUIVOS salvos (.txt e .png
                      compilado), sem saber onde eles vão parar

    interface/     <- a JANELA (Tkinter)
      app.py                botões, slider, cards e tabelas

A dependência anda sempre num sentido só — interface -> exportacao ->
graficos -> nucleo — então dá pra usar as camadas de baixo sozinhas.
Para gerar imagens num script, sem abrir janela nenhuma:

    import matplotlib
    matplotlib.use("Agg")
    from catalogador.nucleo import parse_frx_file, apply_exclusions, classify
    from catalogador.graficos import build_sample_figure

    elementos = parse_frx_file("amostra.txt")
    mantidos, _ = apply_exclusions(elementos, tube_z={78, 79})
    maj, tracos, total = classify(mantidos, threshold_percent=10.0)
    build_sample_figure(mantidos, maj, tracos, total, "Amostra").savefig("saida.png")
"""

from catalogador.interface import App


if __name__ == "__main__":
    app = App()
    app.mainloop()
