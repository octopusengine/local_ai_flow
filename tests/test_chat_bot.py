from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import cli_ollama
import james
import runner


class ChatBotTests(unittest.TestCase):
    def test_holly_loads_with_profile_and_automatic_commands(self):
        reference, task = james.select_chat_bot('HOLLY.json', 'cz')
        self.assertEqual(reference, 'bot/holly.json')
        commands, language = cli_ollama.resolve_sc_commands(
            SimpleNamespace(sc_commands=['chat', 'hlasku'], sc_language='cz'), task)
        resolved = cli_ollama.apply_sc_commands(cli_ollama.apply_assistant_components(task), commands, language)
        self.assertIn('Jsi Holly', resolved['instruction'])
        self.assertIn('hláškou', resolved['instruction'])
        self.assertEqual(resolved['slash_commands'], ['brief', 'chat', 'hlasku'])
        self.assertEqual(james.extract_chat_sc_command('/hlasku vesmír', task), ('vesmír', ['hlasku']))

    def test_bot_paths_are_restricted(self):
        for name in ['../holly', 'bot/holly', 'missing', 'holly.txt']:
            with self.subTest(name=name), self.assertRaises(ValueError):
                james.select_chat_bot(name, 'cz')
        with self.assertRaises(ValueError):
            cli_ollama.resolve_task_file('bot/../project.json')
        self.assertEqual(cli_ollama.resolve_task_file('bot/holly.json'), james.PROJECT_ROOT / 'bot' / 'holly.json')

    def test_invalid_bot_does_not_replace_active_bot_or_context(self):
        config = {'language': 'cz'}
        with (
            patch.object(james, 'set_chat_selector', return_value=True),
            patch.object(james, 'ensure_chat_context_file'),
            patch.object(james, 'append_chat_bot_context', return_value=None) as bot_context,
            patch.object(james, 'clear_screen'),
            patch.object(james, 'render_page_header'),
            patch.object(james, 'render_chat_commands'),
            patch.object(james, 'write_chat_input'),
            patch.object(james, 'read_chat_active_image', return_value=None),
            patch.object(james, 'run_flow', return_value=0) as run_flow,
            patch.object(james, 'render_chat_reply'),
            patch.object(james, 'append_chat_turn'),
            patch.object(james, 'clear_chat_context') as clear_context,
            patch.object(james, 'chat_task_context_window', return_value=8192),
            patch('builtins.input', side_effect=['/mod old-model', '/bot holly', '/bot missing', '/hlasku Test', '/task task_base.json', 'Hello', '/bye']),
            redirect_stdout(StringIO()),
        ):
            james.run_chat(config)
        bot_call, task_call = run_flow.call_args_list
        self.assertEqual(bot_call.kwargs['task_override'], 'bot/holly.json')
        self.assertEqual(bot_call.kwargs['model_override'], 'qwen3.5:latest')
        self.assertEqual(bot_call.kwargs['num_ctx'], 8192)
        self.assertEqual(bot_call.kwargs['sc_commands'], ['hlasku'])
        self.assertTrue(bot_call.kwargs['quiet'])
        self.assertEqual(task_call.kwargs['task_override'], 'task_base.json')
        self.assertNotIn('num_ctx', task_call.kwargs)
        clear_context.assert_not_called()
        bot_context.assert_called_once_with(config, 'bot/holly.json')
        self.assertEqual(config, {'language': 'cz'})

    def test_optional_bot_markdown_preserves_sources_and_conversation(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'bot').mkdir()
            context = root / 'chat_context.txt'
            turns = '- user:\nHello\n- assistant:\nHi'
            james.write_chat_context(context, 'Existing source', turns)
            original = context.read_bytes()
            with (
                patch.object(cli_ollama, 'PROJECT_DIR', root),
                patch.object(james, 'ensure_chat_context_file', return_value=context) as ensure,
            ):
                self.assertIsNone(james.append_chat_bot_context({}, 'bot/holly.json'))
                ensure.assert_not_called()
                self.assertEqual(context.read_bytes(), original)
                introduction = root / 'bot' / 'holly.md'
                introduction.write_text('Jsi palubní počítač.\n\nMáš IQ 6000.', encoding='utf-8-sig')
                self.assertEqual(james.append_chat_bot_context({}, 'bot/holly.json'), introduction.resolve())
                sources, kept_turns = james.split_chat_context(context.read_text(encoding='utf-8'))
                self.assertIn('Existing source', sources)
                self.assertIn('Path: bot/holly.md', sources)
                self.assertIn('Máš IQ 6000.', sources)
                self.assertEqual(kept_turns, turns)

    def test_bot_switch_replaces_options_and_commands(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'bot').mkdir()
            catalog = cli_ollama.load_sc_catalog()
            for name, task in [('one', {'model': 'one', 'options': {'temperature': .1}, 'sc': ['brief']}),
                               ('two', {'model': 'two', 'options': {'top_k': 10}})]:
                (root / 'bot' / (name + '.json')).write_text(json.dumps(task), encoding='utf-8')
            with patch.object(james, 'PROJECT_ROOT', root), patch.object(cli_ollama, 'PROJECT_DIR', root), patch.object(cli_ollama, 'load_sc_catalog', return_value=catalog):
                _, first = james.select_chat_bot('one', 'cz')
                _, second = james.select_chat_bot('two', 'cz')
            self.assertEqual(second, {'model': 'two', 'options': {'top_k': 10}})
            self.assertIn('sc', first)

    def test_runner_preserves_chat_arguments_with_bot_and_window(self):
        command = runner.FlowCommand('test', ('python', 'cli_ollama.py'),
            ('python', 'cli_ollama.py', '--type', 'task_chat.json', '--context', 'chat_context.txt', '--sc', 'chat', '--num-ctx', '1024'))
        nodes = runner.apply_task_override([command], 'bot/holly.json')
        nodes = runner.apply_ollama_option(nodes, '--num-ctx', '8192')
        args = nodes[0].execution_arguments
        self.assertIn('chat_context.txt', args)
        self.assertIn('chat', args)
        self.assertIn('bot/holly.json', args)
        self.assertNotIn('task_chat.json', args)
        self.assertNotIn('1024', args)
        self.assertEqual(args[-2:], ('--num-ctx', '8192'))

    def test_sc_validation_and_no_catalog_mutation(self):
        args = SimpleNamespace(sc_commands=[], sc_language='cz')
        for task in [{'sc': 'brief'}, {'sc': ['missing']}, {'short_commands': []},
                     {'short_commands': {'brief': 'override'}}, {'sc': ['tldr', 'translate']}]:
            with self.subTest(task=task), self.assertRaises(ValueError):
                cli_ollama.resolve_sc_commands(args, task)
        task = {'sc': ['custom'], 'short_commands': {'custom': 'Custom instruction'}}
        commands, _ = cli_ollama.resolve_sc_commands(args, task)
        self.assertEqual(commands[0]['sc_en'], 'Custom instruction')
        self.assertNotIn('custom', cli_ollama.load_sc_catalog())


if __name__ == '__main__':
    unittest.main()
