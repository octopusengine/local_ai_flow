"""Tests for James database-record rendering."""

from contextlib import redirect_stdout
from io import StringIO
import unittest
from unittest.mock import patch

import james


class JamesDatabaseRecordTests(unittest.TestCase):
    def test_database_record_footer_repeats_identity_fields(self) -> None:
        row = {
            "uid": 42,
            "project": "project_example",
            "selector": "batch_ocr",
            "task": "\\task_ocr",
            "model": "deepseek-ocr:3b",
            "answer": "Long answer",
        }
        output = StringIO()

        with (
            patch.object(james, "clear_screen"),
            patch.object(james, "read_key", return_value="b"),
            redirect_stdout(output),
        ):
            self.assertEqual(james.render_database_record([row], 0, 80), 0)

        self.assertIn(
            "UID: 42 | P: project_example | S: batch_ocr | T: \\task_ocr | M: deepseek-ocr:3b",
            output.getvalue(),
        )


class JamesChatCommandTests(unittest.TestCase):
    def test_catalog_modifier_is_forwarded_to_chat_flow(self) -> None:
        prompt, commands = james.extract_chat_sc_command("/eli5 Explain gravity.")

        self.assertEqual(prompt, "Explain gravity.")
        self.assertEqual(commands, ["eli5"])

    def test_catalog_action_and_alias_are_forwarded_to_chat_flow(self) -> None:
        prompt, commands = james.extract_chat_sc_command("/rowto bake bread")

        self.assertEqual(prompt, "bake bread")
        self.assertEqual(commands, ["howto"])

    def test_unknown_leading_slash_text_remains_a_normal_message(self) -> None:
        prompt, commands = james.extract_chat_sc_command("/not-a-command explain this")

        self.assertEqual(prompt, "/not-a-command explain this")
        self.assertEqual(commands, [])

    def test_chat_forwards_catalog_action_to_runner(self) -> None:
        config = {"chat_model": "test-model", "language": "cz"}

        with (
            patch.object(james, "set_chat_selector", return_value=True),
            patch.object(james, "ensure_chat_context_file"),
            patch.object(james, "clear_screen"),
            patch.object(james, "render_chat_commands"),
            patch.object(james, "write_chat_input"),
            patch.object(james, "append_chat_turn"),
            patch.object(james, "run_flow", return_value=0) as run_flow,
            patch("builtins.input", side_effect=["/plan Make a migration plan", "/bye"]),
        ):
            james.run_chat(config)

        self.assertEqual(run_flow.call_args.kwargs["sc_commands"], ["plan"])


if __name__ == "__main__":
    unittest.main()
