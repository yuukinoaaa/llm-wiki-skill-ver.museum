import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from llm_wiki_ingest.extractors import extract_document
from llm_wiki_ingest.materialize import materialize_plan
from llm_wiki_ingest.slug import slugify
from llm_wiki_ingest.validate import validate_wiki


def make_docx(path: Path, paragraphs: list[str]) -> None:
    xml_parts = [
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">',
        "<w:body>",
    ]
    for paragraph in paragraphs:
        xml_parts.append("<w:p><w:r><w:t>")
        xml_parts.append(paragraph)
        xml_parts.append("</w:t></w:r></w:p>")
    xml_parts.append("</w:body></w:document>")
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("word/document.xml", "".join(xml_parts))


def make_pdf(path: Path) -> None:
    path.write_bytes(
        b"%PDF-1.4\n"
        b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n"
        b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n"
        b"3 0 obj << /Type /Page /Parent 2 0 R /Contents 4 0 R >> endobj\n"
        b"4 0 obj << /Length 44 >> stream\n"
        b"BT /F1 12 Tf 72 720 Td (Hello PDF block) Tj ET\n"
        b"endstream endobj\n"
        b"trailer << /Root 1 0 R >>\n%%EOF\n"
    )


class ExtractDocumentTests(unittest.TestCase):
    def test_extracts_txt_md_docx_and_pdf_into_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            txt = root / "note.txt"
            md = root / "note.md"
            docx = root / "note.docx"
            pdf = root / "note.pdf"

            txt.write_text("First paragraph.\n\nSecond paragraph.", encoding="utf-8")
            md.write_text("# Heading\n\nMarkdown body.", encoding="utf-8")
            make_docx(docx, ["Docx paragraph one.", "Docx paragraph two."])
            make_pdf(pdf)

            cases = {
                txt: ["First paragraph.", "Second paragraph."],
                md: ["Heading", "Markdown body."],
                docx: ["Docx paragraph one.", "Docx paragraph two."],
                pdf: ["Hello PDF block"],
            }

            for path, expected_texts in cases.items():
                with self.subTest(path=path.suffix):
                    document = extract_document(path)
                    self.assertEqual(document.source.type, path.suffix.lstrip("."))
                    self.assertEqual([block.text for block in document.blocks], expected_texts)
                    self.assertTrue(document.source.sha256)
                    self.assertEqual(document.blocks[0].id, "b0001")


class SlugTests(unittest.TestCase):
    def test_slugifies_ascii_and_uses_stable_fallback_for_non_ascii(self) -> None:
        self.assertEqual(slugify("01 Welcome Stop"), "01-welcome-stop")
        self.assertRegex(slugify("文献之邦", fallback_prefix="page"), r"^page-[0-9a-f]{8}$")


