"""Motor de reconciliación de simulaciones vs ejecuciones demo (SPEC-001 §6.6, CA-19)."""

from dataclasses import dataclass
from datetime import datetime, timedelta

from sistema_luces.domain.simulation import SimulacionV1
from sistema_luces.imports.demo import EjecucionDemoObservada


@dataclass(frozen=True)
class InformeReconciliacion:
    matched_count: int
    unmatched_count: int
    simulaciones_reconciliadas: list[SimulacionV1]
    ejecuciones_no_conciliadas: list[EjecucionDemoObservada]


class ReconciliadorDemo:
    """Cruza operaciones paper simuladas con ejecuciones de broker observadas."""

    def __init__(
        self,
        tolerancia_tiempo_segundos: int = 30,
        tolerancia_precio_pts: int = 500,
    ) -> None:
        self.tolerancia_tiempo = timedelta(seconds=tolerancia_tiempo_segundos)
        self.tolerancia_precio = tolerancia_precio_pts

    def reconciliar(
        self,
        simulaciones: list[SimulacionV1],
        ejecuciones_demo: list[EjecucionDemoObservada],
    ) -> InformeReconciliacion:
        matched_sims: list[SimulacionV1] = []
        ejecuciones_usadas: set[str] = set()

        for sim in simulaciones:
            matched_exec: EjecucionDemoObservada | None = None

            for demo in ejecuciones_demo:
                if demo.execution_id in ejecuciones_usadas:
                    continue

                # 1. Misma dirección y símbolo
                if demo.side != sim.direction:
                    continue

                # 2. Tolerancia temporal en apertura
                if sim.opened_at_utc is not None:
                    delta_t = abs(sim.opened_at_utc - demo.entry_time_utc)
                    if delta_t > self.tolerancia_tiempo:
                        continue

                # 3. Tolerancia de precio
                if sim.planned_entry is not None:
                    delta_p = abs(sim.planned_entry - demo.entry_price)
                    if delta_p > self.tolerancia_precio:
                        continue

                matched_exec = demo
                break

            if matched_exec is not None:
                ejecuciones_usadas.add(matched_exec.execution_id)
                sim_recon = SimulacionV1(
                    simulation_id=sim.simulation_id,
                    signal_id=sim.signal_id,
                    environment=sim.environment,
                    demo_account_hash=matched_exec.account_hash,
                    status=sim.status,
                    proposed_at_utc=sim.proposed_at_utc,
                    opened_at_utc=sim.opened_at_utc,
                    closed_at_utc=sim.closed_at_utc,
                    horizon_end_utc=sim.horizon_end_utc,
                    direction=sim.direction,
                    planned_entry=sim.planned_entry,
                    stop=sim.stop,
                    target=sim.target,
                    risk_profile_version=sim.risk_profile_version,
                    instrument_profile_version=sim.instrument_profile_version,
                    requested_quantity_simulated=sim.requested_quantity_simulated,
                    effective_quantity_simulated=sim.effective_quantity_simulated,
                    quantity_scale=sim.quantity_scale,
                    fill_entry=sim.fill_entry,
                    fill_exit=sim.fill_exit,
                    fill_source="simulator",
                    source_execution_ids=(matched_exec.execution_id,),
                    spread_cost=sim.spread_cost,
                    slippage_cost=abs((sim.fill_entry or 0) - matched_exec.entry_price),
                    commission_cost=sim.commission_cost,
                    carry_cost=sim.carry_cost,
                    money_scale=sim.money_scale,
                    currency=sim.currency,
                    exit_reason=sim.exit_reason,
                    gross_pnl=sim.gross_pnl,
                    net_pnl=sim.net_pnl,
                    realized_r=sim.realized_r,
                    mfe=sim.mfe,
                    mae=sim.mae,
                    reconciliation_status="MATCHED",
                    reconciliation_reason_codes=("DEMO_EXECUTION_MATCHED",),
                    market_event_cutoff=sim.market_event_cutoff,
                    cost_profile_version=sim.cost_profile_version,
                    correlation_id=sim.correlation_id,
                    causation_id=sim.causation_id,
                    schema_version=1,
                )
                matched_sims.append(sim_recon)
            else:
                sim_unmatched = SimulacionV1(
                    simulation_id=sim.simulation_id,
                    signal_id=sim.signal_id,
                    environment=sim.environment,
                    demo_account_hash=sim.demo_account_hash,
                    status=sim.status,
                    proposed_at_utc=sim.proposed_at_utc,
                    opened_at_utc=sim.opened_at_utc,
                    closed_at_utc=sim.closed_at_utc,
                    horizon_end_utc=sim.horizon_end_utc,
                    direction=sim.direction,
                    planned_entry=sim.planned_entry,
                    stop=sim.stop,
                    target=sim.target,
                    risk_profile_version=sim.risk_profile_version,
                    instrument_profile_version=sim.instrument_profile_version,
                    requested_quantity_simulated=sim.requested_quantity_simulated,
                    effective_quantity_simulated=sim.effective_quantity_simulated,
                    quantity_scale=sim.quantity_scale,
                    fill_entry=sim.fill_entry,
                    fill_exit=sim.fill_exit,
                    fill_source=sim.fill_source,
                    source_execution_ids=sim.source_execution_ids,
                    spread_cost=sim.spread_cost,
                    slippage_cost=sim.slippage_cost,
                    commission_cost=sim.commission_cost,
                    carry_cost=sim.carry_cost,
                    money_scale=sim.money_scale,
                    currency=sim.currency,
                    exit_reason=sim.exit_reason,
                    gross_pnl=sim.gross_pnl,
                    net_pnl=sim.net_pnl,
                    realized_r=sim.realized_r,
                    mfe=sim.mfe,
                    mae=sim.mae,
                    reconciliation_status="UNMATCHED",
                    reconciliation_reason_codes=("NO_DEMO_MATCH_FOUND",),
                    market_event_cutoff=sim.market_event_cutoff,
                    cost_profile_version=sim.cost_profile_version,
                    correlation_id=sim.correlation_id,
                    causation_id=sim.causation_id,
                    schema_version=1,
                )
                matched_sims.append(sim_unmatched)

        # Identificar ejecuciones demo no conciliadas
        unmatched_demos: list[EjecucionDemoObservada] = [
            demo for demo in ejecuciones_demo if demo.execution_id not in ejecuciones_usadas
        ]

        matched_count = len([s for s in matched_sims if s.reconciliation_status == "MATCHED"])
        unmatched_count = len(unmatched_demos)

        return InformeReconciliacion(
            matched_count=matched_count,
            unmatched_count=unmatched_count,
            simulaciones_reconciliadas=matched_sims,
            ejecuciones_no_conciliadas=unmatched_demos,
        )
