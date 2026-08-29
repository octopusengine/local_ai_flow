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
    def test_task_override_replaces_the_flow_task_and_keeps_other_arguments(self) -> None:
        command = runner.FlowCommand(
            source_label="step 1",
            display_arguments=("python", "cli_ollama.py", "--type", "task_chat.json", "--model", "flow-model", "--input", "prompt.txt"),
            execution_arguments=(
                sys.executable,
                str(runner.PROJECT_ROOT / "cli_ollama.py"),
                "--type",
                "task_chat.json",
                "--model",
                "flow-model",
                "--input",
                "prompt.txt",
            ),
        )

        updated_command = runner.apply_task_override([command], "task_test.json")[0]

        self.assertEqual(
            updated_command.execution_arguments[2:],
            ("--input", "prompt.txt", "--type", "task_test.json"),
        )

    def test_task_override_rejects_a_directory_path(self) -> None:
        with self.assertRaisesRegex(runner.FlowError, "without a directory path"):
            runner.apply_task_override([], "assistant/tasks/task_test.json")

    def test_image_override_replaces_an_existing_image_argument(self) -> None:
        command = runner.FlowCommand(
            source_label="step 1",
            display_arguments=("python", "cli_ollama.py", "--type", "task_chat.json", "--image", "old.png"),
            execution_arguments=(
                sys.executable,
                str(runner.PROJECT_ROOT / "cli_ollama.py"),
                "--type",
                "task_chat.json",
                "--image",
                "old.png",
            ),
        )

        updated_command = runner.apply_image_override([command], "camera.png")[0]

        self.assertEqual(updated_command.execution_arguments[-2:], ("--image", "camera.png"))

    def test_sc_language_override_replaces_a_flow_language_and_preserves_other_arguments(self) -> None:
        command = runner.FlowCommand(
            source_label="step 1",
            display_arguments=("python", "cli_ollama.py", "--type", "task_chat.json", "--sc-en"),
            execution_arguments=(
                sys.executable,
                str(runner.PROJECT_ROOT / "cli_ollama.py"),
                "--type",
                "task_chat.json",
                "--sc-en",
            ),
        )

        updated_command = runner.apply_sc_language_override([command], "cz")[0]

        self.assertEqual(updated_command.display_arguments, ("python", "cli_ollama.py", "--type", "task_chat.json", "--sc-cz"))
        self.assertEqual(updated_command.execution_arguments[-1], "--sc-cz")

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


class RunnerBatchLoopTests(unittest.TestCase):
    def test_batch_list_loop_is_expanded_after_the_batch_command_runs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_directory = Path(temporary_directory)
            flow_path = project_directory / "flow.txt"
            flow_path.write_text(
                "python cli_tool.py --batch\n"
                "@for ITEM in $batch_list\n"
                "    python cli_tool.py --echo $ITEM\n"
                "@endfor\n",
                encoding="utf-8",
            )
            nodes = runner.load_text_flow(flow_path, project_directory)

            self.assertIsInstance(nodes[1], runner.FlowBatchLoop)

            executed_arguments: list[tuple[str, ...]] = []

            def run_command(arguments: tuple[str, ...], **_kwargs: object) -> SimpleNamespace:
                executed_arguments.append(arguments)
                if "--batch" in arguments:
                    (project_directory / "batch_list.txt").write_text("one.txt\ntwo.txt\n", encoding="utf-8")
                return SimpleNamespace(returncode=0)

            with patch.object(runner.subprocess, "run", side_effect=run_command):
                result = runner.run_flow(
                    flow_path,
                    nodes,
                    False,
                    project_directory=project_directory,
                    capture_output=False,
                    debug_enabled=False,
                )

        self.assertEqual(result, 0)
        self.assertEqual([arguments[-1] for arguments in executed_arguments], ["--batch", "one.txt", "two.txt"])

    def test_batch_alias_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_directory = Path(temporary_directory)
            flow_path = project_directory / "flow.txt"
            flow_path.write_text(
                "@for ITEM in $batch\n"
                "    python cli_tool.py --echo $ITEM\n"
                "@endfor\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(runner.FlowError, r"invalid flow control line"):
                runner.load_text_flow(flow_path, project_directory)


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
