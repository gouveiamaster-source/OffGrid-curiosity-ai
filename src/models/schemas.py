"""Schemas Pydantic — re-exportados do pacote models."""

from src.models import (
    SearchRequest,
    SearchResult,
    SearchResponse,
    DocumentInfo,
    IngestResponse,
    GraphStats,
    GutenbergBookMeta,
    ProspectRequest,
    ProspectResult,
    ProspectResponse,
    CatalogStats,
)

__all__ = [
    "SearchRequest",
    "SearchResult",
    "SearchResponse",
    "DocumentInfo",
    "IngestResponse",
    "GraphStats",
    "GutenbergBookMeta",
    "ProspectRequest",
    "ProspectResult",
    "ProspectResponse",
    "CatalogStats",
]
