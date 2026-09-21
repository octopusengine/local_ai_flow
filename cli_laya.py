"""cli_laya.py - process markdown (front matter + body) with the laya model (RLCD).

Settings are read from cli_laya.json (next to this script); command-line switches take precedence.

Examples:
    python cli_laya.py                      # one file (ticket.md), everything per cli_laya.json
    python cli_laya.py letter.md            # a different input file
    python cli_laya.py --batch              # batch: every *.md in ./data -> *.json next to it
    python cli_laya.py -b other_folder      # batch from a different folder
    python cli_laya.py -q other.json        # a different questions file
    python cli_laya.py -c mine.json         # a different configuration file
    python cli_laya.py --update             # check for (and download) a newer model version
    python cli_laya.py -V                   # program version and model info (local only)
    python cli_laya.py -V -u                # same + query Hugging Face (needs internet)
    python cli_laya.py -v -b                # verbose: what is going on right now (stderr)
"""
import argparse
import json
import os
import platform
import sys
import time
import traceback
from datetime import datetime
from importlib import metadata as importlib_metadata
from pathlib import Path

from lib.wrapp_log import console_log, get_project_directory, load_project_config, log_event, read_log_enabled
from lib.wrapp_db import (
    DEFAULT_TASKS_DATABASE_PATH, DEFAULT_TASKS_SCHEMA_PATH,
    read_db_enabled, read_db_selector, record_task_output,
)

__version__ = "0.1.1"

os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

# Verbose mode (-v): diagnostics go to stderr, so results on stdout stay clean
_verbose = False
_t0 = time.perf_counter()


def vlog(msg: str) -> None:
    if _verbose:
        print(f"[{time.perf_counter() - _t0:7.2f} s] {msg}", file=sys.stderr, flush=True)


def _pkg_version(name: str) -> str:
    try:
        return importlib_metadata.version(name)
    except importlib_metadata.PackageNotFoundError:
        return "not installed"


REPO = "convaiinnovations/laya"
DEFAULT_CONFIG = Path(__file__).resolve().parent / "cli_laya.json"
PROJECT_ROOT = Path(__file__).resolve().parent
QUESTION_TYPES = ("choice", "score", "noul")
# checkpoint -> subfolder in the repo (None = repo root, i.e. the English model)
CHECKPOINTS = {"english": None, "multilingual": "multilingual", "typed-decisions": "typed-decisions"}

# Short checkpoint descriptions, taken from the laya documentation (PyPI / Hugging Face)
CHECKPOINT_INFO = {
    "english": "ModernBERT-large, 421M parameters, context 512, English",
    "multilingual": "mmBERT-base, 322M parameters, context 1024, 100+ languages",
    "typed-decisions": "ModernBERT-large, 421M parameters, context 1024, fine-tuned on 4 workflows",
}

# Built-in defaults, used when a key is missing from the configuration
DEFAULTS = {
    "model_dir": r"D:\data_codex\laya_models",
    "questions": "question.json",
    "input": "ticket.md",
    "batch_dir": "data",
    "checkpoint": "multilingual",
    "device": "cpu",
    "cpu_threads": None,
    "max_len": None,
    "head_max_len": None,
    "update": False,
}
PATH_KEYS = ("model_dir", "questions", "input", "batch_dir")


def validate_config(cfg: dict, where: str) -> None:
    if cfg["checkpoint"] not in CHECKPOINTS:
        raise ValueError(f"{where}: 'checkpoint' must be one of {tuple(CHECKPOINTS)}")
    if not isinstance(cfg["device"], str) or not cfg["device"]:
        raise ValueError(f"{where}: 'device' must be a string (e.g. \"cpu\" or \"cuda\")")
    for key in ("cpu_threads", "max_len", "head_max_len"):
        v = cfg[key]
        if v is not None and (not isinstance(v, int) or isinstance(v, bool) or v < 1):
            raise ValueError(f"{where}: '{key}' must be a positive integer or null")
    if not isinstance(cfg["update"], bool):
        raise ValueError(f"{where}: 'update' must be true or false")
    for key in PATH_KEYS:
        if not isinstance(cfg[key], str) or not cfg[key]:
            raise ValueError(f"{where}: '{key}' must be a path (string)")


