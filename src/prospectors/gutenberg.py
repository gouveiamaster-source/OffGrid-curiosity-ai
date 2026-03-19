"""
Prospector do Project Gutenberg — https://www.gutenberg.org/

Funcionalidades:
  - Busca livros pelo catálogo RDF off-line ou via API OPDS online
  - Download do texto puro (.txt / UTF-8) de um livro por Book-ID
  - Ingestão automática no Alexandria-AI (DocumentLoader → SemanticSearch + KnowledgeGraph)
  - Catálogo local persistido em JSON para consultas sem internet

Fontes usadas:
  • OPDS catalog: https://gutendex.com/books/  (JSON REST, sem chave)
  • Texto: https://www.gutenberg.org/cache/epub/{id}/pg{id}.txt
           https://www.gutenberg.org/files/{id}/{id}-0.txt  (fallback)
"""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass, field, asdict
from typing import Optional, Any
from urllib.parse import urlencode
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

from loguru import logger

# ─── Caminhos locais ───────────────────────────────────────────────────────
CATALOG_DIR = "data/gutenberg"
CATALOG_FILE = os.path.join(CATALOG_DIR, "catalog_cache.json")
BOOKS_DIR = os.path.join(CATALOG_DIR, "books")

# ─── URLs ──────────────────────────────────────────────────────────────────
GUTENDEX_API = "https://gutendex.com/books/"
GUTENBERG_TEXT_URLS = [
    "https://www.gutenberg.org/cache/epub/{id}/pg{id}.txt",
    "https://www.gutenberg.org/files/{id}/{id}-0.txt",
    "https://www.gutenberg.org/files/{id}/{id}.txt",
]

# ─── Pausa entre requests (cortesia com o servidor) ────────────────────────
REQUEST_DELAY = 1.5   # segundos


@dataclass
class GutenbergBook:
    id: int
    title: str
    authors: list[str]
    languages: list[str]
    subjects: list[str]
    download_count: int
    formats: dict
    local_path: Optional[str] = None
    ingested: bool = False


@dataclass
class ProspectResult:
    book_id: int
    title: str
    authors: list[str]
    languages: list[str]
    subjects: list[str]
    status: str                     # "ok" | "already_indexed" | "download_failed" | "ingest_failed"
    document_id: Optional[str] = None
    chunks: int = 0
    entities: int = 0
    error: Optional[str] = None


