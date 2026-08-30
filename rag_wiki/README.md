# Local RAG wiki

This directory contains local knowledge bases for James/chat and the
[`cli_vector.py`](../cli_vector.py) tool. Each wiki is an independent SQLite
database, such as `data/wiki_btc.db` or `data/wiki_btc_cz.db`. Subject areas
therefore remain separate, and a database can be backed up as a single file.

## How RAG works

RAG (*Retrieval-Augmented Generation*) does not retrain the language model or
store anything in its weights. Before an answer is generated, it finds useful
passages in the selected wiki and adds them to the context of the question.

```text
sources (.md, .txt, .pdf, web)
        │ ingest
        ▼
chunks + metadata + FTS5 + vectors ──► wiki_NAME.db
                                         │
question ──► query embedding ──► nearest chunks
                                         │
                                         ▼
                         context for James/chat or a model response
```

During ingest, text is split into overlapping **chunks**. Each chunk stores
its source, order, optional page number, and an embedding: a numerical vector
created by `embeddinggemma`. During semantic search, the query is embedded as
well, and `sqlite-vec` returns the chunks with the smallest vector distance.

Alongside that, FTS5 provides exact full-text search. Vector search is useful
for meaning and paraphrases; FTS5 is useful for exact words, names, and
numbers. Retrieved chunks are evidence for an answer, not a guarantee of
truth: the model must preserve their context and source.

## Layout

```text
rag_wiki/
├─ src/                 curated sources by group, for example btc_cz/
│  └─ NAME/web_src.json optional web-source manifest
├─ data/                generated wiki_NAME.db databases
├─ databases.json       profile → source group → database
├─ rag_swg.py           helper for the diagnostic RAG SVG map
└─ *.md                 guides and design documentation
```

Shared settings live in [`cli_vector.json`](../cli_vector.json): the embedding
model, chunk size, overlap, and embedding batch size. `databases.json` maps a
profile to its `src/NAME` source directory and `wiki_NAME.db` database, and
selects the default profile.

## `cli_vector.py` in practice

Run commands from the project root. Ollama must be available with the
embedding model configured in `cli_vector.json`.

```powershell
# Create or refresh a wiki from rag_wiki/src/btc.
python .\cli_vector.py ingest-wiki btc --embed

# Select a specific wiki for subsequent commands.
python .\cli_vector.py --db btc inspect
python .\cli_vector.py --db btc search -k 5 "bitcoin mining"

# Exact word matching via FTS5 only.
python .\cli_vector.py --db btc search --mode text "hardware wallet"

# Write retrieval material for a later chat run.
python .\cli_vector.py --db btc context -k 5 --out rag_context.txt "bitcoin mining"

# Produce a standalone 2D diagnostic map of query terms and selected chunks.
python .\cli_vector.py --db btc --svg "bitcoin mining, hardware wallet"
```

`ingest` adds or updates changed sources for the already selected profile.
`ingest-wiki NAME` creates and populates a named wiki from `src/NAME`.
`--set-wiki NAME` saves a profile as the default. `verify` checks schema,
chunk, and vector consistency. `context` does not create an answer; it only
writes selected source material to a file that a chat flow can then use.

## Documentation in this directory

| Document | Contents |
| --- | --- |
| [cli_vector.md](cli_vector.md) | Main English guide to commands, profiles, ingest, search, and context generation. |
| [cli_vector_cz.md](cli_vector_cz.md) | Czech version of the `cli_vector.py` guide. |
| [rag_chunk_cz.md](rag_chunk_cz.md) | Detailed Czech explanation of chunks, embeddings, distances, queries, and James/chat usage. |
| [rag_schema.md](rag_schema.md) | Personal LLM-wiki schema, source metadata, and traceability principles. |
| [rag_srovnani.md](rag_srovnani.md) | Czech comparison of SQLite + sqlite-vec + FTS5, Chroma, and Qdrant for local RAG. |
| [vector_db_cz.md](vector_db_cz.md) | Czech overview of vector-database choices for small local projects. |

## Relation to James/chat

In chat, `/rag NAME` first attaches a wiki. `/chunk query` retrieves the
default number of chunks and attaches them to the active context; `/ask query`
performs retrieval and the subsequent model query in one step. See
[rag_chunk_cz.md](rag_chunk_cz.md) for the detailed current behaviour and the
meaning of vector distances. `cli_vector.py` remains the better interface for
standalone retrieval tests and visualisation.
