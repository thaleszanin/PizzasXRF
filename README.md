# PizzasXRF

Os programas de XRF do laboratório. O do meio é o catalogador de
espectros: lê os `.txt` do WinQXAS, separa os elementos em
**majoritários** e **traço**, desenha três gráficos por amostra (total,
majoritários e traço) e salva gráfico e tabela. Em volta dele, a
**pré-análise**, que confere o erro da medida antes de catalogar
qualquer coisa, e o **corretor**, que cruza os resultados de tubos
diferentes.

## Os programas

| Programa | O que é |
| --- | --- |
| `pre_analise_xrf.py` | A **pré-análise**: roda antes do catalogador e diz quais elementos saíram com erro alto demais e precisam ser tirados antes de refazer a análise. |
| `catalogador_frx.py` / `generico/catalogador_xrf.py` | O **catalogador** de espectros, nas duas versões descritas abaixo. |
| `corretor_ag_au_rh.py` | O **corretor**, que reconcilia uma batelada medida em até 3 tubos. |

## As duas versões do catalogador

| Onde | O que é |
| --- | --- |
| `catalogador_frx.py` (raiz) | A versão com o **banco central de amostras**: pastas e subpastas editáveis por commodity (madeira, carne, soja, …). |
| `generico/catalogador_xrf.py` | O catalogador **genérico**: faz a distinção majoritário/traço de qualquer tipo de amostra, sem pastas e sem commodity. Nasceu como cópia de antes do banco e é onde os **tipos de gráfico** foram adicionados (pizza, rosca, barras, barra empilhada e Pareto). |

As duas são independentes: rodam ao mesmo tempo e não compartilham
código. Detalhes da versão genérica em [`generico/LEIA-ME.txt`](generico/LEIA-ME.txt).

## Áreas ou concentrações (versão genérica)

A primeira caixinha da janela — **"Calcular os gráficos por:"** — escolhe
de onde vêm os números:

| Opção | O que carregar |
| --- | --- |
| **1 — Áreas (.txt do XRF)** | os `.txt` do WinQXAS, um por amostra (obrigatório) e o mapeamento (opcional). O valor de cada elemento é a área do pico, em cps. |
| **2 — Concentrações (planilha .xlsx)** | a planilha exportada pelo programa de concentrações (obrigatória) e o mapeamento (opcional). A batelada inteira sai da aba **"Resultados"**, uma amostra por linha; o valor é a concentração, na unidade que estiver no cabeçalho (mg/kg). |

