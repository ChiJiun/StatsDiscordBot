"""Ensure the five-section HTML report uses embedded PDFs where present."""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

import report_generator


class ReportGeneratorPdfTests(unittest.TestCase):
    def test_source_sections_embed_pdf_without_losing_feedback(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "Question").mkdir()
            (root / "Answer").mkdir()
            (root / "Question" / "Example.pdf").write_bytes(b"%PDF-1.4\nquestion")
            (root / "Answer" / "Example.pdf").write_bytes(b"%PDF-1.4\nsolution")
            with mock.patch.object(report_generator, "__file__", str(root / "report_generator.py")):
                result = report_generator.generate_html_report(
                    "Student", "123", "Example", 1, "My answer",
                    "English feedback is available and complete. " * 4,
                    "Statistical feedback is available and complete. " * 4,
                )
            self.assertEqual(result.count('<object class="pdf-viewer"'), 2)
            self.assertIn('data:application/pdf;base64,', result)
            self.assertIn("My answer", result)
            self.assertIn("English feedback is available", result)
            self.assertIn("Statistical feedback is available", result)
            self.assertEqual(result.count('<h2 class="section">'), 5)

    def test_docx_without_conversion_shows_explicit_warning(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "Question").mkdir()
            (root / "Answer").mkdir()
            # Source exists but conversion fails; never claim that plain text is complete.
            (root / "Question" / "Example.docx").write_bytes(b"invalid document")
            with mock.patch.object(report_generator, "__file__", str(root / "report_generator.py")), \
                 mock.patch.object(report_generator, "embed_pdf", return_value=None):
                result = report_generator.generate_html_report(
                    "Student", "123", "Example", 1, "answer", "feedback", "feedback"
                )
            self.assertIn("PDF 轉換失敗", result)
            self.assertIn("圖表及原始排版可能遺失", result)


if __name__ == "__main__":
    unittest.main()
