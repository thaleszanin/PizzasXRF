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
