"""
Busca semântica — todas as dependências externas via src.search.deps.
"""

from __future__ import annotations

import os
import pickle
from pathlib import Path

from loguru import logger

from src.ingestion.document_loader import AlexDocument
from src.models.schemas import DocumentInfo, SearchResult
from src.search import deps

INDEX_DIR = "data/index"
VECTOR_INDEX_PATH = os.path.join(INDEX_DIR, "vector.index")
META_PATH = os.path.join(INDEX_DIR, "chunks_meta.pkl")

DEFAULT_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"
MAX_VIEWER_BYTES = 2 * 1024 * 1024


class SemanticSearch:
    """
    Índice de busca semântica.

    Dependências externas isoladas via deps.py:
      • EmbeddingsBackend  →  sentence-transformers
      • VectorIndex        →  faiss-cpu  (fallback: numpy BruteForce)
    """

    def __init__(self, model_name: str = DEFAULT_MODEL):
        self.model_name = model_name
        self._embeddings = deps.EmbeddingsBackend(model_name)
        self._index = deps.VectorIndex()
        self._meta: list[dict] = []
        self._doc_registry: dict[str, DocumentInfo] = {}

    # ──────────────────────────────────────────────────────────────────────
    # API pública
    # ──────────────────────────────────────────────────────────────────────

    def add_document(self, doc: AlexDocument) -> None:
        """Codifica os chunks do documento e os adiciona ao índice vetorial."""
        if not doc.chunks:
            logger.warning(f"Documento {doc.filename} sem chunks, pulando.")
            return

        texts = [c.text for c in doc.chunks]
        embeddings = self._embeddings.encode(texts)   # (N, D) — via deps
        self._index.add(embeddings)

        for chunk in doc.chunks:
            self._meta.append(
                {
                    "chunk_id": chunk.chunk_id,
                    "doc_id": doc.id,
                    "filename": doc.filename,
                    "text": chunk.text,
                    "page": chunk.page,
                    "source_path": doc.metadata.get("path"),
                }
            )

        self._doc_registry[doc.id] = DocumentInfo(
            document_id=doc.id,
            filename=doc.filename,
            chunks=len(doc.chunks),
            entities=len(doc.entities),
        )
        logger.info(
            f"Documento indexado: {doc.filename} ({len(doc.chunks)} chunks) "
            f"[backend={self._index.backend_name}]"
        )

    def search(self, query: str, top_k: int = 5) -> list[SearchResult]:
        """Busca semântica — retorna os chunks mais similares."""
        if self._index.total == 0:
            return []

        q_emb = self._embeddings.encode([query])            # (1, D) — via deps
        distances, indices = self._index.search(q_emb, top_k)

        results = []
        for dist, idx in zip(distances[0], indices[0]):
            if idx < 0 or idx >= len(self._meta):
                continue
            m = self._meta[int(idx)]
            results.append(
                SearchResult(
                    document_id=m["doc_id"],
                    filename=m["filename"],
                    chunk_text=m["text"],
                    score=float(dist),
                    page=m.get("page"),
                )
            )
        return results

    def remove_document(self, doc_id: str) -> bool:
        if doc_id not in self._doc_registry:
            return False

        kept_meta = [m for m in self._meta if m["doc_id"] != doc_id]
        if kept_meta:
            texts = [m["text"] for m in kept_meta]
            embeddings = self._embeddings.encode(texts)   # via deps
            self._index = deps.VectorIndex()
            self._index.add(embeddings)
        else:
            self._index = deps.VectorIndex()

        self._meta = kept_meta
        del self._doc_registry[doc_id]
        self.save_index()
        return True

    def list_documents(self) -> list[DocumentInfo]:
        return list(self._doc_registry.values())

    def get_document_content(self, doc_id: str) -> dict:
        """
        Retorna conteúdo para visualizador Plain/Rich Text.

        Estratégia:
          1) tenta abrir arquivo de origem (path salvo no meta)
          2) fallback: concatena chunks já indexados
        """
        if doc_id not in self._doc_registry:
            raise FileNotFoundError(f"Documento {doc_id} não encontrado")

        filename = self._doc_registry[doc_id].filename
        source_path = self._resolve_source_path(doc_id, filename)
        ext = Path(filename).suffix.lower()

        if source_path and os.path.exists(source_path):
            try:
                size = os.path.getsize(source_path)
                if size > MAX_VIEWER_BYTES:
                    return {
                        "document_id": doc_id,
                        "filename": filename,
                        "format": ext,
                        "plain_text": (
                            f"Arquivo muito grande para preview ({size} bytes). "
                            "Use download local para leitura completa."
                        ),
                        "rich_html": "",
                        "source_path": source_path,
                    }

                if ext in {".txt", ".md", ".html", ".htm"}:
                    with open(source_path, encoding="utf-8", errors="replace") as f:
                        raw = f.read()
                else:
                    raw = self._chunks_text(doc_id)

                plain_text, rich_html = self._build_preview(raw, ext)
                return {
                    "document_id": doc_id,
                    "filename": filename,
                    "format": ext,
                    "plain_text": plain_text,
                    "rich_html": rich_html,
                    "source_path": source_path,
                }
            except Exception as e:
                logger.warning(f"Falha ao abrir conteúdo de {doc_id}: {e}")

        # Fallback para índice (chunks)
        raw = self._chunks_text(doc_id)
        plain_text, rich_html = self._build_preview(raw, ext)
        return {
            "document_id": doc_id,
            "filename": filename,
            "format": ext,
            "plain_text": plain_text,
            "rich_html": rich_html,
            "source_path": source_path,
        }

    @property
    def backend_info(self) -> dict:
        """Informações sobre backends em uso — útil para /health."""
        return {
            "vector_backend": self._index.backend_name,
            "embeddings_loaded": self._embeddings.loaded,
            "total_vectors": self._index.total,
            "deps": {k: v.available for k, v in deps.probe().items()},
        }

    # ──────────────────────────────────────────────────────────────────────
    # Persistência
    # ──────────────────────────────────────────────────────────────────────

    def save_index(self) -> None:
        os.makedirs(INDEX_DIR, exist_ok=True)
        try:
            self._index.save(VECTOR_INDEX_PATH)          # delega para deps.VectorIndex
            with open(META_PATH, "wb") as f:
                pickle.dump((self._meta, self._doc_registry), f)
            logger.debug("Índice vetorial salvo.")
        except Exception as e:
            logger.error(f"Erro ao salvar índice: {e}")

    def load_index(self) -> None:
        self._index.load(VECTOR_INDEX_PATH)              # delega para deps.VectorIndex
        if os.path.exists(META_PATH):
            try:
                with open(META_PATH, "rb") as f:
                    self._meta, self._doc_registry = pickle.load(f)
            except Exception as e:
                logger.warning(f"Falha ao carregar metadados: {e}")

    def _chunks_text(self, doc_id: str) -> str:
        chunks = [m["text"] for m in self._meta if m.get("doc_id") == doc_id]
        return "\n\n".join(chunks)

    def _resolve_source_path(self, doc_id: str, filename: str) -> str | None:
        # caminho salvo no meta (versões novas)
        for m in self._meta:
            if m.get("doc_id") == doc_id and m.get("source_path"):
                return str(m["source_path"])

        # fallback para índices antigos sem source_path
        guesses = [
            os.path.join("data/uploads", filename),
            os.path.join("data/gutenberg/books", filename),
        ]
        for g in guesses:
            if os.path.exists(g):
                return g
        return None

    def _build_preview(self, raw: str, ext: str) -> tuple[str, str]:
        plain_text = raw.strip()
        rich_html = ""

        if ext == ".md":
            try:
                import markdown
                rich_html = markdown.markdown(plain_text)
                rich_html = self._sanitize_html(rich_html)
            except Exception:
                rich_html = ""
        elif ext in {".html", ".htm"}:
            try:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(raw, "html.parser")
                for tag in soup(["script", "style"]):
                    tag.decompose()
                body = soup.body.decode_contents() if soup.body else str(soup)
                rich_html = self._sanitize_html(body)
                plain_text = soup.get_text(separator="\n").strip()
            except Exception:
                rich_html = ""

        return plain_text, rich_html

    def _sanitize_html(self, html: str) -> str:
        """Sanitização rígida para renderização Rich Text."""
        try:
            import bleach
            from bs4 import BeautifulSoup

            allowed_tags = [
                "p", "br", "strong", "em", "b", "i", "u", "s", "blockquote",
                "code", "pre", "ul", "ol", "li", "h1", "h2", "h3", "h4", "h5", "h6",
                "a", "hr", "table", "thead", "tbody", "tr", "th", "td",
            ]
            allowed_attrs = {
                "a": ["href", "title", "target", "rel"],
                "th": ["colspan", "rowspan"],
                "td": ["colspan", "rowspan"],
            }

            cleaned = bleach.clean(
                html,
                tags=allowed_tags,
                attributes=allowed_attrs,
                protocols=["http", "https", "mailto"],
                strip=True,
                strip_comments=True,
            )

            soup = BeautifulSoup(cleaned, "html.parser")

            for el in soup.find_all(True):
                attrs = dict(el.attrs)
                for attr, val in attrs.items():
                    attr_l = str(attr).lower()
                    val_s = " ".join(val) if isinstance(val, list) else str(val)
                    if attr_l.startswith("on"):
                        del el.attrs[attr]
                        continue
                    if attr_l in {"href", "src"} and val_s.strip().lower().startswith("javascript:"):
                        del el.attrs[attr]

                if el.name == "a":
                    el.attrs["rel"] = "noopener noreferrer nofollow"
                    if "target" not in el.attrs:
                        el.attrs["target"] = "_blank"

            return str(soup)
        except Exception:
            return ""