Daí pra frente é tudo igual: mesma separação majoritário/traço, mesmos
gráficos, mesmas tabelas. Muda o rótulo da coluna de valores ("Área
(cps)" ou "Concentração (mg/kg)") e as casas decimais — concentração de
0,065 mg/kg não pode virar "0". Célula `-` na planilha quer dizer "não
detectado" e o elemento simplesmente não entra no gráfico daquela
amostra.

As duas grandezas não se misturam na mesma tela, então trocar a opção
limpa as amostras carregadas (o programa avisa antes).

## Tipos de gráfico (versão genérica)

A caixinha **"Tipo de gráfico"** troca o desenho dos três painéis de
todas as amostras de uma vez, e vale também para as imagens salvas:

| Tipo | Para que serve |
| --- | --- |
| **Pizza** (padrão) | O de sempre: a proporção de cada elemento, com os rótulos por fora e linha guia até a fatia. |
| **Rosca** | A mesma pizza com o miolo vazio. |
| **Barras** | Uma linha por elemento, da maior para a menor. É o mais legível quando a amostra tem muitos elementos e as fatias viram riscos. |
| **Barra empilhada** | Uma barra só de 0 a 100%, com legenda. Duas amostras lado a lado se comparam de bater o olho — o que duas pizzas não permitem. |
| **Pareto** | Barras em pé mais a curva do acumulado: quantos elementos respondem por quase tudo. |

## Modo escuro e claro (versão genérica)

A janela abre no **modo escuro**; o botão no canto de cima à direita
alterna para o claro e volta. A troca é imediata e não recarrega nada —
só os gráficos são redesenhados, porque a cor deles é pixel, não estilo.

O que é salvo não segue o tema: o `.png` sai sempre com fundo branco,
para o arquivo não depender do modo em que a janela estava aberta. As
janelinhas de abrir/salvar arquivo e os avisos são do Windows, então
continuam com a cara do sistema.

## Como rodar

```
pip install matplotlib
python catalogador_frx.py
```

(A pré-análise é um programa à parte — veja a seção dela mais abaixo.)

Para calcular pelas concentrações (só na versão genérica), também
`pip install openpyxl`.

O Tkinter e o SQLite já vêm com o Python. No Linux, se o Tkinter faltar:
`sudo apt install python3-tk`.

## O banco de amostras

O botão **"Banco de amostras…"** abre a árvore de pastas. Nela dá para:

* criar, renomear, mover, reordenar e apagar pastas em qualquer
  profundidade (`1> madeira`, `1.1> in natura`, `1.1.2> pó`, `2> carne`…);
* importar `.txt` do XRF direto para dentro de uma pasta;
* guardar no banco as amostras que já estão abertas na tela;
* arrastar amostras e pastas de um lugar para outro;
* procurar amostra por nome ou por código do arquivo;
* trazer para o catalogador tudo o que está numa pasta (com as
  subpastas).

Cada amostra guarda o tubo de raios X com que foi medida, então uma
batelada com medidas de tubos diferentes descarta o elemento certo em
cada uma.

Tudo mora num arquivo só — `amostras.db`, na pasta "Catalogador FRX" do
seu perfil de usuário (a pasta e o programa da raiz ainda usam o nome
antigo, FRX; só a versão genérica foi renomeada para XRF). Backup é copiar esse arquivo; para o banco ser do
laboratório inteiro, aponte o programa para um arquivo numa pasta de rede
em "Abrir outro…".

## Pré-análise

`pre_analise_xrf.py` é o programa que roda **antes** do catalogador.
Ele lê os mesmos `.txt` do WinQXAS, mas olha a coluna que o catalogador
descarta: o **erro** do ajuste de cada pico.

O erro do arquivo é absoluto, na mesma unidade da área, e sozinho não
diz nada — 200 cps de erro é ótimo num pico de 80 000 e é um desastre
num pico de 300. Então o programa calcula o **erro relativo**:

```
erro % = erro ÷ área × 100
```

Passou do limite, o elemento é marcado: a recomendação é refazer a
análise sem ele, porque o ajuste não conseguiu separar o pico dele do
fundo. O limite padrão é **50%** e o **slider** da janela muda esse
valor — o mesmo slider (com caixinha ao lado) do catalogador genérico.

Linhas repetidas do mesmo elemento (Kα e Lα, por exemplo) viram uma
linha só, como no catalogador: as áreas somam e os erros somam em
quadratura, `√(e1² + e2²)`.

A tela tem três partes:

* em cima, os botões (**"1. Carregar amostras (.txt)"** e
  **"2. Carregar mapeamento (.csv/.txt)"**, no mesmo formato
  `código,nome real` dos outros programas) e o slider;
* embaixo deles, o **resumo do conjunto** — o log inicial, falando de
  todas as amostras de uma vez: quantas passaram e quais precisam ser
  refeitas, com os elementos que estouraram em cada uma;
* e a lista de amostras, uma embaixo da outra: a tabela de elementos
  ordenada do pior erro pro melhor, com as linhas reprovadas em
  vermelho e negrito, e ao lado dela o **log daquela amostra** ("na
  amostra M213, 2 de 14 elementos passaram de 50% de erro: Cr…") ou um
  "OK", quando não há nada a fazer.

O botão **"Exportar planilha (.xlsx)"** salva exatamente isso: uma aba
só, com a batelada empilhada na vertical — o resumo em cima, e um bloco
por amostra com a tabela (`Z`, `Elemento`, `Área (cps)`, `Erro (cps)`,
**`Erro Percentual (%)`**, `Situação`), as linhas reprovadas em negrito
vermelho sobre fundo rosado, e o log da amostra na coluna ao lado.

Como roda:

```
pip install openpyxl
python pre_analise_xrf.py
```

Aqui não entra matplotlib: a pré-análise não desenha gráfico nenhum.

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
