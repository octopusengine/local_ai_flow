# cli_laya (version 0.1.1)

A small command-line tool that loads a markdown file (for example a support ticket) and asks typed questions about it using the **laya** model (an open-source model trained with RLCD, Apache 2.0). It prints the answers and, in batch mode, saves them as JSON next to the source files.

The model **does not generate text**: for every question it returns a choice, a number on a scale, or a yes/no probability, all in a single forward pass.

## Contents of the folder

| file | purpose |
|---|---|
| `cli_laya.py` | the program itself |
| `cli_laya.json` | settings (model path, default files, laya parameters) |
| `question.json` | the questions put to the model |
| `ticket.md` | sample input |
| `hello_laya.py` | the simplest "hello world" (a demo only, not needed to run `cli_laya.py`) |
| `data/` | folder for batch processing (create it yourself) |

## Installation

You need Python (laya declares 3.8+; tested on 3.10 under Windows) and about 1 GB of disk space for the model.

```powershell
python -m venv venv
venv\Scripts\activate
pip install laya
```

`pip install laya` also pulls in the dependencies (torch, transformers, huggingface_hub). Nothing else needs to be installed.

### First run

```powershell
python cli_laya.py
```

If the model is missing from the folder given by `model_dir`, it is downloaded automatically from Hugging Face (the multilingual checkpoint, roughly 680 MB). Subsequent runs download nothing and work offline.

### Note on Windows and symlinks

The standard `huggingface_hub` cache uses symbolic links, which some disks (for example exFAT/FAT32) do not support; the download then fails with `WinError 1`. The program therefore downloads the model straight into `model_dir` using `local_dir`, which does not use symlinks, so the model can live on any disk.

## Usage

```
python cli_laya.py [input.md] [-b [DIR]] [-c CONFIG.json] [-q QUESTIONS.json] [-u] [--model-dir DIR] [-V] [-v]
```

| switch | meaning |
|---|---|
| `input.md` | the input file (default: `input` from the configuration) |
| `-b`, `--batch [DIR]` | batch: process every `*.md` in a folder (without `DIR`, `batch_dir` is used, i.e. `./data`) |
| `-c`, `--config FILE.json` | a different configuration file |
| `-q`, `--question FILE.json` | a different questions file |
| `--out FILE.json` | save single-file results as JSON using the batch schema; cannot be combined with `--batch`; parent folder must exist |
| `-u`, `--update` | check Hugging Face for a newer model version |
| `--model-dir DIR` | a different model folder |
| `--model NAME` | select `multilingual`, `english` or `typed-decisions` for this run; leaves the configured default unchanged |
| `--download-only` | prepare the selected model and exit without inference; combine with `-u` to check/download its latest revision |
| `-d`, `--download MODEL` | download/update `english`, `multilingual` or `typed-decisions` and exit; no input or questions needed, default checkpoint unchanged |
| `-v`, `--verbose` | verbose mode: diagnostic messages about what is going on (see below) |
| `-V`, `--version` | print the program version and model info (see below); with `-u` also queries Hugging Face |

Command-line switches take precedence over the configuration. An input file and `--batch` cannot be combined.

### Examples

One file, everything per the configuration:

```powershell
python cli_laya.py
```

```
File     : ticket.md
Questions: D:\data_codex\laya\question.json
Model    : multilingual (cpu)
department : billing (confidence 1.00)
urgency    : 1.80
churn_risk : 0.028
Total time: 31.85 s (setup and model load 31.27 s, answer 0.58 s)
```

(The timings in this sample are illustrative; the answers are from a real run on the sample ticket.)

A different input and different questions:

```powershell
python cli_laya.py letter.md -q other_questions.json
```

Batch from `./data`:

```powershell
python cli_laya.py --batch
```

```
Batch    : 3 files from D:\data_codex\laya\data
Questions: D:\data_codex\laya\question.json
Model    : multilingual (cpu), loaded in 31.27 s
[1/3] a.md
  department : billing (confidence 0.90)
  urgency    : 1.50
  churn_risk : 0.250
  time: 0.52 s -> a.json
[2/3] b.md
...
Done: 3 of 3 files. Answers total 1.60 s, average 0.53 s/file; whole run 32.9 s (setup and model load 31.27 s)
```

