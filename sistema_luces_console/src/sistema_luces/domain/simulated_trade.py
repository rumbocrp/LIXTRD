"""Contratos de dominio inmutables para operativas simuladas, espectro agudo de ejecución y métricas de riesgo simulado."""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
import uuid
import time
from sistema_luces.domain.operator_trade import TradeDirection, TradeOutcome

@dataclass(frozen=True)
class AcuteExecutionResult:
    """Resultado del cálculo del espectro agudo de ejecución en profundidad L2."""
    direction: str                     # "LONG" o "SHORT"
    nominal_price: float               # Precio de toque (Best Bid o Best Ask)
    effective_fill_price: float        # Precio final ponderado por profundidad y penalización aguda
    slippage_pips: float               # Desviación total en pips frente al nominal
    book_depth_slippage: float         # Fricción por barrido de niveles L2 (k=1..5)
    adverse_selection_slippage: float  # Micro-penalización por toxicidad (VPIN/OFI adverso)
    spectrum_sharpness_score: float    # Índice de agudeza del espectro [0.0, 100.0]
    spectrum_tier: str                 # "OPTIMAL_TOUCH", "MODERATE_SLIP", "DEEP_SWEEP", "ACUTE_ADVERSE"
    spread_friction_ratio: float       # Ratio slippage / spread instantáneo

    def to_dict(self) -> Dict[str, Any]:
        return {
            "direction": self.direction,
            "nominal_price": round(self.nominal_price, 4),
            "effective_fill_price": round(self.effective_fill_price, 4),
            "slippage_pips": round(self.slippage_pips, 4),
            "book_depth_slippage": round(self.book_depth_slippage, 4),
            "adverse_selection_slippage": round(self.adverse_selection_slippage, 4),
            "spectrum_sharpness_score": round(self.spectrum_sharpness_score, 2),
            "spectrum_tier": self.spectrum_tier,
            "spread_friction_ratio": round(self.spread_friction_ratio, 3),
        }

@dataclass
class SimulatedOperation:
    """Representa una operación simulada ejecutada en tiempo real bajo el modelo del Sistema de Luces."""
    operation_id: str
    instrument: str
    direction: TradeDirection
    entry_timestamp_utc: int
    entry_price: float
    stop_loss_price: float
    take_profit_price: float
    size: float
    
    exit_timestamp_utc: Optional[int] = None
    exit_price: Optional[float] = None
    status: str = "OPEN" # "OPEN", "CLOSED"
    pnl_usd: float = 0.0
    return_pct: float = 0.0
    r_multiple: float = 0.0
    slippage_pips: float = 0.0
    commission_usd: float = 0.0
    acute_slippage_penalty: float = 0.0
    execution_spectrum_tier: str = "OPTIMAL_TOUCH"
    simulated_risk_pct_at_entry: float = 0.0
    close_reason: str = ""

    @property
    def is_closed(self) -> bool:
        return self.status == "CLOSED"

    @classmethod
    def create(
        cls,
        instrument: str,
        direction: TradeDirection,
        entry_price: float,
        stop_loss_price: float,
        take_profit_price: float,
        size: float = 1.0,
        simulated_risk_pct: float = 1.5,
        execution_tier: str = "OPTIMAL_TOUCH",
        acute_penalty: float = 0.0,
        entry_timestamp_utc: Optional[int] = None,
        operation_id: Optional[str] = None,
    ) -> SimulatedOperation:
        now_ms = entry_timestamp_utc or int(time.time() * 1000)
        op_id = operation_id or str(uuid.uuid4())
        return cls(
            operation_id=op_id,
            instrument=instrument.upper(),
            direction=direction,
            entry_timestamp_utc=now_ms,
            entry_price=entry_price,
            stop_loss_price=stop_loss_price,
            take_profit_price=take_profit_price,
            size=size,
            simulated_risk_pct_at_entry=simulated_risk_pct,
            execution_spectrum_tier=execution_tier,
            acute_slippage_penalty=acute_penalty,
        )

    def close(
        self,
        exit_price: float,
        exit_timestamp_utc: Optional[int] = None,
        close_reason: str = "SIGNAL_STANDBY",
        commission_per_unit: float = 0.02,
    ) -> None:
        self.exit_price = exit_price
        self.exit_timestamp_utc = exit_timestamp_utc or int(time.time() * 1000)
        self.status = "CLOSED"
        self.close_reason = close_reason

        # Cálculo de PnL y R-múltiplo
        risk_dist = abs(self.entry_price - self.stop_loss_price)
        if self.direction == TradeDirection.LONG:
            gain_dist = self.exit_price - self.entry_price
        else:
            gain_dist = self.entry_price - self.exit_price

        self.commission_usd = round(self.size * commission_per_unit, 2)
        raw_pnl = gain_dist * self.size * 100.0 # Factor de escala estándar
        self.pnl_usd = round(raw_pnl - self.commission_usd, 2)
        self.return_pct = round((gain_dist / max(1e-4, self.entry_price)) * 100.0, 3)

        if risk_dist > 1e-6:
            self.r_multiple = round(gain_dist / risk_dist, 2)
        else:
            self.r_multiple = 0.0

    def compute_unrealized_pnl(self, current_price: float) -> float:
        if self.direction == TradeDirection.LONG:
            diff = current_price - self.entry_price
        else:
            diff = self.entry_price - current_price
        return round(diff * self.size * 100.0, 2)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "operation_id": self.operation_id,
            "instrument": self.instrument,
            "direction": self.direction.value,
            "entry_timestamp_utc": self.entry_timestamp_utc,
            "entry_price": round(self.entry_price, 4),
            "stop_loss_price": round(self.stop_loss_price, 4),
            "take_profit_price": round(self.take_profit_price, 4),
            "size": round(self.size, 2),
            "exit_timestamp_utc": self.exit_timestamp_utc,
            "exit_price": round(self.exit_price, 4) if self.exit_price is not None else None,
            "status": self.status,
            "pnl_usd": self.pnl_usd,
            "return_pct": self.return_pct,
            "r_multiple": self.r_multiple,
            "slippage_pips": round(self.slippage_pips, 4),
            "commission_usd": self.commission_usd,
            "acute_slippage_penalty": round(self.acute_slippage_penalty, 4),
            "execution_spectrum_tier": self.execution_spectrum_tier,
            "simulated_risk_pct_at_entry": round(self.simulated_risk_pct_at_entry, 2),
            "close_reason": self.close_reason,
        }

