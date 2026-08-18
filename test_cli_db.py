"""Tests for interactive completed-task record navigation."""

from __future__ import annotations

from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import sys
import unittest
from unittest.mock import patch

import cli_db
from lib.wrapp_db import TaskDatabaseError, list_task_rows, record_task_output


class CliDatabaseTests(unittest.TestCase):
    def test_render_task_record_repeats_id_after_long_content(self) -> None:
        output = StringIO()

        with redirect_stdout(output):
            cli_db.render_task_record({"uid": 42, "answer": "long answer"})

        self.assertEqual(output.getvalue().count("ID: 42"), 1)
        self.assertLess(output.getvalue().rfind("ID: 42"), output.getvalue().rfind("← previous ID"))

    def test_cycle_task_id_wraps_between_existing_ids(self) -> None:
        task_ids = [2, 5, 9]

        self.assertEqual(cli_db.cycle_task_id(task_ids, 2, -1), 9)
        self.assertEqual(cli_db.cycle_task_id(task_ids, 9, 1), 2)
        self.assertEqual(cli_db.cycle_task_id(task_ids, 5, -1), 2)
        self.assertEqual(cli_db.cycle_task_id(task_ids, 5, 1), 9)

    def test_cycle_task_id_rejects_unknown_or_invalid_navigation(self) -> None:
        with self.assertRaises(TaskDatabaseError):
            cli_db.cycle_task_id([], 1, 1)
        with self.assertRaises(TaskDatabaseError):
            cli_db.cycle_task_id([2, 5], 3, 1)
        with self.assertRaises(ValueError):
            cli_db.cycle_task_id([2, 5], 2, 0)

    def test_confirm_task_delete_accepts_only_y(self) -> None:
        self.assertTrue(cli_db.confirm_task_delete(5, iter(["x", "y"]).__next__))
        self.assertFalse(cli_db.confirm_task_delete(5, iter(["n"]).__next__))
        self.assertFalse(cli_db.confirm_task_delete(5, iter(["q"]).__next__))

    def test_browse_deletes_current_record_and_moves_to_next_id(self) -> None:
        records = {2: {"uid": 2}, 5: {"uid": 5}, 9: {"uid": 9}}
        keypresses = iter(["d", "y", "q"])
        shown_ids: list[int] = []

        def delete_record(_database_path, task_id: int) -> bool:
            return records.pop(task_id, None) is not None

        with (
            patch.object(cli_db, "list_task_rows", return_value=list(records.values())),
            patch.object(cli_db, "get_task_row", side_effect=lambda _path, uid: records.get(uid)),
            patch.object(cli_db, "delete_task", side_effect=delete_record),
            patch.object(cli_db, "read_terminal_key", side_effect=keypresses),
            patch.object(cli_db, "clear_record_screen"),
            patch.object(cli_db, "render_task_record", side_effect=lambda row: shown_ids.append(row["uid"])),
        ):
            cli_db.browse_task_records(Path("tasks.db"), 5)

        self.assertNotIn(5, records)
        self.assertEqual(shown_ids, [5, 9])

    def test_short_actions_and_export_id_forms_are_parsed(self) -> None:
        cases = (
            (["cli_db.py", "-l"], "list", True),
            (["cli_db.py", "-a", "test answer"], "add", "test answer"),
            (["cli_db.py", "-d", "12"], "delete_uid", 12),
            (["cli_db.py", "--merge-db", "db2.db"], "merge_database", "db2.db"),
            (["cli_db.py", "-e", "123"], "answer_export_uid", 123),
            (["cli_db.py", "-exp", "123", "answer.txt"], "answer_export_filename", "answer.txt"),
            (["cli_db.py", "--export", "123"], "export_uid", 123),
            (["cli_db.py", "--export", "123", "record.json"], "export_filename", "record.json"),
            (["cli_db.py", "--list", "--model", "deepseek", "filtered.db"], "list_output_database", "filtered.db"),
            (["cli_db.py", "--db", "holly_pivo1.db", "-l"], "source_database", "holly_pivo1.db"),
            (["cli_db.py", "--edit", "12", "updated answer"], "edit_uid", 12),
            (
                ["cli_db.py", "db2.db", "-e", "--ID", "123", "--out", "answer.txt"],
                "answer_export_uid",
                123,
            ),
        )

        for argv, attribute, expected in cases:
            with self.subTest(argv=argv), patch.object(sys, "argv", argv):
                arguments = cli_db.parse_arguments()
            self.assertEqual(getattr(arguments, attribute), expected)

        with patch.object(sys, "argv", ["cli_db.py", "--edit", "12", "updated answer"]):
            arguments = cli_db.parse_arguments()
        self.assertEqual(arguments.edit_answer, "updated answer")

    def test_default_export_path_uses_active_project(self) -> None:
        project_directory = Path("C:/example/project_test")

        with patch.object(cli_db, "get_active_project_directory", return_value=project_directory):
            self.assertEqual(cli_db.resolve_export_path(None, "export.txt"), project_directory / "export.txt")
            self.assertEqual(cli_db.resolve_export_path("chosen.txt", "export.txt"), project_directory / "chosen.txt")

        with patch.object(cli_db, "get_active_project_directory", return_value=project_directory):
            with self.assertRaises(TaskDatabaseError):
                cli_db.resolve_export_path("nested/chosen.txt", "export.txt")

    def test_list_columns_are_loaded_from_tasks_base_configuration(self) -> None:
        columns = cli_db.load_list_columns()

        self.assertEqual(columns[0], {"field": "uid", "name": "id", "width": 5})
        self.assertEqual(columns[-1]["field"], "answer")

    def test_list_model_filter_can_create_a_filtered_database(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            project_root = Path(temporary_directory)
            data_directory = project_root / "data"
            data_directory.mkdir()
            assistant_data_directory = project_root / "assistant" / "data"
            assistant_data_directory.mkdir(parents=True)
            source_root = Path(__file__).resolve().parent
            for filename in ("tasks.json", "tasks_base.json"):
                (assistant_data_directory / filename).write_text(
                    (source_root / "assistant" / "data" / filename).read_text(encoding="utf-8"), encoding="utf-8"
                )
            source_database = data_directory / "tasks.db"
            schema_path = assistant_data_directory / "tasks.json"
            for model in ("deepseek-ocr:3b", "qwen3.5:latest"):
                record_task_output(
                    source_database,
                    schema_path,
                    project="test_project",
                    selector="test",
                    task="assistant/tasks/task_test.json",
                    model=model,
                    parameters={},
                    prompt="prompt",
                    instruction=None,
                    answer="answer",
                )

            with (
                patch.object(cli_db, "PROJECT_ROOT", project_root),
                patch.object(cli_db, "TASKS_BASE_CONFIG_PATH", assistant_data_directory / "tasks_base.json"),
                patch.object(sys, "argv", ["cli_db.py", "--list", "--model", "deepseek", "filtered.db"]),
            ):
                self.assertEqual(cli_db.main(), 0)

            filtered_rows = list_task_rows(data_directory / "filtered.db")

        self.assertEqual(len(filtered_rows), 1)
        self.assertEqual(filtered_rows[0]["model"], "deepseek-ocr:3b")


if __name__ == "__main__":
    unittest.main()
