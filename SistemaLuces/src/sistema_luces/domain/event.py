"""Sobre de eventos, JSON canonico y familias de payloads (SPEC-001 §6.1, §6.2, §6.3, CA-4)."""

from dataclasses import asdict, dataclass, is_dataclass
from datetime import date, datetime, timezone
import hashlib
import json
import math
import re
from typing import Any, Literal

from sistema_luces.domain.error import ErrorDominio
from sistema_luces.domain.result import Resultado, exito, fallo
from sistema_luces.domain.vocabulary import (
    Environment,
    Instrument,
    Source,
    parse_environment,
    parse_instrument,
    parse_source,
    validate_price_scaled,
    validate_quantity_scaled,
    validate_scale_factor,
)

_UUID_REGEX = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE)
_HASH_REGEX = re.compile(r"^[0-9a-f]{64}$", re.IGNORECASE)

TIPOS_EVENTO_PERMITIDOS: frozenset[str] = frozenset(
    {
        "QUOTE_TICK",
        "INDEX_MARKET_SNAPSHOT",
        "CROSS_ASSET_SNAPSHOT",
        "DEPTH_DELTA",
        "SESSION_STATUS",
        "HEARTBEAT",
        "GAP_DETECTED",
        "DUPLICATE",
        "OUT_OF_ORDER",
        "STALE",
        "RECONNECTED",
        "CLOCK_ROLLBACK",
        "DISK_ERROR",
        "CASE_CREATED",
        "SIGNAL_EMITTED",
        "SIGNAL_EXPIRED",
        "SIGNAL_INVALIDATED",
        "LABEL_MATURED",
        "LIGHT_TRANSITION",
        "SIM_PROPOSED",
        "SIM_OPENED",
        "SIM_FILL",
        "SIM_CLOSED",
        "SIM_REJECTED",
        "SIM_CANCELLED",
        "RISK_PROFILE_ACTIVATED",
        "RISK_LIMIT_HIT",
        "KILL_SWITCH",
        "TRAINING_ATTEMPT",
        "EVALUATION",
        "PROMOTION",
        "ROLLBACK",
        "DRIFT",
        "IMPORT_ACCEPTED",
        "IMPORT_REJECTED",
        "RECONCILIATION_UPDATED",
    }
)


def _canonical_serializer(obj: object) -> object:
    if isinstance(obj, datetime):
        if obj.tzinfo is None:
            raise ValueError("No se admiten datetimes naive en JSON canonico")
        utc_dt = obj.astimezone(timezone.utc)
        if utc_dt.microsecond > 0:
            return utc_dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        return utc_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    if isinstance(obj, date):
        return obj.isoformat()
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            raise ValueError("No se admiten floats NaN o Infinitos")
        return obj
    if is_dataclass(obj):
        return asdict(obj)
    if isinstance(obj, (set, frozenset)):
        return sorted(list(obj))
    if isinstance(obj, tuple):
        return list(obj)
    raise TypeError(f"Objeto no serializable en JSON canonico: {type(obj).__name__}")


def canonical_json_dumps(obj: object) -> str:
    """Produce una representacion JSON canonica UTF-8 con claves ordenadas y sin espacios."""
    return json.dumps(
        obj,
        default=_canonical_serializer,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    )


def canonical_json_bytes(obj: object) -> bytes:
    """Produce los bytes UTF-8 del JSON canonico."""
    return canonical_json_dumps(obj).encode("utf-8")


def compute_payload_hash(payload: object) -> str:
    """Calcula el hash SHA-256 hex del payload en formato JSON canonico."""
    return hashlib.sha256(canonical_json_bytes(payload)).hexdigest()


@dataclass(frozen=True)
class SobreEventoV1:
    event_id: str
    event_type: str
    schema_version: Literal[1]
    occurred_at_utc: datetime
    received_at_utc: datetime
    persisted_at_utc: datetime | None
    source: Source
    environment: Environment
    source_account_id_hash: str | None
    instrument: Instrument
    symbol_id: str | None
    source_sequence: int | None
    correlation_id: str
    causation_id: str | None
    payload_hash: str
    previous_hash: str | None
    payload: dict[str, Any]


