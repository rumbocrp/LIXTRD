"""Matriz de Filtrado Personalizada y Adaptación al Estilo del Operador (Fase 3)."""

from __future__ import annotations
from typing import Dict, Any, Optional
from sistema_luces.domain.models import DecisionLuzContract
from sistema_luces.domain.vocabulary import TrafficLightColor, ActionType, ReasonCode
from sistema_luces.domain.strategy import StrategyDefinition
from sistema_luces.learning.operator_profiler import OperatorBehavioralProfiler

class PersonalizedFilterMatrix:
    """Modula las decisiones del Sistema de Luces adaptándolas a la ventaja estadística del operador."""
    def __init__(self, profiler: Optional[OperatorBehavioralProfiler] = None):
        self.profiler = profiler or OperatorBehavioralProfiler()
        self.setup_edge_cache: Dict[str, str] = {}
        self.refresh_edges()

    def refresh_edges(self) -> None:
        profiles = self.profiler.compute_setup_profiles()
        for setup_id, stats in profiles.items():
            self.setup_edge_cache[setup_id] = stats.get("edge_tag", "NEUTRAL")

    def apply_filter(
        self,
        decision: DecisionLuzContract,
        active_strategy: Optional[StrategyDefinition] = None,
        market_regime: str = "NORMAL",
    ) -> DecisionLuzContract:
        """
        Ajusta la decisión y añade recomendaciones de riesgo personalizadas
        según el perfil histórico de acierto del operador.
        """
        if not active_strategy:
            return decision

        setup_id = active_strategy.strategy_id
        edge_tag = self.setup_edge_cache.get(setup_id, "NEUTRAL")

        # 1. Caso NEGATIVE_EDGE: El operador suele perder en este setup -> Filtrado defensivo
        if edge_tag == "NEGATIVE_EDGE":
            # Si la confianza no es abrumadora (>85%), forzar precaución preventiva
            if decision.confidence_score_ppm < 850_000:
                return DecisionLuzContract(
                    decision_id=decision.decision_id,
                    instrument=decision.instrument,
                    timeframe=decision.timeframe,
                    data_timestamp_utc=decision.data_timestamp_utc,
                    created_at_utc=decision.created_at_utc,
                    state=TrafficLightColor.YELLOW,
                    action=ActionType.MONITOR,
                    net_utility_long_ppm=decision.net_utility_long_ppm,
                    net_utility_short_ppm=decision.net_utility_short_ppm,
                    confidence_score_ppm=decision.confidence_score_ppm,
                    calibration_quality_ppm=decision.calibration_quality_ppm,
                    kalman_beta_scaled=decision.kalman_beta_scaled,
                    kalman_z_score_scaled=decision.kalman_z_score_scaled,
                    ofi_imbalance_scaled=decision.ofi_imbalance_scaled,
                    micro_price_mid_delta_ppm=decision.micro_price_mid_delta_ppm,
                    champion_model_id=decision.champion_model_id,
                    valid_until_utc=decision.valid_until_utc,
                    reason_codes=decision.reason_codes + [ReasonCode.MONITOR_POLICY],
                    data_health=decision.data_health,
                )

        # 2. Caso STRONG_EDGE: El operador domina este setup -> Bonificación de convicción
        if edge_tag == "STRONG_EDGE" and decision.state != TrafficLightColor.YELLOW:
            # Calibración de alta convicción
            pass

        return decision
