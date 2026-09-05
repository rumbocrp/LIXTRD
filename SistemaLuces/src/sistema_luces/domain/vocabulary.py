"""Vocabulario cerrado y validadores numericos (SPEC-001 §4.1, §12.2, OPT-2)."""

import decimal
import math
from typing import Literal

from sistema_luces.domain.error import ErrorDominio
from sistema_luces.domain.result import Resultado, exito, fallo

Instrument = Literal["US500"]
Environment = Literal["NO_DATA", "SINTETICO", "REPLAY", "SHADOW", "DEMO_OBSERVADO", "BROKER_DEMO_OBSERVED"]
Source = Literal[
    "replay",
    "yahoo_finance",
    "ctrader_demo",
    "broker_demo_import",
    "journal_import",
    "simulator",
    "system",
    "operator",
]
Light = Literal["GREEN", "YELLOW", "RED"]
Direction = Literal["LONG", "SHORT", "MONITOR"]
DireccionCanonica = Literal["LARGO", "MONITORIZAR", "CORTO"]
EstadoUI = Literal["cargando", "vacio", "parcial", "error", "obsoleto", "conflicto", "exito"]
Actor = Literal["system", "operator", "import"]
DecisionWindow = Literal["S30", "S60"]
TimeWindow = DecisionWindow
ReconciliationStatus = Literal["PENDING", "MATCHED", "PARTIAL", "UNMATCHED", "INVALID"]

INSTRUMENTO_CANONICO: str = "US500"
INSTRUMENT_CANONICO: str = INSTRUMENTO_CANONICO
ENTORNOS_PERMITIDOS: frozenset[str] = frozenset(
    {"NO_DATA", "SINTETICO", "REPLAY", "SHADOW", "DEMO_OBSERVADO", "BROKER_DEMO_OBSERVED"}
)
VALID_ENVIRONMENTS: frozenset[str] = ENTORNOS_PERMITIDOS
FUENTES_PERMITIDAS: frozenset[str] = frozenset(
    {"replay", "yahoo_finance", "ctrader_demo", "broker_demo_import", "journal_import", "simulator", "system", "operator"}
)
LUCES_PERMITIDAS: frozenset[str] = frozenset({"GREEN", "YELLOW", "RED"})
DIRECCIONES_PERMITIDAS: frozenset[str] = frozenset({"LONG", "SHORT", "MONITOR"})
DIRECCIONES_CANONICAS_PERMITIDAS: frozenset[str] = frozenset({"LARGO", "MONITORIZAR", "CORTO"})
ESTADOS_UI_PERMITIDOS: frozenset[str] = frozenset(
    {"cargando", "vacio", "parcial", "error", "obsoleto", "conflicto", "exito"}
)
ACTORES_PERMITIDOS: frozenset[str] = frozenset({"system", "operator", "import"})
VENTANAS_DECISION_PERMITIDAS: frozenset[str] = frozenset({"S30", "S60"})
ESTADOS_CONCILIACION_PERMITIDOS: frozenset[str] = frozenset(
    {"PENDING", "MATCHED", "PARTIAL", "UNMATCHED", "INVALID"}
)

# Mapeos Canónicos de Vocabulario Español (RB-L001, RF-L017)
TEXTO_CANONICO_LUZ: dict[str, str] = {
    "GREEN": "LARGO",
    "YELLOW": "MONITORIZAR",
    "RED": "CORTO",
}
COLOR_CANONICO_LUZ: dict[str, str] = {
    "GREEN": "VERDE",
    "YELLOW": "AMARILLO",
    "RED": "ROJO",
}
TEXTO_CANONICO_DIRECCION: dict[str, str] = {
    "LONG": "LARGO",
    "SHORT": "CORTO",
    "MONITOR": "MONITORIZAR",
}
MAPEO_LUZ_A_DIRECCION_CANONICA: dict[str, DireccionCanonica] = {
    "GREEN": "LARGO",
    "YELLOW": "MONITORIZAR",
    "RED": "CORTO",
}
MAPEO_DIRECCION_A_CANONICA: dict[str, DireccionCanonica] = {
    "LONG": "LARGO",
    "SHORT": "CORTO",
    "MONITOR": "MONITORIZAR",
    "LARGO": "LARGO",
    "CORTO": "CORTO",
    "MONITORIZAR": "MONITORIZAR",
}
MAPEO_CANONICA_A_DIRECTION: dict[str, Direction] = {
    "LARGO": "LONG",
    "CORTO": "SHORT",
    "MONITORIZAR": "MONITOR",
}

_FORBIDDEN_ENV_NAMES: frozenset[str] = frozenset(
    {"".join(["L", "I", "V", "E"]), "REAL", "PROD", "PRODUCTION"}
)


def obtener_texto_luz(luz: str) -> str:
    """Retorna el significado canónico en español (LARGO, MONITORIZAR, CORTO)."""
    return TEXTO_CANONICO_LUZ.get(luz, "MONITORIZAR")


