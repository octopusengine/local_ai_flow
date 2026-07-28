"""Tests for task preparation in ``cli_ollama.py``."""

from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import cli_ollama


class CliOllamaSkillTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
