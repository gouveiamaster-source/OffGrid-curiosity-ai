# Branches de Dosimetria — Alexandria-AI

Este documento descreve a estrutura de branches criadas para o desenvolvimento
futuro da ferramentaria de dosimetria integrada ao Alexandria-AI.

## Branches planejadas

| Branch | Propósito |
|---|---|
| `feature/dosimetria-modelos` | Modelos Pydantic, enums de unidades e tipos de radiação |
| `feature/dosimetria-calculo` | Motor de cálculo, fatores wR, conversão de unidades, limites CNEN |
| `feature/dosimetria-integracao` | Rotas FastAPI, integração com busca semântica e grafo |
| `feature/dosimetria-interface` | Aba "☢️ Dosimetria" no frontend, calculadora interativa |

## Criar os branches localmente

Após clonar o repositório (ou `git fetch`), execute:

```bash
# A partir do main (base estável)
git fetch origin

git checkout -b feature/dosimetria-modelos origin/main
git push -u origin feature/dosimetria-modelos

git checkout -b feature/dosimetria-calculo feature/dosimetria-modelos
git push -u origin feature/dosimetria-calculo

git checkout -b feature/dosimetria-integracao feature/dosimetria-calculo
git push -u origin feature/dosimetria-integracao

git checkout -b feature/dosimetria-interface feature/dosimetria-integracao
git push -u origin feature/dosimetria-interface
```

## Estrutura de arquivos já disponível neste branch

```
src/dosimetria/
├── __init__.py           ← pacote dosimetria
├── modelos.py            ← schemas Pydantic (Material, FonteRadiacao, ResultadoDose…)
├── calculo.py            ← MotorDosimetria (inverso do quadrado, atenuação, wR)
├── limites.py            ← tabela CNEN NE 3.01 / IAEA BSS + verificar_conformidade()
└── rotas.py              ← APIRouter FastAPI (/dosimetria/calcular, /limites, /conformidade)
```

## Ordem de integração sugerida

```
main
 └─ feature/dosimetria-modelos       (1º — base de dados)
     └─ feature/dosimetria-calculo   (2º — motor de cálculo)
         └─ feature/dosimetria-integracao   (3º — API + grafo)
             └─ feature/dosimetria-interface  (4º — UI)
```

## Como registrar o router na API principal

Em `main.py`, adicione após os outros imports e antes da definição dos endpoints:

```python
from src.dosimetria.rotas import router as dosimetria_router

# ...
app.include_router(dosimetria_router)
```

## Endpoints disponíveis após integração

| Método | Rota | Descrição |
|---|---|---|
| `POST` | `/dosimetria/calcular` | Cálculo dosimétrico pontual |
| `GET` | `/dosimetria/limites` | Tabela de limites regulatórios |
| `POST` | `/dosimetria/conformidade` | Verifica conformidade de uma dose |

## Referências normativas

- **CNEN NE 3.01** — Diretrizes Básicas de Proteção Radiológica (Brasil)
- **IAEA BSS GSR Part 3** — Radiation Protection and Safety of Radiation Sources
- **ICRP Publication 103** — The 2007 Recommendations of the ICRP
- **ICRU Report 85** — Fundamental Quantities and Units for Ionizing Radiation
