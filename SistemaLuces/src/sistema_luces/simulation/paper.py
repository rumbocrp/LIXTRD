"""Simulador Paper interno sin capacidades de ejecución externa (SPEC-001 §5.3, §6.6, CA-11, CA-12, CA-15)."""

from datetime import datetime, timedelta
import uuid

from sistema_luces.domain.error import ErrorDominio
from sistema_luces.domain.event import QuoteTickPayloadV1
from sistema_luces.domain.manifest import CostProfileV1
from sistema_luces.domain.result import Resultado, exito, fallo
from sistema_luces.domain.signal import SenalV1
from sistema_luces.domain.simulation import SimulacionV1, validar_simulacion
from sistema_luces.risk.engine import MotorRiesgo
from sistema_luces.simulation.lifecycle import EvaluadorTripleBarrera


class SimuladorPapel:
    """Gestiona el ciclo de vida de operaciones simuladas estrictamente en memoria/base local."""

    def __init__(
        self,
        motor_riesgo: MotorRiesgo | None = None,
        cost_profile: CostProfileV1 | None = None,
        stop_points: int = 500,
        target_points: int = 2000,
        horizon_minutes: int = 5,
    ) -> None:
        self.motor_riesgo = motor_riesgo or MotorRiesgo()
        self.cost_profile = cost_profile or CostProfileV1(
            profile_version="cost-us500-v1",
            spread_points_base=40,
            spread_points_adverse=60,
            spread_points_stress=100,
            slippage_points_base=0,
            slippage_points_adverse=10,
            slippage_points_stress=30,
            commission_per_lot_usd_cents=0,
            carry_per_night_usd_cents=0,
            latency_ms_base=10,
            latency_ms_stress=50,
        )
        self.stop_points = stop_points
        self.target_points = target_points
        self.horizon_minutes = horizon_minutes
        self.evaluador = EvaluadorTripleBarrera(
            stop_loss_points=stop_points,
            take_profit_points=target_points,
        )
        self._simulaciones_activas: dict[str, SimulacionV1] = {}

    def proponer_y_abrir(
        self,
        senal: SenalV1,
        current_bid: int,
        current_ask: int,
        now_utc: datetime,
        quantity: int = 100,
    ) -> Resultado[SimulacionV1]:
        """Procesa una señal, valida riesgo y abre simulación paper."""
        # 1. Invariante CA-11: Vencimiento de señal (30s)
        if now_utc > senal.valid_until_utc:
            return fallo(
                ErrorDominio(
                    codigo="SIGNAL_EXPIRED",
                    mensaje_seguro="La señal ha vencido su periodo de vigencia de 30s",
                    reintentable=False,
                    correlation_id=senal.correlation_id,
                    detalles={
                        "valid_until_utc": senal.valid_until_utc.isoformat(),
                        "now_utc": now_utc.isoformat(),
                    },
                )
            )

        # 2. Invariante CA-12: Luz amarilla o dirección MONITOR no producen órdenes simuladas
        if senal.light == "YELLOW" or senal.direction == "MONITOR":
            return fallo(
                ErrorDominio(
                    codigo="VALIDATION_ERROR",
                    mensaje_seguro="Señal con luz YELLOW / MONITOR no puede proponer apertura simulada",
                    reintentable=False,
                    correlation_id=senal.correlation_id,
                    detalles={"light": senal.light, "direction": senal.direction},
                )
            )

        # 3. Determinación de precios ejecutables
        sim_id = str(uuid.uuid4())
        horizon_end = now_utc + timedelta(minutes=self.horizon_minutes)

        if senal.direction == "LONG":
            planned_entry = current_ask
            fill_entry = current_ask
            stop = planned_entry - self.stop_points
            target = planned_entry + self.target_points
        elif senal.direction == "SHORT":
            planned_entry = current_bid
            fill_entry = current_bid
            stop = planned_entry + self.stop_points
            target = planned_entry - self.target_points
        else:
            return fallo(
                ErrorDominio(
                    codigo="VALIDATION_ERROR",
                    mensaje_seguro=f"Dirección inválida para simulación: {senal.direction}",
                    reintentable=False,
                    correlation_id=senal.correlation_id,
                    detalles={"direction": senal.direction},
                )
            )

        sim_propuesta = SimulacionV1(
            simulation_id=sim_id,
            signal_id=senal.signal_id,
            environment=senal.environment,
            demo_account_hash=None,
            status="PROPOSED",
            proposed_at_utc=now_utc,
            opened_at_utc=None,
            closed_at_utc=None,
            horizon_end_utc=horizon_end,
            direction=senal.direction,
            planned_entry=planned_entry,
            stop=stop,
            target=target,
            risk_profile_version=self.motor_riesgo.profile.profile_version,
            instrument_profile_version="us500-v1",
            requested_quantity_simulated=quantity,
            effective_quantity_simulated=quantity,
            quantity_scale=100,
            fill_entry=None,
            fill_exit=None,
            fill_source="simulator",
            source_execution_ids=(),
            spread_cost=self.cost_profile.spread_points_base,
            slippage_cost=self.cost_profile.slippage_points_base,
            commission_cost=self.cost_profile.commission_per_lot_usd_cents,
            carry_cost=self.cost_profile.carry_per_night_usd_cents,
            money_scale=100,
            currency="USD",
            exit_reason=None,
            gross_pnl=None,
            net_pnl=None,
            realized_r=None,
            mfe=None,
            mae=None,
            reconciliation_status="PENDING",
            reconciliation_reason_codes=(),
            market_event_cutoff=senal.market_event_cutoff,
            cost_profile_version=self.cost_profile.profile_version,
            correlation_id=senal.correlation_id,
            causation_id=senal.signal_id,
            schema_version=1,
        )

        # 4. Evaluación de Riesgo
        res_riesgo = self.motor_riesgo.evaluar_propuesta(sim_propuesta, now_utc)
        if not res_riesgo.exito:
            return fallo(res_riesgo.error)

        # 5. Transición a OPEN_SIMULATED
        sim_abierta = SimulacionV1(
            simulation_id=sim_propuesta.simulation_id,
            signal_id=sim_propuesta.signal_id,
            environment=sim_propuesta.environment,
            demo_account_hash=sim_propuesta.demo_account_hash,
            status="OPEN_SIMULATED",
            proposed_at_utc=sim_propuesta.proposed_at_utc,
            opened_at_utc=now_utc,
            closed_at_utc=None,
            horizon_end_utc=sim_propuesta.horizon_end_utc,
            direction=sim_propuesta.direction,
            planned_entry=sim_propuesta.planned_entry,
            stop=sim_propuesta.stop,
            target=sim_propuesta.target,
            risk_profile_version=sim_propuesta.risk_profile_version,
            instrument_profile_version=sim_propuesta.instrument_profile_version,
            requested_quantity_simulated=sim_propuesta.requested_quantity_simulated,
            effective_quantity_simulated=sim_propuesta.effective_quantity_simulated,
            quantity_scale=sim_propuesta.quantity_scale,
            fill_entry=fill_entry,
            fill_exit=None,
            fill_source="simulator",
            source_execution_ids=sim_propuesta.source_execution_ids,
            spread_cost=sim_propuesta.spread_cost,
            slippage_cost=sim_propuesta.slippage_cost,
            commission_cost=sim_propuesta.commission_cost,
            carry_cost=sim_propuesta.carry_cost,
            money_scale=sim_propuesta.money_scale,
            currency=sim_propuesta.currency,
            exit_reason=None,
            gross_pnl=None,
            net_pnl=None,
            realized_r=None,
            mfe=0,
            mae=0,
            reconciliation_status="PENDING",
            reconciliation_reason_codes=(),
            market_event_cutoff=sim_propuesta.market_event_cutoff,
            cost_profile_version=sim_propuesta.cost_profile_version,
            correlation_id=sim_propuesta.correlation_id,
            causation_id=sim_propuesta.causation_id,
            schema_version=1,
        )

        val_res = validar_simulacion(sim_abierta)
        if not val_res.exito:
            return fallo(val_res.error)

        self.motor_riesgo.registrar_apertura(sim_abierta)
        self._simulaciones_activas[sim_id] = sim_abierta
        return exito(sim_abierta)

    def avanzar_tick(
        self,
        simulation_id: str,
        tick: QuoteTickPayloadV1,
        now_utc: datetime,
    ) -> Resultado[SimulacionV1]:
        """Avanza la simulación con un nuevo tick y ejecuta salidas si aplica."""
        if simulation_id not in self._simulaciones_activas:
            return fallo(
                ErrorDominio(
                    codigo="NOT_FOUND",
                    mensaje_seguro=f"Simulación no encontrada o ya cerrada: {simulation_id}",
                    reintentable=False,
                    correlation_id="",
                    detalles={"simulation_id": simulation_id},
                )
            )

        sim = self._simulaciones_activas[simulation_id]
        if sim.status != "OPEN_SIMULATED":
            return exito(sim)

        # 1. Comprobar vencimiento de horizonte temporal (5 min)
        if sim.horizon_end_utc and now_utc >= sim.horizon_end_utc:
            fill_exit = tick.bid if sim.direction == "LONG" else tick.ask
            return self._cerrar_simulacion(sim, fill_exit, "time", now_utc)

        # 2. Evaluar triple barrera
        if sim.direction == "LONG":
            assert sim.fill_entry is not None
            estado_barrera, exit_price = self.evaluador.evaluar_tick_long(
                entry_ask=sim.fill_entry,
                tick_bid=tick.bid,
                tick_ask=tick.ask,
            )
            # Actualizar MFE / MAE
            mfe = max(sim.mfe or 0, tick.bid - sim.fill_entry)
            mae = min(sim.mae or 0, tick.bid - sim.fill_entry)
        else:
            assert sim.fill_entry is not None
            estado_barrera, exit_price = self.evaluador.evaluar_tick_short(
                entry_bid=sim.fill_entry,
                tick_bid=tick.bid,
                tick_ask=tick.ask,
            )
            mfe = max(sim.mfe or 0, sim.fill_entry - tick.ask)
            mae = min(sim.mae or 0, sim.fill_entry - tick.ask)

        if estado_barrera == "TAKE_PROFIT":
            return self._cerrar_simulacion(sim, exit_price, "target", now_utc)
        elif estado_barrera in {"STOP_LOSS", "AMBIGUOUS_STOP_FIRST"}:
            return self._cerrar_simulacion(sim, exit_price, "stop", now_utc)

        # Continúa abierta, actualizar tracking
        sim_actualizada = SimulacionV1(
            simulation_id=sim.simulation_id,
            signal_id=sim.signal_id,
            environment=sim.environment,
            demo_account_hash=sim.demo_account_hash,
            status=sim.status,
            proposed_at_utc=sim.proposed_at_utc,
            opened_at_utc=sim.opened_at_utc,
            closed_at_utc=None,
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
            fill_exit=None,
            fill_source=sim.fill_source,
            source_execution_ids=sim.source_execution_ids,
            spread_cost=sim.spread_cost,
            slippage_cost=sim.slippage_cost,
            commission_cost=sim.commission_cost,
            carry_cost=sim.carry_cost,
            money_scale=sim.money_scale,
            currency=sim.currency,
            exit_reason=None,
            gross_pnl=None,
            net_pnl=None,
            realized_r=None,
            mfe=mfe,
            mae=mae,
            reconciliation_status=sim.reconciliation_status,
            reconciliation_reason_codes=sim.reconciliation_reason_codes,
            market_event_cutoff=sim.market_event_cutoff,
            cost_profile_version=sim.cost_profile_version,
            correlation_id=sim.correlation_id,
            causation_id=sim.causation_id,
            schema_version=1,
        )
        self._simulaciones_activas[simulation_id] = sim_actualizada
        return exito(sim_actualizada)

    def _cerrar_simulacion(
        self,
        sim: SimulacionV1,
        fill_exit: int,
        exit_reason: str,
        now_utc: datetime,
    ) -> Resultado[SimulacionV1]:
        assert sim.fill_entry is not None

        if sim.direction == "LONG":
            delta_points = fill_exit - sim.fill_entry
        else:
            delta_points = sim.fill_entry - fill_exit

        # delta_points scaled 100, qty scaled 100 -> USD = (delta_points * qty) / 10000.0
        # en centavos de USD: USD * 100 = (delta_points * qty) / 100
        gross_pnl_cents = (delta_points * sim.effective_quantity_simulated) // 100

        # Costos en centavos
        spread_cents = ((sim.spread_cost or 0) * sim.effective_quantity_simulated) // 100
        slippage_cents = ((sim.slippage_cost or 0) * sim.effective_quantity_simulated) // 100
        commission_cents = sim.commission_cost or 0
        total_costs_cents = spread_cents + slippage_cents + commission_cents

        net_pnl_cents = gross_pnl_cents - total_costs_cents

        # Realized R (stop loss distance = self.stop_points)
        r_scale = 1_000_000
        realized_r = (delta_points * r_scale) // self.stop_points

        sim_cerrada = SimulacionV1(
            simulation_id=sim.simulation_id,
            signal_id=sim.signal_id,
            environment=sim.environment,
            demo_account_hash=sim.demo_account_hash,
            status="CLOSED_SIMULATED",
            proposed_at_utc=sim.proposed_at_utc,
            opened_at_utc=sim.opened_at_utc,
            closed_at_utc=now_utc,
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
            fill_exit=fill_exit,
            fill_source=sim.fill_source,
            source_execution_ids=sim.source_execution_ids,
            spread_cost=sim.spread_cost,
            slippage_cost=sim.slippage_cost,
            commission_cost=sim.commission_cost,
            carry_cost=sim.carry_cost,
            money_scale=sim.money_scale,
            currency=sim.currency,
            exit_reason=exit_reason,
            gross_pnl=gross_pnl_cents,
            net_pnl=net_pnl_cents,
            realized_r=realized_r,
            mfe=sim.mfe,
            mae=sim.mae,
            reconciliation_status=sim.reconciliation_status,
            reconciliation_reason_codes=sim.reconciliation_reason_codes,
            market_event_cutoff=sim.market_event_cutoff,
            cost_profile_version=sim.cost_profile_version,
            correlation_id=sim.correlation_id,
            causation_id=sim.causation_id,
            schema_version=1,
        )

        val_res = validar_simulacion(sim_cerrada)
        if not val_res.exito:
            return fallo(val_res.error)

        self.motor_riesgo.registrar_cierre(sim_cerrada, net_pnl_cents)
        del self._simulaciones_activas[sim.simulation_id]
        return exito(sim_cerrada)
