"""
Alexandria-AI — Motor de conhecimento off-grid inspirado no curiosity-ai.
Ponto de entrada da API FastAPI.

Routers registrados
───────────────────
• src.ingestion.rotas   — POST /ingest, GET|DELETE /documents
• src.search.rotas      — POST /search
• src.knowledge.rotas   — GET /graph/*
• src.prospectors.rotas — GET|POST /prospector/gutenberg/*
• src.dosimetria.rotas  — POST|GET /dosimetria/*
"""

import os
import shutil
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger

from src.container import graph, loader, search_engine
from src.dosimetria.rotas import router as dosimetria_router
from src.ingestion.rotas import MAX_UPLOAD_BYTES, PUBLIC_UPLOAD_ENABLED, router as ingestion_router
from src.knowledge.rotas import router as knowledge_router
from src.prospectors.rotas import router as prospectors_router
from src.search.rotas import router as search_router

# ---------------------------------------------------------------------------
# Configuração de semente (Fábulas de Esopo)
# ---------------------------------------------------------------------------
SEED_AESOP_ON_STARTUP: bool = os.getenv("SEED_AESOP_ON_STARTUP", "true").lower() == "true"
SEED_SOURCE_FILE = "src/seed/material_inicial_fabulas_de_esopo.txt"
SEED_TARGET_FILE = "data/uploads/material_inicial_fabulas_de_esopo.txt"


def _ensure_default_aesop_material() -> None:
    """
    Garante Fábulas de Esopo como material inicial padrão.

    Regra:
      - Se já existe documento com esse filename no índice, não faz nada.
      - Se não existe, copia o arquivo seed para uploads e indexa.
    """
    if not SEED_AESOP_ON_STARTUP:
        return

    existing_names = {d.filename for d in search_engine.list_documents()}
    seed_name = os.path.basename(SEED_TARGET_FILE)
    if seed_name in existing_names:
        return

    if not os.path.exists(SEED_SOURCE_FILE):
        logger.warning(f"Seed padrão não encontrado em {SEED_SOURCE_FILE}")
        return

    os.makedirs(os.path.dirname(SEED_TARGET_FILE), exist_ok=True)
    shutil.copyfile(SEED_SOURCE_FILE, SEED_TARGET_FILE)

    doc = loader.load(SEED_TARGET_FILE)
    graph.add_document(doc)
    search_engine.add_document(doc)
    search_engine.save_index()
    logger.info("Material inicial padrão carregado: Fábulas de Esopo")


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Inicializa componentes pesados uma única vez na subida."""
    search_engine.load_index()
    _ensure_default_aesop_material()
    yield
    search_engine.save_index()


# ---------------------------------------------------------------------------
# Aplicação
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Alexandria-AI",
    description="Motor de conhecimento local, off-grid, inspirado no curiosity-ai.",
    version="0.1.0",
    lifespan=lifespan,
)

# Serve o frontend estático
app.mount("/static", StaticFiles(directory="static"), name="static")

os.makedirs("data/uploads", exist_ok=True)
os.makedirs("data/index", exist_ok=True)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
app.include_router(ingestion_router)
app.include_router(search_router)
app.include_router(knowledge_router)
app.include_router(prospectors_router)
app.include_router(dosimetria_router)


# ---------------------------------------------------------------------------
# Rotas principais
# ---------------------------------------------------------------------------


@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve a interface principal."""
    return FileResponse("static/index.html")


@app.get("/health", tags=["Sistema"])
async def health():
    """Estado do sistema: documentos indexados, grafo, configuração."""
    return {
        "status": "ok",
        "documents_indexed": len(search_engine.list_documents()),
        "graph_nodes": graph.stats().nodes,
        "public_upload_enabled": PUBLIC_UPLOAD_ENABLED,
        "max_upload_bytes": MAX_UPLOAD_BYTES,
        "seed_aesop_on_startup": SEED_AESOP_ON_STARTUP,
        **loader.ocr_info,
        **search_engine.backend_info,
    }
