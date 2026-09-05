"""Motor Cuantitativo Compuesto con Confluencia Bayesiana Dinámica y Control Humano (Fase 2-6)."""

import math
from typing import Dict, Any, Tuple, Optional
from sistema_luces.domain.models import QuantFeatures, DecisionLuzContract
from sistema_luces.domain.vocabulary import TrafficLightColor, ActionType, HealthState
from sistema_luces.domain.state_machine import DecisionStateMachine
from sistema_luces.domain.human_control import HumanControlDials
from sistema_luces.quant.kalman import DynamicKalmanFilter
from sistema_luces.quant.order_flow import MultiLevelOrderFlowEngine, StoikovMicroPriceEngine
from sistema_luces.quant.correlation import EWMACorrelationEngine
from sistema_luces.quant.bayesian_gate import BayesianConfluenceGate

class QuantitativeDecisionEngine:
    """Motor cuantitativo central que fusiona Cointegración, Microestructura L2 y Confluencia Bayesiana."""
    def __init__(
        self,
        instrument: str = "XAUUSD",
        champion_model_id: str = "model-kalman-ofi-bayesian-v2.0",
        dials: Optional[HumanControlDials] = None,
    ):
        self.instrument = instrument
        self.champion_model_id = champion_model_id
        self.dials = dials or HumanControlDials()
        self.kalman = DynamicKalmanFilter(delta=1e-4, R_0=1e-2)
        self.order_flow = MultiLevelOrderFlowEngine(num_levels=5, kappa=0.65)
        self.correlation = EWMACorrelationEngine(decay_lambda=0.96)
        self.bayesian_gate = BayesianConfluenceGate(
            z_critical=self.dials.z_critical,
            ofi_critical=self.dials.ofi_critical,
        )
        self.state_machine = DecisionStateMachine(dials=self.dials)
        self.last_decision: Optional[DecisionLuzContract] = None

    def process_tick(
        self,
        bid_p: float,
        bid_v: float,
        ask_p: float,
        ask_v: float,
        cross_asset_price: float,
        source_ts: int,
        health: HealthState = HealthState.HEALTHY,
        bids_depth: Optional[list] = None,
        asks_depth: Optional[list] = None,
    ) -> DecisionLuzContract:
        # 1. Procesar Microestructura y OFI Multi-Nivel
        bids_l = bids_depth if bids_depth else [(bid_p, bid_v)]
        asks_l = asks_depth if asks_depth else [(ask_p, ask_v)]
        ofi, mid_p, micro_p, vpin = self.order_flow.compute(bids_l, asks_l)
        spread = max(1e-4, ask_p - bid_p)

        # 2. Procesar Filtro de Kalman sobre par cointegrado
        alpha, beta, z_score = self.kalman.update(mid_p, cross_asset_price)

        # 3. Procesar Correlación Dinámica EWMA (lambda = 0.96)
        corr = self.correlation.update(mid_p, cross_asset_price)

        # 4. Construir Vector de Características Cuantitativas
        features = QuantFeatures(
            kalman_beta=beta,
            kalman_alpha=alpha,
            spread_z_score=z_score,
            order_flow_imbalance=ofi,
            mid_price=mid_p,
            micro_price=micro_p,
            cross_asset_correlation=corr,
            vpin_toxicity=vpin,
            spread_pips=spread,
        )

        # 5. Evaluación de Confluencia Bayesiana
        prob_long, odds_long, _ = self.bayesian_gate.evaluate_confluence(features, direction="LONG")
        prob_short, odds_short, _ = self.bayesian_gate.evaluate_confluence(features, direction="SHORT")

        # Score compuesto direccional [-1.0, +1.0]
        if prob_long >= prob_short:
            composite_score = (prob_long - 0.50) * 2.0
            dominant_prob = prob_long
        else:
            composite_score = -(prob_short - 0.50) * 2.0
            dominant_prob = prob_short

        # 6. Estimación de Utilidad Neta en PPM
        spread_cost_ratio = spread / max(1e-4, mid_p)
        net_u_long = max(-1.0, min(1.0, (0.0035 * max(0.0, composite_score)) - spread_cost_ratio))
        net_u_short = max(-1.0, min(1.0, (0.0035 * max(0.0, -composite_score)) - spread_cost_ratio))

        # 7. Evaluar a través de la Máquina de Estados con Diales de Control Humano
        state, action, reasons = self.state_machine.evaluate(
            features=features,
            health=health,
            net_u_long=net_u_long,
            net_u_short=net_u_short,
            composite_score=composite_score,
        )

        # Probabilidad de confianza continua y fluctuante en tiempo real
        if state == TrafficLightColor.GREEN:
            active_prob = prob_long
        elif state == TrafficLightColor.RED:
            active_prob = prob_short
        else:
            # En AMARILLO refleja la probabilidad máxima dominante en desarrollo
            active_prob = dominant_prob

        # Calidad de calibración basada en consistencia de OFI y Kalman
        calib_qual = max(0.65, min(0.98, 1.0 - (vpin * 0.35)))

        # 8. Generar Contrato Inmutable DecisionLuz
        decision = DecisionLuzContract.create(
            instrument=self.instrument,
            timeframe="TICK",
            state=state,
            action=action,
            net_utility_long=net_u_long,
            net_utility_short=net_u_short,
            confidence_score=active_prob,
            calibration_quality=calib_qual,
            features=features,
            champion_model_id=self.champion_model_id,
            reason_codes=reasons,
            data_health=health,
            data_timestamp_utc=source_ts,
        )

        self.last_decision = decision
        return decision
