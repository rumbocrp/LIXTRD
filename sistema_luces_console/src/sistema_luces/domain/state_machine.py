"""Máquina de Estados de Decisión con Histéresis y Diales de Control Humano (Fase 2)."""

from typing import List, Tuple, Optional
from sistema_luces.domain.vocabulary import TrafficLightColor, ActionType, ReasonCode, HealthState
from sistema_luces.domain.models import QuantFeatures
from sistema_luces.domain.human_control import HumanControlDials

class DecisionStateMachine:
    """
    Máquina de estados asimétrica para el Sistema de Luces con supervisión humana:
    - Umbral de entrada T_in = 0.45 (ajustable por dial)
    - Umbral de salida T_out = 0.15 (ajustable por dial)
    - Prohibida la conmutación directa GREEN <-> RED (pasa obligatoriamente por YELLOW)
    - Interrupción atómica inmediata si Hard Veto está activo o si los datos no son óptimos
    - Filtro de fricción: si el spread absorbe más del 35% de la ventaja estimada -> AMARILLO
    """
    def __init__(
        self,
        dials: Optional[HumanControlDials] = None,
        t_entry: Optional[float] = None,
        t_exit: Optional[float] = None,
        z_threshold: Optional[float] = None,
        ofi_threshold: Optional[float] = None,
    ):
        self.dials = dials or HumanControlDials()
        if t_entry is not None:
            self.dials.set_t_entry(t_entry)
        if t_exit is not None:
            self.dials.set_t_exit(t_exit)
        if z_threshold is not None:
            self.dials.set_z_critical(z_threshold)
        if ofi_threshold is not None:
            self.dials.set_ofi_critical(ofi_threshold)

        self.current_state = TrafficLightColor.YELLOW
        self.current_action = ActionType.MONITOR

    def evaluate(
        self,
        features: QuantFeatures,
        health: HealthState,
        net_u_long: float,
        net_u_short: float,
        composite_score: float,
    ) -> Tuple[TrafficLightColor, ActionType, List[ReasonCode]]:
        reasons: List[ReasonCode] = []

        # 1. Comprobación de Veto Manual del Operador (Hard Veto en <1.0ms)
        if self.dials.is_hard_veto_active:
            reasons.append(ReasonCode.MONITOR_POLICY)
            self.current_state = TrafficLightColor.YELLOW
            self.current_action = ActionType.MONITOR
            return self.current_state, self.current_action, reasons

        # 2. Validación de seguridad Fail-Safe de Datos
        if health != HealthState.HEALTHY:
            reasons.append(ReasonCode.MONITOR_DATA_STALE)
            self.current_state = TrafficLightColor.YELLOW
            self.current_action = ActionType.MONITOR
            return self.current_state, self.current_action, reasons

        # 3. Detección de Toxicidad VPIN
        if features.vpin_toxicity >= 0.85:
            reasons.append(ReasonCode.MONITOR_HIGH_TOXICITY)
            self.current_state = TrafficLightColor.YELLOW
            self.current_action = ActionType.MONITOR
            return self.current_state, self.current_action, reasons

        # 4. Filtro de Fricción de Spread (Cost Friction Filter)
        spread_cost_ratio = features.spread_pips / max(1e-4, features.mid_price)
        expected_raw_alpha = max(1e-6, abs(composite_score) * 0.0015)
        if spread_cost_ratio / expected_raw_alpha > self.dials.max_spread_friction_ratio:
            if abs(composite_score) >= self.dials.t_entry:
                reasons.append(ReasonCode.MONITOR_SPREAD_EXPANSION)
                self.current_state = TrafficLightColor.YELLOW
                self.current_action = ActionType.MONITOR
                return self.current_state, self.current_action, reasons

        # Aplicar clamp de confianza del operador
        clamped_score = max(-self.dials.max_confidence_clamp, min(self.dials.max_confidence_clamp, composite_score))

        # 5. Evaluación de condiciones de entrada con diales dinámicos
        long_condition = (
            clamped_score >= self.dials.t_entry
            and features.spread_z_score < -self.dials.z_critical
            and features.order_flow_imbalance >= (self.dials.ofi_critical / 2.0)
            and features.micro_price >= features.mid_price
        )

        short_condition = (
            clamped_score <= -self.dials.t_entry
            and features.spread_z_score > self.dials.z_critical
            and features.order_flow_imbalance <= -(self.dials.ofi_critical / 2.0)
            and features.micro_price <= features.mid_price
        )

        # 6. Transiciones de Estado con Histéresis Asimétrica
        if self.current_state == TrafficLightColor.YELLOW:
            if long_condition:
                self.current_state = TrafficLightColor.GREEN
                self.current_action = ActionType.BUY
                reasons.append(ReasonCode.KALMAN_Z_OVERSOLD)
                reasons.append(ReasonCode.OFI_BUY_IMBALANCE)
                if features.micro_price > features.mid_price:
                    reasons.append(ReasonCode.MICRO_PRICE_PREMIUM)
            elif short_condition:
                self.current_state = TrafficLightColor.RED
                self.current_action = ActionType.SELL
                reasons.append(ReasonCode.KALMAN_Z_OVERBOUGHT)
                reasons.append(ReasonCode.OFI_SELL_IMBALANCE)
                if features.micro_price < features.mid_price:
                    reasons.append(ReasonCode.MICRO_PRICE_DISCOUNT)
            else:
                reasons.append(ReasonCode.MONITOR_HYSTERESIS_HOLD)

        elif self.current_state == TrafficLightColor.GREEN:
            # Salida de posición larga: si cae por debajo de T_out o el spread se invierte
            if clamped_score < self.dials.t_exit or features.spread_z_score >= 0.0 or features.order_flow_imbalance < -self.dials.ofi_critical:
                self.current_state = TrafficLightColor.YELLOW
                self.current_action = ActionType.MONITOR
                reasons.append(ReasonCode.MONITOR_POLICY)
            else:
                reasons.append(ReasonCode.KALMAN_Z_OVERSOLD)
                reasons.append(ReasonCode.OFI_BUY_IMBALANCE)

        elif self.current_state == TrafficLightColor.RED:
            # Salida de posición corta: si sube por encima de -T_out o el spread se invierte
            if clamped_score > -self.dials.t_exit or features.spread_z_score <= 0.0 or features.order_flow_imbalance > self.dials.ofi_critical:
                self.current_state = TrafficLightColor.YELLOW
                self.current_action = ActionType.MONITOR
                reasons.append(ReasonCode.MONITOR_POLICY)
            else:
                reasons.append(ReasonCode.KALMAN_Z_OVERBOUGHT)
                reasons.append(ReasonCode.OFI_SELL_IMBALANCE)

        return self.current_state, self.current_action, reasons
