"""Tesorería de Evidencia y Presupuesto de Riesgo del Operador (Fase 6).
Implementa:
- Presupuesto de riesgo diario (límite de pérdida del 2.0% de equity).
- Fichas de evidencia para prevenir sobreajuste (Bucle L3) en barridos de hiperparámetros.
- Monitor continuo de degradación de Brier Score (umbral de alarma BS > 0.165).
- Degradación automática a AMARILLO / STANDBY si se agota el presupuesto diario.
"""

from __future__ import annotations
import time
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

@dataclass
class TreasuryStatus:
    daily_loss_budget_usd: float
    current_daily_loss_usd: float
    remaining_budget_usd: float
    is_risk_budget_exhausted: bool
    evidence_tokens_remaining: int
    rolling_brier_score: float
    is_brier_score_degraded: bool
    should_force_yellow_standby: bool

class EvidenceTreasury:
    """Administra los límites diarios de riesgo, tokens de evidencia y salud probabilística."""
    def __init__(
        self,
        daily_loss_budget_usd: float = 200.0, # 2.0% sobre cuenta de $10,000
        max_daily_evidence_tokens: int = 50,
        brier_alarm_threshold: float = 0.165,
    ):
        self.daily_loss_budget_usd = daily_loss_budget_usd
        self.evidence_tokens = max_daily_evidence_tokens
        self.brier_threshold = brier_alarm_threshold
        
        self.current_realized_loss_usd = 0.0
        self.brier_history: List[float] = []

    def record_pnl(self, pnl_usd: float) -> float:
        """Registra el PnL de un trade cerrado y descuenta del presupuesto diario si es pérdida."""
        if pnl_usd < 0:
            self.current_realized_loss_usd += abs(pnl_usd)
        return self.current_realized_loss_usd

    def record_prediction_outcome(self, predicted_prob: float, actual_win: bool) -> float:
        """Calcula el Brier Score instantáneo: BS = (p - y)^2."""
        y = 1.0 if actual_win else 0.0
        bs = (predicted_prob - y) ** 2
        self.brier_history.append(bs)
        if len(self.brier_history) > 100:
            self.brier_history.pop(0)
        return bs

    def consume_evidence_token(self) -> bool:
        """Descuenta una ficha de evidencia para un barrido de optimización."""
        if self.evidence_tokens > 0:
            self.evidence_tokens -= 1
            return True
        return False

    def get_status(self) -> TreasuryStatus:
        remaining = max(0.0, self.daily_loss_budget_usd - self.current_realized_loss_usd)
        is_exhausted = remaining <= 0.0
        
        mean_bs = (sum(self.brier_history) / len(self.brier_history)) if self.brier_history else 0.10
        is_degraded = mean_bs > self.brier_threshold
        
        force_standby = is_exhausted or is_degraded

        return TreasuryStatus(
            daily_loss_budget_usd=self.daily_loss_budget_usd,
            current_daily_loss_usd=round(self.current_realized_loss_usd, 2),
            remaining_budget_usd=round(remaining, 2),
            is_risk_budget_exhausted=is_exhausted,
            evidence_tokens_remaining=self.evidence_tokens,
            rolling_brier_score=round(mean_bs, 4),
            is_brier_score_degraded=is_degraded,
            should_force_yellow_standby=force_standby,
        )