def obtener_color_luz(luz: str) -> str:
    """Retorna el nombre canónico del color en español (VERDE, AMARILLO, ROJO)."""
    return COLOR_CANONICO_LUZ.get(luz, "AMARILLO")


def obtener_texto_direccion(direccion: str) -> str:
    """Retorna el nombre canónico de la dirección en español (LARGO, MONITORIZAR, CORTO)."""
    return TEXTO_CANONICO_DIRECCION.get(direccion, "MONITORIZAR")


def parse_environment(raw: str, correlation_id: str = "") -> Resultado[Environment]:
    """Valida y canonicaliza el entorno, detectando intentos prohibidos."""
    if not isinstance(raw, str):
        return fallo(
            ErrorDominio(
                codigo="VALIDATION_ERROR",
                mensaje_seguro="El entorno debe ser una cadena de texto",
                reintentable=False,
                correlation_id=correlation_id,
                detalles={"tipo": type(raw).__name__},
            )
        )
    normalized = raw.strip()
    if normalized.upper() in _FORBIDDEN_ENV_NAMES:
        return fallo(
            ErrorDominio(
                codigo="ENVIRONMENT_NOT_ALLOWED",
                mensaje_seguro="El entorno solicitado no esta permitido en esta arquitectura",
                reintentable=False,
                correlation_id=correlation_id,
                detalles={"entorno_solicitado": normalized},
            )
        )
    if normalized in ENTORNOS_PERMITIDOS:
        return exito(normalized)  # type: ignore[return-value]
    return fallo(
        ErrorDominio(
            codigo="VALIDATION_ERROR",
            mensaje_seguro="Entorno no reconocido",
            reintentable=False,
            correlation_id=correlation_id,
            detalles={"entorno": raw},
        )
    )


def parse_estado_ui(raw: str, correlation_id: str = "") -> Resultado[EstadoUI]:
    """Valida que el estado de UI pertenezca a los 7 estados canónicos."""
    if isinstance(raw, str) and raw in ESTADOS_UI_PERMITIDOS:
        return exito(raw)  # type: ignore[return-value]
    return fallo(
        ErrorDominio(
            codigo="VALIDATION_ERROR",
            mensaje_seguro="Estado de interfaz no reconocido",
            reintentable=False,
            correlation_id=correlation_id,
            detalles={"estado_ui": str(raw)},
        )
    )


def parse_instrument(raw: str, correlation_id: str = "") -> Resultado[Instrument]:
    """Valida que el instrumento sea exclusivamente US500."""
    if not isinstance(raw, str) or raw != INSTRUMENTO_CANONICO:
        return fallo(
            ErrorDominio(
                codigo="INSTRUMENT_NOT_ALLOWED",
                mensaje_seguro=f"Solo se admite el instrumento canonico {INSTRUMENTO_CANONICO}",
                reintentable=False,
                correlation_id=correlation_id,
                detalles={"instrumento": str(raw)},
            )
        )
    return exito("US500")


def parse_light(raw: str, correlation_id: str = "") -> Resultado[Light]:
    if isinstance(raw, str) and raw in LUCES_PERMITIDAS:
        return exito(raw)  # type: ignore[return-value]
    return fallo(
        ErrorDominio(
            codigo="VALIDATION_ERROR",
            mensaje_seguro="Luz invalida",
            reintentable=False,
            correlation_id=correlation_id,
            detalles={"luz": str(raw)},
        )
    )


def parse_direction(raw: str, correlation_id: str = "") -> Resultado[Direction]:
    if isinstance(raw, str) and raw in DIRECCIONES_PERMITIDAS:
        return exito(raw)  # type: ignore[return-value]
    return fallo(
        ErrorDominio(
            codigo="VALIDATION_ERROR",
            mensaje_seguro="Direccion invalida",
            reintentable=False,
            correlation_id=correlation_id,
            detalles={"direccion": str(raw)},
        )
    )


def parse_direccion_canonica(raw: str, correlation_id: str = "") -> Resultado[DireccionCanonica]:
    if not isinstance(raw, str):
        return fallo(
            ErrorDominio(
                codigo="VALIDATION_ERROR",
                mensaje_seguro="La direccion canonica debe ser una cadena de texto",
                reintentable=False,
                correlation_id=correlation_id,
                detalles={"tipo": type(raw).__name__},
            )
        )
    normalized = raw.strip().upper()
    if normalized in DIRECCIONES_CANONICAS_PERMITIDAS:
        return exito(normalized)  # type: ignore[return-value]
    if normalized in MAPEO_DIRECCION_A_CANONICA:
        return exito(MAPEO_DIRECCION_A_CANONICA[normalized])  # type: ignore[return-value]
    return fallo(
        ErrorDominio(
            codigo="VALIDATION_ERROR",
            mensaje_seguro="Direccion canonica no reconocida",
            reintentable=False,
            correlation_id=correlation_id,
            detalles={"direccion": str(raw)},
        )
    )


