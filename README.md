# PizzasXRF

Catalogador de espectros de FRX: lê os `.txt` do WinQXAS, separa os
elementos em **majoritários** e **traço**, desenha três pizzas por
amostra e salva gráfico e tabela.

## As duas versões

| Onde | O que é |
| --- | --- |
| `catalogador_frx.py` (raiz) | A versão com o **banco central de amostras**: pastas e subpastas editáveis por commodity (madeira, carne, soja, …). |
| `generico/catalogador_frx.py` | Cópia congelada de antes do banco — o catalogador **genérico**, que faz a distinção majoritário/traço de qualquer tipo de amostra, sem pastas e sem commodity. |

As duas são independentes: rodam ao mesmo tempo e não compartilham
código. Detalhes da versão congelada em [`generico/LEIA-ME.txt`](generico/LEIA-ME.txt).

## Como rodar

```
pip install matplotlib
python catalogador_frx.py
```

O Tkinter e o SQLite já vêm com o Python. No Linux, se o Tkinter faltar:
`sudo apt install python3-tk`.

## O banco de amostras

O botão **"Banco de amostras…"** abre a árvore de pastas. Nela dá para:

* criar, renomear, mover, reordenar e apagar pastas em qualquer
  profundidade (`1> madeira`, `1.1> in natura`, `1.1.2> pó`, `2> carne`…);
* importar `.txt` do FRX direto para dentro de uma pasta;
* guardar no banco as amostras que já estão abertas na tela;
* arrastar amostras e pastas de um lugar para outro;
* procurar amostra por nome ou por código do arquivo;
* trazer para o catalogador tudo o que está numa pasta (com as
  subpastas).

Cada amostra guarda o tubo de raios X com que foi medida, então uma
batelada com medidas de tubos diferentes descarta o elemento certo em
cada uma.

Tudo mora num arquivo só — `amostras.db`, na pasta "Catalogador FRX" do
seu perfil de usuário. Backup é copiar esse arquivo; para o banco ser do
laboratório inteiro, aponte o programa para um arquivo numa pasta de rede
em "Abrir outro…".

## Corretor Ag/Au/Rh

`corretor_ag_au_rh.py` é um programa à parte (não usa o banco de
amostras) que reconcilia os resultados de uma batelada medida em até 3
tubos de raios X diferentes. Ag, Au e Rh aqui são os **tubos** (o
material do ânodo), não elementos da amostra — cada tubo dá seu próprio
arquivo Excel de resultados, com as concentrações dos elementos reais
que aquele tubo conseguiu detectar (Ca, Cl, Cr, Fe, K, Mn, P, Zn…), e
esses elementos variam de tubo pra tubo.

A tela tem um painel por tubo: **"Abrir arquivo…"** lê automaticamente a
aba **"Resultados"** da planilha exportada pelo programa de
concentrações (cabeçalho em 3 linhas: nome do elemento ocupando 2
colunas, linha `LD`, depois `C`/`Erro`). Pode deixar sem arquivo o tubo
que não foi usado.

Depois de "Processar", o programa roda a correção em **cada elemento**
que aparece em pelo menos um dos tubos abertos: usa o tubo Au como
referência fixa, calcula o fator de correção pra Ag e Rh, e cruza as
até 3 leituras de cada amostra (Teste 1 com as 3, Teste 2 com 2,
descartando a leitura inconsistente). A tabela final tem uma linha por
amostra e, pra cada elemento, um bloco de colunas por tubo que o mediu
(ex.: `Fe Conc (Ag)`, `Fe Conc (Au)`, `Fe Conc (Rh)`), deixando claro de
qual tubo veio cada resultado — elemento que só um tubo mediu passa
direto, sem correção nem descarte.

Cada painel tem seu próprio botão **"Mapeamento…"** (mesmo formato
`.csv`/`.txt` de "código,nome real" do catalogador). Isso é necessário
porque cada tubo gera um código de arquivo diferente pra mesma amostra
física — por exemplo, `111111aa` (tubo Ag), `222222bb` (tubo Au) e
`333333cc` (tubo Rh) podem ser todos a amostra `M213`. O mapeamento de
cada painel é aplicado **antes** de comparar os tubos entre si, então as
três leituras já chegam como `M213` na hora de casar as amostras; quem
não tem associação no mapeamento daquele tubo continua aparecendo pelo
código original.

Como roda:

```
pip install openpyxl
python corretor_ag_au_rh.py
```

A lógica completa (fator de correção, Teste 1 com 3 alvos, Teste 2 com
2 alvos) está documentada no topo de `corretor/nucleo.py`.
