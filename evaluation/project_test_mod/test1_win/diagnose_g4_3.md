Model: gemma4:latest | Parametry: task_base.json, cz | temperature: 0.5 | num_predict: 2048 | num_ctx: 4096 | repeat_penalty: 1.1 | think: false | seed: 856251  
Čas: 157,2 s | Tokeny/s: ≈ 8,2 (odhad, 3 znaky/token)

---

Zde je postupná diagnostika pro určení zdroje chyby HTTP 404 při komunikaci s Ollamou z Python aplikace.

Předpokládáme, že **`ollama list`** funguje, což potvrzuje, že lokální služba Ollama běží a základní síťová komunikace je funkční. Chyba 404 tedy pravděpodobně souvisí s adresováním nebo endpointem API.

---

### Krok 1: Ověření primární URL (Adresa Serveru)

Nejčastější příčina 404 je špatná základní adresa (host/port).

**Diagnostický krok:**
Zkuste provést volání k **základnímu API endpointu** pomocí `curl` z toho stejného kontextu, kde běží aplikace. Standardní lokální adresy pro Ollama jsou obvykle:
*   `http://localhost:11434/api/generate` (pro generování)
*   `http://localhost:11434/api/pull` (pro stažení modelů)

**Příklad testu:**
```bash
curl -X GET http://localhost:11434/api/version
```

**Interpretace výsledků:**
*   **Úspěch (HTTP 200 OK):** Pokud dostanete JSON odpověď obsahující verzi, znamená to, že **základní adresa (`http://localhost:11434`) je správná**. Problém je ve vašem kódu nebo v konkrétním endpointu.
*   **Chyba 404:** Znamená, že Ollama na portu `11434` nezná požadovaný základní cíl (i když by měl). Zkontrolujte, zda není Ollama spuštěna na jiném portu nebo hostiteli.

### Krok 2: Ověření API Endpointu (Cílový Cíl)

Pokud je základní URL správná, ale aplikace stále dostává 404, problém je v konkrétním cílém koncovém bodě (endpointu).

**Diagnostický krok:**
Použijte `curl` k testování **konkrétního endpointu**, který vaše Python aplikace volá. Nejčastěji se jedná o `/api/generate`.

**Příklad testu pro generování textu (nutné s JSON payloadem):**
```bash
curl -X POST http://localhost:11434/api/generate \
  -H "Content-Type: application/json" \
  -d '{
    "model": "llama2", 
    "prompt": "Hello world"
  }'
```

**Interpretace výsledků:**
*   **Úspěch (HTTP 200 OK):** API endpoint je správný. Problém je v **parametrizaci** (např. špatná struktura JSON, chybějící hlavička).
*   **Chyba 404:** Znamená to, že Ollama na tomto portu nezná cestu `/api/generate`. Může být nutné použít jiný endpoint nebo je vaše verze Ollamy starší a používá jinou strukturu.

### Krok 3: Ověření Modelu (Existující Model)

Pokud se dotáhnete správného endpointu, ale stále dostanete chybu, může to signalizovat problém s modelem. I když je to často chyba typu "Model not found" a ne vždy čistý 404, je důležité ho ověřit.

**Diagnostický krok:**
Váš kód musí explicitně odeslat název modelu, který byl úspěšně stažen pomocí `ollama pull <model_name>`. Zkuste vytvořit nejjednodušší volání generování s modelem, který *znáte* z výstupu `ollama list`.

**Příklad testu (pokud víte, že model "llama2" existuje):**
(Použijte stejný příkaz jako v Kroku 2, ale zajistěte si, že název modelu je přesně ten samý.)

**Interpretace výsledků:**
*   **Úspěch (HTTP 200 OK):** Model a endpoint fungují. Chyba je v kódu aplikace (např. špatné zpracování odpovědi).
*   **Chyba 404 nebo jiná chyba o modelu:** Zkontrolujte, zda jste model správně stáhnuli (`ollama pull <model>`) a zda název v API volání odpovídá názvu z `ollama list`.

---

### Shrnutí diagnostického procesu (Checklist)

| Problém | Testovací nástroj | Co testovat | Výsledek 404 znamená... | Řešení |
| :--- | :--- | :--- | :--- | :--- |
| **Adresa Serveru** | `curl` | `http://localhost:11434/api/version` | Port nebo základní host není dostupný. | Zkontrolujte, jestli je Ollama spuštěna a na jakém portu běží. |
| **API Endpoint** | `curl` | `POST http://localhost:11434/api/generate ...` | Cesta k API endpointu je špatná nebo neexistuje v aktuální verzi Ollamy. | Ověřte dokumentaci pro váš konkrétní model Ollamy a použijte správný cíl. |
| **Model** | `curl` (v rámci POST) | Model název v payloadu (`"model": "..."`) | Model není stažen nebo je špatně specifikován. | Spusťte `ollama pull <správní_název>` a ověřte název pomocí `ollama list`. |