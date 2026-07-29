"""Tests for interactive completed-task record navigation."""

from __future__ import annotations

from pathlib import Path
import sys
import unittest
from unittest.mock import patch

import cli_db
from lib.wrapp_db import TaskDatabaseError


class CliDatabaseTests(unittest.TestCase):
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
            (["cli_db.py", "-m", "db2.db"], "merge_database", "db2.db"),
            (["cli_db.py", "-e", "123"], "export_uid", 123),
            (
                ["cli_db.py", "db2.db", "-e", "--ID", "123", "--out", "answer.txt"],
                "export_uid",
                123,
            ),
        )

        for argv, attribute, expected in cases:
            with self.subTest(argv=argv), patch.object(sys, "argv", argv):
                arguments = cli_db.parse_arguments()
            self.assertEqual(getattr(arguments, attribute), expected)


if __name__ == "__main__":
    unittest.main()
