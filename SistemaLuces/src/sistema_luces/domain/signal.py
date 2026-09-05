"""Documento de Senal versionada (SPEC-001 §6.5, CA-10, CA-12, OPT-7)."""

from dataclasses import dataclass
from datetime import datetime
import re
from typing import Literal

from sistema_luces.domain.error import ErrorDominio
from sistema_luces.domain.result import Resultado, exito, fallo
from sistema_luces.domain.vocabulary import (
    DecisionWindow,
    Direction,
    Environment,
    Light,
    parse_decision_window,
    parse_direction,
    parse_environment,
    parse_instrument,
    parse_light,
    validate_price_scaled,
    validate_probability_scaled,
    validate_scale_factor,
)

_UUID_REGEX = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE)
_HASH_REGEX = re.compile(r"^[0-9a-f]{64}$", re.IGNORECASE)


@dataclass(frozen=True)
class SenalV1:
    signal_id: str
    case_id: str
    created_at_utc: datetime
    valid_until_utc: datetime
    environment: Environment
    instrument: Literal["US500"]
    decision_window: DecisionWindow
    market_event_cutoff: datetime
    reference_bid: int
    reference_ask: int
    price_scale: int
    data_age_ms: int | None
    direction: Direction
    light: Light
    reason_codes: tuple[str, ...]
    health_state: str
    safety_forced: bool
    strategy_id: str
    strategy_version: str
    feature_set_version: str
    feature_snapshot_hash: str
    model_id: str | None
    model_version: str | None
    model_hash: str | None
    calibration_version: str | None
    policy_version: str
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
    schema_version: Literal[1] = 1


def validar_senal(s: SenalV1) -> Resultado[SenalV1]:
    if not _UUID_REGEX.match(s.signal_id) or not _UUID_REGEX.match(s.case_id):
        return fallo(
            ErrorDominio(
                codigo="VALIDATION_ERROR",
                mensaje_seguro="signal_id y case_id deben ser UUIDs validos",
                reintentable=False,
                correlation_id=s.correlation_id,
                detalles={},
            )
        )
    env_res = parse_environment(s.environment, s.correlation_id)
    if not env_res.exito:
        return fallo(env_res.error)

    inst_res = parse_instrument(s.instrument, s.correlation_id)
    if not inst_res.exito:
        return fallo(inst_res.error)

    win_res = parse_decision_window(s.decision_window, s.correlation_id)
    if not win_res.exito:
        return fallo(win_res.error)

    dir_res = parse_direction(s.direction, s.correlation_id)
    if not dir_res.exito:
        return fallo(dir_res.error)

    light_res = parse_light(s.light, s.correlation_id)
    if not light_res.exito:
        return fallo(light_res.error)

    # Invariante: Si la luz es YELLOW, direction DEBE ser MONITOR (§6.5, CA-12)
    if s.light == "YELLOW" and s.direction != "MONITOR":
        return fallo(
            ErrorDominio(
                codigo="VALIDATION_ERROR",
                mensaje_seguro="Una senal con luz YELLOW debe tener obligatoriamente direccion MONITOR",
                reintentable=False,
                correlation_id=s.correlation_id,
                detalles={"light": s.light, "direction": s.direction},
            )
        )

    # Invariante: Coherencia de direccion y color
    if s.direction == "LONG" and s.light == "RED":
        return fallo(
            ErrorDominio(
                codigo="VALIDATION_ERROR",
                mensaje_seguro="Una senal LONG no puede tener luz RED",
                reintentable=False,
                correlation_id=s.correlation_id,
                detalles={"direction": s.direction, "light": s.light},
            )
        )
    if s.direction == "SHORT" and s.light == "GREEN":
        return fallo(
            ErrorDominio(
                codigo="VALIDATION_ERROR",
                mensaje_seguro="Una senal SHORT no puede tener luz GREEN",
                reintentable=False,
                correlation_id=s.correlation_id,
                detalles={"direction": s.direction, "light": s.light},
            )
        )

    # Invariante OPT-7: Causalidad temporal
    if not (s.market_event_cutoff <= s.created_at_utc < s.valid_until_utc):
        return fallo(
            ErrorDominio(
                codigo="VALIDATION_ERROR",
                mensaje_seguro=(
                    "Se viola la causalidad temporal: "
                    "market_event_cutoff <= created_at_utc < valid_until_utc"
                ),
                reintentable=False,
                correlation_id=s.correlation_id,
                detalles={
                    "market_event_cutoff": s.market_event_cutoff.isoformat(),
                    "created_at_utc": s.created_at_utc.isoformat(),
                    "valid_until_utc": s.valid_until_utc.isoformat(),
                },
            )
        )

    # Validar precios de referencia
    res_bid = validate_price_scaled(s.reference_bid, s.correlation_id)
    if not res_bid.exito:
        return fallo(res_bid.error)
    res_ask = validate_price_scaled(s.reference_ask, s.correlation_id)
    if not res_ask.exito:
        return fallo(res_ask.error)
    res_scale = validate_scale_factor(s.price_scale, s.correlation_id)
    if not res_scale.exito:
        return fallo(res_scale.error)

    # Validar probabilidades
    for prob in [s.calibrated_probability_long, s.calibrated_probability_short]:
        if prob is not None:
            res_p = validate_probability_scaled(prob, s.correlation_id)
            if not res_p.exito:
                return fallo(res_p.error)

    return exito(s)


@dataclass(frozen=True)
class PropuestaSimulacionV1:
    proposal_id: str
    signal_id: str
    created_at_utc: datetime
    direction: Direction
    quantity: int
    stop_loss_points: int
    take_profit_points: int
    estimated_risk_usd: int
    correlation_id: str

