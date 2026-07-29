"""Tests for task preparation in ``cli_ollama.py``."""

import argparse
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import cli_ollama
from lib.wrapp_db import list_task_rows


class CliOllamaSkillTests(unittest.TestCase):
    def test_parse_boolean_accepts_true_and_false_only(self) -> None:
        self.assertTrue(cli_ollama.parse_boolean("true"))
        self.assertFalse(cli_ollama.parse_boolean("FALSE"))
        with self.assertRaises(argparse.ArgumentTypeError):
            cli_ollama.parse_boolean("yes")

    def test_existing_skill_is_prepended_to_system_instruction(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            project_directory = Path(temporary_directory)
            skills_directory = project_directory / "skills"
            skills_directory.mkdir()
            (skills_directory / "programmer.md").write_text(
                "Write maintainable code.", encoding="utf-8"
            )
            task = {"skill": "./skills/programmer.md", "instruction": "Build a calculator."}

            with patch.object(cli_ollama, "PROJECT_DIR", project_directory):
                resolved_task = cli_ollama.apply_skill(task)

        self.assertEqual(
            resolved_task["instruction"],
            "Write maintainable code.\n\nBuild a calculator.",
        )
        self.assertEqual(task["instruction"], "Build a calculator.")

    def test_missing_skill_leaves_task_unchanged(self) -> None:
        task = {"skill": "./skills/not-installed.md", "instruction": "Build a calculator."}
        with TemporaryDirectory() as temporary_directory:
            with patch.object(cli_ollama, "PROJECT_DIR", Path(temporary_directory)):
                self.assertEqual(cli_ollama.apply_skill(task), task)

    def test_skill_is_kept_when_cli_instruction_replaces_task_instruction(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            project_directory = Path(temporary_directory)
            skills_directory = project_directory / "skills"
            skills_directory.mkdir()
            (skills_directory / "programmer.md").write_text(
                "Write maintainable code.", encoding="utf-8"
            )
            task = {"skill": "./skills/programmer.md", "instruction": "Old instruction."}
            arguments = SimpleNamespace(
                model=None,
                seed_rnd=False,
                seed=None,
                temp=None,
                num_predict=None,
                num_ctx=None,
                repeat_penalty=None,
            )

            resolved_task = cli_ollama.apply_overrides(
                task,
                arguments,
                data=None,
                instruction="New instruction.",
            )
            with patch.object(cli_ollama, "PROJECT_DIR", project_directory):
                resolved_task = cli_ollama.apply_skill(resolved_task)

        self.assertEqual(
            resolved_task["instruction"],
            "Write maintainable code.\n\nNew instruction.",
        )

    def test_debug_option_is_saved_in_project_json(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            project_directory = Path(temporary_directory)
            (project_directory / "project.json").write_text(
                json.dumps({"subdir": "active", "log": False, "debug": False}),
                encoding="utf-8",
            )
            arguments = SimpleNamespace(
                project=None,
                debug=True,
                clear_log=False,
                clear_out=None,
            )

            with (
                patch.object(cli_ollama, "PROJECT_DIR", project_directory),
                patch.object(cli_ollama, "parse_arguments", return_value=arguments),
            ):
                self.assertEqual(cli_ollama.main(), 0)

            saved_config = json.loads((project_directory / "project.json").read_text(encoding="utf-8"))

        self.assertTrue(saved_config["debug"])

    def test_successful_final_response_is_recorded_when_db_is_enabled(self) -> None:
        class FakeOllamaApi:
            def __init__(self, *, on_response_text, **_kwargs) -> None:
                self.on_response_text = on_response_text

            def effective_task_debug_enabled(self, _task: dict[str, object]) -> bool:
                return False

            def effective_task_options(self, _task: dict[str, object]) -> dict[str, object]:
                return {"seed": 7, "temperature": 0.2, "num_predict": 32}

            def run_task(self, _task: dict[str, object], **_kwargs) -> int:
                self.on_response_text("final answer")
                return 0

        with TemporaryDirectory() as temporary_directory:
            project_root = Path(temporary_directory)
            tasks_directory = project_root / "tasks_flows"
            tasks_directory.mkdir()
            (tasks_directory / "task_test.json").write_text(
                json.dumps({"model": "test-model", "prompt": "test prompt"}),
                encoding="utf-8",
            )
            data_directory = project_root / "data"
            data_directory.mkdir()
            (data_directory / "tasks.json").write_text(
                (Path(__file__).resolve().parent / "data" / "tasks.json").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            project_directory = project_root / "pokus"
            project_directory.mkdir()
            arguments = SimpleNamespace(
                echo_message=None,
                test=False,
                list_models=False,
                status=False,
                task_type="task_test.json",
                input_file=None,
                translation_direction=None,
                data=None,
                instruction=None,
                out=None,
                model=None,
                seed_rnd=False,
                seed=None,
                temp=None,
                num_predict=None,
                num_ctx=None,
                repeat_penalty=None,
                append_out=False,
                out_header=None,
            )
            with (
                patch.object(cli_ollama, "PROJECT_DIR", project_root),
                patch.object(cli_ollama, "TASKS_FLOWS_DIR", tasks_directory),
                patch("lib.wrapp_ollama.ollama_api", FakeOllamaApi),
            ):
                result = cli_ollama.run_command(
                    arguments,
                    {"db": True},
                    project_directory,
                    log_enabled=False,
                    project_debug=False,
                    db_enabled=True,
                    db_selector="test123",
                )
            rows = list_task_rows(data_directory / "tasks.db", "pokus")

        self.assertEqual(result, 0)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["prompt"], "test prompt")
        self.assertEqual(rows[0]["answer"], "final answer")
        self.assertEqual(rows[0]["model"], "test-model")
        self.assertEqual(rows[0]["selector"], "test123")


if __name__ == "__main__":
    unittest.main()
