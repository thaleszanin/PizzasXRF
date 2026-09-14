# -*- coding: utf-8 -*-
"""O desenho das tabelas do banco de amostras.

Por que SQLite
--------------
O banco é UM arquivo (`.db`), lido pelo módulo `sqlite3` que já vem com
o Python — nada para instalar, nada de servidor, e dá para copiar o
banco inteiro arrastando um arquivo. É esse arquivo que a aba do banco
"baixa" em "Salvar uma cópia…" e que outra pessoa abre na aba dela.

O que mora nele
---------------
                 ┌───────────┐
                 │ amostras  │  uma por NOME (o que vem do mapeamento)
                 └─────┬─────┘
        ┌──────────────┼──────────────┐
  ┌─────┴─────┐  ┌─────┴─────┐  ┌─────┴─────┐
  │ atributos │  │ medicoes  │  │ (foto)    │
  └─────┬─────┘  └─────┬─────┘  └───────────┘
  ┌─────┴─────┐  ┌─────┴─────┐
  │categorias │  │ leituras  │
  └───────────┘  └───────────┘

* `amostras`   — a amostra física: "M003", "Cinza 12". O nome é único
                 e é por ele que tudo se junta: o mapeamento dá esse
                 nome ao .txt, e a planilha traz esse nome na coluna
                 chave.
* `categorias` — as colunas da planilha do banco ("Nome popular",
                 "Latitude"…). Cada banco tem as suas, e dá para criar,
                 renomear e apagar pela janela.
* `atributos`  — o valor de cada categoria em cada amostra. Uma linha
                 por par: apagar uma categoria leva embora os valores
                 dela e mais nada.
* `medicoes`   — UMA leitura no XRF: um .txt, um tubo. A mesma amostra
                 pode ter três (Ag, Rh e Au). Guarda o que o programa
                 exporta dela — a tabela em texto e o gráfico em PNG —
                 e as condições em que foi classificada (limite do
                 traço, tubo, o que foi descartado). Sem isso, a coluna
                 "grupo" não quer dizer nada seis meses depois.
* `leituras`   — uma linha por elemento da medição, com o valor e o
                 grupo em que caiu (majoritário, traço ou descartado).
                 Linha por elemento, e não um blob com a tabela: "qual a
                 média de Fe nas cinzas?" vira uma consulta.

A `impressao` de uma medição é um resumo dos pares (elemento, valor) e
é única: reimportar a mesma batelada não duplica nada — a medição que
já estava é ATUALIZADA com a classificação e a imagem novas.
"""

# Versão do formato. Sobe de 1 em 1 quando as tabelas mudam; fica
# gravada no próprio arquivo (PRAGMA user_version) para o programa saber
# o que precisa migrar num banco antigo.
VERSAO = 1

# Os grupos em que uma leitura pode cair.
MAJORITARIO, TRACO, DESCARTADO = "majoritário", "traço", "descartado"

# A técnica que todo banco deste programa registra. Fica em `meta`, então
# um banco pode ter outra.
TECNICA_SIGLA = "FRX"
TECNICA_NOME = "Espectroscopia de Fluorescência de Raios X"

ESQUEMA = """
CREATE TABLE meta (
    chave TEXT PRIMARY KEY,
    valor TEXT NOT NULL
) WITHOUT ROWID;

CREATE TABLE categorias (
    id    INTEGER PRIMARY KEY,
    nome  TEXT    NOT NULL UNIQUE COLLATE NOCASE,
    ordem INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE amostras (
    id        INTEGER PRIMARY KEY,
    nome      TEXT    NOT NULL UNIQUE COLLATE NOCASE,
    foto      BLOB,                       -- PNG/JPG da amostra, se houver
    criado_em TEXT    NOT NULL
);

CREATE TABLE atributos (
    amostra_id   INTEGER NOT NULL REFERENCES amostras(id)   ON DELETE CASCADE,
    categoria_id INTEGER NOT NULL REFERENCES categorias(id) ON DELETE CASCADE,
    valor        TEXT    NOT NULL DEFAULT '',
    PRIMARY KEY (amostra_id, categoria_id)
) WITHOUT ROWID;

CREATE INDEX ix_atributos_categoria ON atributos (categoria_id);

CREATE TABLE medicoes (
    id           INTEGER PRIMARY KEY,
    amostra_id   INTEGER NOT NULL REFERENCES amostras(id) ON DELETE CASCADE,
    tubo         TEXT    NOT NULL DEFAULT 'Nenhum',
    codigo       TEXT    NOT NULL DEFAULT '',   -- nome do .txt de origem
    grandeza     TEXT    NOT NULL DEFAULT 'Área',
    unidade      TEXT    NOT NULL DEFAULT 'cps',
    limite       REAL    NOT NULL,              -- limite do grupo traço (%)
    tipo_grafico TEXT    NOT NULL DEFAULT '',
    descartados  TEXT    NOT NULL DEFAULT '',   -- "Ar, Ag"
    tabela       TEXT    NOT NULL DEFAULT '',   -- o .txt que o programa exporta
    imagem       BLOB,                          -- o .png que o programa exporta
    impressao    TEXT    NOT NULL UNIQUE,
    criado_em    TEXT    NOT NULL
);

CREATE INDEX ix_medicoes_amostra ON medicoes (amostra_id, tubo);

CREATE TABLE leituras (
    medicao_id INTEGER NOT NULL REFERENCES medicoes(id) ON DELETE CASCADE,
    z          INTEGER NOT NULL,
    valor      REAL    NOT NULL,
    grupo      TEXT    NOT NULL,
    PRIMARY KEY (medicao_id, z)
) WITHOUT ROWID;
"""
