Model: qwen3.5:latest | Parametry: task_base.json, cz | temperature: 0.5 | num_predict: 2048 | num_ctx: 4096 | repeat_penalty: 1.1 | think: false | seed: 898876  
Čas: 74,8 s | Tokeny/s: ≈ 5,4 (odhad, 3 znaky/token)

---

Zde je stručný návod k diagnóze problému s Ollama (HTTP 404):

1. **Ověření dostupnosti serveru**
   *Příkaz:* `curl http://localhost:11434`
   *Výsledek:* Pokud vrátí JSON `{ "error": ... }`, je server spuštěn, ale API endpoint neexistuje (chybí prefix `/api/`). Pokud vrátí chybu o připojení, špatně je nastaven port nebo firewall.

2. **Ověření správného URL pro modely**
   *Příkaz:* `curl http://localhost:11434/api/tags`
   *Výsledek:* Pokud vrátí seznam `{ "models": [...] }`, API funguje a port je správný. Chybějící endpoint `/api/generate` nebo `/api/chat` se zde projeví, pokud použijete špatnou cestu (např. `http://localhost:11434/api/...`).

3. **Ověření existence konkrétního modelu**
   *Příkaz:* Zkontrolujte výstup z kroku 2 nebo spusťte `ollama list`.
   *Výsledek:* Pokud je model v seznamu, ale Python ho nedokáže načíst při volání `/api/generate`, může jít o problém s verzí modelu (např. požaduje starší verzi) nebo chybějícímu prefixu v kódu aplikace (`/v1` vs `//`).

4. **Rychlé řešení pro Python**
   Ujistěte se, že URL ve vašem Python skriptu obsahuje správný prefix (obvykle `/api/generate`) a model je uveden přesně takovým způsobem, jak jej Ollama registruje (`ollama list`).