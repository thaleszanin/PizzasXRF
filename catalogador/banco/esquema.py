# -*- coding: utf-8 -*-
"""O desenho das tabelas do banco de amostras e as migrações de versão.

Por que SQLite
--------------
O banco é UM arquivo (`amostras.db`), lido pelo módulo `sqlite3` que já
vem com o Python — nada para instalar, nada de servidor, e dá para
copiar/fazer backup do banco inteiro arrastando um arquivo. Também dá
para colocar esse arquivo numa pasta de rede e o laboratório inteiro
enxergar as mesmas amostras.

Por que a árvore é guardada assim
---------------------------------
Cada pasta guarda só quem é o PAI dela (`pai_id`). É a forma mais barata
de deixar a árvore EDITÁVEL: mover "Cinza" de madeira para carne é UM
update de uma linha só. A alternativa comum (guardar o caminho inteiro,
tipo "1/3/7", em cada linha) deixa a leitura um tico mais rápida mas
obriga a reescrever TODOS os descendentes a cada movimentação — e a
promessa aqui é justamente que reorganizar a árvore seja barato.

Para ler uma sub-árvore inteira de uma vez (por exemplo, "todas as
amostras de madeira, incluindo as subpastas") usamos `WITH RECURSIVE`,
que o SQLite resolve por conta própria, sem trazer a árvore para o
Python. O índice em (`pai_id`, `ordem`) faz essa descida ser uma busca
por índice em cada nível, não uma varredura da tabela.

A pasta raiz
------------
A linha de id=1 ("Amostras") existe sempre e é a única com `pai_id`
NULL. Ela não é enfeite: no SQLite, dois NULLs são considerados
DIFERENTES entre si, então `UNIQUE (pai_id, nome)` não impediria duas
commodities com o mesmo nome se elas pendurassem direto no NULL. Com uma
raiz de verdade, a regra "não pode ter duas pastas irmãs com o mesmo
nome" vale em todos os níveis.

Onde ficam os números da medida
-------------------------------
Uma linha por elemento em `leituras` (amostra, Z, área) em vez de um
blob com a tabela inteira. Custa o mesmo para carregar uma amostra e
abre a porta para as perguntas que vão aparecer quando houver soja e
carne no banco — "qual a média de Fe nas cinzas de madeira?" vira uma
consulta, não um script que abre 300 arquivos.
"""

# Versão do formato do banco. Sobe de 1 em 1 quando as tabelas mudam;
# `_migrar` em repositorio.py usa isso para saber o que aplicar num
# banco antigo. Fica gravado no próprio arquivo (PRAGMA user_version).
VERSAO = 1

# A pasta que existe sempre e não pode ser apagada nem renomeada.
RAIZ_ID = 1
RAIZ_NOME = "Amostras"

ESQUEMA = """
CREATE TABLE pastas (
    id      INTEGER PRIMARY KEY,
    pai_id  INTEGER REFERENCES pastas(id) ON DELETE CASCADE,
    nome    TEXT    NOT NULL,
    ordem   INTEGER NOT NULL DEFAULT 0,
    UNIQUE (pai_id, nome)
);

-- a descida da árvore (filhos de X, na ordem) é sempre por este índice
CREATE INDEX ix_pastas_pai ON pastas (pai_id, ordem, nome);

CREATE TABLE amostras (
    id          INTEGER PRIMARY KEY,
    pasta_id    INTEGER NOT NULL REFERENCES pastas(id) ON DELETE RESTRICT,
    nome        TEXT    NOT NULL,
    codigo      TEXT    NOT NULL DEFAULT '',   -- nome do .txt de origem
    tubo        TEXT    NOT NULL DEFAULT 'Nenhum',
    observacoes TEXT    NOT NULL DEFAULT '',
    origem      TEXT    NOT NULL DEFAULT '',   -- caminho de onde veio
    impressao   TEXT    NOT NULL,              -- resumo dos números lidos
    criado_em   TEXT    NOT NULL,
    -- a mesma medida não entra duas vezes, nem com outro nome de arquivo
    UNIQUE (impressao)
);

CREATE INDEX ix_amostras_pasta ON amostras (pasta_id, nome);
CREATE INDEX ix_amostras_codigo ON amostras (codigo);

CREATE TABLE leituras (
    amostra_id INTEGER NOT NULL REFERENCES amostras(id) ON DELETE CASCADE,
    z          INTEGER NOT NULL,
    area       REAL    NOT NULL,
    PRIMARY KEY (amostra_id, z)
) WITHOUT ROWID;
"""

# A árvore que um banco novo já nasce tendo. É só um ponto de partida —
# tudo aqui pode ser renomeado, movido ou apagado pela janela do banco, e
# outras commodities (soja, carne, ...) entram do mesmo jeito.
ARVORE_INICIAL = [
    ("Madeira", [
        ("In natura", [("Bruta", []), ("Pó", [])]),
        ("Cinza", []),
    ]),
    ("Carne", [
        ("In natura", []),
        ("Cinza", []),
    ]),
]
