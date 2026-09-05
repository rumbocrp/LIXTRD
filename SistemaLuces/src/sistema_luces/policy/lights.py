"""Implementación de la Política de Luces (SPEC-001 §6.4, §6.5, CA-8, CA-11, CA-12, CA-27)."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal
import uuid

from sistema_luces.domain.error import ErrorDominio
from sistema_luces.domain.result import Resultado, exito, fallo
from sistema_luces.domain.signal import SenalV1, validar_senal
from sistema_luces.domain.state import TransicionEstadoV1, validar_transicion_estado
from sistema_luces.domain.vocabulary import (
    DecisionWindow,
    Direction,
    Environment,
    Light,
)
from sistema_luces.policy.hysteresis import HisteresisLuces


@dataclass(frozen=True)
class SolicitudLuz:
    case_id: str
    created_at_utc: datetime
    environment: Environment
    instrument: Literal["US500"]
    decision_window: DecisionWindow
    market_event_cutoff: datetime
    reference_bid: int
    reference_ask: int
    price_scale: int
    data_age_ms: int | None
    feed_health_state: str
    model_id: str | None
    model_version: str | None
    model_hash: str | None
    calibration_version: str | None
    feature_snapshot_hash: str
    raw_score_long: int | None
    raw_score_short: int | None
    calibrated_probability_long: int | None
    calibrated_probability_short: int | None
    expected_value_long_net: int | None
    expected_value_short_net: int | None
    cost_profile_version: str | None
    correlation_id: str
    causation_id: str | None
    code_hash: str
    signal_id: str | None = None
    policy_version: str | None = None


@dataclass(frozen=True)
class DecisionLuzV1:
    senal: SenalV1
    transicion: TransicionEstadoV1


class PoliticaLuces:
    """Motor de política de decisión de luces, abstención e histéresis."""

    def __init__(
        self,
        policy_version: str = "policy-us500-v1",
        strategy_id: str = "strat-us500-v1",
        strategy_version: str = "1.0.0",
        feature_set_version: str = "features-v1",
        threshold_green: int = 650_000,
        threshold_red: int = 350_000,
    ) -> None:
        self.policy_version = policy_version
        self.strategy_id = strategy_id
        self.strategy_version = strategy_version
        self.feature_set_version = feature_set_version
        self.threshold_green = threshold_green
        self.threshold_red = threshold_red
        self.histeresis = HisteresisLuces(
            threshold_green=threshold_green,
            threshold_red=threshold_red,
            initial_light="YELLOW",
        )

    def decidir(self, solicitud: SolicitudLuz) -> Resultado[DecisionLuzV1]:
        """Evalúa un caso maduro y emite una SenalV1 y TransicionEstadoV1 atómica."""
        prev_light = self.histeresis.luz_actual
        sig_id = solicitud.signal_id or str(uuid.uuid4())
        policy_ver = solicitud.policy_version or self.policy_version

        target_light: Light
        target_direction: Direction
        reasons: list[str] = []
        safety_forced = False

        # 1. Comprobar salud del feed (CA-7)
        if solicitud.feed_health_state != "HEALTHY":
            target_light = "YELLOW"
            target_direction = "MONITOR"
            safety_forced = True
            reasons.append("FEED_DEGRADED_YELLOW")
            self.histeresis.transicionar("YELLOW", solicitud.feed_health_state, solicitud.created_at_utc, solicitud.correlation_id)
        else:
            # 2. Determinar luz deseada según probabilidades calibradas
            prob_long = solicitud.calibrated_probability_long
            prob_short = solicitud.calibrated_probability_short

            desired_light: Light = "YELLOW"
            if prob_long is not None and prob_long >= self.threshold_green:
                desired_light = "GREEN"
            elif (prob_short is not None and prob_short >= self.threshold_green) or (
                prob_long is not None and prob_long <= self.threshold_red
            ):
                desired_light = "RED"
            else:
                desired_light = "YELLOW"

            # 3. Aplicar histéresis y protección de saltos (CA-8)
            if desired_light == prev_light:
                target_light = desired_light
                if target_light == "GREEN":
                    target_direction = "LONG"
                    reasons.append("MODEL_EDGE_LONG")
                elif target_light == "RED":
                    target_direction = "SHORT"
                    reasons.append("MODEL_EDGE_SHORT")
                else:
                    target_direction = "MONITOR"
                    reasons.append("LOW_CONFIDENCE_MONITOR")
            else:
                res_trans = self.histeresis.transicionar(
                    desired_light,
                    solicitud.feed_health_state,
                    solicitud.created_at_utc,
                    solicitud.correlation_id,
                )
                if res_trans.exito:
                    target_light = res_trans.datos
                    if target_light == "GREEN":
                        target_direction = "LONG"
                        reasons.append("MODEL_EDGE_LONG")
                    elif target_light == "RED":
                        target_direction = "SHORT"
                        reasons.append("MODEL_EDGE_SHORT")
                    else:
                        target_direction = "MONITOR"
                        reasons.append("LOW_CONFIDENCE_MONITOR")
                else:
                    # Si no es válida la transición directa (ej. GREEN <-> RED), caer a YELLOW intermedio
                    self.histeresis.transicionar(
                        "YELLOW",
                        solicitud.feed_health_state,
                        solicitud.created_at_utc,
                        solicitud.correlation_id,
                    )
                    target_light = "YELLOW"
                    target_direction = "MONITOR"
                    reasons.append("HYSTERESIS_INTERMEDIATE_YELLOW")

        # 4. Invariante CA-12: Luz YELLOW siempre impone MONITOR
        if target_light == "YELLOW":
            target_direction = "MONITOR"

        # 5. Invariante CA-11: Vencimiento de 30 segundos
        valid_until_utc = solicitud.created_at_utc + timedelta(seconds=30)

        # 6. Construcción de SenalV1
        senal = SenalV1(
            signal_id=sig_id,
            case_id=solicitud.case_id,
            created_at_utc=solicitud.created_at_utc,
            valid_until_utc=valid_until_utc,
            environment=solicitud.environment,
            instrument=solicitud.instrument,
            decision_window=solicitud.decision_window,
            market_event_cutoff=solicitud.market_event_cutoff,
            reference_bid=solicitud.reference_bid,
            reference_ask=solicitud.reference_ask,
            price_scale=solicitud.price_scale,
            data_age_ms=solicitud.data_age_ms,
            direction=target_direction,
            light=target_light,
            reason_codes=tuple(reasons),
            health_state=solicitud.feed_health_state,
            safety_forced=safety_forced,
            strategy_id=self.strategy_id,
            strategy_version=self.strategy_version,
            feature_set_version=self.feature_set_version,
            feature_snapshot_hash=solicitud.feature_snapshot_hash,
            model_id=solicitud.model_id,
            model_version=solicitud.model_version,
            model_hash=solicitud.model_hash,
            calibration_version=solicitud.calibration_version,
            policy_version=policy_ver,
            raw_score_long=solicitud.raw_score_long,
            raw_score_short=solicitud.raw_score_short,
            calibrated_probability_long=solicitud.calibrated_probability_long,
            calibrated_probability_short=solicitud.calibrated_probability_short,
            expected_value_long_net=solicitud.expected_value_long_net,
            expected_value_short_net=solicitud.expected_value_short_net,
            cost_profile_version=solicitud.cost_profile_version,
            correlation_id=solicitud.correlation_id,
            causation_id=solicitud.causation_id,
            code_hash=solicitud.code_hash,
            schema_version=1,
        )

        val_sig = validar_senal(senal)
        if not val_sig.exito:
            return fallo(val_sig.error)

        # 7. Construcción de TransicionEstadoV1
        transicion = TransicionEstadoV1(
            transition_id=str(uuid.uuid4()),
            aggregate_type="light",
            aggregate_id=f"light-{solicitud.instrument.lower()}",
            previous_state=prev_light,
            next_state=target_light,
            actor="system",
            occurred_at_utc=solicitud.created_at_utc,
            causation_id=sig_id,
            correlation_id=solicitud.correlation_id,
            policy_version=policy_ver,
            reason_codes=tuple(reasons),
            safety_forced=safety_forced,
        )

        val_trans = validar_transicion_estado(transicion)
        if not val_trans.exito:
            return fallo(val_trans.error)

        return exito(DecisionLuzV1(senal=senal, transicion=transicion))
