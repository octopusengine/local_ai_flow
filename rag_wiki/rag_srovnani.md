# Srovnání lokálních RAG úložišť

## Výchozí situace

Budoucí zdroje jsou `.txt`, `.md` a `.pdf` v `rag_wiki/src/`; každá odborná
oblast má vlastní databázi v `rag_wiki/data/`. `wiki_base.db` je jen výchozí
profil, vedle něj mohou být například `wiki_gardening.db` a
`wiki_procesor.db`. Lokální Ollama a pozdější napojení `cli_vector.py` na
`cli_ollama.py` zůstávají společné. Bez serveru a Dockeru.

Podklady ukazují dvě důležité vrstvy. Ukázka s Chroma načítá PDF, dělí je na
chunky a ukládá je do persistentního adresáře. Star Wars ukázka používá Qdrant
Local, metadata a odděluje retrieval od chatového modelu. `rag_schema.md` ale
správně doplňuje, že wiki není jen similarity search: zdroje mají zůstat
neměnné a odpovědi mají uvádět původ. Přiložený jedenáctistránkový PDF příklad
má nadpisy, sloupce, tabulky a stránky, proto chunk musí nést nejméně cestu,
hash, číslo stránky a sekci; holé dělení po znacích nestačí.

## Alternativy

| Varianta | Uložení | Silná stránka | Omezení pro tento případ |
|---|---|---|---|
| **SQLite + sqlite-vec + FTS5** | jeden `.db` soubor na odbornou wiki | SQL metadata, full-text i vector search, záloha prostým kopírováním souboru | `sqlite-vec` je pre-v1; ingestion a schema píšeme sami |
| **Chroma PersistentClient** | adresář (v něm SQLite + indexy) | nejkratší Python prototyp; přesně jej používá dodaná PDF ukázka | není to jeden soubor `wiki_base.db`; více frameworkové magie |
| **Qdrant Local** | adresář Qdrant storage | kvalitní filtry/payload, jasná cesta k serverové verzi; používá jej Star Wars ukázka | pro malou osobní wiki je těžší a také nevytvoří jediný `.db` soubor |
| **LanceDB** | adresář s Lance tabulkami | embedded, sloupcová data a možnost růstu | pro lokální wiki nepotřebuje jeho datový formát ani indexy navíc |
| **FAISS + SQLite metadata** | index + samostatný `.db` | jednoduché a rychlé similarity hledání | dvě úložiště, vlastní synchronizace ID, filtrů a mazání |
| **PostgreSQL + pgvector** | databázový server | silné SQL, transakce a více uživatelů | vyžaduje provoz serveru; mimo současné „lokálně bez infrastruktury“ |

Oficiální dokumentace potvrzuje, že Chroma persistuje do zadaného adresáře,
LanceDB se připojuje k lokálnímu adresáři a Qdrant je běžně provozován jako
služba. Naproti tomu `sqlite-vec` je SQLite rozšíření bez serveru: vektory jsou
v tabulce `vec0`, metadata mohou být v SQLite a KNN dotaz je `SELECT`.

## Doporučení

**Pro tuto první verzi zvolit SQLite + sqlite-vec + FTS5 v jednom souboru pro
každou odbornou wiki.** `wiki_base.db` je výchozí, nikoli dogma: profil v
`cli_vector.json` určí dvojici zdrojová skupina/databáze, například
`gardening -> wiki_gardening.db`. To oddělí domény a přitom dovolí metadata i
následné citace vyjádřit normálním SQL; FTS5 doplní vektorové hledání o přesné
názvy, zkratky a identifikátory. Praktická budoucí struktura je `sources`
(cesta, hash, typ), `chunks` (text, stránka, sekce, pořadí) a vektorová
tabulka navázaná na `chunks`; FTS5 indexuje text chunků. Vše musí ukládat
jméno embedding modelu a jeho dimenzi, aby se nemíchaly nekompatibilní vektory.

Riziko je explicitní: `sqlite-vec` je stále pre-v1 a může měnit API. Proto má
`cli_vector.py` skrýt databázové operace za malý adapter a `verify` ověřovat
schéma, model a hashe zdrojů. Pokud wiki přeroste jeden lokální proces nebo
budou nutné bohatší filtry a vzdálený přístup, stejný datový model lze převést
do Qdrantu. Do té doby je Qdrant vhodná druhá volba, ne výchozí implementace.

## Zdroje

* Dodané podklady: `rag_inspiration/rag_schema.md`, ukázka
  `Retrieval-Augmented-Generation-main` (Chroma/PDF),
  `Star-Wars-Movie-Expert-main` (Qdrant) a `vector_db_cz.md`.
* [sqlite-vec: vector search v SQLite](https://alexgarcia.xyz/sqlite-vec/) a
  [stav projektu a upozornění pre-v1](https://github.com/asg017/sqlite-vec).
* [Chroma PersistentClient](https://docs.trychroma.com/docs/run-chroma/cloud-client?lang=typescript),
  [LanceDB local connection](https://lancedb.github.io/lancedb/python/python/),
  [Qdrant local quickstart](https://qdrant.tech/documentation/quick-start/),
  [FAISS](https://github.com/facebookresearch/faiss) a
  [pgvector](https://github.com/pgvector/pgvector).
