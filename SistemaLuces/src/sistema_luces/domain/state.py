"""Maquina de estados y transiciones permitidas (SPEC-001 §6.4, CA-8)."""

from dataclasses import dataclass
from datetime import datetime
import re
from typing import Literal

from sistema_luces.domain.error import ErrorDominio
from sistema_luces.domain.result import Resultado, exito, fallo
from sistema_luces.domain.vocabulary import Actor, parse_actor

_UUID_REGEX = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE)

EstadoFeed = Literal["INITIALIZING", "HEALTHY", "STALE", "GAPPED", "RECONNECTING", "STOPPED"]
EstadoLuces = Literal["YELLOW", "GREEN", "RED"]
EstadoSimulacion = Literal["PROPOSED", "OPEN_SIMULATED", "CLOSED_SIMULATED", "REJECTED", "CANCELLED"]
EstadoSenal = Literal["CANDIDATE", "EMITTED", "ACTIVE", "EXPIRED", "INVALIDATED", "MATURE", "INVALID"]
EstadoEtiqueta = Literal["PENDING", "MATURE", "INVALID"]

TRANSICIONES_PERMITIDAS: dict[str, dict[str | None, frozenset[str]]] = {
    "feed": {
        None: frozenset({"INITIALIZING"}),
        "INITIALIZING": frozenset({"HEALTHY", "STALE", "GAPPED", "STOPPED"}),
        "HEALTHY": frozenset({"STALE", "GAPPED", "RECONNECTING", "STOPPED"}),
        "STALE": frozenset({"HEALTHY", "GAPPED", "RECONNECTING", "STOPPED"}),
        "GAPPED": frozenset({"RECONNECTING", "STOPPED"}),
        "RECONNECTING": frozenset({"HEALTHY", "STALE", "GAPPED", "STOPPED"}),
        "STOPPED": frozenset({"INITIALIZING"}),
    },
    "signal": {
        None: frozenset({"CANDIDATE"}),
        "CANDIDATE": frozenset({"EMITTED", "INVALIDATED"}),
        "EMITTED": frozenset({"ACTIVE", "EXPIRED", "INVALIDATED"}),
        "ACTIVE": frozenset({"EXPIRED", "INVALIDATED"}),
        "EXPIRED": frozenset({"MATURE", "INVALID"}),
        "INVALIDATED": frozenset({"INVALID"}),
    },
    "light": {
        None: frozenset({"YELLOW"}),
        "YELLOW": frozenset({"YELLOW", "GREEN", "RED"}),
        "GREEN": frozenset({"GREEN", "YELLOW"}),
        "RED": frozenset({"RED", "YELLOW"}),
    },
    "simulation": {
        None: frozenset({"PROPOSED"}),
        "PROPOSED": frozenset({"OPEN_SIMULATED", "REJECTED", "CANCELLED"}),
        "OPEN_SIMULATED": frozenset({"CLOSED_SIMULATED"}),
    },
    "label": {
        None: frozenset({"PENDING"}),
        "PENDING": frozenset({"MATURE", "INVALID"}),
    },
}


def es_transicion_valida(aggregate_type: str, previous_state: str | None, next_state: str) -> bool:
    """Comprueba si una transicion es admisible segun las maquinas de estado de §6.4."""
    if aggregate_type not in TRANSICIONES_PERMITIDAS:
        return False
    maquina = TRANSICIONES_PERMITIDAS[aggregate_type]
    destinos_permitidos = maquina.get(previous_state, frozenset())
    return next_state in destinos_permitidos


@dataclass(frozen=True)
class TransicionEstadoV1:
    transition_id: str
    aggregate_type: Literal["feed", "signal", "light", "simulation", "label"]
    aggregate_id: str
    previous_state: str | None
    next_state: str
    actor: Actor
    occurred_at_utc: datetime
    causation_id: str | None
    correlation_id: str
    policy_version: str
    reason_codes: tuple[str, ...]
    safety_forced: bool


def validar_transicion_estado(trans: TransicionEstadoV1) -> Resultado[TransicionEstadoV1]:
    if not _UUID_REGEX.match(trans.transition_id):
        return fallo(
            ErrorDominio(
                codigo="VALIDATION_ERROR",
                mensaje_seguro="transition_id debe ser un UUID valido",
                reintentable=False,
                correlation_id=trans.correlation_id,
                detalles={"transition_id": trans.transition_id},
            )
        )
    if trans.aggregate_type not in TRANSICIONES_PERMITIDAS:
        return fallo(
            ErrorDominio(
                codigo="VALIDATION_ERROR",
                mensaje_seguro=f"Tipo de agregado desconocido: {trans.aggregate_type}",
                reintentable=False,
                correlation_id=trans.correlation_id,
                detalles={"aggregate_type": trans.aggregate_type},
            )
        )
    actor_res = parse_actor(trans.actor, trans.correlation_id)
    if not actor_res.exito:
        return fallo(actor_res.error)

    if not es_transicion_valida(trans.aggregate_type, trans.previous_state, trans.next_state):
        return fallo(
            ErrorDominio(
                codigo="VALIDATION_ERROR",
                mensaje_seguro=(
                    f"Transicion no permitida para {trans.aggregate_type}: "
                    f"{trans.previous_state} -> {trans.next_state}"
                ),
                reintentable=False,
                correlation_id=trans.correlation_id,
                detalles={
                    "aggregate_type": trans.aggregate_type,
                    "previous_state": trans.previous_state,
                    "next_state": trans.next_state,
                },
            )
        )

    return exito(trans)
