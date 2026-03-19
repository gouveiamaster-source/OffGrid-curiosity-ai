"""
Módulo de busca semântica.

Hierarquia de dependências:
	semantic_search.py   ← lógica de negócio
	deps.py              ← wrapper único de todas as deps externas
													(faiss, sentence-transformers, numpy, torch)
"""

from src.search.deps import probe, report, EmbeddingsBackend, VectorIndex

__all__ = ["probe", "report", "EmbeddingsBackend", "VectorIndex"]
