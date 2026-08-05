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
from lib.wrapp_ollama import ollama_api


class CliOllamaSkillTests(unittest.TestCase):
    def test_parse_boolean_accepts_true_and_false_only(self) -> None:
        self.assertTrue(cli_ollama.parse_boolean("true"))
        self.assertFalse(cli_ollama.parse_boolean("FALSE"))
        with self.assertRaises(argparse.ArgumentTypeError):
            cli_ollama.parse_boolean("yes")

    def test_setector_alias_sets_selector_argument(self) -> None:
        with patch("sys.argv", ["cli_ollama.py", "--setector", "test123"]):
            arguments = cli_ollama.parse_arguments()

        self.assertEqual(arguments.selector, "test123")

    def test_merge_arguments_are_parsed(self) -> None:
        with patch("sys.argv", ["cli_ollama.py", "-m", "first.txt", "second text", "result.txt"]):
            merge_arguments = cli_ollama.parse_arguments()

        self.assertEqual(merge_arguments.merge_values, ["first.txt", "second text", "result.txt"])

    def test_prepare_merge_uses_file_or_literal_text_and_default_destination(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            project_directory = Path(temporary_directory)
            (project_directory / "first.txt").write_text("First content\n", encoding="utf-8")
            arguments = SimpleNamespace(
                echo_message=None,
                export_uid=None,
                merge_values=["first.txt", "Add more content"],
            )
            result = cli_ollama.run_command(
                arguments,
                {},
                project_directory,
                log_enabled=False,
                project_debug=False,
                db_enabled=False,
                db_selector="",
            )
            output_path = project_directory / "merged.txt"

            content = output_path.read_text(encoding="utf-8")

        self.assertEqual(result, 0)
        self.assertEqual(content, "First content\n\nAdd more content")
        self.assertEqual(output_path.name, "merged.txt")

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
            "Write maintainable code.\n\n\nBuild a calculator.",
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
            "Write maintainable code.\n\n\nNew instruction.",
        )

    def test_cli_options_override_task_options_and_shared_defaults(self) -> None:
        arguments = SimpleNamespace(
            model=None,
            seed_rnd=False,
            seed=None,
            temp=0.1,
            num_predict=None,
            num_ctx=None,
            repeat_penalty=None,
        )
        task = {
            "model": "test-model",
            "prompt": "test prompt",
            "temperature": 0.3,
            "options": {"temperature": 0.2, "num_predict": 2048},
        }

        with TemporaryDirectory() as temporary_directory:
            project_root = Path(temporary_directory)
            library_directory = project_root / "lib"
            library_directory.mkdir()
            (project_root / "project.json").write_text("{}", encoding="utf-8")
            config_path = library_directory / "ollama.json"
            config_path.write_text(
                json.dumps(
                    {
                        "url": "http://localhost:11434",
                        "debug": False,
                        "default_options": {
                            "seed": 42,
                            "num_predict": 1024,
                            "num_ctx": 4096,
                            "temperature": 0.5,
                            "repeat_penalty": 1.1,
                        },
                    }
                ),
                encoding="utf-8",
            )
            app = ollama_api(config_path)
            effective_options = app.effective_task_options(
                cli_ollama.apply_overrides(task, arguments, data=None)
            )

        self.assertEqual(effective_options["seed"], 42)
        self.assertEqual(effective_options["num_predict"], 2048)
        self.assertEqual(effective_options["temperature"], 0.1)

    def test_zero_seed_in_task_generates_one_random_seed(self) -> None:
        arguments = SimpleNamespace(
            model=None,
            seed_rnd=False,
            seed=None,
            temp=None,
            num_predict=None,
            num_ctx=None,
            repeat_penalty=None,
        )
        task = {"model": "test-model", "prompt": "test prompt", "seed": 0}

        with TemporaryDirectory() as temporary_directory:
            project_root = Path(temporary_directory)
            (project_root / "project.json").write_text("{}", encoding="utf-8")
            library_directory = project_root / "lib"
            library_directory.mkdir()
            config_path = library_directory / "ollama.json"
            config_path.write_text(
                json.dumps(
                    {
                        "url": "http://localhost:11434",
                        "debug": False,
                        "default_options": {
                            "seed": 42,
                            "num_predict": 1024,
                            "num_ctx": 4096,
                            "temperature": 0.5,
                            "repeat_penalty": 1.1,
                        },
                    }
                ),
                encoding="utf-8",
            )
            app = ollama_api(config_path)
            resolved_task = cli_ollama.apply_overrides(task, arguments, data=None)
            with patch.object(cli_ollama.secrets, "randbelow", return_value=123456):
                resolved_task = cli_ollama.materialize_zero_seed(resolved_task, app)

        self.assertEqual(resolved_task["options"], {"seed": 123457})
        self.assertEqual(app.effective_task_options(resolved_task)["seed"], 123457)

    def test_cli_seed_overrides_zero_seed_in_task(self) -> None:
        arguments = SimpleNamespace(
            model=None,
            seed_rnd=False,
            seed=42,
            temp=None,
            num_predict=None,
            num_ctx=None,
            repeat_penalty=None,
        )
        task = {"model": "test-model", "prompt": "test prompt", "seed": 0}

        with TemporaryDirectory() as temporary_directory:
            project_root = Path(temporary_directory)
            (project_root / "project.json").write_text("{}", encoding="utf-8")
            library_directory = project_root / "lib"
            library_directory.mkdir()
            config_path = library_directory / "ollama.json"
            config_path.write_text(
                json.dumps(
                    {
                        "url": "http://localhost:11434",
                        "debug": False,
                        "default_options": {
                            "seed": 7,
                            "num_predict": 1024,
                            "num_ctx": 4096,
                            "temperature": 0.5,
                            "repeat_penalty": 1.1,
                        },
                    }
                ),
                encoding="utf-8",
            )
            app = ollama_api(config_path)
            resolved_task = cli_ollama.apply_overrides(task, arguments, data=None)
            with patch.object(cli_ollama.secrets, "randbelow") as random_seed:
                resolved_task = cli_ollama.materialize_zero_seed(resolved_task, app)

        random_seed.assert_not_called()
        self.assertEqual(app.effective_task_options(resolved_task)["seed"], 42)

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

    def test_selector_option_is_saved_in_project_json(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            project_directory = Path(temporary_directory)
            (project_directory / "project.json").write_text(
                json.dumps({"subdir": "active", "log": False, "selector": "old"}),
                encoding="utf-8",
            )
            arguments = SimpleNamespace(
                project=None,
                debug=None,
                selector="test123",
                clear_log=False,
                clear_out=None,
            )

            with (
                patch.object(cli_ollama, "PROJECT_DIR", project_directory),
                patch.object(cli_ollama, "parse_arguments", return_value=arguments),
            ):
                self.assertEqual(cli_ollama.main(), 0)

            saved_config = json.loads((project_directory / "project.json").read_text(encoding="utf-8"))

        self.assertEqual(saved_config["selector"], "test123")

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
        parameters = json.loads(rows[0]["parameters"])
        self.assertEqual(parameters["temperature"], 0.2)
        self.assertEqual(
            parameters["task_state"],
            {
                "model": "test-model",
                "prompt": "test prompt",
                "type": "prompt",
                "debug": False,
                "think": False,
                "effective_options": {"seed": 7, "temperature": 0.2, "num_predict": 32},
            },
        )

    def test_task_state_keeps_task_settings_and_final_cli_options(self) -> None:
        task = {
            "type": "ocr",
            "model": "vision-model",
            "prompt": "Read the image.",
            "max_image_size": 640,
            "options": {"temperature": 0.1, "num_predict": 4096},
        }

        task_state = cli_ollama.build_task_state(
            task,
            task_kind="ocr",
            effective_options={
                "seed": 42,
                "temperature": 0.3,
                "num_predict": 4096,
                "num_ctx": 4096,
                "repeat_penalty": 1.1,
            },
            debug_enabled=True,
            output_path=Path("C:/project/ocr.txt"),
            image_path=Path("C:/project/camera.png"),
            project_directory=Path("C:/project"),
        )

        self.assertEqual(task_state["options"], {"temperature": 0.1, "num_predict": 4096})
        self.assertEqual(task_state["max_image_size"], 640)
        self.assertEqual(task_state["effective_options"]["temperature"], 0.3)
        self.assertEqual(task_state["output_file"], "ocr.txt")
        self.assertEqual(task_state["input_file"], "camera.png")


if __name__ == "__main__":
    unittest.main()