def load_config(path: Path, required: bool) -> dict:
    """Defaults + values from the JSON file. Relative paths in the file are resolved from its folder."""
    cfg = dict(DEFAULTS)
    if not path.is_file():
        if required:
            raise ValueError(f"Configuration not found: {path}")
        return cfg
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ValueError(f"{path}: invalid JSON ({e})")
    if not isinstance(data, dict):
        raise ValueError(f"{path}: expected a JSON object")
    unknown = [k for k in data if k not in DEFAULTS and not k.startswith("_")]
    if unknown:
        raise ValueError(f"{path}: unknown keys {unknown}; allowed: {list(DEFAULTS)}")
    for key, value in data.items():
        if key.startswith("_"):
            continue
        if key in PATH_KEYS and isinstance(value, str) and value and not Path(value).is_absolute():
            value = str(path.parent / value)
        cfg[key] = value
    validate_config(cfg, str(path))
    return cfg


def parse_markdown(path: Path) -> dict:
    """Front matter (key: value lines between ---) + body -> 'state' dict."""
    text = path.read_text(encoding="utf-8")
    state = {}
    body = text
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) == 3:
            _, front, body = parts
            for line in front.strip().splitlines():
                key, _, value = line.partition(":")
                if key.strip():
                    state[key.strip()] = value.strip()
    state["body"] = body.strip()
    return state


def load_questions(path: Path) -> dict:
    """Load and validate the questions file. Raises ValueError with a description on error."""
    try:
        questions = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ValueError(f"{path}: invalid JSON ({e})")
    if not isinstance(questions, dict) or not questions:
        raise ValueError(f"{path}: expected a non-empty object {{question_id: {{...}}}}")
    for qid, q in questions.items():
        if not isinstance(q, dict) or q.get("type") not in QUESTION_TYPES:
            raise ValueError(f"{path}: question '{qid}' must have a 'type' from {QUESTION_TYPES}")
        if not q.get("instructions"):
            raise ValueError(f"{path}: question '{qid}' has no 'instructions'")
        if q["type"] == "choice" and not isinstance(q.get("criteria"), dict):
            raise ValueError(f"{path}: 'choice' question '{qid}' needs 'criteria' as an object "
                             f"{{option: description}}")
        if q["type"] == "score" and not isinstance(q.get("criteria"), list):
            raise ValueError(f"{path}: 'score' question '{qid}' needs 'criteria' as a list "
                             f"(from the lowest to the highest level)")
    return questions


def format_answer(qtype: str, ans: dict) -> str:
    if qtype == "choice":
        return f"{ans['choice']} (confidence {ans['confidence']:.2f})"
    if qtype == "score":
        return f"{ans['score']:.2f}"
    return f"{ans['noul']:.3f}"


def print_answers(questions: dict, answers: dict, indent: str = "") -> None:
    width = max(len(qid) for qid in questions)
    for qid, q in questions.items():
        print(f"{indent}{qid:<{width}} : {format_answer(q['type'], answers[qid])}", flush=True)


def _json_default(obj):
    """Fallback conversion for values json cannot handle (e.g. numpy numbers)."""
    return obj.tolist() if hasattr(obj, "tolist") else str(obj)


def _fmt_time(ts: float) -> str:
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")


def local_checkpoint_info(model_dir: Path, checkpoint: str):
    """Info about the downloaded copy of a checkpoint, or None if not downloaded. Best effort."""
    sub = CHECKPOINTS[checkpoint]
    base = model_dir / (sub or "")
    weights = base / "model.safetensors"
    if not weights.is_file():
        return None
    st = weights.stat()
    info = {"size": st.st_size, "when": st.st_mtime, "commit": None,
            "encoder": None, "max_len": None, "head_max_len": None}
    # when downloading into local_dir, huggingface_hub writes: commit, etag, download time
    meta = model_dir / ".cache" / "huggingface" / "download" / (sub or "") / "model.safetensors.metadata"
    try:
        lines = meta.read_text(encoding="utf-8").splitlines()
        info["commit"] = lines[0].strip() or None
        info["when"] = float(lines[2])
        vlog(f"{checkpoint}: metadata read from {meta}")
    except Exception:
        vlog(f"{checkpoint}: metadata {meta} not available (revision unknown)")
    try:
        model_cfg = json.loads((base / "rl_agent_config.json").read_text(encoding="utf-8"))
        for key in ("encoder", "max_len", "head_max_len"):
            info[key] = model_cfg.get(key)
    except Exception:
        pass
    return info


