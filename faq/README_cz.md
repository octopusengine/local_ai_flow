# James: instalace a první test

Tento postup předpokládá Windows PowerShell. Příkazy pro Linux a macOS jsou
uvedené tam, kde se liší.

## 1. Nainstalujte Ollamu a modely

Nainstalujte Ollamu z [ollama.com/download](https://ollama.com/download) a
spusťte Ollama Desktop. Na Linuxu lze použít oficiální instalaci:

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

Stáhněte alespoň model pro rychlý první test:

```powershell
ollama pull qwen3.5:4b
```

Pro profily v Cowork se podle dostupné paměti hodí také:

```powershell
ollama pull qwen3.5:latest   # Light, Hardware, Artist, Musician
ollama pull gpt-oss:latest   # Coding
```

Nostr používá `qwen3.5:4b`. Malé modely stačí pro první ověření; další modely
lze přidat později.

## 2. Nainstalujte tento projekt

```powershell
git clone https://github.com/octopusengine/local_ai_flow.git
cd local_ai_flow
py -3 -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Linux a macOS:

```bash
git clone https://github.com/octopusengine/local_ai_flow.git
cd local_ai_flow
python3 -m venv venv
source venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Volitelné moduly instalujte až tehdy, když je budete používat:

```powershell
python -m pip install -r requirements_ble.txt     # BLE / Hardware MCP
python -m pip install -r requirements_nostr.txt   # Nostr MCP
python -m pip install -r requirements_laya.txt    # RLPC / Laya
```

## Jak poznám, že Ollama běží?

Ollama Desktop musí být spuštěná jako aplikace. API potom běží lokálně na
`http://127.0.0.1:11434` (obvykle také `http://localhost:11434`). Ověřte ho:

```powershell
ollama list
ollama ps
curl.exe http://127.0.0.1:11434/api/tags
```

`ollama list` vypíše nainstalované modely, `ollama ps` právě načtené modely a
poslední příkaz vrátí JSON s katalogem modelů. Když API neběží, spusťte ho
ručně:

```powershell
ollama serve
```

Na Linuxu se po instalaci obvykle používá `systemctl status ollama` a
`systemctl start ollama`. James používá URL z `lib/ollama.json`; výchozí je
lokální Ollama.

## První spuštění Jamese

Spusťte projekt z jeho kořene:

```powershell
python james.py
```

Při prvním použití:

1. Otevřete `Setup → project → show` a zkontrolujte `project.json`.
   `subdir` určuje aktivní projektový adresář; pokud chybí, nastavte ho přes
   `Setup → project → dir_name`.
2. James při prvním přístupu vytvoří nastavenou SQLite databázi `main_db`
   (výchozí `data/tasks.db`) podle schématu `data/tasks.json`.
3. V `Setup → agents` zkontrolujte profily, modely a Markdown instrukce.
   V `Setup → tools` je přehled nástrojů a jejich přiřazení k profilům.
4. Volitelné BLE, Nostr, MCP nebo Laya moduly doinstalujte podle potřeby.
   James neukončí kvůli chybějícímu volitelnému modulu základní Chat, Flow ani
   Cowork; v příslušném menu vypíše chybějící soubory.

## Test James / Chat

Nejprve lze ověřit API bez menu:

```powershell
python cli_ollama.py --test
```

Potom v Jamesovi zvolte `Chat`, napište jednoduchý dotaz, například:

```text
Napiš jednou větou, že lokální Ollama odpovídá.
```

Úspěch znamená odpověď modelu bez chyby připojení. Aktivní model lze během
Chatu zobrazit nebo změnit příkazem `/mod`; aktivní projekt zobrazí `/proj`.

## Test Flow

V hlavním menu zvolte `Flow`, potom `Test` a spusťte jeden krátký testovací
flow. Pro samostatné ověření použijte také:

```powershell
python runner.py --help
```

Pro Laya otevřete `Flow → RLPC_Laya`; před inferencí musí být nainstalované
`requirements_laya.txt` a příslušný model v `assets/laya_models`.

Úspěšný flow vypíše dokončení a případné výstupy uloží do aktivního projektu.
Při chybě si nejprve otevřete flow klávesou `i` a zkontrolujte jeho kroky a
požadované soubory.

## Test Cowork

V hlavním menu zvolte `Cowork`, vyberte `Light AGENT session` a spusťte
`one-shot task` s dotazem:

```text
Vypiš soubory v aktivním projektu a stručně popiš, co je v něm hlavní.
```

Pak vyzkoušejte `Coding session` nebo `Agent artist`. `set project` mění
projekt pouze pro právě vybraného agenta a nepřepisuje `project.json`.

Ověřte také `setup-info`: ukazuje skutečný projekt, aktivní model, profil
nástrojů, cestu k `log.txt` a databázi. Při výchozím `log: true` se průběh
zapisuje do `log.txt` v pracovním projektu a dokončený běh do `main_db`.
Pro Musician použijte dotaz na vytvoření `.rb` nebo `.mid` souboru; agent
neprohlašuje, že Sonic Pi nebo MIDI přehrál, pokud to nástroj nepotvrdil.

---

[English version / Anglická verze](README.md)
