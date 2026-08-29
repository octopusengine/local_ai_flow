"""Tests for the local SQLite/FTS5/sqlite-vec RAG storage wrapper."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from lib.wrapp_vector import _normalise_pdf_text, _web_source_text, ingest, inspect, open_database, reset_database, search_text, search_vectors, verify
from lib.wrapp_web import html_to_text


def fake_embed(texts: list[str]) -> list[list[float]]:
    """Produce fixed-size deterministic vectors without a running Ollama server."""

    return [[float(len(text) % 7), float(sum(map(ord, text)) % 11), 1.0] for text in texts]


class WrappVectorTests(unittest.TestCase):
    def test_html_to_text_excludes_navigation_and_footer_boilerplate(self) -> None:
        document = """
        <header>Bitcoin site header</header><nav>Documentation Resources Community</nav>
        <main><h1>Hardware wallets</h1><p>Keep recovery information private.</p></main>
        <footer>Privacy Terms Documentation Vocabulary</footer>
        """

        self.assertEqual(html_to_text(document), "Hardware wallets\nKeep recovery information private.")

    def test_web_source_text_keeps_provenance_out_of_embedded_content(self) -> None:
        source = type("Source", (), {"name": "wallets", "url": "https://example.test/wallets"})()

        with patch("lib.wrapp_vector.fetch_url_text", return_value="<main>Hardware wallet guide.</main>"):
            self.assertEqual(_web_source_text(source), "Hardware wallet guide.")

    def test_reset_database_removes_sources_that_are_no_longer_in_the_source_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source_root = root / "src"
            group = source_root / "base"
            group.mkdir(parents=True)
            old_source = group / "old.md"
            old_source.write_text("Legacy source that must disappear.", encoding="utf-8")

            connection = open_database(root / "data" / "wiki_base.db")
            try:
                ingest(connection, source_root, "base", "test-embed", fake_embed, chunk_size=120, chunk_overlap=20)
                old_source.unlink()
                (group / "current.md").write_text("Current source after full rebuild.", encoding="utf-8")

                reset_database(connection)
                ingest(connection, source_root, "base", "test-embed", fake_embed, chunk_size=120, chunk_overlap=20)

                rows = connection.execute("SELECT relative_path FROM sources").fetchall()
                self.assertEqual([row["relative_path"] for row in rows], ["base/current.md"])
                self.assertEqual(verify(connection), [])
            finally:
                connection.close()

    def test_ingest_fetches_named_web_sources_sequentially_and_indexes_visible_text(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source_root = root / "src"
            group = source_root / "btc"
            group.mkdir(parents=True)
            group.joinpath("web_src.json").write_text(
                '{"first": "https://example.test/first", "second": "https://example.test/second"}',
                encoding="utf-8",
            )
            fetched: list[str] = []

            def fake_fetch(url: str, **_kwargs: object) -> str:
                fetched.append(url)
                return f"<html><head><script>ignored()</script></head><body><h1>{url}</h1><p>Bitcoin proof of work.</p></body></html>"

            connection = open_database(root / "data" / "wiki_btc.db")
            try:
                with patch("lib.wrapp_vector.fetch_url_text", side_effect=fake_fetch):
                    result = ingest(
                        connection,
                        source_root,
                        "btc",
                        "test-embed",
                        fake_embed,
                        chunk_size=120,
                        chunk_overlap=20,
                        web_src_file="web_src.json",
                    )
                self.assertEqual(fetched, ["https://example.test/first", "https://example.test/second"])
                self.assertEqual(result["web_pages"], 2)
                self.assertEqual(result["web_failed"], 0)
                self.assertTrue(search_text(connection, "bitcoin", 3))
                stored = connection.execute("SELECT relative_path, source_type FROM sources ORDER BY relative_path").fetchall()
                self.assertEqual([row["source_type"] for row in stored], ["web", "web"])
                self.assertIn("https://example.test/first", stored[0]["relative_path"])
            finally:
                connection.close()

    def test_pdf_normalisation_repairs_ligatures_and_line_hyphenation(self) -> None:
        text = _normalise_pdf_text("kryptogra \ufb01cké\ntransakce-\nmi\u00ad\n")

        self.assertEqual(text, "kryptografické\ntransakcemi\n")

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
                notices: list[tuple[str, str]] = []
                result = ingest(
                    connection, source_root, "base", "test-embed", fake_embed,
                    chunk_size=35, chunk_overlap=5,
                    on_local_result=lambda relative_path, status: notices.append((relative_path, status)),
                )
                self.assertEqual(result["local_files"], 1)
                self.assertGreater(result["chunks"], 1)
                self.assertEqual(notices[0][0], "base/note.md")
                self.assertRegex(notices[0][1], r"^loaded \d+ characters$")
                self.assertEqual(inspect(connection)["embedding_model"], "test-embed")
                self.assertEqual(verify(connection), [])

                self.assertTrue(search_text(connection, "registers", 3))
                self.assertTrue(search_vectors(connection, fake_embed(["registers"])[0], 3))

                second_notices: list[tuple[str, str]] = []
                second = ingest(
                    connection, source_root, "base", "test-embed", fake_embed,
                    chunk_size=35, chunk_overlap=5,
                    on_local_result=lambda relative_path, status: second_notices.append((relative_path, status)),
                )
                self.assertEqual(second["skipped"], 1)
                self.assertEqual(second_notices, [("base/note.md", "unchanged; skipped")])
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