def validar_sobre_evento(sobre: SobreEventoV1) -> Resultado[SobreEventoV1]:
    if not isinstance(sobre.event_id, str) or not _UUID_REGEX.match(sobre.event_id):
        return fallo(
            ErrorDominio(
                codigo="VALIDATION_ERROR",
                mensaje_seguro="event_id debe ser un UUID valido",
                reintentable=False,
                correlation_id=sobre.correlation_id,
                detalles={"event_id": str(sobre.event_id)},
            )
        )
    if sobre.event_type not in TIPOS_EVENTO_PERMITIDOS:
        return fallo(
            ErrorDominio(
                codigo="SCHEMA_UNSUPPORTED",
                mensaje_seguro=f"Tipo de evento no admitido: {sobre.event_type}",
                reintentable=False,
                correlation_id=sobre.correlation_id,
                detalles={"event_type": sobre.event_type},
            )
        )
    if sobre.schema_version != 1:
        return fallo(
            ErrorDominio(
                codigo="SCHEMA_UNSUPPORTED",
                mensaje_seguro="Solo se admite schema_version=1 en V1",
                reintentable=False,
                correlation_id=sobre.correlation_id,
                detalles={"schema_version": sobre.schema_version},
            )
        )
    env_res = parse_environment(sobre.environment, sobre.correlation_id)
    if not env_res.exito:
        return fallo(env_res.error)

    src_res = parse_source(sobre.source, sobre.correlation_id)
    if not src_res.exito:
        return fallo(src_res.error)

    inst_res = parse_instrument(sobre.instrument, sobre.correlation_id)
    if not inst_res.exito:
        return fallo(inst_res.error)

    if not isinstance(sobre.occurred_at_utc, datetime) or sobre.occurred_at_utc.tzinfo is None:
        return fallo(
            ErrorDominio(
                codigo="VALIDATION_ERROR",
                mensaje_seguro="occurred_at_utc debe ser un datetime con zona UTC",
                reintentable=False,
                correlation_id=sobre.correlation_id,
                detalles={},
            )
        )
    if not isinstance(sobre.received_at_utc, datetime) or sobre.received_at_utc.tzinfo is None:
        return fallo(
            ErrorDominio(
                codigo="VALIDATION_ERROR",
                mensaje_seguro="received_at_utc debe ser un datetime con zona UTC",
                reintentable=False,
                correlation_id=sobre.correlation_id,
                detalles={},
            )
        )
    if sobre.source_sequence is not None and (
        not isinstance(sobre.source_sequence, int) or sobre.source_sequence < 0
    ):
        return fallo(
            ErrorDominio(
                codigo="VALIDATION_ERROR",
                mensaje_seguro="source_sequence debe ser un entero >= 0 o None",
                reintentable=False,
                correlation_id=sobre.correlation_id,
                detalles={"source_sequence": str(sobre.source_sequence)},
            )
        )

    # Validar payload_hash contra el payload canónico
    try:
        calculated_hash = compute_payload_hash(sobre.payload)
    except Exception as e:
        return fallo(
            ErrorDominio(
                codigo="VALIDATION_ERROR",
                mensaje_seguro=f"Error al serializar payload canonicamente: {e}",
                reintentable=False,
                correlation_id=sobre.correlation_id,
                detalles={},
            )
        )

    if calculated_hash.lower() != sobre.payload_hash.lower():
        return fallo(
            ErrorDominio(
                codigo="INTEGRITY_ERROR",
                mensaje_seguro="El payload_hash del sobre no coincide con el SHA-256 del payload",
                reintentable=False,
                correlation_id=sobre.correlation_id,
                detalles={"declarado": sobre.payload_hash, "calculado": calculated_hash},
            )
        )

    return exito(sobre)


