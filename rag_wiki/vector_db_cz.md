# Vektorová databáze pro malé lokální testy

Kontext: lokální běh malého LLM modelu, nástroje přímo v Pythonu, žádná infrastruktura navíc (žádný server, žádný Docker).

## Doporučení podle velikosti úlohy

### Nejmenší testy (desítky až stovky dokumentů), minimum závislostí
**FAISS** (`faiss-cpu`) — v podstatě jen knihovna nad numpy, žádná perzistence/schema navíc, retrieval logiku řídíš sám. Ideální, když chceš vidět "pod kapotu" a embeddings si počítáš jinde (např. `sentence_transformers`).

```python
import faiss
import numpy as np

dim = 384  # podle embedding modelu
index = faiss.IndexFlatL2(dim)

vectors = np.random.rand(10, dim).astype("float32")  # tvoje embeddings
index.add(vectors)

query = np.random.rand(1, dim).astype("float32")
distances, indices = index.search(query, k=3)
```

### Chceš metadata, filtrování, jednoduchou perzistenci na disk
**ChromaDB** — běží embedded (nic se nespouští jako služba), umí ukládat na disk, má vestavěné embedding funkce (nebo dodáš vlastní), umí metadata filtry. Asi nejpohodlnější volba pro solo testování.

```python
import chromadb

client = chromadb.PersistentClient(path="./chroma_db")
collection = client.get_or_create_collection("specs")

collection.add(
    documents=["Klient MUSÍ poslat platný token...", "Server MŮŽE odmítnout..."],
    metadatas=[{"section": "4.1"}, {"section": "4.2"}],
    ids=["doc1", "doc2"],
)

results = collection.query(query_texts=["autentizace token"], n_results=2)
```

### Čistě lokální, jeden soubor, prostor pro pozdější škálování
**LanceDB** — ukládá data jako Lance formát (columnar, na disku), taky embedded. Hodí se, když chceš později růst bez migrace na jiný nástroj.

```python
import lancedb

db = lancedb.connect("./lancedb")
table = db.create_table("specs", data=[
    {"vector": [0.1, 0.2, 0.3], "text": "...", "section": "4.1"}
])

results = table.search([0.1, 0.2, 0.25]).limit(3).to_list()
```

## Shrnutí / doporučení

Pro setup s Python nástroji volanými přímo (žádné MCP, žádná extra infrastruktura) je **ChromaDB** nejpřirozenější volba: nulová konfigurace, embedded, perzistence na disk mezi běhy, integrovaný embedding krok (nemusíš ručně skládat `sentence_transformers` + FAISS zvlášť).

Pokud chceš minimální závislosti a psát retrieval logiku sám → **FAISS** je nejjednodušší na pochopení a nejrychlejší na rozjetí bez instalace čehokoliv navíc.

| Nástroj | Perzistence | Metadata/filtry | Závislosti | Vhodné pro |
|---|---|---|---|---|
| FAISS | Ne (nutno řešit ručně) | Ne (vlastní řešení) | Minimální | Pochopení principu, plná kontrola |
| ChromaDB | Ano (na disk) | Ano | Střední | Solo testování, rychlý start |
| LanceDB | Ano (columnar soubor) | Ano | Střední | Prototyp s výhledem na škálování |

## Referenční projekt: Star Wars Movie Expert

