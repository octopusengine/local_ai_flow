"""Capture and vision integration tests without a running Ollama server."""
import base64
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from lib.wrapp_agent import AgentEngine, AgentRun, ProjectToolScope, ToolPolicy, build_file_tools, load_tool_schema, tools_for_schema
from tests.test_wrapp_agent import FakeResponse

SCHEMA = Path(__file__).resolve().parents[1] / "assistant/tools/tool_schema.json"
PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+j9r8AAAAASUVORK5CYII=")


class AgentVisionTests(unittest.TestCase):
    def test_real_pygame_capture(self):
        repository = SCHEMA.parents[2]
        interpreter = repository / "proj_pygame/venv/Scripts/python.exe"
        if not interpreter.is_file():
            import importlib.util
            if importlib.util.find_spec("pygame") is None:
                self.skipTest("Pygame interpreter is unavailable")
            interpreter = Path(sys.executable)
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = (
                "import pygame\npygame.init()\n"
                "screen = pygame.display.set_mode((320, 240))\n"
                "for frame in range(10):\n"
                "    screen.fill((30, 40, 60))\n"
                "    pygame.draw.rect(screen, (60, 190, 100), (0, 200, 320, 40))\n"
                "    pygame.draw.rect(screen, (80, 160, 255), (30 + frame * 10, 160, 25, 40))\n"
                "    PRESENT\n"
                "raise RuntimeError('capture must stop before this point')\n"
            )
            tools = build_file_tools(ProjectToolScope(root), run_confirm=lambda _: True)
            for present in ("pygame.display.flip()", "pygame.display.update()"):
                with self.subTest(present=present):
                    (root / "game.py").write_text(source.replace("PRESENT", present), encoding="utf-8")
                    with patch("lib.wrapp_agent.sys.executable", str(interpreter)):
                        result = tools["run_pygame"].function("game.py", frame=3)
                    self.assertIn("Outcome: captured", result)
                    self.assertIn("display update 3 (320x240)", result)
                    self.assertTrue((root / "pygame.png").read_bytes().startswith(b"\x89PNG"))
                    self.assertEqual((root / "game.py").read_text(), source.replace("PRESENT", present))

    def test_vision_returns_description_without_image_in_main_history(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "pygame.png").write_bytes(PNG)
            schema = load_tool_schema(SCHEMA, "extended")
            requests_seen = []
            def post(url, **kwargs):
                payload = kwargs["json"]
                requests_seen.append(payload)
                if url.endswith("/show"):
                    return FakeResponse({"capabilities": ["vision"] if payload["model"] == "eyes" else []})
                if payload["model"] == "eyes":
                    self.assertEqual(payload["messages"][-1]["images"], [base64.b64encode(PNG).decode()])
                    return FakeResponse({"message": {"content": "A white pixel."}})
                if not any(m.get("role") == "tool" for m in payload["messages"]):
                    return FakeResponse({"message": {"role": "assistant", "tool_calls": [
                        {"function": {"name": "inspect_image", "arguments": {"path": "pygame.png"}}}
                    ]}})
                return FakeResponse({"message": {"role": "assistant", "content": "Checked."}})
            engine = AgentEngine(api=SimpleNamespace(base_url="http://ollama.test", default_options={}),
                                 model="text", tool_schema=schema,
                                 tools=tools_for_schema(schema, build_file_tools(ProjectToolScope(root))),
                                 timeout_seconds=5, post=post)
            run = AgentRun("text", root, ToolPolicy.CODE, "Check image")
            messages = [{"role": "user", "content": run.prompt}]
            with patch.dict(os.environ, {"JAMES_VISION_MODEL": ""}), patch(
                "lib.wrapp_agent.requests.get", return_value=FakeResponse({"models": [{"name": "eyes"}]})
            ):
                engine.run(messages, run)
            self.assertIn("A white pixel", run.tool_calls[0].result)
            self.assertNotIn(base64.b64encode(PNG).decode(), str(messages))
            self.assertEqual(engine.model, "text")

    def test_missing_vision_and_invalid_images(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "pygame.png").write_bytes(PNG)
            (root / "fake.png").write_text("not an image")
            (root / ".env").write_bytes(PNG)
            tools = build_file_tools(ProjectToolScope(root))
            for path in ("../escape.png", ".env", "fake.png"):
                with self.subTest(path=path), self.assertRaises(ValueError):
                    tools["inspect_image"].function(path)
            engine = AgentEngine(api=SimpleNamespace(base_url="http://ollama.test", default_options={}),
                                 model="text", tool_schema=[], tools={}, timeout_seconds=5,
                                 post=lambda *a, **k: FakeResponse({"capabilities": []}))
            with patch.dict(os.environ, {"JAMES_VISION_MODEL": "text"}):
                result = engine._inspect_image(tools["inspect_image"].function("pygame.png"))
            self.assertIn("not visually inspected", result)

    def test_capture_publishes_only_fresh_successful_output(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "game.py").write_text("# game")
            (root / "pygame.png").write_bytes(b"old")
            artifacts = set()
            tools = build_file_tools(ProjectToolScope(root), run_confirm=lambda _: True, on_artifact=artifacts.add)
            def capture(command, **kwargs):
                self.assertEqual(kwargs["env"]["SDL_VIDEODRIVER"], "dummy")
                Path(command[3]).write_bytes(PNG)
                return subprocess.CompletedProcess(command, 0, "captured", "")
            with patch("lib.wrapp_agent.subprocess.run", side_effect=capture):
                result = tools["run_pygame"].function("game.py", frame=2)
            self.assertIn("Outcome: captured", result)
            self.assertEqual((root / "pygame.png").read_bytes(), PNG)
            self.assertEqual(artifacts, {"pygame.png"})
            for effect in (subprocess.TimeoutExpired("game", 1),):
                with patch("lib.wrapp_agent.subprocess.run", side_effect=effect):
                    result = tools["run_pygame"].function("game.py")
                self.assertIn("No new screenshot", result)
                self.assertEqual((root / "pygame.png").read_bytes(), PNG)
            with patch("lib.wrapp_agent.subprocess.run", return_value=subprocess.CompletedProcess([], 0, "", "")):
                self.assertIn("Outcome: failed", tools["run_pygame"].function("game.py"))
            with self.assertRaises(ValueError):
                tools["run_pygame"].function("game.py", frame=True)
            observe = build_file_tools(ProjectToolScope(root), ToolPolicy.OBSERVE)
            self.assertIn("does not allow", observe["run_pygame"].function("game.py"))
            declined = build_file_tools(ProjectToolScope(root), run_confirm=lambda _: False)
            self.assertIn("declined", declined["run_pygame"].function("game.py"))


if __name__ == "__main__":
    unittest.main()
