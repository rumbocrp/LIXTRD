"""Puerta de Aprobación Criptográfica y Validación Campeón / Retador (Fase 6).
Implementa:
- Requisito de muestra mínima de 10,000 ticks en modo sombra (Shadow Run).
- Prueba estadística de Diebold-Mariano (p < 0.01) para validar superioridad sobre el campeón vigente.
- Aprobación criptográfica obligatoria del operador (Firma HMAC/Ed25519) antes de promover pesos a producción.
"""

from __future__ import annotations
import hmac
import hashlib
import math
import numpy as np
from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass

@dataclass(frozen=True)
class PromotionEvaluationResult:
    challenger_model_id: str
    champion_model_id: str
    shadow_ticks_collected: int
    min_ticks_required: int
    challenger_brier_score: float
    champion_brier_score: float
    dm_statistic: float
    p_value: float
    is_statistically_superior: bool
    is_ready_for_promotion: bool
    rejection_reason: Optional[str] = None

class ChampionChallengerGate:
    """Controla la evaluación en sombra y la promoción de modelos de ML bajo supervisión criptográfica."""
    def __init__(
        self,
        min_shadow_ticks: int = 10_000,
        significance_level: float = 0.01,
        operator_secret_key: str = "operator-master-ed25519-key-luces-v2",
    ):
        self.min_shadow_ticks = min_shadow_ticks
        self.alpha_p = significance_level
        self.operator_key = operator_secret_key.encode("utf-8")
        
        # Historial de errores cuadráticos de predicción en sombra
        self.champion_errors: List[float] = []
        self.challenger_errors: List[float] = []

    def record_shadow_tick(self, champion_pred: float, challenger_pred: float, actual_outcome: float) -> None:
        """Registra el error cuadrático en sombra de ambos modelos."""
        e_champ = (champion_pred - actual_outcome) ** 2
        e_chall = (challenger_pred - actual_outcome) ** 2
        self.champion_errors.append(e_champ)
        self.challenger_errors.append(e_chall)

    def evaluate_promotion(self, champion_id: str, challenger_id: str) -> PromotionEvaluationResult:
        n_ticks = len(self.challenger_errors)
        if n_ticks == 0:
            return PromotionEvaluationResult(
                challenger_model_id=challenger_id,
                champion_model_id=champion_id,
                shadow_ticks_collected=0,
                min_ticks_required=self.min_shadow_ticks,
                challenger_brier_score=1.0,
                champion_brier_score=1.0,
                dm_statistic=0.0,
                p_value=1.0,
                is_statistically_superior=False,
                is_ready_for_promotion=False,
                rejection_reason="Cero ticks registrados en sombra",
            )

        mean_champ_bs = float(np.mean(self.champion_errors))
        mean_chall_bs = float(np.mean(self.challenger_errors))

        # 1. Comprobación de muestra mínima
        if n_ticks < self.min_shadow_ticks:
            return PromotionEvaluationResult(
                challenger_model_id=challenger_id,
                champion_model_id=champion_id,
                shadow_ticks_collected=n_ticks,
                min_ticks_required=self.min_shadow_ticks,
                challenger_brier_score=round(mean_chall_bs, 4),
                champion_brier_score=round(mean_champ_bs, 4),
                dm_statistic=0.0,
                p_value=1.0,
                is_statistically_superior=False,
                is_ready_for_promotion=False,
                rejection_reason=f"Muestra insuficiente ({n_ticks}/{self.min_shadow_ticks} ticks)",
            )

        # 2. Prueba estadística de Diebold-Mariano (1995)
        # d_t = e_{champ, t} - e_{chall, t}
        d = np.array(self.champion_errors) - np.array(self.challenger_errors)
        d_mean = float(np.mean(d))
        d_var = float(np.var(d, ddof=1)) if n_ticks > 1 else 0.0
        
        if d_var < 1e-9:
            if d_mean > 0:
                dm_stat = 99.0
                p_val = 0.0
            else:
                dm_stat = 0.0
                p_val = 1.0
        else:
            dm_stat = float(d_mean / math.sqrt(d_var / n_ticks))
            # CDF normal de una cola
            p_val = float(0.5 * (1.0 - math.erf(dm_stat / math.sqrt(2.0))))

        is_superior = (dm_stat > 0) and (p_val < self.alpha_p)
        ready = is_superior and (mean_chall_bs < 0.165)

        reason = None if ready else ("El modelo retador no supera estadísticamente al campeón (p >= 0.01)" if not is_superior else "Brier Score superior a 0.165")

        return PromotionEvaluationResult(
            challenger_model_id=challenger_id,
            champion_model_id=champion_id,
            shadow_ticks_collected=n_ticks,
            min_ticks_required=self.min_shadow_ticks,
            challenger_brier_score=round(mean_chall_bs, 4),
            champion_brier_score=round(mean_champ_bs, 4),
            dm_statistic=round(dm_stat, 3),
            p_value=round(p_val, 5),
            is_statistically_superior=is_superior,
            is_ready_for_promotion=ready,
            rejection_reason=reason,
        )

    def verify_operator_authorization_signature(
        self,
        challenger_model_id: str,
        timestamp_utc: int,
        signature_hex: str,
    ) -> bool:
        """Verifica criptográficamente la autorización del operador."""
        message = f"PROMOTE_MODEL:{challenger_model_id}:{timestamp_utc}".encode("utf-8")
        expected_sig = hmac.new(self.operator_key, message, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected_sig, signature_hex)

    def generate_authorization_signature(self, challenger_model_id: str, timestamp_utc: int) -> str:
        """Genera la firma de autorización criptográfica con la clave del operador."""
        message = f"PROMOTE_MODEL:{challenger_model_id}:{timestamp_utc}".encode("utf-8")
        return hmac.new(self.operator_key, message, hashlib.sha256).hexdigest()
