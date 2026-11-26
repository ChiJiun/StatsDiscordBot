"""Embed complete question/solution PDFs in standalone HTML reports."""

import base64
import html
import logging
import shutil
import subprocess
import tempfile
from pathlib import Path


LOGGER = logging.getLogger(__name__)


def _convert_docx_to_pdf(source: Path):
    """Convert with LibreOffice without sharing a user profile across workers."""
    office = shutil.which("libreoffice") or shutil.which("soffice")
    if office is None:
        LOGGER.warning("Cannot render %s as PDF: LibreOffice is not installed", source)
        return None

    try:
        with tempfile.TemporaryDirectory(prefix="stats-report-pdf-") as tmp:
            profile = (Path(tmp) / "profile").as_uri()
            subprocess.run(
                [office, f"-env:UserInstallation={profile}", "--headless",
                 "--convert-to", "pdf:writer_pdf_Export", "--outdir", tmp,
                 str(source)],
                check=True, capture_output=True, text=True, timeout=90,
            )
            return (Path(tmp) / f"{source.stem}.pdf").read_bytes()
    except (OSError, subprocess.SubprocessError) as exc:
        LOGGER.warning("Cannot convert %s to PDF: %s", source, exc)
        return None


def embed_pdf(directory, title, label):
    """Return a self-contained PDF viewer, or None if no usable PDF is available.

    Prefer an exported PDF to avoid conversion differences. DOCX sources are
    converted on demand; the entire PDF is encoded into the HTML so the file
    still works when downloaded from Discord or Google Drive.
    """
    if not title or title in (".", "..") or Path(title).name != title or "\\" in title:
        return None

    root = Path(directory)
    pdf_path = root / f"{title}.pdf"
    docx_path = root / f"{title}.docx"
    data = None

    if pdf_path.is_file():
        try:
            data = pdf_path.read_bytes()
        except OSError as exc:
            LOGGER.warning("Cannot read %s: %s", pdf_path, exc)

    if (not data or not data.startswith(b"%PDF-")) and docx_path.is_file():
        data = _convert_docx_to_pdf(docx_path)

    if not data or not data.startswith(b"%PDF-"):
        return None

    src = "data:application/pdf;base64," + base64.b64encode(data).decode("ascii")
    safe_label = html.escape(label, quote=True)
    safe_filename = html.escape(f"{title}.pdf", quote=True)
    return (
        f'<object class="pdf-viewer" type="application/pdf" data="{src}" '
        f'aria-label="{safe_label} PDF">'
        '<p>瀏覽器無法預覽 PDF，請使用下方下載連結。</p>'
        "</object>"
        f'<p><a href="{src}" download="{safe_filename}">下載完整 PDF</a></p>'
    )
