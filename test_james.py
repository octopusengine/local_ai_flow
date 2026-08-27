"""Tests for James database-record rendering."""

from contextlib import redirect_stdout
from datetime import date, timedelta
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

import james
from lib.wrapp_vector import DatabaseProfile


class JamesDatabaseRecordTests(unittest.TestCase):
    def test_database_record_footer_repeats_identity_fields(self) -> None:
        config = james.load_james_config()
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
            self.assertEqual(james.render_database_record(config, [row], 0, 80), 0)

        self.assertIn(
            "UID: 42 | P: project_example | S: batch_ocr | T: \\task_ocr | M: deepseek-ocr:3b",
            output.getvalue(),
        )

    def test_database_record_left_and_right_arrows_move_between_records(self) -> None:
        config = james.load_james_config()
        rows = [
            {"uid": index, "project": "p", "selector": "s", "task": "t", "model": "m", "answer": "a"}
            for index in (1, 2, 3)
        ]

        with redirect_stdout(StringIO()):
            with (
                patch.object(james, "clear_screen"),
                patch.object(james, "read_key", side_effect=["left", " "]),
            ):
                self.assertEqual(james.render_database_record(config, rows, 1, 80), 2)
            with (
                patch.object(james, "clear_screen"),
                patch.object(james, "read_key", side_effect=["right", " "]),
            ):
                self.assertEqual(james.render_database_record(config, rows, 1, 80), 0)

    def test_database_record_deletes_the_current_row_only_after_confirmation(self) -> None:
        config = james.load_james_config()
        rows = [{"uid": 42, "project": "p", "selector": "s", "task": "t", "model": "m", "answer": "a"}]

        with (
            patch.object(james, "clear_screen"),
            patch.object(james, "read_key", return_value="d"),
            patch.object(james, "delete_task", return_value=True) as delete_task,
            patch.object(james, "pause"),
            patch("builtins.input", return_value="yes"),
            redirect_stdout(StringIO()),
        ):
            self.assertEqual(james.render_database_record(config, rows, 0, 80), 0)

        delete_task.assert_called_once_with(james.main_database_file(config), 42)
        self.assertEqual(rows, [])

    def test_database_record_adds_new_answer_using_cli_db_add(self) -> None:
        config = james.load_james_config()
        rows = [{"uid": 42, "project": "p", "selector": "s", "task": "t", "model": "m", "answer": "a"}]

        with (
            patch.object(james, "clear_screen"),
            patch.object(james, "read_key", side_effect=["a", "b"]),
            patch.object(james, "run_database_action") as run_database_action,
            patch("builtins.input", return_value="Nový obsah"),
            redirect_stdout(StringIO()),
        ):
            self.assertEqual(james.render_database_record(config, rows, 0, 80), 0)

        run_database_action.assert_called_once_with(config, ["--add", "Nový obsah"])

    def test_database_list_refreshes_after_returning_from_a_record(self) -> None:
        config = james.load_james_config()
        first_rows = [{"uid": 2, "project": "p", "selector": "s", "task": "t", "model": "m", "answer": "old", "stars": 0}]
        refreshed_rows = [*first_rows, {"uid": 3, "project": "p", "selector": "s", "task": "t", "model": "m", "answer": "new", "stars": 0}]

        with (
            patch.object(james, "list_task_rows", side_effect=[first_rows, refreshed_rows]) as list_task_rows,
            patch.object(james, "render_database_browser"),
            patch.object(james, "render_database_record", return_value=0),
            patch.object(james, "read_key", side_effect=["\r", " "]),
        ):
            james.browse_database_records(config)

        self.assertEqual(list_task_rows.call_count, 2)


