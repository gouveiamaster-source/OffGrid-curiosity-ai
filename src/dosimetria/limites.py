"""
Limites regulatórios de dose — CNEN NE 3.01 / IAEA BSS / ICRP 103.

Fornece:
  - Tabela de limites por categoria (trabalhador, público, etc.)
  - Função de verificação de conformidade

Branch de destino: feature/dosimetria-calculo
"""

from __future__ import annotations

from .modelos import LimitesDose

# ──────────────────────────────────────────────────────────────────────────────
# Tabela de limites regulatórios (CNEN NE 3.01 — Resolução CNEN 164/2014)
# ──────────────────────────────────────────────────────────────────────────────

LIMITES_REGULATORIOS: dict[str, LimitesDose] = {
    "trabalhador_ocupacional": LimitesDose(
        categoria="trabalhador_ocupacional",
        limite_anual_mSv=20.0,
        limite_efetivo_5anos_mSv=100.0,
        limite_extremidades_mSv=500.0,
        referencia="CNEN NE 3.01 / IAEA BSS GSR Part 3",
    ),
    "aprendiz_estudante": LimitesDose(
        categoria="aprendiz_estudante",
        limite_anual_mSv=6.0,
        limite_efetivo_5anos_mSv=30.0,
        limite_extremidades_mSv=150.0,
        referencia="CNEN NE 3.01 / IAEA BSS GSR Part 3",
    ),
    "publico_geral": LimitesDose(
        categoria="publico_geral",
        limite_anual_mSv=1.0,
        limite_efetivo_5anos_mSv=5.0,
        limite_extremidades_mSv=50.0,
        referencia="CNEN NE 3.01 / IAEA BSS GSR Part 3",
    ),
    "gestante_trabalhadora": LimitesDose(
        categoria="gestante_trabalhadora",
        # O limite de 1 mSv refere-se à dose efetiva ao feto durante toda a gestação
        # conforme CNEN NE 3.01 seção 3.2.3.
        limite_anual_mSv=1.0,
        limite_efetivo_5anos_mSv=1.0,
        limite_extremidades_mSv=50.0,
        referencia="CNEN NE 3.01",
    ),
}


def verificar_conformidade(dose_mSv: float, categoria: str) -> dict:
    """
    Verifica se a dose está dentro dos limites regulatórios para a categoria.

    Retorna dict com:
      - conforme: bool
      - margem_mSv: float  (positivo = abaixo do limite; negativo = excedido)
      - percentual_limite: float
      - limite_aplicado: LimitesDose
    """
    limite = LIMITES_REGULATORIOS.get(categoria)
    if limite is None:
        raise ValueError(
            f"Categoria '{categoria}' desconhecida. "
            f"Opções: {list(LIMITES_REGULATORIOS.keys())}"
        )

    conforme = dose_mSv <= limite.limite_anual_mSv
    margem = limite.limite_anual_mSv - dose_mSv
    percentual = (dose_mSv / limite.limite_anual_mSv) * 100.0

    return {
        "conforme": conforme,
        "dose_recebida_mSv": dose_mSv,
        "limite_anual_mSv": limite.limite_anual_mSv,
        "margem_mSv": margem,
        "percentual_limite": round(percentual, 2),
        "categoria": categoria,
        "referencia": limite.referencia,
    }