class GutenbergProspector:
    """
    Prospector de livros do Project Gutenberg.

    Uso típico:
        prospector = GutenbergProspector(search_engine, graph)
        results = prospector.prospect(query="Dom Casmurro", limit=5, languages=["pt"])
    """

    def __init__(self, search_engine=None, graph=None):
        self._search_engine: Optional[Any] = search_engine
        self._graph: Optional[Any] = graph
        self._catalog: dict[int, GutenbergBook] = {}
        os.makedirs(BOOKS_DIR, exist_ok=True)
        self._load_catalog()

    # ──────────────────────────────────────────────────────────────────────
    # API pública
    # ──────────────────────────────────────────────────────────────────────

    def search_catalog(
        self,
        query: str = "",
        languages: Optional[list[str]] = None,
        topic: str = "",
        limit: int = 20,
        page: int = 1,
    ) -> list[GutenbergBook]:
        """
        Consulta o catálogo Gutendex e retorna metadados dos livros.
        Não faz download — apenas lista.
        """
        params: dict = {"page": page}
        if query:
            params["search"] = query
        if languages:
            params["languages"] = ",".join(languages)
        if topic:
            params["topic"] = topic

        url = f"{GUTENDEX_API}?{urlencode(params)}"
        logger.info(f"Consultando catálogo Gutenberg: {url}")

        data = self._http_get_json(url)
        if not data:
            return []

        books = []
        for item in data.get("results", [])[:limit]:
            book = self._parse_gutendex_item(item)
            self._catalog[book.id] = book
            books.append(book)

        self._save_catalog()
        return books

    def prospect(
        self,
        query: str = "",
        book_ids: Optional[list[int]] = None,
        languages: Optional[list[str]] = None,
        topic: str = "",
        limit: int = 5,
        skip_already_ingested: bool = True,
    ) -> list[ProspectResult]:
        """
        Busca livros, faz download e indexa no Alexandria-AI.

        Pode receber:
          - query + languages (busca pelo catálogo Gutendex)
          - book_ids (download direto por ID)
        """
        results: list[ProspectResult] = []

        if book_ids:
            books = []
            for bid in book_ids:
                if bid in self._catalog:
                    books.append(self._catalog[bid])
                else:
                    # Busca metadados do livro individual
                    meta = self._fetch_book_meta(bid)
                    if meta:
                        books.append(meta)
        else:
            books = self.search_catalog(query=query, languages=languages, topic=topic, limit=limit)

        for book in books:
            result = self._prospect_one(book, skip_already_ingested)
            results.append(result)
            time.sleep(REQUEST_DELAY)

        return results

    def get_cached_books(self) -> list[dict]:
        """Retorna livros do catálogo local (sem acesso à internet)."""
        return [asdict(b) for b in self._catalog.values()]

    def catalog_stats(self) -> dict:
        total = len(self._catalog)
        ingested = sum(1 for b in self._catalog.values() if b.ingested)
        downloaded = sum(1 for b in self._catalog.values() if b.local_path)
        return {
            "total_catalogued": total,
            "downloaded": downloaded,
            "ingested": ingested,
        }

    # ──────────────────────────────────────────────────────────────────────
    # Internos — prospecção de um livro
    # ──────────────────────────────────────────────────────────────────────

    def _prospect_one(self, book: GutenbergBook, skip_already_ingested: bool) -> ProspectResult:
        base = ProspectResult(
            book_id=book.id,
            title=book.title,
            authors=book.authors,
            languages=book.languages,
            subjects=book.subjects,
            status="ok",
        )

        # Verifica se já foi indexado
        if skip_already_ingested and book.ingested:
            base.status = "already_indexed"
            return base

        # Download do texto
        txt_path = self._download_book(book)
        if not txt_path:
            base.status = "download_failed"
            base.error = "Não foi possível baixar o texto do livro."
            return base

        book.local_path = txt_path
        self._catalog[book.id] = book
        self._save_catalog()

        # Ingestão
        if self._search_engine and self._graph:
            try:
                doc = self._ingest(txt_path)
                book.ingested = True
                self._save_catalog()
                base.document_id = doc.id
                base.chunks = len(doc.chunks)
                base.entities = len(doc.entities)
                base.status = "ok"
            except Exception as e:
                logger.error(f"Falha ao ingerir livro {book.id}: {e}")
                base.status = "ingest_failed"
                base.error = str(e)
        else:
            # Modo sem motor — apenas faz download
            base.status = "downloaded_only"

        return base

    def _ingest(self, txt_path: str):
        if self._search_engine is None or self._graph is None:
            raise RuntimeError("Motores de busca/grafo não inicializados.")
        assert self._search_engine is not None
        assert self._graph is not None
        from src.ingestion.document_loader import DocumentLoader
        loader = DocumentLoader()
        doc = loader.load(txt_path)
        self._search_engine.add_document(doc)
        self._graph.add_document(doc)
        self._search_engine.save_index()
        return doc

    # ──────────────────────────────────────────────────────────────────────
    # Internos — download
    # ──────────────────────────────────────────────────────────────────────

    def _download_book(self, book: GutenbergBook) -> Optional[str]:
        # Verifica se já existe localmente
        local = os.path.join(BOOKS_DIR, f"pg{book.id}.txt")
        if os.path.exists(local):
            logger.info(f"Livro {book.id} já baixado: {local}")
            return local

        # Tenta formatos txt do mapa de formatos do book
        txt_url = self._best_txt_url(book)
        urls_to_try = ([txt_url] if txt_url else []) + [
            u.format(id=book.id) for u in GUTENBERG_TEXT_URLS
        ]

        for url in urls_to_try:
            logger.info(f"Baixando livro {book.id}: {url}")
            content = self._http_get_bytes(url)
            if content:
                # Remove BOM e cabeçalho/rodapé do Gutenberg
                text = self._clean_gutenberg_text(content)
                if len(text.strip()) < 500:
                    continue   # arquivo inválido/vazio
                with open(local, "w", encoding="utf-8") as f:
                    f.write(text)
                logger.info(f"Livro {book.id} salvo em {local} ({len(text):,} chars)")
                return local
            time.sleep(0.5)

        logger.warning(f"Não foi possível baixar o livro {book.id}")
        return None

    @staticmethod
    def _best_txt_url(book: GutenbergBook) -> Optional[str]:
        """Seleciona a melhor URL de texto plano a partir dos formatos do livro."""
        fmts = book.formats
        # Preferência: UTF-8 > ASCII > genérico
        for mime in ("text/plain; charset=utf-8", "text/plain; charset=us-ascii", "text/plain"):
            if mime in fmts:
                return fmts[mime]
        # Fallback: qualquer chave text/plain
        for key, val in fmts.items():
            if key.startswith("text/plain"):
                return val
        return None

    @staticmethod
    def _clean_gutenberg_text(content: bytes) -> str:
        """Remove BOM, cabeçalho e rodapé padrão do Project Gutenberg."""
        # Detecta encoding
        for enc in ("utf-8-sig", "utf-8", "latin-1"):
            try:
                text = content.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        else:
            text = content.decode("latin-1", errors="replace")

        # Remove cabeçalho (tudo até "*** START OF THE PROJECT GUTENBERG EBOOK")
        start_pat = re.compile(
            r"\*{3}\s*START OF (THE|THIS) PROJECT GUTENBERG EBOOK[^\n]*\n",
            re.IGNORECASE,
        )
        m = start_pat.search(text)
        if m:
            text = text[m.end():]

        # Remove rodapé (a partir de "*** END OF THE PROJECT GUTENBERG EBOOK")
        end_pat = re.compile(
            r"\*{3}\s*END OF (THE|THIS) PROJECT GUTENBERG EBOOK",
            re.IGNORECASE,
        )
        m = end_pat.search(text)
        if m:
            text = text[: m.start()]

        return text.strip()

    # ──────────────────────────────────────────────────────────────────────
    # Internos — HTTP
    # ──────────────────────────────────────────────────────────────────────

    @staticmethod
    def _http_get_json(url: str) -> Optional[dict]:
        try:
            req = Request(url, headers={"User-Agent": "Alexandria-AI/0.1 (educational)"})
            with urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (URLError, HTTPError, json.JSONDecodeError) as e:
            logger.error(f"HTTP JSON error {url}: {e}")
            return None

    @staticmethod
    def _http_get_bytes(url: str) -> Optional[bytes]:
        try:
            req = Request(url, headers={"User-Agent": "Alexandria-AI/0.1 (educational)"})
            with urlopen(req, timeout=60) as resp:
                return resp.read()
        except (URLError, HTTPError) as e:
            logger.warning(f"HTTP bytes error {url}: {e}")
            return None

    # ──────────────────────────────────────────────────────────────────────
    # Internos — metadados
    # ──────────────────────────────────────────────────────────────────────

    def _fetch_book_meta(self, book_id: int) -> Optional[GutenbergBook]:
        url = f"{GUTENDEX_API}{book_id}/"
        data = self._http_get_json(url)
        if not data:
            return None
        book = self._parse_gutendex_item(data)
        self._catalog[book.id] = book
        self._save_catalog()
        return book

    @staticmethod
    def _parse_gutendex_item(item: dict) -> GutenbergBook:
        authors = [a.get("name", "") for a in item.get("authors", [])]
        return GutenbergBook(
            id=item["id"],
            title=item.get("title", "Sem título"),
            authors=authors,
            languages=item.get("languages", []),
            subjects=item.get("subjects", [])[:10],
            download_count=item.get("download_count", 0),
            formats=item.get("formats", {}),
        )

    # ──────────────────────────────────────────────────────────────────────
    # Persistência do catálogo local
    # ──────────────────────────────────────────────────────────────────────

    def _save_catalog(self) -> None:
        os.makedirs(CATALOG_DIR, exist_ok=True)
        data = {str(k): asdict(v) for k, v in self._catalog.items()}
        with open(CATALOG_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _load_catalog(self) -> None:
        if not os.path.exists(CATALOG_FILE):
            return
        try:
            with open(CATALOG_FILE, encoding="utf-8") as f:
                raw = json.load(f)
            for k, v in raw.items():
                self._catalog[int(k)] = GutenbergBook(**v)
            logger.info(f"Catálogo Gutenberg carregado: {len(self._catalog)} entradas")
        except Exception as e:
            logger.warning(f"Falha ao carregar catálogo Gutenberg: {e}")
