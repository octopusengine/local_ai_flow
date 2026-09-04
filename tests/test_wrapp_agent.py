"""Tests for the reusable local coding-agent wrapper without a running Ollama."""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch
from urllib.request import urlopen

from lib.wrapp_agent import (
    AgentEngine,
    AgentRun,
    AgentToolCall,
    ProjectToolScope,
    ToolPolicy,
    build_file_tools,
    database_tool_call,
    load_tool_schema,
    record_agent_run,
    review_agent_run,
    schema_tool_names,
    session_info_requested,
    tools_for_schema,
)


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "assistant" / "tools" / "tool_schema.json"


class FakeResponse:
    """Minimal non-streaming response accepted by ``AgentEngine``."""

    status_code = 200

    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, object]:
        return self.payload


class WrappAgentTests(unittest.TestCase):
    def test_tool_schema_profiles_select_light_or_extended_tools(self) -> None:
        light = load_tool_schema(SCHEMA_PATH, "light")
        extended = load_tool_schema(SCHEMA_PATH, "extended")
        hw_extended = load_tool_schema(SCHEMA_PATH, "hw_extended")
        hardware = load_tool_schema(SCHEMA_PATH, "hardware")
        nostr = load_tool_schema(SCHEMA_PATH, "nostr")

        self.assertEqual(
            schema_tool_names(light),
            {"session_info", "list_files", "read_file", "write_file", "python_runtime_info", "run_python", "run_command", "system_wait"},
        )
        self.assertTrue(schema_tool_names(light) < schema_tool_names(extended))
        self.assertIn("browser_test", schema_tool_names(extended))
        self.assertEqual(
            schema_tool_names(hw_extended),
            schema_tool_names(extended) | {"hardware_list_devices", "hardware_run_action"},
        )
        self.assertEqual(
            schema_tool_names(hardware),
            {"session_info", "list_files", "read_file", "find_text", "file_info", "python_runtime_info", "system_datetime", "system_wait", "network_ping", "hardware_list_devices", "hardware_run_action"},
        )
        self.assertNotIn("run_command", schema_tool_names(hardware))
        self.assertNotIn("run_python", schema_tool_names(hardware))
        self.assertNotIn("network_ping", schema_tool_names(light))
        self.assertNotIn("network_ping", schema_tool_names(extended))
        self.assertEqual(
            schema_tool_names(nostr),
            schema_tool_names(light) | {"system_datetime", "hardware_list_devices", "hardware_run_action", "nostr_status", "nostr_doctor", "nostr_list_relays", "nostr_list_friends", "nostr_list_messages", "nostr_get_message", "nostr_sync", "nostr_mark_handled", "nostr_reply", "nostr_send_friend"},
        )
        self.assertIn("nostr_sync", schema_tool_names(nostr))

    def test_hardware_tools_use_the_shared_allowlist_without_a_per_run_catalog_gate(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            scope = ProjectToolScope(Path(temporary_directory))
            expected_result = {"ok": True, "device_id": "test-led", "action_id": "esp-hi"}
            with patch(
                "lib.wrapp_agent.hw_mcp.run_hardware_action",
                new=AsyncMock(return_value=expected_result),
            ) as run_action:
                tools = build_file_tools(scope, ToolPolicy.CODE)
                result = json.loads(tools["hardware_run_action"].function("test-led", "esp-hi"))

            self.assertEqual(result, expected_result)
            run_action.assert_awaited_once_with("test-led", "esp-hi", 15.0)
            observe_tools = build_file_tools(scope, ToolPolicy.OBSERVE)
            self.assertIn("does not allow hardware", observe_tools["hardware_run_action"].function("test-led", "esp-hi"))

    def test_hardware_diagnostic_tools_return_safe_structured_results(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            scope = ProjectToolScope(Path(temporary_directory))
            with patch("lib.wrapp_agent.wrapp_services.system_datetime", return_value="2026-09-02T20:45:00+02:00"), patch(
                "lib.wrapp_agent.wrapp_services.network_ping",
                return_value={"host": "8.8.8.8", "reachable": True, "exit_code": 0, "duration_ms": 12, "summary": "reply", "output": "raw ping output"},
            ):
                tools = build_file_tools(scope, ToolPolicy.CODE)
                current_time = json.loads(tools["system_datetime"].function())
                ping = json.loads(tools["network_ping"].function())

        self.assertEqual(current_time, {"datetime": "2026-09-02T20:45:00+02:00"})
        self.assertEqual(ping["summary"], "reply")
        self.assertNotIn("output", ping)

    def test_system_wait_is_bounded_and_reports_the_completed_wait(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            tools = build_file_tools(ProjectToolScope(Path(temporary_directory)), ToolPolicy.CODE)
            with patch("lib.wrapp_agent.time.sleep") as sleep:
                result = json.loads(tools["system_wait"].function(20))

        self.assertEqual(result, {"ok": True, "waited_seconds": 20})
        sleep.assert_called_once_with(20)
        with self.assertRaisesRegex(ValueError, "1 through 60"):
            tools["system_wait"].function(61)

    def test_scope_rejects_absolute_and_escaping_paths(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            scope = ProjectToolScope(root)

            with self.assertRaisesRegex(ValueError, "Absolute"):
                scope.resolve(str(root))
            with self.assertRaisesRegex(ValueError, "inside"):
                scope.resolve("../outside.txt")

    def test_file_tools_do_not_expose_dotenv_content(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            (root / ".env").write_text("KEY1=secret-value\n", encoding="utf-8")
            tools = build_file_tools(ProjectToolScope(root), ToolPolicy.CODE)

            with self.assertRaisesRegex(ValueError, "secret files"):
                tools["read_file"].function(".env")
            self.assertEqual(tools["find_text"].function("KEY1"), "(no matches)")

    def test_file_tools_stay_in_scope_and_observe_never_writes(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            scope = ProjectToolScope(Path(temporary_directory))
            tools = build_file_tools(scope, ToolPolicy.CODE)

            result = tools["write_file"].function("src/app.py", "print('ok')\n")

            self.assertIn("Saved src/app.py", result)
            self.assertEqual(tools["read_file"].function("src/app.py"), "print('ok')\n")
            with self.assertRaisesRegex(ValueError, "inside"):
                tools["write_file"].function("../outside.txt", "no")
            observe_tools = build_file_tools(scope, ToolPolicy.OBSERVE)
            self.assertIn("does not allow", observe_tools["write_file"].function("no.py", "no"))
            self.assertFalse((scope.root / "no.py").exists())

    def test_session_info_returns_the_live_provider_report(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            scope = ProjectToolScope(Path(temporary_directory))
            tools = build_file_tools(scope, session_info_provider=lambda: "Model: test-model\nElapsed: 2.5 s")

            result = tools["session_info"].function()

            self.assertEqual(result, "Model: test-model\nElapsed: 2.5 s")

    def test_session_info_request_detector_recognizes_model_and_duration_metadata(self) -> None:
        self.assertTrue(session_info_requested("Do box.md přidej model a jak dlouho to trvalo."))
        self.assertTrue(session_info_requested("Include session runtime metadata."))
        self.assertFalse(session_info_requested("Vytvoř box.py s dvanácti kruhy."))

    def test_read_file_supports_inclusive_line_ranges(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            scope = ProjectToolScope(Path(temporary_directory))
            scope.root.joinpath("notes.txt").write_text("one\ntwo\nthree\n", encoding="utf-8")
            tools = build_file_tools(scope)

            result = tools["read_file"].function("notes.txt", start_line=2, end_line=3)

            self.assertEqual(result, "two\nthree\n")

    def test_find_text_respects_path_glob_and_result_locations(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            scope = ProjectToolScope(Path(temporary_directory))
            source_directory = scope.root / "src"
            source_directory.mkdir()
            source_directory.joinpath("app.py").write_text("# target value\nTARGET = 3\n", encoding="utf-8")
            source_directory.joinpath("notes.txt").write_text("target in ignored extension\n", encoding="utf-8")
            tools = build_file_tools(scope)

            result = tools["find_text"].function("target", path="src", glob="*.py")

            self.assertIn("src/app.py:1: # target value", result)
            self.assertIn("src/app.py:2: TARGET = 3", result)
            self.assertNotIn("notes.txt", result)

    def test_file_info_reports_scoped_file_metadata(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            scope = ProjectToolScope(Path(temporary_directory))
            scope.root.joinpath("app.py").write_text("print('ok')\n", encoding="utf-8")
            tools = build_file_tools(scope)

            result = tools["file_info"].function("app.py")

            self.assertIn("Path: app.py", result)
            self.assertIn("Type: file", result)
            self.assertIn("Extension: .py", result)

    def test_apply_patch_updates_matching_context_and_rejects_stale_context(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            scope = ProjectToolScope(Path(temporary_directory))
            source_path = scope.root / "app.py"
            source_path.write_text("first\nold\nlast\n", encoding="utf-8")
            tools = build_file_tools(scope, ToolPolicy.CODE)
            patch_text = "@@ -1,3 +1,3 @@\n first\n-old\n+new\n last\n"

            result = tools["apply_patch"].function("app.py", patch_text)

            self.assertIn("Patched app.py", result)
            self.assertEqual(source_path.read_text(encoding="utf-8"), "first\nnew\nlast\n")
            with self.assertRaisesRegex(ValueError, "context"):
                tools["apply_patch"].function("app.py", "@@ -1,1 +1,1 @@\n-missing\n+replacement\n")
            self.assertEqual(source_path.read_text(encoding="utf-8"), "first\nnew\nlast\n")

    def test_apply_patch_accepts_common_begin_patch_context_format(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            scope = ProjectToolScope(Path(temporary_directory))
            source_path = scope.root / "app.py"
            source_path.write_text("first\nold\nlast\n", encoding="utf-8")
            tools = build_file_tools(scope, ToolPolicy.CODE)
            patch_text = "*** Begin Patch\n*** Update File: app.py\n@@\n-old\n+new\n*** End Patch"

            result = tools["apply_patch"].function("app.py", patch_text)

            self.assertIn("Patched app.py", result)
            self.assertEqual(source_path.read_text(encoding="utf-8"), "first\nnew\nlast\n")
            with self.assertRaisesRegex(ValueError, "does not match"):
                tools["apply_patch"].function(
                    "app.py", "*** Begin Patch\n*** Update File: other.py\n@@\n-old\n+again\n*** End Patch"
                )

    def test_command_can_run_without_confirmation_and_reports_exit_code(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            scope = ProjectToolScope(Path(temporary_directory))
            tools = build_file_tools(scope, ToolPolicy.CODE, run_confirm=lambda _message: True)

            result = tools["run_command"].function('python -c "print(42)"')

            self.assertIn("42", result)
            self.assertIn("exit code 0", result)

    def test_command_passes_optional_stdin_to_an_interactive_program(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            scope = ProjectToolScope(Path(temporary_directory))
            tools = build_file_tools(scope, ToolPolicy.CODE, run_confirm=lambda _message: True)

            result = tools["run_command"].function(
                'python -c "import sys; print(sys.stdin.read().strip())"',
                stdin="1\n-3\n2\n",
            )

            self.assertIn("1\n-3\n2", result)
            self.assertIn("exit code 0", result)

    def test_toolchain_info_reports_detected_compilers_without_executing_them(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            scope = ProjectToolScope(Path(temporary_directory))
            tools = build_file_tools(scope)
            paths = {"gcc": "/usr/bin/gcc", "g++": "/usr/bin/g++", "rustc": "/usr/bin/rustc"}

            with patch("lib.wrapp_agent.shutil.which", side_effect=paths.get):
                result = tools["toolchain_info"].function()

            self.assertIn("C: gcc: /usr/bin/gcc", result)
            self.assertIn("C++: g++: /usr/bin/g++", result)
            self.assertIn("Rust: rustc: /usr/bin/rustc", result)
            self.assertIn("cl.exe", result)

    def test_run_python_prefers_project_code_path_and_accepts_stdin(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            scope = ProjectToolScope(Path(temporary_directory))
            source_path = scope.root / "interactive.py"
            source_path.write_text("print(input() + '!')\n", encoding="utf-8")
            tools = build_file_tools(scope, ToolPolicy.CODE, run_confirm=lambda _message: True)

            result = tools["run_python"].function("interactive.py", stdin="pygame\n")

            self.assertIn("pygame!", result)
            self.assertIn("PYTHON RUN REPORT", result)
            self.assertIn("Outcome: completed", result)
            self.assertIn("Exit code: 0", result)

    def test_run_python_reports_a_bounded_timeout(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            scope = ProjectToolScope(Path(temporary_directory))
            scope.root.joinpath("loop.py").write_text("while True: pass\n", encoding="utf-8")
            tools = build_file_tools(scope, ToolPolicy.CODE, run_confirm=lambda _message: True)
            timeout = subprocess.TimeoutExpired(["python", "loop.py"], 2, output="still running", stderr="")

            with patch("lib.wrapp_agent.subprocess.run", side_effect=timeout):
                result = tools["run_python"].function("loop.py", timeout_seconds=2)

            self.assertIn("PYTHON RUN REPORT", result)
            self.assertIn("Timeout: 2 s", result)
            self.assertIn("Outcome: timed out", result)
            self.assertIn("still running", result)

    def test_reviewer_receives_only_read_only_tools_and_test_evidence(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            scope = ProjectToolScope(Path(temporary_directory))
            run = AgentRun("test-model", scope.root, ToolPolicy.CODE, "Create app.py")
            run.artifacts.add("app.py")
            run.tool_calls.append(AgentToolCall(1, "run_python", {"path": "app.py"}, "completed", "Exit code: 0"))
            captured: list[dict[str, object]] = []

            class FakeEngine:
                def __init__(self, **kwargs: object) -> None:
                    captured.append(kwargs)

                def run(self, _messages: list[dict[str, object]], _run: AgentRun) -> str:
                    return "PASS: test output was successful."

            with patch("lib.wrapp_agent.AgentEngine", FakeEngine):
                result = review_agent_run(
                    run,
                    api=SimpleNamespace(default_options={}),
                    model="test-model",
                    scope=scope,
                    timeout_seconds=5,
                    options={},
                )

            self.assertTrue(result.startswith("PASS"))
            self.assertEqual(set(captured[0]["tools"]), {"list_files", "read_file", "find_text", "file_info", "python_runtime_info", "web_runtime_info", "browser_test"})
            self.assertNotIn("write_file", captured[0]["tools"])
            self.assertNotIn("run_command", captured[0]["tools"])

    def test_python_runtime_info_never_creates_a_virtual_environment(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            scope = ProjectToolScope(Path(temporary_directory))
            tools = build_file_tools(scope)

            result = tools["python_runtime_info"].function()

            self.assertIn("Interpreter:", result)
            self.assertIn("pygame:", result)
            self.assertFalse((scope.root / ".venv").exists())
            self.assertFalse((scope.root / "venv").exists())

    def test_web_runtime_info_reports_node_and_browser_paths(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            scope = ProjectToolScope(Path(temporary_directory))
            tools = build_file_tools(scope)
            paths = {"node": "/usr/bin/node", "chromium": "/usr/bin/chromium"}

            with patch("lib.wrapp_agent.shutil.which", side_effect=paths.get):
                result = tools["web_runtime_info"].function()

            self.assertIn("Node.js: /usr/bin/node", result)
            self.assertIn("chromium: /usr/bin/chromium", result)

    def test_serve_project_serves_only_the_scoped_directory(self) -> None:
        from lib.wrapp_agent import shutdown_web_servers

        with TemporaryDirectory() as temporary_directory:
            scope = ProjectToolScope(Path(temporary_directory))
            website = scope.root / "site"
            website.mkdir()
            website.joinpath("index.html").write_text("<h1>Local test</h1>", encoding="utf-8")
            tools = build_file_tools(scope, ToolPolicy.CODE, run_confirm=lambda _message: True)
            try:
                result = tools["serve_project"].function("site")
                url = result.split(" at ", 1)[1].split(" ", 1)[0]
                with urlopen(url, timeout=5) as response:
                    content = response.read().decode("utf-8")
            finally:
                shutdown_web_servers()

            self.assertIn("Local test", content)

    def test_browser_test_uses_registered_localhost_server_only(self) -> None:
        from lib.wrapp_agent import shutdown_web_servers

        with TemporaryDirectory() as temporary_directory:
            scope = ProjectToolScope(Path(temporary_directory))
            scope.root.joinpath("index.html").write_text("<p>Ready</p>", encoding="utf-8")
            tools = build_file_tools(scope, ToolPolicy.CODE, run_confirm=lambda _message: True)
            try:
                server_result = tools["serve_project"].function()
                url = server_result.split(" at ", 1)[1].split(" ", 1)[0]
                with (
                    patch("lib.wrapp_agent._web_browser_paths", return_value={"chromium": "/usr/bin/chromium"}),
                    patch("lib.wrapp_agent.subprocess.run", return_value=SimpleNamespace(returncode=0, stdout="<p>Ready</p>", stderr="")),
                ):
                    result = tools["browser_test"].function(url, expected_text="Ready")
                self.assertIn("contains expected text", result)
                with self.assertRaisesRegex(ValueError, "localhost"):
                    tools["browser_test"].function("https://example.com")
            finally:
                shutdown_web_servers()

    def test_engine_returns_tool_results_to_model_across_multiple_steps(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            scope = ProjectToolScope(Path(temporary_directory))
            artifacts: set[str] = set()
            available_tools = build_file_tools(scope, ToolPolicy.CODE, on_artifact=artifacts.add)
            tool_schema = load_tool_schema(SCHEMA_PATH)
            tools = tools_for_schema(tool_schema, available_tools)
            responses = iter(
                [
                    {
                        "message": {
                            "role": "assistant",
                            "tool_calls": [
                                {"function": {"name": "write_file", "arguments": {"path": "app.py", "content": "print('ok')\n"}}},
                                {"function": {"name": "read_file", "arguments": {"path": "app.py"}}},
                            ],
                        }
                    },
                    {"message": {"role": "assistant", "content": "The program was created and verified."}},
                ]
            )

            engine = AgentEngine(
                api=SimpleNamespace(base_url="http://ollama.test", default_options={}),
                model="test-model",
                tool_schema=tool_schema,
                tools=tools,
                max_steps=3,
                timeout_seconds=5,
                post=lambda *_args, **_kwargs: FakeResponse(next(responses)),
            )
            run = AgentRun("test-model", scope.root, ToolPolicy.CODE, "Create app.py")
            messages: list[dict[str, object]] = [{"role": "user", "content": run.prompt}]

            answer = engine.run(messages, run)

            self.assertEqual(answer, "The program was created and verified.")
            self.assertEqual(run.status, "completed")
            self.assertEqual([call.name for call in run.tool_calls], ["write_file", "read_file"])
            self.assertEqual(artifacts, {"app.py"})
            self.assertEqual(messages[-2]["role"], "tool")

    def test_engine_retries_one_future_tense_plan_before_finishing(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            scope = ProjectToolScope(Path(temporary_directory))
            available_tools = build_file_tools(scope, ToolPolicy.CODE)
            tool_schema = load_tool_schema(SCHEMA_PATH, "light")
            tools = tools_for_schema(tool_schema, available_tools)
            responses = iter(
                [
                    {"message": {"role": "assistant", "content": "Napíšu program a pak ho ověřím."}},
                    {"message": {"role": "assistant", "tool_calls": [{"function": {"name": "write_file", "arguments": {"path": "app.py", "content": "print('ok')\n"}}}]}},
                    {"message": {"role": "assistant", "content": "Program je hotový."}},
                ]
            )
            engine = AgentEngine(
                api=SimpleNamespace(base_url="http://ollama.test", default_options={}),
                model="test-model",
                tool_schema=tool_schema,
                tools=tools,
                max_steps=3,
                timeout_seconds=5,
                auto_continue=True,
                post=lambda *_args, **_kwargs: FakeResponse(next(responses)),
            )
            run = AgentRun("test-model", scope.root, ToolPolicy.CODE, "Create app.py")
            messages: list[dict[str, object]] = [{"role": "user", "content": run.prompt}]

            answer = engine.run(messages, run)

            self.assertEqual(answer, "Program je hotový.")
            self.assertTrue(scope.root.joinpath("app.py").is_file())
            self.assertIn("Continue the task now.", str(messages))

    def test_engine_retries_raw_patch_text_as_an_unexecuted_tool_payload(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            scope = ProjectToolScope(Path(temporary_directory))
            scope.root.joinpath("app.py").write_text("old\n", encoding="utf-8")
            available_tools = build_file_tools(scope, ToolPolicy.CODE)
            tool_schema = load_tool_schema(SCHEMA_PATH, "extended")
            tools = tools_for_schema(tool_schema, available_tools)
            patch_text = "@@ -1 +1 @@\n-old\n+new\n"
            responses = iter(
                [
                    {"message": {"role": "assistant", "content": '{"path":"app.py","patch":"*** Begin Patch"}'}},
                    {"message": {"role": "assistant", "tool_calls": [{"function": {"name": "apply_patch", "arguments": {"path": "app.py", "patch": patch_text}}}]}},
                    {"message": {"role": "assistant", "content": "Patch applied."}},
                ]
            )
            engine = AgentEngine(
                api=SimpleNamespace(base_url="http://ollama.test", default_options={}),
                model="test-model",
                tool_schema=tool_schema,
                tools=tools,
                max_steps=3,
                timeout_seconds=5,
                auto_continue=True,
                post=lambda *_args, **_kwargs: FakeResponse(next(responses)),
            )
            run = AgentRun("test-model", scope.root, ToolPolicy.CODE, "Fix app.py")

            answer = engine.run([{"role": "user", "content": run.prompt}], run)

            self.assertEqual(answer, "Patch applied.")
            self.assertEqual(scope.root.joinpath("app.py").read_text(encoding="utf-8"), "new\n")

    def test_database_tool_call_excludes_written_file_content(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            run = AgentRun("test", Path(temporary_directory), ToolPolicy.CODE)
            # The explicit call record mirrors a write call collected by the engine.
            from lib.wrapp_agent import AgentToolCall

            record = database_tool_call(
                AgentToolCall(1, "write_file", {"path": "secret.txt", "content": "not in db"}, "completed", "Saved secret.txt")
            )

            self.assertEqual(record["arguments"], {"path": "secret.txt", "content_characters": 9})

    def test_database_tool_call_excludes_stdin_text(self) -> None:
        from lib.wrapp_agent import AgentToolCall

        record = database_tool_call(
            AgentToolCall(1, "run_command", {"command": "python app.py", "stdin": "1\n-3\n2\n"}, "completed", "ok")
        )

        self.assertEqual(record["arguments"], {"command": "python app.py", "stdin_characters": 7})

    def test_completed_run_is_stored_using_the_shared_task_database_schema(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            temporary_root = Path(temporary_directory)
            project_directory = temporary_root / "project"
            project_directory.mkdir()
            data_directory = temporary_root / "data"
            data_directory.mkdir()
            shutil.copy(ROOT / "data" / "tasks.json", data_directory / "tasks.json")
            run = AgentRun("test-model", project_directory, ToolPolicy.CODE, "Create a program")
            run.status = "completed"
            run.final_answer = "Created and tested app.py."
            run.duration_seconds = 1.25

            uid = record_agent_run(
                run,
                database_path=data_directory / "tasks.db",
                schema_path=data_directory / "tasks.json",
                project_root=temporary_root,
                selector="agent",
                instruction="Test instruction.",
                run_confirm=False,
            )

            from lib.wrapp_db import get_task_row

            row = get_task_row(data_directory / "tasks.db", uid)
            self.assertIsNotNone(row)
            assert row is not None
            self.assertEqual(row["project"], "project")
            self.assertEqual(row["selector"], "agent")
            self.assertEqual(row["task"], "cli_agent")
            self.assertEqual(row["answer"], run.final_answer)


if __name__ == "__main__":
    unittest.main()