def parse_source(raw: str, correlation_id: str = "") -> Resultado[Source]:
    if isinstance(raw, str) and raw in FUENTES_PERMITIDAS:
        return exito(raw)  # type: ignore[return-value]
    return fallo(
        ErrorDominio(
            codigo="VALIDATION_ERROR",
            mensaje_seguro="Fuente invalida",
            reintentable=False,
            correlation_id=correlation_id,
            detalles={"fuente": str(raw)},
        )
    )


def parse_actor(raw: str, correlation_id: str = "") -> Resultado[Actor]:
    if isinstance(raw, str) and raw in ACTORES_PERMITIDOS:
        return exito(raw)  # type: ignore[return-value]
    return fallo(
        ErrorDominio(
            codigo="VALIDATION_ERROR",
            mensaje_seguro="Actor invalido",
            reintentable=False,
            correlation_id=correlation_id,
            detalles={"actor": str(raw)},
        )
    )


def parse_decision_window(raw: str, correlation_id: str = "") -> Resultado[DecisionWindow]:
    if isinstance(raw, str) and raw in VENTANAS_DECISION_PERMITIDAS:
        return exito(raw)  # type: ignore[return-value]
    return fallo(
        ErrorDominio(
            codigo="VALIDATION_ERROR",
            mensaje_seguro="Ventana de decision invalida",
            reintentable=False,
            correlation_id=correlation_id,
            detalles={"ventana": str(raw)},
        )
    )


def parse_reconciliation_status(raw: str, correlation_id: str = "") -> Resultado[ReconciliationStatus]:
    if isinstance(raw, str) and raw in ESTADOS_CONCILIACION_PERMITIDOS:
        return exito(raw)  # type: ignore[return-value]
    return fallo(
        ErrorDominio(
            codigo="VALIDATION_ERROR",
            mensaje_seguro="Estado de conciliacion invalido",
            reintentable=False,
            correlation_id=correlation_id,
            detalles={"estado": str(raw)},
        )
    )


# Validadores numericos OPT-2
def _is_finite_number(value: object) -> bool:
    if isinstance(value, (int, decimal.Decimal)):
        return True
    if isinstance(value, float):
        return not (math.isnan(value) or math.isinf(value))
    return False


def validate_price_scaled(value: int, correlation_id: str = "") -> Resultado[int]:
    """Precio entero escalado > 0."""
    if not isinstance(value, int) or not _is_finite_number(value) or value <= 0:
        return fallo(
            ErrorDominio(
                codigo="VALIDATION_ERROR",
                mensaje_seguro="El precio escalado debe ser un entero finito mayor a 0",
                reintentable=False,
                correlation_id=correlation_id,
                detalles={"valor": str(value)},
            )
        )
    return exito(value)


def validate_quantity_scaled(value: int, correlation_id: str = "") -> Resultado[int]:
    """Cantidad entera escalada > 0."""
    if not isinstance(value, int) or not _is_finite_number(value) or value <= 0:
        return fallo(
            ErrorDominio(
                codigo="VALIDATION_ERROR",
                mensaje_seguro="La cantidad escalada debe ser un entero finito mayor a 0",
                reintentable=False,
                correlation_id=correlation_id,
                detalles={"valor": str(value)},
            )
        )
    return exito(value)


def validate_scale_factor(value: int, correlation_id: str = "") -> Resultado[int]:
    """Factor de escala > 0."""
    if not isinstance(value, int) or not _is_finite_number(value) or value <= 0:
        return fallo(
            ErrorDominio(
                codigo="VALIDATION_ERROR",
                mensaje_seguro="El factor de escala debe ser un entero finito mayor a 0",
                reintentable=False,
                correlation_id=correlation_id,
                detalles={"valor": str(value)},
            )
        )
    return exito(value)


def validate_cost_scaled(value: int, correlation_id: str = "") -> Resultado[int]:
    """Costo entero escalado >= 0."""
    if not isinstance(value, int) or not _is_finite_number(value) or value < 0:
        return fallo(
            ErrorDominio(
                codigo="VALIDATION_ERROR",
                mensaje_seguro="El costo escalado debe ser un entero finito mayor o igual a 0",
                reintentable=False,
                correlation_id=correlation_id,
                detalles={"valor": str(value)},
            )
        )
    return exito(value)


def validate_probability_scaled(value: int, correlation_id: str = "") -> Resultado[int]:
    """Probabilidad o ratio escalado en 0..1_000_000."""
    if not isinstance(value, int) or not _is_finite_number(value) or value < 0 or value > 1_000_000:
        return fallo(
            ErrorDominio(
                codigo="VALIDATION_ERROR",
                mensaje_seguro="La probabilidad o ratio escalado debe estar entre 0 y 1_000_000",
                reintentable=False,
                correlation_id=correlation_id,
                detalles={"valor": str(value)},
            )
        )
    return exito(value)
