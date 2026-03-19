# Guia Operacional de Baixo Ruido - Alexandria-AI

## Objetivo

Este guia descreve o Alexandria-AI do ponto de vista operacional.

A meta do projeto e simples:

- ingerir documentos locais
- extrair texto de forma previsivel
- indexar para busca semantica
- expor visualizacao segura
- manter grafo e catalogo local com o minimo de atrito operacional

O criterio principal nao e exibicao.
O criterio principal e previsibilidade.

## O que o sistema faz

O sistema recebe documentos e os transforma em quatro saidas principais:

1. texto normalizado para analise
2. chunks para indexacao semantica
3. entidades para o grafo
4. preview plain e rich text para leitura

Fontes atualmente suportadas:

- PDF
- TXT
- Markdown
- HTML
- imagens suportadas pelo OCR
- textos prospectados do Project Gutenberg

## Como o fluxo funciona

### 1. Ingestao

O arquivo entra pelo endpoint de upload ou por prospeccao.
Antes de qualquer indexacao, o sistema valida:

- extensao
- content-type
- tamanho maximo
- nome do arquivo
- existencia de conteudo

Se o arquivo for aceito, ele e persistido em disco local.

### 2. Extracao

O carregador escolhe o parser de acordo com a extensao.

- PDF: tenta extracao nativa primeiro
- imagem: usa OCR
- Markdown: converte para HTML e extrai texto
- HTML: remove elementos inseguros e extrai texto
- TXT: leitura direta

### 3. OCR

O OCR e opcional, mas pode operar como caminho principal para imagens e como fallback para PDFs escaneados.

Controles principais:

- OCR_ENGINE_ENABLED
- OCR_LANGUAGES
- OCR_FORCE_PDF
- OCR_MAX_PDF_PAGES
- OCR_MIN_PDF_CHARS

O comportamento esperado e:

- PDFs com texto suficiente seguem pelo parser nativo
- PDFs com pouco texto podem disparar OCR
- imagens entram diretamente no motor OCR

## Sanitizacao

O projeto aplica sanitizacao em dois momentos diferentes.

### Sanitizacao antes da analise

O plain text e normalizado antes de:

- chunking
- extracao de entidades
- indexacao semantica

Isso reduz ruido estrutural como:

- caracteres de controle
- linhas vazias excessivas
- espacos redundantes
- quebras de linha inconsistentes

### Sanitizacao antes da renderizacao rich text

O rich text e tratado para reduzir superficie insegura de HTML.

No backend:

- remove tags nao permitidas
- remove atributos de evento
- remove protocolos inseguros
- reforca atributos seguros em links

No frontend:

- aplica uma segunda camada defensiva antes de usar innerHTML

## Busca semantica

O indice semantico trabalha sobre chunks.

Fluxo:

1. o documento vira chunks
2. cada chunk recebe embedding
3. os embeddings entram em um indice vetorial
4. a consulta recebe embedding
5. o sistema retorna os trechos mais proximos

Backends atuais:

- FAISS quando disponivel
- fallback brute-force com numpy quando FAISS nao estiver presente

O objetivo aqui nao e sofisticacao maxima.
E degradacao controlada.

## Grafo de conhecimento

O grafo atual modela dois tipos de nos:

- documentos
- entidades

E duas relacoes principais:

- contains
- co_occurs

Isso permite:

- listar documentos e entidades
- inspecionar conexoes simples
- visualizar relacoes sem pipeline pesado adicional

## Viewer

O viewer existe para leitura e verificacao rapida.

Modos:

- Plain: texto normalizado
- Rich: renderizacao sanitizada quando a fonte permitir

Uso esperado:

- verificar rapidamente um documento indexado
- validar OCR
- validar conteudo markdown/html sem exportar arquivo

## Gutenberg

O prospector Gutenberg e uma fonte nativa auxiliar.

Ele executa tres papeis:

1. buscar livros no catalogo remoto
2. baixar texto localmente
3. indexar o conteudo no fluxo padrao do sistema

Dependencia externa:

- internet apenas para consulta e download do Gutenberg

Depois disso, o conteudo segue local.

## Persistencia

O projeto grava estado local para manter continuidade operacional.

Diretorios principais:

- data/uploads
- data/index
- data/gutenberg/books

Persistencias principais:

- arquivos enviados
- indice vetorial
- metadados de chunks
- grafo
- cache do catalogo Gutenberg

## Modos de execucao

### Execucao direta

Uso adequado para desenvolvimento e depuracao local.

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### One-click

Uso adequado para reduzir atrito operacional em ambiente de edicao.

Opcoes disponiveis:

- task do VS Code
- launch config do VS Code
- launcher Python

### Container

Uso adequado para padronizar runtime e isolamento.

O container atual ja inclui:

- Python runtime
- dependencias Python
- tesseract-ocr
- idiomas por e eng
- poppler-utils

## Perfil operacional desejado

O projeto foi desenhado para:

- operar localmente por padrao
- degradar de forma controlada
- reduzir dependencia externa
- evitar fluxo excessivamente magico
- manter comportamento compreensivel

Em termos praticos, baixo ruido significa:

- poucas surpresas na execucao
- falhas mais localizaveis
- dados locais em caminhos previsiveis
- sanitizacao explicita
- runtime empacotavel

## Limites atuais

O projeto ainda nao pretende ser:

- um orchestrator distribuido
- uma plataforma multiusuario completa
- um pipeline de NER de alta especializacao
- um sistema de observabilidade avancada

A proposta atual e menor e mais utilitaria.

## Proximos passos coerentes

Se a direcao continuar sendo baixo ruido, os proximos incrementos naturais sao:

1. healthcheck mais detalhado
2. diagnostico de OCR e modelo semantico
3. reindexacao controlada
4. logs mais padronizados
5. trilha de estado por documento

## Resumo

Alexandria-AI e um motor local de ingestao, OCR, busca e leitura.

A arquitetura atual favorece:

- simplicidade suficiente
- operacao previsivel
- seguranca basica explicita
- autonomia local

Essa e a intencao central do projeto.
