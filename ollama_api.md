# Ollama REST API

This project uses the local Ollama REST API for generic prompts, translation,
and image OCR. Its shared API client is `lib/wrapp_ollama.py`; OCR calls the
Generate endpoint directly.

The official and current reference is the [Ollama API documentation](https://docs.ollama.com/api/introduction).

## Local server and models

After Ollama is installed and running, its default local API base URL is:

```text
http://localhost:11434/api
```

Check the local service and installed models:

```powershell
curl.exe http://localhost:11434/api/version
curl.exe http://localhost:11434/api/tags
ollama list
```

Pull a required model when it is not yet installed:

```powershell
ollama pull deepseek-ocr:3b
ollama pull translategemma:12b
```

The active model names are configuration values, not hard-coded requirements:

- `cli_ocr_ollama.json` currently uses `deepseek-ocr:3b`.
- `cli_translate.json` currently uses `translategemma:12b`.

## Generate endpoint

Most one-shot tasks use `POST /api/generate`. The endpoint accepts a model name,
a prompt, optional images, and generation options. `stream` defaults to `true`;
use `false` when the application should receive one JSON object.

```json
{
  "model": "deepseek-ocr:3b",
  "prompt": "Extract all text. Return only the recognized text.",
  "images": ["<base64-image>"],
  "stream": false,
  "options": {
    "temperature": 0.1,
    "num_predict": 4096
  }
}
```

The non-streaming response includes the generated text in `response` and timing
fields such as `total_duration`, `load_duration`, and `eval_duration` (in
nanoseconds). Models that support it may also return a separate `thinking`
field when `think` is enabled.

PowerShell example:

```powershell
$body = @{
  model = "translategemma:12b"
  prompt = "Translate from English to Czech: Good morning"
  stream = $false
  options = @{ temperature = 0.1 }
} | ConvertTo-Json -Depth 4

Invoke-RestMethod `
  -Uri "http://localhost:11434/api/generate" `
  -Method Post `
  -ContentType "application/json" `
  -Body $body
```

For the complete request and response schema, see the official
[Generate endpoint reference](https://docs.ollama.com/api/generate).

## Chat, embeddings, and model management

Use these endpoints when a task calls for more than a single prompt:

| Endpoint | Method | Purpose |
|---|---:|---|
| `/api/chat` | POST | Multi-message conversations, optional tools, and structured output. |
| `/api/embed` | POST | Text embeddings for semantic search or RAG. |
| `/api/tags` | GET | Installed models. |
| `/api/ps` | GET | Models currently loaded in memory. |
| `/api/show` | POST | Model details and capabilities. |
| `/api/pull` | POST | Download a model. |
| `/api/delete` | DELETE | Remove a local model. |
| `/api/version` | GET | Ollama version. |

The [Chat endpoint](https://docs.ollama.com/api/chat) accepts a `messages`
array instead of a single `prompt`. The [API introduction](https://docs.ollama.com/api/introduction)
lists the complete endpoint set.

## Streaming and structured output

With `stream: true`, Ollama returns newline-delimited JSON (NDJSON). Each line
is an independent JSON object, and partial `response` values must be appended
in order. Do not call `response.json()` for streaming responses; iterate over
the lines instead.

Use `"format": "json"` or a JSON Schema object when a task needs structured
model output. Validate every returned JSON document in the application before
using it.

## Practical options

Put runtime settings inside the `options` object. Common controls are:

| Option | Use |
|---|---|
| `temperature` | Randomness; use lower values for OCR, translation, and extraction. |
| `num_predict` | Maximum number of generated tokens. |
| `num_ctx` | Context window size; higher values require more memory. |
| `seed` | Helps make comparable runs more repeatable. |
| `top_p`, `top_k`, `min_p` | Alternative sampling controls. |
| `repeat_penalty` | Reduces repetitive output. |
| `stop` | Stops generation at matching strings. |

The available options and their behavior can vary by model and Ollama version.

## Reliability and security

- Always set a timeout and call `raise_for_status()` for HTTP requests.
- Loading a model can take longer than generating a short response.
- Check that the selected model supports images before sending `images`.
- Keep the API on `localhost` unless authentication and network controls are in
  place.
- Treat model output as untrusted input, including output constrained by JSON
  Schema.