def remote_repo_info():
    """(info, error): the latest repo revision on Hugging Face. Needs internet."""
    try:
        from huggingface_hub import HfApi

        vlog(f"querying Hugging Face for {REPO} (timeout 10 s)")
        mi = HfApi().model_info(REPO, timeout=10)
        vlog(f"Hugging Face answered: revision {mi.sha}")
        return {"sha": mi.sha, "modified": mi.last_modified}, None
    except Exception as e:
        text = str(e).strip().splitlines()[0][:120] if str(e).strip() else ""
        return None, f"{type(e).__name__}: {text}".rstrip(": ")


def print_model_info(model_dir: Path, check_remote: bool) -> None:
    print(f"laya (package) : {_pkg_version('laya')}")
    print(f"Model repo     : {REPO}")
    print(f"Model folder   : {model_dir}")

    downloaded = {}
    for name in CHECKPOINTS:
        info = local_checkpoint_info(model_dir, name)
        print(f"\n{name}")
        print(f"  description : {CHECKPOINT_INFO[name]}")
        if info is None:
            print("  status      : not downloaded")
            continue
        downloaded[name] = info
        print(f"  status      : downloaded, {info['size'] / 1e6:.0f} MB, {_fmt_time(info['when'])}")
        print(f"  revision    : {info['commit'][:8] if info['commit'] else 'unknown'}")
        if info["encoder"]:
            print(f"  from config : encoder {info['encoder']}, max_len {info['max_len']}, "
                  f"head_max_len {info['head_max_len']}")

    print()
    if not check_remote:
        print("To check freshness on Hugging Face: python cli_laya.py -V -u (needs internet)")
        return
    remote, error = remote_repo_info()
    if remote is None:
        print(f"Hugging Face: unavailable ({error})")
        return
    modified = remote["modified"]
    when = modified.astimezone().strftime("%Y-%m-%d %H:%M") if modified else "unknown"
    print(f"Hugging Face: repo last changed {when}, revision {remote['sha'][:8]}")
    for name, info in downloaded.items():
        if not info["commit"]:
            verdict = "revision of the local copy is unknown (cannot compare)"
        elif info["commit"] == remote["sha"]:
            verdict = "local copy is from the latest repo revision"
        else:
            verdict = "the repo has a newer revision (it may not affect this checkpoint)"
        print(f"  {name}: {verdict}")


def ensure_model(model_dir: Path, checkpoint: str, update: bool) -> None:
    """Download the model only when it is missing or --update was given."""
    sub = CHECKPOINTS[checkpoint]
    weights = model_dir / (sub or "") / "model.safetensors"
    present = weights.exists()
    vlog(f"model: looking for {weights} -> {'found' if present else 'not found'}")
    if present and not update:
        vlog("model is stored locally, not checking the network (no --update)")
        return
    from huggingface_hub import snapshot_download

    print("Checking for a newer model / downloading ..." if present else "Model missing, downloading ...",
          file=sys.stderr, flush=True)
    if sub:
        patterns = {"allow_patterns": [f"{sub}/*"]}
    else:  # the English model lives in the repo root; skip the other models' subfolders
        patterns = {"ignore_patterns": [f"{s}/*" for s in CHECKPOINTS.values() if s]}
    vlog(f"snapshot_download({REPO}, local_dir={model_dir}, {patterns})")
    t_dl = time.perf_counter()
    snapshot_download(REPO, local_dir=str(model_dir), **patterns)
    vlog(f"snapshot_download finished in {time.perf_counter() - t_dl:.2f} s")


