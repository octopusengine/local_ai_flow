"""Build, optionally broadcast, and verify one educational OBT MCP transaction."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from lib.mcp_obt import obt_build_transaction, obt_get_balance, obt_send_transaction
from lib.wrapp_log import get_project_directory, load_project_config
from lib.wrapp_terminal import Terminal


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_PLAN_FILENAME = "obt_transaction.json"


def positive_integer(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("must be a positive integer") from error
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return parsed


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build and optionally broadcast one signed educational OBT transaction."
    )
    parser.add_argument("--addr", required=True, help="recipient four-character hexadecimal OBT address")
    parser.add_argument("--val", required=True, type=positive_integer, help="positive OBT amount to send")
    parser.add_argument(
        "--utxo-txid", type=positive_integer, help="specific sender UTXO to spend; otherwise choose the smallest sufficient UTXO"
    )
    parser.add_argument(
        "--confirm", action="store_true", help="broadcast after printing and saving the signed transaction JSON"
    )
    parser.add_argument("--no-db", action="store_true", help="do not write completed steps to data/tasks.db")
    parser.add_argument(
        "--out", default=DEFAULT_PLAN_FILENAME, metavar="FILE", help=f"signed transaction JSON filename (default: {DEFAULT_PLAN_FILENAME})"
    )
    return parser.parse_args()


def resolve_output_path(project_directory: Path, filename: str) -> Path:
    path = Path(filename)
    if path.name != filename or filename in {"", ".", ".."}:
        raise ValueError("--out must be a filename directly inside the active project directory.")
    return project_directory / path


def write_output(path: Path, content: str) -> None:
    path.write_text(content + ("" if content.endswith("\n") else "\n"), encoding="utf-8-sig")


def record_step(
    *,
    project_directory: Path,
    selector: str,
    task: str,
    arguments: dict[str, object],
    answer: str,
    output_path: Path,
) -> None:
    from lib.wrapp_db import DEFAULT_TASKS_DATABASE_PATH, DEFAULT_TASKS_SCHEMA_PATH, record_task_output

    uid = record_task_output(
        PROJECT_ROOT / DEFAULT_TASKS_DATABASE_PATH,
        PROJECT_ROOT / DEFAULT_TASKS_SCHEMA_PATH,
        project=str(project_directory.resolve().relative_to(PROJECT_ROOT.resolve())),
        selector=selector,
        task=f"mcp/{task}",
        model="OBT BBR API",
        parameters={"mcp_function": task, "mcp_arguments": arguments, "output_file": output_path.name},
        prompt=f"Call MCP {task} with {json.dumps(arguments, ensure_ascii=False, sort_keys=True)}.",
        instruction="Educational OBT transaction flow.",
        answer=answer,
    )
    print(f"Task recorded in data/tasks.db: {uid}")


def complete_step(
    terminal: Terminal,
    *,
    label: str,
    result: str,
    output_path: Path,
    project_directory: Path,
    selector: str,
    task: str,
    arguments: dict[str, object],
    database_enabled: bool,
) -> None:
    write_output(output_path, result)
    terminal.g(f"{label}: {result}")
    if database_enabled:
        record_step(
            project_directory=project_directory,
            selector=selector,
            task=task,
            arguments=arguments,
            answer=result,
            output_path=output_path,
        )


def request_debug_confirmation(terminal: Terminal, recipient: str, amount: int) -> bool:
    """Require an exact human phrase before a debug-mode broadcast."""

    expected = f"SEND {recipient.lower()} {amount}"
    if not sys.stdin.isatty():
        raise RuntimeError("Debug confirmation requires an interactive terminal; disable project.json confirm for automation.")
    terminal.y(f"Debug confirmation required. Type exactly: {expected}")
    response = input("> ").strip()
    if response != expected:
        terminal.y("Transaction cancelled: confirmation text did not match.")
        return False
    return True


def main() -> int:
    arguments = parse_arguments()
    terminal = Terminal()
    try:
        project_config = load_project_config(PROJECT_ROOT)
        project_directory = get_project_directory(PROJECT_ROOT, project_config)
        selector = project_config.get("selector", "")
        db_setting = project_config.get("db", False)
        debug_confirmation = project_config.get("confirm", False)
        if not isinstance(selector, str) or not isinstance(db_setting, bool) or not isinstance(debug_confirmation, bool):
            raise ValueError("project.json has invalid db, selector, or confirm settings.")
        database_enabled = db_setting and not arguments.no_db
        plan_path = resolve_output_path(project_directory, arguments.out)

        before_path = project_directory / "obt_balance_before.txt"
        before = obt_get_balance()
        complete_step(
            terminal,
            label="OBT balance before",
            result=before,
            output_path=before_path,
            project_directory=project_directory,
            selector=selector,
            task="obt_get_balance_before",
            arguments={},
            database_enabled=database_enabled,
        )

        build_arguments: dict[str, object] = {"to": arguments.addr, "amount": arguments.val}
        if arguments.utxo_txid is not None:
            build_arguments["utxo_txid"] = arguments.utxo_txid
        plan_text = obt_build_transaction(**build_arguments)
        complete_step(
            terminal,
            label="Signed OBT transaction JSON",
            result=plan_text,
            output_path=plan_path,
            project_directory=project_directory,
            selector=selector,
            task="obt_build_transaction",
            arguments=build_arguments,
            database_enabled=database_enabled,
        )
        plan = json.loads(plan_text)
        payload = plan.get("payload")
        if not isinstance(payload, dict):
            raise RuntimeError("OBT build result does not contain a transaction payload.")

        if not arguments.confirm:
            terminal.y("Dry run completed: transaction was built but not broadcast. Add --confirm to send it.")
            return 0
        if debug_confirmation and not request_debug_confirmation(terminal, arguments.addr, arguments.val):
            return 0

        broadcast_path = project_directory / "obt_broadcast.json"
        broadcast_arguments = {"transaction": payload, "confirm": True}
        broadcast = obt_send_transaction(broadcast_arguments["transaction"], confirm=True)
        complete_step(
            terminal,
            label="OBT server response",
            result=broadcast,
            output_path=broadcast_path,
            project_directory=project_directory,
            selector=selector,
            task="obt_send_transaction",
            arguments=broadcast_arguments,
            database_enabled=database_enabled,
        )

        after_path = project_directory / "obt_balance_after.txt"
        after = obt_get_balance()
        complete_step(
            terminal,
            label="OBT balance after",
            result=after,
            output_path=after_path,
            project_directory=project_directory,
            selector=selector,
            task="obt_get_balance_after",
            arguments={},
            database_enabled=database_enabled,
        )
        return 0
    except (OSError, RuntimeError, ValueError) as error:
        terminal.r(f"ERROR: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
