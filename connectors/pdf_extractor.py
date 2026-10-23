"""Extracción de texto de PDFs (sentencias, convenios, nóminas, cartas) — dossier §3.1 v2.1.

1) Si una página da menos de 100 caracteres se marca para OCR (PDF escaneado). El OCR local
   (Tesseract) es opcional: si `pytesseract` y el binario están instalados se usa; si no, el
   resultado lo indica para que la UI pida al usuario un PDF con texto o una foto más nítida.
2) Ligaduras Unicode y palabras partidas a final de línea se normalizan.
"""

from __future__ import annotations

import io
import shutil
from dataclasses import dataclass, field
from pathlib import Path

import pdfplumber

from core.normalize import dehyphenate, fix_ligatures

MIN_CHARS_PER_PAGE = 100


@dataclass
class PageText:
    number: int
    text: str
    ocr_needed: bool
    ocr_used: bool = False


@dataclass
class PdfExtraction:
    pages: list[PageText] = field(default_factory=list)

    @property
    def text(self) -> str:
        return "\n\n".join(p.text for p in self.pages if p.text)

    @property
    def ocr_pending(self) -> list[int]:
        return [p.number for p in self.pages if p.ocr_needed and not p.ocr_used]

    @property
    def ocr_used(self) -> bool:
        return any(p.ocr_used for p in self.pages)


def clean_text(text: str) -> str:
    text = fix_ligatures(text)
    text = dehyphenate(text)
    lines = [" ".join(line.split()) for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


def _ocr_available() -> bool:
    try:
        import pytesseract  # type: ignore[import-not-found]  # noqa: F401
    except ImportError:
        return False
    return shutil.which("tesseract") is not None


def _ocr_page(page: pdfplumber.page.Page) -> str:
    import pytesseract

    image = page.to_image(resolution=300).original
    return str(pytesseract.image_to_string(image, lang="spa"))


def extract_pdf(source: Path | bytes) -> PdfExtraction:
    data = source if isinstance(source, bytes) else Path(source).read_bytes()
    result = PdfExtraction()
    ocr = _ocr_available()
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        for number, page in enumerate(pdf.pages, start=1):
            raw = page.extract_text() or ""
            needs_ocr = len(raw.strip()) < MIN_CHARS_PER_PAGE
            used = False
            if needs_ocr and ocr:
                raw, used = _ocr_page(page), True
            result.pages.append(PageText(number, clean_text(raw), needs_ocr, used))
    return result
