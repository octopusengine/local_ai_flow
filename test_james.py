"""Tests for James database-record rendering."""

from contextlib import redirect_stdout
from datetime import date, timedelta
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

    def test_database_record_left_and_right_arrows_move_between_records(self) -> None:
        rows = [
            {"uid": index, "project": "p", "selector": "s", "task": "t", "model": "m", "answer": "a"}
            for index in (1, 2, 3)
        ]

        with redirect_stdout(StringIO()):
            with (
                patch.object(james, "clear_screen"),
                patch.object(james, "read_key", side_effect=["left", " "]),
            ):
                self.assertEqual(james.render_database_record(rows, 1, 80), 0)
            with (
                patch.object(james, "clear_screen"),
                patch.object(james, "read_key", side_effect=["right", " "]),
            ):
                self.assertEqual(james.render_database_record(rows, 1, 80), 2)


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


class JamesMenuTests(unittest.TestCase):
    def test_configuration_is_loaded_from_james_directory(self) -> None:
        config = james.load_james_config()

        self.assertEqual(james.JAMES_CONFIG_PATH, james.PROJECT_ROOT / "james" / "james.json")
        self.assertEqual(
            set(james.FLOW_CATEGORY_KEYS),
            {"flows_test", "flows_single", "flows_code", "flows_batch", "flows_media", "flows_mcp"},
        )
        self.assertIn("flow_batch_ocr.txt", config["flows_batch"])

    def test_main_menu_renders_requested_three_by_three_shortcuts(self) -> None:
        config = james.load_james_config()
        output = StringIO()

        with (
            patch.object(james, "clear_screen"),
            patch.object(james, "load_project_config", return_value={"subdir": "project_example"}),
            redirect_stdout(output),
        ):
            james.render_main_menu(config)

        rendered = output.getvalue().casefold()
        for label in ("chat", "mcp", "about", "flow", "rag", "setup", "database", "cowork", "help"):
            self.assertIn(label, rendered)

    def test_flow_cursor_opens_selected_batch_list(self) -> None:
        config = james.load_james_config()

        with (
            patch.object(james, "render_flow_menu"),
            patch.object(james, "flow_list_menu") as flow_list_menu,
            patch.object(james, "read_key", side_effect=["down", "down", "down", "\r", " "]),
        ):
            james.flow_menu(config)

        flow_list_menu.assert_called_once_with(config, "flows_batch", "BATCH")

    def test_flow_list_cursor_runs_selected_flow_and_space_returns(self) -> None:
        config = james.load_james_config()

        with (
            patch.object(james, "render_flow_list_menu") as render_flow_list_menu,
            patch.object(james, "run_flow") as run_flow,
            patch.object(james, "read_key", side_effect=["down", "\r", " "]),
        ):
            james.flow_list_menu(config, "flows_test", "TEST")

        self.assertEqual(render_flow_list_menu.call_args_list[0].args[-1], 0)
        self.assertEqual(render_flow_list_menu.call_args_list[1].args[-1], 1)
        run_flow.assert_called_once_with("flow_base.txt")

    def test_back_footer_mentions_space(self) -> None:
        output = StringIO()

        with redirect_stdout(output):
            james.render_back_footer(40)

        self.assertIn("Space", output.getvalue())

    def test_setup_cursor_opens_ollama_configuration(self) -> None:
        config = james.load_james_config()

        with (
            patch.object(james, "render_setup_menu") as render_setup_menu,
            patch.object(james, "show_text_document") as show_text_document,
            patch.object(james, "read_key", side_effect=["down", "down", "\r", " "]),
        ):
            james.setup_menu(config)

        self.assertEqual(render_setup_menu.call_args_list[0].args[-1], 0)
        self.assertEqual(render_setup_menu.call_args_list[2].args[-1], 2)
        show_text_document.assert_called_once_with(config, james.OLLAMA_CONFIG_PATH, "OLLAMA")

    def test_database_cursor_runs_selected_show_action(self) -> None:
        config = james.load_james_config()

        with (
            patch.object(james, "read_database_summary", return_value=["1 task"]),
            patch.object(james, "render_database_menu") as render_database_menu,
            patch.object(james, "read_task_id", return_value=42),
            patch.object(james, "run_database_action") as run_database_action,
            patch.object(james, "read_key", side_effect=["down", "\r", " "]),
        ):
            james.database_menu(config)

        self.assertEqual(render_database_menu.call_args_list[0].args[1], 0)
        self.assertEqual(render_database_menu.call_args_list[1].args[1], 1)
        run_database_action.assert_called_once_with(config, ["--show", "42"])

    def test_filter_values_include_aligned_record_counts(self) -> None:
        config = james.load_james_config()
        rows = [
            {"project": "alpha", "selector": "batch", "task": "task", "model": "model", "stars": 3},
            {"project": "alpha", "selector": "batch", "task": "task", "model": "model", "stars": 3},
            {"project": "beta", "selector": "", "task": "task", "model": "model", "stars": 1},
        ]
        output = StringIO()

        with patch.object(james, "list_task_rows", return_value=rows):
            values = james.filter_value_groups(config, "project")
        with patch.object(james, "clear_screen"), redirect_stdout(output):
            james.render_filter_value_picker("project", values, 0, 60, 15)

        self.assertEqual(values, [("alpha", 2), ("beta", 1)])
        self.assertIn("      2  alpha", output.getvalue())
        self.assertNotIn("1. alpha", output.getvalue())

    def test_last_week_lists_seven_days_with_today_first(self) -> None:
        config = james.load_james_config()
        today = date.today()
        rows = [
            {"datetime": f"{today}T10:00:00+00:00"},
            {"datetime": f"{today - timedelta(days=1)}T10:00:00+00:00"},
            {"datetime": f"{today - timedelta(days=7)}T10:00:00+00:00"},
        ]

        with patch.object(james, "list_task_rows", return_value=rows):
            values = james.filter_value_groups(config, "last_week")

        self.assertEqual(len(values), 7)
        self.assertEqual(values[0], (str(today), 1))
        self.assertEqual(values[1], (str(today - timedelta(days=1)), 1))
        self.assertNotIn(str(today - timedelta(days=7)), dict(values))

    def test_last_week_selection_filters_by_datetime_prefix(self) -> None:
        config = james.load_james_config()

        with (
            patch.object(james, "render_database_filter_menu"),
            patch.object(james, "pick_filter_value", return_value="2026-08-23"),
            patch.object(james, "browse_database_records") as browse_database_records,
            patch.object(james, "read_key", side_effect=["down"] * 6 + ["\r"]),
        ):
            james.database_filter_menu(config)

        browse_database_records.assert_called_once_with(config, datetime_prefix="2026-08-23")

    def test_about_document_has_its_requested_path(self) -> None:
        self.assertEqual(james.JAMES_ABOUT_PATH, james.PROJECT_ROOT / "james" / "about.md")
        self.assertTrue(james.JAMES_ABOUT_PATH.is_file())

    def test_mcp_configuration_path_is_available(self) -> None:
        self.assertEqual(james.MCP_CONFIG_PATH, james.PROJECT_ROOT / "mcp" / "mcp_config.json")
        self.assertTrue(james.MCP_CONFIG_PATH.is_file())

    def test_help_uses_the_james_help_document(self) -> None:
        config = james.load_james_config()

        with patch.object(james, "show_text_document") as show_text_document:
            james.show_help(config)

        show_text_document.assert_called_once_with(config, james.JAMES_HELP_PATH, "HELP")


if __name__ == "__main__":
    unittest.main()
