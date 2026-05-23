import tempfile
import unittest
from pathlib import Path

from translate_wiki import load_config, process_file, translate_paragraph


class TranslationConfigTests(unittest.TestCase):
    def test_default_translation_config_is_disabled(self) -> None:
        config = load_config({})

        self.assertEqual(config.engine, "none")
        self.assertFalse(config.enabled)
        self.assertIsNone(config.api_key)

    def test_disabled_translation_does_not_call_remote_api(self) -> None:
        config = load_config({})

        self.assertIsNone(translate_paragraph("English paragraph.", config))

    def test_process_file_does_not_modify_markdown_when_translation_disabled(self) -> None:
        config = load_config({})
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "page.md"
            original = "A paragraph that would normally be translated.\n"
            path.write_text(original, encoding="utf-8")

            added = process_file(path, config)

            self.assertEqual(added, 0)
            self.assertEqual(path.read_text(encoding="utf-8"), original)


if __name__ == "__main__":
    unittest.main()
