"""Tests for task preparation in ``cli_ollama.py``."""

import argparse
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import cli_ollama
from lib.wrapp_db import list_task_rows
from lib.wrapp_ollama import OPTION_NAMES, ollama_api


class CliOllamaSkillTests(unittest.TestCase):
    def test_active_task_files_nest_generation_options(self) -> None:
        tasks_directory = Path(__file__).resolve().parent / "assistant" / "tasks"
        for task_path in tasks_directory.glob("task_*.json"):
            task = json.loads(task_path.read_text(encoding="utf-8"))
            with self.subTest(task=task_path.name):
                self.assertIsInstance(task.get("options"), dict)
                self.assertFalse(set(task) & set(OPTION_NAMES))

    def test_english_explain_task_uses_english_teacher_profile(self) -> None:
        task_path = Path(__file__).resolve().parent / "assistant" / "tasks" / "task_explain12_en.json"
        task = cli_ollama.load_task(task_path)

        resolved_task = cli_ollama.apply_assistant_components(task)

        self.assertEqual(resolved_task["default_output_file"], "free_en.txt")
        self.assertIn("Respond in English.", resolved_task["instruction"])
        self.assertIn("bright twelve-year-old", resolved_task["instruction"])

    def test_clear_code_output_keeps_only_matching_fenced_python(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            output_path = Path(temporary_directory) / "answer.py"
            output_path.write_text(
                "Tady je požadovaný soubor:\n\n```python\nimport math\n\nprint(math.pi)\n```\n\n"
                "Případně upravte hodnotu.",
                encoding="utf-8",
            )

            ollama_api._clear(output_path)

            cleaned = output_path.read_text(encoding="utf-8-sig")

        self.assertEqual(cleaned, "import math\n\nprint(math.pi)\n")

    def test_clear_code_output_removes_html_preamble_and_epilogue(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            output_path = Path(temporary_directory) / "page.html"
            output_path.write_text(
                "Výsledek:\n<!doctype html>\n<html><body>Hello</body></html>\nHotovo.",
                encoding="utf-8",
            )

            ollama_api._clear(output_path)

            cleaned = output_path.read_text(encoding="utf-8-sig")

        self.assertEqual(cleaned, "<!doctype html>\n<html><body>Hello</body></html>\n")

    def test_clear_code_output_extracts_fenced_html_with_trailing_prose(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            output_path = Path(temporary_directory) / "fragment.html"
            output_path.write_text(
                "Zde je výsledek:\n\n```html\n<div>Hello</div>\n```\n\n"
                "Tento soubor pak otevřete v prohlížeči.",
                encoding="utf-8",
            )

            ollama_api._clear(output_path)

            cleaned = output_path.read_text(encoding="utf-8-sig")

        self.assertEqual(cleaned, "<div>Hello</div>\n")

    def test_clear_code_output_keeps_only_fenced_rust(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            output_path = Path(temporary_directory) / "main.rs"
            output_path.write_text(
                "```rust\nfn main() {\n    println!(\"Hello\");\n}\n```\nVysvětlení.",
                encoding="utf-8",
            )

            ollama_api._clear(output_path)

            cleaned = output_path.read_text(encoding="utf-8-sig")

        self.assertEqual(cleaned, "fn main() {\n    println!(\"Hello\");\n}\n")

    def test_clear_code_output_leaves_non_code_files_unchanged(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            output_path = Path(temporary_directory) / "answer.txt"
            content = "```python\nprint('keep fences')\n```\n"
            output_path.write_text(content, encoding="utf-8")

            ollama_api._clear(output_path)

            cleaned = output_path.read_text(encoding="utf-8-sig")

        self.assertEqual(cleaned, content)

    def test_parse_boolean_accepts_true_and_false_only(self) -> None:
        self.assertTrue(cli_ollama.parse_boolean("true"))
        self.assertFalse(cli_ollama.parse_boolean("FALSE"))
        with self.assertRaises(argparse.ArgumentTypeError):
            cli_ollama.parse_boolean("yes")

    def test_setector_alias_sets_selector_argument(self) -> None:
        with patch("sys.argv", ["cli_ollama.py", "--setector", "test123"]):
            arguments = cli_ollama.parse_arguments()

        self.assertEqual(arguments.selector, "test123")

    def test_direction_selects_translation_direction(self) -> None:
        with patch("sys.argv", ["cli_ollama.py", "--direction", "e2c"]):
            arguments = cli_ollama.parse_arguments()

        self.assertEqual(arguments.translation_direction, "e2c")

    def test_text_argument_is_parsed_for_translate_tasks(self) -> None:
        with patch("sys.argv", ["cli_ollama.py", "--text", "Proč má člověk teplotu?"]):
            arguments = cli_ollama.parse_arguments()

        self.assertEqual(arguments.literal_text, "Proč má člověk teplotu?")

    def test_merge_arguments_are_parsed(self) -> None:
        with patch("sys.argv", ["cli_ollama.py", "-m", "first.txt", "second text", "result.txt"]):
            merge_arguments = cli_ollama.parse_arguments()

        self.assertEqual(merge_arguments.merge_values, ["first.txt", "second text", "result.txt"])

    def test_new_context_arguments_keep_legacy_aliases(self) -> None:
        with patch(
            "sys.argv",
            [
                "cli_ollama.py",
                "--input", "question.txt",
                "--replace-rules", "Use plain text.",
                "--rules", "Be brief.",
                "--rules", "Use Czech.",
                "--context", "facts.txt",
                "--skill", "teacher_cz",
                "--sc-cz",
                "--sc", "summarize",
                "--sc", "bulletpoints",
                "--dry-run",
            ],
        ):
            arguments = cli_ollama.parse_arguments()

        self.assertEqual(arguments.data, "question.txt")
        self.assertEqual(arguments.instruction, "Use plain text.")
        self.assertEqual(arguments.rules, ["Be brief.", "Use Czech."])
        self.assertEqual(arguments.context_files, ["facts.txt"])
        self.assertIsNone(arguments.extra_capabilities)
        self.assertEqual(arguments.extra_legacy_skills, ["teacher_cz"])
        self.assertEqual(arguments.sc_language, "cz")
        self.assertEqual(arguments.sc_commands, ["summarize", "bulletpoints"])
        self.assertTrue(arguments.dry_run)

    def test_input_prompt_followed_by_hyphen_is_parsed_as_interactive_input(self) -> None:
        with patch(
            "sys.argv",
            ["cli_ollama.py", "--input", "Zadej dodatečnou otázku", "-", "--out", "answer.txt"],
        ):
            arguments = cli_ollama.parse_arguments()

        self.assertEqual(arguments.data, "-")
        self.assertEqual(arguments.input_prompt, "Zadej dodatečnou otázku")
        self.assertEqual(arguments.out, "answer.txt")

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

    def test_task_and_cli_skills_are_ordered_before_rules(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            project_directory = Path(temporary_directory)
            capabilities_directory = project_directory / "assistant" / "capabilities"
            capabilities_directory.mkdir(parents=True)
            (capabilities_directory / "base.md").write_text("Base capability.", encoding="utf-8")
            (capabilities_directory / "extra.md").write_text("Extra capability.", encoding="utf-8")
            with patch.object(cli_ollama, "PROJECT_DIR", project_directory):
                resolved_task = cli_ollama.apply_skills(
                    {"capabilities": ["base"], "instruction": "Task rules."},
                    ["extra"],
                )

        self.assertEqual(
            resolved_task["instruction"],
            "Base capability.\n\n\nExtra capability.\n\n\nTask rules.",
        )

    def test_profile_precedes_capability_in_assistant_system_context(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            project_directory = Path(temporary_directory)
            profiles_directory = project_directory / "assistant" / "profiles"
            capabilities_directory = project_directory / "assistant" / "capabilities"
            profiles_directory.mkdir(parents=True)
            capabilities_directory.mkdir(parents=True)
            (profiles_directory / "teacher.md").write_text("Patient teacher.", encoding="utf-8")
            (capabilities_directory / "explain.md").write_text("Use examples.", encoding="utf-8")
            with patch.object(cli_ollama, "PROJECT_DIR", project_directory):
                resolved_task = cli_ollama.apply_assistant_components(
                    {"profile": "teacher", "capability": "explain", "instruction": "Task rules."}
                )

        self.assertEqual(
            resolved_task["instruction"],
            "Patient teacher.\n\n\nUse examples.\n\n\nTask rules.",
        )

    def test_legacy_cli_skill_can_resolve_a_migrated_profile(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            project_directory = Path(temporary_directory)
            profiles_directory = project_directory / "assistant" / "profiles"
            profiles_directory.mkdir(parents=True)
            (profiles_directory / "teacher.md").write_text("Patient teacher.", encoding="utf-8")
            with patch.object(cli_ollama, "PROJECT_DIR", project_directory):
                resolved_task = cli_ollama.apply_assistant_components(
                    {},
                    extra_legacy_skills=["teacher"],
                )

        self.assertEqual(resolved_task["instruction"], "Patient teacher.")

    def test_input_rules_and_context_are_compiled_into_separate_sections(self) -> None:
        arguments = SimpleNamespace(
            data="input.txt",
            instruction=None,
            rules=["Additional rule."],
            context_files=["facts.txt"],
            out=None,
            input_file=None,
            translation_direction=None,
            model=None,
            seed_rnd=False,
            seed=None,
            temp=None,
            num_predict=None,
            num_ctx=None,
            repeat_penalty=None,
        )
        with TemporaryDirectory() as temporary_directory:
            project_directory = Path(temporary_directory)
            (project_directory / "input.txt").write_text("Current question", encoding="utf-8")
            (project_directory / "facts.txt").write_text("Reference fact", encoding="utf-8")
            resolved_task, output_path = cli_ollama.prepare_prompt_task(
                {"model": "test-model", "prompt": "Old input", "instruction": "Task rules."},
                arguments,
                project_directory,
            )
            resolved_task = cli_ollama.append_runtime_rules(resolved_task, arguments, project_directory)

        self.assertIsNone(output_path)
        self.assertEqual(resolved_task["instruction"], "Task rules.\n\n\nAdditional rule.")
        self.assertEqual(
            resolved_task["prompt"],
            "# Reference context\n\n[REFERENCE FILE: facts.txt]\nReference fact\n[END REFERENCE FILE]\n\n# Current input\n\n[INPUT]\nCurrent question\n[END INPUT]",
        )

    def test_translate_task_accepts_literal_text(self) -> None:
        arguments = SimpleNamespace(
            data=None,
            literal_text="Proč má člověk teplotu?",
            input_file=None,
            translation_direction="c2a",
            out="question_en.txt",
            instruction=None,
            model=None,
            seed_rnd=False,
            seed=None,
            temp=None,
            num_predict=None,
            num_ctx=None,
            repeat_penalty=None,
            context_files=None,
        )
        task = {
            "type": "translate",
            "model": "translate-model",
            "default_direction": "c2a",
            "default_input_file": "question_cz.txt",
            "default_input_file_e2c": "answer_en.txt",
            "default_output_file": "translated.txt",
        }

        with TemporaryDirectory() as temporary_directory:
            resolved_task, output_path = cli_ollama.prepare_translate_task(
                task,
                arguments,
                Path(temporary_directory),
            )

        self.assertEqual(resolved_task["prompt"], "Proč má člověk teplotu?")
        self.assertEqual(resolved_task["instruction"], cli_ollama.TRANSLATION_INSTRUCTIONS["c2a"])
        self.assertEqual(output_path.name, "question_en.txt")

    def test_markdown_files_are_valid_translation_input_and_output(self) -> None:
        arguments = SimpleNamespace(
            data=None,
            literal_text=None,
            input_file="question.md",
            translation_direction="c2a",
            out="answer.md",
            instruction=None,
            model=None,
            seed_rnd=False,
            seed=None,
            temp=None,
            num_predict=None,
            num_ctx=None,
            repeat_penalty=None,
            context_files=None,
        )
        task = {
            "type": "translate",
            "model": "translate-model",
            "default_direction": "c2a",
            "default_input_file": "question.txt",
            "default_input_file_e2c": "answer.txt",
            "default_output_file": "translated.txt",
        }

        with TemporaryDirectory() as temporary_directory:
            project_directory = Path(temporary_directory)
            (project_directory / "question.md").write_text("# Otázka\nProč?", encoding="utf-8")
            resolved_task, output_path = cli_ollama.prepare_translate_task(task, arguments, project_directory)

        self.assertEqual(resolved_task["prompt"], "# Otázka\nProč?")
        self.assertEqual(output_path.name, "answer.md")

    def test_data_reads_existing_markdown_file_from_project(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            project_directory = Path(temporary_directory)
            (project_directory / "addition.md").write_text("# Doplnění", encoding="utf-8")

            value = cli_ollama.read_text_value("addition.md", project_directory, "data")

        self.assertEqual(value, "# Doplnění")

    def test_prompt_input_hyphen_reads_one_interactive_line(self) -> None:
        with (
            patch.object(cli_ollama.sys.stdin, "isatty", return_value=True),
            patch.object(cli_ollama.Terminal, "y") as terminal_output,
            patch("builtins.input", return_value="Další otázka") as input_mock,
        ):
            value = cli_ollama.read_prompt_input("-", Path("."), "Zadej dodatečnou otázku")

        self.assertEqual(value, "Další otázka")
        terminal_output.assert_called_once_with("Zadej dodatečnou otázku:")
        input_mock.assert_called_once_with()

    def test_standard_input_hyphen_reads_all_piped_text(self) -> None:
        with patch("sys.stdin", io.StringIO("První řádek\nDruhý řádek\n")):
            value = cli_ollama.read_standard_input("Prompt input")

        self.assertEqual(value, "První řádek\nDruhý řádek\n")

    def test_translate_task_accepts_standard_input_hyphen(self) -> None:
        arguments = SimpleNamespace(
            data=None,
            literal_text=None,
            input_file="-",
            translation_direction="c2a",
            out="answer.txt",
            instruction=None,
            model=None,
            seed_rnd=False,
            seed=None,
            temp=None,
            num_predict=None,
            num_ctx=None,
            repeat_penalty=None,
            context_files=None,
        )
        task = {
            "type": "translate",
            "model": "translate-model",
            "default_direction": "c2a",
            "default_input_file": "question.txt",
            "default_input_file_e2c": "answer.txt",
            "default_output_file": "translated.txt",
        }

        with TemporaryDirectory() as temporary_directory, patch("sys.stdin", io.StringIO("Jak se máš?")):
            resolved_task, output_path = cli_ollama.prepare_translate_task(
                task, arguments, Path(temporary_directory)
            )

        self.assertEqual(resolved_task["prompt"], "Jak se máš?")
        self.assertEqual(output_path.name, "answer.txt")

    def test_translate_task_rejects_text_and_input_file_together(self) -> None:
        arguments = SimpleNamespace(
            data=None,
            literal_text="Text",
            input_file="question_cz.txt",
            translation_direction=None,
            out=None,
            instruction=None,
        )
        task = {
            "default_direction": "c2a",
            "default_input_file": "question_cz.txt",
            "default_input_file_e2c": "answer_en.txt",
            "default_output_file": "translated.txt",
        }

        with TemporaryDirectory() as temporary_directory:
            with self.assertRaisesRegex(ValueError, "either --in or --text"):
                cli_ollama.prepare_translate_task(task, arguments, Path(temporary_directory))

    def test_prompt_task_uses_configured_default_output_file(self) -> None:
        arguments = SimpleNamespace(
            data=None,
            instruction=None,
            out=None,
            input_file=None,
            translation_direction=None,
            model=None,
            seed_rnd=False,
            seed=None,
            temp=None,
            num_predict=None,
            num_ctx=None,
            repeat_penalty=None,
            context_files=None,
        )

        with TemporaryDirectory() as temporary_directory:
            project_directory = Path(temporary_directory)
            _, output_path = cli_ollama.prepare_prompt_task(
                {"model": "test-model", "default_output_file": "temporary.txt"},
                arguments,
                project_directory,
            )

        self.assertIsNotNone(output_path)
        self.assertEqual(output_path.name, "temporary.txt")

    def test_prompt_task_cli_output_overrides_configured_default_output_file(self) -> None:
        arguments = SimpleNamespace(
            data=None,
            instruction=None,
            out="custom.txt",
            input_file=None,
            translation_direction=None,
            model=None,
            seed_rnd=False,
            seed=None,
            temp=None,
            num_predict=None,
            num_ctx=None,
            repeat_penalty=None,
            context_files=None,
        )

        with TemporaryDirectory() as temporary_directory:
            project_directory = Path(temporary_directory)
            _, output_path = cli_ollama.prepare_prompt_task(
                {"model": "test-model", "default_output_file": "temporary.txt"},
                arguments,
                project_directory,
            )

        self.assertIsNotNone(output_path)
        self.assertEqual(output_path.name, "custom.txt")

    def test_sc_commands_are_injected_in_czech_before_runtime_rules(self) -> None:
        arguments = SimpleNamespace(
            sc_language="cz",
            sc_commands=["summarize", "bulletpoints", "brief"],
            rules=["Použij jen čistý text."],
        )

        commands, language = cli_ollama.resolve_sc_commands(arguments)
        resolved_task = cli_ollama.apply_sc_commands(
            {"instruction": "Task rule."},
            commands,
            language,
        )
        resolved_task = cli_ollama.append_runtime_rules(
            resolved_task,
            arguments,
            Path.cwd(),
        )

        self.assertEqual(resolved_task["slash_commands"], ["summarize", "bulletpoints", "brief"])
        self.assertEqual(resolved_task["sc_language"], "cz")
        self.assertEqual(
            resolved_task["instruction"],
            "Task rule.\n\n\n"
            "Shrň dlouhý text nebo článek se zachováním důležitých bodů.\n\n\n"
            "Vrať výsledek jako stručné odrážky.\n\n\n"
            "Poskytni co nejstručnější užitečnou odpověď.\n\n\n"
            "Odpovídej pouze česky.\n\n\n"
            "Použij jen čistý text.",
        )

    def test_sc_requires_language_and_rejects_multiple_primary_actions(self) -> None:
        with self.assertRaisesRegex(ValueError, "--sc-cz or --sc-en"):
            cli_ollama.resolve_sc_commands(SimpleNamespace(sc_language=None, sc_commands=["summarize"]))
        with self.assertRaisesRegex(ValueError, "Only one primary"):
            cli_ollama.resolve_sc_commands(
                SimpleNamespace(sc_language="en", sc_commands=["summarize", "email"])
            )

    def test_language_neutral_ocr_command_does_not_require_or_inject_a_language(self) -> None:
        commands, language = cli_ollama.resolve_sc_commands(
            SimpleNamespace(sc_language=None, sc_commands=["/ocr"])
        )
        resolved_task = cli_ollama.apply_sc_commands({}, commands, language)

        self.assertIsNone(language)
        self.assertEqual(resolved_task["slash_commands"], ["ocr"])
        self.assertNotIn("sc_language", resolved_task)
        self.assertEqual(
            resolved_task["instruction"],
            "Transcribe all visible text faithfully. Preserve reading order and meaningful structure. "
            "Do not translate, summarize, or add commentary; mark unreadable text as [unreadable].",
        )

    def test_sc_language_without_command_uses_non_injected_explain_default(self) -> None:
        commands, language = cli_ollama.resolve_sc_commands(
            SimpleNamespace(sc_language="en", sc_commands=None)
        )
        resolved_task = cli_ollama.apply_sc_commands({}, commands, language)

        self.assertEqual([command["sc"] for command in commands], ["explain"])
        self.assertEqual(resolved_task["slash_commands"], ["explain"])
        self.assertEqual(resolved_task["instruction"], "Respond only in English.")

    def test_eli_slash_commands_are_available_as_modifiers(self) -> None:
        expected_rules = {
            "eli5": "Vysvětli to jako pětiletému:",
            "eli12": "Vysvětli to jako dvanáctiletému:",
        }

        for command_name, expected_rule in expected_rules.items():
            commands, language = cli_ollama.resolve_sc_commands(
                SimpleNamespace(sc_language="cz", sc_commands=[f"/{command_name}"])
            )
            resolved_task = cli_ollama.apply_sc_commands({}, commands, language)

            self.assertEqual(commands[0]["kind"], "modifier")
            self.assertEqual(resolved_task["slash_commands"], [command_name])
            self.assertIn(expected_rule, resolved_task["instruction"])

    def test_extended_slash_commands_are_available_in_their_groups(self) -> None:
        expected_commands = {
            "review": ("action", "Proveď revizi dodaného kódu"),
            "refactor": ("action", "Refaktoruj dodaný kód"),
            "debug": ("action", "Diagnostikuj dodanou chybu"),
            "test": ("artifact", "Vytvoř cílené automatizované testy"),
            "security": ("modifier", "Posuď výsledek z hlediska relevantních bezpečnostních rizik"),
            "sql": ("artifact", "Napiš správný a čitelný SQL dotaz nebo schéma"),
            "regex": ("artifact", "Vytvoř regulární výraz"),
            "api": ("artifact", "Navrhni praktický kontrakt API"),
            "json": ("modifier", "Vrať pouze platný JSON"),
            "diagram": ("artifact", "Vytvoř přehledný Mermaid diagram"),
            "checklist": ("modifier", "Vrať stručný, proveditelný checklist"),
            "decision": ("action", "Porovnej uvedené možnosti"),
            "describe": ("action", "Věrně popiš, co je na obrázku vidět"),
            "doctor": ("persona_modifier", "Odpovídej jako lékařský specialista"),
        }

        for command_name, (expected_kind, expected_rule) in expected_commands.items():
            commands, language = cli_ollama.resolve_sc_commands(
                SimpleNamespace(sc_language="cz", sc_commands=[f"/{command_name}"])
            )
            resolved_task = cli_ollama.apply_sc_commands({}, commands, language)

            self.assertEqual(commands[0]["kind"], expected_kind)
            self.assertEqual(resolved_task["slash_commands"], [command_name])
            self.assertIn(expected_rule, resolved_task["instruction"])

    def test_programming_slash_commands_are_available_as_artifacts(self) -> None:
        expected_rules = {
            "html": "Vytvoř kompletní responzivní HTML stránku pro požadovaný účel.",
            "python": "Napiš správný a čitelný program v Pythonu pro požadovaný úkol.",
            "rust": "Napiš idiomatický a bezpečný kód v Rustu pro požadovaný úkol.",
            "js": "Vytvoř jeden kompletní HTML dokument s jednoduchou JavaScriptovou aplikací ve vloženém prvku <script>.",
        }

        for command_name, expected_rule in expected_rules.items():
            commands, language = cli_ollama.resolve_sc_commands(
                SimpleNamespace(sc_language="cz", sc_commands=[f"/{command_name}"])
            )
            resolved_task = cli_ollama.apply_sc_commands({}, commands, language)

            self.assertEqual(commands[0]["kind"], "artifact")
            self.assertEqual(resolved_task["slash_commands"], [command_name])
            self.assertIn(expected_rule, resolved_task["instruction"])

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
            "options": {
                "temperature": 0.2,
                "num_predict": 2048,
                "top_k": 64,
                "top_p": 0.85,
                "min_p": 0.05,
                "tfs_z": 0.95,
                "typical_p": 0.9,
            },
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
        self.assertEqual(effective_options["top_k"], 64)
        self.assertEqual(effective_options["top_p"], 0.85)
        self.assertEqual(effective_options["min_p"], 0.05)
        self.assertEqual(effective_options["tfs_z"], 0.95)
        self.assertEqual(effective_options["typical_p"], 0.9)

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

    def test_thinking_level_is_preserved_in_payload_and_task_state(self) -> None:
        task = {"model": "gpt-oss:latest", "prompt": "Write a program.", "think": "low"}
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
            payload = app.build_task_payload(task, "prompt")

        task_state = cli_ollama.build_task_state(
            task,
            task_kind="prompt",
            effective_options={"seed": 42},
            debug_enabled=False,
            output_path=None,
            image_path=None,
            project_directory=Path("C:/project"),
        )

        self.assertEqual(payload["think"], "low")
        self.assertEqual(task_state["think"], "low")

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
                self.last_usage = {"prompt_eval_count": 12, "eval_count": 3, "response_chunks": 3}

            def effective_task_debug_enabled(self, _task: dict[str, object]) -> bool:
                return False

            def effective_task_options(self, _task: dict[str, object]) -> dict[str, object]:
                return {"seed": 7, "temperature": 0.2, "num_predict": 32}

            def run_task(self, _task: dict[str, object], **_kwargs) -> int:
                self.on_response_text("final answer")
                return 0

        with TemporaryDirectory() as temporary_directory:
            project_root = Path(temporary_directory)
            tasks_directory = project_root / "assistant" / "tasks"
            tasks_directory.mkdir(parents=True)
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
                patch.object(cli_ollama, "ASSISTANT_TASKS_DIR", tasks_directory),
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
        self.assertEqual(rows[0]["task"], "task_test.json")
        self.assertEqual(
            rows[0]["key2"],
            '{"eval_count": 3, "prompt_eval_count": 12, "response_chunks": 3}',
        )
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
