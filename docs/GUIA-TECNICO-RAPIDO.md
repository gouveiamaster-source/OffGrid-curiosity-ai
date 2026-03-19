# Guia Tecnico Rapido - Alexandria-AI

Alexandria-AI e um motor de conhecimento local (off-grid).
Voce envia documentos, o sistema indexa o conteudo e permite:

- busca semantica
- visualizacao de texto (plain/rich)
- grafo de entidades
- prospeccao de livros do Project Gutenberg

Nenhum dado precisa sair da sua maquina.

Material inicial padrao:

- Fábulas de Esopo (indexadas automaticamente no startup)

## Inicio rapido

### 1) Instalar

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m spacy download pt_core_news_sm
python -m spacy download en_core_web_sm
```

### 2) Rodar

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Abra no navegador:

```text
http://localhost:8000
```

## Como usar

### Upload e indexacao

1. Arraste ou selecione um arquivo (PDF, TXT, MD, HTML).
2. O sistema extrai texto, cria chunks e indexa para busca.
3. O documento aparece na lista lateral.

### Busca semantica

1. Digite uma pergunta no campo de busca.
2. Escolha Top 3, 5 ou 10.
3. Veja os trechos mais relevantes.

### Visualizador Plain/Rich

1. Clique em olho na lista de documentos.
2. Na aba Visualizador:
   - Plain: texto cru
   - Rich: renderizacao para markdown/html sanitizado

Endpoint usado:

```text
GET /documents/{doc_id}/content
```

### Gutenberg (coleta automatica)

Na aba Gutenberg voce pode:

- buscar livros
- baixar e indexar direto
- acompanhar catalogo local

## Upload publico (regras obrigatorias)

Quando upload publico estiver habilitado, o sistema aplica:

- extensoes permitidas: .pdf .txt .md .html .htm
- validacao de content-type
- sanitizacao do nome do arquivo
- bloqueio de arquivo vazio
- limite de tamanho por arquivo
- evita sobrescrita automatica de nomes

Variaveis principais:

```env
PUBLIC_UPLOAD_ENABLED=true
MAX_UPLOAD_BYTES=10485760
SEED_AESOP_ON_STARTUP=true
```

Se `PUBLIC_UPLOAD_ENABLED=false`, o endpoint de upload retorna 403.

## Container zero absoluto

Arquivos:

- Dockerfile.zero-absoluto
- .dockerignore

Build e execucao:

```bash
docker build -f Dockerfile.zero-absoluto -t alexandria-zero-absoluto .
docker run --rm -p 8000:8000 \
   -e OCR_ENGINE_ENABLED=true \
   -e OCR_LANGUAGES=por+eng \
   -v $(pwd)/data:/app/data \
   alexandria-zero-absoluto
```

Esta imagem ja inclui runtime OCR:

- tesseract-ocr
- tesseract-ocr-por
- tesseract-ocr-eng
- poppler-utils

## Estrutura resumida

```text
main.py                # API principal
static/index.html      # Interface web
src/ingestion/         # Leitura de documentos
src/search/            # Busca semantica
src/knowledge/         # Grafo
src/prospectors/       # Gutenberg
scripts/               # Scripts utilitarios
```

## Licenca

MIT
