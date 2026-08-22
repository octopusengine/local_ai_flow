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
