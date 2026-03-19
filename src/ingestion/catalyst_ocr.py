"""Motor OCR "catalyst-like" com fallback seguro e pré-processamento básico."""

from __future__ import annotations

import os
from importlib import import_module
from dataclasses import dataclass
from typing import Optional

from loguru import logger


@dataclass
class OCRResult:
    text: str
    used: bool
    engine: str
    error: Optional[str] = None


class CatalystOCREngine:
    """
    Motor OCR opcional para documentos escaneados.

    Estratégia:
      - Imagens: OCR direto com pré-processamento.
      - PDF: OCR por páginas quando necessário (texto nativo insuficiente).
      - Falha graciosa quando dependências externas não estão disponíveis.
    """

    def __init__(self) -> None:
        self.enabled = os.getenv("OCR_ENGINE_ENABLED", "true").lower() == "true"
        self.languages = os.getenv("OCR_LANGUAGES", "por+eng")
        self.force_pdf = os.getenv("OCR_FORCE_PDF", "false").lower() == "true"
        self.max_pages = max(1, int(os.getenv("OCR_MAX_PDF_PAGES", "12")))
        self.min_pdf_chars = max(0, int(os.getenv("OCR_MIN_PDF_CHARS", "120")))

    @property
    def info(self) -> dict:
        return {
            "ocr_enabled": self.enabled,
            "ocr_languages": self.languages,
            "ocr_force_pdf": self.force_pdf,
            "ocr_max_pdf_pages": self.max_pages,
        }

    def should_ocr_pdf(self, native_text: str) -> bool:
        if not self.enabled:
            return False
        if self.force_pdf:
            return True
        return len((native_text or "").strip()) < self.min_pdf_chars

    def extract_from_image(self, path: str) -> OCRResult:
        if not self.enabled:
            return OCRResult(text="", used=False, engine="disabled")

        try:
            pytesseract = import_module("pytesseract")
            pil_image = import_module("PIL.Image")
            pil_ops = import_module("PIL.ImageOps")
            pil_filter = import_module("PIL.ImageFilter")

            img = pil_image.open(path)
            # Pré-processamento simples para melhorar contraste e OCR.
            img = pil_ops.exif_transpose(img).convert("L")
            img = pil_ops.autocontrast(img)
            img = img.filter(pil_filter.MedianFilter(size=3))
            img = img.point(lambda p: 255 if p > 160 else 0)

            text = pytesseract.image_to_string(img, lang=self.languages) or ""
            return OCRResult(text=text.strip(), used=True, engine="pytesseract")
        except Exception as e:
            logger.warning(f"OCR imagem falhou para {path}: {e}")
            return OCRResult(text="", used=False, engine="pytesseract", error=str(e))

    def extract_from_pdf(self, path: str) -> OCRResult:
        if not self.enabled:
            return OCRResult(text="", used=False, engine="disabled")

        try:
            convert_from_path = import_module("pdf2image").convert_from_path
            pytesseract = import_module("pytesseract")
            pil_ops = import_module("PIL.ImageOps")
            pil_filter = import_module("PIL.ImageFilter")

            pages = convert_from_path(path, first_page=1, last_page=self.max_pages)
            out = []
            for page_img in pages:
                img = pil_ops.exif_transpose(page_img).convert("L")
                img = pil_ops.autocontrast(img)
                img = img.filter(pil_filter.MedianFilter(size=3))
                img = img.point(lambda p: 255 if p > 160 else 0)
                text = pytesseract.image_to_string(img, lang=self.languages) or ""
                out.append(text.strip())

            merged = "\n\n".join(t for t in out if t)
            return OCRResult(text=merged.strip(), used=bool(merged.strip()), engine="pdf2image+pytesseract")
        except Exception as e:
            logger.warning(f"OCR PDF falhou para {path}: {e}")
            return OCRResult(text="", used=False, engine="pdf2image+pytesseract", error=str(e))
