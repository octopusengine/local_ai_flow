# Ollama REST API – praktický přehled

Tento dokument popisuje komunikaci s lokálním serverem Ollama z příkazové řádky a z Pythonu. Je určený pro běžné lokální použití, například s modely `deepseek-r1:14b` nebo Qwen.

Oficiální API běží po instalaci standardně na adrese:

```text
http://localhost:11434/api
```

Aktuální referenční dokumentace: [Ollama API](https://docs.ollama.com/api/introduction).

## 1. Základní postup

1. Spusťte Ollamu (ve Windows ji obvykle spouští desktopová aplikace na pozadí).
2. Stáhněte model příkazem `ollama pull <model>`.
3. Odešlete HTTP požadavek na endpoint, například `POST /api/generate`.
4. Čtěte odpověď buď průběžně jako stream, nebo najednou jako jeden JSON objekt.

Rychlá kontrola, zda služba odpovídá:

```powershell
curl.exe http://localhost:11434/api/version
curl.exe http://localhost:11434/api/tags
```

## 2. Příkazy Ollama v terminálu

| Příkaz | Význam |
|---|---|
| `ollama serve` | Spustí API server. Nespouštějte jej podruhé, pokud již běží desktopová aplikace. |
| `ollama pull deepseek-r1:14b` | Stáhne model. |
| `ollama list` | Vypíše lokálně nainstalované modely. |
| `ollama run deepseek-r1:14b` | Otevře interaktivní chat v terminálu. |
| `ollama ps` | Ukáže modely právě načtené v paměti. |
| `ollama show deepseek-r1:14b` | Vypíše informace o modelu; přidejte `--modelfile` nebo `--parameters` podle potřeby. |
| `ollama create muj-model -f Modelfile` | Vytvoří vlastní model z `Modelfile`. |
| `ollama cp zdroj cil` | Vytvoří kopii/tag existujícího modelu. |
| `ollama rm model` | Odstraní lokální model. |
| `ollama stop model` | Uvolní právě načtený model z paměti. |

Příklady:

```powershell
ollama pull deepseek-r1:14b
ollama run deepseek-r1:14b
ollama list
ollama ps
```

## 3. Volba endpointu

| Endpoint | Metoda | Kdy jej použít |
|---|---:|---|
| `/api/generate` | POST | Jednorázový textový prompt. Nejjednodušší volba pro skript. |
| `/api/chat` | POST | Konverzace s historií zpráv, systémová instrukce, nástroje. |
| `/api/embed` | POST | Textové embeddingy/vektory pro vyhledávání RAG. |
| `/api/tags` | GET | Seznam stažených modelů. |
| `/api/ps` | GET | Modely nyní v RAM/VRAM. |
| `/api/show` | POST | Detail modelu, šablona, licence, parametry. |
| `/api/pull` | POST | Stažení modelu z registry; standardně streamuje průběh. |
| `/api/create` | POST | Vytvoření modelu z Modelfile či GGUF. |
| `/api/copy` | POST | Kopie/tag modelu. |
| `/api/delete` | DELETE | Smazání lokálního modelu. |
| `/api/version` | GET | Verze běžící Ollamy. |

Kompletní seznam a nejnovější schéma najdete v [referenci endpointů](https://docs.ollama.com/api/introduction).

## 4. `POST /api/generate` – jeden prompt

### Nejmenší požadavek

```json
{
  "model": "deepseek-r1:14b",
  "prompt": "Vysvětli stručně Newtonův druhý zákon.",
  "stream": false
}
```

Volání z PowerShellu:

```powershell
$body = @{
  model = "deepseek-r1:14b"
  prompt = "Kolik je 34 * 15?"
  stream = $false
} | ConvertTo-Json

Invoke-RestMethod `
  -Uri "http://localhost:11434/api/generate" `
  -Method Post `
  -ContentType "application/json" `
  -Body $body
```

### Struktura požadavku

```json
{
  "model": "deepseek-r1:14b",
  "prompt": "Text dotazu pro model",
  "system": "Volitelná systémová instrukce",
  "suffix": "Text za mezerou pro fill-in-the-middle modely",
  "stream": true,
  "think": true,
  "format": "json",
  "raw": false,
  "keep_alive": "5m",
  "options": {
    "temperature": 0.3,
    "num_ctx": 8192,
    "top_p": 0.9,
    "seed": 42
  }
}
```

| Pole | Typ | Význam |
|---|---|---|
| `model` | string | Povinný název modelu, včetně tagu podle potřeby. |
| `prompt` | string | Vstupní text. |
| `system` | string | Systémová instrukce pouze pro tento požadavek. |
| `suffix` | string | Text za doplňovaným místem; je určený pro FIM modely. |
| `images` | pole stringů | Obrázky zakódované Base64; vyžaduje multimodální model. |
| `stream` | boolean | `true` je výchozí; server vrací dílčí JSON řádky. `false` vrátí jeden JSON objekt. |
| `think` | boolean nebo úroveň | Zapne samostatný výstup reasoning. Podporované modely mohou přijmout `"low"`, `"medium"`, `"high"` nebo `"max"`. |
| `format` | `"json"` nebo JSON Schema | Vynutí JSON či konkrétní strukturovaný výstup. |
| `raw` | boolean | Vypne šablonu promptu modelu; používejte jen když víte, jak šablonu sestavit sami. |
| `keep_alive` | string/číslo | Jak dlouho nechat model v paměti, např. `"5m"`; `0` jej po odpovědi uvolní. |
| `options` | objekt | Parametry generování, popsané níže. |

`think` neznamená přístup k neveřejnému vnitřnímu uvažování. Zobrazí pouze reasoning, který konkrétní model a verze Ollamy vrací ve veřejném API.

### Ne-streamovaná odpověď

Při `"stream": false` přijde jeden objekt podobný tomuto:

```json
{
  "model": "deepseek-r1:14b",
  "created_at": "2026-07-13T10:00:00Z",
  "response": "Výsledkem je 510.",
  "thinking": "Nejprve spočítám 34 × 15...",
  "done": true,
  "done_reason": "stop",
  "total_duration": 2100000000,
  "load_duration": 450000000,
  "prompt_eval_count": 18,
  "prompt_eval_duration": 80000000,
  "eval_count": 36,
  "eval_duration": 1500000000
}
```

Nejdůležitější pole:

| Pole | Význam |
|---|---|
| `response` | Text odpovědi. |
| `thinking` | Reasoning, pokud jej podporovaný model vrací a bylo povoleno `think`. |
| `done` | `true` v poslední/kompletní odpovědi. |
| `done_reason` | Důvod ukončení, například `stop`. |
| `*_duration` | Délky v **nanosekundách**. |
| `prompt_eval_count`, `eval_count` | Počet tokenů vstupu a výstupu. |

## 5. Streamování odpovědi a reasoning

API standardně streamuje ve formátu **NDJSON** (`application/x-ndjson`): každý řádek je samostatný platný JSON objekt. Text z jednotlivých řádků se skládá za sebe.

```text
{"response":"Vý","thinking":"Nejprve ","done":false}
{"response":"sledek","thinking":"spočítám...","done":false}
{"response":" je 510.","done":true,"done_reason":"stop"}
```

Při zapnutém reasoning čtěte **obě** pole: `response` pro výslednou odpověď a `thinking` pro reasoning. U starších kombinací modelu a Ollamy může být reasoning součástí `response` v blocích `<think>...</think>`.

### Python: stream `response` i `thinking`

```python
import json
import requests

payload = {
    "model": "deepseek-r1:14b",
    "prompt": "Kolik je 34 * 15?",
    "stream": True,
    "think": True,
    "options": {"temperature": 0.2},
}

with requests.post(
    "http://localhost:11434/api/generate",
    json=payload,
    stream=True,
    timeout=120,
) as response:
    response.raise_for_status()
    for line in response.iter_lines(decode_unicode=True):
        if not line:
            continue

        chunk = json.loads(line)
        if thinking := chunk.get("thinking"):
            print(thinking, end="", flush=True)
        if text := chunk.get("response"):
            print(text, end="", flush=True)

print()
```

Chcete-li mít reasoning a finální odpověď vizuálně oddělené, ukládejte části do dvou proměnných a zobrazte je až po `done: true`.

## 6. `POST /api/chat` – konverzace s historií

Pro chat posílejte pole `messages`, ne jeden `prompt`.

```json
{
  "model": "qwen3:8b",
  "messages": [
    {
      "role": "system",
      "content": "Odpovídej česky a stručně."
    },
    {
      "role": "user",
      "content": "Jak funguje index v databázi?"
    }
  ],
  "stream": false,
  "think": false,
  "options": {
    "temperature": 0.4
  }
}
```

Odpověď je podobná, ale text je v `message.content` a reasoning v `message.thinking`:

```json
{
  "model": "qwen3:8b",
  "message": {
    "role": "assistant",
    "content": "Index je datová struktura...",
    "thinking": ""
  },
  "done": true
}
```

Pro další tah konverzace přidejte předchozí odpověď asistenta do pole `messages` a pak novou zprávu uživatele. Server historii sám nedrží.

### Python: jednoduchý chat

```python
import requests

messages = [
    {"role": "system", "content": "Odpovídej česky."},
    {"role": "user", "content": "Vysvětli mi HTTP status 404."},
]

response = requests.post(
    "http://localhost:11434/api/chat",
    json={"model": "qwen3:8b", "messages": messages, "stream": False},
    timeout=120,
)
response.raise_for_status()
print(response.json()["message"]["content"])
```

## 7. Nastavovací parametry v `options`

Dostupnost a přesný účinek se může lišit podle modelu, formátu a verze Ollamy. Parametry posílejte jako vnořený objekt `options`, ne na vrchní úroveň požadavku.

| Parametr | Typ | Obvyklý účel |
|---|---|---|
| `temperature` | číslo | Míra náhodnosti. Nižší hodnoty jsou stabilnější, vyšší kreativnější. Často `0.0–1.0`. |
| `top_p` | číslo | Nucleus sampling; omezuje výběr tokenů na pravděpodobnostní masu. |
| `top_k` | celé číslo | Omezuje výběr na K nejpravděpodobnějších tokenů. |
| `min_p` | číslo | Odřízne tokeny s příliš malou relativní pravděpodobností. |
| `typical_p` | číslo | Typical sampling. Obvykle jej nekombinujte bezdůvodně s jinými sampling strategiemi. |
| `tfs_z` | číslo | Tail-free sampling. |
| `seed` | celé číslo | Semínko pro opakovatelnější výsledek; úplná shoda není zaručena mezi verzemi/hardwarem. |
| `num_predict` | celé číslo | Maximální počet generovaných tokenů; `-1` znamená generovat dál dle nastavení modelu. |
| `num_ctx` | celé číslo | Velikost kontextového okna v tokenech. Vyšší hodnota spotřebuje více paměti. |
| `num_keep` | celé číslo | Počet tokenů z promptu, které se zachovají při zkracování kontextu. |
| `repeat_last_n` | celé číslo | Rozsah historie pro penalizaci opakování. |
| `repeat_penalty` | číslo | Penalta opakování; vyšší hodnota omezuje opakující se text. |
| `presence_penalty` | číslo | Penalizuje tokeny, které se už v odpovědi objevily. |
| `frequency_penalty` | číslo | Penalizuje častěji použité tokeny. |
| `mirostat` | 0/1/2 | Adaptivní sampling Mirostat; 0 jej vypne. |
| `mirostat_tau` | číslo | Cílová entropie Mirostatu. |
| `mirostat_eta` | číslo | Rychlost učení Mirostatu. |
| `stop` | pole stringů | Sekvence, při nichž se generování ukončí. |
| `num_batch` | celé číslo | Velikost dávky při vyhodnocení promptu; ovlivňuje rychlost a paměť. |
| `num_thread` | celé číslo | Počet CPU vláken pro inference na CPU. |
| `num_gpu` | celé číslo | Počet vrstev/offload pro GPU podle podpory backendu. |
| `main_gpu` | celé číslo | Index hlavní GPU pro více GPU. |
| `low_vram` | boolean | Šetří VRAM za cenu výkonu, pokud backend podporuje. |
| `use_mmap` | boolean | Použije memory mapping modelových souborů. |
| `use_mlock` | boolean | Zamkne model v RAM; může vyžadovat práva a více paměti. |

Praktické výchozí hodnoty pro přesnější odpovědi:

```json
"options": {
  "temperature": 0.2,
  "top_p": 0.9,
  "num_ctx": 8192,
  "repeat_penalty": 1.1
}
```

Pro kreativnější text zkuste `temperature: 0.8`; pro výpočty a extrakci strukturovaných dat začněte s `temperature: 0` až `0.3`.

## 8. Strukturovaný JSON výstup

Jednoduchý režim:

```json
{
  "model": "qwen3:8b",
  "prompt": "Vrať JSON se jménem, městem a věkem fiktivní osoby.",
  "format": "json",
  "stream": false
}
```

Spolehlivější je předat JSON Schema a v promptu výslovně žádat pouze data odpovídající schématu:

```json
{
  "model": "qwen3:8b",
  "prompt": "Vytvoř profil fiktivního zákazníka. Vrať pouze JSON.",
  "format": {
    "type": "object",
    "properties": {
      "name": {"type": "string"},
      "city": {"type": "string"},
      "age": {"type": "integer", "minimum": 0}
    },
    "required": ["name", "city", "age"],
    "additionalProperties": false
  },
  "stream": false,
  "options": {"temperature": 0}
}
```

I při použití schématu vždy na straně aplikace JSON validujte – modelový výstup je vstup z nedůvěryhodného zdroje.

## 9. Správa modelů přes REST

### Seznam nainstalovaných modelů

```text
GET /api/tags
```

```powershell
curl.exe http://localhost:11434/api/tags
```

Odpověď obsahuje `models` a u každého modelu například `name`, `size`, `digest`, rodinu a úroveň kvantizace.

### Modely v paměti

```text
GET /api/ps
```

Odpověď ukazuje také `size_vram`, `context_length` a `expires_at`.

### Stažení modelu

```text
POST /api/pull
```

```json
{
  "model": "qwen3:8b",
  "stream": true
}
```

### Detaily modelu

```text
POST /api/show
```

```json
{
  "model": "deepseek-r1:14b",
  "verbose": true
}
```

### Odstranění modelu

```text
DELETE /api/delete
```

```json
{
  "model": "nepouzivany-model:latest"
}
```

Mazání modelu je nevratné, dokud jej znovu nestáhnete.

## 10. Embeddingy pro vyhledávání/RAG

Endpoint `POST /api/embed` převádí text na číselné vektory.

```json
{
  "model": "embeddinggemma",
  "input": [
    "První dokument",
    "Druhý dokument"
  ]
}
```

Odpověď obsahuje pole `embeddings`, kde každý prvek odpovídá jednomu vstupu. Pro vyhledávání vytvořte embedding dotazu, porovnejte jej s embeddingy dokumentů (například kosinovou podobností) a modelu předložte nejrelevantnější úryvky.

## 11. Chyby, timeouty a bezpečnost

- Neúspěšný HTTP status zpracujte pomocí `response.raise_for_status()` nebo kontrolou `status_code`.
- Nastavte timeout. Načtení velkého modelu a první odpověď mohou trvat déle než samotné generování.
- Počítejte s tím, že některé modely nepodporují obrázky, tools, reasoning nebo zvolenou úroveň `think`.
- Lokální API neposílejte přímo do internetu bez autentizace a síťového omezení. Výchozí adresa `localhost` je pro lokální použití bezpečnější.
- Při `stream: true` nevolejte `response.json()` – čtěte řádky přes `iter_lines()`.
- Při `stream: false` naopak můžete pohodlně použít `response.json()`.

## 12. Souvislost s aplikací v tomto adresáři

Hlavním menu je `james.py`; běžné flows spouští přes `runner.py` a `cli_ollama.py`. Sdílený klient je třída `ollama_api` v `lib/wrapp_ollama.py`. Prompty, překlady a OCR používají `/api/generate`, popis obrázků `/api/chat`. Cowork používá konfiguraci klienta a vlastní tool-calling komunikaci přes `/api/chat` v `lib/wrapp_agent.py`.

Adresa serveru a společné výchozí volby jsou v `lib/ollama.json`, konkrétní úlohy v `assistant/tasks/*.json` a profily agentů v `agent/agents.json` (náhled v James → Setup → agents). RAG používá funkci `embed_texts` a `/api/embed`. Příkazy z tohoto dokumentu spouštějte z kořene projektu.

## 13. Parametry generování

### `temperature`

`temperature` určuje míru náhodnosti při výběru dalšího tokenu.

| Hodnota | Vhodné použití |
|---:|---|
| `0.0` až `0.2` | Stálé odpovědi, výpočty a přesné úlohy. |
| `0.4` až `0.7` | Přirozenější vysvětlování a více variant formulace. |
| `0.8` a více | Kreativní výstupy; roste riziko nepřesností a zbytečné upovídanosti. |

Pro jednoduchý výpočet lze nastavit `0.0`; pro dětské vysvětlení například `0.4`. V dnešním CLI použijte `--temp`, v task JSON objekt `options`. Starší metoda `ollama_api.run()` nad `input.json` nadále podporuje přepsání u jednotlivého dotazu:

```json
{
  "prompt": "vypočítej 1 + 3",
  "temperature": 0.0
}
```

Výchozí hodnoty jsou v `lib/ollama.json` v objektu `default_options`. Následující ukázka patří ke staršímu rozhraní `input.json`: parametry v jeho kořeni přepíší konfiguraci a hodnoty v konkrétní položce `queries` přepíší nastavení pro daný dotaz. V současných `assistant/tasks/*.json` patří tyto parametry do `options`:

```json
{
  "seed": 42,
  "num_predict": 256,
  "num_ctx": 4096,
  "temperature": 0.2,
  "repeat_penalty": 1.1
}
```

### Další užitečné parametry

| Parametr | Význam |
|---|---|
| `seed` | Stejná hodnota pomáhá opakovat podobný výsledek. |
| `num_predict` | Maximální počet vytvořených tokenů; omezuje délku odpovědi. |
| `num_ctx` | Velikost kontextového okna — kolik vstupního textu model udrží. |
| `top_p`, `top_k`, `min_p` | Další řízení variability; obvykle stačí ladit pouze `temperature`. |
| `repeat_penalty` | Omezuje opakování slov a vět. |
| `stop` | Texty, při jejichž výskytu má generování skončit. |
| `think` | Zapíná/vypíná reasoning u modelů, které jej podporují. |
| `stream` | Průběžné posílání odpovědi; běžné textové úlohy streamují, OCR používá `false`. |

Pro tuto aplikaci se hodí zejména `num_predict` pro omezení délky odpovědi a `seed` pro opakovatelnější výsledky. Podporované možnosti se mohou mírně lišit podle modelu a verze Ollamy.

## Oficiální zdroje

- [Úvod a základní URL API](https://docs.ollama.com/api/introduction)
- [Generate endpoint](https://docs.ollama.com/api/generate)
- [Chat endpoint](https://docs.ollama.com/api/chat)
- [Streamování NDJSON](https://docs.ollama.com/api/streaming)
- [Seznam lokálních modelů](https://docs.ollama.com/api/tags)
- [Modely běžící v paměti](https://docs.ollama.com/api/ps)
