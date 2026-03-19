"""
Carregamento e parsing de documentos (PDF, TXT, Markdown, HTML).
Extrai texto, divide em chunks e identifica entidades com spaCy.
"""

from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass, field
from typing import Optional, Any

from loguru import logger
from src.ingestion.catalyst_ocr import CatalystOCREngine


@dataclass
class DocumentChunk:
    chunk_id: str
    doc_id: str
    text: str
    page: Optional[int] = None


@dataclass
class AlexDocument:
    id: str
    filename: str
    raw_text: str
    chunks: list[DocumentChunk] = field(default_factory=list)
    entities: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


class DocumentLoader:
    """
    Carrega documentos de vários formatos, extrai texto, divide em chunks
    e extrai entidades nomeadas usando spaCy (carregado sob demanda).
    """

    CHUNK_SIZE = 512       # chars por chunk
    CHUNK_OVERLAP = 64     # sobreposição entre chunks

    def __init__(self):
        self._nlp: Optional[Any] = None   # lazy load
        self._ner_disabled = False
        self._ocr = CatalystOCREngine()

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------

    @property
    def ocr_info(self) -> dict:
        return self._ocr.info

    def load(self, path: str) -> AlexDocument:
        ext = os.path.splitext(path)[-1].lower()
        logger.info(f"Carregando documento: {path} ({ext})")

        ocr_used = False
        ocr_engine = "disabled"
        ocr_error = None

        if ext == ".pdf":
            raw_text = self._load_pdf(path)
            if self._ocr.should_ocr_pdf(raw_text):
                ocr_result = self._ocr.extract_from_pdf(path)
                if ocr_result.text:
                    raw_text = f"{raw_text}\n\n{ocr_result.text}".strip() if raw_text else ocr_result.text
                ocr_used = ocr_result.used
                ocr_engine = ocr_result.engine
                ocr_error = ocr_result.error
        elif ext in {".md", ".markdown"}:
            raw_text = self._load_markdown(path)
        elif ext in {".html", ".htm"}:
            raw_text = self._load_html(path)
        elif ext in {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp"}:
            ocr_result = self._ocr.extract_from_image(path)
            raw_text = ocr_result.text
            ocr_used = ocr_result.used
            ocr_engine = ocr_result.engine
            ocr_error = ocr_result.error
        else:  # .txt e outros
            raw_text = self._load_text(path)

        # Sanitiza o texto antes da análise semântica/entidades para o grafo.
        clean_text = self._sanitize_plain_text(raw_text)

        doc_id = self._hash(path, clean_text)
        chunks = self._split_chunks(clean_text, doc_id)
        entities = self._extract_entities(clean_text)

        return AlexDocument(
            id=doc_id,
            filename=os.path.basename(path),
            raw_text=clean_text,
            chunks=chunks,
            entities=entities,
            metadata={
                "path": path,
                "size_bytes": os.path.getsize(path),
                "sanitized": True,
                "original_chars": len(raw_text),
                "sanitized_chars": len(clean_text),
                "ocr_used": ocr_used,
                "ocr_engine": ocr_engine,
                "ocr_error": ocr_error,
                **self._ocr.info,
            },
        )

    # ------------------------------------------------------------------
    # Parsers por formato
    # ------------------------------------------------------------------

    def _load_pdf(self, path: str) -> str:
        try:
            from pypdf import PdfReader
            reader = PdfReader(path)
            pages = []
            for page in reader.pages:
                text = page.extract_text() or ""
                pages.append(text)
            return "\n\n".join(pages)
        except Exception as e:
            logger.error(f"Erro ao ler PDF {path}: {e}")
            return ""

    def _load_markdown(self, path: str) -> str:
        try:
            import markdown
            from bs4 import BeautifulSoup
            with open(path, encoding="utf-8") as f:
                md_text = f.read()
            html = markdown.markdown(md_text)
            return BeautifulSoup(html, "html.parser").get_text(separator="\n")
        except Exception as e:
            logger.error(f"Erro ao ler Markdown {path}: {e}")
            return ""

    def _load_html(self, path: str) -> str:
        try:
            from bs4 import BeautifulSoup
            with open(path, encoding="utf-8") as f:
                soup = BeautifulSoup(f.read(), "html.parser")
            for tag in soup(["script", "style"]):
                tag.decompose()
            return soup.get_text(separator="\n")
        except Exception as e:
            logger.error(f"Erro ao ler HTML {path}: {e}")
            return ""

    def _load_text(self, path: str) -> str:
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                return f.read()
        except Exception as e:
            logger.error(f"Erro ao ler TXT {path}: {e}")
            return ""

    # ------------------------------------------------------------------
    # Chunking
    # ------------------------------------------------------------------

    def _split_chunks(self, text: str, doc_id: str) -> list[DocumentChunk]:
        chunks = []
        step = self.CHUNK_SIZE - self.CHUNK_OVERLAP
        for i, start in enumerate(range(0, max(len(text), 1), step)):
            chunk_text = text[start : start + self.CHUNK_SIZE].strip()
            if not chunk_text:
                continue
            chunk_id = f"{doc_id}_c{i}"
            chunks.append(DocumentChunk(chunk_id=chunk_id, doc_id=doc_id, text=chunk_text))
        return chunks

    # ------------------------------------------------------------------
    # NER com spaCy
    # ------------------------------------------------------------------

    def _get_nlp(self) -> Optional[Any]:
        if self._ner_disabled:
            return None
        if self._nlp is None:
            try:
                import spacy
                try:
                    self._nlp = spacy.load("pt_core_news_sm")
                except OSError:
                    try:
                        self._nlp = spacy.load("en_core_web_sm")
                    except OSError:
                        logger.warning("Nenhum modelo spaCy encontrado. NER desabilitado.")
                        self._ner_disabled = True
                        return None
            except ImportError:
                logger.warning("spaCy não instalado. NER desabilitado.")
                self._ner_disabled = True
                return None
        return self._nlp

    def _extract_entities(self, text: str) -> list[str]:
        nlp = self._get_nlp()
        if nlp is None:
            return []
        # Limita texto para NER (evita timeout em documentos enormes)
        snippet = text[:10_000]
        doc = nlp(snippet)
        entities = list({ent.text.strip() for ent in doc.ents if len(ent.text.strip()) > 1})
        return entities

    # ------------------------------------------------------------------
    # Utilitários
    # ------------------------------------------------------------------

    @staticmethod
    def _sanitize_plain_text(text: str) -> str:
        """
        Sanitiza texto bruto para análise:
          - remove caracteres de controle (exceto \n e \t)
          - normaliza quebras de linha para \n
          - compacta espaços excessivos
          - limita blocos vazios consecutivos
        """
        if not text:
            return ""

        # Normaliza quebras de linha
        clean = text.replace("\r\n", "\n").replace("\r", "\n")

        # Remove controles não imprimíveis preservando \n e \t
        clean = "".join(
            ch for ch in clean if (ch == "\n" or ch == "\t" or ord(ch) >= 32)
        )

        # Remove espaços redundantes no fim/início de linhas
        clean = "\n".join(line.strip() for line in clean.split("\n"))

        # Compacta múltiplos espaços internos
        clean = re.sub(r"[ \t]{2,}", " ", clean)

        # Limita linhas em branco consecutivas
        clean = re.sub(r"\n{3,}", "\n\n", clean)

        return clean.strip()

    @staticmethod
    def _hash(path: str, text: str) -> str:
        return hashlib.sha1(f"{path}{len(text)}".encode()).hexdigest()[:12]
