"""Tests for the local SQLite/FTS5/sqlite-vec RAG storage wrapper."""

import tempfile
import unittest
from pathlib import Path

from lib.wrapp_vector import ingest, inspect, open_database, search_text, search_vectors, verify


def fake_embed(texts: list[str]) -> list[list[float]]:
    """Produce fixed-size deterministic vectors without a running Ollama server."""

    return [[float(len(text) % 7), float(sum(map(ord, text)) % 11), 1.0] for text in texts]


class WrappVectorTests(unittest.TestCase):
    def test_ingest_indexes_changed_files_and_supports_both_searches(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source_root = root / "src"
            group = source_root / "base"
            group.mkdir(parents=True)
            source = group / "note.md"
            source.write_text("Microprocessors use registers. Registers are fast memory.", encoding="utf-8")

            connection = open_database(root / "data" / "wiki_base.db")
            try:
                result = ingest(connection, source_root, "base", "test-embed", fake_embed, chunk_size=35, chunk_overlap=5)
                self.assertEqual(result["files"], 1)
                self.assertGreater(result["chunks"], 1)
                self.assertEqual(inspect(connection)["embedding_model"], "test-embed")
                self.assertEqual(verify(connection), [])

                self.assertTrue(search_text(connection, "registers", 3))
                self.assertTrue(search_vectors(connection, fake_embed(["registers"])[0], 3))

                second = ingest(connection, source_root, "base", "test-embed", fake_embed, chunk_size=35, chunk_overlap=5)
                self.assertEqual(second["skipped"], 1)
            finally:
                connection.close()

    def test_chunk_only_ingest_defers_embeddings_but_keeps_fts_search_usable(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source_root = root / "src"
            group = source_root / "gardening"
            group.mkdir(parents=True)
            (group / "garden.md").write_text("Rajčata potřebují slunce a pravidelnou zálivku.", encoding="utf-8")

            connection = open_database(root / "data" / "wiki_gardening.db")
            try:
                ingest(connection, source_root, "gardening", "later", None, chunk_size=120, chunk_overlap=20)
                self.assertEqual(inspect(connection)["embedding_status"], "pending")
                self.assertTrue(search_text(connection, "rajčata", 3))
                self.assertEqual(verify(connection), [])
            finally:
                connection.close()


if __name__ == "__main__":
    unittest.main()
