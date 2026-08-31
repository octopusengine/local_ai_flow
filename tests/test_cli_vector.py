"""Tests for the local SQLite vector CLI surface."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import cli_vector
from rag_wiki import rag_swg


class CliVectorTests(unittest.TestCase):
    def test_batched_embedder_submits_small_batches_and_preserves_order(self) -> None:
        progress = cli_vector._EmbeddingProgress(enabled=False)
        progress.start("btc/notes.md", 5)
        submitted: list[list[str]] = []

        def fake_embed(_config: Path, _model: str, texts: list[str]) -> list[list[float]]:
            submitted.append(texts)
            return [[float(len(text))] for text in texts]

        with patch.object(cli_vector, "embed_texts", side_effect=fake_embed):
            result = cli_vector._batched_embedder("embeddinggemma", 2, progress)(["a", "bb", "ccc", "dddd", "eeeee"])

        self.assertEqual(submitted, [["a", "bb"], ["ccc", "dddd"], ["eeeee"]])
        self.assertEqual(result, [[1.0], [2.0], [3.0], [4.0], [5.0]])

    def test_embedding_progress_waits_twenty_seconds_then_reports_approximately_a_fifth(self) -> None:
        progress = cli_vector._EmbeddingProgress(enabled=True)
        with patch.object(cli_vector.time, "monotonic", side_effect=[100.0, 119.0, 121.0]), patch("builtins.print") as printed:
            progress.start("btc/notes.md", 100)
            progress.update(25)
            progress.update(45)

        self.assertEqual(printed.call_count, 1)
        self.assertIn("45/100 chunks (45 %)", printed.call_args.args[0])
        self.assertIn("ETA", printed.call_args.args[0])

    def test_help_describes_sqlite_rag_commands(self) -> None:
        help_text = cli_vector.build_parser().format_help()

        self.assertIn("SQLite, FTS5, and sqlite-vec", help_text)
        self.assertIn("ingest", help_text)
        self.assertIn("search", help_text)
        self.assertIn("context", help_text)
        self.assertIn("ingest-wiki", help_text)
        self.assertIn("--db", help_text)
        self.assertIn("--set-wiki", help_text)
        self.assertIn("--svg", help_text)
        self.assertTrue(cli_vector.build_parser().parse_args(["ingest", "--no-embed"]).no_embed)
        self.assertTrue(cli_vector.build_parser().parse_args(["ingest-wiki", "bitcoin", "--embed"]).embed)

    def test_svg_query_terms_and_map_include_words_chunks_and_distances(self) -> None:
        hit = type("Hit", (), {
            "chunk_id": 11,
            "path": "btc/guide.md",
            "chunk_index": 3,
            "distance": 1.1234,
            "text": "A hardware wallet keeps private keys separate from an online computer.",
        })()
        self.assertEqual(rag_swg._svg_query_terms("bitcoin mining, hardware wallet"), ["bitcoin", "mining", "hardware", "wallet"])
        self.assertEqual(
            rag_swg._svg_query_terms("bitcoin mining, hardware wallet, horse or donkey"),
            ["bitcoin", "mining", "hardware", "wallet", "horse", "or", "donkey"],
        )
        self.assertEqual(rag_swg._svg_query_groups("bitcoin mining, hardware wallet"), ["bitcoin mining", "hardware wallet"])

        with tempfile.TemporaryDirectory() as temporary_directory:
            output_path = Path(temporary_directory) / "rag.svg"
            rag_swg._write_rag_svg(
                "btc",
                "bitcoin mining, hardware wallet",
                [hit],
                {11: {
                    "bitcoin": 1.0,
                    "mining": 1.1,
                    "hardware": 1.2,
                    "wallet": 1.3,
                    "bitcoin mining": 0.9,
                    "hardware wallet": 1.0,
                }},
                output_path,
            )
            content = output_path.read_text(encoding="utf-8")

        self.assertIn("bitcoin", content)
        self.assertIn("chunk 3", content)
        self.assertIn("1.000", content)
        self.assertIn("2D diagnostic map", content)
        self.assertIn("Edge fit:", content)

    def test_empty_command_prints_help_without_side_effects(self) -> None:
        self.assertEqual(cli_vector.main([]), 0)

    def test_set_wiki_persists_the_named_profile_in_an_explicit_config(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            config_path = Path(temporary_directory) / "cli_vector.json"
            config_path.write_text((cli_vector.PROJECT_DIR / "cli_vector.json").read_text(encoding="utf-8"), encoding="utf-8")

            self.assertEqual(cli_vector.main(["--config", str(config_path), "--set-wiki", "gardening"]), 0)
            self.assertEqual(json.loads(config_path.read_text(encoding="utf-8"))["main_db"], "gardening")

    def test_context_is_limited_and_includes_source_provenance(self) -> None:
        hit = type("Hit", (), {"path": "gardening/zahrada_cz.md", "page_number": None, "chunk_index": 2, "text": "Rajčata potřebují slunce."})()

        context = cli_vector._context_text("gardening", "rajčata", [hit], 500)

        self.assertIn("Database profile: `gardening`", context)
        self.assertIn("gardening/zahrada_cz.md", context)
        self.assertIn("Rajčata potřebují slunce.", context)

    def test_context_path_stays_in_the_active_project_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_directory = Path(temporary_directory) / "project_example"
            project_directory.mkdir()

            context_path = cli_vector._context_path(Path("wiki_gardening_context.txt"), project_directory)
            self.assertEqual(context_path.name, "wiki_gardening_context.txt")
            self.assertEqual(context_path.parent.resolve(), project_directory.resolve())
            with self.assertRaises(cli_vector.VectorError):
                cli_vector._context_path(Path("../outside.txt"), project_directory)

    def test_ingest_wiki_creates_and_selects_a_profile_from_its_source_group(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            config_path = root / "cli_vector.json"
            catalog_path = root / "rag_wiki" / "databases.json"
            source_path = root / "rag_wiki" / "src" / "bitcoin"
            source_path.mkdir(parents=True)
            source_path.joinpath("notes.md").write_text("Bitcoin is a digital asset.", encoding="utf-8")
            catalog_path.write_text(json.dumps({"databases": {"base": {"file": "wiki_base.db", "source_group": "base"}}}), encoding="utf-8")
            config_path.write_text(json.dumps({
                "source_root": "rag_wiki/src",
                "data_dir": "rag_wiki/data",
                "main_db": "base",
                "embedding_model": "unused",
                "databases_config": "rag_wiki/databases.json",
            }), encoding="utf-8")

            with patch.object(cli_vector, "PROJECT_DIR", root):
                self.assertEqual(cli_vector.main(["--config", str(config_path), "ingest-wiki", "bitcoin"]), 0)

            saved_config = json.loads(config_path.read_text(encoding="utf-8"))
            saved_catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
            self.assertEqual(saved_config["main_db"], "bitcoin")
            self.assertEqual(saved_catalog["databases"]["bitcoin"], {"file": "wiki_bitcoin.db", "source_group": "bitcoin"})
            self.assertTrue((root / "rag_wiki" / "data" / "wiki_bitcoin.db").is_file())

            source_path.joinpath("notes.md").write_text("Bitcoin mining uses proof of work.", encoding="utf-8")
            with patch.object(cli_vector, "PROJECT_DIR", root):
                self.assertEqual(cli_vector.main(["--config", str(config_path), "ingest-wiki", "bitcoin", "--reindex"]), 0)


if __name__ == "__main__":
    unittest.main()