def run_batch(router, checkpoint: str, questions: dict, files: list, qfile: Path,
              t_start: float, t_loaded: float, record_result=None, cfg=None) -> int:
    """Process the files one by one; save a JSON with the answer next to each."""
    done, failed, answer_time = 0, 0, 0.0
    total = len(files)
    for i, src in enumerate(files, 1):
        print(f"[{i}/{total}] {src.name}", flush=True)
        try:
            state = parse_markdown(src)
            vlog(f"  input: {len(state['body'].split())} words, keys {list(state)}")
            t0 = time.perf_counter()
            result = router.predict(state, questions, model=checkpoint)
            elapsed = time.perf_counter() - t0
            vlog(f"  routing: {result.get('routing')}")
            print_answers(questions, result["answers"], indent="  ")
            out = src.with_suffix(".json")
            payload = {
                "file": src.name,
                "questions": qfile.name,
                "model": checkpoint,
                "seconds": round(elapsed, 3),
                "answers": result["answers"],
                "routing": result.get("routing"),
            }
            out.write_text(json.dumps(payload, ensure_ascii=False, indent=2,
                                      default=_json_default), encoding="utf-8")
            print(f"  time: {elapsed:.2f} s -> {out.name}", flush=True)
            vlog(f"  written {out} ({out.stat().st_size} B)")
            if record_result is not None:
                record_result(src, qfile, questions, state, result, cfg, elapsed, out)
            done += 1
            answer_time += elapsed
        except Exception as e:  # one bad file must not stop the whole batch
            failed += 1
            print(f"  ERROR: {type(e).__name__}: {e}", file=sys.stderr, flush=True)
            if _verbose:
                traceback.print_exc()
    t_end = time.perf_counter()
    avg = f", average {answer_time / done:.2f} s/file" if done else ""
    print(f"Done: {done} of {total} files" + (f", {failed} failed" if failed else "")
          + f". Answers total {answer_time:.2f} s{avg}; "
          f"whole run {t_end - t_start:.2f} s (setup and model load {t_loaded - t_start:.2f} s)",
          flush=True)
    return 1 if failed else 0


