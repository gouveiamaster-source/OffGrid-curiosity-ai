"""
Rotas FastAPI para busca semântica.

Endpoints:
  POST /search — busca semântica sobre os documentos indexados
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from src.container import search_engine
from src.models.schemas import SearchRequest, SearchResponse

router = APIRouter(tags=["Busca"])


@router.post("/search", response_model=SearchResponse, tags=["Busca"])
async def semantic_search(request: SearchRequest):
    """Busca semântica sobre os documentos indexados."""
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="A query não pode ser vazia.")

    results = search_engine.search(request.query, top_k=request.top_k)
    return SearchResponse(query=request.query, results=results)
