# `cli_vector.py` — local RAG and vector database

For the Czech version, see [cli_vector_cz.md](cli_vector_cz.md).

The project keeps each subject area in its own SQLite file. Gardening, Bitcoin,
and microprocessor sources are therefore never mixed in one retrieval index.

```text
rag_wiki/src/btc/*.md|*.txt|*.pdf
        │
        ├─ ingest: extract → chunk → embeddinggemma
        ▼
rag_wiki/data/wiki_btc.db
  ├─ SQLite: source metadata and hashes
  ├─ FTS5: exact full-text search
  └─ sqlite-vec: semantic vectors for document chunks
        │
        ├─ search: show retrieved chunks
        └─ context: write RAG material for cli_ollama.py
```

## Layout and profiles

```text
rag_wiki/
├─ src/                         # curated source material
│  ├─ btc/                      # English Bitcoin wiki
│  ├─ btc_cz/                   # Czech Bitcoin wiki
│  ├─ gardening/
│  └─ procesor/
├─ data/                        # generated SQLite databases
├─ databases.json               # profile → database file and source group
├─ cli_vector.md                # this guide
└─ cli_vector_cz.md             # Czech guide
```

`cli_vector.json` holds shared settings. The important values are
`embedding_model` (`embeddinggemma`), `embedding_batch_size` (16 chunks),
`chunk_size` (1,200 characters), and `chunk_overlap` (160 characters).

`rag_wiki/databases.json` maps a profile to a source group and database:

```json
"btc_cz": {
  "file": "wiki_btc_cz.db",
  "source_group": "btc_cz"
}
```

Thus `--db btc_cz` reads `rag_wiki/src/btc_cz` and uses
`rag_wiki/data/wiki_btc_cz.db`. `--set-wiki btc_cz` saves that profile as the
default; an explicit `--db` always overrides it.

## What a database stores

| Layer | Purpose |
| --- | --- |
| `sources` | relative path, SHA-256, group, file type, ingest timestamp |
| `chunks` | content, order, character span, and optional PDF page |
| `chunks_fts` | local FTS5 exact-text index |
| `chunk_vectors` | sqlite-vec embeddings for semantic retrieval |
| `vector_meta` | schema version, embedding model, dimensions, index status |

A vector represents a complete chunk, not one word. A query for `bitcoin`
therefore returns the closest **passages**, not a thesaurus of related words.

## `embeddinggemma`

`embeddinggemma` is the RAG embedding model. For every chunk and every vector
query, `cli_vector.py` calls Ollama's `/api/embed`; the result is a 768-value
floating-point vector. sqlite-vec compares a query vector with stored vectors
and returns the nearest chunks.

The locally recorded model metadata lists Gemma 3, about 308M parameters,
2,048 context tokens, 768 embedding dimensions, and the `embedding`
capability. See [`assistant/models/embeddinggemma.md`](../assistant/models/embeddinggemma.md).

`embeddinggemma` retrieves material; it does not compose an answer. A chat
model invoked by `cli_ollama.py` performs the later answer generation.

## Ingest and reindex

`ingest` recursively processes `.md`, `.txt`, and `.pdf` files in the selected
source group:

1. Find files and calculate their SHA-256 checksums.
2. Skip unchanged sources by default.
3. Extract text. PDFs are handled page-by-page, preferring `pdfminer.six` with
   `pypdf` as a fallback; common ligatures and line-end hyphenation are repaired.
4. Split text into paragraph-friendly 1,200-character chunks with 160-character
   overlap.
5. Unless `--no-embed` is supplied, send chunks to Ollama in batches of 16.
6. Store source data, chunks, FTS entries, vectors, and embedding metadata.

For a long embedding run, progress begins after roughly 20 seconds and then
appears around every fifth of the total work:

```text
embedding: btc_cz: 48/188 chunks (26 %), elapsed 22 s, ETA 64 s
```

| Situation | Command |
| --- | --- |
| Added or edited source | `python cli_vector.py --db btc_cz ingest` |
| Text/FTS only, no Ollama call | `python cli_vector.py --db btc_cz ingest --no-embed` |
| Changed PDF extraction or chunk settings | `python cli_vector.py --db btc_cz ingest --reindex` |
| Preview selected files and chunks | `python cli_vector.py --db btc_cz ingest --dry-run` |

`--reindex` replaces chunks and vectors even when the source hash is unchanged.
It does not belong in a query flow; normal `ingest` is incremental. Changing
the embedding model currently requires a new database. Deleting a source file
does not yet remove its old chunks automatically.

## Search and context examples

```powershell
# Exact FTS5 token match; does not contact Ollama.
python cli_vector.py --db btc search "bitcoin" --mode text -k 5

# Semantic retrieval through embeddinggemma and sqlite-vec.
python cli_vector.py --db btc search "electronic money without a trusted third party" --mode vector -k 5

# Write up to three retrieved chunks for the active Ollama project.
python cli_vector.py --db btc_cz context "Jak funguje těžba bitcoinu?" --mode vector -k 3 --out wiki_btc_cz_context.txt
```

`-k 5` means at most five nearest results. A larger `k` widens the evidence
available to the chat model, but can also add weaker or repetitive passages.

`context` writes retrieved chunks with path, PDF page, and chunk number. It does
not ask a model anything. A later `cli_ollama.py` call receives that file as
reference material and should be explicitly instructed to answer only from it.

The paired `flow_vector_btc*.txt` flows demonstrate a Bitcoin mining answer
grounded in RAG context; `flow_vector_word*.txt` compares FTS5 with semantic
retrieval, then creates a list of context-grounded associations.

## Verification

```powershell
python cli_vector.py --db btc_cz inspect
python cli_vector.py --db btc_cz verify
```

`inspect` reports source and chunk counts, the model, dimensions, and
`pending`/`indexed` state. `verify` checks schema and chunk/vector consistency.
James's `RAG → data_tree` shows the directories under `rag_wiki`.
