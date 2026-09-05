# RAG: aktualizace a bezpečná přestavba indexu

- `ingest` doplní chybějící embeddingy i nezměněných zdrojů. Již uložené chunky při doplňování zachovají svá ID.
- Změna velikosti nebo překryvu chunků automaticky vyvolá novou indexaci daného zdroje. `--chunk-overlap 0` je podporován.
- Starší databáze dostanou při otevření sloupec `sources.index_config`. Zdroje bez této informace se při příštím ingestu jednou přeindexují.
- James (`/ask`, RAG demo) i CLI (`search`, `context`, `--svg`) kontrolují embeddingový model databáze před voláním Ollamy. Při neshodě nastavte původní model, nebo databázi přestavte přes `--overwrite`. Samotná shoda dimenzí nestačí.
- RAG payload se v chatovém kontextu ukládá jako Markdown citace. Nadpisy uvnitř chunků, dotazů a údajů o zdroji nemohou vytvořit další sekci nebo předstírat historii konverzace. Zobrazení načteného kontextu zůstává beze změny.
- `--prune` odstraní zdroje, které již nejsou ve zdrojové skupině nebo webovém manifestu. Platí pro `ingest` i `ingest-wiki`. Dočasně nedostupné webové stránky zůstávají zachované. S `--no-web` se webové zdroje ani nemažou.
- Vyprázdnění existujícího lokálního souboru odstraní jeho staré chunky při běžném ingestu. Metadata zdroje zůstávají evidovaná.
- `--overwrite` vytvoří nový index v dočasné databázi a ověří jej. Teprve poté jej publikuje transakčně přes SQLite backup API. Chyba extrakce, embeddingů, ověření nebo stažení kterékoliv webové stránky ponechá původní index zachovaný. Přestavba vyžaduje místo pro nový index a dočasné soubory SQLite.
- Běžný ingest nadále potvrzuje změny po zdrojích. Po přerušení jej lze opakovat; stav `pending` zůstává nastaven, dokud některým chunkům chybí embeddingy.

Příklady:

```text
python cli_vector.py --db btc_cz ingest --no-embed
python cli_vector.py --db btc_cz ingest
python cli_vector.py --db btc_cz ingest --prune
python cli_vector.py --db btc_cz ingest --overwrite
```

Regresní testy: `python -m unittest tests.test_rag_regressions`.
