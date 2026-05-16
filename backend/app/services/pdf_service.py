"""PDF text extraction service.

Uses pypdf — pure Python, no system dependencies.
For scanned/image-based PDFs (no embedded text) we return empty text and
flag the file as 'image-only'. OCR can be added later.
"""
from __future__ import annotations

import logging
from io import BytesIO
from pathlib import Path
from typing import Dict, Optional, Union

from pypdf import PdfReader
from pypdf.errors import PdfReadError

log = logging.getLogger("pdf")


MAX_PAGES = 50  # safety limit per file


def _extract_from_reader(reader: PdfReader) -> str:
    pages_text: list[str] = []
    for i, page in enumerate(reader.pages):
        if i >= MAX_PAGES:
            log.warning("PDF has more than %d pages, truncating", MAX_PAGES)
            break
        try:
            pages_text.append(page.extract_text() or "")
        except Exception as e:
            log.warning("PDF page %d extraction failed: %s", i, e)
            pages_text.append("")
    return "\n\n".join(pages_text).strip()


def extract_text(source: Union[Path, str, bytes]) -> Dict[str, object]:
    """Extract text from a PDF.

    Accepts a file path or raw bytes. Returns a dict:
    {
      "text": str,
      "pages": int,
      "is_image_only": bool,   # True if the PDF has no extractable text
      "error": Optional[str],
    }
    """
    result: Dict[str, object] = {
        "text": "",
        "pages": 0,
        "is_image_only": False,
        "error": None,
    }

    try:
        if isinstance(source, (str, Path)):
            reader = PdfReader(str(source))
        elif isinstance(source, bytes):
            reader = PdfReader(BytesIO(source))
        else:
            raise TypeError(f"Unsupported source type: {type(source)}")
    except PdfReadError as e:
        log.warning("PDF read error: %s", e)
        result["error"] = f"PDF read error: {e}"
        return result
    except Exception as e:
        log.warning("PDF open failed: %s", e)
        result["error"] = f"open failed: {e}"
        return result

    result["pages"] = len(reader.pages)
    text = _extract_from_reader(reader)
    result["text"] = text
    result["is_image_only"] = (len(text.strip()) == 0)
    if result["is_image_only"]:
        log.info("PDF is image-only / no extractable text (pages=%d)", result["pages"])
    else:
        log.info("PDF text extracted: pages=%d, chars=%d", result["pages"], len(text))
    return result
