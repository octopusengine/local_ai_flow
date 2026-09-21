"""Small file bridge for the two Laya demo flows; no model calls or shell execution."""
import argparse
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LANGUAGE_CODES = {"English": "en", "Czech": "cs"}


def read(path):
    return path.read_text(encoding="utf-8")


def write(path, content):
    path.write_text(content, encoding="utf-8")


def number(answer, key, maximum):
    value = answer[key]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{key} must be numeric")
    if not math.isfinite(value) or not 0 <= value <= maximum:
        raise ValueError(f"{key} must be between 0 and {maximum}")
    return value


def decide(answers, test):
    """Conservative demo thresholds, not calibrated confidence guarantees."""
    if test == 2:
        answer = answers["language"]
        choice = answer["choice"]
        if choice not in LANGUAGE_CODES:
            raise ValueError(f"Unknown language: {choice}")
        confidence = number(answer, "confidence", 1)
        return LANGUAGE_CODES[choice] if confidence >= 0.7 else "review"
    answer = answers["action"]
    choice = answer["choice"]
    if choice not in {"accept", "revise", "clarify"}:
        raise ValueError(f"Unknown action: {choice}")
    confidence = number(answer, "confidence", 1)
    grounded = number(answers["grounded"], "noul", 1)
    quality = number(answers["quality"], "score", 2)
    if confidence < 0.7:
        return "review"
    if choice == "accept" and (grounded < 0.7 or quality < 1.5):
        return "revise"
    return choice


def prepare(project, test):
    project.mkdir(parents=True, exist_ok=True)
    sources = ("en", "cs") if test == 2 else ("customer", "history", "facts")
    for name in sources:
        if not (project / f"{name}.md").exists():
            write(project / f"{name}.md", read(ROOT / "data_laya" / f"test{test}_{name}.md"))
    # Remove only known generated demo artifacts, so reruns cannot reuse stale decisions.
    outputs = ([f"{name}{suffix}" for name in ("en", "cs")
                for suffix in (".json", "_translated.md", "_translated.json",
                               "_report.json", "_verification.json")] if test == 2 else
               ["draft.md", "evaluation.md", "evaluation.json", "evaluation_report.json",
                "final.md", "final_evaluation.md", "final_evaluation.json",
                "final_evaluation_report.json"])
    outputs += [f"{name}_{route}.flag" for name in ("en", "cs", "evaluation", "final_evaluation")
                for route in ("en", "cs", "review", "accept", "revise", "clarify")]
    for name in outputs:
        (project / name).unlink(missing_ok=True)


def route(project, test, name):
    for action in ("en", "cs", "review", "accept", "revise", "clarify"):
        (project / f"{name}_{action}.flag").unlink(missing_ok=True)
    answers = json.loads(read(project / f"{name}.json"))["answers"]
    action = decide(answers, test)
    report = {"route": action, "answers": answers}
    if test == 2:
        report["expected_source_language"] = {"en": "English", "cs": "Czech"}[name]
        report["source_language_correct"] = LANGUAGE_CODES[answers["language"]["choice"]] == name
    write(project / f"{name}_report.json", json.dumps(report, ensure_ascii=False, indent=2))
    write(project / f"{name}_{action}.flag", action + "\n")
    print(json.dumps(report, ensure_ascii=False, indent=2))


def pack(project, name):
    draft = "draft.md" if name == "evaluation" else "final.md"
    parts = [(label, read(project / filename)) for label, filename in (
        ("CUSTOMER MESSAGE", "customer.md"), ("HISTORY", "history.md"),
        ("VERIFIED FACTS", "facts.md"), ("DRAFT", draft))]
    write(project / f"{name}.md", "\n\n".join(f"# {label}\n{text}" for label, text in parts))


def verify(project, name):
    source = json.loads(read(project / f"{name}.json"))["answers"]["language"]["choice"]
    target = {"English": "Czech", "Czech": "English"}[source]
    actual = json.loads(read(project / f"{name}_translated.json"))["answers"]["language"]
    report = {"expected_target": target, "detected": actual,
              "passed": actual["choice"] == target and number(actual, "confidence", 1) >= 0.7}
    write(project / f"{name}_verification.json", json.dumps(report, ensure_ascii=False, indent=2))
    print(json.dumps(report, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "route", "pack", "verify", "accept"))
    parser.add_argument("--test", type=int, choices=(2, 3), required=True)
    parser.add_argument("--name", choices=("en", "cs", "evaluation", "final_evaluation"))
    args = parser.parse_args()
    project = ROOT / "project_laya" / f"test{args.test}"
    try:
        if args.action == "prepare":
            prepare(project, args.test)
        elif args.action == "accept":
            if args.test != 3:
                raise ValueError("accept requires test 3")
            write(project / "final.md", read(project / "draft.md"))
        else:
            valid_names = ("en", "cs") if args.test == 2 else ("evaluation", "final_evaluation")
            if args.name not in valid_names:
                raise ValueError("--name must match the selected test")
            if args.action == "route":
                route(project, args.test, args.name)
            elif args.action == "pack" and args.test == 3:
                pack(project, args.name)
            elif args.action == "verify" and args.test == 2:
                verify(project, args.name)
            else:
                raise ValueError("Action does not apply to this test")
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.exit(1, f"Laya flow: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
