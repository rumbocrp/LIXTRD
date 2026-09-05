"""DTOs publicos V1 y sus validadores (SPEC-001 §5.2.1)."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Literal

from sistema_luces.domain.error import ErrorDominio
from sistema_luces.domain.proyeccion_lectura_v1 import (
    BalancinItemV1,
    ProyeccionLecturaV1,
    VALID_HEALTH_STATES,
    validar_proyeccion_lectura_v1,
)
from sistema_luces.domain.result import Resultado, exito, fallo
from sistema_luces.domain.vocabulary import (
    DIRECCIONES_CANONICAS_PERMITIDAS,
    ENTORNOS_PERMITIDOS,
    ESTADOS_UI_PERMITIDOS,
    LUCES_PERMITIDAS,
    DireccionCanonica,
    Direction,
    Environment,
    EstadoUI,
    Light,
    Instrument,
    _FORBIDDEN_ENV_NAMES,
    parse_direccion_canonica,
    parse_environment,
    parse_estado_ui,
    parse_instrument,
    parse_light,
)

ReasonCode = str

_UUID_REGEX = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE)
_HASH_REGEX = re.compile(r"^[0-9a-f]{64}$", re.IGNORECASE)
_ALLOWED_VIEWS = frozenset({"FEED", "LIGHTS", "SIGNALS", "SIMULATIONS", "METRICS", "SECURITY", "TRACE", "IMPORTS"})
_ALLOWED_DOC_SCHEMAS = frozenset(
    {
        "sistema-luces/event-envelope-v1",
        "sistema-luces/state-transition-v1",
        "sistema-luces/signal-v1",
        "sistema-luces/simulation-v1",
        "sistema-luces/metric-snapshot-v1",
    }
)
VALID_HEALTH_STATES: frozenset[str] = frozenset(
    {"NO_DATA", "INITIALIZING", "HEALTHY", "STALE", "GAPPED", "RECONNECTING", "STOPPED", "ERROR"}
)


def _format_iso_utc(dt: datetime | str | None) -> str | None:
    if dt is None:
        return None
    if isinstance(dt, str):
        return dt
    if isinstance(dt, datetime):
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        utc_dt = dt.astimezone(timezone.utc)
        if utc_dt.microsecond == 0:
            return utc_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        return utc_dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    return str(dt)


def _parse_iso_utc(val: datetime | str | None) -> datetime | None:
    if val is None:
        return None
    if isinstance(val, datetime):
        if val.tzinfo is None:
            return val.replace(tzinfo=timezone.utc)
        return val.astimezone(timezone.utc)
    if isinstance(val, str):
        clean_str = val.strip()
        if clean_str.endswith("Z") or clean_str.endswith("z"):
            clean_str = clean_str[:-1] + "+00:00"
        parsed = datetime.fromisoformat(clean_str)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    return None


def _is_valid_uuid(val: str) -> bool:
    return isinstance(val, str) and bool(_UUID_REGEX.match(val))


def _is_valid_hash(val: str) -> bool:
    return isinstance(val, str) and bool(_HASH_REGEX.match(val))


def _is_utc_datetime(dt: object) -> bool:
    return isinstance(dt, datetime) and dt.tzinfo is not None and dt.utcoffset() == timezone.utc.utcoffset(dt)


@dataclass(frozen=True)
class SolicitudReplay:
    correlation_id: str
    environment: Literal["REPLAY"]
    dataset_manifest_hash: str
    range_start_utc: datetime
    range_end_utc: datetime
    clock_seed: int


@dataclass(frozen=True)
class SolicitudShadow:
    correlation_id: str
    environment: Literal["SHADOW"]
    source_profile_version: str
    capabilities_manifest_hash: str
    expected_demo_account_hash: str


@dataclass(frozen=True)
class SolicitudImportacionDemo:
    correlation_id: str
    environment: Literal["BROKER_DEMO_OBSERVED"]
    staged_copy: str
    expected_sha256: str
    adapter_version: str
    expected_demo_account_hash: str


@dataclass(frozen=True)
class SolicitudConsulta:
    correlation_id: str
    environment: Environment
    view: Literal["FEED", "LIGHTS", "SIGNALS", "SIMULATIONS", "METRICS", "SECURITY", "TRACE", "IMPORTS"]
    as_of_event_id: str | None
    cursor: str | None
    limit: int


@dataclass(frozen=True)
class ResumenEjecucion:
    run_id: str
    environment: Literal["REPLAY", "SHADOW"]
    final_event_cutoff: str | None
    accepted_event_count: int
    rejected_event_count: int
    emitted_signal_count: int
    opened_simulation_count: int
    reason_codes: tuple[ReasonCode, ...] = ()


@dataclass(frozen=True)
class ResumenImportacion:
    import_id: str
    environment: Literal["BROKER_DEMO_OBSERVED"]
    final_event_cutoff: str | None
    accepted_count: int
    rejected_count: int
    matched_count: int
    unmatched_count: int
    reason_codes: tuple[ReasonCode, ...] = ()


@dataclass(frozen=True)
class DocumentoVistaV1:
    schema_id: Literal[
        "sistema-luces/event-envelope-v1",
        "sistema-luces/state-transition-v1",
        "sistema-luces/signal-v1",
        "sistema-luces/simulation-v1",
        "sistema-luces/metric-snapshot-v1",
    ] = "sistema-luces/metric-snapshot-v1"
    document_hash: str = ""
    canonical_json_utf8: bytes = b"{}"
    view_id: str | None = None
    view_name: str | None = None
    environment: str | None = None
    as_of_event_id: str | None = None
    generated_at_utc: datetime | None = None
    canonical_json_hash: str | None = None
    payload: dict[str, Any] | None = None


@dataclass(frozen=True)
class VistaLectura:
    instrument: Instrument
    environment: Environment
    health_state: str
    data_age_ms: int | None
    light: Light
    reason_codes: tuple[ReasonCode, ...]
    model_id: str | None
    model_version: str | None
    model_hash: str | None
    policy_version: str
    kill_switch_active: bool
    as_of_event_id: str | None
    next_cursor: str | None
    documents: tuple[DocumentoVistaV1, ...]
    direction: Direction = "MONITOR"
    ui_state: EstadoUI | None = None
    schema_version: int = 1
    # Telemetría cuantitativa densa (Milestones 2 & 3)
    bid: float | None = None
    ask: float | None = None
    spread: float | None = None
    mid_price: float | None = None
    micro_price: float | None = None
    beta_kalman: float | None = None
    z_score: float | None = None
    desbalance_ofi: float | None = None
    balancines: tuple[dict[str, Any] | BalancinItemV1, ...] = ()
    drawdown_diario_pct: float | None = None
    limite_por_trade_pct: float | None = None
    slots_concurrentes_usados: int | None = None
    slots_concurrentes_max: int | None = None
    pnl_paper_acumulado: float | None = None
    secuencia: int | None = None
    hash_snapshot: str | None = None
    salud_feed: str | None = None
    diagnostico_semaforo: dict[str, Any] | None = None
    market_data: dict[str, Any] = field(default_factory=dict)
    market_assets: tuple[dict[str, Any], ...] = ()
    proyeccion: ProyeccionLecturaV1 | None = None


def validar_solicitud_replay(sol: SolicitudReplay) -> Resultado[SolicitudReplay]:
    env_res = parse_environment(sol.environment, sol.correlation_id)
    if not env_res.exito:
        return fallo(env_res.error)
    if sol.environment != "REPLAY":
        return fallo(
            ErrorDominio(
                codigo="VALIDATION_ERROR",
                mensaje_seguro="SolicitudReplay exige entorno REPLAY",
                reintentable=False,
                correlation_id=sol.correlation_id,
                detalles={"entorno": sol.environment},
            )
        )
    if not _is_valid_uuid(sol.correlation_id):
        return fallo(
            ErrorDominio(
                codigo="VALIDATION_ERROR",
                mensaje_seguro="correlation_id debe ser un UUID valido",
                reintentable=False,
                correlation_id=sol.correlation_id,
                detalles={},
            )
        )
    if not _is_valid_hash(sol.dataset_manifest_hash):
        return fallo(
            ErrorDominio(
                codigo="VALIDATION_ERROR",
                mensaje_seguro="dataset_manifest_hash debe ser SHA-256 de 64 hex caracteres",
                reintentable=False,
                correlation_id=sol.correlation_id,
                detalles={},
            )
        )
    if not _is_utc_datetime(sol.range_start_utc) or not _is_utc_datetime(sol.range_end_utc):
        return fallo(
            ErrorDominio(
                codigo="VALIDATION_ERROR",
                mensaje_seguro="Las fechas de rango deben ser datetimes con zona horaria UTC",
                reintentable=False,
                correlation_id=sol.correlation_id,
                detalles={},
            )
        )
    if sol.range_start_utc >= sol.range_end_utc:
        return fallo(
            ErrorDominio(
                codigo="VALIDATION_ERROR",
                mensaje_seguro="range_start_utc debe ser estrictamente anterior a range_end_utc",
                reintentable=False,
                correlation_id=sol.correlation_id,
                detalles={},
            )
        )
    if not isinstance(sol.clock_seed, int) or sol.clock_seed < 0 or sol.clock_seed > (2**63 - 1):
        return fallo(
            ErrorDominio(
                codigo="VALIDATION_ERROR",
                mensaje_seguro="clock_seed debe estar en el rango 0..2^63-1",
                reintentable=False,
                correlation_id=sol.correlation_id,
                detalles={},
            )
        )
    return exito(sol)


def validar_solicitud_shadow(sol: SolicitudShadow) -> Resultado[SolicitudShadow]:
    env_res = parse_environment(sol.environment, sol.correlation_id)
    if not env_res.exito:
        return fallo(env_res.error)
    if sol.environment != "SHADOW":
        return fallo(
            ErrorDominio(
                codigo="VALIDATION_ERROR",
                mensaje_seguro="SolicitudShadow exige entorno SHADOW",
                reintentable=False,
                correlation_id=sol.correlation_id,
                detalles={"entorno": sol.environment},
            )
        )
    if not _is_valid_uuid(sol.correlation_id):
        return fallo(
            ErrorDominio(
                codigo="VALIDATION_ERROR",
                mensaje_seguro="correlation_id debe ser un UUID valido",
                reintentable=False,
                correlation_id=sol.correlation_id,
                detalles={},
            )
        )
    if not isinstance(sol.source_profile_version, str) or not sol.source_profile_version.strip():
        return fallo(
            ErrorDominio(
                codigo="VALIDATION_ERROR",
                mensaje_seguro="source_profile_version requerida",
                reintentable=False,
                correlation_id=sol.correlation_id,
                detalles={},
            )
        )
    if not _is_valid_hash(sol.capabilities_manifest_hash) or not _is_valid_hash(sol.expected_demo_account_hash):
        return fallo(
            ErrorDominio(
                codigo="VALIDATION_ERROR",
                mensaje_seguro="Los hashes de capabilities y cuenta demo deben ser SHA-256 validos",
                reintentable=False,
                correlation_id=sol.correlation_id,
                detalles={},
            )
        )
    return exito(sol)


def validar_solicitud_importacion_demo(sol: SolicitudImportacionDemo) -> Resultado[SolicitudImportacionDemo]:
    env_res = parse_environment(sol.environment, sol.correlation_id)
    if not env_res.exito:
        return fallo(env_res.error)
    if sol.environment != "BROKER_DEMO_OBSERVED":
        return fallo(
            ErrorDominio(
                codigo="VALIDATION_ERROR",
                mensaje_seguro="SolicitudImportacionDemo exige entorno BROKER_DEMO_OBSERVED",
                reintentable=False,
                correlation_id=sol.correlation_id,
                detalles={"entorno": sol.environment},
            )
        )
    if not _is_valid_uuid(sol.correlation_id):
        return fallo(
            ErrorDominio(
                codigo="VALIDATION_ERROR",
                mensaje_seguro="correlation_id debe ser un UUID valido",
                reintentable=False,
                correlation_id=sol.correlation_id,
                detalles={},
            )
        )
    # Validate staged_copy safe basename
    if not isinstance(sol.staged_copy, str) or not sol.staged_copy.strip():
        return fallo(
            ErrorDominio(
                codigo="VALIDATION_ERROR",
                mensaje_seguro="staged_copy requerido",
                reintentable=False,
                correlation_id=sol.correlation_id,
                detalles={},
            )
        )
    p = Path(sol.staged_copy)
    is_safe = (
        not p.is_absolute()
        and ".." not in sol.staged_copy
        and "\\" not in sol.staged_copy
        and ("/" not in sol.staged_copy or sol.staged_copy.startswith("staged/"))
    )
    if not is_safe:
        return fallo(
            ErrorDominio(
                codigo="VALIDATION_ERROR",
                mensaje_seguro="staged_copy debe ser un basename seguro de staging",
                reintentable=False,
                correlation_id=sol.correlation_id,
                detalles={"staged_copy": sol.staged_copy},
            )
        )
    if not _is_valid_hash(sol.expected_sha256) or not _is_valid_hash(sol.expected_demo_account_hash):
        return fallo(
            ErrorDominio(
                codigo="VALIDATION_ERROR",
                mensaje_seguro="expected_sha256 y expected_demo_account_hash deben ser SHA-256 validos",
                reintentable=False,
                correlation_id=sol.correlation_id,
                detalles={},
            )
        )
    return exito(sol)


def validar_solicitud_consulta(sol: SolicitudConsulta) -> Resultado[SolicitudConsulta]:
    env_res = parse_environment(sol.environment, sol.correlation_id)
    if not env_res.exito:
        return fallo(env_res.error)
    if not _is_valid_uuid(sol.correlation_id):
        return fallo(
            ErrorDominio(
                codigo="VALIDATION_ERROR",
                mensaje_seguro="correlation_id debe ser un UUID valido",
                reintentable=False,
                correlation_id=sol.correlation_id,
                detalles={},
            )
        )
    if sol.view not in _ALLOWED_VIEWS:
        return fallo(
            ErrorDominio(
                codigo="VALIDATION_ERROR",
                mensaje_seguro=f"Vista invalida: {sol.view}",
                reintentable=False,
                correlation_id=sol.correlation_id,
                detalles={"view": sol.view},
            )
        )
    if not isinstance(sol.limit, int) or sol.limit < 1 or sol.limit > 200:
        return fallo(
            ErrorDominio(
                codigo="VALIDATION_ERROR",
                mensaje_seguro="El limite de consulta debe ser un entero entre 1 y 200",
                reintentable=False,
                correlation_id=sol.correlation_id,
                detalles={"limit": str(sol.limit)},
            )
        )
    return exito(sol)


def validar_resumen_ejecucion(res: ResumenEjecucion) -> Resultado[ResumenEjecucion]:
    if not _is_valid_uuid(res.run_id):
        return fallo(
            ErrorDominio(
                codigo="VALIDATION_ERROR",
                mensaje_seguro="run_id debe ser un UUID valido",
                reintentable=False,
                correlation_id=res.run_id,
                detalles={},
            )
        )
    for count in [
        res.accepted_event_count,
        res.rejected_event_count,
        res.emitted_signal_count,
        res.opened_simulation_count,
    ]:
        if not isinstance(count, int) or count < 0:
            return fallo(
                ErrorDominio(
                    codigo="VALIDATION_ERROR",
                    mensaje_seguro="Los conteos deben ser enteros mayores o iguales a 0",
                    reintentable=False,
                    correlation_id=res.run_id,
                    detalles={"conteo": str(count)},
                )
            )
    return exito(res)


def validar_resumen_importacion(res: ResumenImportacion) -> Resultado[ResumenImportacion]:
    if not _is_valid_uuid(res.import_id):
        return fallo(
            ErrorDominio(
                codigo="VALIDATION_ERROR",
                mensaje_seguro="import_id debe ser un UUID valido",
                reintentable=False,
                correlation_id=res.import_id,
                detalles={},
            )
        )
    for count in [res.accepted_count, res.rejected_count, res.matched_count, res.unmatched_count]:
        if not isinstance(count, int) or count < 0:
            return fallo(
                ErrorDominio(
                    codigo="VALIDATION_ERROR",
                    mensaje_seguro="Los conteos deben ser enteros mayores o iguales a 0",
                    reintentable=False,
                    correlation_id=res.import_id,
                    detalles={"conteo": str(count)},
                )
            )
    if res.matched_count + res.unmatched_count > res.accepted_count:
        return fallo(
            ErrorDominio(
                codigo="VALIDATION_ERROR",
                mensaje_seguro="matched_count + unmatched_count no puede superar accepted_count",
                reintentable=False,
                correlation_id=res.import_id,
                detalles={
                    "matched": res.matched_count,
                    "unmatched": res.unmatched_count,
                    "accepted": res.accepted_count,
                },
            )
        )
    return exito(res)


def validar_documento_vista(doc: DocumentoVistaV1) -> Resultado[DocumentoVistaV1]:
    if doc.schema_id not in _ALLOWED_DOC_SCHEMAS:
        return fallo(
            ErrorDominio(
                codigo="SCHEMA_UNSUPPORTED",
                mensaje_seguro=f"Esquema de documento no admitido: {doc.schema_id}",
                reintentable=False,
                correlation_id="",
                detalles={"schema_id": doc.schema_id},
            )
        )
    if not isinstance(doc.canonical_json_utf8, bytes):
        return fallo(
            ErrorDominio(
                codigo="VALIDATION_ERROR",
                mensaje_seguro="canonical_json_utf8 debe ser de tipo bytes",
                reintentable=False,
                correlation_id="",
                detalles={},
            )
        )
    computed_hash = hashlib.sha256(doc.canonical_json_utf8).hexdigest()
    if computed_hash.lower() != doc.document_hash.lower():
        return fallo(
            ErrorDominio(
                codigo="INTEGRITY_ERROR",
                mensaje_seguro="El hash del documento no coincide con el hash del JSON canonico",
                reintentable=False,
                correlation_id="",
                detalles={"document_hash": doc.document_hash, "computed_hash": computed_hash},
            )
        )
    return exito(doc)
