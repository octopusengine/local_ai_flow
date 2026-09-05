Model: gemma4:latest | Parametry: task_base.json, cz | temperature: 0.5 | num_predict: 2048 | num_ctx: 4096 | repeat_penalty: 1.1 | think: false | seed: 397971  
Čas: 143,2 s | Tokeny/s: ≈ 9,3 (odhad, 3 znaky/token)

---

Zde je postupná diagnostika pro určení zdroje chyby HTTP 404 při komunikaci s Ollamou z Pythonu.

---

### Diagnostický plán (Krok za Krokem)

#### Krok 1: Ověření dostupnosti základního API endpointu (Adresa serveru)

Nejprve musíte potvrdit, že je váš Python kód cílen do správné adresy a portu.

**Diagnostický příkaz/Akce:**
Použijte `curl` z terminálu na stejném zařízení jako aplikace nebo z jiného počítače v síti (pokud je Ollama vzdálená). Zkuste se připojit k základnímu API endpointu, který by měl být vždy dostupný.

```bash
# Předpoklad: Ollama běží lokálně na portu 11434
curl http://localhost:11434/api/generate -d '{"model": "llama2", "prompt": "test"}'
```

**Interpretace výsledků:**

*   **Úspěch (HTTP 200 OK):** Pokud dostanete odpověď (i když je to jen chybová zpráva, ale *nějaká* data), znamená to, že **adresa serveru (`http://localhost:11434`) je správná a Ollama běží.** Problém pravděpodobně leží v API endpointu nebo modelu.
*   **HTTP 404 Not Found:** Znamená, že na dané adrese neexistuje žádný endpoint s názvem `/api/generate`. **Zkontrolujte dokumentaci Ollamy!** (Standardní endpointy jsou obvykle `http://localhost:11434/api/...`).
*   **Connection Refused / Timeout:** Znamená, že Python aplikace nemůže vůbec k serveru dosáhnout. **Řešení:** Ověřte, že je Ollama skutečně spuštěna a není zablokována firewallem.

---

#### Krok 2: Testování specifického API endpointu (API Endpoint)

Pokud byl Krok 1 úspěšný, ale stále dostáváte 404, problém může být v konkrétní cestě (`/api/...`).

**Diagnostický příkaz/Akce:**
Vyzkoušejte jiný známý a základní endpoint, např. `/api/tags`, který má pouze číst seznam dostupných modelů (pokud je to možné).

```bash
curl http://localhost:11434/api/tags
```

**Interpretace výsledků:**

*   **Úspěch (HTTP 200 OK):** Endpointy jsou pravděpodobně správné. Problém je v kombinaci endpointu a modelu nebo ve formátování dat z Pythonu.
*   **HTTP 404 Not Found:** Potvrzuje to, že **konkrétní API cesta**, kterou používá váš Python kód (např. `/api/generate` vs. `/generate`), je špatná.

---

#### Krok 3: Testování dostupnosti modelu (Chybějící Model)

Pokud se dostanete do endpointu, ale stále selháváte, zkontrolujte, zda skutečně existuje model, který předáváte v požadavku.

**Diagnostický příkaz/Akce:**
Použijte `ollama list` (který už funguje) k získání seznamu dostupných modelů. Poté se pokuste vybrat z tohoto seznamu **konkrétní model** a ověřit ho v požadavku.

1.  **Získejte seznam:**
    ```bash
    ollama list
    # Výsledek: llama2, mistral, phi3
    ```
2.  **Vyzkoušejte generování s *známým* modelem:** (Použijte model z výpisu)
    ```bash
    curl -X POST http://localhost:11434/api/generate -d '{
        "model": "llama2", 
        "prompt": "Jaké je hlavní město Czechí?", 
        "stream": false
    }'
    ```

**Interpretace výsledků:**

*   **Úspěch (HTTP 200 OK):** Všechny části jsou správné. Chyba byla v kódu, který předával název modelu (např. psali `Llama-2` místo `llama2`).
*   **HTTP 404 Not Found / HTTP 500 Internal Error:** Pokud je model v seznamu (`ollama list`), ale stále dostáváte chybu při volání endpointu, může to značit **problém s instalací modelu nebo s ověřením jeho licence/verze**, a problém je na straně Ollamy.

---

### Shrnutí diagnostiky pro Python

| Symptom v `curl` / Testování | Pravděpodobná příčina chyby 404 | Co zkontrolovat v kódu |
| :--- | :--- | :--- |
| **Krok 1 selhává (Timeout/Refused)** | Ollama není spuštěna nebo je blokována. | Spusťte `ollama serve` a ověřte síťové nastavení. |
| **Krok 1 selhává (404 na `/api/...`)** | Nesprávná základní adresa/port. | Zkontrolujte, zda se Python připojuje k `http://localhost:11434`. |
| **Krok 2 selhává (404)** | Špatný API endpoint (cesta). | Ověřte přesnou cestu v dokumentaci Ollamy (např. je to `/api/generate` nebo jen `/generate`). |
| **Krok 3 selhává (404)** | Model není rozpoznán na daném endpointu. | Ujistěte se, že název modelu (`"model": "..."`) přesně odpovídá výstupu `ollama list`. |