def run_cli(record_result=None) -> int:
    global _verbose, _t0
    t_start = _t0 = time.perf_counter()
    ap = argparse.ArgumentParser(description="Process markdown files with the laya model.")
    ap.add_argument("input", nargs="?", default=None,
                    help="input .md file (default from the configuration)")
    ap.add_argument("-b", "--batch", nargs="?", const=True, default=None, metavar="DIR",
                    help="batch: process every *.md in a folder (default: 'batch_dir' from the "
                         "configuration, i.e. ./data) and save a same-named .json next to each")
    ap.add_argument("-c", "--config", metavar="FILE.json", default=None,
                    help=f"configuration file (default: {DEFAULT_CONFIG.name} next to the script)")
    ap.add_argument("-q", "--question", metavar="FILE.json", default=None,
                    help="JSON file with the questions (default from the configuration)")
    ap.add_argument("-u", "--update", action="store_true",
                    help="check Hugging Face and download a newer model version if there is one")
    ap.add_argument("--model-dir", default=None, help="model folder (default from the configuration)")
    ap.add_argument("--model", choices=tuple(CHECKPOINTS),
                    help="checkpoint to use for this run (default: checkpoint from configuration)")
    ap.add_argument("--download-only", action="store_true",
                    help="download/check the selected checkpoint and exit; use -u to check for updates")
    ap.add_argument("-V", "--version", action="store_true",
                    help="print the program version and model info; with -u also query Hugging Face")
    ap.add_argument("-v", "--verbose", action="store_true",
                    help="verbose mode: diagnostic messages (loading, configuration, timings) on stderr")
    ap.add_argument("--out", type=Path, metavar="FILE.json",
                    help="save single-file answers as JSON (cannot be combined with --batch)")
    args = ap.parse_args()
    _verbose = args.verbose
    vlog(f"cli_laya {__version__}, Python {sys.version.split()[0]}, {platform.platform()}")
    vlog(f"working directory: {Path.cwd()}")

    if args.version:
        print(f"cli_laya {__version__}")

    if args.batch and (args.input or args.out):
        print("Give either an input file/--out or --batch, not both.", file=sys.stderr)
        return 1
    try:
        cfg_path = Path(args.config) if args.config else DEFAULT_CONFIG
        cfg = load_config(cfg_path, required=bool(args.config))
    except ValueError as e:
        print(e, file=sys.stderr)
        return 1
    # Command-line switches take precedence over the configuration
    if args.input:
        cfg["input"] = args.input
    if isinstance(args.batch, str):
        cfg["batch_dir"] = args.batch
    if args.question:
        cfg["questions"] = args.question
    if args.model_dir:
        cfg["model_dir"] = args.model_dir
    if args.model:
        cfg["checkpoint"] = args.model
    if args.update:
        cfg["update"] = True
    vlog(f"configuration file: {cfg_path}" + ("" if cfg_path.is_file()
         else " (not found, using built-in defaults)"))
    for key, value in cfg.items():
        vlog(f"  {key} = {value!r}")

    if args.version:
        print()
        print_model_info(Path(cfg["model_dir"]), check_remote=cfg["update"])
        return 0

    if args.download_only:
        ensure_model(Path(cfg["model_dir"]), cfg["checkpoint"], cfg["update"])
        print(f"Model ready: {cfg['checkpoint']} in {cfg['model_dir']}")
        return 0

    qfile, model_dir = Path(cfg["questions"]), Path(cfg["model_dir"])
    if not qfile.is_file():
        print(f"Questions file not found: {qfile}", file=sys.stderr)
        return 1
    try:
        questions = load_questions(qfile)
    except ValueError as e:
        print(e, file=sys.stderr)
        return 1
    vlog(f"questions: {qfile} (count {len(questions)}: "
         + ", ".join(f"{qid}:{q['type']}" for qid, q in questions.items()) + ")")

    files, src = [], None
    if args.batch:
        batch_dir = Path(cfg["batch_dir"])
        if not batch_dir.is_dir():
            print(f"Folder not found: {batch_dir}", file=sys.stderr)
            return 1
        files = sorted(batch_dir.glob("*.md"))
        if not files:
            print(f"No *.md files in folder {batch_dir}.", file=sys.stderr)
            return 1
        vlog(f"batch: folder {batch_dir}, *.md files found: {len(files)}")
    else:
        src = Path(cfg["input"])
        if not src.is_file():
            print(f"File not found: {src}", file=sys.stderr)
            return 1
        state = parse_markdown(src)
        vlog(f"input: {src}, {len(state['body'].split())} words, "
             f"{len(state['body'])} characters, keys {list(state)}")

    checkpoint, sub = cfg["checkpoint"], CHECKPOINTS[cfg["checkpoint"]]
    ensure_model(model_dir, checkpoint, cfg["update"])

    # Import only after the model is ready (torch/transformers take long to load)
    vlog("loading libraries (torch, transformers, laya) ...")
    t_imp = time.perf_counter()
    import torch
    from laya import Router
    from laya.agent import Agent

    t_imported = time.perf_counter()
    vlog(f"libraries loaded in {t_imported - t_imp:.2f} s (torch {getattr(torch, '__version__', '?')}, "
         f"transformers {_pkg_version('transformers')}, laya {_pkg_version('laya')})")
    try:
        vlog(f"torch: threads {torch.get_num_threads()}, CUDA available: {torch.cuda.is_available()}")
    except Exception:
        pass

    if cfg["cpu_threads"]:
        torch.set_num_threads(cfg["cpu_threads"])
        vlog(f"set torch.set_num_threads({cfg['cpu_threads']})")
    vlog(f"loading model {checkpoint} from {model_dir / (sub or '')} (device {cfg['device']}) ...")
    t_mod = time.perf_counter()
    agent = Agent(str(model_dir), subfolder=sub, device=cfg["device"])
    vlog(f"model loaded in {time.perf_counter() - t_mod:.2f} s")
    for key in ("max_len", "head_max_len"):
        if cfg[key]:
            vlog(f"overriding agent.cfg[{key!r}]: {agent.cfg.get(key)!r} -> {cfg[key]!r}")
            agent.cfg[key] = cfg[key]
    vlog(f"model parameters: max_len={agent.cfg.get('max_len')}, "
         f"head_max_len={agent.cfg.get('head_max_len')}")
    router = Router(device=cfg["device"])
    router.attach(checkpoint, agent)
    vlog(f"router created, checkpoint {checkpoint!r} registered (queries will use model={checkpoint!r})")
    t_loaded = time.perf_counter()

    if args.batch:
        print(f"Batch    : {len(files)} files from {batch_dir}", flush=True)
        print(f"Questions: {qfile}", flush=True)
        print(f"Model    : {checkpoint} ({cfg['device']}), loaded in "
              f"{t_loaded - t_start:.2f} s", flush=True)
        vlog(f"starting batch processing (files: {len(files)}); libraries "
             f"{t_imported - t_imp:.2f} s, total until model loaded {t_loaded - t_start:.2f} s")
        return run_batch(router, checkpoint, questions, files, qfile, t_start, t_loaded,
                         record_result, cfg)

    # model=... forces the chosen checkpoint so the router does not try to download another one
    vlog(f"sending query for {src.name} (questions: {len(questions)})")
    result = router.predict(state, questions, model=checkpoint)
    t_end = time.perf_counter()
    vlog(f"routing: {result.get('routing')}")
    vlog(f"answer in {t_end - t_loaded:.2f} s")

    print(f"File     : {src}")
    print(f"Questions: {qfile}")
    print(f"Model    : {checkpoint} ({cfg['device']})")
    print_answers(questions, result["answers"])
    if args.out:
        payload = {
            "file": str(src), "questions": str(qfile), "model": checkpoint,
            "seconds": t_end - t_loaded, "answers": result["answers"],
            "routing": result.get("routing"),
        }
        try:
            args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2,
                                           default=_json_default) + "\n", encoding="utf-8")
        except OSError as error:
            print(f"Cannot write {args.out}: {error}", file=sys.stderr)
            return 1
    print(f"Total time: {t_end - t_start:.2f} s "
          f"(setup and model load {t_loaded - t_start:.2f} s, "
          f"answer {t_end - t_loaded:.2f} s)")
    if record_result is not None:
        record_result(src, qfile, questions, state, result, cfg, t_end - t_loaded, args.out)
    return 0


