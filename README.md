# local_ai_flow

![License](https://img.shields.io/badge/License-MIT-blue.svg)
![Python](https://img.shields.io/badge/Python-3.13-3776AB.svg?logo=python&logoColor=white)
![Local%20AI](https://img.shields.io/badge/AI-local%20first-8A2BE2.svg)
![Ollama%20API](https://img.shields.io/badge/Ollama-local%20API-black.svg)
![Privacy](https://img.shields.io/badge/Privacy-data%20stays%20local-success.svg)

Command-line tools for a local AI workflow: microphone recording, camera capture,
MP3 transcription, image OCR, Czech/English translation, and text-to-speech.
The tools use local Ollama, OpenAI Whisper, Piper, FFmpeg, and OpenCV where
applicable.

Run the commands from the repository root. The examples use PowerShell on
Windows.

## Ollama API and primary models

The AI stages use a local Ollama REST API, normally available at
`http://localhost:11434/api`. See the [Ollama API guide](ollama_api.md) for the
project's API usage and request examples.

The current primary models are configured in JSON files:

- OCR: `deepseek-ocr:3b` in `cli_ocr_ollama.json`.
- Czech/English translation: `translategemma:12b` in `cli_translate.json`.
- MCP tool calling: `qwen3.5:latest` in `mcp/mcp_config.json`.

Current local model setup:

```text
ollama list
translategemma:12b    c2f9a9ca1ec7    8.1 GB
deepseek-ocr:3b       0e7b018b8a22    6.7 GB
qwen3.5:latest        6488c96fa5fa    6.6 GB
```

The project also includes a local MCP server and an Ollama tool-calling test.
See the relative [MCP guide](mcp.md) for its architecture and tools.

## Requirements

- Python with the project dependencies installed:

  ```powershell
  python -m pip install -r requirements.txt
  ```

- A running local [Ollama](https://ollama.com/) instance for OCR, translation,
  and generic Ollama requests.
- The configured Ollama models, for example the model named in
  `cli_ocr_ollama.json`.
- A camera for `cli_camera.py`, and a microphone for `cli_record_mp3.py`.

The repository contains the FFmpeg path configuration in `lib/ffmpeg.json`.

## Project flow management

`cli_project_flow.py` manages the active working directory selected by
`project.json`. Start here when switching to a different project.

```json
{
  "subdir": "project_01",
  "ollama_timeout_seconds": 900
}
```

With this setting, the inputs, outputs, and `log.txt` file are in
`./project_01/`. The shared Ollama response timeout is 900 seconds (15 minutes)
and can be changed directly in `project.json`. It applies to translation, OCR,
generic Ollama requests, and MCP model calls. The flow runner itself does not
impose a time limit on subprocess steps.

```powershell
# Select and create a working directory, then save it in project.json.
python .\cli_project_flow.py -project "project_02"

# Show the active project, file count, total size, and log size.
python .\cli_project_flow.py -status

# Permanently clear the current project's log file.
python .\cli_project_flow.py -clearlog

# Create .\archive\project_02_yymmdd_hhmm.zip.
python .\cli_project_flow.py -archive

# Show help.
python .\cli_project_flow.py -help
```

An archive contains the active project directory and its files. Existing archives
are never overwritten.

## Common behavior

All user-facing tools support standard `-h` / `--help`. Several tools also
provide `-help` as a short compatibility alias.

Most CLI configurations include:

```json
{
  "log": true
}
```

When enabled, the terminal output is also appended to
`./<active-project>/log.txt`, in a separate timestamped run block. Set it to
`false` to keep output only in the terminal.

Working input and output files must normally be directly in the active project
directory, not in its nested directories.

## Camera capture

`cli_camera.py` shows a live preview from the default camera and saves the
captured image as `camera.png` in the active project directory.

```powershell
# Default camera (index 0).
python .\cli_camera.py

# A different camera device.
python .\cli_camera.py --camera 1
```

Press Space, Enter, or click the preview to capture. Press Esc or Q to cancel.
Camera activity is recorded in `log.txt` when `cli_camera.json` has
`"log": true`.

## Microphone recording

`cli_record_mp3.py` records the default microphone to mono MP3. Press any key
to stop recording, or use Ctrl+C.

```powershell
# Creates ./<active-project>/record.mp3.
python .\cli_record_mp3.py

# Use a different output filename.
python .\cli_record_mp3.py interview.mp3

# Temporarily override the configured software gain.
python .\cli_record_mp3.py record.mp3 --gain-db 4
```

The default gain is configured in `lib/record.json`. Valid values range from
`-30` to `30` dB.

## MP3 transcription

`cli_whisper_mp3.py` uses local OpenAI Whisper and writes a `.txt` transcript
next to the selected MP3 file.

```powershell
# Transcribe the first MP3 file alphabetically in the active project.
python .\cli_whisper_mp3.py

# Transcribe a selected MP3 file.
python .\cli_whisper_mp3.py record.mp3
```

Whisper settings are stored in `lib/whisper.json`; its CLI logging switch is in
`cli_whisper_mp3.json`.

## Image OCR

`cli_ocr_ollama.py` recognizes text from an image using the Ollama model in
`cli_ocr_ollama.json`. Supported image extensions are `.png`, `.jpg`, `.jpeg`,
`.webp`, `.bmp`, and `.gif`.

```powershell
# Use input_file from cli_ocr_ollama.json.
python .\cli_ocr_ollama.py

# Process one image, including camera.png captured by cli_camera.py.
python .\cli_ocr_ollama.py camera.png

# Process all supported images in the active project.
python .\cli_ocr_ollama.py -all
```

OCR writes only the recognized text to `image-name.txt`. Model information,
parameters, scan time, and evaluation duration are written to `log.txt`.

## Translation

`cli_translate.py` translates Czech and English text through local Ollama. The
result is always stored as `translate.txt` in the active project directory.

```powershell
# Czech to English using the configured default input file.
python .\cli_translate.py

# English to Czech using the configured default input file.
python .\cli_translate.py e2c

# Czech to English from a selected text file.
python .\cli_translate.py source.txt

# English to Czech from a selected text file.
python .\cli_translate.py e2c source.txt
```

The output file contains only the translation; operational information is in
`log.txt`.

## Text-to-speech

`cli_speech_mp3.py` creates speech from a text file using Piper. The configured
voice codes are `cz` and `en`; the output MP3 uses the input filename.

```powershell
# Default voice and default input file from cli_speech.json.
python .\cli_speech_mp3.py

# English voice with the configured default input file.
python .\cli_speech_mp3.py en

# Default voice and a selected input file.
python .\cli_speech_mp3.py source.txt

# English voice and a selected input file.
python .\cli_speech_mp3.py en translate.txt
```

`cli_speech.json` controls the default voice, input filename, playback, MP3
generation, and voice models.

## Combined workflow

`cli_ai_project.py` chains the tools above for audio or image processing.

```powershell
# Microphone -> MP3 -> transcript.
python .\cli_ai_project.py record

# MP3 -> transcript -> English translation -> English narration.
python .\cli_ai_project.py audio record.mp3 --translate c2e --speech en

# Image -> OCR -> Czech translation -> Czech narration.
python .\cli_ai_project.py image camera.png --translate e2c --speech cz
```

`--translate` without a value uses `c2e`; `--speech` without a value uses
`cz`.

## Simple flow runner

`runner.py` executes the project CLI commands listed in a text file, one after
another. The initial example is [`flow_example.txt`](flow_example.txt).
Commands are validated before the first step starts, use the current Python
interpreter, inherit interactive terminal input, and stop on the first non-zero
exit code. Each CLI keeps its own configuration and project logging.

```powershell
# Validate and display every command without running cameras or AI models.
python .\runner.py .\flow_example.txt --dry-run

# Execute the complete command list.
python .\runner.py .\flow_example.txt
```

This first implementation accepts only root-level `cli_*.py` commands. It does
not use a shell and therefore does not execute arbitrary shell syntax. The
declarative artifact format proposed in `todo_flow.md` remains a later phase.

## Generic Ollama batch requests

`cli_ollama.py` processes a JSON request file through the common Ollama
wrapper.

```powershell
python .\cli_ollama.py
python .\cli_ollama.py cli_input.json output.txt
```

The default input file is `cli_input.json`. See `lib/config.json` for the
shared Ollama connection settings.

## MCP integration test

`cli_mcp.py` tests a local Streamable HTTP MCP server and Ollama tool calling.
The generic server wrapper currently publishes `rot13`, `datetime`, and
`calculate`.

```powershell
python .\cli_mcp.py --model qwen3.5:latest --function rot13 --word apple
python .\cli_mcp.py --model qwen3.5:latest --function datetime
python .\cli_mcp.py --model qwen3.5:latest --function calculate --a 8 --b 2 --operation "+"
```

See the [MCP guide](mcp.md) for the architecture, configuration, output, and
extension instructions.
