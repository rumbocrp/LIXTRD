"""Errores de dominio estructurados y codigos seguros (SPEC-001 §5.1)."""

from dataclasses import dataclass
from typing import Literal

CodigoErrorDominio = Literal[
    "VALIDATION_ERROR",
    "SCHEMA_UNSUPPORTED",
    "ENVIRONMENT_NOT_ALLOWED",
    "INSTRUMENT_NOT_ALLOWED",
    "SOURCE_NOT_DEMO",
    "CAPABILITY_DENIED",
    "DUPLICATE_EVENT",
    "OUT_OF_ORDER",
    "STALE_FEED",
    "GAPPED_FEED",
    "CLOCK_ROLLBACK",
    "STORAGE_UNAVAILABLE",
    "INTEGRITY_ERROR",
    "MODEL_UNAVAILABLE",
    "ECONOMIC_CONTRACT_INCOMPLETE",
    "RISK_LIMIT_HIT",
    "SIGNAL_EXPIRED",
    "IMPORT_INVALID",
    "RECONCILIATION_FAILED",
    "NOT_FOUND",
    "INTERNAL_ERROR",
]

CODIGOS_ERROR_PERMITIDOS: frozenset[str] = frozenset(
    {
        "VALIDATION_ERROR",
        "SCHEMA_UNSUPPORTED",
        "ENVIRONMENT_NOT_ALLOWED",
        "INSTRUMENT_NOT_ALLOWED",
        "SOURCE_NOT_DEMO",
        "CAPABILITY_DENIED",
        "DUPLICATE_EVENT",
        "OUT_OF_ORDER",
        "STALE_FEED",
        "GAPPED_FEED",
        "CLOCK_ROLLBACK",
        "STORAGE_UNAVAILABLE",
        "INTEGRITY_ERROR",
        "MODEL_UNAVAILABLE",
        "ECONOMIC_CONTRACT_INCOMPLETE",
        "RISK_LIMIT_HIT",
        "SIGNAL_EXPIRED",
        "IMPORT_INVALID",
        "RECONCILIATION_FAILED",
        "NOT_FOUND",
        "INTERNAL_ERROR",
    }
)


@dataclass(frozen=True)
class ErrorDominio:
    codigo: CodigoErrorDominio
    mensaje_seguro: str
    reintentable: bool
    correlation_id: str
    detalles: dict[str, str | int | bool | None]

    def __post_init__(self) -> None:
        if self.codigo not in CODIGOS_ERROR_PERMITIDOS:
            raise ValueError(f"Codigo de error invalido: {self.codigo}")
