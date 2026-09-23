# James: installation and first test

This guide assumes Windows PowerShell. Linux and macOS commands are shown
where they differ.

## 1. Install Ollama and its models

Install Ollama from [ollama.com/download](https://ollama.com/download) and
start Ollama Desktop. On Linux, you can use the official installer:

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

Download at least one model for the first test:

```powershell
ollama pull qwen3.5:4b
```

Depending on available memory, these models are also useful for the Cowork
profiles:

```powershell
ollama pull qwen3.5:latest   # Light, Hardware, Artist, Musician
ollama pull gpt-oss:latest   # Coding
```

Nostr uses `qwen3.5:4b`. Small models are enough for the first verification;
you can add more models later.

## 2. Install this project

```powershell
git clone https://github.com/octopusengine/local_ai_flow.git
cd local_ai_flow
py -3 -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Linux and macOS:

```bash
git clone https://github.com/octopusengine/local_ai_flow.git
cd local_ai_flow
python3 -m venv venv
source venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Install optional modules only when you need them:

```powershell
python -m pip install -r requirements_ble.txt     # BLE / Hardware MCP
python -m pip install -r requirements_nostr.txt   # Nostr MCP
python -m pip install -r requirements_laya.txt    # RLPC / Laya
```

## How do I know that Ollama is running?

Ollama Desktop must be running as an application. Its local API normally listens
on `http://127.0.0.1:11434` (also commonly `http://localhost:11434`). Check it:

```powershell
ollama list
ollama ps
curl.exe http://127.0.0.1:11434/api/tags
```

`ollama list` displays installed models, `ollama ps` displays currently loaded
models, and the last command returns the model catalog as JSON. If the API is
not running, start it manually:

```powershell
ollama serve
```

After a Linux installation, use `systemctl status ollama` and
`systemctl start ollama` when appropriate. James uses the URL in
`lib/ollama.json`; the default is the local Ollama service.

## First James launch

Run the project from its root directory:

```powershell
python james.py
```

On the first launch:

1. Open `Setup → project → show` and check `project.json`. Its `subdir` value
   selects the active project directory; if it is missing, set it through
   `Setup → project → dir_name`.
2. On first access, James creates the configured SQLite `main_db` (normally
   `data/tasks.db`) from the `data/tasks.json` schema.
3. Open `Setup → agents` to check profiles, models, and Markdown instructions.
   `Setup → tools` shows the tools and their profile membership.
4. Install optional BLE, Nostr, MCP, or Laya modules as needed. Missing optional
   modules do not stop the basic Chat, Flow, or Cowork menus; the relevant menu
   reports the missing files.

## Test James / Chat

You can first verify the API without the menu:

```powershell
python cli_ollama.py --test
```

Then choose `Chat` in James and enter a simple prompt, for example:

```text
Reply in one sentence that the local Ollama service is responding.
```

Success means that the model responds without a connection error. Show or change
the active model in Chat with `/mod`; `/proj` shows the active project.

## Test Flow

In the main menu choose `Flow`, then `Test`, and run a short test flow. For a
standalone check, you can also use:

```powershell
python runner.py --help
```

For Laya, open `Flow → RLPC_Laya`. Before inference, install
`requirements_laya.txt` and provide the required model in `assets/laya_models`.

A successful flow reports completion and saves any output in the active project.
If a flow fails, press `i` to inspect it and check its steps and required files.

## Test Cowork

In the main menu choose `Cowork`, select `Light AGENT session`, and run
`one-shot task` with this prompt:

```text
List the files in the active project and briefly describe its main contents.
```

Then try `Coding session` or `Agent artist`. `set project` changes the project
only for the selected agent and does not modify `project.json`.

Also open `setup-info`: it shows the actual project, active model, tool profile,
`log.txt` path, and database. With the default `log: true`, the run is written
to `log.txt` in the working project and completed runs are stored in `main_db`.
For Musician, ask for an `.rb` or `.mid` file; the agent does not claim that
Sonic Pi or MIDI playback happened unless a tool confirms it.

---

[Česká verze / Czech version](README_cz.md)
