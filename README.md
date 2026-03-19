# Alexandria-AI

Alexandria-AI e uma base de conhecimento local (off-grid) para:

- indexar documentos
- buscar por significado (busca semantica)
- visualizar conteudo em plain/rich text
- extrair texto de PDFs escaneados e imagens com OCR
- explorar grafo de entidades
- coletar e indexar livros do Project Gutenberg

Tudo local, com foco em privacidade e soberania de dados.

Material inicial padrao:

- Fábulas de Esopo (carregadas automaticamente no startup)

## Demo rapida

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m spacy download pt_core_news_sm
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Abra: `http://localhost:8000`

## One click para navegador

Opcao 1 (terminal, 1 comando):

```bash
/home/codespace/.python/current/bin/python scripts/one_click_browser.py --reload
```

Opcao 2 (VS Code, 1 clique):

1. Abra `Run Task` no VS Code.
2. Execute a task: `One Click: Abrir no Navegador`.

Opcao 3 (Run and Debug, 1 clique):

1. Abra `Run and Debug` no VS Code.
2. Execute a configuracao: `Alexandria One Click`.

Opcao 4 (arquivo raiz):

```bash
/home/codespace/.python/current/bin/python start_one_click.py --host 0.0.0.0 --reload
```

O launcher sobe a API e abre automaticamente no navegador padrao.

Se aparecer HTTP 401 em ambiente remoto/container, normalmente era a URL de abertura do navegador e nao a API. O launcher agora sobe em `0.0.0.0` e tenta abrir `127.0.0.1` via mecanismo de navegador do ambiente.

## O que voce encontra na interface

1. Upload seguro de arquivos (PDF, TXT, MD, HTML e imagens)
2. Busca semantica com ranking de relevancia
3. Visualizador Plain/Rich para documentos indexados
4. Grafo de conhecimento (entidades e relacoes)
5. Aba Gutenberg para busca e indexacao de livros

## Upload publico (protecao ativa)

Regras aplicadas automaticamente:

- validacao de extensao e content-type
- limite de tamanho por arquivo
- sanitizacao de nome do arquivo
- bloqueio de arquivo vazio
- prevencao de sobrescrita silenciosa
- sanitizacao forte da saida rich text (backend + frontend)

Variaveis principais:

```env
PUBLIC_UPLOAD_ENABLED=true
MAX_UPLOAD_BYTES=10485760
SEED_AESOP_ON_STARTUP=true
OCR_ENGINE_ENABLED=true
OCR_LANGUAGES=por+eng
OCR_FORCE_PDF=false
OCR_MAX_PDF_PAGES=12
OCR_MIN_PDF_CHARS=120
```

Dependencias de sistema para OCR (Linux, apenas fora do container):

```bash
sudo apt-get update && sudo apt-get install -y tesseract-ocr poppler-utils
```

## Container zero absoluto

O container ja inclui OCR completo:

- tesseract-ocr
- tesseract-ocr-por
- tesseract-ocr-eng
- poppler-utils

```bash
docker build -f Dockerfile.zero-absoluto -t alexandria-zero-absoluto .
docker run --rm -p 8000:8000 \
	-e OCR_ENGINE_ENABLED=true \
	-e OCR_LANGUAGES=por+eng \
	-v $(pwd)/data:/app/data \
	alexandria-zero-absoluto
```

## Documentacao completa

Guia tecnico rapido:

- [docs/GUIA-TECNICO-RAPIDO.md](docs/GUIA-TECNICO-RAPIDO.md)

Guia operacional em baixissimo ruido:

- [docs/GUIA-OPERACIONAL-BAIXO-RUIDO.md](docs/GUIA-OPERACIONAL-BAIXO-RUIDO.md)

Explicacao simples do intuito do projeto:

- [docs/INTUITO-EXPLICADO-SIMPLES.md](docs/INTUITO-EXPLICADO-SIMPLES.md)

## Licenca

MIT