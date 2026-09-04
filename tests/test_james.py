"""Tests for James database-record rendering."""

from contextlib import redirect_stdout
from datetime import date, timedelta
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, call, patch

import james
from lib import wrapp_md
from lib.wrapp_vector import DatabaseProfile


class JamesDatabaseRecordTests(unittest.TestCase):
    def test_ensure_main_database_creates_an_empty_database_for_a_new_clone(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            project_root = Path(temporary_directory)
            data_directory = project_root / "data"
            data_directory.mkdir()
            (data_directory / "tasks.json").write_text(
                (james.PROJECT_ROOT / "data" / "tasks.json").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            config = {"main_db": "data/tasks.db"}
            with patch.object(james, "PROJECT_ROOT", project_root):
                database_path = james.ensure_main_database(config)
                rows = james.list_task_rows(database_path)
                created = database_path.is_file()

        self.assertEqual(database_path.name, "tasks.db")
        self.assertTrue(created)
        self.assertEqual(rows, [])

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
        self.assertIn("/cmd show slash-command catalog", rendered)
        self.assertIn("/bye quit chat", rendered)
        self.assertIn("/COMMAND [/MODIFIER ...] [message] use a command plus compatible modifiers", rendered)
        self.assertNotIn("/add FILE", rendered)

    def test_chat_help_renders_markdown_without_markers(self) -> None:
        output = StringIO()

        with redirect_stdout(output):
            james.render_chat_help(james.load_james_config())

        rendered = output.getvalue()
        self.assertIn("/hlp show this help", rendered)
        self.assertIn("/cmd show the localized slash-command catalog", rendered)
        self.assertIn("/cam [FILE] capture an image from the camera", rendered)
        self.assertIn("/lng list available Chat languages", rendered)
        self.assertIn("/proj show parsed, color-rendered project.json", rendered)
        self.assertIn("/ocr [FILE] run OCR on", rendered)
        self.assertIn("/src list the attached context sources", rendered)
        self.assertIn("/find TEXT find matching text", rendered)
        self.assertIn("/files or /ls list files in the active project", rendered)
        self.assertIn("/cat show the main chat_context.txt", rendered)
        self.assertIn("/cat FILE show a UTF-8 text file", rendered)
        self.assertIn("/rec [FILE.mp3] record the default microphone", rendered)
        self.assertIn("/voice or /voi [FILE.mp3] record record.mp3", rendered)
        self.assertIn("/whisper [FILE.mp3] transcribe record.mp3", rendered)
        self.assertIn("/play [FILE.mp3] play record.mp3", rendered)
        self.assertIn('/say "TEXT" speak the quoted text', rendered)
        self.assertIn("/debug [on|off|true|false] show or set chat diagnostics", rendered)
        self.assertIn("/tool --PARAM run cli_tool.py", rendered)
        self.assertIn("camera.png", rendered)
        self.assertIn("/COMMAND [/MODIFIER ...] [message] use one catalog command", rendered)
        self.assertNotIn("**", rendered)
        self.assertNotIn("`", rendered)

    def test_chat_help_uses_the_shared_markdown_renderer(self) -> None:
        config = james.load_james_config()
        with (
            patch.object(
                james,
                "render_markdown_lines",
                side_effect=lambda lines, _config: [f"rendered:{line}" for line in lines],
            ) as render_lines,
            redirect_stdout(StringIO()),
        ):
            james.render_chat_help(config)

        self.assertTrue(any("`camera.png`" in line for call in render_lines.call_args_list for line in call.args[0]))

    def test_cmd_renders_the_localized_catalog_with_the_shared_markdown_renderer(self) -> None:
        config = james.load_james_config()
        with TemporaryDirectory() as temporary_directory:
            document = Path(temporary_directory) / "sc.md"
            document.write_text("# Commands\n- `/md`\n", encoding="utf-8")
            with (
                patch.object(james, "slash_commands_document_path", return_value=document),
                patch.object(
                    james,
                    "render_markdown_lines",
                    side_effect=lambda lines, _config: [f"rendered:{line}" for line in lines],
                ) as render_lines,
                redirect_stdout(StringIO()),
            ):
                james.render_chat_slash_commands(config)

        self.assertEqual(render_lines.call_args.args[0], ["# Commands", "- `/md`"])

    def test_bold_markdown_uses_the_configured_color_while_plain_text_is_preserved(self) -> None:
        terminal = Mock()
        terminal.color.side_effect = lambda color, text: f"<{color}>{text}</{color}>"

        rendered = james.render_bold_markdown("Use **/hlp** for help.", terminal, bold_color="cyan")

        self.assertEqual(rendered, "Use <cyan>/hlp</cyan> for help.")
        terminal.color.assert_called_once_with("cyan", "/hlp")

    def test_markdown_renderer_is_reexported_from_the_dedicated_module(self) -> None:
        self.assertIs(james.render_markdown_line, wrapp_md.render_markdown_line)
        self.assertIs(james.render_markdown_lines, wrapp_md.render_markdown_lines)
        self.assertIs(james.render_bold_markdown, wrapp_md.render_bold_markdown)

    def test_document_markdown_renders_headings_bullets_and_configured_inline_markup(self) -> None:
        terminal = Mock()
        terminal.color.side_effect = lambda color, text: f"<{color}>{text}</{color}>"
        config = {
            "width": 12,
            "colors": {
                "col_bold": "yellow",
                "col_italic": "green",
                "col_code": "bright_blue",
                "col_basic": "cyan",
            },
        }

        rendered = james.render_markdown_line("- **Name** uses *italics* and `code`.", config, terminal)

        self.assertEqual(rendered, "• <yellow>Name</yellow> uses <green>italics</green> and <bright_blue>code</bright_blue>.")
        self.assertEqual(james.render_markdown_line("---", config, terminal), "_" * 12)
        self.assertEqual(james.render_markdown_line("# Main heading", config, terminal), "<bright_magenta>*** Main heading ***</bright_magenta>")
        self.assertEqual(james.render_markdown_line("## Second heading", config, terminal), "<yellow>Second heading</yellow>")
        self.assertEqual(james.render_markdown_line("### Third heading", config, terminal), "<yellow>Third heading</yellow>")
        self.assertEqual(
            james.render_markdown_lines(["```text", "**Literal** `code`", "```"], config, terminal),
            ["<cyan>**Literal** `code`</cyan>"],
        )

    def test_text_document_uses_markdown_renderer_only_for_markdown_files(self) -> None:
        config = james.load_james_config()
        with TemporaryDirectory() as temporary_directory:
            document = Path(temporary_directory) / "about.md"
            document.write_text("- `Chat`\n---\n", encoding="utf-8")
            output = StringIO()
            with (
                patch.object(james, "clear_screen"),
                patch.object(james, "render_page_header"),
                patch.object(james, "render_section_header"),
                patch.object(james, "wait_for_back"),
                patch.object(
                    james,
                    "render_markdown_lines",
                    side_effect=lambda lines, _config: [f"rendered:{line}" for line in lines],
                ) as render_lines,
                redirect_stdout(output),
            ):
                james.show_text_document(config, document, "ABOUT")

        self.assertEqual(render_lines.call_count, 1)
        self.assertEqual(render_lines.call_args.args[0], ["- `Chat`", "---"])
        self.assertIn("rendered:- `Chat`", output.getvalue())

    def test_text_document_routes_json_files_to_the_colored_json_renderer(self) -> None:
        config = james.load_james_config()
        with TemporaryDirectory() as temporary_directory:
            document = Path(temporary_directory) / "setup.json"
            document.write_text('{"enabled": true}\n', encoding="utf-8")
            with patch.object(james, "show_json_document") as show_json_document:
                james.show_text_document(config, document, "SETUP")

        show_json_document.assert_called_once_with(config, document, "SETUP")

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

    def test_cmd_command_does_not_run_the_model(self) -> None:
        config = {"chat_model": "test-model", "language": "cz"}

        with (
            patch.object(james, "set_chat_selector", return_value=True),
            patch.object(james, "ensure_chat_context_file"),
            patch.object(james, "clear_screen"),
            patch.object(james, "render_page_header"),
            patch.object(james, "render_chat_commands"),
            patch.object(james, "render_chat_slash_commands") as render_catalog,
            patch.object(james, "run_flow") as run_flow,
            patch("builtins.input", side_effect=["/cmd", "/bye"]),
        ):
            james.run_chat(config)

        render_catalog.assert_called_once_with(config)
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

    def test_rag_and_chunk_commands_require_valid_arguments(self) -> None:
        self.assertEqual(james.extract_chat_rag_command("/rag BTC"), "btc")
        self.assertEqual(james.extract_chat_rag_command("/rag off"), "off")
        self.assertEqual(
            james.extract_chat_chunk_command("/chunk Co je těžba bitcoinu?"),
            (5, "Co je těžba bitcoinu?"),
        )
        self.assertEqual(
            james.extract_chat_chunk_command("/chunk (hardware wallet)", 5),
            (5, "(hardware wallet)"),
        )
        self.assertEqual(
            james.extract_chat_chunk_command("/chunk #(hardware wallet)", 7),
            (7, "#(hardware wallet)"),
        )
        with self.assertRaisesRegex(ValueError, "/rag DATA"):
            james.extract_chat_rag_command("/rag")
        with self.assertRaisesRegex(ValueError, "Use /chunk FILTER"):
            james.extract_chat_chunk_command("/chunk 0 bitcoin")
        with self.assertRaisesRegex(ValueError, "Use /chunk FILTER"):
            james.extract_chat_chunk_command("/chunk 5 bitcoin")
        self.assertEqual(
            james.extract_chat_ask_command("/ask (bitcoin mining) or (hardware wallet) :: Explain the difference."),
            ("(bitcoin mining) or (hardware wallet)", "Explain the difference."),
        )
        with self.assertRaisesRegex(ValueError, "Use /ask FILTER"):
            james.extract_chat_ask_command("/ask bitcoin mining")

    def test_rag_tags_are_limited_and_become_an_and_fts_query(self) -> None:
        tags, question = james.split_chat_rag_tags(
            "#(těžba bitcoinu) #(bezpečné uchování) Jak uložit bitcoin?"
        )
        self.assertEqual(tags, ["těžba bitcoinu", "bezpečné uchování"])
        self.assertEqual(question, "Jak uložit bitcoin?")
        self.assertEqual(james.chat_rag_tag_query(tags), '"těžba bitcoinu" AND "bezpečné uchování"')
        self.assertEqual(james.split_chat_rag_tags("#(těžba bitcoinu)"), (["těžba bitcoinu"], ""))
        self.assertEqual(
            james.split_chat_rag_tags("bitcoinová peněženka, těžba bitcoinů, těžení"),
            (["bitcoinová peněženka", "těžba bitcoinů", "těžení"], ""),
        )
        self.assertEqual(
            james.split_chat_rag_tags("(bitcoinová peněženka) (těžba bitcoinů) (těžení)"),
            (["bitcoinová peněženka", "těžba bitcoinů", "těžení"], ""),
        )
        boolean_tags, operators, remaining = james.split_chat_rag_filter_expression(
            "(bitcoinová peněženka) or (těžba bitcoinů) and (těžení)"
        )
        self.assertEqual(boolean_tags, ["bitcoinová peněženka", "těžba bitcoinů", "těžení"])
        self.assertEqual(operators, ["OR", "AND"])
        self.assertEqual(remaining, "")
        self.assertEqual(
            james.chat_rag_tag_query(boolean_tags, operators),
            '"bitcoinová peněženka" OR "těžba bitcoinů" AND "těžení"',
        )
        with self.assertRaisesRegex(ValueError, "at most three"):
            james.split_chat_rag_tags("#(one) #(two) #(three) #(four)")

    def test_chat_message_reader_uses_the_standard_input_prompt(self) -> None:
        with patch("builtins.input", return_value="Previous prompt") as read_input:
            self.assertEqual(james.read_chat_message(), "Previous prompt")

        read_input.assert_called_once_with(">? ")

    def test_db_command_requires_a_positive_record_id(self) -> None:
        self.assertEqual(james.extract_chat_db_command("/db 42"), 42)
        self.assertEqual(james.extract_chat_db_command(" /DB 0042 "), 42)
        for message in ("/db", "/db 0", "/db -1", "/db forty-two", "/db 1 2"):
            with self.subTest(message=message), self.assertRaisesRegex(ValueError, "positive database record ID"):
                james.extract_chat_db_command(message)

    def test_db_command_reads_the_same_unformatted_answer_as_cli_db_print(self) -> None:
        config = {"main_db": "data/tasks.db"}
        database_path = Path("C:/example/tasks.db")
        with (
            patch.object(james, "main_database_file", return_value=database_path),
            patch.object(james, "get_task_row", return_value={"answer": "**Saved** answer"}) as get_task_row,
        ):
            answer = james.read_chat_database_answer(config, 42)

        self.assertEqual(answer, "**Saved** answer")
        get_task_row.assert_called_once_with(database_path, 42)

    def test_db_command_sends_the_saved_answer_as_the_user_message(self) -> None:
        config = {"chat_model": "test-model", "language": "cz", "main_db": "data/tasks.db"}
        output = StringIO()
        with (
            patch.object(james, "set_chat_selector", return_value=True),
            patch.object(james, "ensure_chat_context_file"),
            patch.object(james, "clear_screen"),
            patch.object(james, "render_page_header"),
            patch.object(james, "render_chat_commands"),
            patch.object(james, "main_database_file", return_value=Path("C:/example/tasks.db")),
            patch.object(james, "get_task_row", return_value={"answer": "/literal saved answer"}),
            patch.object(james, "write_chat_input") as write_chat_input,
            patch.object(james, "read_chat_active_image", return_value=None),
            patch.object(james, "run_flow", return_value=0) as run_flow,
            patch.object(james, "render_chat_reply"),
            patch.object(james, "append_chat_turn") as append_chat_turn,
            patch("builtins.input", side_effect=["/db 42", "/bye"]),
            redirect_stdout(output),
        ):
            james.run_chat(config)

        self.assertIn("Database answer 42 sent as chat input:", output.getvalue())
        self.assertIn("/literal saved answer", output.getvalue())
        write_chat_input.assert_called_once_with(config, "/literal saved answer")
        self.assertEqual(run_flow.call_args.args[0], "flow_chat_cz.json")
        append_chat_turn.assert_called_once_with(config, "/literal saved answer")

    def test_safe_console_text_replaces_characters_unavailable_in_a_legacy_code_page(self) -> None:
        stream = type("LegacyStream", (), {"encoding": "cp1250"})()

        self.assertEqual(james.safe_console_text("Chunk 𝙗", stream), "Chunk ?")

    def test_rag_preview_centres_and_marks_a_literal_query_word(self) -> None:
        before, matched, after = james.build_rag_demo_preview(
            "Opening material that is not relevant. Bitcoin mining uses specialised hardware and energy.",
            "bitcoin mining",
            50,
        )

        self.assertEqual(matched.casefold(), "bitcoin")
        self.assertTrue(before.startswith("..."))
        self.assertIn("mining", after.casefold())

    def test_rag_distance_queries_include_combined_groups_and_unique_words(self) -> None:
        self.assertEqual(
            james.rag_demo_distance_queries("bitcoin mining, hardware wallet", ["bitcoin mining", "hardware wallet"]),
            [
                ("all", "bitcoin mining hardware wallet"),
                ("group: bitcoin mining", "bitcoin mining"),
                ("group: hardware wallet", "hardware wallet"),
                ("word: bitcoin", "bitcoin"),
                ("word: mining", "mining"),
                ("word: hardware", "hardware"),
                ("word: wallet", "wallet"),
            ],
        )

    def test_rag_distance_bands_highlight_only_close_and_distant_values(self) -> None:
        self.assertEqual(james.rag_demo_distance_color(1.10), "yellow")
        self.assertIsNone(james.rag_demo_distance_color(1.11))
        self.assertIsNone(james.rag_demo_distance_color(1.24))
        self.assertEqual(james.rag_demo_distance_color(1.25), "green")

    def test_cam_and_ocr_commands_use_the_configured_camera_default(self) -> None:
        self.assertEqual(james.extract_chat_cam_command("/cam"), "")
        self.assertEqual(james.extract_chat_ocr_command("/ocr"), "")
        self.assertEqual(james.chat_command_default_file("camera"), "camera.png")

    def test_cam_and_ocr_commands_accept_a_custom_project_file(self) -> None:
        self.assertEqual(james.extract_chat_cam_command("/cam receipt.png"), "receipt.png")
        self.assertEqual(james.extract_chat_ocr_command("/ocr receipt.png"), "receipt.png")

    def test_audio_commands_accept_optional_mp3_filenames(self) -> None:
        self.assertEqual(james.extract_chat_rec_command("/rec"), "")
        self.assertEqual(james.extract_chat_rec_command("/rec interview.mp3"), "interview.mp3")
        self.assertEqual(james.extract_chat_voice_command("/voice"), "")
        self.assertEqual(james.extract_chat_voice_command("/voice interview.mp3"), "interview.mp3")
        self.assertEqual(james.extract_chat_voice_command("/voi interview.mp3"), "interview.mp3")
        self.assertEqual(james.extract_chat_whisper_command("/whisper"), "")
        self.assertEqual(james.extract_chat_whisper_command("/whisper interview.mp3"), "interview.mp3")
        self.assertEqual(james.extract_chat_play_command("/play"), "")
        self.assertEqual(james.extract_chat_play_command("/play audio/interview.mp3"), "audio/interview.mp3")

    def test_say_command_selects_text_file_or_the_latest_reply(self) -> None:
        self.assertEqual(james.extract_chat_say_command("/say"), ("last", ""))
        self.assertEqual(james.extract_chat_say_command('/say "Hello world."'), ("text", "Hello world."))
        self.assertEqual(james.extract_chat_say_command("/say notes.txt"), ("file", "notes.txt"))
        with self.assertRaisesRegex(ValueError, "Use /say"):
            james.extract_chat_say_command('/say "missing end')

    def test_markdown_cleanup_for_speech_keeps_only_spoken_text(self) -> None:
        self.assertEqual(
            james.clean_markdown_for_speech(
                "# Result\n\n- **Hello** `world`\n- [Read more](https://example.test)\n\n---\n"
            ),
            "Result\nHello world\nRead more",
        )

    def test_transcript_body_excludes_whisper_metadata(self) -> None:
        self.assertEqual(
            james.extract_transcript_body(
                "Source file: record.mp3\nWhisper language: cs\n\nProč jsou rostliny zelené?\n"
            ),
            "Proč jsou rostliny zelené?",
        )

    def test_chat_say_uses_the_active_language_and_piped_text(self) -> None:
        completed = type("Completed", (), {"returncode": 0, "stdout": "", "stderr": ""})()
        with patch.object(james.subprocess, "run", return_value=completed) as run:
            james.run_chat_say("Hello world.", "en", debug=False)

        self.assertEqual(
            run.call_args.args[0],
            [james.sys.executable, str(james.SPEECH_SCRIPT_PATH), "--en", "-"],
        )
        self.assertEqual(run.call_args.kwargs["input"], "Hello world.")
        self.assertTrue(run.call_args.kwargs["capture_output"])

    def test_chat_say_reads_text_file_or_markdown_cleaned_last_reply(self) -> None:
        config = {"chat_model": "test-model", "language": "cz"}
        terminal = Mock()
        with (
            patch.object(james, "set_chat_selector", return_value=True),
            patch.object(james, "ensure_chat_context_file"),
            patch.object(james, "clear_screen"),
            patch.object(james, "render_page_header"),
            patch.object(james, "render_chat_commands"),
            patch.object(james, "read_chat_project_file", return_value=(Path("notes.txt"), "File speech.")),
            patch.object(james, "read_chat_last_reply", return_value="# Final\n\n**Reply**."),
            patch.object(james, "run_chat_say") as say,
            patch.object(james, "Terminal", return_value=terminal),
            patch("builtins.input", side_effect=['/say "Literal speech."', "/say notes.txt", "/say", "/bye"]),
            redirect_stdout(StringIO()),
        ):
            james.run_chat(config)

        self.assertEqual(
            say.call_args_list,
            [
                call("Literal speech.", "cz", debug=True),
                call("File speech.", "cz", debug=True),
                call("Final\n\nReply.", "cz", debug=True),
            ],
        )

    def test_chat_audio_helpers_use_the_active_project_directory(self) -> None:
        config: dict[str, object] = {}
        project_directory = james.PROJECT_ROOT / "project_test"
        completed = type("Completed", (), {"returncode": 0, "stdout": "", "stderr": ""})()

        with (
            patch.object(james, "active_project_directory", return_value=project_directory),
            patch.object(james.subprocess, "run", return_value=completed) as run,
        ):
            recording = james.run_chat_record(config, "record.mp3")
            transcript = james.run_chat_whisper(config, "record.mp3", debug=False)

        self.assertEqual(recording, project_directory / "record.mp3")
        self.assertEqual(transcript, project_directory / "record.txt")
        self.assertEqual(
            run.call_args_list[0].args[0],
            [
                james.sys.executable,
                str(james.RECORD_SCRIPT_PATH),
                "--project-dir",
                "project_test",
                "record.mp3",
            ],
        )
        self.assertEqual(
            run.call_args_list[1].args[0],
            [
                james.sys.executable,
                str(james.WHISPER_SCRIPT_PATH),
                "--project-dir",
                "project_test",
                "record.mp3",
            ],
        )
        self.assertTrue(run.call_args_list[1].kwargs["capture_output"])

    def test_play_command_uses_a_project_local_mp3(self) -> None:
        config: dict[str, object] = {}
        project_directory = james.PROJECT_ROOT / "project_test"
        with (
            patch.object(james, "active_project_directory", return_value=project_directory),
            patch.object(james, "play_audio_file") as play_audio,
        ):
            audio_path = james.play_chat_mp3(config, "record.mp3")

        self.assertEqual(audio_path, project_directory / "record.mp3")
        play_audio.assert_called_once_with(project_directory / "record.mp3")

    def test_chat_audio_commands_use_record_mp3_by_default(self) -> None:
        config = {"chat_model": "test-model", "language": "cz"}
        terminal = Mock()
        with (
            patch.object(james, "set_chat_selector", return_value=True),
            patch.object(james, "ensure_chat_context_file"),
            patch.object(james, "clear_screen"),
            patch.object(james, "render_page_header"),
            patch.object(james, "render_chat_commands"),
            patch.object(james, "run_chat_record", return_value=Path("record.mp3")) as record,
            patch.object(james, "run_chat_whisper", return_value=Path("record.txt")) as whisper,
            patch.object(james, "read_chat_transcript", return_value="Recognized speech.") as read_transcript,
            patch.object(james, "play_chat_mp3", return_value=Path("record.mp3")) as play,
            patch.object(james, "Terminal", return_value=terminal),
            patch("builtins.input", side_effect=["/rec", "/whisper", "/play", "/bye"]),
            redirect_stdout(StringIO()),
        ):
            james.run_chat(config)

        record.assert_called_once_with(config, "record.mp3")
        whisper.assert_called_once_with(config, "record.mp3", debug=True)
        read_transcript.assert_called_once_with(Path("record.txt"))
        play.assert_called_once_with(config, "record.mp3")
        terminal.y.assert_any_call("Transcript saved: record.txt")
        terminal.g.assert_any_call("Recognized speech.")

    def test_voice_records_corrects_then_submits_the_transcript_to_chat(self) -> None:
        config = {"chat_model": "test-model", "language": "cz"}
        with (
            patch.object(james, "set_chat_selector", return_value=True),
            patch.object(james, "ensure_chat_context_file"),
            patch.object(james, "chat_debug_default", return_value=False),
            patch.object(james, "clear_screen"),
            patch.object(james, "render_page_header"),
            patch.object(james, "render_chat_commands"),
            patch.object(james, "run_chat_record", return_value=Path("record.mp3")) as record,
            patch.object(james, "run_chat_whisper", return_value=Path("record.txt")) as whisper,
            patch.object(
                james,
                "read_chat_transcript",
                return_value="Source file: record.mp3\nWhisper language: cs\n\nRaw voice transcript.",
            ),
            patch.object(james, "write_chat_input") as write_input,
            patch.object(james, "run_flow", return_value=0) as run_flow,
            patch.object(james, "read_chat_last_reply", return_value="Corrected voice transcript."),
            patch.object(james, "render_chat_reply") as render_reply,
            patch.object(james, "append_chat_turn") as append_turn,
            patch("builtins.input", side_effect=["/voice", "/bye"]),
            redirect_stdout(StringIO()),
        ):
            james.run_chat(config)

        record.assert_called_once_with(config, "record.mp3")
        whisper.assert_called_once_with(config, "record.mp3", debug=False)
        self.assertEqual(
            write_input.call_args_list,
            [
                call(config, "Raw voice transcript."),
                call(config, "Corrected voice transcript."),
            ],
        )
        self.assertEqual(run_flow.call_count, 2)
        self.assertEqual(run_flow.call_args_list[0].args[0], "chat/flow_last_reply.json")
        self.assertEqual(run_flow.call_args_list[0].kwargs["sc_commands"], ["speechfix"])
        self.assertEqual(run_flow.call_args_list[0].kwargs["sc_language"], "cz")
        self.assertTrue(run_flow.call_args_list[0].kwargs["capture_output"])
        self.assertTrue(run_flow.call_args_list[0].kwargs["quiet"])
        self.assertEqual(run_flow.call_args_list[1].args[0], "chat/flow_last_reply.json")
        self.assertEqual(run_flow.call_args_list[1].kwargs["sc_commands"], ["chat"])
        self.assertEqual(run_flow.call_args_list[1].kwargs["sc_language"], "cz")
        render_reply.assert_called_once_with(config)
        append_turn.assert_called_once_with(config, "Corrected voice transcript.")

    def test_cat_command_reads_a_project_local_utf8_file(self) -> None:
        self.assertEqual(james.extract_chat_cat_command("/cat"), james.CHAT_CONTEXT_FILENAME)
        self.assertEqual(james.extract_chat_cat_command('/cat "notes.md"'), "notes.md")
        with TemporaryDirectory() as temporary_directory:
            project_directory = Path(temporary_directory)
            (project_directory / "notes.md").write_text("# Notes\n", encoding="utf-8")
            with patch.object(james, "active_project_directory", return_value=project_directory):
                path, content = james.read_chat_project_file({}, "notes.md")

        self.assertEqual(path, (project_directory / "notes.md").resolve())
        self.assertEqual(content, "# Notes\n")

    def test_cat_command_renders_markdown_files_with_the_shared_renderer(self) -> None:
        config = {"chat_model": "test-model", "language": "cz"}
        with TemporaryDirectory() as temporary_directory:
            project_directory = Path(temporary_directory)
            document = project_directory / "notes.md"
            document.write_text("# Notes\n- `item`\n", encoding="utf-8")
            with (
                patch.object(james, "set_chat_selector", return_value=True),
                patch.object(james, "ensure_chat_context_file"),
                patch.object(james, "clear_screen"),
                patch.object(james, "render_page_header"),
                patch.object(james, "render_chat_commands"),
                patch.object(james, "active_project_directory", return_value=project_directory),
                patch.object(
                    james,
                    "render_markdown_lines",
                    side_effect=lambda lines, _config: [f"rendered:{line}" for line in lines],
                ) as render_lines,
                patch.object(james, "run_flow") as run_flow,
                patch("builtins.input", side_effect=["/cat notes.md", "/bye"]),
                redirect_stdout(StringIO()),
            ):
                james.run_chat(config)

        self.assertEqual(render_lines.call_args.args[0], ["# Notes", "- `item`"])
        run_flow.assert_not_called()

    def test_bare_cat_renders_the_main_chat_context(self) -> None:
        config = {"chat_model": "test-model", "language": "cz"}
        with TemporaryDirectory() as temporary_directory:
            project_directory = Path(temporary_directory)
            context_path = project_directory / james.CHAT_CONTEXT_FILENAME
            context_path.write_text("# Core chat context\n- **Important**\n", encoding="utf-8")
            output = StringIO()
            with (
                patch.object(james, "set_chat_selector", return_value=True),
                patch.object(james, "ensure_chat_context_file", return_value=context_path),
                patch.object(james, "clear_screen"),
                patch.object(james, "render_page_header"),
                patch.object(james, "render_chat_commands"),
                patch.object(james, "active_project_directory", return_value=project_directory),
                patch.object(
                    james,
                    "render_markdown_lines",
                    side_effect=lambda lines, _config: [f"rendered:{line}" for line in lines],
                ) as render_lines,
                patch.object(james, "run_flow") as run_flow,
                patch("builtins.input", side_effect=["/cat", "/bye"]),
                redirect_stdout(output),
            ):
                james.run_chat(config)

        self.assertIn("chat_context.txt:", output.getvalue())
        self.assertIn("rendered:# Core chat context", output.getvalue())
        self.assertEqual(render_lines.call_args.args[0], ["# Core chat context", "- **Important**"])
        run_flow.assert_not_called()

    def test_last_command_reuses_the_shared_markdown_reply_renderer(self) -> None:
        config = {"chat_model": "test-model", "language": "cz"}
        with (
            patch.object(james, "set_chat_selector", return_value=True),
            patch.object(james, "ensure_chat_context_file"),
            patch.object(james, "clear_screen"),
            patch.object(james, "render_page_header"),
            patch.object(james, "render_chat_commands"),
            patch.object(james, "render_chat_reply") as render_reply,
            patch("builtins.input", side_effect=["/last", "/bye"]),
            redirect_stdout(StringIO()),
        ):
            james.run_chat(config)

        render_reply.assert_called_once()

    def test_debug_command_parses_status_and_explicit_states(self) -> None:
        self.assertEqual(james.extract_chat_debug_command("/debug"), "status")
        self.assertEqual(james.extract_chat_debug_command("/debug on"), "on")
        self.assertEqual(james.extract_chat_debug_command("/debug true"), "on")
        self.assertEqual(james.extract_chat_debug_command("/debug off"), "off")
        self.assertEqual(james.extract_chat_debug_command("/debug false"), "off")
        with self.assertRaisesRegex(ValueError, "Use /debug"):
            james.extract_chat_debug_command("/debug verbose")

    def test_chat_debug_defaults_to_on(self) -> None:
        self.assertTrue(james.chat_debug_default())

    def test_mod_without_a_model_requests_the_model_list(self) -> None:
        self.assertEqual(james.extract_chat_mod_command("/mod"), (None, ""))
        self.assertEqual(james.extract_chat_mod_command("/mod qwen3.5:latest"), ("qwen3.5:latest", ""))

    def test_lng_command_lists_or_selects_only_supported_chat_languages(self) -> None:
        self.assertEqual(james.extract_chat_lng_command("/lng"), "")
        self.assertEqual(james.extract_chat_lng_command("/lng ES"), "es")
        with self.assertRaisesRegex(ValueError, "Available: cz, en, es"):
            james.extract_chat_lng_command("/lng de")

    def test_proj_command_lists_or_selects_a_session_subdirectory(self) -> None:
        self.assertEqual(james.extract_chat_proj_command("/proj"), "")
        self.assertEqual(james.extract_chat_proj_command(' /PROJ "project_test/rag" '), "project_test/rag")
        self.assertIsNone(james.extract_chat_proj_command("/project project_test"))

    def test_active_project_directory_honors_chat_only_override(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            temporary_root = Path(temporary_directory)
            with (
                patch.object(james, "PROJECT_ROOT", temporary_root),
                patch.object(james, "load_project_config") as load_project,
            ):
                directory = james.active_project_directory({james.CHAT_PROJECT_SUBDIR_OVERRIDE_KEY: "temporary"})

        self.assertEqual(directory, (temporary_root / "temporary").resolve())
        load_project.assert_not_called()

    def test_lng_switches_only_the_current_chat_session(self) -> None:
        config = {"chat_model": "test-model", "language": "cz"}
        with (
            patch.object(james, "set_chat_selector", return_value=True),
            patch.object(james, "ensure_chat_context_file"),
            patch.object(james, "clear_screen"),
            patch.object(james, "render_page_header"),
            patch.object(james, "render_chat_commands"),
            patch.object(james, "write_chat_input") as write_chat_input,
            patch.object(james, "read_chat_active_image", return_value=None),
            patch.object(james, "run_flow", return_value=0) as run_flow,
            patch.object(james, "render_chat_reply"),
            patch.object(james, "append_chat_turn"),
            patch("builtins.input", side_effect=["/lng es", "Explain this", "/bye"]),
        ):
            james.run_chat(config)

        self.assertEqual(config["language"], "cz")
        self.assertEqual(run_flow.call_args.args[0], "flow_chat_es.json")
        self.assertEqual(write_chat_input.call_args.args[0]["language"], "es")

    def test_task_command_lists_and_validates_task_json_files(self) -> None:
        self.assertEqual(james.extract_chat_task_command("/task"), "")
        self.assertEqual(james.extract_chat_task_command("/task task_test.json"), "task_test.json")
        self.assertIn("task_base.json", james.available_chat_tasks())
        self.assertEqual(james.select_chat_task("TASK_BASE.JSON"), "task_base.json")
        with self.assertRaisesRegex(ValueError, "assistant/tasks"):
            james.select_chat_task("../task_base.json")
        with self.assertRaisesRegex(ValueError, "not found"):
            james.select_chat_task("missing.json")

    def test_chat_task_model_is_read_from_the_selected_task(self) -> None:
        self.assertEqual(james.chat_task_model("task_base.json"), "qwen3.5:latest")

    def test_task_command_changes_the_session_selection_and_overrides_the_chat_flow(self) -> None:
        config = {"chat_model": "test-model", "language": "cz"}

        with (
            patch.object(james, "set_chat_selector", return_value=True),
            patch.object(james, "ensure_chat_context_file"),
            patch.object(james, "clear_screen"),
            patch.object(james, "render_page_header"),
            patch.object(james, "render_chat_commands"),
            patch.object(james, "write_chat_input"),
            patch.object(james, "read_chat_active_image", return_value=None),
            patch.object(james, "run_flow", return_value=0) as run_flow,
            patch.object(james, "render_chat_reply"),
            patch.object(james, "append_chat_turn"),
            patch("builtins.input", side_effect=["/task task_test.json", "/explain Test", "/bye"]),
        ):
            james.run_chat(config)

        self.assertEqual(run_flow.call_args.kwargs["task_override"], "task_test.json")

    def test_run_flow_passes_and_displays_the_active_task_and_model(self) -> None:
        completed = type("Completed", (), {"returncode": 0})()
        output = StringIO()

        with patch.object(james.subprocess, "run", return_value=completed) as run, redirect_stdout(output):
            james.run_flow(
                "flow_chat_cz.json",
                pause_after=False,
                report_result=False,
                clear_before=False,
                task_override="task_base.json",
                model_override="model_abc",
            )

        self.assertEqual(
            run.call_args.args[0],
            [
                james.sys.executable,
                str(james.RUNNER_SCRIPT_PATH),
                "--model",
                "model_abc",
                "--task",
                "task_base.json",
                "flow_chat_cz.json",
            ],
        )
        self.assertIn("Starting runner.py flow_chat_cz.json (task: task_base.json | Model: model_abc)", output.getvalue())

    def test_run_flow_quiet_prints_only_a_muted_status(self) -> None:
        completed = type("Completed", (), {"returncode": 0})()
        output = StringIO()

        with patch.object(james.subprocess, "run", return_value=completed), redirect_stdout(output):
            james.run_flow(
                "flow_chat_cz.json",
                pause_after=False,
                report_result=False,
                clear_before=False,
                quiet=True,
            )

        self.assertEqual(output.getvalue(), "• Running…\n")

    def test_chat_model_list_highlights_the_active_model(self) -> None:
        completed = type(
            "Completed",
            (),
            {"returncode": 0, "stdout": "NAME ID SIZE\nqwen3.5:latest abc 4 GB\nother:def ghi 2 GB\n", "stderr": ""},
        )()
        terminal = Mock()
        terminal.color.side_effect = lambda color, text: f"<{color}>{text}</{color}>"
        output = StringIO()

        with (
            patch.object(james.subprocess, "run", return_value=completed) as run,
            patch.object(james, "Terminal", return_value=terminal),
            redirect_stdout(output),
        ):
            james.render_chat_models("qwen3.5:latest")

        self.assertEqual(run.call_args.args[0], ["ollama", "list"])
        self.assertEqual(run.call_args.kwargs["cwd"], james.PROJECT_ROOT)
        self.assertIn("<yellow>qwen3.5:latest</yellow> abc 4 GB", output.getvalue())
        self.assertIn("other:def ghi 2 GB", output.getvalue())

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

    def test_rag_context_is_replaced_without_losing_other_sources_or_turns(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            project_directory = Path(temporary_directory)
            context_path = project_directory / james.CHAT_CONTEXT_FILENAME
            context_path.write_text(
                "## File source\nPath: notes.txt\n\nKeep this source\n\n"
                "## [RAG]\nDatabase: wiki_old.db\n\n### RAG result 1\n\nDiscard this chunk\n\n"
                "## Conversation\n- user:\n  Hello\n- assistant:\n  Hi\n",
                encoding="utf-8",
            )
            with patch.object(james, "active_project_directory", return_value=project_directory):
                james.replace_chat_rag_context({}, "## [RAG]\nDatabase: wiki_btc.db\n\n### RAG result 1\n\nFresh chunk")
                removed_count = james.drop_chat_rag_context({})

            context = context_path.read_text(encoding="utf-8")
            self.assertEqual(removed_count, 1)
            self.assertIn("Keep this source", context)
            self.assertNotIn("Discard this chunk", context)
            self.assertNotIn("Fresh chunk", context)
            self.assertIn("## Conversation", context)

    def test_add_command_rejects_paths_outside_the_project(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            project_directory = Path(temporary_directory)
            config = {"chat_context_turns": 6}
            with patch.object(james, "active_project_directory", return_value=project_directory):
                with self.assertRaisesRegex(ValueError, "outside"):
                    james.append_chat_file_context(config, "../secret.txt")

    def test_ocr_command_adds_the_result_to_context_with_an_ocr_label(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            project_directory = Path(temporary_directory)
            image_path = project_directory / "camera.png"
            image_path.write_bytes(b"image")
            (project_directory / james.OCR_OUTPUT_FILENAME).write_text("Recognized receipt text", encoding="utf-8")
            config = {"chat_context_turns": 6}

            with patch.object(james, "active_project_directory", return_value=project_directory):
                output_path, character_count = james.append_chat_ocr_context(config, image_path)

            context = (project_directory / james.CHAT_CONTEXT_FILENAME).read_text(encoding="utf-8")
            self.assertEqual(output_path, (project_directory / james.OCR_OUTPUT_FILENAME).resolve())
            self.assertEqual(character_count, len("Recognized receipt text"))
            self.assertIn("## [OCR]", context)
            self.assertIn("Image: camera.png", context)
            self.assertIn("Recognized receipt text", context)

    def test_active_chat_image_is_project_local_and_can_be_cleared(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            project_directory = Path(temporary_directory)
            image_path = project_directory / "camera.png"
            image_path.write_bytes(b"image")
            with patch.object(james, "active_project_directory", return_value=project_directory):
                selected = james.set_chat_active_image({}, image_path)
                active = james.read_chat_active_image({})
                james.clear_chat_active_image({})
                cleared = james.read_chat_active_image({})

        self.assertEqual(selected, "camera.png")
        self.assertEqual(active, "camera.png")
        self.assertIsNone(cleared)

    def test_ctx_drop_ocr_and_save_manage_the_persistent_context(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            project_directory = Path(temporary_directory)
            context_path = project_directory / james.CHAT_CONTEXT_FILENAME
            context_path.write_text(
                "## [OCR]\nImage: camera.png\nResult: ocr.txt\n\nReceipt text\n\n"
                "## [IMAGE]\nImage: camera.png\nResult: describe.txt\n\nA receipt.\n\n"
                "## Conversation\n- user:\n  Hello\n- assistant:\n  Hi\n",
                encoding="utf-8",
            )
            with patch.object(james, "active_project_directory", return_value=project_directory):
                source_count, turn_count, character_count = james.chat_context_status({})
                sources = james.list_chat_context_sources({})
                removed_count = james.drop_chat_ocr_context({})
                export_path = james.save_chat_context({}, "export.md")

            updated_context = context_path.read_text(encoding="utf-8")
            self.assertEqual((source_count, turn_count), (2, 1))
            self.assertEqual(sources, ["[OCR]: camera.png", "[IMAGE]: camera.png"])
            self.assertGreater(character_count, 0)
            self.assertEqual(removed_count, 1)
            self.assertNotIn("[OCR]", updated_context)
            self.assertIn("[IMAGE]", updated_context)
            self.assertEqual(export_path.read_text(encoding="utf-8"), updated_context)

    def test_clipboard_find_and_last_helpers_use_project_local_context(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            project_directory = Path(temporary_directory)
            (project_directory / "notes.md").write_text("A useful receipt note\n", encoding="utf-8")
            (project_directory / james.CHAT_REPLY_FILENAME).write_text("Latest response", encoding="utf-8")

            with patch.object(james, "active_project_directory", return_value=project_directory):
                character_count = james.append_chat_clipboard_context({}, "Copied text")
                matches = james.find_chat_project_text({}, "receipt")
                last_reply = james.read_chat_last_reply({})

            context = (project_directory / james.CHAT_CONTEXT_FILENAME).read_text(encoding="utf-8")
            self.assertEqual(character_count, len("Copied text"))
            self.assertIn("## [CLIPBOARD]", context)
            self.assertIn("Copied text", context)
            self.assertEqual(matches, [("notes.md", 1, "A useful receipt note")])
            self.assertEqual(last_reply, "Latest response")

    def test_files_command_lists_relative_project_files(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            project_directory = Path(temporary_directory)
            (project_directory / "notes.txt").write_text("Notes", encoding="utf-8")
            nested_directory = project_directory / "source"
            nested_directory.mkdir()
            (nested_directory / "details.md").write_text("Details", encoding="utf-8")

            with patch.object(james, "active_project_directory", return_value=project_directory):
                files, total_count = james.list_chat_project_files({})

            self.assertEqual(files, ["notes.txt", "source/details.md"])
            self.assertEqual(total_count, 2)
            self.assertTrue(james.is_chat_files_command("/files"))
            self.assertTrue(james.is_chat_files_command("/ls"))

    def test_find_command_requires_search_text(self) -> None:
        with self.assertRaisesRegex(ValueError, "Use /find"):
            james.extract_chat_find_command("/find")

    def test_tool_command_forwards_parsed_cli_parameters(self) -> None:
        completed = type("Completed", (), {"returncode": 0})()
        self.assertEqual(james.extract_chat_tool_command("/tool --date-time"), ["--date-time"])
        self.assertEqual(james.extract_chat_tool_command("/tool --url 'https://example.test'"), ["--url", "https://example.test"])
        with patch.object(james.subprocess, "run", return_value=completed) as run:
            james.run_chat_tool(["--ping"])

        self.assertEqual(run.call_args.args[0], [james.sys.executable, str(james.TOOL_SCRIPT_PATH), "--ping"])

    def test_tool_command_requires_a_parameter(self) -> None:
        with self.assertRaisesRegex(ValueError, "Use /tool"):
            james.extract_chat_tool_command("/tool")

    def test_load_command_replaces_the_complete_context(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            project_directory = Path(temporary_directory)
            context_path = project_directory / james.CHAT_CONTEXT_FILENAME
            context_path.write_text("Old context\n", encoding="utf-8")
            (project_directory / "saved_chat.md").write_text("## Imported\nNew context\n", encoding="utf-8")

            with patch.object(james, "active_project_directory", return_value=project_directory):
                source_path, character_count = james.load_chat_context({}, "saved_chat.md")

            self.assertEqual(source_path, (project_directory / "saved_chat.md").resolve())
            self.assertEqual(character_count, len("## Imported\nNew context\n"))
            self.assertEqual(context_path.read_text(encoding="utf-8"), "## Imported\nNew context\n")

    def test_load_command_requires_a_file_name(self) -> None:
        with self.assertRaisesRegex(ValueError, "Use /load"):
            james.extract_chat_load_command("/load")

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
            patch.object(james, "chat_debug_default", return_value=False),
            patch.object(james, "clear_screen"),
            patch.object(james, "render_page_header"),
            patch.object(james, "render_chat_commands"),
            patch.object(james, "write_chat_input") as write_chat_input,
            patch.object(james, "read_chat_active_image", return_value=None),
            patch.object(james, "run_flow", return_value=0) as run_flow,
            patch.object(james, "render_chat_reply"),
            patch.object(james, "save_chat_summary") as save_chat_summary,
            patch.object(james, "append_chat_turn") as append_chat_turn,
            patch("builtins.input", side_effect=["/mod current-model", "/sum", "/bye"]),
        ):
            james.run_chat(config)

        write_chat_input.assert_called_once_with(config, james.chat_summary_prompt("cz"))
        self.assertEqual(run_flow.call_args.kwargs["model_override"], "current-model")
        self.assertTrue(run_flow.call_args.kwargs["capture_output"])
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

    def test_chunk_attaches_context_without_running_the_model(self) -> None:
        config = {"chat_model": "test-model", "language": "cz"}
        profile = DatabaseProfile("btc", Path("wiki_btc.db"), "btc")
        with (
            patch.object(james, "set_chat_selector", return_value=True),
            patch.object(james, "ensure_chat_context_file"),
            patch.object(james, "clear_screen"),
            patch.object(james, "render_page_header"),
            patch.object(james, "render_chat_commands"),
            patch.object(james, "select_chat_rag_profile", return_value=profile) as select_profile,
            patch.object(james, "drop_chat_rag_context", return_value=0),
            patch.object(james, "build_chat_rag_context", return_value=("## [RAG]", 3)) as build_context,
            patch.object(james, "replace_chat_rag_context") as replace_context,
            patch.object(james, "render_chat_rag_context") as render_context,
            patch.object(james, "run_flow", return_value=0) as run_flow,
            patch("builtins.input", side_effect=["/rag btc", "/chunk Co je těžba bitcoinu?", "/bye"]),
            redirect_stdout(StringIO()),
        ):
            james.run_chat(config)

        select_profile.assert_called_once_with("btc")
        build_context.assert_called_once_with(profile, "Co je těžba bitcoinu?", 5)
        replace_context.assert_called_once_with(config, "## [RAG]")
        render_context.assert_called_once_with(config, "## [RAG]")
        run_flow.assert_not_called()

    def test_tag_only_chunk_waits_for_a_following_question(self) -> None:
        config = {"chat_model": "test-model", "language": "cz"}
        profile = DatabaseProfile("btc", Path("wiki_btc.db"), "btc")
        with (
            patch.object(james, "set_chat_selector", return_value=True),
            patch.object(james, "ensure_chat_context_file"),
            patch.object(james, "clear_screen"),
            patch.object(james, "render_page_header"),
            patch.object(james, "render_chat_commands"),
            patch.object(james, "select_chat_rag_profile", return_value=profile),
            patch.object(james, "drop_chat_rag_context", return_value=0),
            patch.object(james, "build_chat_rag_context", return_value=("## [RAG]", 2)) as build_context,
            patch.object(james, "replace_chat_rag_context"),
            patch.object(james, "render_chat_rag_context"),
            patch.object(james, "write_chat_input") as write_chat_input,
            patch.object(james, "read_chat_active_image", return_value=None),
            patch.object(james, "run_flow", return_value=0) as run_flow,
            patch.object(james, "render_chat_reply"),
            patch.object(james, "append_chat_turn"),
            patch("builtins.input", side_effect=["/rag btc", "/chunk #(těžba bitcoinu) #(bezpečné uchování)", "Jak bezpečně uložit bitcoin?", "/bye"]),
            redirect_stdout(StringIO()),
        ):
            james.run_chat(config)

        build_context.assert_called_once_with(profile, '"těžba bitcoinu" AND "bezpečné uchování"', 5)
        write_chat_input.assert_called_once_with(config, "Jak bezpečně uložit bitcoin?")
        self.assertEqual(run_flow.call_count, 1)

    def test_ask_attaches_semantic_rag_context_and_submits_its_question(self) -> None:
        config = {"chat_model": "test-model", "language": "cz"}
        profile = DatabaseProfile("btc", Path("wiki_btc.db"), "btc")
        with (
            patch.object(james, "set_chat_selector", return_value=True),
            patch.object(james, "ensure_chat_context_file"),
            patch.object(james, "clear_screen"),
            patch.object(james, "render_page_header"),
            patch.object(james, "render_chat_commands"),
            patch.object(james, "select_chat_rag_profile", return_value=profile),
            patch.object(james, "drop_chat_rag_context", return_value=0),
            patch.object(james, "build_chat_semantic_rag_context", return_value=("## [RAG]", [object(), object()], {}, {})) as build_context,
            patch.object(james, "replace_chat_rag_context") as replace_context,
            patch.object(james, "render_chat_rag_context"),
            patch.object(james, "write_chat_input") as write_chat_input,
            patch.object(james, "read_chat_active_image", return_value=None),
            patch.object(james, "run_flow", return_value=0) as run_flow,
            patch.object(james, "render_chat_reply"),
            patch.object(james, "append_chat_turn"),
            patch("builtins.input", side_effect=["/rag btc", "/ask (bitcoin mining) or (hardware wallet) :: Explain the relation.", "/bye"]),
            redirect_stdout(StringIO()),
        ):
            james.run_chat(config)

        build_context.assert_called_once_with(profile, ["bitcoin mining", "hardware wallet"], ["OR"], 5)
        replace_context.assert_called_once_with(config, "## [RAG]")
        write_chat_input.assert_called_once_with(config, "Explain the relation.")
        self.assertEqual(run_flow.call_count, 1)

    def test_chat_camera_and_ocr_commands_do_not_run_the_chat_flow(self) -> None:
        config = {"chat_model": "test-model", "language": "cz"}

        with (
            patch.object(james, "set_chat_selector", return_value=True),
            patch.object(james, "ensure_chat_context_file"),
            patch.object(james, "chat_debug_default", return_value=False),
            patch.object(james, "clear_screen"),
            patch.object(james, "render_page_header"),
            patch.object(james, "render_chat_commands"),
            patch.object(james, "capture_chat_camera", return_value=Path("camera.png")) as capture_camera,
            patch.object(james, "run_chat_ocr", return_value=Path("camera.png")) as run_ocr,
            patch.object(james, "append_chat_ocr_context", return_value=(Path("ocr.txt"), 10)) as append_ocr,
            patch.object(james, "run_flow") as run_flow,
            patch("builtins.input", side_effect=["/cam", "/ocr", "/bye"]),
        ):
            james.run_chat(config)

        capture_camera.assert_called_once_with(config, "camera.png", debug=False)
        run_ocr.assert_called_once_with(config, "camera.png")
        append_ocr.assert_called_once_with(config, Path("camera.png"))
        run_flow.assert_not_called()

    def test_camera_ocr_and_img_commands_call_the_expected_clis(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            project_directory = Path(temporary_directory)
            (project_directory / "receipt.png").write_bytes(b"image")
            completed = type("Completed", (), {"returncode": 0})()
            with (
                patch.object(james, "active_project_directory", return_value=project_directory),
                patch.object(james.subprocess, "run", return_value=completed) as run,
            ):
                captured_path = james.capture_chat_camera({}, "capture.png")
                ocr_path = james.run_chat_ocr({"language": "cz"}, "receipt.png")
                image_path = james.run_chat_img({"language": "cz"}, "receipt.png")
                english_image_path = james.run_chat_img({"language": "en"}, "receipt.png")

            self.assertEqual(captured_path, (project_directory / "capture.png").resolve())
            self.assertEqual(ocr_path, (project_directory / "receipt.png").resolve())
            self.assertEqual(image_path, (project_directory / "receipt.png").resolve())
            self.assertEqual(english_image_path, (project_directory / "receipt.png").resolve())
            self.assertEqual(
                run.call_args_list[0].args[0],
                [james.sys.executable, str(james.CAMERA_SCRIPT_PATH), "--out", "capture.png"],
            )
            self.assertEqual(
                run.call_args_list[0].kwargs,
                {"cwd": james.PROJECT_ROOT, "check": False, "capture_output": True, "text": True, "encoding": "utf-8", "errors": "replace"},
            )
            self.assertEqual(
                run.call_args_list[1].args[0],
                [
                    james.sys.executable,
                    str(james.OLLAMA_SCRIPT_PATH),
                    "--type",
                    "task_ocr.json",
                    "--sc-cz",
                    "--sc",
                    "/ocr",
                    "--in",
                    "receipt.png",
                ],
            )
            self.assertEqual(
                run.call_args_list[2].args[0],
                [
                    james.sys.executable,
                    str(james.OLLAMA_SCRIPT_PATH),
                    "--type",
                    "task_describe.json",
                    "--sc-cz",
                    "--sc",
                    "/describe",
                    "--in",
                    "receipt.png",
                ],
            )
            self.assertEqual(
                run.call_args_list[3].args[0],
                [
                    james.sys.executable,
                    str(james.OLLAMA_SCRIPT_PATH),
                    "--type",
                    "task_describe.json",
                    "--sc-en",
                    "--sc",
                    "/describe",
                    "--in",
                    "receipt.png",
                ],
            )

    def test_chat_debug_switches_camera_diagnostics_for_the_current_session(self) -> None:
        config = {"chat_model": "test-model", "language": "cz"}
        output = StringIO()
        with (
            patch.object(james, "set_chat_selector", return_value=True),
            patch.object(james, "ensure_chat_context_file"),
            patch.object(james, "chat_debug_default", return_value=False),
            patch.object(james, "clear_screen"),
            patch.object(james, "render_page_header"),
            patch.object(james, "render_chat_commands"),
            patch.object(james, "capture_chat_camera", return_value=Path("camera.png")) as capture_camera,
            patch("builtins.input", side_effect=["/debug", "/debug on", "/cam", "/debug off", "/cam", "/bye"]),
            redirect_stdout(output),
        ):
            james.run_chat(config)

        self.assertEqual(
            capture_camera.call_args_list,
            [
                call(config, "camera.png", debug=True),
                call(config, "camera.png", debug=False),
            ],
        )
        self.assertIn("Chat debug: off.", output.getvalue())
        self.assertIn("Chat debug: on.", output.getvalue())

    def test_chat_debug_keeps_runner_output_live(self) -> None:
        config = {"chat_model": "test-model", "language": "cz"}
        with (
            patch.object(james, "set_chat_selector", return_value=True),
            patch.object(james, "ensure_chat_context_file"),
            patch.object(james, "chat_debug_default", return_value=False),
            patch.object(james, "clear_screen"),
            patch.object(james, "render_page_header"),
            patch.object(james, "render_chat_commands"),
            patch.object(james, "write_chat_input"),
            patch.object(james, "read_chat_active_image", return_value=None),
            patch.object(james, "run_flow", return_value=0) as run_flow,
            patch.object(james, "append_chat_turn"),
            patch("builtins.input", side_effect=["/debug on", "Explain this", "/bye"]),
        ):
            james.run_chat(config)

        self.assertFalse(run_flow.call_args.kwargs["capture_output"])
        self.assertFalse(run_flow.call_args.kwargs["quiet"])

    def test_chat_debug_off_uses_quiet_flow_execution(self) -> None:
        config = {"chat_model": "test-model", "language": "cz"}
        with (
            patch.object(james, "set_chat_selector", return_value=True),
            patch.object(james, "ensure_chat_context_file"),
            patch.object(james, "chat_debug_default", return_value=False),
            patch.object(james, "clear_screen"),
            patch.object(james, "render_page_header"),
            patch.object(james, "render_chat_commands"),
            patch.object(james, "write_chat_input"),
            patch.object(james, "read_chat_active_image", return_value=None),
            patch.object(james, "run_flow", return_value=0) as run_flow,
            patch.object(james, "render_chat_reply"),
            patch.object(james, "append_chat_turn"),
            patch("builtins.input", side_effect=["Explain this", "/bye"]),
        ):
            james.run_chat(config)

        self.assertTrue(run_flow.call_args.kwargs["capture_output"])
        self.assertTrue(run_flow.call_args.kwargs["quiet"])

    def test_img_activates_vision_input_for_the_next_chat_question(self) -> None:
        config = {"chat_model": "test-model", "language": "cz"}
        with (
            patch.object(james, "set_chat_selector", return_value=True),
            patch.object(james, "ensure_chat_context_file"),
            patch.object(james, "clear_screen"),
            patch.object(james, "render_page_header"),
            patch.object(james, "render_chat_commands"),
            patch.object(james, "run_chat_img", return_value=Path("camera.png")),
            patch.object(james, "append_chat_img_context", return_value=(Path("describe.txt"), 10)),
            patch.object(james, "set_chat_active_image", return_value="camera.png"),
            patch.object(james, "read_chat_active_image", return_value="camera.png"),
            patch.object(james, "write_chat_input"),
            patch.object(james, "run_flow", return_value=0) as run_flow,
            patch.object(james, "render_chat_reply"),
            patch.object(james, "append_chat_turn"),
            patch("builtins.input", side_effect=["/img", "What are the icons?", "/bye"]),
            redirect_stdout(StringIO()),
        ):
            james.run_chat(config)

        self.assertEqual(run_flow.call_args.kwargs["image_file"], "camera.png")

    def test_catalog_modifier_is_forwarded_to_chat_flow(self) -> None:
        prompt, commands = james.extract_chat_sc_command("/eli5 Explain gravity.")

        self.assertEqual(prompt, "Explain gravity.")
        self.assertEqual(commands, ["eli5"])

    def test_catalog_tldr_action_is_forwarded_to_chat_flow(self) -> None:
        prompt, commands = james.extract_chat_sc_command("/tldr Long text to condense.")

        self.assertEqual(prompt, "Long text to condense.")
        self.assertEqual(commands, ["tldr"])

    def test_catalog_wtf_action_is_forwarded_to_chat_flow(self) -> None:
        prompt, commands = james.extract_chat_sc_command("/wtf Explain vector search.")

        self.assertEqual(prompt, "Explain vector search.")
        self.assertEqual(commands, ["wtf"])

    def test_catalog_command_without_text_is_available_for_chat_context(self) -> None:
        prompt, commands = james.extract_chat_sc_command("/tldr")

        self.assertEqual(prompt, "")
        self.assertEqual(commands, ["tldr"])

    def test_catalog_commands_can_be_chained_before_the_chat_input(self) -> None:
        prompt, commands = james.extract_chat_sc_command("/tldr /list /md chat_context.txt")

        self.assertEqual(prompt, "chat_context.txt")
        self.assertEqual(commands, ["tldr", "list", "md"])

    def test_bare_non_transform_catalog_command_uses_localized_chat_context_input(self) -> None:
        config = {"chat_model": "test-model", "language": "cz"}
        with (
            patch.object(james, "set_chat_selector", return_value=True),
            patch.object(james, "ensure_chat_context_file"),
            patch.object(james, "clear_screen"),
            patch.object(james, "render_page_header"),
            patch.object(james, "render_chat_commands"),
            patch.object(james, "write_chat_input") as write_chat_input,
            patch.object(james, "read_chat_active_image", return_value=None),
            patch.object(james, "run_flow", return_value=0) as run_flow,
            patch.object(james, "render_chat_reply"),
            patch.object(james, "append_chat_turn") as append_chat_turn,
            patch("builtins.input", side_effect=["/plan", "/bye"]),
        ):
            james.run_chat(config)

        write_chat_input.assert_called_once_with(
            config,
            "Aplikuj zvolený slash command na celý dodaný kontext chatu.",
        )
        self.assertEqual(run_flow.call_args.kwargs["sc_commands"], ["plan"])
        append_chat_turn.assert_called_once_with(config, "/plan [chat context]")

    def test_tldr_uses_only_the_latest_reply_with_a_flow_without_chat_context(self) -> None:
        config = {"chat_model": "test-model", "language": "cz"}
        with (
            patch.object(james, "set_chat_selector", return_value=True),
            patch.object(james, "ensure_chat_context_file"),
            patch.object(james, "clear_screen"),
            patch.object(james, "render_page_header"),
            patch.object(james, "render_chat_commands"),
            patch.object(james, "read_chat_last_reply", return_value="The previous answer."),
            patch.object(james, "write_chat_input") as write_chat_input,
            patch.object(james, "run_flow", return_value=0) as run_flow,
            patch.object(james, "render_chat_reply"),
            patch.object(james, "append_chat_turn") as append_chat_turn,
            patch("builtins.input", side_effect=["/tldr", "/bye"]),
        ):
            james.run_chat(config)

        write_chat_input.assert_called_once_with(config, "The previous answer.")
        self.assertEqual(run_flow.call_args.args[0], "chat/flow_last_reply.json")
        self.assertEqual(run_flow.call_args.kwargs["sc_commands"], ["tldr"])
        self.assertEqual(run_flow.call_args.kwargs["sc_language"], "cz")
        append_chat_turn.assert_called_once_with(config, "/tldr [last reply]")

    def test_tldr_can_be_chained_with_format_modifiers(self) -> None:
        config = {"chat_model": "test-model", "language": "cz"}
        with (
            patch.object(james, "set_chat_selector", return_value=True),
            patch.object(james, "ensure_chat_context_file"),
            patch.object(james, "chat_debug_default", return_value=False),
            patch.object(james, "clear_screen"),
            patch.object(james, "render_page_header"),
            patch.object(james, "render_chat_commands"),
            patch.object(james, "read_chat_last_reply", return_value="The previous answer."),
            patch.object(james, "write_chat_input"),
            patch.object(james, "run_flow", return_value=0) as run_flow,
            patch.object(james, "render_chat_reply"),
            patch.object(james, "append_chat_turn"),
            patch("builtins.input", side_effect=["/tldr /list /md", "/bye"]),
        ):
            james.run_chat(config)

        self.assertEqual(run_flow.call_args.kwargs["sc_commands"], ["tldr", "list", "md"])
        self.assertTrue(run_flow.call_args.kwargs["capture_output"])

    def test_wtf_uses_a_named_project_file_without_a_chat_context(self) -> None:
        config = {"chat_model": "test-model", "language": "cz"}
        with (
            patch.object(james, "set_chat_selector", return_value=True),
            patch.object(james, "ensure_chat_context_file"),
            patch.object(james, "clear_screen"),
            patch.object(james, "render_page_header"),
            patch.object(james, "render_chat_commands"),
            patch.object(james, "read_chat_transform_input", return_value=("Saved context.", "chat_context.txt")) as read_input,
            patch.object(james, "write_chat_input") as write_chat_input,
            patch.object(james, "run_flow", return_value=0) as run_flow,
            patch.object(james, "render_chat_reply"),
            patch.object(james, "append_chat_turn") as append_chat_turn,
            patch("builtins.input", side_effect=["/wtf chat_context.txt", "/bye"]),
        ):
            james.run_chat(config)

        read_input.assert_called_once_with(config, "wtf", "chat_context.txt")
        write_chat_input.assert_called_once_with(config, "Saved context.")
        self.assertEqual(run_flow.call_args.args[0], "chat/flow_last_reply.json")
        self.assertEqual(run_flow.call_args.kwargs["sc_commands"], ["wtf"])
        self.assertEqual(run_flow.call_args.kwargs["sc_language"], "cz")
        append_chat_turn.assert_called_once_with(config, "/wtf chat_context.txt")

    def test_transform_command_reads_a_utf8_project_file(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            project_directory = Path(temporary_directory)
            (project_directory / "chat_context.txt").write_text("Full chat context\n", encoding="utf-8")
            with patch.object(james, "active_project_directory", return_value=project_directory):
                text, source = james.read_chat_transform_input({}, "tldr", "chat_context.txt")

        self.assertEqual(text, "Full chat context")
        self.assertEqual(source, "chat_context.txt")

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
            patch.object(james, "read_chat_active_image", return_value=None),
            patch.object(james, "append_chat_turn"),
            patch.object(james, "run_flow", return_value=0) as run_flow,
            patch.object(james, "render_chat_reply"),
            patch("builtins.input", side_effect=["/plan Make a migration plan", "/bye"]),
        ):
            james.run_chat(config)

        self.assertEqual(run_flow.call_args.kwargs["sc_commands"], ["plan"])

    def test_chat_reply_uses_the_shared_markdown_renderer(self) -> None:
        config = james.load_james_config()
        with (
            patch.object(james, "read_chat_last_reply", return_value="# Result\n- **One** with `code`\n---"),
            patch.object(
                james,
                "render_markdown_lines",
                side_effect=lambda lines, _config: [f"rendered:{line}" for line in lines],
            ) as render_lines,
            redirect_stdout(StringIO()),
        ):
            james.render_chat_reply(config)

        self.assertEqual(render_lines.call_args.args[0], ["# Result", "- **One** with `code`", "---"])


class JamesMenuTests(unittest.TestCase):
    def test_configuration_is_loaded_from_james_directory(self) -> None:
        config = james.load_james_config()

        self.assertEqual(james.JAMES_CONFIG_PATH, james.PROJECT_ROOT / "james" / "james.json")
        self.assertEqual(james.JAMES_FLOWS_CONFIG_PATH, james.PROJECT_ROOT / "james" / "james_flows.json")
        self.assertEqual(james.WRAPP_MD_CONFIG_PATH, james.PROJECT_ROOT / "lib" / "wrapp_md.json")
        self.assertEqual(
            set(james.FLOW_CATEGORY_KEYS),
            {
                "flows_test",
                "flows_single",
                "flows_code",
                "flows_batch",
                "flows_media",
                "flows_mcp_base",
                "flows_mcp_hardware",
                "flows_rag_wiki",
            },
        )
        self.assertIn("flow_batch_ocr.txt", config["flows_batch"])
        self.assertEqual(config["flows_mcp_hardware"], ["flow_test_ble.txt"])
        self.assertEqual(
            config["flows_test"],
            ["flow_test.txt", "flow_base.txt", "flow_tools.txt", "flow_chat_test.txt", "flow_chat_test2.txt", "flow_chat_test3.txt"],
        )
        for flow_key in james.FLOW_CATEGORY_KEYS:
            for flow_name in config[flow_key]:
                self.assertTrue((james.PROJECT_ROOT / "flows" / flow_name).is_file())
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
        self.assertEqual(config["colors"]["col_italic"], "green")
        self.assertEqual(config["colors"]["col_code"], "bright_blue")
        self.assertNotIn("colors", json.loads(james.JAMES_CONFIG_PATH.read_text(encoding="utf-8")))
        self.assertNotIn("flows_test", json.loads(james.JAMES_CONFIG_PATH.read_text(encoding="utf-8")))
        self.assertIn("flows_test", json.loads(james.JAMES_FLOWS_CONFIG_PATH.read_text(encoding="utf-8")))
        self.assertEqual(json.loads(james.WRAPP_MD_CONFIG_PATH.read_text(encoding="utf-8"))["colors"]["col_bold"], "yellow")
        self.assertEqual(json.loads(james.WRAPP_MD_CONFIG_PATH.read_text(encoding="utf-8"))["colors"]["col_italic"], "green")
        self.assertEqual(json.loads(james.WRAPP_MD_CONFIG_PATH.read_text(encoding="utf-8"))["colors"]["col_code"], "bright_blue")

    def test_saving_james_config_keeps_markdown_colors_and_flow_lists_in_their_own_files(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            config_path = Path(temporary_directory) / "james.json"
            with patch.object(james, "JAMES_CONFIG_PATH", config_path):
                james.save_james_config({"name": "James", "flows_test": ["flow.txt"], "colors": {"col_bold": "yellow"}})

            saved = json.loads(config_path.read_text(encoding="utf-8"))

        self.assertEqual(saved, {"name": "James"})

    def test_main_menu_renders_requested_three_by_three_shortcuts(self) -> None:
        config = james.load_james_config()
        config["language"] = "cz"
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
        self.assertIn("jam3$-01 - v0.3.0 | project: project_example | menu", rendered)
        self.assertIn(" project_example | cz |", rendered)
        self.assertLess(
            output.getvalue().index(" project_example | cz |"),
            output.getvalue().index("-" * int(config["width"])),
        )
        menu_lines = [line for line in output.getvalue().splitlines() if "|" in line and "chat" in line.casefold()]
        self.assertEqual(len(menu_lines), 1)
        self.assertEqual(menu_lines[0].count("|"), 3)
        self.assertEqual(len(menu_lines[0]), int(config["width"]))

    def test_chat_header_shows_yellow_language_and_debug_state(self) -> None:
        terminal = Mock()
        terminal.color.side_effect = lambda color, text: f"<{color}>{text}</{color}>"
        output = StringIO()
        with (
            patch.object(james, "Terminal", return_value=terminal),
            patch.object(james, "active_project_name", return_value="project_test"),
            redirect_stdout(output),
        ):
            james.render_page_header({"name": "Jam3$-01", "language": "cz"}, "chat", chat_debug=True)

        self.assertEqual(
            output.getvalue().strip(),
            "Jam3$-01 - v0.3.0 | debug: true\n| project: <yellow>project_test</yellow> | <yellow>cz</yellow>",
        )

    def test_chat_header_shows_the_selected_rag_wiki_on_the_second_line(self) -> None:
        terminal = Mock()
        terminal.color.side_effect = lambda color, text: f"<{color}>{text}</{color}>"
        output = StringIO()
        profile = DatabaseProfile("btc", Path("rag_wiki/data/wiki_btc.db"), "btc")

        with (
            patch.object(james, "Terminal", return_value=terminal),
            patch.object(james, "active_project_name", return_value="project_test"),
            redirect_stdout(output),
        ):
            james.render_page_header(
                {"name": "Jam3$-01", "language": "cz"},
                "chat",
                chat_debug=False,
                chat_rag=profile,
            )

        self.assertEqual(
            output.getvalue().strip(),
            "Jam3$-01 - v0.3.0 | debug: false\n"
            "| project: <yellow>project_test</yellow> | <yellow>cz</yellow> | RAG: wiki_btc",
        )

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
            patch.object(james, "read_key", side_effect=["down", "down", "down", "down", "\r", " "]),
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
        self.assertEqual(render_flow_menu.call_args_list[1].args[1], 8)

    def test_flow_cursor_wraps_from_last_category_to_first(self) -> None:
        config = james.load_james_config()

        with (
            patch.object(james, "render_flow_menu"),
            patch.object(james, "run_user_input_flow") as user_input_flow,
            patch.object(james, "read_key", side_effect=[*["down"] * 9, "\r", " "]),
        ):
            james.flow_menu(config)

        user_input_flow.assert_called_once_with(config)

    def test_flow_cursor_opens_the_hardware_mcp_list(self) -> None:
        config = james.load_james_config()

        with (
            patch.object(james, "render_flow_menu"),
            patch.object(james, "flow_list_menu") as flow_list_menu,
            patch.object(james, "read_key", side_effect=[*["down"] * 7, "\r", " "]),
        ):
            james.flow_menu(config)

        flow_list_menu.assert_called_once_with(config, "flows_mcp_hardware", "MCP HARDWARE")

    def test_user_input_flow_runs_an_existing_txt_file_from_flows(self) -> None:
        config = james.load_james_config()
        with (
            patch("builtins.input", return_value="flow_base.txt"),
            patch.object(james, "run_flow") as run_flow,
            patch.object(james, "clear_screen"),
            patch.object(james, "render_page_header"),
            patch.object(james, "render_section_header"),
        ):
            james.run_user_input_flow(config)

        run_flow.assert_called_once_with("flow_base.txt")

    def test_user_input_flow_rejects_a_path_outside_flows(self) -> None:
        config = james.load_james_config()
        output = StringIO()
        with (
            patch("builtins.input", return_value="../outside.txt"),
            patch.object(james, "run_flow") as run_flow,
            patch.object(james, "clear_screen"),
            patch.object(james, "render_page_header"),
            patch.object(james, "render_section_header"),
            patch.object(james, "pause"),
            redirect_stdout(output),
        ):
            james.run_user_input_flow(config)

        self.assertIn("without a directory path", output.getvalue())
        run_flow.assert_not_called()

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

    def test_flow_list_info_shows_the_selected_flow_without_running_it(self) -> None:
        config = james.load_james_config()

        with (
            patch.object(james, "render_flow_list_menu"),
            patch.object(james, "show_flow_info") as show_flow_info,
            patch.object(james, "run_flow") as run_flow,
            patch.object(james, "read_key", side_effect=["down", "i", " "]),
        ):
            james.flow_list_menu(config, "flows_test", "TEST")

        show_flow_info.assert_called_once_with(config, "flow_base.txt", "TEST")
        run_flow.assert_not_called()

    def test_flow_list_footer_offers_yellow_info_key(self) -> None:
        config = james.load_james_config()
        terminal = Mock()
        terminal.style.side_effect = lambda text, **_kwargs: f"<{text}>"
        output = StringIO()

        with (
            patch.object(james, "Terminal", return_value=terminal),
            patch.object(james, "clear_screen"),
            patch.object(james, "render_page_header"),
            patch.object(james, "render_section_header"),
            patch.object(james, "render_back_footer"),
            redirect_stdout(output),
        ):
            james.render_flow_list_menu(config, "flows_test", "TEST", 0)

        self.assertIn("↑/↓ move | <i>nfo | Enter run", output.getvalue())
        terminal.style.assert_any_call("i", fg="yellow", bold=True)

    def test_flow_info_reads_the_flow_file_without_running_it(self) -> None:
        config = james.load_james_config()
        expected_path = james.PROJECT_ROOT / "flows" / "flow_base.txt"

        with patch.object(james, "show_text_document") as show_text_document:
            james.show_flow_info(config, "flow_base.txt", "TEST")

        show_text_document.assert_called_once_with(config, expected_path, "FLOW · TEST · flow_base.txt")

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
            patch.object(james, "read_key", side_effect=["down", "down", "down", "down", "\r", " "]),
        ):
            james.setup_menu(config)

        self.assertEqual(render_setup_menu.call_args_list[0].args[-1], 0)
        self.assertEqual(render_setup_menu.call_args_list[4].args[-1], 4)
        show_json_document.assert_called_once_with(config, james.OLLAMA_CONFIG_PATH, "OLLAMA")

    def test_setup_cursor_wraps_from_first_option_to_last(self) -> None:
        config = james.load_james_config()
        config["language"] = "cz"

        with (
            patch.object(james, "render_setup_menu") as render_setup_menu,
            patch.object(james, "show_text_document") as show_text_document,
            patch.object(james, "read_key", side_effect=["up", "\r", " "]),
        ):
            james.setup_menu(config)

        self.assertEqual(render_setup_menu.call_args_list[1].args[-1], 6)
        show_text_document.assert_called_once_with(config, james.SC_COMMANDS_CZ_PATH, "SLASH COMMANDS")

    def test_setup_cursor_opens_ollama_models_below_ollama(self) -> None:
        config = james.load_james_config()

        with (
            patch.object(james, "render_setup_menu") as render_setup_menu,
            patch.object(james, "show_ollama_models") as show_ollama_models,
            patch.object(james, "read_key", side_effect=["down", "down", "down", "down", "down", "\r", " "]),
        ):
            james.setup_menu(config)

        self.assertEqual(render_setup_menu.call_args_list[5].args[-1], 5)
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
        config["language"] = "cz"

        with (
            patch.object(james, "render_setup_menu"),
            patch.object(james, "show_text_document") as show_text_document,
            patch.object(james, "read_key", side_effect=["down"] * 6 + ["\r", " "]),
        ):
            james.setup_menu(config)

        show_text_document.assert_called_once_with(config, james.SC_COMMANDS_CZ_PATH, "SLASH COMMANDS")
        config["language"] = "en"
        self.assertEqual(james.slash_commands_document_path(config), james.SC_COMMANDS_DEFAULT_PATH)

    def test_setup_cursor_opens_james_chat_configuration(self) -> None:
        config = james.load_james_config()

        with (
            patch.object(james, "render_setup_menu"),
            patch.object(james, "show_json_document") as show_json_document,
            patch.object(james, "read_key", side_effect=["down", "down", "down", "\r", " "]),
        ):
            james.setup_menu(config)

        show_json_document.assert_called_once_with(config, james.CHAT_COMMANDS_CONFIG_PATH, "JAMES_CHAT")

    def test_james_setup_view_omits_flow_lists_and_chat_defaults(self) -> None:
        config = james.load_james_config()
        output = StringIO()

        with patch.object(james, "clear_screen"), patch.object(james, "wait_for_back"), redirect_stdout(output):
            james.show_james_config(config)

        rendered = output.getvalue()
        self.assertIn("Markdown colors: lib/wrapp_md.json", rendered)
        self.assertNotIn("col_bold: yellow", rendered)
        self.assertNotIn("flows_test:", rendered)
        self.assertNotIn("chat_model:", rendered)

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

    def test_about_documents_have_their_requested_paths(self) -> None:
        self.assertEqual(james.JAMES_ABOUT_PATH, james.PROJECT_ROOT / "james" / "about.md")
        self.assertEqual(james.JAMES_ABOUT_CZ_PATH, james.PROJECT_ROOT / "james" / "about_cz.md")
        self.assertTrue(james.JAMES_ABOUT_PATH.is_file())
        self.assertTrue(james.JAMES_ABOUT_CZ_PATH.is_file())

    def test_about_uses_the_configured_language_document(self) -> None:
        config = james.load_james_config()
        config["language"] = "cz"
        self.assertEqual(james.about_document_path(config), james.JAMES_ABOUT_CZ_PATH)
        config["language"] = "en"
        self.assertEqual(james.about_document_path(config), james.JAMES_ABOUT_PATH)

        with (
            patch.object(james, "clear_screen"),
            patch.object(james, "render_page_header"),
            patch.object(james, "render_section_header"),
            patch.object(james, "render_optional_wrapper_versions") as render_optional_wrapper_versions,
            patch.object(james, "wait_for_back"),
            redirect_stdout(StringIO()),
        ):
            james.show_about(config)

        render_optional_wrapper_versions.assert_called_once_with(config)

    def test_about_lists_present_and_absent_optional_wrapper_files(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            ble_path = directory / "wrapp_ble.py"
            ble_path.write_text('__version__ = "7.1"\n', encoding="utf-8")
            missing_nostr_path = directory / "wrapp_nostr.py"
            with patch.object(
                james,
                "OPTIONAL_WRAPPER_PATHS",
                (("wrapp_ble", ble_path), ("wrapp_nostr", missing_nostr_path)),
            ):
                self.assertEqual(james.optional_wrapper_versions(), [("wrapp_ble", "7.1"), ("wrapp_nostr", None)])

    def test_about_renders_absent_optional_wrapper_in_a_distinct_muted_color(self) -> None:
        config = {"colors": {"col_head": "cyan"}}
        terminal = Mock()
        terminal.style.side_effect = lambda text, **_kwargs: text
        terminal.color.side_effect = lambda color, text: f"<{color}>{text}</{color}>"
        output = StringIO()

        with (
            patch.object(james, "Terminal", return_value=terminal),
            patch.object(james, "optional_wrapper_versions", return_value=[("wrapp_ble", "0.2"), ("wrapp_nostr", None)]),
            redirect_stdout(output),
        ):
            james.render_optional_wrapper_versions(config)

        self.assertIn("<green>0.2</green>", output.getvalue())
        self.assertIn("<bright_black>not present</bright_black>", output.getvalue())

    def test_mcp_configuration_path_is_available(self) -> None:
        self.assertEqual(james.MCP_CONFIG_PATH, james.PROJECT_ROOT / "mcp" / "mcp_config.json")
        self.assertTrue(james.MCP_CONFIG_PATH.is_file())

    def test_mcp_menu_opens_each_module_with_cursor_selection(self) -> None:
        config = james.load_james_config()

        with (
            patch.object(james, "render_mcp_menu"),
            patch.object(james, "mcp_base_menu") as mcp_base_menu,
            patch.object(james, "mcp_hardware_menu") as mcp_hardware_menu,
            patch.object(james, "show_mcp_nostr_status") as show_mcp_nostr_status,
            patch.object(james, "read_key", side_effect=["\r", "down", "\r", "down", "\r", " "]),
        ):
            james.mcp_menu(config)

        mcp_base_menu.assert_called_once_with(config)
        mcp_hardware_menu.assert_called_once_with(config)
        show_mcp_nostr_status.assert_called_once_with(config)

    def test_mcp_cursor_wraps_from_first_action_to_last(self) -> None:
        config = james.load_james_config()

        with (
            patch.object(james, "render_mcp_menu") as render_mcp_menu,
            patch.object(james, "show_mcp_nostr_status") as show_mcp_nostr_status,
            patch.object(james, "read_key", side_effect=["up", "\r", " "]),
        ):
            james.mcp_menu(config)

        self.assertEqual(render_mcp_menu.call_args_list[1].args[1], 2)
        show_mcp_nostr_status.assert_called_once_with(config)

    def test_mcp_base_menu_keeps_the_three_established_actions(self) -> None:
        config = james.load_james_config()

        with (
            patch.object(james, "render_mcp_base_menu"),
            patch.object(james, "run_mcp_server") as run_mcp_server,
            patch.object(james, "list_mcp_services") as list_mcp_services,
            patch.object(james, "show_text_document") as show_text_document,
            patch.object(james, "read_key", side_effect=["\r", "down", "\r", "down", "\r", " "]),
        ):
            james.mcp_base_menu(config)

        run_mcp_server.assert_called_once_with(config)
        list_mcp_services.assert_called_once_with(config)
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

    def test_list_mcp_hardware_services_uses_the_stdio_server_config(self) -> None:
        config = james.load_james_config()
        completed = type("Completed", (), {"returncode": 0})()

        with (
            patch.object(james, "clear_screen"),
            patch.object(james, "render_page_header"),
            patch.object(james.subprocess, "run", return_value=completed) as run,
            patch.object(james, "pause"),
        ):
            james.list_mcp_hardware_services(config)

        self.assertEqual(
            run.call_args.args[0],
            [
                james.sys.executable,
                str(james.MCP_SCRIPT_PATH),
                "--server-config",
                str(james.MCP_HW_SERVER_CONFIG_PATH),
                "--list",
                "--no-db",
                "--timeout",
                "30",
            ],
        )

    def test_optional_hardware_module_reports_missing_files_without_running_a_command(self) -> None:
        config = james.load_james_config()
        missing = [james.BLE_SCRIPT_PATH]

        with (
            patch.object(james, "missing_module_files", return_value=missing),
            patch.object(james, "show_missing_mcp_module") as show_missing_mcp_module,
            patch.object(james.subprocess, "run") as run,
        ):
            james.list_mcp_hardware_services(config)

        show_missing_mcp_module.assert_called_once_with(config, "MCP hardware", missing)
        run.assert_not_called()

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
            patch.object(james, "read_key", side_effect=["down", "down", "\r", "down", "\r", " "]),
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

        self.assertEqual(render_rag_menu.call_args_list[1].args[1], 4)
        show_rag_data_tree.assert_called_once_with(config)

    def test_rag_menu_opens_data_tree(self) -> None:
        config = james.load_james_config()

        with (
            patch.object(james, "render_rag_menu"),
            patch.object(james, "show_rag_data_tree") as show_rag_data_tree,
            patch.object(james, "read_key", side_effect=["down", "down", "down", "down", "\r", " "]),
        ):
            james.rag_menu(config)

        show_rag_data_tree.assert_called_once_with(config)

    def test_rag_menu_runs_the_read_only_demo_test(self) -> None:
        config = james.load_james_config()

        with (
            patch.object(james, "render_rag_menu"),
            patch.object(james, "run_rag_demo_test") as run_rag_demo_test,
            patch.object(james, "read_key", side_effect=["down", "\r", " "]),
        ):
            james.rag_menu(config)

        run_rag_demo_test.assert_called_once_with(config)

    def test_rag_demo_asks_for_setup_preview_count_and_query_then_renders_vector_chunks(self) -> None:
        config = james.load_james_config()
        profile = DatabaseProfile("btc", Path("wiki_btc.db"), "btc")
        connection = Mock()
        query_embeddings = [[0.1, 0.2], [0.3, 0.4], [0.5, 0.6]]
        hit = type(
            "Hit",
            (),
            {"chunk_id": 42, "path": "btc/guide.md", "page_number": None, "chunk_index": 2, "text": "Useful bitcoin wallet text.", "distance": 0.125},
        )()
        output = StringIO()

        with (
            patch.object(james, "clear_screen"),
            patch.object(james, "render_page_header"),
            patch.object(james, "render_section_header"),
            patch.object(james, "select_chat_rag_profile", return_value=profile),
            patch.object(james, "load_vector_config", return_value=({"embedding_model": "embeddinggemma"}, {})),
            patch.object(james, "embed_texts", return_value=query_embeddings) as embed_texts,
            patch.object(james, "open_database", return_value=connection),
            patch.object(james, "search_vectors", return_value=[hit]) as search_vectors,
            patch.object(james, "rag_demo_chunk_distances", return_value={42: {"all": 0.125, "word: bitcoin": 0.2, "word: wallet": 0.3}}),
            patch.object(james, "wait_for_back") as wait_for_back,
            patch("builtins.input", side_effect=["btc", "100", "20", "bitcoin wallet"]),
            redirect_stdout(output),
        ):
            james.run_rag_demo_test(config)

        embed_texts.assert_called_once_with(james.OLLAMA_CONFIG_PATH, "embeddinggemma", ["bitcoin wallet", "bitcoin", "wallet"])
        search_vectors.assert_called_once_with(connection, query_embeddings[0], 20)
        connection.close.assert_called_once()
        wait_for_back.assert_called_once_with(int(config["width"]))
        self.assertIn("btc/guide.md · chunk 2 · distance 0.1250", output.getvalue())
        self.assertIn("Useful bitcoin wallet text.", output.getvalue())

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


class JamesCoworkTests(unittest.TestCase):
    def test_cowork_plans_are_persisted_per_project_with_explicit_steps(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            project_directory = Path(temporary_directory)
            plans = [
                {
                    "id": "20260831_120000",
                    "title": "Physics demo",
                    "goal": "Create a visual simulation.",
                    "status": "draft",
                    "created_at": "2026-08-31T12:00:00+02:00",
                    "updated_at": "2026-08-31T12:00:00+02:00",
                    "steps": [{"title": "Define the mechanics", "status": "todo"}],
                }
            ]

            path = james.save_cowork_plans(project_directory, plans)

            self.assertEqual(path, (project_directory / ".cowork" / "plans.json").resolve())
            self.assertEqual(james.load_cowork_plans(project_directory), plans)

    def test_create_cowork_plan_collects_goal_and_steps_without_starting_code(self) -> None:
        config = james.load_james_config()
        with TemporaryDirectory() as temporary_directory:
            project_directory = Path(temporary_directory)
            session = james.CoworkSession(project_directory=project_directory)
            with (
                patch.object(james, "clear_screen"),
                patch.object(james, "render_page_header"),
                patch.object(james, "render_section_header"),
                patch.object(james, "pause"),
                patch("builtins.input", side_effect=["Physics demo", "Create a visual simulation.", "Define mechanics", "Implement visualization", ""]),
                redirect_stdout(StringIO()),
            ):
                james.create_cowork_plan(config, session)

            plans = james.load_cowork_plans(project_directory)

        self.assertEqual(plans[0]["title"], "Physics demo")
        self.assertEqual([step["title"] for step in plans[0]["steps"]], ["Define mechanics", "Implement visualization"])

    def test_plan_step_prompt_passes_only_the_selected_step_to_code(self) -> None:
        plan = {
            "id": "20260831_120000",
            "title": "Physics demo",
            "goal": "Create a visual simulation.",
            "status": "draft",
            "created_at": "2026-08-31T12:00:00+02:00",
            "updated_at": "2026-08-31T12:00:00+02:00",
            "steps": [
                {"title": "Define mechanics", "status": "done"},
                {"title": "Implement visualization", "status": "todo"},
                {"title": "Write documentation", "status": "todo"},
            ],
        }

        prompt = james.cowork_plan_step_prompt(plan, 1)

        self.assertIn("Plan title: Physics demo", prompt)
        self.assertIn("Selected step (2/3): Implement visualization", prompt)
        self.assertIn("- Define mechanics", prompt)
        self.assertIn("- Write documentation", prompt)
        self.assertIn("do not implement these now", prompt)
        self.assertIn("do not modify .cowork/plans.json", prompt)

    def test_prepare_plan_step_is_explicitly_read_only(self) -> None:
        plan = {
            "id": "20260831_120000",
            "title": "Physics demo",
            "goal": "Create a visual simulation.",
            "status": "draft",
            "created_at": "2026-08-31T12:00:00+02:00",
            "updated_at": "2026-08-31T12:00:00+02:00",
            "steps": [{"title": "Define mechanics", "status": "todo"}],
        }

        prompt = james.cowork_plan_step_prompt(plan, 0, mode="prepare")

        self.assertIn("Prepare the selected step only", prompt)
        self.assertIn("Do not create, modify, delete, run, compile, or serve anything", prompt)

    def test_send_plan_step_records_code_outcome_and_user_confirmed_completion(self) -> None:
        config = james.load_james_config()
        plan = {
            "id": "20260831_120000",
            "title": "Physics demo",
            "goal": "Create a visual simulation.",
            "status": "draft",
            "created_at": "2026-08-31T12:00:00+02:00",
            "updated_at": "2026-08-31T12:00:00+02:00",
            "steps": [{"title": "Define mechanics", "status": "todo"}],
        }
        with TemporaryDirectory() as temporary_directory:
            project_directory = Path(temporary_directory)
            session = james.CoworkSession(project_directory=project_directory)
            james.save_cowork_plans(project_directory, [plan])
            fake_run = SimpleNamespace(status="completed", final_answer="Implemented mechanics.", review=None, summary=lambda: "AGENT RUN REPORT")
            with (
                patch.object(james, "choose_cowork_plan_step", return_value=(plan, 0)),
                patch.object(james, "run_cowork_prompt", return_value=fake_run) as run_prompt,
                patch.object(james, "print_cowork_run"),
                patch.object(james, "pause"),
                patch("builtins.input", side_effect=["i", "d"]),
                redirect_stdout(StringIO()),
            ):
                james.send_cowork_plan_step_to_code(config, session)

            saved = james.load_cowork_plans(project_directory)

        self.assertEqual(saved[0]["status"], "done")
        self.assertEqual(saved[0]["steps"][0]["status"], "done")
        self.assertEqual(saved[0]["steps"][0]["last_run"]["status"], "completed")
        self.assertEqual(saved[0]["steps"][0]["last_run"]["mode"], "implement")
        self.assertEqual(saved[0]["steps"][0]["last_run"]["summary"], "Implemented mechanics.")
        self.assertIn("Selected step (1/1): Define mechanics", run_prompt.call_args.args[3])
        self.assertEqual(run_prompt.call_args.args[2], [{"role": "system", "content": james.AGENT_SYSTEM_PROMPT}])

    def test_manual_step_status_can_skip_a_step_without_losing_it(self) -> None:
        config = james.load_james_config()
        plan = {
            "id": "20260831_120000",
            "title": "Physics demo",
            "goal": "Create a visual simulation.",
            "status": "draft",
            "created_at": "2026-08-31T12:00:00+02:00",
            "updated_at": "2026-08-31T12:00:00+02:00",
            "steps": [{"title": "Optional documentation", "status": "todo"}],
        }
        with TemporaryDirectory() as temporary_directory:
            project_directory = Path(temporary_directory)
            session = james.CoworkSession(project_directory=project_directory)
            james.save_cowork_plans(project_directory, [plan])
            with (
                patch.object(james, "choose_cowork_plan_step", return_value=(plan, 0)),
                patch("builtins.input", return_value="s"),
                patch.object(james, "pause"),
                redirect_stdout(StringIO()),
            ):
                james.update_cowork_plan_step_status(config, session)
            saved = james.load_cowork_plans(project_directory)

        self.assertEqual(saved[0]["steps"][0]["status"], "skipped")
        self.assertEqual(saved[0]["status"], "done")

    def test_prepare_mode_filters_out_writing_and_execution_tools(self) -> None:
        config = james.load_james_config()
        with TemporaryDirectory() as temporary_directory:
            project_directory = Path(temporary_directory)
            session = james.CoworkSession(project_directory=project_directory, model="test-model", db_enabled=False)
            created_engines: list[object] = []

            class FakeEngine:
                def __init__(self, **kwargs: object) -> None:
                    created_engines.append(kwargs)

                def run(self, _messages: list[dict[str, object]], run: object) -> str:
                    assert isinstance(run, james.AgentRun)
                    run.status = "completed"
                    run.final_answer = "Prepared."
                    return run.final_answer

            with (
                patch.object(james, "load_project_config", return_value={"debug": False}),
                patch.object(james, "ollama_api", return_value=SimpleNamespace(read_timeout_seconds=5, default_options={"num_ctx": 4096, "num_predict": 1024})),
                patch.object(james, "AgentEngine", FakeEngine),
                redirect_stdout(StringIO()),
            ):
                run = james.run_cowork_prompt(
                    config,
                    session,
                    [{"role": "system", "content": james.AGENT_SYSTEM_PROMPT}],
                    "Prepare the selected plan step.",
                    policy_override=james.ToolPolicy.OBSERVE,
                    allowed_tool_names=james.PLAN_PREPARE_TOOL_NAMES,
                )

        schema_names = {tool["function"]["name"] for tool in created_engines[0]["tool_schema"]}
        self.assertEqual(run.policy, james.ToolPolicy.OBSERVE)
        self.assertNotIn("write_file", schema_names)
        self.assertNotIn("apply_patch", schema_names)
        self.assertNotIn("run_python", schema_names)
        self.assertNotIn("run_command", schema_names)
        self.assertTrue(schema_names <= james.PLAN_PREPARE_TOOL_NAMES)

    def test_code_menu_shows_session_local_settings_and_actions(self) -> None:
        config = james.load_james_config()
        session = james.CoworkSession(
            project_directory=james.PROJECT_ROOT / "proj_snake",
            model="test-model",
            policy=james.ToolPolicy.DRAFT,
            run_confirm=False,
        )
        output = StringIO()

        with patch.object(james, "clear_screen"), redirect_stdout(output):
            james.render_cowork_code_menu(config, session, 1)

        rendered = output.getvalue()
        self.assertIn("start agent session", rendered)
        self.assertIn("one-shot task", rendered)
        self.assertIn("select model", rendered)
        self.assertIn("recent runs", rendered)
        self.assertIn("setup-info", rendered)
        self.assertIn("test-model", rendered)
        self.assertIn("off (test mode)", rendered)

    def test_cowork_menu_opens_code_with_a_fresh_session(self) -> None:
        config = james.load_james_config()
        with TemporaryDirectory() as temporary_directory:
            project_directory = Path(temporary_directory)
            with (
                patch.object(james, "load_cowork_agent_config", return_value={"log": True, "db": True, "model": "configured-model", "options": {"num_ctx": 4096, "num_predict": 2048}, "run_confirm": False, "auto_continue": True, "review": True, "tool_schema_light": True, "selector": "agent"}),
                patch.object(james, "active_project_directory", return_value=project_directory),
                patch.object(james, "render_cowork_menu"),
                patch.object(james, "cowork_code_menu") as code_menu,
                patch.object(james, "read_key", side_effect=["\r", " "]),
            ):
                james.cowork_menu(config)

        session = code_menu.call_args.args[1]
        profiles = james.load_cowork_agents_config()
        self.assertEqual(session.project_directory, project_directory)
        self.assertEqual(session.agent_id, "light")
        self.assertEqual(session.model, profiles["light"].model)
        self.assertEqual(session.tool_schema_profile, "light")
        self.assertFalse(session.run_confirm)
        self.assertTrue(session.db_enabled)
        self.assertEqual(session.db_selector, "agent")

    def test_cowork_agent_catalog_declares_light_code_hardware_and_nostr(self) -> None:
        profiles = james.load_cowork_agents_config()

        self.assertEqual(tuple(profiles), ("light", "code", "hardware", "nostr"))
        self.assertEqual(profiles["light"].tool_schema_profile, "light")
        self.assertEqual(profiles["code"].tool_schema_profile, "extended")
        self.assertEqual(profiles["hardware"].tool_schema_profile, "hardware")
        self.assertEqual(profiles["nostr"].tool_schema_profile, "nostr")
        self.assertEqual(profiles["code"].agent_options["num_ctx"], 8192)
        self.assertEqual(profiles["light"].agent_options["num_ctx"], 4096)
        self.assertEqual(profiles["hardware"].agent_options["num_ctx"], 4096)
        hardware_tools = {
            tool["function"]["name"]
            for tool in james.load_tool_schema(james.AGENT_TOOL_SCHEMA_PATH, profiles["hardware"].tool_schema_profile)
        }
        self.assertIn("hardware_run_action", hardware_tools)
        self.assertNotIn("run_command", hardware_tools)
        self.assertNotIn("run_python", hardware_tools)
        nostr_tools = {tool["function"]["name"] for tool in james.load_tool_schema(james.AGENT_TOOL_SCHEMA_PATH, profiles["nostr"].tool_schema_profile)}
        self.assertIn("nostr_reply", nostr_tools)
        self.assertIn("nostr_send_friend", nostr_tools)
        self.assertIn("hardware_run_action", nostr_tools)
        self.assertIn("nostr_sync", nostr_tools)

    def test_hardware_agent_disables_automatic_continuation_and_review(self) -> None:
        profile = james.load_cowork_agents_config()["hardware"]
        settings = {
            "log": True,
            "db": True,
            "model": "shared-model",
            "options": {"num_ctx": 4096, "num_predict": 2048},
            "run_confirm": False,
            "auto_continue": True,
            "review": True,
            "tool_schema_light": False,
            "selector": "agent",
        }
        with patch.object(james, "load_cowork_agent_config", return_value=settings):
            session = james.cowork_session_from_profile(james.PROJECT_ROOT, profile)

        self.assertFalse(session.auto_continue)
        self.assertFalse(session.review_enabled)
        self.assertEqual(session.agent_options["num_ctx"] if session.agent_options else None, 4096)
        prompt = james.cowork_system_prompt(session)
        self.assertIn("when the user asks what is available", prompt)
        self.assertIn("do not reload the catalog before", prompt)
        self.assertIn("Never claim a physical action succeeded", prompt)

    def test_nostr_agent_disables_automatic_continuation_and_review(self) -> None:
        profile = james.load_cowork_agents_config()["nostr"]
        settings = {"log": True, "db": True, "model": "shared-model", "options": {"num_ctx": 4096, "num_predict": 2048}, "run_confirm": False, "auto_continue": True, "review": True, "tool_schema_light": False, "selector": "agent"}
        with patch.object(james, "load_cowork_agent_config", return_value=settings):
            session = james.cowork_session_from_profile(james.PROJECT_ROOT, profile)
        self.assertFalse(session.auto_continue)
        self.assertFalse(session.review_enabled)
        self.assertIn("deliberately narrow", james.cowork_system_prompt(session))
        self.assertIn("Do not question whether forwarding", james.cowork_system_prompt(session))
        self.assertIn("local DB is an archive, not a", james.cowork_system_prompt(session))
        self.assertIn("wait -> sync -> inspect", james.cowork_system_prompt(session))
        self.assertIn("background listener", james.cowork_system_prompt(session))

    def test_setup_info_shows_parsed_code_setup_and_task_directory(self) -> None:
        config = james.load_james_config()
        session = james.CoworkSession(project_directory=james.PROJECT_ROOT, model="session-model")
        output = StringIO()

        with (
            patch.object(james, "clear_screen"),
            patch.object(james, "render_page_header"),
            patch.object(james, "render_section_header"),
            patch.object(james, "wait_for_back") as wait_for_back,
            patch.object(james, "load_cowork_agent_config", return_value={"log": True, "db": True, "model": "configured-model", "options": {"num_ctx": 4096, "num_predict": 2048}, "run_confirm": False, "auto_continue": True, "review": True, "tool_schema_light": False, "selector": "agent"}),
            patch.object(james, "available_chat_tasks", return_value=["task_a.json", "task_b.json"]),
            redirect_stdout(output),
        ):
            james.show_cowork_setup_info(config, session)

        rendered = output.getvalue()
        self.assertIn("configured-model", rendered)
        self.assertIn("session-model", rendered)
        self.assertIn("extended", rendered)
        self.assertIn(str(james.ASSISTANT_TASKS_PATH), rendered)
        wait_for_back.assert_called_once_with(int(config["width"]))

    def test_cowork_prompt_uses_shared_engine_and_records_completed_run(self) -> None:
        config = james.load_james_config()
        with TemporaryDirectory() as temporary_directory:
            project_directory = Path(temporary_directory)
            session = james.CoworkSession(project_directory=project_directory, model="test-model")
            created_engines: list[object] = []

            class FakeEngine:
                def __init__(self, **kwargs: object) -> None:
                    created_engines.append(kwargs)

                def run(self, messages: list[dict[str, object]], run: object) -> str:
                    assert isinstance(run, james.AgentRun)
                    run.status = "completed"
                    run.final_answer = "Completed."
                    run.duration_seconds = 0.5
                    return run.final_answer

            with (
                patch.object(james, "load_project_config", return_value={"debug": False}),
                patch.object(james, "ollama_api", return_value=SimpleNamespace(read_timeout_seconds=5, default_options={"num_ctx": 4096, "num_predict": 1024})),
                patch.object(james, "AgentEngine", FakeEngine),
                patch.object(james, "record_agent_run", return_value=101) as record_run,
                patch.object(james, "main_database_file", return_value=project_directory / "tasks.db"),
                redirect_stdout(StringIO()),
            ):
                messages: list[dict[str, object]] = [{"role": "system", "content": james.AGENT_SYSTEM_PROMPT}]
                run = james.run_cowork_prompt(config, session, messages, "Create app.py")

        self.assertEqual(run.final_answer, "Completed.")
        self.assertEqual(messages[-1], {"role": "user", "content": "Create app.py"})
        self.assertEqual(created_engines[0]["model"], "test-model")
        self.assertTrue(created_engines[0]["verbose"])
        self.assertEqual(record_run.call_args.kwargs["task"], "cowork_code")


if __name__ == "__main__":
    unittest.main()
