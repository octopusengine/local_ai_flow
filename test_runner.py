"""Tests for flow reporting in ``runner.py``."""

import json
import sys
import tempfile
import unittest
from types import SimpleNamespace
from pathlib import Path
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


class RunnerTextFlowVariableTests(unittest.TestCase):
    def test_text_flow_expands_declared_variables_in_arguments(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            flow_path = Path(temporary_directory) / "flow.txt"
            flow_path.write_text(
                "$dotaz = \"Proč má člověk teplotu?\"\n"
                "$prefix = \"medical\"\n"
                "python cli_ollama.py --text \"$dotaz\" --out \"${prefix}_answer.txt\"\n",
                encoding="utf-8",
            )

            commands = runner.load_text_flow(flow_path)

        self.assertEqual(len(commands), 1)
        self.assertEqual(
            commands[0].display_arguments,
            ("python", "cli_ollama.py", "--text", "Proč má člověk teplotu?", "--out", "medical_answer.txt"),
        )

    def test_text_flow_rejects_unknown_variable(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            flow_path = Path(temporary_directory) / "flow.txt"
            flow_path.write_text("python cli_ollama.py --text $dotaz\n", encoding="utf-8")

            with self.assertRaisesRegex(runner.FlowError, r"unknown flow variable \$dotaz"):
                runner.load_text_flow(flow_path)

    def test_text_flow_rejects_duplicate_variable_declaration(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            flow_path = Path(temporary_directory) / "flow.txt"
            flow_path.write_text("$dotaz = \"A\"\n$dotaz = \"B\"\n", encoding="utf-8")

            with self.assertRaisesRegex(runner.FlowError, r"\$dotaz is already defined"):
                runner.load_text_flow(flow_path)


class RunnerConditionalFlowTests(unittest.TestCase):
    def test_version_two_loads_both_branches(self) -> None:
        document = {
            "version": 2,
            "steps": [
                {
                    "if": {"file_not_empty": "ocr.txt"},
                    "then": [{"run": "cli_ollama.py", "args": ["--echo", "then"]}],
                    "else": [{"run": "cli_ollama.py", "args": ["--echo", "else"]}],
                }
            ],
        }
        with tempfile.TemporaryDirectory() as temporary_directory:
            flow_path = Path(temporary_directory) / "flow.json"
            flow_path.write_text(json.dumps(document), encoding="utf-8")

            nodes = runner.load_json_flow(flow_path, "260730_1200")

        self.assertEqual(len(nodes), 1)
        self.assertIsInstance(nodes[0], runner.FlowBranch)
        branch = nodes[0]
        self.assertEqual(branch.condition.kind, "file_not_empty")
        self.assertEqual(len(branch.then_steps), 1)
        self.assertEqual(len(branch.else_steps), 1)

    def test_file_conditions_distinguish_missing_empty_and_populated_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_directory = Path(temporary_directory)
            empty_file = project_directory / "empty.txt"
            empty_file.touch()
            populated_file = project_directory / "result.txt"
            populated_file.write_text("OCR result", encoding="utf-8")

            self.assertFalse(
                runner.evaluate_flow_condition(
                    runner.FlowCondition("file_exists", Path("missing.txt")), project_directory
                )
            )
            self.assertTrue(
                runner.evaluate_flow_condition(
                    runner.FlowCondition("file_exists", Path("empty.txt")), project_directory
                )
            )
            self.assertFalse(
                runner.evaluate_flow_condition(
                    runner.FlowCondition("file_not_empty", Path("empty.txt")), project_directory
                )
            )
            self.assertTrue(
                runner.evaluate_flow_condition(
                    runner.FlowCondition("file_not_empty", Path("result.txt")), project_directory
                )
            )

    def test_runtime_executes_only_the_selected_branch(self) -> None:
        def echo_command(label: str) -> runner.FlowCommand:
            return runner.FlowCommand(
                source_label=label,
                display_arguments=("python", "cli_ollama.py", "--echo", label),
                execution_arguments=(
                    sys.executable,
                    str(runner.PROJECT_ROOT / "cli_ollama.py"),
                    "--echo",
                    label,
                ),
            )

        branch = runner.FlowBranch(
            source_label="step 1",
            condition=runner.FlowCondition("file_exists", Path("ocr.txt")),
            then_steps=(echo_command("then"),),
            else_steps=(echo_command("else"),),
        )
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_directory = Path(temporary_directory)
            with patch.object(
                runner.subprocess,
                "run",
                return_value=SimpleNamespace(returncode=0),
            ) as run_mock:
                self.assertEqual(
                    runner.run_flow(
                        Path("flow.json"),
                        [branch],
                        False,
                        project_directory=project_directory,
                        capture_output=False,
                        debug_enabled=False,
                    ),
                    0,
                )
            self.assertEqual(run_mock.call_args.args[0][-1], "else")

            (project_directory / "ocr.txt").write_text("text", encoding="utf-8")
            with patch.object(
                runner.subprocess,
                "run",
                return_value=SimpleNamespace(returncode=0),
            ) as run_mock:
                self.assertEqual(
                    runner.run_flow(
                        Path("flow.json"),
                        [branch],
                        False,
                        project_directory=project_directory,
                        capture_output=False,
                        debug_enabled=False,
                    ),
                    0,
                )
            self.assertEqual(run_mock.call_args.args[0][-1], "then")


if __name__ == "__main__":
    unittest.main()
