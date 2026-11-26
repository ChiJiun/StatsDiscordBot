"""Targeted tests for standalone report PDF embedding."""

import base64
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from pdf_embed import embed_pdf


class EmbedPdfTests(unittest.TestCase):
    def test_exported_pdf_is_embedded_and_downloadable(self):
        with tempfile.TemporaryDirectory() as folder:
            (Path(folder) / "Question 1.pdf").write_bytes(b"%PDF-1.4\ncontent")
            content = embed_pdf(folder, "Question 1", "完整題目")
            self.assertIn('type="application/pdf"', content)
            self.assertIn('download="Question 1.pdf"', content)
            self.assertIn(base64.b64encode(b"%PDF-1.4\ncontent").decode(), content)

    @mock.patch("pdf_embed._convert_docx_to_pdf")
    def test_pdf_takes_precedence_over_docx(self, convert):
        with tempfile.TemporaryDirectory() as folder:
            (Path(folder) / "A.pdf").write_bytes(b"%PDF-1.5\n")
            (Path(folder) / "A.docx").write_bytes(b"docx")
            self.assertIsNotNone(embed_pdf(folder, "A", "解答"))
            convert.assert_not_called()

    @mock.patch("pdf_embed._convert_docx_to_pdf", return_value=b"%PDF-1.7\n")
    def test_docx_can_be_converted(self, convert):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "A.docx"
            source.write_bytes(b"placeholder")
            self.assertIn("data:application/pdf;base64,", embed_pdf(folder, "A", "解答"))
            convert.assert_called_once_with(source)

    @mock.patch("pdf_embed.shutil.which", return_value=None)
    def test_missing_converter_fails_gracefully(self, _):
        with tempfile.TemporaryDirectory() as folder:
            (Path(folder) / "A.docx").write_bytes(b"placeholder")
            self.assertIsNone(embed_pdf(folder, "A", "解答"))

    def test_invalid_paths_and_missing_sources(self):
        with tempfile.TemporaryDirectory() as folder:
            for name in ["../private", "a/b", r"a\b", ".", ""]:
                self.assertIsNone(embed_pdf(folder, name, "題目"))
            self.assertIsNone(embed_pdf(folder, "missing", "題目"))

    def test_invalid_pdf_is_not_embedded(self):
        with tempfile.TemporaryDirectory() as folder:
            (Path(folder) / "A.pdf").write_bytes(b"not a pdf")
            self.assertIsNone(embed_pdf(folder, "A", "題目"))


if __name__ == "__main__":
    unittest.main()
