"""Tests for flow reporting in ``runner.py``."""

import sys
import unittest
from unittest.mock import patch

import runner


class RunnerParameterReportTests(unittest.TestCase):
    def test_ollama_task_report_contains_effective_generation_options(self) -> None:
        command = runner.FlowCommand(
            source_label="line 1",
            display_arguments=("python", "cli_ollama.py", "--type", "task_test.json", "--temp", "0.4"),
            execution_arguments=(
                sys.executable,
                str(runner.PROJECT_ROOT / "cli_ollama.py"),
                "--type",
                "task_test.json",
                "--temp",
                "0.4",
            ),
        )

        report = runner.get_ollama_parameter_report(command)

        self.assertEqual(
            report,
            "[ task: prompt | model: qwen3.5:latest | seed: 42 | temperature: 0.4 | "
            "num_predict: 1024 | num_ctx: 4096 | repeat_penalty: 1.1 | think: false ]",
        )

    def test_project_and_debug_commands_do_not_have_generation_report(self) -> None:
        command = runner.FlowCommand(
            source_label="line 1",
            display_arguments=("python", "cli_ollama.py", "--debug", "false"),
            execution_arguments=(
                sys.executable,
                str(runner.PROJECT_ROOT / "cli_ollama.py"),
                "--debug",
                "false",
            ),
        )

        self.assertIsNone(runner.get_ollama_parameter_report(command))

    def test_random_seed_is_materialized_before_parameter_report(self) -> None:
        command = runner.FlowCommand(
            source_label="line 1",
            display_arguments=("python", "cli_ollama.py", "--type", "task_test.json", "--seed_rnd"),
            execution_arguments=(
                sys.executable,
                str(runner.PROJECT_ROOT / "cli_ollama.py"),
                "--type",
                "task_test.json",
                "--seed_rnd",
            ),
        )

        with patch.object(runner.secrets, "randbelow", return_value=122):
            materialized_command = runner.materialize_random_seed(command)

        self.assertEqual(materialized_command.display_text, command.display_text)
        self.assertEqual(materialized_command.execution_arguments[-2:], ("--seed", "123"))
        self.assertIn("seed: 123", runner.get_ollama_parameter_report(materialized_command))


if __name__ == "__main__":
    unittest.main()