class MaterializeTests(unittest.TestCase):
    def test_materializes_pages_manifest_route_links_and_backlinks(self) -> None:
        plan = {
            "source_id": "source-demo",
            "source_hash": "abc123",
            "topic": "demo-topic",
            "pages": [
                {
                    "type": "stop",
                    "path": "stops/01-welcome.md",
                    "title": "欢迎词",
                    "body_md": "第一段讲解。",
                    "source_block_ids": ["b0001"],
                    "outgoing_links": ["works/shi-ji.md"],
                },
                {
                    "type": "stop",
                    "path": "stops/02-history.md",
                    "title": "史籍文献",
                    "body_md": "第二段讲解。",
                    "source_block_ids": ["b0002"],
                    "outgoing_links": [],
                },
                {
                    "type": "work",
                    "path": "works/shi-ji.md",
                    "title": "史记",
                    "body_md": "《史记》实体页。",
                    "source_block_ids": ["b0001"],
                    "outgoing_links": [],
                },
            ],
        }

        with tempfile.TemporaryDirectory() as tmp:
            wiki = Path(tmp) / "wiki"
            summary = materialize_plan(plan, wiki, apply=True)

            self.assertEqual(summary["created"], 4)
            stop_one = (wiki / "content" / "stops" / "01-welcome.md").read_text(encoding="utf-8")
            stop_two = (wiki / "content" / "stops" / "02-history.md").read_text(encoding="utf-8")
            work = (wiki / "content" / "works" / "shi-ji.md").read_text(encoding="utf-8")
            manifest = json.loads((wiki / "llm-wiki-manifest.json").read_text(encoding="utf-8"))

            self.assertIn("[[works/shi-ji|史记]]", stop_one)
            self.assertIn("下一页：[[stops/02-history|史籍文献]]", stop_one)
            self.assertIn("上一页：[[stops/01-welcome|欢迎词]]", stop_two)
            self.assertIn("[[stops/01-welcome|欢迎词]]", work)
            self.assertEqual(manifest["sources"]["source-demo"]["hash"], "abc123")
            self.assertEqual(manifest["pages"]["works/shi-ji.md"]["type"], "work")

    def test_dry_run_does_not_write_files(self) -> None:
        plan = {
            "source_id": "source-demo",
            "source_hash": "abc123",
            "topic": "demo-topic",
            "pages": [
                {
                    "type": "concept",
                    "path": "concepts/version.md",
                    "title": "版本",
                    "body_md": "版本概念。",
                    "source_block_ids": [],
                    "outgoing_links": [],
                }
            ],
        }
        with tempfile.TemporaryDirectory() as tmp:
            wiki = Path(tmp) / "wiki"
            summary = materialize_plan(plan, wiki, apply=False)
            self.assertEqual(summary["would_create"], 2)
            self.assertFalse((wiki / "content").exists())

    def test_materialize_accepts_plural_page_type_aliases(self) -> None:
        plan = {
            "source_id": "source-demo",
            "source_hash": "abc123",
            "topic": "demo-topic",
            "pages": [
                {
                    "type": "concepts",
                    "path": "concepts/version-culture.md",
                    "title": "版本文化",
                    "body_md": "版本文化概念。",
                    "source_block_ids": ["b0001"],
                    "outgoing_links": [],
                }
            ],
        }

        with tempfile.TemporaryDirectory() as tmp:
            wiki = Path(tmp) / "wiki"
            materialize_plan(plan, wiki, apply=True)

            page = (wiki / "content" / "concepts" / "version-culture.md").read_text(encoding="utf-8")
            manifest = json.loads((wiki / "llm-wiki-manifest.json").read_text(encoding="utf-8"))
            self.assertIn('type: "concept"', page)
            self.assertEqual(manifest["pages"]["concepts/version-culture.md"]["type"], "concept")

    def test_materialize_fails_when_outgoing_link_target_is_missing(self) -> None:
        plan = {
            "source_id": "source-demo",
            "source_hash": "abc123",
            "topic": "demo-topic",
            "pages": [
                {
                    "type": "stop",
                    "path": "stops/01-welcome.md",
                    "title": "欢迎词",
                    "body_md": "第一段讲解。",
                    "source_block_ids": ["b0001"],
                    "outgoing_links": ["persons/qian-chu.md"],
                }
            ],
        }

        with tempfile.TemporaryDirectory() as tmp:
            wiki = Path(tmp) / "wiki"
            with self.assertRaisesRegex(ValueError, "Missing outgoing link targets"):
                materialize_plan(plan, wiki, apply=True)

            self.assertFalse((wiki / "content" / "persons" / "qian-chu.md").exists())
            self.assertFalse((wiki / "llm-wiki-manifest.json").exists())

    def test_materialize_dry_run_fails_when_outgoing_link_target_is_missing(self) -> None:
        plan = {
            "source_id": "source-demo",
            "source_hash": "abc123",
            "topic": "demo-topic",
            "pages": [
                {
                    "type": "stop",
                    "path": "stops/01-welcome.md",
                    "title": "Welcome",
                    "body_md": "Intro.",
                    "source_block_ids": ["b0001"],
                    "outgoing_links": ["concepts/missing-concept.md"],
                }
            ],
        }

        with tempfile.TemporaryDirectory() as tmp:
            wiki = Path(tmp) / "wiki"
            with self.assertRaisesRegex(ValueError, "stops/01-welcome.md -> concepts/missing-concept.md"):
                materialize_plan(plan, wiki, apply=False)

            self.assertFalse((wiki / "content").exists())

    def test_materialize_creates_index_page_for_homepage(self) -> None:
        plan = {
            "source_id": "source-demo",
            "source_hash": "abc123",
            "topic": "demo-topic",
            "pages": [
                {
                    "type": "stop",
                    "path": "stops/01-welcome.md",
                    "title": "欢迎词",
                    "body_md": "第一段讲解。",
                    "source_block_ids": ["b0001"],
                    "outgoing_links": [],
                },
                {
                    "type": "work",
                    "path": "works/shi-ji.md",
                    "title": "史记",
                    "body_md": "《史记》实体页。",
                    "source_block_ids": ["b0002"],
                    "outgoing_links": [],
                },
            ],
        }

        with tempfile.TemporaryDirectory() as tmp:
            wiki = Path(tmp) / "wiki"
            materialize_plan(plan, wiki, apply=True)

            index = (wiki / "content" / "index.md").read_text(encoding="utf-8")
            manifest = json.loads((wiki / "llm-wiki-manifest.json").read_text(encoding="utf-8"))

            self.assertIn('type: "index"', index)
            self.assertIn("[[stops/01-welcome|欢迎词]]", index)
            self.assertIn("[[works/shi-ji|史记]]", index)
            self.assertEqual(manifest["pages"]["index.md"]["type"], "index")

    def test_materialize_prunes_stale_manifest_pages_for_same_source(self) -> None:
        first_plan = {
            "source_id": "source-demo",
            "source_hash": "abc123",
            "topic": "demo-topic",
            "pages": [
                {
                    "type": "concept",
                    "path": "concepts/old.md",
                    "title": "Old",
                    "body_md": "Old concept.",
                    "source_block_ids": [],
                    "outgoing_links": [],
                }
            ],
        }
        second_plan = {
            "source_id": "source-demo",
            "source_hash": "abc123",
            "topic": "demo-topic",
            "pages": [
                {
                    "type": "concept",
                    "path": "concepts/new.md",
                    "title": "New",
                    "body_md": "New concept.",
                    "source_block_ids": [],
                    "outgoing_links": [],
                }
            ],
        }

        with tempfile.TemporaryDirectory() as tmp:
            wiki = Path(tmp) / "wiki"
            materialize_plan(first_plan, wiki, apply=True)
            (wiki / "content" / "concepts" / "old.md").unlink()
            materialize_plan(second_plan, wiki, apply=True)

            manifest = json.loads((wiki / "llm-wiki-manifest.json").read_text(encoding="utf-8"))

            self.assertNotIn("concepts/old.md", manifest["pages"])
            self.assertIn("concepts/new.md", manifest["pages"])
            self.assertEqual(validate_wiki(wiki), [])


