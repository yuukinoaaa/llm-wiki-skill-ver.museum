import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
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

    def test_clean_stubs_dry_run_reports_only_materialize_stub_pages(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            wiki = root / "wiki"
            concepts = wiki / "content" / "concepts"
            concepts.mkdir(parents=True)
            stub = concepts / "placeholder.md"
            normal = concepts / "normal.md"
            stub.write_text(
                "---\ntitle: placeholder\ntype: concept\n---\n\n"
                "此页面由 `materialize` 根据摄入计划中的链接自动创建，用于避免 Wiki 出现断链。",
                encoding="utf-8",
            )
            normal.write_text("---\ntitle: normal\ntype: concept\n---\n\nReal content.", encoding="utf-8")
            stdout = io.StringIO()

            with redirect_stdout(stdout):
                exit_code = main(["clean-stubs", "--wiki", str(wiki), "--dry-run"])

            output = json.loads(stdout.getvalue())
            self.assertEqual(exit_code, 0)
            self.assertEqual(output["would_delete"], 1)
            self.assertEqual(output["deleted"], [])
            self.assertEqual(output["candidates"], ["concepts/placeholder.md"])
            self.assertTrue(stub.exists())
            self.assertTrue(normal.exists())

    def test_clean_stubs_apply_deletes_only_materialize_stub_pages(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            wiki = root / "wiki"
            concepts = wiki / "content" / "concepts"
            concepts.mkdir(parents=True)
            stub = concepts / "placeholder.md"
            normal = concepts / "normal.md"
            stub.write_text(
                "---\ntitle: placeholder\ntype: concept\n---\n\n"
                "此页面由 `materialize` 根据摄入计划中的链接自动创建，用于避免 Wiki 出现断链。",
                encoding="utf-8",
            )
            normal.write_text("---\ntitle: normal\ntype: concept\n---\n\nReal content.", encoding="utf-8")
            stdout = io.StringIO()

            with redirect_stdout(stdout):
                exit_code = main(["clean-stubs", "--wiki", str(wiki), "--apply"])

            output = json.loads(stdout.getvalue())
            self.assertEqual(exit_code, 0)
            self.assertEqual(output["would_delete"], 0)
            self.assertEqual(output["deleted"], ["concepts/placeholder.md"])
            self.assertFalse(stub.exists())
            self.assertTrue(normal.exists())


if __name__ == "__main__":
    unittest.main()
