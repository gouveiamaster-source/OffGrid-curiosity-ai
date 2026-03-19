"""
Motor de cálculo dosimétrico — off-grid, sem dependências externas.

Implementa:
  - Lei do inverso do quadrado da distância
  - Atenuação exponencial (Lei de Beer-Lambert)
  - Conversão entre unidades de dose (Gy ↔ Sv ↔ mSv ↔ rem ↔ rad)
  - Fatores de ponderação de radiação (wR) conforme ICRP 103

Branch de destino: feature/dosimetria-calculo
"""

from __future__ import annotations

import math
from typing import Optional

from .modelos import (
    ConfiguracaoCalculo,
    FonteRadiacao,
    Material,
    ResultadoDose,
    TipoRadiacao,
    UnidadeDose,
)


# ──────────────────────────────────────────────────────────────────────────────
# Fatores de ponderação de radiação wR (ICRP 103, Tabela A.1)
# ──────────────────────────────────────────────────────────────────────────────

_FATOR_PONDERACAO_RADIACAO: dict[TipoRadiacao, float] = {
    TipoRadiacao.RAIO_X: 1.0,
    TipoRadiacao.GAMA:   1.0,
    TipoRadiacao.BETA:   1.0,
    TipoRadiacao.ALFA:   20.0,
    TipoRadiacao.PROTONS: 2.0,
    TipoRadiacao.NEUTRONS: 10.0,   # valor médio conservador (varia com a energia)
}


# ──────────────────────────────────────────────────────────────────────────────
# Conversão de unidades
# ──────────────────────────────────────────────────────────────────────────────

_PARA_MSV: dict[UnidadeDose, float] = {
    UnidadeDose.SV:  1_000.0,
    UnidadeDose.MSV: 1.0,
    UnidadeDose.GY:  1_000.0,   # pressupõe wR = 1 (fótons/elétrons)
    UnidadeDose.MGY: 1.0,
    UnidadeDose.CGY: 10.0,
    UnidadeDose.REM: 10.0,      # 1 rem = 10 mSv
    UnidadeDose.RAD: 10.0,      # 1 rad = 10 mGy ≈ 10 mSv (wR=1)
}

_DE_MSV: dict[UnidadeDose, float] = {u: 1.0 / f for u, f in _PARA_MSV.items()}

# Distância de referência usada na lei do inverso do quadrado (1 cm = ponto fonte)
_DISTANCIA_REFERENCIA_CM = 1.0


def converter_dose(valor: float, de: UnidadeDose, para: UnidadeDose) -> float:
    """Converte um valor de dose entre unidades."""
    em_msv = valor * _PARA_MSV[de]
    return em_msv * _DE_MSV[para]


# ──────────────────────────────────────────────────────────────────────────────
# Cálculos físicos
# ──────────────────────────────────────────────────────────────────────────────

def inverso_quadrado(taxa_referencia: float, distancia_ref_cm: float, distancia_cm: float) -> float:
    """
    Aplica a lei do inverso do quadrado da distância.

    taxa(d) = taxa_ref × (d_ref / d)²
    """
    if distancia_cm <= 0:
        raise ValueError("Distância deve ser positiva.")
    return taxa_referencia * (distancia_ref_cm / distancia_cm) ** 2


def atenuacao_exponencial(
    taxa_entrada: float,
    coeficiente_atenuacao_cm: float,
    espessura_cm: float,
) -> float:
    """
    Aplica a lei de Beer-Lambert para atenuação em meio homogêneo.

    I(x) = I₀ × exp(−μx)
    """
    return taxa_entrada * math.exp(-coeficiente_atenuacao_cm * espessura_cm)


def dose_absorvida_Gy(
    taxa_kerma_ar_Gy_s: float,
    tempo_s: float,
    fator_f: float = 1.0,
) -> float:
    """
    Calcula a dose absorvida em Gray.

    D = K_ar × t × f
    onde f é o fator de conversão kerma-no-ar → dose-absorvida (tipicamente ~1).
    """
    return taxa_kerma_ar_Gy_s * tempo_s * fator_f


def dose_equivalente_mSv(dose_absorvida_mGy: float, tipo_radiacao: TipoRadiacao) -> float:
    """
    Converte dose absorvida (mGy) em dose equivalente (mSv).

    H = D × wR
    """
    wr = _FATOR_PONDERACAO_RADIACAO.get(tipo_radiacao, 1.0)
    return dose_absorvida_mGy * wr


# ──────────────────────────────────────────────────────────────────────────────
# Motor de cálculo principal
# ──────────────────────────────────────────────────────────────────────────────

class MotorDosimetria:
    """
    Motor de cálculo dosimétrico off-grid.

    Uso:
        motor = MotorDosimetria()
        resultado = motor.calcular(configuracao)
    """

    def calcular(self, config: ConfiguracaoCalculo) -> ResultadoDose:
        """Executa o cálculo dosimétrico completo para a configuração fornecida."""
        fonte = config.fonte
        material = config.material
        distancia = config.distancia_cm
        tempo = config.tempo_exposicao_s

        detalhes: dict = {
            "tipo_radiacao": fonte.tipo.value,
            "energia_MeV": fonte.energia_MeV,
            "distancia_cm": distancia,
            "tempo_s": tempo,
            "material": material.nome,
            "densidade_g_cm3": material.densidade,
        }

        # Taxa kerma ou conversão a partir de atividade
        if fonte.taxa_kerma_ar is not None:
            taxa = fonte.taxa_kerma_ar  # Gy/s já fornecida
            metodo = "taxa_kerma_ar_direto"
        else:
            # Sem taxa kerma fornecida: não é possível calcular sem dados adicionais
            raise ValueError(
                "Forneça taxa_kerma_ar na FonteRadiacao para calcular a dose. "
                "Cálculo a partir de atividade será implementado em versão futura."
            )

        # Aplica lei do inverso do quadrado (referência a 1 cm)
        taxa_distancia = inverso_quadrado(taxa, _DISTANCIA_REFERENCIA_CM, distancia)
        detalhes["taxa_kerma_a_distancia_Gy_s"] = taxa_distancia

        # Aplica atenuação no material se coeficiente disponível
        if material.coeficiente_atenuacao is not None:
            taxa_atenuada = atenuacao_exponencial(
                taxa_distancia,
                material.coeficiente_atenuacao,
                distancia,
            )
            detalhes["taxa_apos_atenuacao_Gy_s"] = taxa_atenuada
            metodo = "inverso_quadrado+atenuacao_exponencial"
        else:
            taxa_atenuada = taxa_distancia

        # Dose absorvida em mGy
        dose_mGy = dose_absorvida_Gy(taxa_atenuada, tempo) * 1_000.0
        detalhes["dose_absorvida_mGy"] = dose_mGy

        # Dose equivalente em mSv
        dose_mSv = dose_equivalente_mSv(dose_mGy, fonte.tipo)
        detalhes["fator_ponderacao_wR"] = _FATOR_PONDERACAO_RADIACAO.get(fonte.tipo, 1.0)

        # Converte para unidade solicitada
        dose_saida = converter_dose(dose_mSv, UnidadeDose.MSV, config.unidade_saida)

        return ResultadoDose(
            dose=dose_saida,
            unidade=config.unidade_saida,
            dose_equivalente_mSv=dose_mSv,
            metodo_calculo=metodo,
            detalhes=detalhes,
        )
