"""Integration checks using a stub model and a real temporary SQLite database."""
import json
import os
import shutil
import sqlite3
from contextlib import ExitStack, redirect_stdout, redirect_stderr
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import cli_laya

ROOT = Path(__file__).resolve().parents[1]


class LayaPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.root = Path(self.stack.enter_context(TemporaryDirectory()))
        (self.root / "data").mkdir()
        shutil.copyfile(ROOT / "data/tasks.json", self.root / "data/tasks.json")
        self.questions = self.root / "questions.json"
        self.questions.write_text(json.dumps({
            "language": {"type": "choice", "instructions": "Language?",
                         "criteria": {"en": "English", "cs": "Czech"}}
        }), encoding="utf-8")
        self.source = self.root / "input.md"
        self.source.write_text("---\nsubject: Greeting\n---\nHello world", encoding="utf-8")
        self.result = {"answers": {"language": {"choice": "en", "confidence": .9}},
                       "routing": {"model": "multilingual"}}
        self.router = Mock()
        self.router.predict.return_value = self.result
        self.stack.enter_context(patch.dict("sys.modules", {
            "torch": Mock(), "laya": SimpleNamespace(Router=Mock(return_value=self.router)),
            "laya.agent": SimpleNamespace(Agent=Mock(return_value=SimpleNamespace(cfg={})))
        }))
        self.stack.enter_context(patch.object(cli_laya, "PROJECT_ROOT", self.root))
        self.stack.enter_context(patch.object(cli_laya, "ensure_model"))
        self.stack.enter_context(patch.dict(os.environ, {"OLLAMA_FLOW_LOG": ""}))
        self.output = StringIO()
        self.stack.enter_context(redirect_stdout(self.output))
        self.stack.enter_context(redirect_stderr(self.output))
        self.configure(True, True)

    def configure(self, log, db):
        (self.root / "project.json").write_text(json.dumps({
            "subdir": "project_laya/test2", "log": log, "db": db, "selector": "rlpc_laya"
        }), encoding="utf-8")

    def run_cli(self, *args):
        with patch("sys.argv", ["cli_laya.py", *args]):
            return cli_laya.main()

    def run_single(self):
        return self.run_cli(str(self.source), "-q", str(self.questions), "-v")

    def rows(self):
        with sqlite3.connect(self.root / "data/tasks.db") as conn:
            conn.row_factory = sqlite3.Row
            return [dict(row) for row in conn.execute("SELECT * FROM tasks")]

    def log(self):
        return (self.root / "project_laya/test2/log.txt").read_text(encoding="utf-8-sig")

    def test_single_records_full_input_questions_result_and_selector(self):
        self.assertEqual(self.run_single(), 0)
        row, = self.rows()
        self.assertEqual(row["selector"], "rlpc_laya")
        self.assertEqual(Path(row["project"]), Path("project_laya/test2"))
        self.assertEqual(row["model"], "laya:multilingual")
        self.assertEqual(json.loads(row["prompt"]), {"subject": "Greeting", "body": "Hello world"})
        self.assertEqual(json.loads(row["answer"]), self.result)
        self.assertEqual(json.loads(row["instruction"])["language"]["instructions"], "Language?")
        self.assertGreaterEqual(float(row["key1"]), 0)
        self.assertIn("laya_result", self.log())
        self.assertIn("Hello world", self.log())
        self.assertIn("working directory", self.log())

    def test_flags_are_independent(self):
        for log, db in ((False, False), (True, False), (False, True)):
            with self.subTest(log=log, db=db):
                logpath = self.root / "project_laya/test2/log.txt"
                dbpath = self.root / "data/tasks.db"
                logpath.unlink(missing_ok=True)
                dbpath.unlink(missing_ok=True)
                self.configure(log, db)
                self.assertEqual(self.run_single(), 0)
                self.assertEqual(logpath.exists(), log)
                self.assertEqual(dbpath.exists(), db)

    def test_batch_stores_each_success_and_continues_after_failure(self):
        batch = self.root / "batch"
        batch.mkdir()
        for name in ("a", "b", "c"):
            (batch / f"{name}.md").write_text(name, encoding="utf-8")
        self.router.predict.side_effect = [self.result, RuntimeError("prediction failed"), self.result]
        self.assertEqual(self.run_cli("-b", str(batch), "-q", str(self.questions)), 1)
        self.assertEqual(len(self.rows()), 2)
        self.assertTrue((batch / "a.json").exists())
        self.assertFalse((batch / "b.json").exists())
        self.assertTrue((batch / "c.json").exists())
        self.assertIn("prediction failed", self.log())

    def test_runner_logging_does_not_duplicate_console_session(self):
        with patch.dict(os.environ, {"OLLAMA_FLOW_LOG": "1"}):
            self.assertEqual(self.run_single(), 0)
        self.assertNotIn("session_start", self.log())
        self.assertEqual(self.log().count('event="laya_result"'), 1)
        self.assertEqual(len(self.rows()), 1)

    def test_database_failure_is_reported_and_returns_failure(self):
        with patch.object(cli_laya, "record_task_output", side_effect=ValueError("database unavailable")):
            self.assertEqual(self.run_single(), 1)
        self.assertIn("database unavailable", self.log())
        self.assertNotIn("Task recorded", self.output.getvalue())

    def test_version_and_invalid_input_do_not_create_database_records(self):
        self.assertEqual(self.run_cli("-V"), 0)
        self.assertEqual(self.run_cli(str(self.root / "missing.md"), "-q", str(self.questions)), 1)
        self.assertFalse((self.root / "data/tasks.db").exists())
        self.assertIn("File not found", self.log())

    def test_model_failure_is_logged_without_success_record(self):
        self.router.predict.side_effect = RuntimeError("model failed")
        self.assertEqual(self.run_single(), 1)
        self.assertIn("model failed", self.log())
        self.assertFalse((self.root / "data/tasks.db").exists())

    def test_model_override_reaches_prediction_and_database(self):
        self.assertEqual(self.run_cli(str(self.source), "-q", str(self.questions), "--model", "english"), 0)
        self.assertEqual(self.router.predict.call_args.kwargs["model"], "english")
        row, = self.rows()
        self.assertEqual(row["model"], "laya:english")
        self.assertEqual(json.loads(row["parameters"])["config"]["checkpoint"], "english")

    def test_download_only_updates_selected_model_without_input_or_db(self):
        self.source.unlink()
        self.questions.unlink()
        with patch.object(cli_laya, "ensure_model") as download:
            self.assertEqual(self.run_cli("--model", "english", "-u", "--download-only"), 0)
        self.assertEqual(download.call_args.args[1:], ("english", True))
        self.router.predict.assert_not_called()
        self.assertFalse((self.root / "data/tasks.db").exists())


if __name__ == "__main__":
    unittest.main()
