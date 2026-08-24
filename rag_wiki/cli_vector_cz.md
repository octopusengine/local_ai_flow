# `cli_vector.py` — lokální RAG a vektorová databáze

Projekt ukládá znalosti do samostatných SQLite databází. Každá wiki je jeden
soubor `.db`; zahradničení, Bitcoin a mikroprocesory se proto nepromíchají.

```text
rag_wiki/src/btc_cz/*.md|*.txt|*.pdf
        │
        ├─ ingest: extrakce → chunky → embeddinggemma
        ▼
rag_wiki/data/wiki_btc_cz.db
  ├─ SQLite: zdroje, hashe a metadata
  ├─ FTS5: přesné textové hledání
  └─ sqlite-vec: vektory chunků pro významové hledání
        │
        ├─ search: zobrazí dohledané chunky
        └─ context: uloží RAG kontext pro cli_ollama.py
```

## Struktura a konfigurace

```text
rag_wiki/
├─ src/                         # ručně spravované zdroje
│  ├─ btc/                      # anglická Bitcoin wiki
│  ├─ btc_cz/                   # česká Bitcoin wiki
│  ├─ gardening/
│  └─ procesor/
├─ data/                        # vytvořené SQLite databáze
│  ├─ wiki_btc.db
│  └─ wiki_btc_cz.db
├─ databases.json               # mapa profil → DB soubor a zdrojová skupina
├─ cli_vector.md                # English guide
└─ cli_vector_cz.md             # tento dokument
```

Kořenový soubor `cli_vector.json` nastavuje společné chování:

```json
{
  "source_root": "rag_wiki/src",
  "data_dir": "rag_wiki/data",
  "main_db": "btc",
  "embedding_model": "embeddinggemma",
  "embedding_batch_size": 16,
  "chunk_size": 1200,
  "chunk_overlap": 160,
  "databases_config": "rag_wiki/databases.json"
}
```

`rag_wiki/databases.json` propojuje název profilu se zdroji a databází:

```json
"btc_cz": {
  "file": "wiki_btc_cz.db",
  "source_group": "btc_cz"
}
```

`--db btc_cz` tedy čte `rag_wiki/src/btc_cz` a pracuje se souborem
`rag_wiki/data/wiki_btc_cz.db`. Příkaz `--set-wiki btc_cz` uloží profil jako
výchozí; explicitní `--db` má vždy přednost.

## Co obsahuje `.db`

| Vrstva | Účel |
| --- | --- |
| `sources` | relativní cesta, SHA-256, skupina, typ souboru a čas ingestu |
| `chunks` | text, pořadí, znakovou pozici a případně stránku PDF |
| `chunks_fts` (FTS5) | přesné lokální full-textové hledání |
| `chunk_vectors` (sqlite-vec) | embedding každého chunku pro semantic search |
| `vector_meta` | verze schématu, model, dimenze a stav indexace |

Vektor reprezentuje celý chunk, ne jednotlivé slovo. Dotaz `bitcoin` tedy
vrací nejbližší **pasáže**, nikoli slovník synonym.

## `embeddinggemma`

`embeddinggemma` je model používaný pro vektorovou databázi. Při ingestu
`cli_vector.py` pošle text každého chunku přes Ollama `/api/embed` a získá jeho
číselnou reprezentaci: pole 768 `float` hodnot. Stejný model převede na vektor
i pozdější dotaz. sqlite-vec pak vyhledá uložené chunky s nejbližším vektorem.

Lokálně zaznamenané parametry: Gemma 3, přibližně 308 milionů parametrů,
kontext 2 048, embedding 768 dimenzí a capability `embedding`. Viz
[`assistant/models/embeddinggemma.md`](../assistant/models/embeddinggemma.md).

```text
text chunk ──embeddinggemma──► [0.12, -0.03, …, 0.44]  (768 hodnot)
dotaz      ──embeddinggemma──► [0.10, -0.02, …, 0.41]
                                      │
                                      └── sqlite-vec: nejbližší chunky
```

Pro generování odpovědi po retrievalu se používá chatový model přes
`cli_ollama.py`; `embeddinggemma` sám text negeneruje.

