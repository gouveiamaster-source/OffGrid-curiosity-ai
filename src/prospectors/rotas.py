"""
Rotas FastAPI para o Prospector do Project Gutenberg.

Endpoints:
  GET  /prospector/gutenberg/catalog  — catálogo local de livros prospectados
  GET  /prospector/gutenberg/stats    — estatísticas do catálogo local
  GET  /prospector/gutenberg/search   — consulta catálogo Gutendex (requer internet)
  POST /prospector/gutenberg/prospect — download e indexação de livros
"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.concurrency import run_in_threadpool

from src.container import gutenberg
from src.models.schemas import (
    CatalogStats,
    GutenbergBookMeta,
    ProspectRequest,
    ProspectResponse,
    ProspectResult,
)

router = APIRouter(prefix="/prospector/gutenberg", tags=["Gutenberg"])


@router.get("/catalog", response_model=list[GutenbergBookMeta], summary="Catálogo local")
async def gutenberg_catalog():
    """Lista os livros já prospectados no catálogo local."""
    raw = gutenberg.get_cached_books()
    return [GutenbergBookMeta(**b) for b in raw]


@router.get("/stats", response_model=CatalogStats, summary="Estatísticas do catálogo")
async def gutenberg_stats():
    """Estatísticas do catálogo local do Gutenberg."""
    return CatalogStats(**gutenberg.catalog_stats())


@router.get(
    "/search",
    response_model=list[GutenbergBookMeta],
    summary="Buscar no Gutendex (requer internet)",
)
async def gutenberg_search(
    q: str = "",
    lang: str = "",
    topic: str = "",
    limit: int = 20,
):
    """
    Consulta o catálogo Gutendex (requer internet) e retorna metadados.
    Não faz download nem indexa — apenas lista.
    """
    languages = [lang_code.strip() for lang_code in lang.split(",") if lang_code.strip()] if lang else []
    books = gutenberg.search_catalog(
        query=q, languages=languages, topic=topic, limit=min(limit, 40)
    )
    return [
        GutenbergBookMeta(
            id=b.id,
            title=b.title,
            authors=b.authors,
            languages=b.languages,
            subjects=b.subjects,
            download_count=b.download_count,
            local_path=b.local_path,
            ingested=b.ingested,
        )
        for b in books
    ]


@router.post(
    "/prospect",
    response_model=ProspectResponse,
    summary="Prospectar e indexar livros do Gutenberg",
)
async def gutenberg_prospect(request: ProspectRequest):
    """
    Prospecta livros do Project Gutenberg:
    faz download do texto puro e indexa no Alexandria-AI.

    Aceita busca por query/idioma ou IDs específicos.
    """
    results_raw = await run_in_threadpool(
        gutenberg.prospect,
        request.query,
        request.book_ids or None,
        request.languages or None,
        request.topic,
        request.limit,
        request.skip_already_ingested,
    )

    results = [
        ProspectResult(
            book_id=r.book_id,
            title=r.title,
            authors=r.authors,
            languages=r.languages,
            subjects=r.subjects,
            status=r.status,
            document_id=r.document_id,
            chunks=r.chunks,
            entities=r.entities,
            error=r.error,
        )
        for r in results_raw
    ]

    return ProspectResponse(total=len(results), results=results)
