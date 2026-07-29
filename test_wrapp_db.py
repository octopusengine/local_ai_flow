"""Tests for the completed-task SQLite storage."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from lib.wrapp_db import (
    TaskDatabaseError,
    add_dummy_task,
    create_database,
    delete_task,
    format_task_rows,
    get_task_row,
    list_task_rows,
    record_task_output,
    set_task_stars,
    short_text,
)


PROJECT_ROOT = Path(__file__).resolve().parent
SCHEMA_PATH = PROJECT_ROOT / "data" / "tasks.json"


class TaskDatabaseTests(unittest.TestCase):
    def test_create_record_and_filter_rows(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            database_path = Path(temporary_directory) / "tasks.db"
            create_database(database_path, SCHEMA_PATH)
            uid = record_task_output(
                database_path,
                SCHEMA_PATH,
                project="pokus",
                selector="test123",
                task="tasks_flows/task_test.json",
                model="qwen3.5:latest",
                parameters={"seed": 7, "temperature": 0.2},
                prompt="A prompt with several words.",
                instruction="Keep it short.",
                answer="A final answer.",
            )
            record_task_output(
                database_path,
                SCHEMA_PATH,
                project="other",
                selector="other",
                task="tasks_flows/task_test.json",
                model="qwen3.5:latest",
                parameters={},
                prompt="Other prompt.",
                instruction=None,
                answer="Other answer.",
            )
            rows = list_task_rows(database_path, "pokus", "test123")
            record = get_task_row(database_path, uid)

        self.assertEqual(len(rows), 1)
        self.assertEqual(uid, 1)
        self.assertEqual(rows[0]["uid"], uid)
        self.assertEqual(rows[0]["project"], "pokus")
        self.assertEqual(rows[0]["selector"], "test123")
        self.assertEqual(rows[0]["answer"], "A final answer.")
        self.assertIn('"temperature": 0.2', rows[0]["parameters"])

        self.assertIsNotNone(record)
        assert record is not None
        self.assertEqual(record["instruction"], "Keep it short.")

    def test_short_output_is_single_line_and_bounded(self) -> None:
        self.assertEqual(short_text("a\n  b\t c", 20), "a b c")
        self.assertEqual(short_text("abcdefghijkl", 8), "abcdefg…")
        rendered = format_task_rows([])
        self.assertEqual(rendered, ["id    | project              | selector   | model                | prompt               | answer              "])

    def test_missing_database_has_a_clear_error(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            with self.assertRaises(TaskDatabaseError):
                list_task_rows(Path(temporary_directory) / "missing.db")

    def test_dummy_record_can_be_deleted(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            database_path = Path(temporary_directory) / "tasks.db"
            uid = add_dummy_task(database_path, SCHEMA_PATH, "pokus", "test123")
            rows = list_task_rows(database_path, "pokus", "test123")
            deleted = delete_task(database_path, uid)
            deleted_again = delete_task(database_path, uid)

        self.assertEqual(len(rows), 1)
        self.assertEqual(uid, 1)
        self.assertEqual(rows[0]["task"], "dummy test")
        self.assertEqual(rows[0]["selector"], "test123")
        self.assertEqual(rows[0]["model"], "")
        self.assertEqual(rows[0]["answer"], "")
        self.assertTrue(deleted)
        self.assertFalse(deleted_again)

    def test_stars_can_be_set_for_one_existing_record(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            database_path = Path(temporary_directory) / "tasks.db"
            uid = add_dummy_task(database_path, SCHEMA_PATH, "pokus", "test123")
            updated = set_task_stars(database_path, uid, 3)
            row = get_task_row(database_path, uid)
            matching_rows = list_task_rows(database_path, stars=3)
            missing = set_task_stars(database_path, 999, 3)

        self.assertTrue(updated)
        self.assertIsNotNone(row)
        assert row is not None
        self.assertEqual(row["stars"], 3)
        self.assertEqual([matching_row["uid"] for matching_row in matching_rows], [uid])
        self.assertFalse(missing)


if __name__ == "__main__":
    unittest.main()
