Model: gpt-oss:latest | Parametry: task_base.json, cz | temperature: 0.5 | num_predict: 2048 | num_ctx: 4096 | repeat_penalty: 1.1 | think: false | seed: 346966  
Čas: 111,9 s | Tokeny/s: ≈ 7,3 (odhad, 3 znaky/token)

---

**Diagnostika 404 v Python aplikaci používající Ollama**

| Krok | Co testovat | Příkaz / kód | Co výsledek znamená |
|------|-------------|--------------|---------------------|
| 1 | **Ověřit, že server je běžící a poslouchá na správném portu** | ```bash\ncurl -s http://localhost:11434/api/tags\n``` | *200 OK* → server funguje. <br>*Connection refused / timeout* → server neběží nebo je špatná adresa/port. |
| 2 | **Zkontrolovat základní API endpoint `/api`** | ```bash\ncurl -s http://localhost:11434/api\n``` | *200 OK* (nebo jednoduchý JSON) → endpoint existuje. <br>*404* → špatná adresa nebo port. |
| 3 | **Ověřit, že požadovaný model je nainstalován** | ```bash\ncurl -s http://localhost:11434/api/tags | jq .models[].name\n``` | Seznam dostupných modelů. Pokud vámi zvolený model v seznamu chybí → *missing model*. |
| 4 | **Testovat konkrétní endpoint pro generování** (např. `/api/generate`) | ```bash\ncurl -s -X POST http://localhost:11434/api/generate \\\n     -H "Content-Type: application/json" \\\n     -d '{"model":"nazev-modelu","prompt":"test"}'\n``` | *200* → endpoint funguje. <br>*404* s JSON `{"error":"...missing model..."}` → model neexistuje. <br>*404* bez takové zprávy → chyba v URL (např. `/api/generate/` místo `/api/generate`). |
| 5 | **Zkontrolovat, že Python používá stejnou URL** | ```python\nimport requests\nresp = requests.get('http://localhost:11434/api')\nprint(resp.status_code, resp.text)\n``` | Pokud kód vrací 404 → chyba v `base_url` nebo portu v aplikaci. |
| 6 | **Vyhledat chybu ve výstupu serveru** (pokud je zapnutý log) | ```bash\njournalctl -u ollama.service -f   # pokud používáte systemd\necho "logy se zobrazí"```

### Co hledat v odpovědi

- **`Connection refused / timeout`** – špatná adresa/port nebo server neběží.  
- **`404 Not Found` s JSON obsahem** – endpoint existuje, ale požadovaný model není nainstalován (většinou `{"error":"model not found"}`).  
- **`404 Not Found` bez JSON** – špatná cesta v URL nebo nesprávný port.  

### Shrnutí kroků

1. **Ověř server a port** (`curl /api`).  
2. **Zkontroluj, že endpoint `/api/generate` existuje** (nebo jiný, který používáš).  
3. **Projdi seznam dostupných modelů** (`/api/tags`).  
4. **Vyzkoušej požadavek s konkrétním modelem** a sleduj JSON chybu.  
5. **Ujisti se, že Python používá stejný `base_url`** jako testy v terminálu.  

Tímto postupem rychle odhalíš, jestli je problém v adrese serveru, nesprávném endpointu nebo chybějícím modelu.