"""Documento de Simulacion interna paper (SPEC-001 §6.6, CA-13, CA-14, CA-15)."""

from dataclasses import dataclass
from datetime import datetime
import re
from typing import Literal

from sistema_luces.domain.error import ErrorDominio
from sistema_luces.domain.result import Resultado, exito, fallo
from sistema_luces.domain.vocabulary import (
    Direction,
    Environment,
    ReconciliationStatus,
    parse_direction,
    parse_environment,
    parse_reconciliation_status,
    validate_cost_scaled,
    validate_price_scaled,
    validate_quantity_scaled,
    validate_scale_factor,
)

_UUID_REGEX = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE)

ESTADOS_SIMULACION_PERMITIDOS = frozenset({"PROPOSED", "OPEN_SIMULATED", "CLOSED_SIMULATED", "REJECTED", "CANCELLED"})
CAUSAS_SALIDA_PERMITIDAS = frozenset({"stop", "target", "time", "manual_demo", "risk_limit", "invalid_data"})


@dataclass(frozen=True)
class SimulacionV1:
    simulation_id: str
    signal_id: str
    environment: Environment
    demo_account_hash: str | None
    status: Literal["PROPOSED", "OPEN_SIMULATED", "CLOSED_SIMULATED", "REJECTED", "CANCELLED"]
    proposed_at_utc: datetime
    opened_at_utc: datetime | None
    closed_at_utc: datetime | None
    horizon_end_utc: datetime | None
    direction: Direction
    planned_entry: int
    stop: int
    target: int
    risk_profile_version: str
    instrument_profile_version: str
    requested_quantity_simulated: int
    effective_quantity_simulated: int
    quantity_scale: int
    fill_entry: int | None
    fill_exit: int | None
    fill_source: Literal["simulator", "broker_demo_import"]
    source_execution_ids: tuple[str, ...]
    spread_cost: int | None
    slippage_cost: int | None
    commission_cost: int | None
    carry_cost: int | None
    money_scale: int
    currency: str
    exit_reason: str | None
    gross_pnl: int | None
    net_pnl: int | None
    realized_r: int | None
    mfe: int | None
    mae: int | None
    reconciliation_status: ReconciliationStatus
    reconciliation_reason_codes: tuple[str, ...]
    market_event_cutoff: datetime
    cost_profile_version: str | None
    correlation_id: str
    causation_id: str | None
    schema_version: Literal[1] = 1


def validar_simulacion(sim: SimulacionV1) -> Resultado[SimulacionV1]:
    if not _UUID_REGEX.match(sim.simulation_id) or not _UUID_REGEX.match(sim.signal_id):
        return fallo(
            ErrorDominio(
                codigo="VALIDATION_ERROR",
                mensaje_seguro="simulation_id y signal_id deben ser UUIDs validos",
                reintentable=False,
                correlation_id=sim.correlation_id,
                detalles={},
            )
        )
    env_res = parse_environment(sim.environment, sim.correlation_id)
    if not env_res.exito:
        return fallo(env_res.error)

    dir_res = parse_direction(sim.direction, sim.correlation_id)
    if not dir_res.exito:
        return fallo(dir_res.error)

    if sim.status not in ESTADOS_SIMULACION_PERMITIDOS:
        return fallo(
            ErrorDominio(
                codigo="VALIDATION_ERROR",
                mensaje_seguro=f"Estado de simulacion invalido: {sim.status}",
                reintentable=False,
                correlation_id=sim.correlation_id,
                detalles={"status": sim.status},
            )
        )

    recon_res = parse_reconciliation_status(sim.reconciliation_status, sim.correlation_id)
    if not recon_res.exito:
        return fallo(recon_res.error)

    # Validar precios y escalas
    for name, val in [("planned_entry", sim.planned_entry), ("stop", sim.stop), ("target", sim.target)]:
        res = validate_price_scaled(val, sim.correlation_id)
        if not res.exito:
            return fallo(res.error)

    res_qty = validate_quantity_scaled(sim.requested_quantity_simulated, sim.correlation_id)
    if not res_qty.exito:
        return fallo(res_qty.error)

    res_qscale = validate_scale_factor(sim.quantity_scale, sim.correlation_id)
    if not res_qscale.exito:
        return fallo(res_qscale.error)

    res_mscale = validate_scale_factor(sim.money_scale, sim.correlation_id)
    if not res_mscale.exito:
        return fallo(res_mscale.error)

    # Invariante de barreras de triple barrera:
    # LONG: stop < planned_entry < target
    # SHORT: target < planned_entry < stop
    if sim.direction == "LONG":
        if not (sim.stop < sim.planned_entry < sim.target):
            return fallo(
                ErrorDominio(
                    codigo="VALIDATION_ERROR",
                    mensaje_seguro="Para LONG se exige stop < planned_entry < target",
                    reintentable=False,
                    correlation_id=sim.correlation_id,
                    detalles={"stop": sim.stop, "entry": sim.planned_entry, "target": sim.target},
                )
            )
    elif sim.direction == "SHORT":
        if not (sim.target < sim.planned_entry < sim.stop):
            return fallo(
                ErrorDominio(
                    codigo="VALIDATION_ERROR",
                    mensaje_seguro="Para SHORT se exige target < planned_entry < stop",
                    reintentable=False,
                    correlation_id=sim.correlation_id,
                    detalles={"target": sim.target, "entry": sim.planned_entry, "stop": sim.stop},
                )
            )

    # Validar causa de salida si existe
    if sim.exit_reason is not None and sim.exit_reason not in CAUSAS_SALIDA_PERMITIDAS:
        return fallo(
            ErrorDominio(
                codigo="VALIDATION_ERROR",
                mensaje_seguro=f"Causa de salida invalida: {sim.exit_reason}",
                reintentable=False,
                correlation_id=sim.correlation_id,
                detalles={"exit_reason": sim.exit_reason},
            )
        )

    # Validar costos si estan presentes
    for c in [sim.spread_cost, sim.slippage_cost, sim.commission_cost, sim.carry_cost]:
        if c is not None:
            res_c = validate_cost_scaled(c, sim.correlation_id)
            if not res_c.exito:
                return fallo(res_c.error)

    return exito(sim)
