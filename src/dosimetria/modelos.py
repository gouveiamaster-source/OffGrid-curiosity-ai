"""
Modelos de dados para ferramentaria de dosimetria.

Define as estruturas Pydantic e dataclasses utilizadas pelos módulos de
cálculo e API de dosimetria do Alexandria-AI.

Branch de destino: feature/dosimetria-modelos
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ──────────────────────────────────────────────────────────────────────────────
# Enums
# ──────────────────────────────────────────────────────────────────────────────

class TipoRadiacao(str, Enum):
    """Tipos de radiação ionizante suportados."""
    ALFA = "alfa"
    BETA = "beta"
    GAMA = "gama"
    NEUTRONS = "neutrons"
    RAIO_X = "raio_x"
    PROTONS = "protons"


class UnidadeDose(str, Enum):
    """Unidades de dose de radiação."""
    GY = "Gy"        # Gray (dose absorvida)
    MGY = "mGy"      # milliGray
    CGY = "cGy"      # centigray
    SV = "Sv"        # Sievert (dose equivalente)
    MSV = "mSv"      # millisievert
    REM = "rem"      # Roentgen Equivalent Man (unidade antiga)
    RAD = "rad"      # Radiation Absorbed Dose (unidade antiga)


# ──────────────────────────────────────────────────────────────────────────────
# Modelos de entrada
# ──────────────────────────────────────────────────────────────────────────────

class Material(BaseModel):
    """Material de atenuação ou meio absorvedor."""
    nome: str = Field(..., description="Nome do material (ex: água, tecido, chumbo)")
    densidade: float = Field(..., gt=0, description="Densidade em g/cm³")
    numero_atomico_efetivo: Optional[float] = Field(
        None, ge=1, description="Número atômico efetivo (Z_ef)"
    )
    coeficiente_atenuacao: Optional[float] = Field(
        None, ge=0, description="Coeficiente de atenuação linear (cm⁻¹)"
    )


class FonteRadiacao(BaseModel):
    """Fonte de radiação para cálculo de dose."""
    tipo: TipoRadiacao
    energia_MeV: float = Field(..., gt=0, description="Energia em MeV")
    atividade_Bq: Optional[float] = Field(
        None, ge=0, description="Atividade da fonte em Becquerel"
    )
    taxa_kerma_ar: Optional[float] = Field(
        None, ge=0, description="Taxa de kerma no ar em Gy/s"
    )


class ConfiguracaoCalculo(BaseModel):
    """Configuração para cálculo dosimétrico."""
    fonte: FonteRadiacao
    material: Material
    distancia_cm: float = Field(..., gt=0, description="Distância fonte-detector em cm")
    tempo_exposicao_s: float = Field(default=1.0, gt=0, description="Tempo de exposição em segundos")
    unidade_saida: UnidadeDose = Field(default=UnidadeDose.MSV, description="Unidade da dose de saída")


# ──────────────────────────────────────────────────────────────────────────────
# Modelos de saída
# ──────────────────────────────────────────────────────────────────────────────

class ResultadoDose(BaseModel):
    """Resultado de cálculo dosimétrico."""
    dose: float = Field(..., description="Valor da dose calculada")
    unidade: UnidadeDose
    dose_equivalente_mSv: float = Field(..., description="Dose equivalente em mSv")
    incerteza_percentual: Optional[float] = Field(
        None, ge=0, description="Incerteza do cálculo em %"
    )
    metodo_calculo: str = Field(..., description="Método utilizado no cálculo")
    detalhes: dict = Field(default_factory=dict, description="Parâmetros intermediários")


class LimitesDose(BaseModel):
    """Limites regulatórios de dose por categoria de trabalhador/público."""
    categoria: str = Field(..., description="Categoria (trabalhador_ocupacional, publico_geral, etc.)")
    limite_anual_mSv: float = Field(..., description="Limite anual em mSv")
    limite_efetivo_5anos_mSv: float = Field(..., description="Limite efetivo em 5 anos em mSv")
    limite_extremidades_mSv: float = Field(..., description="Limite para extremidades em mSv")
    referencia: str = Field(default="CNEN NE 3.01 / IAEA BSS", description="Norma de referência")
