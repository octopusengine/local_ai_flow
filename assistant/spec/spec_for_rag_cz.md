# RAG pro specifikace

## Co je RAG

RAG (Retrieval-Augmented Generation) je technika, kdy model před generováním odpovědi nejdřív **vyhledá relevantní informace z externího zdroje** (databáze, soubory, dokumenty) a ty pak vloží do kontextu jako podklad pro odpověď. Řeší dva základní problémy malých/lokálních modelů: omezené znalosti (co se nevešlo do trénování nebo je novější) a omezenou kontextovou paměť (nejde nacpat celou dokumentaci najednou).

### Pipeline

1. **Indexace** — dokumenty rozsekáš na kousky (chunks), každý převedeš na vektor (embedding) a uložíš do vektorové databáze.
2. **Retrieval** — dotaz uživatele taky převedeš na embedding a najdeš nejpodobnější chunky (kosinová podobnost apod.).
3. **Augmentace** — nalezené chunky vložíš do promptu jako kontext.
4. **Generace** — model odpoví na základě dotazu + vloženého kontextu.

### Ukázka: základní retrieval

```python
from sentence_transformers import SentenceTransformer
import numpy as np

embedder = SentenceTransformer("all-MiniLM-L6-v2")

docs = ["Python je interpretovaný jazyk...", "MCP je protokol pro nástroje..."]
doc_vectors = embedder.encode(docs)

def retrieve(query, k=2):
    q_vec = embedder.encode([query])[0]
    sims = doc_vectors @ q_vec / (
        np.linalg.norm(doc_vectors, axis=1) * np.linalg.norm(q_vec)
    )
    top_k = np.argsort(sims)[::-1][:k]
    return [docs[i] for i in top_k]

context = "\n".join(retrieve("co je MCP?"))
prompt = f"Kontext:\n{context}\n\nOtázka: co je MCP?\nOdpověz na základě kontextu."
```

V kontextu lokálního malého modelu s nástroji v Pythonu je RAG jen další nástroj stejného typu jako `read_file` — funkce `retrieve(query)` volaná jako tool call nebo předřazená před prompt. Vektorovou DB (FAISS, Chroma, LanceDB...) lze mít lokálně jako soubor/proces vedle sebe, bez potřeby MCP.

### Obecné důležité detaily

- **Velikost chunků** — moc velké kousky = míň přesný retrieval a plýtvání kontextem; moc malé = ztráta souvislostí. Obvykle 200–500 tokenů s překryvem.
- **Malý model = malé okno** — je potřeba hlídat, kolik textu retrieval vrátí, ať se vejde i dotaz a odpověď.
- **Kvalita embedding modelu** ovlivňuje výsledek víc než kvalita LLM samotného.
- **"Lost in the middle"** — i relevantní info uprostřed dlouhého kontextu model občas ignoruje; na pořadí chunků záleží.
- **Halucinace i přes RAG** — model může kontext ignorovat. Pomáhá explicitní instrukce ("odpověz JEN na základě kontextu, jinak řekni nevím").
- **Aktualizace indexu** — snadné přidat nová data přeindexováním, na rozdíl od fine-tuningu.
- **Hybrid search** — čistě vektorové vyhledávání někdy míjí přesné shody (názvy, kódy); kombinace s keyword/BM25 vyhledáváním bývá spolehlivější.

## RAG a specifikace

Specifikace (technická dokumentace, API specs, projektové specs) jsou typický kandidát na RAG index, protože:

- **Jsou statické a strukturované** — nemění se každou minutu, index nemusí být přebudováván pořád dokola.
- **Bývají dlouhé** — celá spec se často ani nevejde do promptu malého modelu; RAG vytáhne jen relevantní část (sekci, endpoint, parametr...).
- **Přesnost je kritická** — u specifikace nechceš, aby si model "domýšlel" detail; RAG dá přesný citovaný text místo halucinace.
- **Structured chunking se hodí extra dobře** — spec dokumenty mají přirozenou strukturu (nadpisy, sekce, číslované požadavky), takže chunkování podle sekcí dává lepší výsledky než u volného textu.

### Detaily specificky pro spec dokumenty

- **Chunkuj podle struktury, ne podle délky** — jedna sekce/požadavek = jeden chunk, i když to znamená nestejnou velikost. Rozseknutí requirementu napůl je horší než nekonzistentní velikost chunků.
- **Ulož metadata s chunkem** — číslo sekce, verzi dokumentu, nadpis. Model pak může citovat přesně ("podle sekce 4.2...") místo vágního odkazu na dokumentaci.
- **Verzování** — pokud se spec časem mění, ukládej verzi/datum k chunku, ať RAG nenamíchá starou a novou verzi dohromady.
- **Přesné termíny > sémantická podobnost** — specifikace často obsahují přesné názvy polí, kódy chyb, verze API. Čistě vektorový retrieval je někdy přehlédne. Hybrid search (vektor + keyword/BM25) je tu obzvlášť užitečný.
- **"Must / should / may" jazyk** — pokud je spec psaná v RFC stylu (MUST, SHOULD, MAY), stojí za to tohle zachovat v chunku doslovně, protože nese normativní váhu — parafráze by mohla nechtěně změnit význam požadavku.

### Ukázka: chunkování podle sekcí + metadata

```python
import re

def chunk_spec_by_sections(text: str, doc_version: str):
    """Rozseká spec dokument podle nadpisů sekcí (např. '## 4.2 Název') 
    a ke každému chunku přidá metadata."""
    pattern = re.compile(r"^##\s+(\d+(\.\d+)*)\s+(.+)$", re.MULTILINE)
    matches = list(pattern.finditer(text))

    chunks = []
    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        section_number = m.group(1)
        section_title = m.group(3)
        body = text[start:end].strip()

        chunks.append({
            "section": section_number,
            "title": section_title,
            "text": body,
            "doc_version": doc_version,
        })
    return chunks

# příklad použití
spec_text = """
## 4.1 Autentizace
Klient MUSÍ poslat platný token v hlavičce Authorization.

## 4.2 Rate limiting
Server MŮŽE odmítnout požadavek při překročení limitu 100 req/min.
"""

chunks = chunk_spec_by_sections(spec_text, doc_version="v1.3")
for c in chunks:
    print(f"[{c['section']} {c['title']}] ({c['doc_version']})")
    print(c["text"])
```

### Ukázka: hybrid search (vektor + keyword)

```python
def hybrid_search(query, chunks, doc_vectors, embedder, k=3, keyword_boost=0.2):
    """Kombinuje vektorovou podobnost s jednoduchým keyword matchem,
    aby se nepřehlédly přesné termíny (názvy polí, kódy chyb...)."""
    q_vec = embedder.encode([query])[0]
    scores = []
    for chunk, vec in zip(chunks, doc_vectors):
        sim = (vec @ q_vec) / (
            (vec ** 2).sum() ** 0.5 * (q_vec ** 2).sum() ** 0.5
        )
        keyword_hit = 1.0 if query.lower() in chunk["text"].lower() else 0.0
        scores.append(sim + keyword_boost * keyword_hit)

    ranked = sorted(zip(chunks, scores), key=lambda x: x[1], reverse=True)
    return [c for c, _ in ranked[:k]]
```

## Shrnutí

Specifikace jsou jeden z nejlepších případů pro RAG — jsou dlouhé, strukturované, vyžadují přesnost a mění se jen občas (verzovaně). Klíčové je chunkovat podle struktury dokumentu (ne podle pevné délky), ukládat metadata (sekce, verze) a nespoléhat jen na sémantickou podobnost, ale kombinovat ji s přesným vyhledáváním klíčových termínů.
