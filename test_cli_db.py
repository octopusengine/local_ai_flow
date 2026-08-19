"""Tests for interactive completed-task record navigation."""

from __future__ import annotations

from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
import sqlite3
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
            (["cli_db.py", "--stru"], "structure", True),
            (["cli_db.py", "--group", "project"], "group_field", "project"),
            (["cli_db.py", "--sum"], "summary", True),
            (["cli_db.py", "--last"], "last", True),
            (["cli_db.py", "-a", "test answer"], "add", "test answer"),
            (["cli_db.py", "-d", "12"], "delete_uid", 12),
            (["cli_db.py", "--merge-db", "db2.db"], "merge_database", "db2.db"),
            (["cli_db.py", "-e", "123"], "answer_export_uid", 123),
            (["cli_db.py", "-E", "123"], "answer_print_uid", 123),
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

    def test_structure_group_and_sum_actions(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            project_root = Path(temporary_directory)
            data_directory = project_root / "data"
            data_directory.mkdir()
            source_root = Path(__file__).resolve().parent
            schema_path = data_directory / "tasks.json"
            schema_path.write_text((source_root / "data" / "tasks.json").read_text(encoding="utf-8"), encoding="utf-8")
            database_path = data_directory / "metrics.db"
            for project, usage in (
                ("alpha", '{"eval_count": 3, "prompt_eval_count": 5, "response_chunks": 4}'),
                ("alpha", '{"eval_count": 7, "prompt_eval_count": 11, "response_chunks": 8}'),
                ("beta", None),
            ):
                record_task_output(
                    database_path,
                    schema_path,
                    project=project,
                    selector="test",
                    task="task.json",
                    model="model",
                    parameters={},
                    prompt="prompt",
                    instruction=None,
                    answer="answer",
                    key2=usage,
                )

            task_rows = list_task_rows(database_path, task="task.json")

            def run_action(*action: str) -> str:
                output = StringIO()
                with (
                    patch.object(cli_db, "PROJECT_ROOT", project_root),
                    patch.object(sys, "argv", ["cli_db.py", *action, "--db", "metrics.db"]),
                    redirect_stdout(output),
                ):
                    self.assertEqual(cli_db.main(), 0)
                return output.getvalue()

            structure = run_action("--stru")
            grouped = run_action("--group", "project")
            connection = sqlite3.connect(database_path)
            try:
                connection.execute("UPDATE tasks SET datetime = ? WHERE uid = 1", ("2026-07-14T10:00:00+00:00",))
                connection.execute("UPDATE tasks SET datetime = ? WHERE uid = 2", ("2026-08-14T10:00:00+00:00",))
                connection.execute("UPDATE tasks SET datetime = ? WHERE uid = 3", ("2026-08-15T10:00:00+00:00",))
                connection.commit()
            finally:
                connection.close()
            monthly = run_action("--group", "monthly")
            summary = run_action("--sum")
            last = run_action("--last")

        self.assertIn("uid: INTEGER", structure)
        self.assertIn("key2: TEXT", structure)
        self.assertEqual(len(task_rows), 3)
        self.assertEqual(grouped.splitlines(), ["project | count", "alpha | 2", "beta | 1"])
        self.assertEqual(monthly.splitlines(), ["monthly | count", "2608 | 2", "2607 | 1"])
        self.assertIn("Total records: 3", summary)
        self.assertIn("Projects: 2", summary)
        self.assertIn("eval_count: 10", summary)
        self.assertIn("prompt_eval_count: 16", summary)
        self.assertIn("response_chunks: 12", summary)
        self.assertEqual(last, "3\n")

    def test_print_answer_writes_only_answer_to_standard_output(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            project_root = Path(temporary_directory)
            data_directory = project_root / "data"
            data_directory.mkdir()
            source_root = Path(__file__).resolve().parent
            schema_path = data_directory / "tasks.json"
            schema_path.write_text((source_root / "data" / "tasks.json").read_text(encoding="utf-8"), encoding="utf-8")
            database_path = data_directory / "answers.db"
            uid = record_task_output(
                database_path,
                schema_path,
                project="test",
                selector="test",
                task="task.json",
                model="model",
                parameters={},
                prompt="prompt",
                instruction=None,
                answer="answer without a newline",
            )
            output = StringIO()
            with (
                patch.object(cli_db, "PROJECT_ROOT", project_root),
                patch.object(sys, "argv", ["cli_db.py", "-E", str(uid), "--db", "answers.db"]),
                redirect_stdout(output),
            ):
                self.assertEqual(cli_db.main(), 0)

        self.assertEqual(output.getvalue(), "answer without a newline")

    def test_clear_answer_text_removes_common_markdown_and_html_formatting(self) -> None:
        answer = "# Heading\n\n**Bold** *text* with [a link](https://example.test).\n<h1>HTML title</h1><p>Paragraph <strong>text</strong><br>next line</p>\n- bullet\n1. item"

        self.assertEqual(
            cli_db.clear_answer_text(answer),
            "Heading\n\nBold text with a link.\n\nHTML title\n\nParagraph text\nnext line\n\nbullet\nitem",
        )

    def test_print_answer_clear_option_writes_cleaned_text(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            project_root = Path(temporary_directory)
            data_directory = project_root / "data"
            data_directory.mkdir()
            source_root = Path(__file__).resolve().parent
            schema_path = data_directory / "tasks.json"
            schema_path.write_text((source_root / "data" / "tasks.json").read_text(encoding="utf-8"), encoding="utf-8")
            database_path = data_directory / "answers.db"
            uid = record_task_output(
                database_path,
                schema_path,
                project="test",
                selector="test",
                task="task.json",
                model="model",
                parameters={},
                prompt="prompt",
                instruction=None,
                answer="**spoken** <h1>answer</h1>",
            )
            output = StringIO()
            with (
                patch.object(cli_db, "PROJECT_ROOT", project_root),
                patch.object(sys, "argv", ["cli_db.py", "-E", str(uid), "--clear", "--db", "answers.db"]),
                redirect_stdout(output),
            ):
                self.assertEqual(cli_db.main(), 0)

        self.assertEqual(output.getvalue(), "spoken \nanswer")

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
            source_root = Path(__file__).resolve().parent
            for filename in ("tasks.json", "tasks_base.json"):
                (data_directory / filename).write_text(
                    (source_root / "data" / filename).read_text(encoding="utf-8"), encoding="utf-8"
                )
            source_database = data_directory / "tasks.db"
            schema_path = data_directory / "tasks.json"
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
                patch.object(cli_db, "TASKS_BASE_CONFIG_PATH", data_directory / "tasks_base.json"),
                patch.object(sys, "argv", ["cli_db.py", "--list", "--model", "deepseek", "filtered.db"]),
            ):
                self.assertEqual(cli_db.main(), 0)

            filtered_rows = list_task_rows(data_directory / "filtered.db")

        self.assertEqual(len(filtered_rows), 1)
        self.assertEqual(filtered_rows[0]["model"], "deepseek-ocr:3b")


if __name__ == "__main__":
    unittest.main()
