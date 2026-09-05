Model: gpt-oss:latest | Parametry: task_base.json, cz | temperature: 0.5 | num_predict: 2048 | num_ctx: 4096 | repeat_penalty: 1.1 | think: false | seed: 453280  
Čas: 139,3 s | Tokeny/s: ≈ 5,9 (odhad, 3 znaky/token)

---

## Krok‑za‑krokovým průvodcem diagnostiky HTTP 404 při volání Ollama z Pythonu

| # | Akce | Příkaz / kód | Co hledáme | Co výsledek znamená |
|---|------|--------------|------------|---------------------|
| 1 | **Ověř, že se server běží na správném hostiteli a portu** | `curl -I http://localhost:11434/` <br> (nebo `telnet localhost 11434`) | Odpověď *200 OK* nebo *404 Not Found* je přítomnost služby. | **200** – server běží; pokračuj.<br>**404** – port není otevřený, špatný hostitel/port. |
| 2 | **Zkontroluj základní API endpoint `/api/tags` (nebo `/api/models`)** | `curl -sS http://localhost:11434/api/tags | jq .` | Seznam dostupných modelů. | Pokud dostaneš *404* s textem „Endpoint not found“, používáš špatnou URL (např. `/api/model`). |
| 3 | **Zkuste volat konkrétní endpoint, který má být podporován** | `curl -sS http://localhost:11434/api/generate` <br> (`-X POST -d '{"model":"llama2"}'`) | Odpověď by měla obsahovat JSON s *message* nebo *error*. | **404** + „endpoint not found“ → endpoint neexistuje (špatná verze API). |
| 4 | **Zkontroluj, zda požadovaný model existuje** | `curl -sS http://localhost:11434/api/tags | jq '.models[] | select(.name=="llama2")'` | Pokud je prázdný výstup → model není nainstalován. | **404** + „model not found“ v těle odpovědi – model chybí. |
| 5 | **Proveď test z Pythonu s detailní logikou**  

```python
import requests, json

URL = "http://localhost:11434/api/generate"
payload = {"model":"llama2","prompt":"Hello"}
r = requests.post(URL, json=payload)

print(r.status_code)
print(r.text)          # JSON s chybovou zprávou
```

| Výsledek | Co znamená |
|----------|------------|
| `200` | Úspěšné volání – model a endpoint fungují. |
| `404` + `"endpoint not found"` | Špatná URL (např. `/api/generatee`). |
| `404` + `"model not found"` | Model „llama2“ není nainstalován. |
| jiný kód | Problém je mimo model/endpoint (např. síť, autorizace). |

### Shrnutí diagnostických kroků

1. **Server běží?** – `curl -I` nebo `telnet`.  
2. **Endpoint existuje?** – `curl /api/tags`, `/api/generate`.  
3. **Model je nainstalován?** – `curl /api/tags | jq` a vyhledání jména modelu.  
4. **Python volání** – zkontroluj status code a tělo odpovědi.

Pokud po kroku 1 dostaneš 404, pravděpodobně používáš špatný host/port.  
Po kroku 2 je endpoint neexistující (např. chyba v URL).  
Po kroku 3 chybí model – nainstaluj ho pomocí `ollama pull <model>`.  

Tímto postupem rychle odhalíš, kde se 404 skrývá.