class JamesChatCommandTests(unittest.TestCase):
    def test_chat_command_header_shows_internal_and_catalog_shortcuts(self) -> None:
        output = StringIO()

        with redirect_stdout(output):
            james.render_chat_commands()

        rendered = output.getvalue()
        self.assertIn("/hlp help chat commands", rendered)
        self.assertIn("/add FILE attach a project file", rendered)
        self.assertIn("/sum save context summary", rendered)
        self.assertIn("/COMMAND message use any command from sc.json", rendered)
        self.assertNotIn("/bye return to menu", rendered)

    def test_chat_help_renders_bold_markdown_without_markers(self) -> None:
        output = StringIO()

        with redirect_stdout(output):
            james.render_chat_help(james.load_james_config())

        rendered = output.getvalue()
        self.assertIn("/hlp show this help", rendered)
        self.assertIn("/COMMAND message use any command from sc.json", rendered)
        self.assertNotIn("**", rendered)

    def test_bold_markdown_uses_the_configured_color_while_plain_text_is_preserved(self) -> None:
        terminal = Mock()
        terminal.color.side_effect = lambda color, text: f"<{color}>{text}</{color}>"

        rendered = james.render_bold_markdown("Use **/hlp** for help.", terminal, bold_color="cyan")

        self.assertEqual(rendered, "Use <cyan>/hlp</cyan> for help.")
        terminal.color.assert_called_once_with("cyan", "/hlp")

    def test_chat_help_command_does_not_run_the_model(self) -> None:
        config = {"chat_model": "test-model", "language": "cz"}

        with (
            patch.object(james, "set_chat_selector", return_value=True),
            patch.object(james, "ensure_chat_context_file"),
            patch.object(james, "clear_screen"),
            patch.object(james, "render_page_header"),
            patch.object(james, "render_chat_commands"),
            patch.object(james, "render_chat_help") as render_chat_help,
            patch.object(james, "run_flow") as run_flow,
            patch("builtins.input", side_effect=["/hlp", "/bye"]),
        ):
            james.run_chat(config)

        render_chat_help.assert_called_once_with(config)
        run_flow.assert_not_called()

    def test_url_command_accepts_a_plain_or_markdown_http_url(self) -> None:
        self.assertEqual(
            james.extract_chat_url_command("/url https://www.agamapoint.com/bitcoin"),
            "https://www.agamapoint.com/bitcoin",
        )
        self.assertEqual(
            james.extract_chat_url_command("/url [Bitcoin](https://www.agamapoint.com/bitcoin)"),
            "https://www.agamapoint.com/bitcoin",
        )

    def test_url_command_rejects_missing_and_non_http_urls(self) -> None:
        with self.assertRaisesRegex(ValueError, "http"):
            james.extract_chat_url_command("/url")
        with self.assertRaisesRegex(ValueError, "http"):
            james.extract_chat_url_command("/url file:///C:/secret.txt")

    def test_url_fetch_strips_markup_and_ignores_scripts(self) -> None:
        response = Mock()
        response.headers = {"Content-Type": "text/html", "Content-Length": "200"}
        response.content = b"<html></html>"
        response.text = (
            "<html><head><title>Test page</title><script>ignore()</script></head>"
            "<body><h1>Hello</h1><p>Useful <b>text</b>.</p></body></html>"
        )

        with patch.object(james.requests, "get", return_value=response):
            title, text = james.fetch_chat_url_text("https://example.test/page")

        self.assertEqual(title, "Test page")
        self.assertEqual(text, "Hello\nUseful text.")

    def test_url_context_is_preserved_when_a_chat_turn_is_added(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            project_directory = Path(temporary_directory)
            config = {"chat_context_turns": 6}
            (project_directory / james.CHAT_CONTEXT_FILENAME).write_text(james.CHAT_INITIAL_CONTEXT, encoding="utf-8")
            (project_directory / james.CHAT_REPLY_FILENAME).write_text("Answer", encoding="utf-8")
            with patch.object(james, "active_project_directory", return_value=project_directory):
                james.append_chat_url_context(config, "https://example.test", "Example", "Reference text")
                james.append_chat_turn(config, "Question")

            context = (project_directory / james.CHAT_CONTEXT_FILENAME).read_text(encoding="utf-8")
            self.assertIn("URL: https://example.test", context)
            self.assertIn("Reference text", context)
            self.assertIn("## Conversation", context)
            self.assertIn("- user:\n  Question", context)
            self.assertIn("- assistant:\n  Answer", context)

    def test_add_command_appends_a_project_text_file_to_context(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            project_directory = Path(temporary_directory)
            config = {"chat_context_turns": 6}
            (project_directory / "notes.txt").write_text("Important project notes", encoding="utf-8")
            with patch.object(james, "active_project_directory", return_value=project_directory):
                file_path, character_count = james.append_chat_file_context(config, "notes.txt")

            context = (project_directory / james.CHAT_CONTEXT_FILENAME).read_text(encoding="utf-8")
            self.assertEqual(file_path, (project_directory / "notes.txt").resolve())
            self.assertEqual(character_count, len("Important project notes"))
            self.assertIn("## File source\nPath: notes.txt", context)
            self.assertIn("Important project notes", context)

    def test_add_command_rejects_paths_outside_the_project(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            project_directory = Path(temporary_directory)
            config = {"chat_context_turns": 6}
            with patch.object(james, "active_project_directory", return_value=project_directory):
                with self.assertRaisesRegex(ValueError, "outside"):
                    james.append_chat_file_context(config, "../secret.txt")

    def test_sum_command_writes_the_latest_reply_to_summary_file(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            project_directory = Path(temporary_directory)
            (project_directory / james.CHAT_REPLY_FILENAME).write_text("## Summary\nImportant facts", encoding="utf-8")
            with patch.object(james, "active_project_directory", return_value=project_directory):
                summary_path = james.save_chat_summary({})

            self.assertEqual(summary_path, project_directory / james.CHAT_SUMMARY_FILENAME)
            self.assertEqual(summary_path.read_text(encoding="utf-8"), "## Summary\nImportant facts\n")

    def test_sum_prompt_uses_configured_language(self) -> None:
        self.assertIn("Shrň", james.chat_summary_prompt("cz"))
        self.assertIn("Summarize", james.chat_summary_prompt("en"))

    def test_sum_command_uses_the_active_model_and_does_not_append_a_turn(self) -> None:
        config = {"chat_model": "default-model", "language": "cz"}

        with (
            patch.object(james, "set_chat_selector", return_value=True),
            patch.object(james, "ensure_chat_context_file"),
            patch.object(james, "clear_screen"),
            patch.object(james, "render_page_header"),
            patch.object(james, "render_chat_commands"),
            patch.object(james, "write_chat_input") as write_chat_input,
            patch.object(james, "run_flow", return_value=0) as run_flow,
            patch.object(james, "save_chat_summary") as save_chat_summary,
            patch.object(james, "append_chat_turn") as append_chat_turn,
            patch("builtins.input", side_effect=["/mod current-model", "/sum", "/bye"]),
        ):
            james.run_chat(config)

        write_chat_input.assert_called_once_with(config, james.chat_summary_prompt("cz"))
        self.assertEqual(run_flow.call_args.kwargs["model_override"], "current-model")
        save_chat_summary.assert_called_once_with(config)
        append_chat_turn.assert_not_called()

    def test_chat_url_command_adds_context_without_running_the_model(self) -> None:
        config = {"chat_model": "test-model", "language": "cz"}

        with (
            patch.object(james, "set_chat_selector", return_value=True),
            patch.object(james, "ensure_chat_context_file"),
            patch.object(james, "clear_screen"),
            patch.object(james, "render_page_header"),
            patch.object(james, "render_chat_commands"),
            patch.object(james, "fetch_chat_url_text", return_value=("Example", "Reference text")),
            patch.object(james, "append_chat_url_context") as append_context,
            patch.object(james, "run_flow") as run_flow,
            patch("builtins.input", side_effect=["/url https://example.test", "/bye"]),
        ):
            james.run_chat(config)

        append_context.assert_called_once_with(
            config,
            "https://example.test",
            "Example",
            "Reference text",
        )
        run_flow.assert_not_called()

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
            patch.object(james, "render_page_header"),
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
            {"flows_test", "flows_single", "flows_code", "flows_batch", "flows_media", "flows_mcp", "flows_rag_wiki"},
        )
        self.assertIn("flow_batch_ocr.txt", config["flows_batch"])
        self.assertEqual(
            config["flows_rag_wiki"],
            [
                "flow_rag_test.txt",
                "flow_rag_btc.txt",
                "flow_vector_btc.txt",
                "flow_vector_btc2.txt",
                "flow_vector_btc_cz.txt",
                "flow_vector_word.txt",
                "flow_vector_word_cz.txt",
            ],
        )
        self.assertEqual(config["colors"]["col_bold"], "yellow")

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
        self.assertIn("jam3$-01 - v0.2.2 | project: project_example | menu", rendered)
        self.assertIn(" project_example | cz |", rendered)
        self.assertLess(
            output.getvalue().index(" project_example | cz |"),
            output.getvalue().index("-" * int(config["width"])),
        )
        menu_lines = [line for line in output.getvalue().splitlines() if "|" in line and "chat" in line.casefold()]
        self.assertEqual(len(menu_lines), 1)
        self.assertEqual(menu_lines[0].count("|"), 3)
        self.assertIn("v0.2", menu_lines[0])
        self.assertEqual(len(menu_lines[0]), int(config["width"]))

    def test_section_header_uses_one_line_at_the_configured_width(self) -> None:
        output = StringIO()

        with redirect_stdout(output):
            james.render_section_header(65, "database")

        rendered = output.getvalue().rstrip("\n")
        self.assertEqual(rendered, "--- [ DATABASE ] " + "-" * 48)
        self.assertEqual(len(rendered), 65)

    def test_section_header_uses_the_configured_heading_color(self) -> None:
        terminal = Mock()
        terminal.color.side_effect = lambda _color, text: text
        terminal.style.side_effect = lambda text, **_kwargs: text
        config = {"colors": {"col_head": "cyan"}}

        with patch.object(james, "Terminal", return_value=terminal), redirect_stdout(StringIO()):
            james.render_section_header(30, "database", config)

        terminal.style.assert_called_once_with("DATABASE", fg="cyan", bold=True)

    def test_flow_cursor_opens_selected_batch_list(self) -> None:
        config = james.load_james_config()

        with (
            patch.object(james, "render_flow_menu"),
            patch.object(james, "flow_list_menu") as flow_list_menu,
            patch.object(james, "read_key", side_effect=["down", "down", "down", "\r", " "]),
        ):
            james.flow_menu(config)

        flow_list_menu.assert_called_once_with(config, "flows_batch", "BATCH")

    def test_flow_cursor_wraps_from_first_category_to_last(self) -> None:
        config = james.load_james_config()

        with (
            patch.object(james, "render_flow_menu") as render_flow_menu,
            patch.object(james, "flow_list_menu") as flow_list_menu,
            patch.object(james, "read_key", side_effect=["up", "\r", " "]),
        ):
            james.flow_menu(config)

        flow_list_menu.assert_called_once_with(config, "flows_rag_wiki", "RAG_WIKI")
        self.assertEqual(render_flow_menu.call_args_list[1].args[1], 6)

    def test_flow_cursor_wraps_from_last_category_to_first(self) -> None:
        config = james.load_james_config()

        with (
            patch.object(james, "render_flow_menu"),
            patch.object(james, "flow_list_menu") as flow_list_menu,
            patch.object(james, "read_key", side_effect=[*["down"] * 7, "\r", " "]),
        ):
            james.flow_menu(config)

        flow_list_menu.assert_called_once_with(config, "flows_test", "TEST")

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
            patch.object(james, "show_json_document") as show_json_document,
            patch.object(james, "read_key", side_effect=["down", "down", "down", "\r", " "]),
        ):
            james.setup_menu(config)

        self.assertEqual(render_setup_menu.call_args_list[0].args[-1], 0)
        self.assertEqual(render_setup_menu.call_args_list[3].args[-1], 3)
        show_json_document.assert_called_once_with(config, james.OLLAMA_CONFIG_PATH, "OLLAMA")

    def test_setup_cursor_wraps_from_first_option_to_last(self) -> None:
        config = james.load_james_config()

        with (
            patch.object(james, "render_setup_menu") as render_setup_menu,
            patch.object(james, "show_text_document") as show_text_document,
            patch.object(james, "read_key", side_effect=["up", "\r", " "]),
        ):
            james.setup_menu(config)

        self.assertEqual(render_setup_menu.call_args_list[1].args[-1], 5)
        show_text_document.assert_called_once_with(config, james.SC_COMMANDS_CZ_PATH, "SLASH COMMANDS")

    def test_setup_cursor_opens_ollama_models_below_ollama(self) -> None:
        config = james.load_james_config()

        with (
            patch.object(james, "render_setup_menu") as render_setup_menu,
            patch.object(james, "show_ollama_models") as show_ollama_models,
            patch.object(james, "read_key", side_effect=["down", "down", "down", "down", "\r", " "]),
        ):
            james.setup_menu(config)

        self.assertEqual(render_setup_menu.call_args_list[4].args[-1], 4)
        show_ollama_models.assert_called_once_with(config)

    def test_ollama_models_runs_ollama_list(self) -> None:
        config = james.load_james_config()
        completed = type("Completed", (), {"returncode": 0, "stdout": "NAME  ID\nmodel  abc\n", "stderr": ""})()
        output = StringIO()

        with (
            patch.object(james, "clear_screen"),
            patch.object(james, "render_page_header"),
            patch.object(james, "render_section_header"),
            patch.object(james, "wait_for_back"),
            patch.object(james.subprocess, "run", return_value=completed) as run,
            redirect_stdout(output),
        ):
            james.show_ollama_models(config)

        self.assertEqual(run.call_args.args[0], ["ollama", "list"])
        self.assertIn("NAME  ID", output.getvalue())

    def test_setup_slash_commands_uses_language_specific_reference(self) -> None:
        config = james.load_james_config()

        with (
            patch.object(james, "render_setup_menu"),
            patch.object(james, "show_text_document") as show_text_document,
            patch.object(james, "read_key", side_effect=["down"] * 5 + ["\r", " "]),
        ):
            james.setup_menu(config)

        show_text_document.assert_called_once_with(config, james.SC_COMMANDS_CZ_PATH, "SLASH COMMANDS")
        config["language"] = "en"
        self.assertEqual(james.slash_commands_document_path(config), james.SC_COMMANDS_DEFAULT_PATH)

    def test_james_setup_view_omits_flow_lists(self) -> None:
        config = james.load_james_config()
        output = StringIO()

        with patch.object(james, "clear_screen"), patch.object(james, "wait_for_back"), redirect_stdout(output):
            james.show_james_config(config)

        rendered = output.getvalue()
        self.assertIn("chat_model: qwen3.5:latest", rendered)
        self.assertIn("col_bold: yellow", rendered)
        self.assertNotIn("flows_test:", rendered)

    def test_project_setup_view_renders_parsed_key_value_rows(self) -> None:
        config = james.load_james_config()
        output = StringIO()

        with (
            patch.object(james, "clear_screen"),
            patch.object(james, "load_project_config", return_value={"subdir": "project_example", "debug": True}),
            patch.object(james, "wait_for_back"),
            redirect_stdout(output),
        ):
            james.show_project_config(config)

        rendered = output.getvalue()
        self.assertIn("subdir: project_example", rendered)
        self.assertIn("debug: true", rendered)
        self.assertNotIn('"subdir"', rendered)

    def test_database_cursor_opens_filter_as_the_second_action(self) -> None:
        config = james.load_james_config()

        with (
            patch.object(james, "read_database_summary", return_value=["1 task"]),
            patch.object(james, "render_database_menu") as render_database_menu,
            patch.object(james, "database_filter_menu") as database_filter_menu,
            patch.object(james, "read_key", side_effect=["down", "\r", " "]),
        ):
            james.database_menu(config)

        self.assertEqual(render_database_menu.call_args_list[0].args[1], 0)
        self.assertEqual(render_database_menu.call_args_list[1].args[1], 1)
        database_filter_menu.assert_called_once_with(config)

    def test_clone_uses_selected_selector_and_a_new_data_database_name(self) -> None:
        config = james.load_james_config()

        with (
            patch.object(james, "pick_filter_value", return_value="rag_btc"),
            patch.object(james, "run_database_action") as run_database_action,
            patch("builtins.input", return_value="rag_btc_copy"),
        ):
            james.clone_database_by_selector(config)

        run_database_action.assert_called_once_with(
            config, ["--selector", "rag_btc", "--clone", "data/rag_btc_copy.db"]
        )

    def test_clone_stars_uses_clone_stars_with_a_new_data_database_name(self) -> None:
        config = james.load_james_config()

        with (
            patch.object(james, "run_database_action") as run_database_action,
            patch("builtins.input", return_value="starred_copy"),
        ):
            james.clone_database_by_stars(config)

        run_database_action.assert_called_once_with(config, ["--clone-stars", "data/starred_copy.db"])

    def test_clone_menu_opens_selector_and_starred_paths(self) -> None:
        config = james.load_james_config()

        with (
            patch.object(james, "render_clone_menu"),
            patch.object(james, "clone_database_by_selector") as by_selector,
            patch.object(james, "clone_database_by_stars") as by_stars,
            patch.object(james, "read_key", side_effect=["\r", "down", "\r", " "]),
        ):
            james.clone_database(config)

        by_selector.assert_called_once_with(config)
        by_stars.assert_called_once_with(config)

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
            james.render_filter_value_picker(config, "project", values, 0, 60, 15)

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

    def test_mcp_menu_opens_its_three_actions_with_cursor_selection(self) -> None:
        config = james.load_james_config()

        with (
            patch.object(james, "render_mcp_menu"),
            patch.object(james, "run_mcp_server") as run_mcp_server,
            patch.object(james, "list_mcp_services") as list_mcp_services,
            patch.object(james, "show_text_document") as show_text_document,
            patch.object(james, "read_key", side_effect=["\r", "down", "\r", "down", "\r", " "]),
        ):
            james.mcp_menu(config)

        run_mcp_server.assert_called_once_with(config)
        list_mcp_services.assert_called_once_with(config)
        show_text_document.assert_called_once_with(config, james.MCP_CONFIG_PATH, "MCP · SETUP")

    def test_mcp_cursor_wraps_from_first_action_to_last(self) -> None:
        config = james.load_james_config()

        with (
            patch.object(james, "render_mcp_menu") as render_mcp_menu,
            patch.object(james, "show_text_document") as show_text_document,
            patch.object(james, "read_key", side_effect=["up", "\r", " "]),
        ):
            james.mcp_menu(config)

        self.assertEqual(render_mcp_menu.call_args_list[1].args[1], 2)
        show_text_document.assert_called_once_with(config, james.MCP_CONFIG_PATH, "MCP · SETUP")

    def test_run_mcp_server_starts_the_configured_server_and_reports_its_endpoint(self) -> None:
        config = james.load_james_config()
        server = type("Server", (), {"pid": 1234})()

        with (
            patch.object(james, "clear_screen"),
            patch.object(james, "render_page_header"),
            patch.object(james, "mcp_endpoint", return_value=("127.0.0.1", 8000, "/mcp")),
            patch.object(james, "mcp_port_is_open", return_value=False),
            patch.object(james.subprocess, "Popen", return_value=server) as popen,
            patch.object(james, "pause"),
        ):
            james.run_mcp_server(config)

        self.assertEqual(popen.call_args.args[0], [james.sys.executable, str(james.MCP_SERVER_PATH)])

    def test_list_mcp_services_uses_the_cli_list_command(self) -> None:
        config = james.load_james_config()
        completed = type("Completed", (), {"returncode": 0})()

        with (
            patch.object(james, "clear_screen"),
            patch.object(james, "render_page_header"),
            patch.object(james, "mcp_endpoint", return_value=("127.0.0.1", 8000, "/mcp")),
            patch.object(james, "mcp_port_is_open", return_value=True),
            patch.object(james.subprocess, "run", return_value=completed) as run,
            patch.object(james, "pause"),
        ):
            james.list_mcp_services(config)

        self.assertEqual(run.call_args.args[0], [james.sys.executable, str(james.MCP_SCRIPT_PATH), "--list", "--connect-local"])

    def test_help_uses_the_james_help_document(self) -> None:
        config = james.load_james_config()

        with patch.object(james, "show_text_document") as show_text_document:
            james.show_help(config)

        show_text_document.assert_called_once_with(config, james.JAMES_HELP_PATH, "HELP")

    def test_rag_menu_opens_vector_and_database_catalogs(self) -> None:
        config = james.load_james_config()

        with (
            patch.object(james, "render_rag_menu"),
            patch.object(james, "show_text_document") as show_text_document,
            patch.object(james, "read_key", side_effect=["down", "\r", "down", "\r", " "]),
        ):
            james.rag_menu(config)

        self.assertEqual(
            show_text_document.call_args_list,
            [
                ((config, james.VECTOR_CONFIG_PATH, "RAG · CLI VECTOR"), {}),
                ((config, james.VECTOR_DATABASES_PATH, "RAG · DATABASES"), {}),
            ],
        )

    def test_rag_menu_starts_with_cursor_selected_ingest(self) -> None:
        config = james.load_james_config()

        with (
            patch.object(james, "render_rag_menu") as render_rag_menu,
            patch.object(james, "ingest_new_wiki") as ingest_new_wiki,
            patch.object(james, "read_key", side_effect=["\r", " "]),
        ):
            james.rag_menu(config)

        self.assertEqual(render_rag_menu.call_args_list[0].args[-1], 0)
        ingest_new_wiki.assert_called_once_with(config)

    def test_rag_cursor_wraps_from_first_action_to_last(self) -> None:
        config = james.load_james_config()

        with (
            patch.object(james, "render_rag_menu") as render_rag_menu,
            patch.object(james, "show_rag_data_tree") as show_rag_data_tree,
            patch.object(james, "read_key", side_effect=["up", "\r", " "]),
        ):
            james.rag_menu(config)

        self.assertEqual(render_rag_menu.call_args_list[1].args[1], 3)
        show_rag_data_tree.assert_called_once_with(config)

    def test_rag_menu_opens_data_tree(self) -> None:
        config = james.load_james_config()

        with (
            patch.object(james, "render_rag_menu"),
            patch.object(james, "show_rag_data_tree") as show_rag_data_tree,
            patch.object(james, "read_key", side_effect=["down", "down", "down", "\r", " "]),
        ):
            james.rag_menu(config)

        show_rag_data_tree.assert_called_once_with(config)

    def test_rag_ingest_existing_profile_offers_overwrite_choice(self) -> None:
        config = james.load_james_config()
        profile = DatabaseProfile("btc", Path("wiki_btc.db"), "btc")
        completed = type("Completed", (), {"returncode": 0})()

        with (
            patch.object(james, "clear_screen"),
            patch.object(james, "render_page_header"),
            patch.object(james, "load_vector_config", return_value=({}, {"btc": profile})),
            patch.object(james, "new_database_profile", return_value=profile),
            patch.object(james.subprocess, "run", return_value=completed) as run,
            patch.object(james, "pause"),
            patch("builtins.input", side_effect=["btc", "o"]),
        ):
            james.ingest_new_wiki(config)

        self.assertEqual(run.call_args.args[0][-4:], ["ingest-wiki", "btc", "--embed", "--overwrite"])


if __name__ == "__main__":
    unittest.main()