# Payloads específicos de §6.3
@dataclass(frozen=True)
class QuoteTickPayloadV1:
    bid: int
    ask: int
    price_scale: int
    bid_size: int | None
    ask_size: int | None
    source_timestamp_utc: datetime
    source_sequence: int | None


def validar_payload_quote_tick(p: QuoteTickPayloadV1, correlation_id: str = "") -> Resultado[QuoteTickPayloadV1]:
    res_bid = validate_price_scaled(p.bid, correlation_id)
    if not res_bid.exito:
        return fallo(res_bid.error)
    res_ask = validate_price_scaled(p.ask, correlation_id)
    if not res_ask.exito:
        return fallo(res_ask.error)
    res_scale = validate_scale_factor(p.price_scale, correlation_id)
    if not res_scale.exito:
        return fallo(res_scale.error)

    if p.ask < p.bid:
        return fallo(
            ErrorDominio(
                codigo="VALIDATION_ERROR",
                mensaje_seguro="El precio ask no puede ser inferior al precio bid",
                reintentable=False,
                correlation_id=correlation_id,
                detalles={"bid": p.bid, "ask": p.ask},
            )
        )
    if p.bid_size is not None and (not isinstance(p.bid_size, int) or p.bid_size <= 0):
        return fallo(
            ErrorDominio(
                codigo="VALIDATION_ERROR",
                mensaje_seguro="bid_size debe ser mayor a 0 o None",
                reintentable=False,
                correlation_id=correlation_id,
                detalles={"bid_size": str(p.bid_size)},
            )
        )
    if p.ask_size is not None and (not isinstance(p.ask_size, int) or p.ask_size <= 0):
        return fallo(
            ErrorDominio(
                codigo="VALIDATION_ERROR",
                mensaje_seguro="ask_size debe ser mayor a 0 o None",
                reintentable=False,
                correlation_id=correlation_id,
                detalles={"ask_size": str(p.ask_size)},
            )
        )
    return exito(p)


@dataclass(frozen=True)
class DepthDeltaPayloadV1:
    side: Literal["BID", "ASK"]
    level: int
    price: int
    size: int
    action: Literal["ADD", "UPDATE", "DELETE"]
    sequence: int
    quarantined: bool = True


@dataclass(frozen=True)
class SessionStatusPayloadV1:
    status: Literal["OPEN", "CLOSED", "UNKNOWN"]
    session_name: str
    source: str


@dataclass(frozen=True)
class HeartbeatPayloadV1:
    last_sequence: int | None
    last_tick_utc: datetime | None
    source_age_ms: int | None


@dataclass(frozen=True)
class GapDetectedPayloadV1:
    start_sequence: int
    end_sequence: int
    missing_count: int
    action: str = "FORCE_YELLOW_STOP_SIM"
    resolution: str | None = None


@dataclass(frozen=True)
class DuplicatePayloadV1:
    duplicate_key: str
    retained_event_id: str


@dataclass(frozen=True)
class OutOfOrderPayloadV1:
    expected_sequence: int
    received_sequence: int
    action: str = "QUARANTINE"


@dataclass(frozen=True)
class StalePayloadV1:
    data_age_ms: int
    threshold_ms: int
    action: str = "FORCE_YELLOW"


@dataclass(frozen=True)
class ReconnectedPayloadV1:
    attempt: int
    duration_ms: int
    last_safe_cutoff: datetime | None


@dataclass(frozen=True)
class ClockRollbackPayloadV1:
    previous_time_utc: datetime
    new_time_utc: datetime
    delta_ms: int
    action: str = "FAIL_CLOSED"


@dataclass(frozen=True)
class DiskErrorPayloadV1:
    safe_code: str
    operation: str
    persistence_state: str


@dataclass(frozen=True)
class FeedQualityPayloadV1:
    anomaly_type: str
    details: dict[str, Any]
    action: str = "FORCE_YELLOW"