Batch from another folder:

```powershell
python cli_laya.py -b D:\tickets\2026-09
```

Check for a newer model version:

```powershell
python cli_laya.py --update
```

## Input markdown format

Download or update the English checkpoint without running inference:

```powershell
python cli_laya.py --model english -u --download-only
python cli_laya.py -d english
python cli_laya.py project_laya/test3/evaluation.md -q project_laya/test3/question3.json --model english
```

`-u` updates only the selected checkpoint. Without `--model`, the configured
checkpoint is used (`multilingual` by default). `-V -u` remains an information
check, not a download. English weights live at the root of `model_dir`;
multilingual weights remain in its `multilingual` subfolder.

`-d english` is the short form for downloading/updating English without inference.
It checks Hugging Face even when the weights already exist and reuses unchanged
files. It accepts `-c` and `--model-dir`; it cannot be combined with an input,
`--batch`, `--out`, `-V`, or a conflicting `--model` value.

An optional front matter (`key: value` lines between `---`) and a body. Everything is passed to the model as a dictionary, with the body under the key `body`.

```markdown
---
from: john.miller@example.com
subject: Double charge on invoice #4411
---

Hello,

we were charged twice for March. Please refund the duplicate amount
today, otherwise we will have to cancel our plan.
```

The front matter is deliberately simple: every line is `key: value`; nested structures and lists are not supported. A file without front matter is fine, the whole file is then used as the body.

The `multilingual` checkpoint accepts many languages, so the input may be in Czech or any other language it supports.

## Questions (`question.json`)

A JSON object where the key is the question id and the value is its description. You can add, remove and rename questions freely; the program adapts.

```json
{
  "department": {
    "type": "choice",
    "instructions": "Which department should handle this request?",
    "criteria": {
      "billing": "invoices, payments, refunds",
      "technical": "bugs, outages, system errors",
      "sales": "pricing, new contracts",
      "other": "everything else"
    }
  },
  "urgency": {
    "type": "score",
    "instructions": "How urgent is this request?",
    "criteria": ["not urgent", "soon", "critical deadline or blocking issue"]
  },
  "churn_risk": {
    "type": "noul",
    "instructions": "Does the user threaten to cancel or leave?"
  }
}
```

| `type` | `criteria` | output |
|---|---|---|
| `choice` | an object `{option: description}` | the chosen option and its confidence (0-1) |
| `score` | a list of levels from lowest to highest | a number from 0 to (number of levels - 1), i.e. 0-2 for three levels |
| `noul` | not needed | probability of "yes" (0-1) |

`instructions` is required for every type. On a mistake in the file the program prints a clear message (invalid JSON, unknown `type`, wrong shape of `criteria`).

The question and option texts are in English, as in all the examples in the laya documentation. The `multilingual` checkpoint can read input in other languages; English question wording is simply the safest, best-documented choice.

## Configuration (`cli_laya.json`)

```json
{
  "model_dir": "D:\\data_codex\\laya_models",
  "questions": "question.json",
  "input": "ticket.md",
  "batch_dir": "data",

  "checkpoint": "multilingual",
  "device": "cpu",
  "cpu_threads": null,

  "max_len": null,
  "head_max_len": null,

  "update": false
}
```

| key | meaning |
|---|---|
| `model_dir` | folder with the model |
| `questions` | the questions file |
| `input` | default input markdown file |
| `batch_dir` | default folder for batch mode |
| `checkpoint` | `multilingual`, `english` or `typed-decisions` |
| `device` | `cpu` (or `cuda`) |
| `cpu_threads` | number of torch threads on CPU, `null` = default |
| `max_len`, `head_max_len` | context length and token budget for the option descriptions; `null` = the model's own values. Set them if a single `choice` question has many options |
| `update` | `true` = always check for a newer model version |

