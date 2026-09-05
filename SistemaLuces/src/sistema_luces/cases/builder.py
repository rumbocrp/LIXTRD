"""Constructor de Casos V1 y snapshots causales (SPEC-001 §5.3, §6.3, CA-9, OPT-7, WP-05)."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
import re
from typing import Any, Literal

from sistema_luces.cases.features import calcular_snapshot_features, calcular_snapshot_hash
from sistema_luces.domain.error import ErrorDominio
from sistema_luces.domain.event import SobreEventoV1
from sistema_luces.domain.result import Resultado, exito, fallo
from sistema_luces.domain.vocabulary import (
    DecisionWindow,
    Environment,
    Instrument,
    parse_decision_window,
    parse_environment,
    parse_instrument,
    validate_scale_factor,
)

_UUID_REGEX = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE)
_HASH_REGEX = re.compile(r"^[0-9a-f]{64}$", re.IGNORECASE)


@dataclass(frozen=True)
class SolicitudCaso:
    case_id: str
    correlation_id: str
    decision_window: DecisionWindow
    window_start_utc: datetime
    window_end_utc: datetime
    market_event_cutoff: datetime
    feed_health_state: str
    feature_set_version: str
    environment: Environment = "REPLAY"
    instrument: Literal["US500"] = "US500"
    price_scale: int = 100
    causation_id: str | None = None
    buffer_eventos: tuple[SobreEventoV1, ...] = ()


def validar_solicitud_caso(sol: SolicitudCaso) -> Resultado[SolicitudCaso]:
    if not isinstance(sol.case_id, str) or not _UUID_REGEX.match(sol.case_id):
        return fallo(
            ErrorDominio(
                codigo="VALIDATION_ERROR",
                mensaje_seguro="case_id debe ser un UUID valido",
                reintentable=False,
                correlation_id=sol.correlation_id,
                detalles={"case_id": str(sol.case_id)},
            )
        )
    if not isinstance(sol.correlation_id, str) or not _UUID_REGEX.match(sol.correlation_id):
        return fallo(
            ErrorDominio(
                codigo="VALIDATION_ERROR",
                mensaje_seguro="correlation_id debe ser un UUID valido",
                reintentable=False,
                correlation_id=sol.correlation_id,
                detalles={"correlation_id": str(sol.correlation_id)},
            )
        )

    env_res = parse_environment(sol.environment, sol.correlation_id)
    if not env_res.exito:
        return fallo(env_res.error)

    inst_res = parse_instrument(sol.instrument, sol.correlation_id)
    if not inst_res.exito:
        return fallo(inst_res.error)

    win_res = parse_decision_window(sol.decision_window, sol.correlation_id)
    if not win_res.exito:
        return fallo(win_res.error)

    scale_res = validate_scale_factor(sol.price_scale, sol.correlation_id)
    if not scale_res.exito:
        return fallo(scale_res.error)

    # Validar fechas UTC
    for name, dt in [
        ("window_start_utc", sol.window_start_utc),
        ("window_end_utc", sol.window_end_utc),
        ("market_event_cutoff", sol.market_event_cutoff),
    ]:
        if not isinstance(dt, datetime) or dt.tzinfo is None:
            return fallo(
                ErrorDominio(
                    codigo="VALIDATION_ERROR",
                    mensaje_seguro=f"{name} debe ser un datetime con zona horaria UTC",
                    reintentable=False,
                    correlation_id=sol.correlation_id,
                    detalles={},
                )
            )

    # Invariante OPT-7
    if not (sol.window_start_utc < sol.window_end_utc <= sol.market_event_cutoff):
        return fallo(
            ErrorDominio(
                codigo="VALIDATION_ERROR",
                mensaje_seguro="Invariante de causalidad: window_start_utc < window_end_utc <= market_event_cutoff",
                reintentable=False,
                correlation_id=sol.correlation_id,
                detalles={
                    "window_start_utc": sol.window_start_utc.isoformat(),
                    "window_end_utc": sol.window_end_utc.isoformat(),
                    "market_event_cutoff": sol.market_event_cutoff.isoformat(),
                },
            )
        )

    return exito(sol)


@dataclass(frozen=True)
class CasoV1:
    case_id: str
    decision_window: DecisionWindow
    window_start_utc: datetime
    window_end_utc: datetime
    market_event_cutoff: datetime
    reference_bid: int | None
    reference_ask: int | None
    price_scale: int
    feature_set_version: str
    feature_snapshot: dict[str, Any]
    feature_snapshot_hash: str
    feed_health_state: str
    eligible_for_signal: bool
    event_count_in_window: int
    reason_codes: tuple[str, ...]
    correlation_id: str
    causation_id: str | None
    created_at_utc: datetime
    environment: Environment = "REPLAY"
    instrument: Literal["US500"] = "US500"


def validar_caso(caso: CasoV1) -> Resultado[CasoV1]:
    if not isinstance(caso.case_id, str) or not _UUID_REGEX.match(caso.case_id):
        return fallo(
            ErrorDominio(
                codigo="VALIDATION_ERROR",
                mensaje_seguro="case_id debe ser un UUID valido",
                reintentable=False,
                correlation_id=caso.correlation_id,
                detalles={"case_id": str(caso.case_id)},
            )
        )

    env_res = parse_environment(caso.environment, caso.correlation_id)
    if not env_res.exito:
        return fallo(env_res.error)

    computed_hash = calcular_snapshot_hash(caso.feature_snapshot)
    if computed_hash.lower() != caso.feature_snapshot_hash.lower():
        return fallo(
            ErrorDominio(
                codigo="INTEGRITY_ERROR",
                mensaje_seguro="feature_snapshot_hash no coincide con el hash del snapshot",
                reintentable=False,
                correlation_id=caso.correlation_id,
                detalles={"declarado": caso.feature_snapshot_hash, "calculado": computed_hash},
            )
        )

    return exito(caso)


class ConstructorCaso:
    """Construye snapshots inmutables de casos cumpliendo rigurosamente OPT-7 y CA-9."""

    def construir(
        self,
        solicitud: SolicitudCaso,
        buffer_eventos: list[SobreEventoV1] | tuple[SobreEventoV1, ...] | None = None,
    ) -> Resultado[CasoV1]:
        res_sol = validar_solicitud_caso(solicitud)
        if not res_sol.exito:
            return fallo(res_sol.error)

        eventos = buffer_eventos if buffer_eventos is not None else solicitud.buffer_eventos

        features = calcular_snapshot_features(
            events=eventos,
            window_start_utc=solicitud.window_start_utc,
            window_end_utc=solicitud.window_end_utc,
            market_event_cutoff=solicitud.market_event_cutoff,
        )

        reasons: list[str] = []
        eligible: bool = True

        # Verificar salud del feed
        if solicitud.feed_health_state != "HEALTHY":
            eligible = False
            reasons.append("FEED_NOT_HEALTHY")

        # Verificar disponibilidad de datos
        if features["tick_count"] == 0 or features["price_last_bid"] is None or features["price_last_ask"] is None:
            eligible = False
            reasons.append("INSUFFICIENT_DATA")

        caso = CasoV1(
            case_id=solicitud.case_id,
            decision_window=solicitud.decision_window,
            window_start_utc=solicitud.window_start_utc,
            window_end_utc=solicitud.window_end_utc,
            market_event_cutoff=solicitud.market_event_cutoff,
            reference_bid=features["price_last_bid"],
            reference_ask=features["price_last_ask"],
            price_scale=solicitud.price_scale,
            feature_set_version=solicitud.feature_set_version,
            feature_snapshot=features,
            feature_snapshot_hash=features["feature_snapshot_hash"],
            feed_health_state=solicitud.feed_health_state,
            eligible_for_signal=eligible,
            event_count_in_window=features["tick_count"],
            reason_codes=tuple(reasons),
            correlation_id=solicitud.correlation_id,
            causation_id=solicitud.causation_id,
            created_at_utc=solicitud.market_event_cutoff,
            environment=solicitud.environment,
            instrument=solicitud.instrument,
        )

        res_val = validar_caso(caso)
        if not res_val.exito:
            return fallo(res_val.error)

        return exito(caso)
