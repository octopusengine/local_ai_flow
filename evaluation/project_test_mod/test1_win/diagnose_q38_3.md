Model: qwen3.8:latest | Parametry: task_base.json, cz | temperature: 0.5 | num_predict: 2048 | num_ctx: 4096 | repeat_penalty: 1.1 | think: false | seed: 51581  
Čas: 275,4 s | Tokeny/s: ≈ 1,6 (odhad, 3 znaky/token)

---

1. **Ověřte dostupnost serveru**
   Spusťte: `curl -i http://localhost:11434/api/version`
   *Výsledek:* `200 OK` a JSON s verzí = Server běží na správném portu.
   *Chyba:* `Connection refused` nebo `Timeout` = Ollama neběží, je blokovaná firewallem nebo běží na jiném hostu/portu.

2. **Ověřte existenci modelu**
   Spusťte: `curl -i http://localhost:11434/api/tags`
   *Výsledek:* JSON seznam modelů = API funguje. Hledejte ve výstupu název svého modelu (např. `"name": "llama2"`). Pokud ho tam není, model není stažen (`ollama pull [nazev]`).

3. **Ověřte správný endpoint pro dotaz**
   Spusťte: `curl -i http://localhost:11434/api/generate -d '{"model": "llama2", "prompt": "Hi"}'`
   *Výsledek:* `200 OK` = Model existuje a endpoint je správně.
   *Chyba:* `404 Not Found` s textem `"model not found"` = Model v systému neexistuje (viz krok 2).
   *Chyba:* `404 Not Found` bez konkrétní zprávy o modelu = Nepravý URL path ve vaší Python aplikaci (Ollama používá `/api/generate`, `/api/chat` nebo `/v1/chat/completions`, ne `/predict`).

**Shrnutí pro Python:**
*   404 + "model not found" → Spusťte `ollama pull [nazev]`.
*   404 + jiný text → Zkontrolujte, zda v kódu používáte správnou cestu (např. `http://localhost:11434/api/generate` místo `http://localhost:11434/predict`).