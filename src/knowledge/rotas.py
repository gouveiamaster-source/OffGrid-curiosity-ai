"""
Rotas FastAPI para o grafo de conhecimento.

Endpoints:
  GET /graph/stats  — estatísticas do grafo (nós, arestas)
  GET /graph/nodes  — lista de nós (entidades e documentos)
  GET /graph/edges  — lista de arestas (relações)
"""

from __future__ import annotations

from fastapi import APIRouter

from src.container import graph
from src.models.schemas import GraphStats

router = APIRouter(prefix="/graph", tags=["Grafo"])


@router.get("/stats", response_model=GraphStats, summary="Estatísticas do grafo")
async def graph_stats():
    """Estatísticas do grafo de conhecimento."""
    return graph.stats()


@router.get("/nodes", summary="Nós do grafo")
async def graph_nodes(limit: int = 100):
    """Retorna nós do grafo (entidades e documentos)."""
    return graph.get_nodes(limit=limit)


@router.get("/edges", summary="Arestas do grafo")
async def graph_edges(limit: int = 200):
    """Retorna arestas do grafo (relações)."""
    return graph.get_edges(limit=limit)
