import tempfile
import unittest
from pathlib import Path

from llm_wiki_ingest.serve import resolve_public_path


class CleanUrlResolutionTests(unittest.TestCase):
    def test_resolves_quartz_clean_urls_to_html_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            public = Path(tmp)
            (public / "exhibits").mkdir()
            target = public / "exhibits" / "changsheng-wuji-wadang.html"
            target.write_text("<html></html>", encoding="utf-8")

            self.assertEqual(resolve_public_path(public, "/exhibits/changsheng-wuji-wadang"), target.resolve())
            self.assertEqual(resolve_public_path(public, "/exhibits/changsheng-wuji-wadang/"), target.resolve())
            self.assertEqual(resolve_public_path(public, "/exhibits/changsheng-wuji-wadang.html"), target.resolve())

    def test_resolves_directory_indexes_and_assets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            public = Path(tmp)
            (public / "concepts").mkdir()
            index = public / "concepts" / "index.html"
            css = public / "index.css"
            index.write_text("<html></html>", encoding="utf-8")
            css.write_text("body {}", encoding="utf-8")

            self.assertEqual(resolve_public_path(public, "/concepts/"), index.resolve())
            self.assertEqual(resolve_public_path(public, "/concepts"), index.resolve())
            self.assertEqual(resolve_public_path(public, "/index.css"), css.resolve())

    def test_rejects_path_traversal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            public = Path(tmp)
            self.assertIsNone(resolve_public_path(public, "/../secret.txt"))


if __name__ == "__main__":
    unittest.main()