Rules:

- Relative paths in the JSON are resolved **from the folder that contains the configuration**, not from the current folder, so the program can be run from anywhere.
- Keys starting with `_` (for example `_comment`) are ignored. An unknown key is an error (this catches typos).
- The configuration is looked up next to `cli_laya.py`. If it is missing, the values built into the script are used. A different file is given with `-c`; a missing file given with `-c` is an error.
- Priority: command line, then configuration, then built-in values.

## Batch mode

`--batch` takes every `*.md` from a folder (no subfolders, in alphabetical order) and loads the model only once. Next to each `FILE.md` it saves `FILE.json`; an existing one is overwritten.

Contents of `FILE.json`:

```json
{
  "file": "a.md",
  "questions": "question.json",
  "model": "multilingual",
  "seconds": 0.52,
  "answers": {
    "department": { "choice": "billing", "confidence": 0.9, "...": "..." },
    "urgency": { "score": 1.5, "...": "..." },
    "churn_risk": { "noul": 0.25, "...": "..." }
  },
  "routing": { "model": "multilingual", "...": "..." }
}
```

`answers` holds the complete answer from laya (including the probabilities of the individual options), so the dots in the sample are just abbreviations. The exact structure depends on the laya version.

A bad file (unreadable, model error) prints an error and the batch continues. Its JSON is not created.

## Version and model information

```powershell
python cli_laya.py -V          # local information only, works offline
python cli_laya.py -V -u       # additionally queries Hugging Face (needs internet)
```

The output contains the program version (`__version__` in `cli_laya.py`), the version of the installed `laya` package, the model folder and, for each of the three checkpoints:

- a description (encoder, parameter count, context, languages; taken from the laya documentation),
- whether it is downloaded, its size and download date,
- the shortened revision (commit) of the repo it was downloaded from (written by `huggingface_hub` when downloading into `local_dir`),
- `encoder`, `max_len` and `head_max_len` read from the downloaded model's own configuration.

With `-u` the program asks Hugging Face for the latest repo revision and its change date and compares it with the revision of the local copy. A revision covers the whole repo (all three checkpoints at once), so "the repo has a newer revision" does not mean that your checkpoint changed. Without internet the program just reports that Hugging Face is unavailable.

Information that is not available (for example the revision of a model downloaded some other way) is shown as "unknown". laya publishes no version number for the model itself, so a model is identified by its download date and revision.

## Verbose mode (`-v`)

Loading the model takes tens of seconds and, without any output, it looks as if the program had stalled. With `-v` the program reports what it is doing. Diagnostic messages go to **stderr**, so the results on stdout stay clean and can be redirected (`python cli_laya.py -b > results.txt`) without diagnostic noise. Every message starts with the time since the program started.

```powershell
python cli_laya.py -v
```

```
[   0.00 s] cli_laya 0.1.1, Python 3.10.x, Windows-10-...
[   0.00 s] configuration file: D:\data_codex\laya\cli_laya.json
[   0.00 s]   model_dir = 'D:\\data_codex\\laya_models'
[   0.00 s]   checkpoint = 'multilingual'
...
[   0.01 s] questions: question.json (count 3: department:choice, urgency:score, churn_risk:noul)
[   0.01 s] input: ticket.md, 35 words, 190 characters, keys ['from', 'subject', 'body']
[   0.01 s] model: looking for D:\data_codex\laya_models\multilingual\model.safetensors -> found
[   0.01 s] model is stored locally, not checking the network (no --update)
[   0.01 s] loading libraries (torch, transformers, laya) ...
[   9.80 s] libraries loaded in 9.79 s (torch 2.x, transformers 4.x, laya 0.3.4)
[   9.80 s] loading model multilingual from D:\data_codex\laya_models\multilingual (device cpu) ...
[  31.10 s] model loaded in 21.30 s
[  31.10 s] model parameters: max_len=1024, head_max_len=256
[  31.11 s] sending query for ticket.md (questions: 3)
[  31.55 s] routing: {'model': 'multilingual', ...}
[  31.55 s] answer in 0.44 s
```

