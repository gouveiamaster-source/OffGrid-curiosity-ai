"""
Rotas FastAPI para a ferramentaria de dosimetria.

Endpoints:
  POST /dosimetria/calcular       — cálculo dosimétrico pontual
  GET  /dosimetria/limites        — tabela de limites regulatórios
  POST /dosimetria/conformidade   — verifica conformidade de uma dose

Branch de destino: feature/dosimetria-integracao
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.dosimetria.calculo import MotorDosimetria
from src.dosimetria.limites import LIMITES_REGULATORIOS, verificar_conformidade
from src.dosimetria.modelos import ConfiguracaoCalculo, LimitesDose, ResultadoDose

router = APIRouter(prefix="/dosimetria", tags=["Dosimetria"])

_motor = MotorDosimetria()


# ──────────────────────────────────────────────────────────────────────────────
# Schemas de request auxiliares
# ──────────────────────────────────────────────────────────────────────────────

class ConformidadeRequest(BaseModel):
    dose_mSv: float = Field(..., ge=0, description="Dose recebida em mSv")
    categoria: str = Field(
        ...,
        description="Categoria do indivíduo (trabalhador_ocupacional, publico_geral, etc.)",
    )


# ──────────────────────────────────────────────────────────────────────────────
# Endpoints
# ──────────────────────────────────────────────────────────────────────────────

@router.post("/calcular", response_model=ResultadoDose, summary="Cálculo dosimétrico pontual")
async def calcular_dose(config: ConfiguracaoCalculo) -> ResultadoDose:
    """
    Executa cálculo dosimétrico com base na configuração fornecida.

    Aplica:
    - Lei do inverso do quadrado da distância
    - Atenuação exponencial (se coeficiente de atenuação disponível)
    - Fator de ponderação de radiação (wR) conforme ICRP 103
    """
    try:
        return _motor.calcular(config)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get(
    "/limites",
    response_model=dict[str, LimitesDose],
    summary="Tabela de limites regulatórios",
)
async def listar_limites() -> dict[str, LimitesDose]:
    """Retorna a tabela completa de limites regulatórios de dose (CNEN NE 3.01 / IAEA BSS)."""
    return LIMITES_REGULATORIOS


@router.post("/conformidade", summary="Verificar conformidade de dose")
async def verificar_dose(req: ConformidadeRequest) -> dict:
    """
    Verifica se uma dose recebida está dentro dos limites regulatórios
    para a categoria informada.
    """
    try:
        return verificar_conformidade(req.dose_mSv, req.categoria)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
