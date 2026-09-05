Model: ornith:9b | Parametry: task_base.json, cz | temperature: 0.5 | num_predict: 2048 | num_ctx: 4096 | repeat_penalty: 1.1 | think: false | seed: 376347  
Čas: 210,0 s | Tokeny/s: ≈ 4,6 (odhad, 3 znaky/token)

---

# Diagnóza HTTP 404 v Ollama s Pythonem – Krok za krokem

## 1. Zkontroluj, že Ollama běží na správné adrese

```bash
curl http://localhost:11434
```

**Očekávaný výsledek:**  
`{"error": "no models"}` nebo `{"status": "running"}` (závisí na verze).

Pokud dostaneš jinou chybu nebo se nic nevrací, Ollama běžící není. Zkus:
```bash
ollama serve
```
a pak znovu `curl http://localhost:11434`.

---

## 2. Zjisti, které modely jsou nainstalovány

```bash
ollama list
```

**Výsledek ukáže seznam dostupných modelů**, např.:
```
NAME    ID               SIZE
llama2  sha256:abc123... 1.3 GB
mistral sha256:def456... 4.0 GB
```

Pokud je seznam prázdný, nainstaluj model:
```bash
ollama pull llama2
```

---

## 3. Zkus požadavek přímo přes curl (bez Pythonu)

```bash
curl http://localhost:11434/api/generate -d '{
  "model": "llama2",
  "prompt": "Say hello"
}'
```

**Možné výsledky a jejich význam:**

| Výsledek | Znamená to |
|----------|-----------|
| Vrací `{"response": "..."}` | ✅ API funguje, model existuje |
| `"error":"model not found"` (HTTP 406) | ❌ Model neexistuje → spouštíš `ollama list` |
| HTTP 404 | ❌ Buď špatná cesta URL, nebo endpoint neexistuje |
| HTTP 503 / timeout | ⚠️ Ollama běžící není nebo je přetížený |

---

## 4. Zjisti přesnou cestu API v Pythonu

Pokud používáš `requests`, zkus:

```python
import requests

# Test základního endpointu
resp = requests.get("http://localhost:11434")
print(resp.status_code, resp.text)

# Test generace s modellem
payload = {
    "model": "llama2",
    "prompt": "Hello"
}
resp = requests.post("http://localhost:11434/api/generate", json=payload)
print(resp.status_code, resp.text)
```

---

## 5. Pokud používáš chat endpoint místo generate

Pokud tvůj kód volá `/api/chat` namísto `/api/generate`, zkus:

```python
payload = {
    "model": "llama2",
    "messages": [{"role":"user","content":"Hello"}]
}
resp = requests.post("http://localhost:11434/api/chat", json=payload)
print(resp.status_code, resp.text)
```

**Poznámka:** Starší verze Ollama nepodporovaly `/api/chat`, jen `/api/generate`. Pokud máš novější verzi (≥ 0.1.27), oba endpointy fungují.

---

## 6. Zkontroluj, zda se v Pythonu používá správný model

Častá chyba: v kódu je např. `"model": "llama2"` ale v `ollama list` je nainstalován jiný model (např. `"codellama"`). Vždy porovnej jméno z Pythonu s výpisem `ollama list`.

---

## Shrnutí – co řešit podle situace:

| Problém | Řešení |
|---------|--------|
| Ollama běžící není | Spusť `ollama serve` a restartuj Python |
| Špatná URL (např. `/v1/chat/completions`) | Použij oficiální endpointy: `/api/generate` nebo `/api/chat` |
| Chybějící model v požadavku | Nainstaluj ho `ollama pull <model>` |
| Model existuje, ale API nepracuje | Zkus curl příkaz z bodu 3 – pokud i tam chyba, je to problém na straně Ollamy |

Tímto postupem rozlišíš, zda je chyba v adrese serveru, endpointu nebo modelu.