def main() -> int:
    """Share project logging and task storage with the other flow CLIs."""
    try:
        # Keep the standalone tool usable without a project.json.
        project_config = load_project_config(PROJECT_ROOT) if (PROJECT_ROOT / "project.json").is_file() else {
            "subdir": ".", "log": False, "db": False,
        }
        project_directory = get_project_directory(PROJECT_ROOT, project_config)
        log_enabled = read_log_enabled(PROJECT_ROOT / "project.json") if (PROJECT_ROOT / "project.json").is_file() else False
        db_enabled = read_db_enabled(project_config)
        selector = read_db_selector(project_config)
    except (OSError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1

    def record_result(src, qfile, questions, state, result, cfg, elapsed, out):
        # Normalize tensor/numpy values before passing them to shared JSON writers.
        result = json.loads(json.dumps(result, ensure_ascii=False, default=_json_default))
        parameters = {
            "program": "cli_laya.py", "task_kind": "rlpc_laya",
            "input_file": str(src.resolve()), "questions_file": str(qfile.resolve()),
            "output_file": str(out.resolve()) if out else None,
            "config": cfg, "questions": questions, "routing": result.get("routing"),
            "answer_seconds": elapsed,
        }
        if log_enabled:
            log_event(project_directory, "cli_laya.py", {
                "event": "laya_result", "input": state, "parameters": parameters,
                "result": result,
            })
        if db_enabled:
            uid = record_task_output(
                PROJECT_ROOT / DEFAULT_TASKS_DATABASE_PATH,
                PROJECT_ROOT / DEFAULT_TASKS_SCHEMA_PATH,
                project=str(project_directory.relative_to(PROJECT_ROOT.resolve())),
                selector=selector, task=f"cli_laya.py:{qfile.name}",
                model=f"laya:{cfg['checkpoint']}", parameters=parameters,
                prompt=json.dumps(state, ensure_ascii=False),
                instruction=json.dumps(questions, ensure_ascii=False),
                answer=json.dumps(result, ensure_ascii=False), key1=f"{elapsed:.3f}",
            )
            print(f"Task recorded in data/tasks.db: {uid}")

    with console_log(project_directory, "cli_laya.py", log_enabled):
        try:
            return run_cli(record_result)
        except Exception as error:
            print(f"ERROR: {type(error).__name__}: {error}", file=sys.stderr)
            if _verbose:
                traceback.print_exc()
            return 1


if __name__ == "__main__":
    sys.exit(main())
