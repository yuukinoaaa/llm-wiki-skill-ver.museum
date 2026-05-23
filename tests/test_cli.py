import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path

from llm_wiki_ingest.cli import main


class CliErrorTests(unittest.TestCase):
    def test_extract_missing_source_prints_actionable_error_without_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "actual.docx").write_bytes(b"not a real docx but enough for candidate listing")
            stderr = io.StringIO()

            with redirect_stderr(stderr):
                exit_code = main(["extract", str(root / "source.docx"), "--out", str(root / "source.blocks.json")])

            output = stderr.getvalue()
            self.assertEqual(exit_code, 1)
            self.assertIn("Input file not found", output)
            self.assertIn("source.docx", output)
            self.assertIn("Current directory", output)
            self.assertIn("actual.docx", output)
            self.assertNotIn("Traceback", output)

    def test_materialize_invalid_plan_prints_actionable_error_without_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = root / "ingest-plan.json"
            plan.write_text(
                json.dumps(
                    {
                        "source_id": "source-demo",
                        "source_hash": "abc123",
                        "topic": "demo-topic",
                        "pages": [
                            {
                                "type": "wrong-kind",
                                "path": "wrong/page.md",
                                "title": "Wrong",
                                "body_md": "Wrong page.",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            stderr = io.StringIO()

            with redirect_stderr(stderr):
                exit_code = main(["materialize", str(plan), "--wiki", str(root / "wiki"), "--dry-run"])

            output = stderr.getvalue()
            self.assertEqual(exit_code, 1)
            self.assertIn("Plan error", output)
            self.assertIn("wrong-kind", output)
            self.assertNotIn("Traceback", output)


if __name__ == "__main__":
    unittest.main()
