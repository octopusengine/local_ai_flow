"""Offline regression checks for Laya output and flow routing."""
import json
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import cli_laya
import cli_laya_flow as bridge


class LayaFlowTests(unittest.TestCase):
    def test_language_routes_and_low_confidence(self):
        for choice, confidence, expected in (("English", .9, "en"), ("Czech", .9, "cs"),
                                              ("Czech", .3, "review"), ("English", .3, "review")):
            with self.subTest(choice=choice, confidence=confidence):
                self.assertEqual(bridge.decide({"language": {"choice": choice, "confidence": confidence}}, 2), expected)

    def test_context_routes_and_acceptance_gates(self):
        for choice, confidence, grounded, quality, expected in (
            ("accept", .9, .9, 1.8, "accept"), ("accept", .9, .2, 1.8, "revise"),
            ("accept", .9, .9, .5, "revise"), ("revise", .9, .9, 2, "revise"),
            ("clarify", .9, .9, 2, "clarify"), ("accept", .1, .9, 2, "review")):
            with self.subTest(choice=choice, expected=expected):
                self.assertEqual(bridge.decide({
                    "action": {"choice": choice, "confidence": confidence},
                    "grounded": {"noul": grounded}, "quality": {"score": quality}}, 3), expected)

    def test_invalid_result_clears_old_branch(self):
        with TemporaryDirectory() as directory:
            project = Path(directory)
            bridge.write(project / "en_en.flag", "en")
            bridge.write(project / "en.json", '{"answers":{"language":{"choice":"bad","confidence":0.9}}}')
            with self.assertRaises(ValueError):
                bridge.route(project, 2, "en")
            self.assertFalse((project / "en_en.flag").exists())
        for value in (float("nan"), float("inf"), -1, 2, True, "0.9"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                bridge.decide({"language": {"choice": "English", "confidence": value}}, 2)

    def test_prepare_preserves_inputs_and_removes_stale_outputs(self):
        with TemporaryDirectory() as directory:
            project = Path(directory)
            bridge.write(project / "en.md", "Custom input")
            bridge.write(project / "en_translated.md", "Old translation")
            bridge.write(project / "en_en.flag", "Old decision")
            bridge.prepare(project, 2)
            self.assertEqual(bridge.read(project / "en.md"), "Custom input")
            self.assertTrue((project / "cs.md").exists())
            self.assertFalse((project / "en_translated.md").exists())
            self.assertFalse((project / "en_en.flag").exists())

    def test_context_contains_all_sources_and_final_replaces_draft(self):
        with TemporaryDirectory() as directory:
            project = Path(directory)
            bridge.prepare(project, 3)
            bridge.write(project / "draft.md", "Old proposal")
            bridge.write(project / "final.md", "Corrected proposal")
            bridge.pack(project, "final_evaluation")
            context = bridge.read(project / "final_evaluation.md")
            for marker in ("CUSTOMER MESSAGE", "HISTORY", "VERIFIED FACTS", "DRAFT", "Corrected proposal", "INC-42"):
                self.assertIn(marker, context)
            self.assertNotIn("Old proposal", context)

    def test_single_file_json_output_with_stub_model(self):
        with TemporaryDirectory() as directory:
            project = Path(directory)
            src, out = project / "input.md", project / "answer.json"
            bridge.write(src, "Hello world")
            result = {"answers": {"language": {"choice": "English", "confidence": .9}}, "routing": {"model": "multilingual"}}
            router = Mock()
            router.predict.return_value = result
            modules = {"torch": Mock(), "laya": SimpleNamespace(Router=Mock(return_value=router)),
                       "laya.agent": SimpleNamespace(Agent=Mock(return_value=SimpleNamespace(cfg={})))}
            with patch("sys.argv", ["cli_laya.py", str(src), "-q", str(bridge.ROOT / "project_laya/test2/question2.json"), "--out", str(out)]), patch.dict("sys.modules", modules), patch.object(cli_laya, "ensure_model", return_value="multilingual"), redirect_stdout(StringIO()):
                self.assertEqual(cli_laya.run_cli(), 0)
            payload = json.loads(bridge.read(out))
            self.assertEqual(payload["answers"], result["answers"])
            self.assertEqual(payload["file"], str(src))


if __name__ == "__main__":
    unittest.main()