(Times and versions in the sample are illustrative.) It reports:

- the environment (program and Python version, system, working directory),
- the effective configuration after merging the file and the switches,
- the loaded questions and the input file (word and character counts, front matter keys),
- the model check (found / being downloaded; with `--update` also the duration of `snapshot_download`),
- loading of the libraries and of the model separately, with times, the torch/transformers/laya versions, the number of torch threads and CUDA availability,
- overridden parameters (`max_len`, `head_max_len`) and the values the model actually runs with,
- the routing from the laya answer,
- in batch mode, for every file also the input, the routing and the written JSON; on an error the full traceback.

The difference from `-V`: capital `-V` prints the version and model information and exits, lowercase `-v` makes the normal processing more talkative.

## Exit codes

### Project logging and database records

When `project.json` is present next to the script, `cli_laya.py` uses its active
`subdir`, `selector`, `log` and `db` settings. The switches are independent:

- `log: true` captures stdout/stderr in the active project's `log.txt` and adds
  a structured `laya_result` event with the input, questions, configuration,
  routing, result and inference time. When runner already captures the console
  (`OLLAMA_FLOW_LOG=1`), the CLI does not duplicate that console capture.
- `db: true` records each successfully completed input in `data/tasks.db`, using
  the shared task schema and active project/selector. Input and questions are
  stored as JSON in `prompt` and `instruction`; `answer` contains the full model
  result. `parameters` includes paths, configuration and inference time; `key1`
  also contains inference seconds. This works without `--out`.
- Batch mode creates one record per successful file. A failed prediction or
  output/database write reports an error, returns a nonzero final status, and
  does not prevent later batch files from running. Version/help commands do not
  create inference records.

Without `project.json`, standalone operation has logging and database recording
disabled. No additional dependencies are needed for this integration.

| code | meaning |
|---|---|
| `0` | everything went fine |
| `1` | an error (missing file/folder, invalid configuration or questions, incompatible switches) or at least one file in a batch failed |

## How it works inside

1. The configuration and the questions are loaded and validated.
2. The model is looked up in `model_dir`. If it is missing (or `--update` is given), it is downloaded with `snapshot_download(..., local_dir=...)`.
3. The checkpoint is loaded straight from the local folder (`Agent`) and handed to the router (`Router.attach`), which therefore downloads nothing else.
4. `router.predict(..., model=checkpoint)` answers all questions in one pass. The chosen checkpoint is forced, so the router does not choose one by language.

Time is measured from the start of `main()` to the moment the answer is returned, split into setup and model load, and the answer itself. The start of the Python interpreter is not counted.

## Limitations and honest caveats

- **Accuracy.** According to the laya documentation, the base checkpoints are weak zero-shot, close to chance on their own benchmark. The multilingual one also has no calibrated probabilities. On the sample ticket the department `billing` and urgency 1.80 out of 2 came out right, but the churn risk was 0.028 even though the ticket explicitly threatens to cancel the plan, and a confidence of 1.00 is overconfident. Treat the outputs as a demonstration, not as reliable decisions. For real use the model would have to be fine-tuned on your own data (laya ships a fine-tuning notebook).
- **Many options.** The option descriptions share a limited token budget. With dozens of options in one `choice` question accuracy drops sharply; raise `head_max_len`/`max_len` or split the options into two steps.
- **Untested parts.** In practice only `multilingual` on CPU has been tested. The `english` and `typed-decisions` checkpoints and `device: "cuda"` are supported by the program but untested.
- **Calibration temperatures** (`temperature`) are not exposed in the configuration.
- **Performance.** According to the documentation an answer takes roughly 200-450 ms on CPU, and loading the model a few seconds to tens of seconds. The real numbers are shown in the output.

## Links

- PyPI: <https://pypi.org/project/laya/>
- Model: <https://huggingface.co/convaiinnovations/laya>
- Source code: <https://github.com/NandhaKishorM/laya>
