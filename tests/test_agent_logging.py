"""Incremental plain-text agent logs, independent of terminal verbosity."""
import json
import io
import sys
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import james
from lib.wrapp_agent import AgentEngine, AgentRun, AgentTool, ToolPolicy
from lib.wrapp_log import console_log, log_event


class AgentLoggingTests(unittest.TestCase):
    def test_stream_keeps_final_token_metrics_without_logging_fragments(self):
        engine = AgentEngine(api=SimpleNamespace(default_options={}), model="test",
                             tool_schema=[], tools={}, timeout_seconds=5)
        response = SimpleNamespace(iter_lines=lambda **_: iter([
            json.dumps({"message": {"content": "Hello"}}),
            json.dumps({"done": True, "prompt_eval_count": 120, "eval_count": 50,
                        "eval_duration": 2_000_000_000}),
        ]))
        result = engine._collect_streamed_response(response)
        self.assertEqual(result["message"]["content"], "Hello")
        self.assertEqual(engine._token_metrics(result), {
            "input_tokens": 120, "output_tokens": 50, "generation_tokens/sec": 25.0})
        for data in ({}, {"eval_count": 10, "eval_duration": 0},
                     {"eval_count": True, "eval_duration": -1}):
            self.assertEqual(engine._token_metrics(data)["generation_tokens/sec"], "unavailable")

    def test_model_settings_logged_again_only_when_changed(self):
        with TemporaryDirectory() as directory:
            engine = AgentEngine(api=SimpleNamespace(default_options={}), model="test",
                                 tool_schema=[], tools={}, timeout_seconds=5, log_enabled=True)
            engine._log_directory = Path(directory)
            engine._log_model(model="test", options={"temperature": 0.2})
            engine._log_model(model="test", options={"temperature": 0.2})
            engine._log_model(model="vision", options={"num_predict": 4096})
            engine._log_model(model="test", options={"temperature": 0.2})
            text = (Path(directory) / "log.txt").read_text(encoding="utf-8-sig")
            self.assertEqual(text.count("event: model |"), 3)

    def test_logging_preserves_original_colored_terminal_output(self):
        outputs = []
        for enabled in (False, True):
            with TemporaryDirectory() as directory:
                root = Path(directory)
                stdout, stderr = io.StringIO(), io.StringIO()
                with redirect_stdout(stdout), redirect_stderr(stderr), patch.dict("os.environ", {"FORCE_COLOR": "1", "NO_COLOR": "", "OLLAMA_FLOW_LOG": "0"}):
                    with console_log(root, "james.cowork.code", enabled):
                        callbacks = james.create_cowork_callbacks()
                        callbacks.on_status("Waiting for Ollama response")
                        callbacks.on_thinking("Thinking...")
                        callbacks.on_tool_call("read_file", {"path": "app.py"})
                        callbacks.on_tool_result("read_file", "file contents")
                        if enabled:
                            before = stdout.getvalue(), stderr.getvalue()
                            log_event(root, "agent", {"event": "model_request", "options": {"temperature": 0.2}})
                            self.assertEqual((stdout.getvalue(), stderr.getvalue()), before)
                        callbacks.on_content("Finished")
                        print("diagnostic", file=sys.stderr)
                        if enabled:
                            text = (root / "log.txt").read_text(encoding="utf-8-sig")
                            self.assertIn("Finished", text)
                            self.assertIn("diagnostic", text)
                            self.assertIn("temperature: 0.2", text)
                            self.assertNotIn("\x1b", text)
                outputs.append((stdout.getvalue(), stderr.getvalue()))
                if not enabled:
                    self.assertFalse((root / "log.txt").exists())
        self.assertEqual(outputs[0], outputs[1])
        self.assertIn("\x1b[", outputs[1][0])

    def test_tool_events_are_written_before_completion_and_append_without_colors(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            log_event(root, "previous", {"event": "old entry"})
            def action():
                self.assertIn("[tool_call] [role=assistant] action", (root / "log.txt").read_text(encoding="utf-8-sig"))
                return "\x1b[31mčervený\x1b[0m\nsecond line"
            schema = [{"type": "function", "function": {"name": "action", "parameters": {"type": "object", "properties": {}}}}]
            responses = iter([
                {"message": {"tool_calls": [{"function": {"name": "action", "arguments": {}}}]}},
                {"message": {"content": "Done"}},
            ])
            def post(*args, **kwargs):
                payload = next(responses)
                if payload["message"].get("content"):
                    self.assertIn("event: tool", (root / "log.txt").read_text(encoding="utf-8-sig"))
                return SimpleNamespace(status_code=200, json=lambda: payload, raise_for_status=lambda: None)
            engine = AgentEngine(api=SimpleNamespace(base_url="http://test", default_options={}),
                                 model="test", tool_schema=schema, tools={"action": AgentTool("action", action, "read")},
                                 options={"temperature": 0.2}, timeout_seconds=5, log_enabled=True, post=post)
            with redirect_stdout(io.StringIO()), patch.dict("os.environ", {"OLLAMA_FLOW_LOG": "0"}), console_log(root, "test", True):
                engine.callbacks = james.create_cowork_callbacks()
                engine.run([], AgentRun("test", root, ToolPolicy.CODE, "Test prompt"))
            text = (root / "log.txt").read_text(encoding="utf-8-sig")
            for expected in ("old entry", "event: start", "Test prompt", '"temperature": 0.2', "červený", "event: summary", "duration_seconds:"):
                self.assertIn(expected, text)
            self.assertEqual(text.count("event: model |"), 1)
            self.assertEqual(text.count("červený"), 1)
            self.assertNotIn("model_stream", text)
            self.assertNotIn("model_response", text)
            self.assertNotIn("\x1b", text)
            self.assertNotIn("\\u001b", text)

    def test_partial_stream_is_saved_when_model_fails_and_false_creates_no_file(self):
        for enabled in (True, False):
            with self.subTest(enabled=enabled), TemporaryDirectory() as directory:
                root = Path(directory)
                def lines(**kwargs):
                    yield json.dumps({"message": {"content": "partial answer"}})
                    if enabled:
                        self.assertIn("partial answer", (root / "log.txt").read_text(encoding="utf-8-sig"))
                    yield json.dumps({"error": "out of memory"})
                response = SimpleNamespace(status_code=200, iter_lines=lines, raise_for_status=lambda: None)
                engine = AgentEngine(api=SimpleNamespace(base_url="http://test", default_options={}),
                                     model="test", tool_schema=[], tools={}, timeout_seconds=5, verbose=True,
                                     log_enabled=enabled, post=lambda *a, **kw: response)
                with redirect_stdout(io.StringIO()), patch.dict("os.environ", {"OLLAMA_FLOW_LOG": "0"}), console_log(root, "test", enabled):
                    engine.callbacks = james.create_cowork_callbacks()
                    with self.assertRaisesRegex(RuntimeError, "out of memory"):
                        engine.run([], AgentRun("test", root, ToolPolicy.CODE))
                if enabled:
                    text = (root / "log.txt").read_text(encoding="utf-8-sig")
                    self.assertIn("status: failed", text)
                    self.assertIn("out of memory", text)
                    self.assertEqual(text.count("partial answer"), 1)
                else:
                    self.assertFalse((root / "log.txt").exists())

    def test_profile_log_default_override_and_validation(self):
        data = json.loads(james.COWORK_AGENTS_CONFIG_PATH.read_text(encoding="utf-8-sig"))
        self.assertTrue(all(profile.get("log") is True for profile in data["agents"].values()))
        with TemporaryDirectory() as directory:
            path = Path(directory) / "agents.json"
            for agent in data["agents"].values():
                for filename in agent["system_prompt_files"]:
                    (path.parent / filename).write_text(
                        (james.COWORK_AGENTS_CONFIG_PATH.parent / filename).read_text(encoding="utf-8"),
                        encoding="utf-8",
                    )
            for value in (None, False, "true"):
                profile = data["agents"]["code"]
                profile.pop("log", None)
                if value is not None:
                    profile["log"] = value
                path.write_text(json.dumps(data), encoding="utf-8")
                with patch.object(james, "COWORK_AGENTS_CONFIG_PATH", path):
                    if value == "true":
                        with self.assertRaisesRegex(ValueError, "log"):
                            james.load_cowork_agents_config()
                    else:
                        loaded = james.load_cowork_agents_config()["code"]
                        self.assertEqual(loaded.log_enabled, value is None)
                        session = james.cowork_session_from_profile(Path(directory), loaded)
                        self.assertEqual(session.log_enabled, value is None)