@dataclass
class SimulatedRiskMetrics:
    """Métricas cuantitativas del riesgo simulado bajo el modelo y el espectro de ejecución."""
    instantaneous_execution_risk_pct: float # Riesgo instantáneo de fricción/deslizamiento [0.0, 100.0]
    position_risk_pct: float                # Porcentaje de capital asignado al riesgo [0.5, 3.0]
    rolling_simulated_var_95_pct: float     # Value-at-Risk simulado al 95%
    rolling_simulated_cvar_95_pct: float    # Expected Shortfall (CVaR) simulado al 95%
    total_simulated_risk_pct: float         # Índice compuesto de riesgo simulado [0.0, 100.0]
    max_simulated_drawdown_pct: float       # Máximo drawdown histórico de la simulación
    win_rate_pct: float                     # Tasa de acierto de operativas cerradas
    profit_factor: float                    # Factor de beneficio
    total_trades_count: int                 # Operaciones totales
    open_trades_count: int                  # Operaciones activas en este momento
    realized_pnl_usd: float                 # PnL realizado acumulado
    unrealized_pnl_usd: float               # PnL no realizado de posiciones abiertas

    def to_dict(self) -> Dict[str, Any]:
        return {
            "instantaneous_execution_risk_pct": round(self.instantaneous_execution_risk_pct, 2),
            "position_risk_pct": round(self.position_risk_pct, 2),
            "rolling_simulated_var_95_pct": round(self.rolling_simulated_var_95_pct, 2),
            "rolling_simulated_cvar_95_pct": round(self.rolling_simulated_cvar_95_pct, 2),
            "total_simulated_risk_pct": round(self.total_simulated_risk_pct, 2),
            "max_simulated_drawdown_pct": round(self.max_simulated_drawdown_pct, 2),
            "win_rate_pct": round(self.win_rate_pct, 2),
            "profit_factor": round(self.profit_factor, 2),
            "total_trades_count": self.total_trades_count,
            "open_trades_count": self.open_trades_count,
            "realized_pnl_usd": round(self.realized_pnl_usd, 2),
            "unrealized_pnl_usd": round(self.unrealized_pnl_usd, 2),
        }
