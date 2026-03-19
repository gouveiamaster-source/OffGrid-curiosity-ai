"""
Alexandria-AI — Motor de conhecimento off-grid inspirado no curiosity-ai.
Ponto de entrada da API FastAPI.
"""

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from contextlib import asynccontextmanager
import os
import re
import shutil
from pathlib import Path
from loguru import logger

from src.ingestion.document_loader import DocumentLoader
from src.knowledge.graph import KnowledgeGraph
from src.search.semantic_search import SemanticSearch
from src.prospectors.gutenberg import GutenbergProspector
from src.models.schemas import (
    SearchRequest,
    SearchResponse,
    DocumentInfo,
    GraphStats,
    IngestResponse,
    ProspectRequest,
    ProspectResponse,
    ProspectResult,
    GutenbergBookMeta,
    CatalogStats,
)

# ---------------------------------------------------------------------------
# Singletons compartilhados
# ---------------------------------------------------------------------------
loader = DocumentLoader()
graph = KnowledgeGraph()
search_engine = SemanticSearch()
gutenberg = GutenbergProspector(search_engine=search_engine, graph=graph)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Inicializa componentes pesados uma única vez na subida."""
    search_engine.load_index()
    _ensure_default_aesop_material()
    yield
    search_engine.save_index()


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

ALLOWED_EXTENSIONS = {".pdf", ".txt", ".md", ".html", ".htm", ".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp"}
ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "text/plain",
    "text/markdown",
    "text/html",
    "application/xhtml+xml",
    "image/png",
    "image/jpeg",
    "image/bmp",
    "image/tiff",
    "image/webp",
}
MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_BYTES", str(10 * 1024 * 1024)))
PUBLIC_UPLOAD_ENABLED = os.getenv("PUBLIC_UPLOAD_ENABLED", "true").lower() == "true"
SEED_AESOP_ON_STARTUP = os.getenv("SEED_AESOP_ON_STARTUP", "true").lower() == "true"

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
# Rotas
# ---------------------------------------------------------------------------


@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve a interface principal."""
    return FileResponse("static/index.html")


@app.post("/ingest", response_model=IngestResponse, tags=["Ingestão"])
async def ingest_document(file: UploadFile = File(...)):
    """
    Recebe um documento (PDF, TXT, MD, HTML), extrai texto,
    indexa para busca semântica e atualiza o grafo de conhecimento.
    """
    if not PUBLIC_UPLOAD_ENABLED:
        raise HTTPException(status_code=403, detail="Upload público desativado pelo administrador.")

    original_name = file.filename or "upload"
    safe_name = Path(original_name).name
    safe_name = re.sub(r"[^a-zA-Z0-9._ -]", "_", safe_name).strip()
    if not safe_name:
        raise HTTPException(status_code=400, detail="Nome de arquivo inválido.")

    ext = os.path.splitext(safe_name)[-1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Tipo de arquivo não suportado: {ext}. Aceitos: {ALLOWED_EXTENSIONS}",
        )

    if file.content_type and file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Content-Type não permitido: {file.content_type}. "
                f"Aceitos: {ALLOWED_CONTENT_TYPES}"
            ),
        )

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Arquivo vazio.")
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Arquivo excede limite de {MAX_UPLOAD_BYTES} bytes.",
        )

    # Evita overwrite silencioso em upload público
    base, ext = os.path.splitext(safe_name)
    candidate = safe_name
    counter = 1
    while os.path.exists(os.path.join("data/uploads", candidate)):
        candidate = f"{base}_{counter}{ext}"
        counter += 1

    save_path = os.path.join("data/uploads", candidate)
    with open(save_path, "wb") as f:
        f.write(content)

    # Extrai texto
    doc = loader.load(save_path)

    # Atualiza grafo e índice de busca
    graph.add_document(doc)
    search_engine.add_document(doc)
    search_engine.save_index()

    return IngestResponse(
        document_id=doc.id,
        filename=candidate,
        chunks=len(doc.chunks),
        entities=len(doc.entities),
    )


@app.get("/documents/{doc_id}/content", tags=["Documentos"])
async def document_content(doc_id: str):
    """
    Retorna payload para visualizador Plain/Rich Text.
    """
    try:
        return search_engine.get_document_content(doc_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Documento não encontrado.")


@app.post("/search", response_model=SearchResponse, tags=["Busca"])
async def semantic_search(request: SearchRequest):
    """Busca semântica sobre os documentos indexados."""
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="A query não pode ser vazia.")

    results = search_engine.search(request.query, top_k=request.top_k)
    return SearchResponse(query=request.query, results=results)


@app.get("/documents", response_model=list[DocumentInfo], tags=["Documentos"])
async def list_documents():
    """Lista todos os documentos indexados."""
    return search_engine.list_documents()


@app.delete("/documents/{doc_id}", tags=["Documentos"])
async def delete_document(doc_id: str):
    """Remove um documento do índice e do grafo."""
    removed = search_engine.remove_document(doc_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Documento não encontrado.")
    graph.remove_document(doc_id)
    return {"detail": f"Documento {doc_id} removido com sucesso."}


@app.get("/graph/stats", response_model=GraphStats, tags=["Grafo"])
async def graph_stats():
    """Estatísticas do grafo de conhecimento."""
    return graph.stats()


@app.get("/graph/nodes", tags=["Grafo"])
async def graph_nodes(limit: int = 100):
    """Retorna nós do grafo (entidades e documentos)."""
    return graph.get_nodes(limit=limit)


@app.get("/graph/edges", tags=["Grafo"])
async def graph_edges(limit: int = 200):
    """Retorna arestas do grafo (relações)."""
    return graph.get_edges(limit=limit)


@app.get("/health", tags=["Sistema"])
async def health():
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


# ---------------------------------------------------------------------------
# Rotas — Prospector Gutenberg
# ---------------------------------------------------------------------------

@app.get("/prospector/gutenberg/catalog", response_model=list[GutenbergBookMeta], tags=["Gutenberg"])
async def gutenberg_catalog():
    """Lista os livros já prospectados no catálogo local."""
    raw = gutenberg.get_cached_books()
    return [GutenbergBookMeta(**b) for b in raw]


@app.get("/prospector/gutenberg/stats", response_model=CatalogStats, tags=["Gutenberg"])
async def gutenberg_stats():
    """Estatísticas do catálogo local do Gutenberg."""
    return CatalogStats(**gutenberg.catalog_stats())


@app.get("/prospector/gutenberg/search", response_model=list[GutenbergBookMeta], tags=["Gutenberg"])
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
    languages = [l.strip() for l in lang.split(",") if l.strip()] if lang else []
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


@app.post("/prospector/gutenberg/prospect", response_model=ProspectResponse, tags=["Gutenberg"])
async def gutenberg_prospect(request: ProspectRequest):
    """
    Prospecta livros do Project Gutenberg:
    faz download do texto puro e indexa no Alexandria-AI.

    Aceita busca por query/idioma ou IDs específicos.
    """
    from fastapi.concurrency import run_in_threadpool

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
