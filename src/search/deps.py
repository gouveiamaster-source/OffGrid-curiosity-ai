"""
src/search/deps.py
──────────────────
Wrapper centralizado de TODAS as dependências externas do módulo de busca
semântica.  Nenhum outro arquivo do pacote `search` deve importar
`faiss`, `sentence_transformers`, `numpy` ou `torch` diretamente —
tudo passa por aqui.

Benefícios:
  • Um único lugar para checar disponibilidade / versão de cada dep.
  • Fallback controlado: se FAISS não estiver instalado, um backend
    puro-Python (BruteForce) entra automaticamente.
  • Fácil mockar em testes unitários — basta monkeypatchar este módulo.
  • Troca de backend de embeddings sem tocar em SemanticSearch.
"""

from __future__ import annotations

import importlib
import os
from dataclasses import dataclass
from typing import Any, Optional

from loguru import logger

# ─── Estado de disponibilidade, preenchido em _probe() ─────────────────────

@dataclass
class _DepStatus:
    available: bool
    version: Optional[str] = None
    error: Optional[str] = None


_status: dict[str, _DepStatus] = {}
_probed = False


def probe() -> dict[str, _DepStatus]:
    """
    Verifica (uma única vez) quais backends estão disponíveis.
    Retorna um dict com o status de cada dependência.
    """
    global _probed
    if _probed:
        return _status

    for name, import_name in [
        ("numpy",               "numpy"),
        ("faiss",               "faiss"),
        ("sentence_transformers","sentence_transformers"),
        ("torch",               "torch"),
    ]:
        try:
            mod = importlib.import_module(import_name)
            ver = getattr(mod, "__version__", "?")
            _status[name] = _DepStatus(available=True, version=ver)
            logger.debug(f"[deps] {name} {ver} ✓")
        except ImportError as e:
            _status[name] = _DepStatus(available=False, error=str(e))
            logger.warning(f"[deps] {name} indisponível: {e}")

    _probed = True
    return _status


def report() -> str:
    """Retorna um bloco de texto com o status de cada dependência."""
    s = probe()
    lines = ["── Dependências de Busca Semântica ──"]
    for name, st in s.items():
        if st.available:
            lines.append(f"  ✅ {name:<25} v{st.version}")
        else:
            lines.append(f"  ❌ {name:<25} {st.error}")
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# NUMPY
# ─────────────────────────────────────────────────────────────────────────────

def get_numpy():
    """Retorna o módulo numpy ou lança ImportError com mensagem clara."""
    probe()
    if not _status.get("numpy", _DepStatus(False)).available:
        raise ImportError(
            "numpy não está instalado. Execute: pip install numpy"
        )
    import numpy as np
    return np


# ─────────────────────────────────────────────────────────────────────────────
# EMBEDDINGS  (sentence-transformers)
# ─────────────────────────────────────────────────────────────────────────────

class EmbeddingsBackend:
    """Fachada para geração de embeddings — isola sentence-transformers."""

    def __init__(self, model_name: str):
        self.model_name = model_name
        self._model: Any = None

    def encode(self, texts: list[str]):
        """
        Codifica textos em vetores float32 normalizados.
        Retorna numpy.ndarray de shape (N, D).
        """
        np = get_numpy()
        model = self._load_model()
        vecs = model.encode(
            texts,
            normalize_embeddings=True,
            show_progress_bar=False,
            batch_size=32,
        )
        return np.array(vecs, dtype=np.float32)

    def _load_model(self):
        if self._model is not None:
            return self._model
        probe()
        if not _status.get("sentence_transformers", _DepStatus(False)).available:
            raise ImportError(
                "sentence-transformers não está instalado. "
                "Execute: pip install sentence-transformers"
            )
        from sentence_transformers import SentenceTransformer
        logger.info(f"[deps] Carregando modelo de embeddings: {self.model_name}")
        self._model = SentenceTransformer(self.model_name)
        return self._model

    @property
    def loaded(self) -> bool:
        return self._model is not None


# ─────────────────────────────────────────────────────────────────────────────
# ÍNDICE VETORIAL  (FAISS  ou  BruteForce fallback)
# ─────────────────────────────────────────────────────────────────────────────

