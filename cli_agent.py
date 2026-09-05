"""Command-line adapter for the reusable local Ollama coding agent."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from lib.wrapp_agent import (
    DEFAULT_MAX_STEPS,
    SYSTEM_PROMPT,
    AgentCallbacks,
    AgentEngine,
    AgentRun,
    ProjectToolScope,
    ToolPolicy,
    build_file_tools,
    format_session_info,
    load_tool_schema,
    record_agent_run,
    review_agent_run,
    resolve_agent_options,
    session_info_context,
    session_info_requested,
    tools_for_schema,
)
from lib.wrapp_log import (
    console_log,
    get_project_directory,
    load_json_object,
    load_project_config,
    read_debug_enabled,
)
from lib.wrapp_ollama import ollama_api
from lib.wrapp_terminal import Terminal


PROJECT_ROOT = Path(__file__).resolve().parent
OLLAMA_CONFIG_PATH = PROJECT_ROOT / "lib" / "ollama.json"
AGENT_CONFIG_PATH = PROJECT_ROOT / "cli_agent.json"
TOOL_SCHEMA_PATH = PROJECT_ROOT / "assistant" / "tools" / "tool_schema.json"
DEFAULT_MODEL = "gpt-oss:latest"
TERMINAL = Terminal()


def load_agent_config(path: Path = AGENT_CONFIG_PATH) -> dict[str, object]:
    """Load and validate the small configuration dedicated to ``cli_agent``."""
    config = load_json_object(path)
    for name in ("log", "db", "run_confirm", "auto_continue", "review", "tool_schema_light"):
        if not isinstance(config.get(name), bool):
            raise ValueError(f"'{name}' must be true or false in {path.name}.")
    model = config.get("model")
    if not isinstance(model, str) or not model.strip():
        raise ValueError(f"'model' must be non-empty text in {path.name}.")
    config["model"] = model.strip()
    config["options"] = resolve_agent_options({}, config.get("options"))
    selector = config.get("selector", "agent")
    if not isinstance(selector, str) or not selector.strip():
        raise ValueError(f"'selector' must be non-empty text in {path.name}.")
    config["selector"] = selector
    return config


def tool_schema_profile(agent_config: dict[str, object]) -> str:
    """Choose an explicit schema profile, retaining the legacy boolean fallback."""
    explicit_profile = agent_config.get("tool_schema_profile")
    if explicit_profile is None:
        return "light" if agent_config["tool_schema_light"] else "extended"
    if not isinstance(explicit_profile, str) or not explicit_profile.strip():
        raise ValueError("'tool_schema_profile' must be non-empty text when present.")
    return explicit_profile.strip()


def positive_integer(value: str) -> int:
    """Parse a positive integer command-line option."""
    try:
        parsed = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("must be a whole number") from error
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return parsed


def positive_float(value: str) -> float:
    """Parse a positive timeout value in seconds."""
    try:
        parsed = float(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("must be a number") from error
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return parsed


def parse_arguments() -> argparse.Namespace:
    """Parse options for the thin CLI adapter."""
    parser = argparse.ArgumentParser(
        description="Run an interactive Ollama coding agent in the project from project.json."
    )
    parser.add_argument("--model", help="tool-capable Ollama model (overrides cli_agent.json model)")
    parser.add_argument("--max-steps", type=positive_integer, default=DEFAULT_MAX_STEPS, help=f"maximum model/tool turns per user request (default: {DEFAULT_MAX_STEPS})")
    parser.add_argument("--prompt", metavar="TEXT", help="run one request and exit instead of opening the interactive prompt")
    parser.add_argument("--timeout", type=positive_float, metavar="SECONDS", help="Ollama response timeout; defaults to ollama_timeout_seconds in project.json")
    parser.add_argument("--verbose", action="store_true", help="stream and show Ollama thinking, text, and tool-call progress")
    parser.add_argument("--policy", choices=[policy.value for policy in ToolPolicy], default=ToolPolicy.CODE.value, help="tool approval policy (default: code)")
    parser.add_argument("--show-config", action="store_true", help="print the resolved active project and tool schema profile, then exit")
    parser.add_argument("--version", action="version", version="cli_agent.py 0.2")
    return parser.parse_args()


def create_callbacks(verbose: bool) -> AgentCallbacks:
    """Render engine events in the existing CLI style."""
    in_thinking = False
    in_content = False

    def on_status(text: str) -> None:
        print(f"{TERMINAL.color('bright_black', '[agent]')} {text}", flush=True)

    def on_thinking(text: str) -> None:
        nonlocal in_thinking
        if not verbose:
            return
        if not in_thinking:
            TERMINAL.v("\n[thinking]")
            in_thinking = True
        print(TERMINAL.color("v", text), end="", flush=True)

    def on_content(text: str) -> None:
        nonlocal in_content
        if not verbose:
            return
        if not in_content:
            TERMINAL.w("\n\n[answer]")
            in_content = True
        print(TERMINAL.color("w", text), end="", flush=True)

    def on_tool_call(name: str, arguments: dict[str, object]) -> None:
        print(f"{TERMINAL.color('y', '[tool]')} {name}({arguments})", flush=True)

    def on_tool_result(_name: str, result: str) -> None:
        print(f"{TERMINAL.color('g', '[result]')} {result}", flush=True)

    return AgentCallbacks(on_status, on_thinking, on_content, on_tool_call, on_tool_result)


def run_request(
    messages: list[dict[str, object]],
    prompt: str,
    *,
    scope: ProjectToolScope,
    arguments: argparse.Namespace,
    api: ollama_api,
    tool_schema: list[dict[str, object]],
    timeout_seconds: float,
    run_confirm: bool,
    agent_options: dict[str, int | float],
    auto_continue: bool,
    review_enabled: bool,
    schema_profile: str,
) -> AgentRun:
    """Build a run-specific engine, execute one prompt, and return its report."""
    policy = ToolPolicy(arguments.policy)
    run = AgentRun(arguments.model, scope.root, policy, prompt)
    session_info_provider = lambda: format_session_info(
        run,
        schema_profile=schema_profile,
        options=agent_options,
        max_steps=arguments.max_steps,
        run_confirm=run_confirm,
        auto_continue=auto_continue,
        review_enabled=review_enabled,
    )
    available_tools = build_file_tools(
        scope,
        policy,
        # ``run_confirm: false`` is useful during controlled local test runs.
        # It changes only shell-command confirmation; Draft writes still ask.
        run_confirm=None if run_confirm else lambda _message: True,
        on_artifact=run.artifacts.add,
        session_info_provider=session_info_provider,
    )
    tools = tools_for_schema(tool_schema, available_tools)
    engine = AgentEngine(
        api=api,
        model=arguments.model,
        tool_schema=tool_schema,
        tools=tools,
        max_steps=arguments.max_steps,
        timeout_seconds=timeout_seconds,
        options=agent_options,
        auto_continue=auto_continue,
        verbose=arguments.verbose,
        callbacks=create_callbacks(arguments.verbose),
    )
    if session_info_requested(prompt):
        messages.append({"role": "system", "content": session_info_context(session_info_provider())})
    messages.append({"role": "user", "content": prompt})
    engine.run(messages, run)
    if review_enabled:
        try:
            run.review = review_agent_run(
                run,
                api=api,
                model=arguments.model,
                scope=scope,
                timeout_seconds=timeout_seconds,
                options=agent_options,
                think=engine.think,
            )
        except RuntimeError as error:
            run.review_error = str(error)
    return run


def print_run(run: AgentRun) -> None:
    """Print the verified completion text and compact activity report."""
    if run.final_answer is not None:
        print(f"\n{TERMINAL.color('c', 'Agent:')} {TERMINAL.color('w', run.final_answer)}")
    if run.review is not None:
        print(f"\n{TERMINAL.color('c', 'Review:')} {TERMINAL.color('w', run.review)}")
    print(f"\n{TERMINAL.color('c', run.summary())}")


def run_interactive_agent(
    *,
    project_directory: Path,
    arguments: argparse.Namespace,
    project_debug: bool | None,
    agent_config: dict[str, object],
) -> int:
    """Prepare shared resources and process one or more stdin requests."""
    scope = ProjectToolScope(project_directory)
    schema_profile = tool_schema_profile(agent_config)
    tool_schema = load_tool_schema(TOOL_SCHEMA_PATH, schema_profile)
    api = ollama_api(config_path=OLLAMA_CONFIG_PATH, debug_enabled=project_debug, time_trace=True)
    agent_options = resolve_agent_options(api.default_options, agent_config["options"])
    timeout_seconds = arguments.timeout if arguments.timeout is not None else api.read_timeout_seconds
    print(f"{TERMINAL.color('c', '[agent]')} Local agent ready in: {scope.root}", flush=True)
    print(f"{TERMINAL.color('y', '[model]')} {arguments.model}; policy: {arguments.policy}; schema: {schema_profile}. Type 'exit' or 'quit' to end.", flush=True)

    messages: list[dict[str, object]] = [{"role": "system", "content": SYSTEM_PROMPT}]
    if arguments.prompt is not None:
        run = run_request(
            messages,
            arguments.prompt,
            scope=scope,
            arguments=arguments,
            api=api,
            tool_schema=tool_schema,
            timeout_seconds=timeout_seconds,
            run_confirm=bool(agent_config["run_confirm"]),
            agent_options=agent_options,
            auto_continue=bool(agent_config["auto_continue"]),
            review_enabled=bool(agent_config["review"]),
            schema_profile=schema_profile,
        )
        if agent_config["db"]:
            uid = record_agent_run(
                run,
                database_path=PROJECT_ROOT / "data" / "tasks.db",
                schema_path=PROJECT_ROOT / "data" / "tasks.json",
                project_root=PROJECT_ROOT,
                selector=str(agent_config["selector"]),
                instruction=SYSTEM_PROMPT,
                run_confirm=bool(agent_config["run_confirm"]),
            )
            print(f"Agent run recorded in data/tasks.db: {uid}")
        print_run(run)
        return 0

    while True:
        try:
            user_input = input(f"\n{TERMINAL.color('c', 'You: ')}")
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if user_input.strip().casefold() in {"exit", "quit"}:
            return 0
        if not user_input.strip():
            continue
        try:
            run = run_request(
                messages,
                user_input,
                scope=scope,
                arguments=arguments,
                api=api,
                tool_schema=tool_schema,
                timeout_seconds=timeout_seconds,
                run_confirm=bool(agent_config["run_confirm"]),
                agent_options=agent_options,
                auto_continue=bool(agent_config["auto_continue"]),
                review_enabled=bool(agent_config["review"]),
                schema_profile=schema_profile,
            )
            if agent_config["db"]:
                uid = record_agent_run(
                    run,
                    database_path=PROJECT_ROOT / "data" / "tasks.db",
                    schema_path=PROJECT_ROOT / "data" / "tasks.json",
                    project_root=PROJECT_ROOT,
                    selector=str(agent_config["selector"]),
                    instruction=SYSTEM_PROMPT,
                    run_confirm=bool(agent_config["run_confirm"]),
                )
                print(f"Agent run recorded in data/tasks.db: {uid}")
        except RuntimeError as error:
            Terminal(file=sys.stderr).r(f"ERROR: {error}")
            return 1
        print_run(run)


def main() -> int:
    """Resolve the active project, then delegate work to ``lib.wrapp_agent``."""
    arguments = parse_arguments()
    try:
        agent_config = load_agent_config()
        if arguments.model is None:
            arguments.model = str(agent_config["model"])
        project_config = load_project_config(PROJECT_ROOT)
        project_directory = get_project_directory(PROJECT_ROOT, project_config)
        project_debug = read_debug_enabled(PROJECT_ROOT / "project.json")
        if arguments.show_config:
            print(f"Project directory: {project_directory}")
            print(f"Tool schema: {TOOL_SCHEMA_PATH} ({tool_schema_profile(agent_config)})")
            print(f"Tool policy: {arguments.policy}")
            print(f"Agent configuration: {json.dumps(agent_config, ensure_ascii=False)}")
            return 0
    except ValueError as error:
        Terminal(file=sys.stderr).r(f"ERROR: {error}")
        return 1

    with console_log(project_directory, "cli_agent.py", bool(agent_config["log"])):
        try:
            return run_interactive_agent(
                project_directory=project_directory,
                arguments=arguments,
                project_debug=project_debug,
                agent_config=agent_config,
            )
        except (OSError, ValueError, RuntimeError) as error:
            Terminal(file=sys.stderr).r(f"ERROR: {error}")
            return 1


if __name__ == "__main__":
    raise SystemExit(main())
