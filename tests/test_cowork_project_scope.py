"""Cowork project routing with real file, log and SQLite writes; no live model."""
from contextlib import ExitStack, redirect_stdout
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import james


class CoworkProjectScopeTests(unittest.TestCase):
    def test_disabled_persistence_and_failed_run_logging(self):
        config = james.load_james_config()
        with TemporaryDirectory() as directory, ExitStack() as stack:
            root = Path(directory).resolve()
            session = james.CoworkSession(root, log_enabled=False, db_enabled=False)
            stack.enter_context(patch.dict("os.environ", {"OLLAMA_FLOW_LOG": "0"}))
            stack.enter_context(patch.object(james, "load_project_config", return_value={}))
            stack.enter_context(patch.object(james, "ollama_api", return_value=SimpleNamespace(read_timeout_seconds=5, default_options={})))
            record = stack.enter_context(patch.object(james, "record_agent_run"))
            stack.enter_context(patch.object(james, "clear_screen"))
            stack.enter_context(patch.object(james, "pause"))
            stack.enter_context(redirect_stdout(StringIO()))
            with (patch.object(james.AgentEngine, "_call_ollama", return_value={"message": {"content": "Done"}}),
                  patch("builtins.input", return_value="Respond")):
                james.run_cowork_one_shot(config, session)
            self.assertFalse((root / "log.txt").exists())
            record.assert_not_called()
            session.log_enabled = True
            session.db_enabled = True
            with (patch.object(james.AgentEngine, "_call_ollama", side_effect=RuntimeError("model unavailable")),
                  patch("builtins.input", return_value="Respond")):
                james.run_cowork_one_shot(config, session)
            log = (root / "log.txt").read_text(encoding="utf-8-sig")
            self.assertIn("status: failed", log)
            self.assertIn("model unavailable", log)
            record.assert_not_called()

    def test_plan_wrapper_logs_to_selected_project(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            session = james.CoworkSession(root)
            with (patch.dict("os.environ", {"OLLAMA_FLOW_LOG": "0"}),
                  patch.object(james, "_send_cowork_plan_step_to_code", side_effect=lambda *_: print("plan result")),
                  redirect_stdout(StringIO())):
                james.send_cowork_plan_step_to_code({}, session)
            self.assertIn("plan result", (root / "log.txt").read_text(encoding="utf-8-sig"))

    def test_cowork_starts_from_project_json_not_chat_override(self):
        config = james.load_james_config()
        config[james.CHAT_PROJECT_SUBDIR_OVERRIDE_KEY] = "proj_chat"
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / config["project_config"]).write_text('{"subdir":"proj_default"}')
            with (patch.object(james, "PROJECT_ROOT", root),
                  patch.object(james, "render_cowork_menu"),
                  patch.object(james, "read_key", side_effect=["\r", "b"]),
                  patch.object(james, "cowork_code_menu") as enter):
                james.cowork_menu(config)
            self.assertEqual(enter.call_args.args[1].project_directory, (root / "proj_default").resolve())
            self.assertFalse((root / "proj_chat").exists())
            self.assertEqual(config[james.CHAT_PROJECT_SUBDIR_OVERRIDE_KEY], "proj_chat")

    def test_override_routes_files_commands_logs_and_database(self):
        config = james.load_james_config()
        schema = james.PROJECT_ROOT / james.DEFAULT_TASKS_SCHEMA_PATH
        profile = james.load_cowork_agents_config()["artist"]
        with TemporaryDirectory() as directory, ExitStack() as stack:
            root = Path(directory).resolve()
            default = root / "proj_default"
            selected = root / "nested" / "proj_selected"
            default.mkdir()
            selected.mkdir(parents=True)
            project_json = root / config["project_config"]
            project_json.write_text('{"subdir":"proj_default", "debug":false}')
            original = project_json.read_bytes()
            db = root / "history.db"
            stack.enter_context(patch.object(james, "PROJECT_ROOT", root))
            stack.enter_context(patch.object(james, "DEFAULT_TASKS_SCHEMA_PATH", schema))
            stack.enter_context(patch.object(james, "main_database_file", return_value=db))
            stack.enter_context(patch.dict("os.environ", {"OLLAMA_FLOW_LOG": "0"}))
            stack.enter_context(patch.object(james, "ollama_api", return_value=SimpleNamespace(read_timeout_seconds=5, default_options={})))
            for name in ("clear_screen", "pause"):
                stack.enter_context(patch.object(james, name))
            stack.enter_context(redirect_stdout(StringIO()))
            session = james.cowork_session_from_profile(james.active_project_directory(config), profile)
            self.assertEqual(session.project_directory, default)
            with (patch.object(james, "pick_cowork_setting", return_value=0),
                  patch("builtins.input", return_value="nested/proj_selected")):
                james.select_cowork_project(config, session)
            session.review_enabled = False
            session.db_enabled = True
            session.log_enabled = True
            with (patch.object(james.AgentEngine, "_call_ollama", side_effect=[
                    {"message": {"tool_calls": [{"function": {"name": "write_file", "arguments": {"path": "art.svg", "content": "<svg/>"}}}]}},
                    {"message": {"content": "Saved art.svg"}}]),
                  patch("builtins.input", return_value="Create art.svg")):
                james.run_cowork_one_shot(config, session)
            self.assertEqual((selected / "art.svg").read_text(), "<svg/>")
            self.assertEqual(list(default.iterdir()), [])
            self.assertIn("james.cowork.artist", (selected / "log.txt").read_text(encoding="utf-8-sig"))
            rows = james.list_task_rows(db)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["project"], "nested/proj_selected")
            self.assertEqual(rows[0]["task"], "cowork_artist")
            self.assertEqual(json.loads(rows[0]["parameters"])["agent_id"], "artist")
            self.assertEqual(project_json.read_bytes(), original)
            tools = james.build_file_tools(james.ProjectToolScope(selected), james.ToolPolicy.CODE, run_confirm=lambda _: True)
            with patch("lib.wrapp_agent.subprocess.run", return_value=SimpleNamespace(stdout="", stderr="", returncode=0)) as command:
                tools["run_command"].function("echo check")
            self.assertEqual(command.call_args.kwargs["cwd"], selected)
            with self.assertRaises(ValueError):
                tools["write_file"].function("../../outside.txt", "no")
            output = StringIO()
            with redirect_stdout(output):
                james.render_cowork_code_menu(config, session, 0)
            self.assertIn("nested/proj_selected", output.getvalue().splitlines()[0])


if __name__ == "__main__":
    unittest.main()
