"""Snapshot metrico y catalogos de observabilidad (SPEC-001 §6.7, CA-22, DM-6)."""

from dataclasses import dataclass
from datetime import datetime
import re
from typing import Literal

from sistema_luces.domain.error import ErrorDominio
from sistema_luces.domain.result import Resultado, exito, fallo
from sistema_luces.domain.vocabulary import (
    Environment,
    Source,
    parse_environment,
    parse_instrument,
    parse_source,
)

_UUID_REGEX = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE)

PLANOS_METRICOS_PERMITIDOS: frozenset[str] = frozenset(
    {
        "FEED",
        "SIGNALS",
        "PREDICTIVE",
        "ROBUSTNESS",
        "DEMO",
        "EXECUTION",
        "SECURITY",
        "TRACEABILITY",
    }
)

PlanoMetrico = Literal[
    "FEED", "SIGNALS", "PREDICTIVE", "ROBUSTNESS", "DEMO", "EXECUTION", "SECURITY", "TRACEABILITY"
]


@dataclass(frozen=True)
class MetricValueV1:
    value_int: int | None = None
    value_ratio_scaled: int | None = None
    reason_code: str | None = None


@dataclass(frozen=True)
class SnapshotMetricoV1:
    metric_snapshot_id: str
    metric_name: str
    metric_plane: Literal[
        "FEED", "SIGNALS", "PREDICTIVE", "ROBUSTNESS", "DEMO", "EXECUTION", "SECURITY", "TRACEABILITY"
    ]
    range_start_utc: datetime
    range_end_utc: datetime
    ny_session_date: str
    source: Source
    environment: Environment
    instrument: Literal["US500"]
    strategy_version: str | None
    model_version: str | None
    policy_version: str
    raw_count: int
    effective_sample_size: int
    value_int: int | None
    value_ratio_scaled: int | None
    histogram_int: tuple[int, ...] | None
    unit: str
    scale: int
    dimensions: dict[str, str | int | bool | None]
    input_event_cutoff: datetime
    dataset_hash: str | None
    code_hash: str
    computed_at_utc: datetime
    schema_version: Literal[1] = 1


def validar_snapshot_metrico(snap: SnapshotMetricoV1) -> Resultado[SnapshotMetricoV1]:
    if not _UUID_REGEX.match(snap.metric_snapshot_id):
        return fallo(
            ErrorDominio(
                codigo="VALIDATION_ERROR",
                mensaje_seguro="metric_snapshot_id debe ser un UUID valido",
                reintentable=False,
                correlation_id="",
                detalles={"metric_snapshot_id": snap.metric_snapshot_id},
            )
        )
    if snap.metric_plane not in PLANOS_METRICOS_PERMITIDOS:
        return fallo(
            ErrorDominio(
                codigo="VALIDATION_ERROR",
                mensaje_seguro=f"Plano metrico no permitido: {snap.metric_plane}",
                reintentable=False,
                correlation_id="",
                detalles={"metric_plane": snap.metric_plane},
            )
        )
    env_res = parse_environment(snap.environment)
    if not env_res.exito:
        return fallo(env_res.error)

    src_res = parse_source(snap.source)
    if not src_res.exito:
        return fallo(src_res.error)

    inst_res = parse_instrument(snap.instrument)
    if not inst_res.exito:
        return fallo(inst_res.error)

    if snap.raw_count < 0 or snap.effective_sample_size < 0:
        return fallo(
            ErrorDominio(
                codigo="VALIDATION_ERROR",
                mensaje_seguro="Los conteos metricos deben ser mayores o iguales a 0",
                reintentable=False,
                correlation_id="",
                detalles={"raw_count": snap.raw_count, "effective_sample_size": snap.effective_sample_size},
            )
        )

    return exito(snap)
