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
| `catalogador_xrf.py` / `banco_de_dados.py` | O **catalogador** de espectros, nas duas versões descritas abaixo. |
| `corretor_ag_au_rh.py` | O **corretor**, que reconcilia uma batelada medida em até 3 tubos. |

## As duas versões do catalogador

| Onde | O que é |
| --- | --- |
| `catalogador_xrf.py` | O catalogador **genérico** (pacote `catalogador/`): faz a distinção majoritário/traço de qualquer tipo de amostra, sem pastas e sem commodity. É onde os **tipos de gráfico** foram adicionados (pizza, rosca, barras, barra empilhada e Pareto). |
| `banco_de_dados.py` | A versão (pacote `bancodedados/`) que ganha o **banco de amostras**: cada arquivo `.db` abre numa aba, com as medições (o `.txt` e o `.png` que o programa exporta), as informações da planilha de cada amostra (categorias editáveis) e a exportação em `.json` para o catálogo. Tudo o mais — tipos de gráfico, tema, concentrações — é igual à genérica. |

As duas são independentes: rodam ao mesmo tempo e não compartilham
código. Detalhes da versão genérica em [`LEIA-ME.txt`](LEIA-ME.txt).

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
python catalogador_xrf.py
```

Para a versão com banco de amostras:

```
python banco_de_dados.py
```

(A pré-análise é um programa à parte — veja a seção dela mais abaixo.)

Para calcular pelas concentrações — e, na versão com banco, para
importar a planilha de informações — também `pip install openpyxl`.

O Tkinter e o SQLite já vêm com o Python. No Linux, se o Tkinter faltar:
`sudo apt install python3-tk`.

## O banco de amostras

Na versão `banco_de_dados.py`, a janela é um caderno de abas: a primeira
é o catalogador de sempre e cada banco aberto (**"Abrir banco (.db)…"**
ou **"Novo banco…"**, no canto de cima à direita) ganha a sua. Abrir
vários `.db` abre várias abas; o título de cada uma nasce igual ao nome
do arquivo e pode ser trocado (dois cliques na aba, ou "Renomear"). Os
bancos abertos voltam sozinhos da próxima vez.

**O que entra no banco**

* **"Adicionar ao banco de amostras"** (na aba Catalogador, ou
  "Adicionar amostras da tela" na aba do banco): guarda as amostras que
  estão na tela — para cada uma, a **mesma tabela `.txt` e o mesmo
  gráfico `.png`** que a exportação geraria, classificados com o tubo e
  o limite do traço de agora. O **mapeamento é obrigatório**: é ele que
  dá o nome de cada amostra (`061025ab` → `M021`), e é por esse nome que
  as medições dos três tubos (Ag, Rh, Au) e as informações da planilha
  se juntam na mesma amostra. Reexportar a mesma batelada não duplica:
  a medição que já estava é atualizada.
* **"Importar .txt/.png exportados…"**: lê de volta os arquivos que o
  próprio programa salvou (o `.png` de mesmo nome entra junto). Também
  precisa do mapeamento.
* **"Importar planilha (.xlsx)…"**: as informações de cada amostra. A
  regra de forma é uma só — **a primeira linha traz os nomes das
  categorias e uma das colunas traz o nome da amostra** (o mesmo nome
  do mapeamento). O programa sugere a coluna que mais bate com os nomes
  que ele conhece; na lista de madeiras, por exemplo, é o "Código NOVO
  temático" (`M001`, `M002`…), e não a primeira. Cada banco pode ter
  categorias diferentes: as que vierem na planilha viram as do banco.

**O que dá para fazer nele**

* a página mostra **um azulejo por amostra** (nome, as duas primeiras
  informações e uma etiqueta por tubo medido); clicar abre a amostra
  inteira: as informações numa caixa por categoria (editáveis na hora),
  a foto (opcional) e cada medição com o gráfico e a tabela;
* **"Categorias…"** cria, renomeia, reordena e apaga categorias — vale
  para o banco inteiro;
* **"Salvar cópia (.db)…"** baixa o banco num arquivo (o `.db` aberto já
  é gravado a cada mudança; a cópia é para levar, mandar ou guardar);
* **"Exportar JSON…"** gera o `.json` do catálogo e, ao lado dele, a
  pasta `dados/` com as imagens. Uma entrada por amostra:

```json
{
    "id": "FRXM-0003",
    "filename": "061025ab",
    "tecnica": {"sigla": "FRX", "nome": "Espectroscopia de Fluorescência de Raios X"},
    "nome": "M003",
    "rotulo": "M003",
    "Nome popular": "Roxinho",
    "Nome científico": "Peltogyne paniculata",
    "Latitude": "-9.366127996",
    "elementos": {
        "Ag": {"Majoritários": {"Ca": 19158, "Fe": 15797}, "Traço": {"P": 992}},
        "Rh": {"...": "..."}
    },
    "arquivos": {"Ag": "061025ab", "Rh": "150725ab"},
    "imagem": "dados/imagem-madeira/M003.png",
    "espectros": {
        "Ag": "dados/espectros/frx/agv/061025ab_agv.png",
        "Rh": "dados/espectros/frx/rhv/150725ab_rhv.png"
    }
}
```

As chaves fixas (`id`, `filename`, `tecnica`, `nome`, `rotulo`,
`elementos`, `arquivos`, `imagem`, `espectros`) são as mesmas em qualquer
banco; entre `rotulo` e `elementos` entram as categorias daquele banco,
com o nome que têm nele. O `id` é a sigla da técnica + a inicial do nome
do banco + o número da amostra; `imagem` é a foto, se houver, senão o
gráfico da primeira medição.

O banco é um arquivo SQLite (`sqlite3` vem com o Python). A lista dos
bancos abertos fica em `config.json`, na pasta "Catalogador XRF" do seu
perfil de usuário.

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