## Co dělá `ingest`

`ingest` zpracovává `.md`, `.txt` a `.pdf` v příslušném `src/PROFILE`.

1. Najde zdrojové soubory rekurzivně.
2. Spočítá jejich SHA-256; nezměněné standardně přeskočí.
3. Načte text. PDF se vytahuje po stránkách, přednostně přes `pdfminer.six`,
   s fallbackem `pypdf`; opravují se ligatury a dělení slova přes konec řádku.
4. Text rozdělí na chunky o 1 200 znacích s překryvem 160 znaků. Hranice se
   pokud možno posune na odstavec nebo řádek.
5. Bez `--no-embed` odešle chunky v dávkách 16 do `embeddinggemma`.
6. V transakci uloží zdroj, chunky, FTS index a vektory.

U dlouhého běhu se první stav vypíše po zhruba 20 sekundách, pak přibližně po
pětinách práce:

```text
embedding: btc_cz: 48/188 chunks (26 %), elapsed 22 s, ETA 64 s
```

### Běžný ingest a reindex

| Situace | Příkaz |
| --- | --- |
| Nový nebo upravený zdroj | `python cli_vector.py --db btc_cz ingest` |
| Pouze FTS5, bez volání Ollamy | `python cli_vector.py --db btc_cz ingest --no-embed` |
| Změněný PDF extraktor, chunk size nebo overlap | `python cli_vector.py --db btc_cz ingest --reindex` |
| Kontrola vybraných souborů/chunků bez zápisu | `python cli_vector.py --db btc_cz ingest --dry-run` |

Běžný `ingest` zpracuje pouze změny. `--reindex` nahradí chunky a vektory i
pro soubor se stejným hashem, proto nepatří do dotazovacího flow. Změna
embedding modelu vyžaduje novou DB, aby se nemíchaly vektory odlišných modelů
nebo dimenzí. Smazaný soubor ze `src` zatím jeho staré chunky automaticky
neodstraní.

## Příklady hledání

```powershell
# Přesná tokenová shoda, bez Ollamy.
python cli_vector.py --db btc search "bitcoin" --mode text -k 5

# Významové hledání: vytvoří embedding dotazu přes Ollamu.
python cli_vector.py --db btc search "electronic money without a trusted third party" --mode vector -k 5

# Česká varianta nad oddělenou wiki.
python cli_vector.py --db btc_cz search "Jak funguje těžba bitcoinu?" --mode vector -k 3
```

`-k 5` znamená maximálně pět nejbližších výsledků. Vyšší `k` dá modelu širší
podklad, ale může přidat slabší či opakující se pasáže.

## Od vyhledání k odpovědi modelu

`context` pouze uloží nalezené chunky včetně cesty, stránky a pořadí do souboru
aktivního projektu. Odpověď až z tohoto podkladu vytvoří `cli_ollama.py`.

```powershell
python3 cli_ollama.py --project project_example
python cli_vector.py --db btc_cz context "Jak funguje těžba bitcoinu?" --mode vector -k 3 --out wiki_btc_cz_context.txt
python cli_tool.py --clr
python cli_tool.py --add "RAG: těžba Bitcoinu" wiki_btc_cz_context.txt
python cli_ollama.py --type task_base.json --sc-cz --input "Vysvětli těžbu pouze podle kontextu." --context "RAG: těžba Bitcoinu" tools_context.txt
```

Flow `flow_vector_btc.txt` / `flow_vector_btc_cz.txt` ukazují RAG odpověď na
otázku o těžbě. `flow_vector_word.txt` / `flow_vector_word_cz.txt` porovnávají
FTS5 a vektorové hledání a z nalezených chunků vytvoří přes `--sc list` seznam
asociací.

## Kontrola

```powershell
python cli_vector.py --db btc_cz inspect
python cli_vector.py --db btc_cz verify
```

`inspect` vypíše počty zdrojů/chunků, model, dimenzi a stav `pending` nebo
`indexed`. `verify` kontroluje schéma a konzistenci chunků i vektorů. V James
je strom zdrojových adresářů pod `RAG → data_tree`.