class VectorIndex:
    """
    Abstração sobre o índice vetorial.

    Backend primário : FAISS  (IndexFlatIP — cossenoidal com vetores normalizados)
    Backend fallback : BruteForceIndex (puro numpy, mais lento, zero deps extra)

    A interface pública é idêntica independentemente do backend escolhido.
    """

    def __init__(self, dim: Optional[int] = None):
        self._dim = dim
        self._backend: Optional[str] = None   # "faiss" | "brute"
        self._index: Any = None               # objeto do backend

    # ── API pública ────────────────────────────────────────────────────────

    def add(self, vectors) -> None:
        """Adiciona vetores ao índice. vectors: numpy.ndarray (N, D)"""
        np = get_numpy()
        vectors = np.array(vectors, dtype=np.float32)
        if self._dim is None:
            self._dim = vectors.shape[1]
        self._ensure_index()
        if self._backend == "faiss":
            self._index.add(vectors)
        else:
            self._index["vectors"] = np.vstack(
                [self._index["vectors"], vectors]
            ) if self._index["vectors"] is not None else vectors

    def search(self, query_vec, top_k: int) -> tuple:
        """
        Retorna (distances, indices) como numpy arrays, igual à API FAISS.
        query_vec: numpy.ndarray (1, D)
        """
        np = get_numpy()
        if self._index is None or self.total == 0:
            return np.array([[]]), np.array([[]], dtype=np.int64)

        top_k = min(top_k, self.total)

        if self._backend == "faiss":
            return self._index.search(query_vec, top_k)
        else:
            # BruteForce: produto interno (cossenoidal com normalização)
            vecs = self._index["vectors"]           # (N, D)
            scores = (vecs @ query_vec[0]).flatten() # (N,)
            idx = np.argsort(scores)[::-1][:top_k]
            return scores[idx].reshape(1, -1), idx.reshape(1, -1)

    def reset(self) -> None:
        """Limpa o índice mantendo o backend."""
        self._index = None
        self._ensure_index()

    @property
    def total(self) -> int:
        if self._index is None:
            return 0
        if self._backend == "faiss":
            return self._index.ntotal
        return len(self._index["vectors"]) if self._index["vectors"] is not None else 0

    @property
    def backend_name(self) -> str:
        return self._backend or "uninitialised"

    # ── Persistência delegada ──────────────────────────────────────────────

    def save(self, path: str) -> None:
        """Persiste o índice em disco."""
        import pickle, os        # noqa: E401
        os.makedirs(os.path.dirname(path), exist_ok=True)
        if self._backend == "faiss" and self._index is not None:
            import faiss
            faiss.write_index(self._index, path)
        else:
            with open(path + ".pkl", "wb") as f:
                pickle.dump(self._index, f)

    def load(self, path: str) -> bool:
        """Carrega índice de disco. Retorna True se bem-sucedido."""
        import pickle            # noqa: E401
        probe()

        # Tenta FAISS primeiro
        if _status.get("faiss", _DepStatus(False)).available and os.path.exists(path):
            try:
                import faiss
                self._index = faiss.read_index(path)
                self._dim = self._index.d
                self._backend = "faiss"
                logger.info(
                    f"[deps] Índice FAISS carregado: {self._index.ntotal} vetores "
                    f"(dim={self._dim})"
                )
                return True
            except Exception as e:
                logger.warning(f"[deps] Falha ao carregar FAISS: {e}")

        # Fallback BruteForce
        pkl_path = path + ".pkl"
        if os.path.exists(pkl_path):
            try:
                with open(pkl_path, "rb") as f:
                    self._index = pickle.load(f)
                self._backend = "brute"
                np = get_numpy()
                if self._index and self._index.get("vectors") is not None:
                    self._dim = self._index["vectors"].shape[1]
                logger.info(
                    f"[deps] Índice BruteForce carregado: "
                    f"{self.total} vetores"
                )
                return True
            except Exception as e:
                logger.warning(f"[deps] Falha ao carregar BruteForce pkl: {e}")

        return False

    # ── Interno ────────────────────────────────────────────────────────────

    def _ensure_index(self) -> None:
        if self._index is not None:
            return
        probe()
        if _status.get("faiss", _DepStatus(False)).available:
            import faiss
            self._index = faiss.IndexFlatIP(self._dim or 384)
            self._backend = "faiss"
            logger.debug(
                f"[deps] Backend FAISS inicializado (dim={self._dim or 384})"
            )
        else:
            np = get_numpy()
            self._index = {"vectors": None}
            self._backend = "brute"
            logger.warning(
                "[deps] FAISS indisponível — usando BruteForceIndex (numpy). "
                "Instale faiss-cpu para melhor performance."
            )