Projekt [andrisgauracs/Star-Wars-Movie-Expert](https://github.com/andrisgauracs/Star-Wars-Movie-Expert) je malý, přehledný příklad RAG nad filmovými scénáři. Jeho tok dat je:

```text
IMSDb HTML scénář
  -> BeautifulSoup: obsah <pre>
  -> LangChain Document {page_content, title}
  -> RecursiveCharacterTextSplitter
  -> OpenAI embedding
  -> Qdrant kolekce na disku
  -> similarity retrieval (k=15)
  -> prompt s kontextem -> chatový LLM -> odpověď
```

Konkrétně `main.py` stáhne tři scénáře původní trilogie, ze stránky vezme text elementu `<pre>` a každému dokumentu uloží metadata `title`. Při prvním běhu dělí text pomocí `RecursiveCharacterTextSplitter` na chunky o velikosti 2 500 znaků s překryvem 250 znaků. Prioritní separátory jsou hranice scén `INT.` / `EXT.`, potom odstavce, řádky a mezery. `add_start_index=True` přidává ke chunku polohu v původním dokumentu. Zdroj: [main.py](https://github.com/andrisgauracs/Star-Wars-Movie-Expert/blob/main/main.py).

Použitá vektorová databáze je **Qdrant** přes `qdrant-client` a `langchain-qdrant`. Klient se vytváří jako `QdrantClient(path="./qdrant_db")`, tedy v embedded/persistent režimu do adresáře, nikoli nutně jako samostatný server v Dockeru. Kolekce se jmenuje `star-wars-scripts`. Při existující kolekci ji kód znovu otevře; jinak vytvoří embeddingy pomocí `OpenAIEmbeddings(model="text-embedding-3-small")` a uloží dokumenty přes `QdrantVectorStore.from_documents`. Použitý chat model je `gpt-4o` s teplotou 0. Závislosti potvrzuje [pyproject.toml](https://github.com/andrisgauracs/Star-Wars-Movie-Expert/blob/main/pyproject.toml).

Pro dotaz vytvoří `vectorstore.as_retriever(search_kwargs={"k": 15})`. Retriever vloží vrácené úryvky do promptu, který LLM instruuje používat výhradně dodaný kontext a přiznat, že odpověď ve scénářích není. README popisuje stejný záměr a možnost později přejít z lokálního úložiště na vzdálený Qdrant: [README](https://github.com/andrisgauracs/Star-Wars-Movie-Expert#readme).

### Akademické zhodnocení vzoru

Je to dobrý **didaktický minimální prototyp**: odděluje ingest, index a generování odpovědi; metadata titulu a hranice scén dávají výsledkům základní provenienci; Qdrant lze provozovat lokálně. Naopak není to ještě robustní znalostní systém:

* `except Exception` rozhoduje, zda index existuje. Může tím zakrýt chybu připojení nebo poškozenou kolekci a nesmí být v produkčním řešení.
* Výsledek nevypisuje identifikátory chunků, skóre ani citaci zdroje. Instrukce v promptu sama o sobě negarantuje věrnost kontextu ani skutečné citování.
* Není evidována verze zdroje, hash souboru, verze chunkeru ani embedding modelu. Po změně zdroje/modelu nelze spolehlivě poznat, co reindexovat.
* `2 500` znaků, `250` znaků překryvu a `k=15` jsou rozumné pro scénáře, ale nejsou obecně optimální. Technickou dokumentaci, tabulky a kód je vhodné dělit strukturálně (nadpis/sekce/funkce), ne jen podle délky.
* Chybí vyhodnocení retrievalu (testovací otázky, očekávané zdroje, recall@k/MRR), filtrování metadat, prahování relevance a ochrana proti prompt injection uvnitř importovaných dokumentů.

Z toho plyne užitečný princip: RAG snižuje pravděpodobnost halucinace tím, že dává modelu dohledatelný kontext; nedělá však z modelu databázový dotazovací stroj ani nedokazuje pravdivost zdroje. Spolehlivost je třeba měřit zvlášť pro načtení zdroje, chunking, retrieval a odpověď.

## Vhodnost pro tento lokální Ollama projekt

Pro cíl „nachunkovat vlastní znalosti, najít relevantní pasáže a předat je lokálnímu modelu“ je architektura referenčního projektu vhodná, ale doporučuje se menší a průhlednější první verze:

1. **Qdrant Local jako výchozí backend.** `qdrant-client` umí perzistentní cestu na lokálním disku; získáme kolekce, payload/metadata a filtry bez serveru či Dockeru. Zároveň je to stejná technologie jako v referenci a pozdější přechod na Qdrant server nevyžaduje měnit datový model.
2. **Embedding přes lokální Ollama, ne přes OpenAI.** Rozhraní si má uložit jméno embedding modelu i dimenzi v metadatech kolekce. Index nesmí míchat vektory z různých modelů; změna modelu znamená novou kolekci nebo reindex.
3. **Nejprve retrieval, až potom `ask`.** Příkaz `search` má vracet chunk, zdroj, pořadí/skóre a metadata. Teprve když jsou výsledky kvalitní, `ask` z nich sestaví kontext pro `cli_ollama.py` a vedle odpovědi zobrazí zdroje.
4. **Provenience a idempotence od začátku.** Každý chunk by měl nést alespoň `id`, `source_path`, `source_sha256`, `source_type`, `section`, `chunk_index`, `start/end`, `chunker_version`, `embedding_model` a čas ingestu. Reindex pak mění pouze chunky ze změněného zdroje.

ChromaDB zůstává přiměřená alternativa pro úplně první experiment, FAISS pro studium similarity-searchu. Pro tento projekt ale **Qdrant Local** lépe vyvažuje nulovou infrastrukturu, perzistenci, metadata a možný budoucí růst. LangChain není nutná závislost: v první iteraci je jednodušší volat klienta Qdrantu a Ollama API přímo, aby byly data, parametry a chyby viditelné.

## Osnova `cli_vector.py`

Soubor `cli_vector.py` zatím záměrně pouze parsuje níže uvedené příkazy; nic neukládá, nestahuje ani nevolá Ollama. To dovoluje ustálit rozhraní a testy ještě před volbou konkrétní implementace.

| Příkaz | Účel | Důležité volby |
|---|---|---|
| `init` | založit/zkontrolovat schéma kolekce | `--collection`, `--embedding-model` |
| `ingest SOURCES…` | najít soubory, rozdělit je, embedovat a upsertovat | `--glob`, `--chunk-size`, `--chunk-overlap`, `--dry-run`, `--reindex` |
| `search QUERY` | vrátit dohledané chunky bez generování | `-k`, `--min-score`, `--where key=value` |
| `ask QUESTION` | sestavit RAG kontext a později volat chat model | `--model`, `-k`, `--show-context` |
| `inspect` | statistika, schéma a kolekce | `--collection` |
| `verify` | ověřit hashe zdrojů a kompatibilitu embeddingů | `--collection` |

Společné volby jsou `--store data/vector_db`, `--backend qdrant-local` (později také `chroma`/`faiss`) a `--json`. Před implementací je třeba rozhodnout zejména: podporované formáty zdrojů (nejprve `.md`, `.txt`, `.py`), tokenizér pro měření chunků, embedding model v Ollama a politiku pro odstranění chunků ze smazaného zdroje. Mazání či přepis celé kolekce by měl až případný budoucí příkaz vyžadovat explicitní potvrzení.
