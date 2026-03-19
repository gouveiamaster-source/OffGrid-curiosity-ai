"""Schemas Pydantic compartilhados."""

from pydantic import BaseModel, Field
from typing import Optional


class SearchRequest(BaseModel):
    query: str = Field(..., description="Texto da consulta semântica")
    top_k: int = Field(default=5, ge=1, le=50, description="Número de resultados")


class SearchResult(BaseModel):
    document_id: str
    filename: str
    chunk_text: str
    score: float
    page: Optional[int] = None


class SearchResponse(BaseModel):
    query: str
    results: list[SearchResult]


class DocumentInfo(BaseModel):
    document_id: str
    filename: str
    chunks: int
    entities: int


class IngestResponse(BaseModel):
    document_id: str
    filename: str
    chunks: int
    entities: int


class GraphStats(BaseModel):
    nodes: int
    edges: int
    documents: int
    entities: int


# ── Prospector Gutenberg ──────────────────────────────────────────────────

class GutenbergBookMeta(BaseModel):
    id: int
    title: str
    authors: list[str]
    languages: list[str]
    subjects: list[str]
    download_count: int
    local_path: Optional[str] = None
    ingested: bool = False


class ProspectRequest(BaseModel):
    query: str = Field(default="", description="Busca textual no catálogo Gutenberg")
    book_ids: list[int] = Field(default_factory=list, description="IDs específicos de livros")
    languages: list[str] = Field(default_factory=list, description="Filtro de idioma (ex: pt, en)")
    topic: str = Field(default="", description="Filtro de assunto/tópico")
    limit: int = Field(default=5, ge=1, le=20, description="Máximo de livros a prospectar")
    skip_already_ingested: bool = Field(default=True)


class ProspectResult(BaseModel):
    book_id: int
    title: str
    authors: list[str]
    languages: list[str]
    subjects: list[str]
    status: str          # ok | already_indexed | download_failed | ingest_failed | downloaded_only
    document_id: Optional[str] = None
    chunks: int = 0
    entities: int = 0
    error: Optional[str] = None


class ProspectResponse(BaseModel):
    total: int
    results: list[ProspectResult]


class CatalogStats(BaseModel):
    total_catalogued: int
    downloaded: int
    ingested: int
