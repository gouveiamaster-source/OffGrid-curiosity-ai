# Estrutura de Routers (Branches de Código) — Alexandria-AI

Este documento descreve como o código da API está dividido em **routers FastAPI**
independentes — cada um responsável por um domínio funcional do sistema.

## Visão geral

```
main.py                      ← ponto de entrada; registra todos os routers
src/container.py             ← singletons compartilhados (loader, graph, search_engine, gutenberg)
│
├── src/ingestion/rotas.py   ← POST /ingest, GET|DELETE /documents
├── src/search/rotas.py      ← POST /search
├── src/knowledge/rotas.py   ← GET /graph/*
├── src/prospectors/rotas.py ← GET|POST /prospector/gutenberg/*
└── src/dosimetria/rotas.py  ← POST|GET /dosimetria/*
```

## Tabela de routers

| Arquivo | Prefixo / Tags | Endpoints |
|---|---|---|
| `src/ingestion/rotas.py` | Tags: Ingestão, Documentos | `POST /ingest`, `GET /documents`, `GET /documents/{id}/content`, `DELETE /documents/{id}` |
| `src/search/rotas.py` | Tags: Busca | `POST /search` |
| `src/knowledge/rotas.py` | Prefixo: `/graph` · Tags: Grafo | `GET /graph/stats`, `GET /graph/nodes`, `GET /graph/edges` |
| `src/prospectors/rotas.py` | Prefixo: `/prospector/gutenberg` · Tags: Gutenberg | `GET /catalog`, `GET /stats`, `GET /search`, `POST /prospect` |
| `src/dosimetria/rotas.py` | Prefixo: `/dosimetria` · Tags: Dosimetria | `POST /calcular`, `GET /limites`, `POST /conformidade` |

## Como adicionar um novo router

1. Crie `src/<módulo>/rotas.py` com um `APIRouter`:

```python
from fastapi import APIRouter
from src.container import search_engine  # importe só o que precisar

router = APIRouter(prefix="/meu-modulo", tags=["Meu Módulo"])

@router.get("/exemplo")
async def exemplo():
    return {"ok": True}
```

2. Registre em `main.py`:

```python
from src.meu_modulo.rotas import router as meu_modulo_router
# ...
app.include_router(meu_modulo_router)
```

## Singletons compartilhados (`src/container.py`)

Todos os routers importam os singletons a partir de `src.container` para garantir
que uma única instância de cada componente seja usada em toda a aplicação:

| Singleton | Tipo | Finalidade |
|---|---|---|
| `loader` | `DocumentLoader` | Carrega e fragmenta documentos |
| `graph` | `KnowledgeGraph` | Grafo de entidades e relações |
| `search_engine` | `SemanticSearch` | Índice vetorial e busca semântica |
| `gutenberg` | `GutenbergProspector` | Download e indexação de livros do Gutenberg |

## Branches de dosimetria (histórico)

A ferramentaria de dosimetria foi desenvolvida em branches encadeados:

| Branch | Propósito |
|---|---|
| `feature/dosimetria-modelos` | Modelos Pydantic, enums de unidades e tipos de radiação |
| `feature/dosimetria-calculo` | Motor de cálculo, fatores wR, conversão de unidades, limites CNEN |
| `feature/dosimetria-integracao` | Rotas FastAPI, integração com busca semântica e grafo |
| `feature/dosimetria-interface` | Aba "☢️ Dosimetria" no frontend, calculadora interativa |

Para criar esses branches localmente execute:

```bash
bash scripts/setup_dosimetria_branches.sh
```

Consulte `docs/DOSIMETRIA-BRANCHES.md` para o guia completo de dosimetria.
