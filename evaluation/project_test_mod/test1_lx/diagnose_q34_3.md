Model: qwen3.5:4b | Parametry: task_base.json, cz | temperature: 0.5 | num_predict: 2048 | num_ctx: 4096 | repeat_penalty: 1.1 | think: false | seed: 970761  
Čas: 108,2 s | Tokeny/s: ≈ 9,7 (odhad, 3 znaky/token)

---

Zde je stručný návod pro diagnózu problému s Ollama v Pythonu:

### 1. Zkontrolujte, zda běží správný model (Chybný endpoint)
Python aplikace pravděpodobně volí konkrétní model (`/v1/chat/completions`), ale ve vašem repozitářiu není tento model nainstalován nebo má jinou verzi.

*   **Příkaz:** `ollama list`
    *   **Výsledek:** Zobrazí seznam dostupných modelů (např. `llama2`, `mistral`). Pokud vidíte jen starší verze a vaše app očekává novější, může být endpoint neplatný pro tento kontext nebo chybějící parametr modelu v požadavku.
*   **Příkaz:** `ollama show <model_název>` (např. `ollama show llama2`)
    *   **Výsledek:** Ukaže detaily modelu, včetně verze (`version`). Porovnejte tuto verzi s tím, co očekává vaše aplikace.

### 2. Zkontrolujte přesnost URL a port (Chybná adresa serveru)
Python `requests` modul může hledat na špatném portu nebo doméně. Standardní Ollama běží na portu 11434, ale někdy se mění.

*   **Příkaz:** `curl http://localhost:11434/api/tags`
    *   **Výsledek (200 OK):** Server je spustěn a API funguje. Pokud Python volá `/v1/...`, ale curl to nedokáže, zkontrolujte port v kódu aplikace.
*   **Příkaz:** `curl http://localhost:8080/api/tags` (pokud používáte jiný port)
    *   **Výsledek (404):** Znamená špatný port nebo adresa serveru není správně nastavena v Python kódu.

### 3. Testujte konkrétní endpoint a chybu modelu
Pokud je server na, ale dostáváte HTTP 404 při volání `/v1/chat/completions`, může jít o chybějící model nebo nesprávný způsob volání API (Ollama podporuje starší `/api/generate` i nový `/v1`).

*   **Příkaz:** `curl http://localhost:11434/v1/chat/completions -d '{"model": "mistral", "messages": [{"role":"user","content":"test"}]}'`
    *   **Výsledek (206/JSON):** Model existuje a API funguje. Pokud Python volá jinou cestu, změňte ji na `/v1/chat/completions`.
*   **Příkaz:** `curl http://localhost:11434/generate -d '{"model": "mistral", "prompt":"test"}'` (starší API)
    *   **Výsledek (206/JSON):** Pokud tento příkaz funguje, ale `/v1/chat/completions` ne, může být vaše aplikace nastavena na starší protokol nebo model.

### Shrnutí diagnostiky v Pythonu
Pro rychlou kontrolu přímo z kódu použijte:

```python
import requests

# Test 1: Existence serveru a tagů (Endpoint /api/tags)
resp = requests.get("http://localhost:11434/api/tags")
print(f"Test tagů: {resp.status_code}") 
# Výsledek != 200 -> špatný port/adresa

if resp.status_code == 200:
    models = [m['name'] for m in resp.json()]
    
    # Test 2: Existence konkrétního modelu (Endpoint /v1/chat/completions)
    payload = {"model": "mistral", "messages": [{"role": "user", "content": "test"}]}
    try:
        r_chat = requests.post("http://localhost:11434/v1/chat/completions", json=payload, timeout=2)
        print(f"Test modelu mistral (v1): {r_chat.status_code}") 
        # Výsledek 404 -> Model 'mistral' neexistuje nebo špatná verze
        
    except Exception as e:
        print(f"Chyba při volání API: {e}")
```

**Důležité:** Pokud dostáváte HTTP 404, nejčastěji znamená to buď **neexistující model** v repozitáři (řešeno `ollama pull <model>`) nebo **nesprávný port/adresa**.