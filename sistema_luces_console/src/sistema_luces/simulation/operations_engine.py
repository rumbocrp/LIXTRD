"""Orquestador de Operativas Simuladas en Tiempo Real y Gestión de Posiciones bajo el Sistema de Luces."""

from __future__ import annotations
from typing import Dict, List, Optional, Tuple, Any
import time

from sistema_luces.domain.vocabulary import TrafficLightColor, ActionType
from sistema_luces.domain.operator_trade import TradeDirection
from sistema_luces.domain.models import DecisionLuzContract, QuantFeatures
from sistema_luces.domain.simulated_trade import SimulatedOperation, AcuteExecutionResult, SimulatedRiskMetrics
from sistema_luces.quant.execution_spectrum import AcuteExecutionSpectrumEngine
from sistema_luces.quant.simulated_risk import SimulatedRiskEngine

class SimulatedOperationsEngine:
    """
    Gestiona el ciclo de vida completo de las operaciones simuladas:
    - Apertura en verde (LONG) y rojo (SHORT) con espectro agudo de ejecución.
    - Cierre por transición a amarillo (STANDBY), inversión de señal, SL o TP.
    - Seguimiento continuo de riesgo, PnL y retornos para alimentar el modelo de riesgo.
    """
    def __init__(
        self,
        db: Optional[Any] = None,
        base_size: float = 1.0,
        stop_mult: float = 2.0,
        target_mult: float = 3.5,
    ):
        self.db = db
        self.base_size = base_size
        self.stop_mult = stop_mult
        self.target_mult = target_mult

        self.execution_engine = AcuteExecutionSpectrumEngine()
        self.risk_engine = SimulatedRiskEngine()

        self.active_positions: Dict[str, Optional[SimulatedOperation]] = {}
        self.closed_operations: List[SimulatedOperation] = []
        self.last_closed_operation: Optional[SimulatedOperation] = None

    def get_open_operations(self) -> List[SimulatedOperation]:
        return [op for op in self.active_positions.values() if op is not None]

    def get_recent_operations(self, instrument: Optional[str] = None, limit: int = 10) -> List[SimulatedOperation]:
        ops = self.closed_operations
        if instrument:
            ops = [op for op in ops if op.instrument == instrument.upper()]
        return ops[-limit:]

    def on_tick(
        self,
        instrument: str,
        decision: DecisionLuzContract,
        bid_p: float,
        ask_p: float,
        bids_depth: Optional[List[Tuple[float, float]]] = None,
        asks_depth: Optional[List[Tuple[float, float]]] = None,
        features: Optional[QuantFeatures] = None,
    ) -> Tuple[Optional[SimulatedOperation], Optional[SimulatedOperation], AcuteExecutionResult, SimulatedRiskMetrics]:
        """
        Procesa el tick actual, actualiza la operativa simulada y calcula el espectro de riesgo.
        """
        sym = instrument.upper()
        mid_p = (bid_p + ask_p) / 2.0
        spread = max(1e-4, ask_p - bid_p)
        vpin = features.vpin_toxicity if features else 0.15
        ofi = features.order_flow_imbalance if features else 0.0
        z_score = features.spread_z_score if features else 0.0
        now_ms = decision.data_timestamp_utc or int(time.time() * 1000)

        b_depth = bids_depth if bids_depth else [(bid_p, 50.0)]
        a_depth = asks_depth if asks_depth else [(ask_p, 50.0)]

        active_op = self.active_positions.get(sym)
        just_closed_op: Optional[SimulatedOperation] = None

        # 1. Evaluar si la posición activa debe cerrarse
        if active_op is not None and not active_op.is_closed:
            # Actualizar PnL flotante
            active_op.pnl_usd = active_op.compute_unrealized_pnl(mid_p)

            close_reason = None

            # a) Cierre por transición de política a Standby (AMARILLO)
            if decision.state == TrafficLightColor.YELLOW:
                close_reason = "SIGNAL_STANDBY"
            # b) Cierre por reversión contraria
            elif active_op.direction == TradeDirection.LONG and decision.state == TrafficLightColor.RED:
                close_reason = "SIGNAL_REVERSED"
            elif active_op.direction == TradeDirection.SHORT and decision.state == TrafficLightColor.GREEN:
                close_reason = "SIGNAL_REVERSED"
            # c) Cierre por Stop-Loss
            elif active_op.direction == TradeDirection.LONG and bid_p <= active_op.stop_loss_price:
                close_reason = "STOP_LOSS_HIT"
            elif active_op.direction == TradeDirection.SHORT and ask_p >= active_op.stop_loss_price:
                close_reason = "STOP_LOSS_HIT"
            # d) Cierre por Take-Profit
            elif active_op.direction == TradeDirection.LONG and bid_p >= active_op.take_profit_price:
                close_reason = "TAKE_PROFIT_HIT"
            elif active_op.direction == TradeDirection.SHORT and ask_p <= active_op.take_profit_price:
                close_reason = "TAKE_PROFIT_HIT"

            if close_reason:
                # Ejecutar salida con espectro agudo en el lado opuesto del libro
                exit_dir = "SHORT" if active_op.direction == TradeDirection.LONG else "LONG"
                exit_exec = self.execution_engine.simulate_fill(
                    direction=exit_dir,
                    spread=spread,
                    vpin=vpin,
                    ofi=ofi,
                    bids_depth=b_depth,
                    asks_depth=a_depth,
                    size=active_op.size,
                )
                active_op.close(
                    exit_price=exit_exec.effective_fill_price,
                    exit_timestamp_utc=now_ms,
                    close_reason=close_reason,
                )
                self.closed_operations.append(active_op)
                self.risk_engine.record_closed_operation(active_op)
                if self.db is not None and hasattr(self.db, "save_simulated_operation"):
                    try:
                        self.db.save_simulated_operation(active_op)
                    except Exception:
                        pass
                just_closed_op = active_op
                self.last_closed_operation = active_op
                self.active_positions[sym] = None
                active_op = None

        # 2. Si no hay posición abierta, evaluar condiciones de apertura
        direction_to_open: Optional[TradeDirection] = None
        if active_op is None:
            if decision.state == TrafficLightColor.GREEN and decision.action == ActionType.BUY:
                direction_to_open = TradeDirection.LONG
            elif decision.state == TrafficLightColor.RED and decision.action == ActionType.SELL:
                direction_to_open = TradeDirection.SHORT

        # 3. Simulación del espectro agudo de ejecución actual
        exec_dir = "LONG" if (direction_to_open == TradeDirection.LONG or decision.state == TrafficLightColor.GREEN) else "SHORT"
        acute_result = self.execution_engine.simulate_fill(
            direction=exec_dir,
            spread=spread,
            vpin=vpin,
            ofi=ofi,
            bids_depth=b_depth,
            asks_depth=a_depth,
            size=self.base_size,
        )

        # 4. Cálculo de métricas cuantitativas de riesgo simulado
        open_ops = self.get_open_operations()
        risk_metrics = self.risk_engine.compute_risk_metrics(
            acute_result=acute_result,
            z_score=z_score,
            vpin=vpin,
            confidence_ppm=decision.confidence_score_ppm,
            open_operations=open_ops,
        )

        # 5. Si corresponde apertura, ejecutar operación con el precio agudo
        if direction_to_open is not None:
            fill_price = acute_result.effective_fill_price
            risk_dist = spread * self.stop_mult
            target_dist = spread * self.target_mult

            if direction_to_open == TradeDirection.LONG:
                sl_price = fill_price - risk_dist
                tp_price = fill_price + target_dist
            else:
                sl_price = fill_price + risk_dist
                tp_price = fill_price - target_dist

            new_op = SimulatedOperation.create(
                instrument=sym,
                direction=direction_to_open,
                entry_price=fill_price,
                stop_loss_price=sl_price,
                take_profit_price=tp_price,
                size=self.base_size,
                simulated_risk_pct=risk_metrics.total_simulated_risk_pct,
                execution_tier=acute_result.spectrum_tier,
                acute_penalty=acute_result.adverse_selection_slippage,
                entry_timestamp_utc=now_ms,
            )
            new_op.slippage_pips = acute_result.slippage_pips
            self.active_positions[sym] = new_op
            active_op = new_op
            if self.db is not None and hasattr(self.db, "save_simulated_operation"):
                try:
                    self.db.save_simulated_operation(new_op)
                except Exception:
                    pass

        return active_op, just_closed_op, acute_result, risk_metrics
