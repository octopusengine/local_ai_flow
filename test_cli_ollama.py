"""Tests for task preparation in ``cli_ollama.py``."""

import argparse
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import cli_ollama


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


if __name__ == "__main__":
    unittest.main()
