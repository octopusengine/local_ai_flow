# ollama_api

![License](https://img.shields.io/badge/License-MIT-blue.svg)
![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB.svg?logo=python&logoColor=white)
![Ollama](https://img.shields.io/badge/Ollama-local%20API-black.svg)
![Privacy](https://img.shields.io/badge/Privacy-local%20processing-success.svg)

`ollama_api` is a local command-line workflow for Ollama. Its main command,
`cli_ollama.py`, runs typed prompt, translation, image OCR, and image-description
tasks through one shared configuration and one consistent logging mechanism.

## Requirements

- Python 3.10 or newer
- [Ollama](https://ollama.com/) running locally or reachable at the URL configured
  in `lib/ollama.json`
- Python packages from `requirements.txt`

Create and activate a virtual environment before installing the dependencies.

```powershell
# Windows PowerShell
py -3 -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

```bash
# Linux and macOS
python3 -m venv venv
source venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Install the models used by the supplied task files:

```bash
ollama pull deepseek-coder-v2:latest
ollama pull translategemma:12b
ollama pull deepseek-ocr:3b
ollama pull qwen3.5:latest
```

Run commands from the repository root.

## Quick start

```bash
# Verify the configured server, its API endpoints, and installed models.
python cli_ollama.py --test

# Print the available local models.
python cli_ollama.py --list

# Run the default prompt task from task_test.json.
python cli_ollama.py
```

`--test` does not load a model. It reports the configured URL, DNS resolution,
HTTP responses from Ollama, the installed-model list, and a safe probe of the
generate endpoint. Use it first when a task cannot connect or reports HTTP 404.

## Configuration and files

`project.json` selects the active project directory and controls logging:

```json
{
  "subdir": "project_test260726",
  "log": true,
  "ollama_timeout_seconds": 900
}
```

All task inputs and outputs are directly inside this directory. With the example
above, they are in `project_test260726/`. When `log` is `true`, terminal output
from `cli_ollama.py`, including `--test` and `--list`, is appended to
`project_test260726/log.txt`.

The shared server address and default generation options are in
`lib/ollama.json`. Task files define one operation each:

| Task file | Purpose |
| --- | --- |
| `task_test.json` | Generic text prompt |
| `task_translate.json` | Czech/English translation |
| `task_ocr.json` | OCR from an image |
| `task_describe.json` | Image description |

Text files that may contain Czech text must be saved as UTF-8 without BOM.

## `cli_ollama.py` reference

```text
python cli_ollama.py [options]
```

| Option | Description |
| --- | --- |
| `--type TASK.json` | Task configuration in the repository root. Default: `task_test.json`. |
| `--data TEXT.txt` | UTF-8 prompt text file for a generic prompt task. |
| `--in FILE` | Input file for translation, OCR, or image-description tasks. |
| `--out RESULT.txt` | Output text file in the active project directory. |
| `--model MODEL` | Override the model specified by the task. |
| `--seed SEED` | Override the Ollama random seed. |
| `--temp TEMPERATURE` | Override temperature; must be zero or greater. |
| `--num-predict TOKENS` | Override the maximum generated-token count. |
| `--num-ctx TOKENS` | Override the context-window size. |
| `--repeat-penalty VALUE` | Override the repetition penalty. |
| `--c2a`, `-c2a` | Translate Czech to English. Translation tasks only. |
| `--e2c`, `-e2c` | Translate English to Czech. `--a2c` is a legacy alias. |
| `--status`, `-s` | Show the active project, shared Ollama, and selected task configuration. |
| `--test` | Verbose Ollama connectivity and endpoint diagnostic. |
| `--list` | List models available from the configured Ollama server. |
| `--version`, `-v` | Show program and wrapper versions. |
| `--help`, `-h` | Show command help. |

`--test` and `--list` are standalone actions. They do not require a task file,
and they cannot be combined with each other.

## Examples

### Generic prompt

```bash
# Use task_test.json and its prompt.
python cli_ollama.py

# Replace the prompt with project_test260726/test.txt.
python cli_ollama.py --type task_test.json --data test.txt

# Override the model and sampling settings.
python cli_ollama.py --model qwen3.5:latest --temp 0.2 --num-predict 512
```

### Translation

```bash
# Czech to English. Uses the task's default Czech input file and translate.txt.
python cli_ollama.py --type task_translate.json --c2a

# English to Czech with explicit input and output files.
python cli_ollama.py --type task_translate.json --e2c --in source_en.txt --out result_cs.txt
```

### OCR and image description

```bash
# Extract text from an image.
python cli_ollama.py --type task_ocr.json --in camera.png --out camera.txt

# Describe an image.
python cli_ollama.py --type task_describe.json --in camera.png --out description.txt
```

Supported image formats are PNG, JPEG, WEBP, BMP, and GIF. The input image and
output text file must be directly inside the active project directory.

## Flow runner

`runner.py` executes a validated list of project commands from a flow file and
stops at the first non-zero exit code.

```bash
# Validate a flow without running it.
python runner.py project_test260726/flow_proj.txt --dry-run

# Run the flow.
python runner.py project_test260726/flow_proj.txt
```

See `flow_ollama.txt` and `project_test260726/flow_proj.txt` for complete
examples of prompt, OCR, translation, and image-description stages.

When Ollama explicitly reports `model 'name' not found`, the affected task is
logged as skipped and the runner continues with the next flow step. Other
non-zero exit codes still stop the flow.

## Other utilities

The repository also contains optional camera, microphone, Whisper, Piper, and
MCP utilities. The Ollama prompt, translation, OCR, and image-description
operations are consolidated in `cli_ollama.py`; the former standalone Python
scripts for these operations have been removed.

## Troubleshooting

Start with:

```bash
python cli_ollama.py --test
python cli_ollama.py --list
```

If a task reports HTTP 404, inspect the response body. A message such as
`model 'name' not found` means the server is reachable but that model has not
been installed on this machine. Install it with:

```bash
ollama pull name
```
