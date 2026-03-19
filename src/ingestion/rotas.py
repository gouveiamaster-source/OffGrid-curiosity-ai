"""
Rotas FastAPI para ingestão de documentos e gestão do acervo.

Endpoints:
  POST   /ingest                      — envia um documento para indexação
  GET    /documents                   — lista documentos indexados
  GET    /documents/{doc_id}/content  — conteúdo de um documento
  DELETE /documents/{doc_id}          — remove documento do índice e do grafo
"""

from __future__ import annotations

import os
import re
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

from src.container import graph, loader, search_engine
from src.models.schemas import DocumentInfo, IngestResponse

router = APIRouter(tags=["Ingestão", "Documentos"])

# ---------------------------------------------------------------------------
# Configuração de upload (sobrescrita via variáveis de ambiente)
# ---------------------------------------------------------------------------
ALLOWED_EXTENSIONS = {
    ".pdf", ".txt", ".md", ".html", ".htm",
    ".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp",
}
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
MAX_UPLOAD_BYTES: int = int(os.getenv("MAX_UPLOAD_BYTES", str(10 * 1024 * 1024)))
PUBLIC_UPLOAD_ENABLED: bool = os.getenv("PUBLIC_UPLOAD_ENABLED", "true").lower() == "true"


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/ingest", response_model=IngestResponse, tags=["Ingestão"])
async def ingest_document(file: UploadFile = File(...)):
    """
    Recebe um documento (PDF, TXT, MD, HTML, imagem), extrai texto,
    indexa para busca semântica e atualiza o grafo de conhecimento.
    """
    if not PUBLIC_UPLOAD_ENABLED:
        raise HTTPException(
            status_code=403,
            detail="Upload público desativado pelo administrador.",
        )

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

    doc = loader.load(save_path)
    graph.add_document(doc)
    search_engine.add_document(doc)
    search_engine.save_index()

    return IngestResponse(
        document_id=doc.id,
        filename=candidate,
        chunks=len(doc.chunks),
        entities=len(doc.entities),
    )


@router.get("/documents", response_model=list[DocumentInfo], tags=["Documentos"])
async def list_documents():
    """Lista todos os documentos indexados."""
    return search_engine.list_documents()


@router.get("/documents/{doc_id}/content", tags=["Documentos"])
async def document_content(doc_id: str):
    """Retorna payload para visualizador Plain/Rich Text."""
    try:
        return search_engine.get_document_content(doc_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Documento não encontrado.")


@router.delete("/documents/{doc_id}", tags=["Documentos"])
async def delete_document(doc_id: str):
    """Remove um documento do índice e do grafo."""
    removed = search_engine.remove_document(doc_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Documento não encontrado.")
    graph.remove_document(doc_id)
    return {"detail": f"Documento {doc_id} removido com sucesso."}
