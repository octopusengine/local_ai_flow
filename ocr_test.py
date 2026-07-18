"""Jednoduchý test OCR modelu deepseek-ocr v lokální Ollamě."""

import base64
import json
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

from lib.wrapp_cli_log import load_ollama_timeout_seconds


PROJECT_ROOT = Path(__file__).resolve().parent
CONFIG_FILE = PROJECT_ROOT / "cli_ocr_ollama.json"
DEFAULT_PROMPT = "Extract all text from this image. Return only the recognized text, preserving line breaks."


def report(message: str) -> None:
    """Vypíše průběh zpracování s časem."""
    now = datetime.now().strftime("%H:%M:%S")
    print(f"[{now}] {message}", flush=True)


def debug(message: str, enabled: bool) -> None:
    if enabled:
        report(f"DEBUG: {message}")


def load_config() -> dict:
    try:
        config = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ValueError(f"Konfigurační soubor nebyl nalezen: {CONFIG_FILE.resolve()}") from None
    except json.JSONDecodeError as error:
        raise ValueError(f"Neplatný JSON v {CONFIG_FILE}: {error}") from error

    for name in ("model", "ocr_directory", "input_file", "output_extension"):
        if not isinstance(config.get(name), str) or not config[name].strip():
            raise ValueError(f"V {CONFIG_FILE} chybí neprázdná hodnota {name!r}.")
    if "options" in config and not isinstance(config["options"], dict):
        raise ValueError(f"Hodnota 'options' v {CONFIG_FILE} musí být JSON objekt.")
    if "debug" in config and not isinstance(config["debug"], bool):
        raise ValueError(f"Hodnota 'debug' v {CONFIG_FILE} musí být true nebo false.")
    if "image_extensions" in config and (
        not isinstance(config["image_extensions"], list)
        or not all(isinstance(extension, str) and extension.startswith(".") for extension in config["image_extensions"])
    ):
        raise ValueError(f"Hodnota 'image_extensions' v {CONFIG_FILE} musí být seznam přípon obrázků.")
    return config


def main(input_file_override: str | None = None) -> int:
    report("Spouštím OCR test přes lokální Ollamu.")
    report(f"Načítám nastavení ze souboru: {CONFIG_FILE.resolve()}")
    try:
        config = load_config()
        ollama_timeout_seconds = load_ollama_timeout_seconds(PROJECT_ROOT)
    except ValueError as error:
        print(f"CHYBA: {error}", file=sys.stderr)
        return 1

    debug_enabled = config.get("debug", False)
    report(f"Nastavený model: {config['model']}")
    debug(f"Parametry modelu: {json.dumps(config.get('options', {}), ensure_ascii=False)}", debug_enabled)

    ocr_directory = Path(config["ocr_directory"])
    input_file = Path(input_file_override or config["input_file"])
    input_image = input_file if input_file.is_absolute() else ocr_directory / input_file
    output_extension = config["output_extension"]
    if not output_extension.startswith("."):
        output_extension = f".{output_extension}"
    output_text = ocr_directory / f"{input_image.stem}{output_extension}"
    report(f"Pracovní složka OCR: {ocr_directory.resolve()}")
    ocr_directory.mkdir(parents=True, exist_ok=True)
    report(f"Kontroluji vstupní obrázek: {input_image.resolve()}")
    if not input_image.is_file():
        print(f"CHYBA: Vstupní obrázek nebyl nalezen: {input_image.resolve()}", file=sys.stderr)
        return 1

    image_bytes = input_image.read_bytes()
    report(f"Načítám obrázek ({len(image_bytes):,} bajtů).")
    report("Převádím obrázek do formátu pro Ollamu.")
    image_base64 = base64.b64encode(image_bytes).decode("ascii")
    payload = {
        "model": config["model"],
        "prompt": config.get("prompt", DEFAULT_PROMPT),
        "images": [image_base64],
        "stream": False,
        "options": config.get("options", {}),
    }
    ollama_url = config.get("ollama_url", "http://localhost:11434/api/generate")
    version_url = ollama_url.removesuffix("/api/generate") + "/api/version"

    try:
        report(f"Ověřuji, že Ollama běží: {version_url}")
        version_response = requests.get(version_url, timeout=10)
        version_response.raise_for_status()
        version = version_response.json().get("version", "neznámá verze")
        report(f"Ollama odpovídá (verze {version}).")

        report(f"Otevírám model {config['model']} a spouštím OCR požadavek.")
        debug(f"API URL: {ollama_url}", debug_enabled)
        debug(f"Délka OCR zadání: {len(payload['prompt'])} znaků", debug_enabled)
        debug("Obrázek je přiložen jako Base64; jeho obsah se do výpisu nezapisuje.", debug_enabled)
        scan_started_at = datetime.now()
        evaluation_started_at = time.monotonic()
        response = requests.post(
            ollama_url,
            json=payload,
            timeout=(10, ollama_timeout_seconds),
        )
        evaluation_seconds = time.monotonic() - evaluation_started_at
        debug(f"API odpovědělo HTTP {response.status_code}.", debug_enabled)
        response.raise_for_status()
        report("Ollama dokončila OCR; zpracovávám odpověď.")
        result = response.json()
    except requests.RequestException as error:
        print(f"CHYBA: Nepodařilo se spojit s Ollamou: {error}", file=sys.stderr)
        return 1
    except ValueError as error:
        print(f"CHYBA: Ollama nevrátila platný JSON: {error}", file=sys.stderr)
        return 1

    text = result.get("response")
    if not isinstance(text, str):
        print(f"CHYBA: Odpověď neobsahuje text OCR: {result}", file=sys.stderr)
        return 1

    report(f"Rozpoznaný text má {len(text)} znaků.")
    report(f"Vyhodnocení OCR trvalo {evaluation_seconds:.1f} s.")
    report(f"Ukládám OCR výstup do: {output_text.resolve()}")
    output_report = (
        f"Použitý model: {config['model']}\n"
        f"Parametry modelu: {json.dumps(config.get('options', {}), ensure_ascii=False)}\n"
        f"Datum skenování: {scan_started_at.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"Čas trvání vyhodnocení: {evaluation_seconds:.1f} s\n"
        "---\n"
        f"{text}"
    )
    output_text.write_text(output_report, encoding="utf-8")
    report("Hotovo. OCR text byl úspěšně uložen.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