class ValidateTests(unittest.TestCase):
    def test_validate_reports_broken_wikilinks_and_missing_frontmatter(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            wiki = Path(tmp) / "wiki"
            content = wiki / "content"
            content.mkdir(parents=True)
            (content / "index.md").write_text(
                "---\ntitle: 首页\ntype: index\n---\n\n[[missing/page|Missing]]",
                encoding="utf-8",
            )
            (content / "bad.md").write_text("No frontmatter", encoding="utf-8")

            issues = validate_wiki(wiki)

            self.assertIn("Broken link in index.md: [[missing/page|Missing]]", issues)
            self.assertIn("Missing frontmatter field in bad.md: title", issues)
            self.assertIn("Missing frontmatter field in bad.md: type", issues)

    def test_validate_reports_materialize_stub_pages(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            wiki = Path(tmp) / "wiki"
            content = wiki / "content" / "concepts"
            content.mkdir(parents=True)
            (content / "placeholder.md").write_text(
                "---\ntitle: placeholder\ntype: concept\n---\n\n"
                "此页面由 `materialize` 根据摄入计划中的链接自动创建，用于避免 Wiki 出现断链。",
                encoding="utf-8",
            )

            issues = validate_wiki(wiki)

            self.assertIn("Materialize stub page remains: concepts/placeholder.md", issues)


if __name__ == "__main__":
    unittest.main()
