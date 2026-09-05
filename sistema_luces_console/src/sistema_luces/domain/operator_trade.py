"""Contratos y modelos inmutables para la operativa personal del operador (Fase 0)."""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Dict, Any
import hashlib
import json
import uuid

class TradeDirection(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"

class TradeOutcome(str, Enum):
    WIN = "WIN"
    LOSS = "LOSS"
    BREAKEVEN = "BREAKEVEN"
    OPEN = "OPEN"

@dataclass(frozen=True)
class OperatorTradeRecord:
    """Registro inmutable de una operación realizada o planificada por el operador."""
    trade_id: str
    instrument: str
    direction: TradeDirection
    setup_id: str
    strategy_version: str
    
    entry_timestamp_utc: int
    entry_price: float
    stop_loss_price: float
    take_profit_price: float
    
    exit_timestamp_utc: Optional[int] = None
    exit_price: Optional[float] = None
    outcome: TradeOutcome = TradeOutcome.OPEN
    
    # Métricas normalizadas en PPM (Parts Per Million: 1.0 R = 1,000,000 ppm)
    risk_r_multiple_ppm: int = 0
    net_pnl_usd_scaled: int = 0 # centavos (ej. $125.50 = 12550)
    commission_usd_scaled: int = 0
    slippage_pips_scaled: int = 0
    
    market_regime_tag: str = "UNKNOWN"
    operator_notes: str = ""
    source_file_sha256: str = ""

    @property
    def is_closed(self) -> bool:
        return self.exit_timestamp_utc is not None and self.exit_price is not None

    def compute_sha256(self) -> str:
        payload = f"{self.trade_id}:{self.instrument}:{self.direction.value}:{self.entry_timestamp_utc}:{self.entry_price}:{self.exit_price}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    @classmethod
    def create(
        cls,
        instrument: str,
        direction: TradeDirection,
        setup_id: str,
        strategy_version: str,
        entry_timestamp_utc: int,
        entry_price: float,
        stop_loss_price: float,
        take_profit_price: float,
        exit_timestamp_utc: Optional[int] = None,
        exit_price: Optional[float] = None,
        pnl_usd: float = 0.0,
        commission_usd: float = 0.0,
        slippage_pips: float = 0.0,
        market_regime_tag: str = "NORMAL",
        operator_notes: str = "",
        source_sha256: str = "",
        trade_id: Optional[str] = None,
    ) -> OperatorTradeRecord:
        t_id = trade_id or str(uuid.uuid4())
        
        # Calcular R-Múltiplo si la operación está cerrada
        risk_dist = abs(entry_price - stop_loss_price)
        r_ppm = 0
        outcome = TradeOutcome.OPEN

        if exit_price is not None and risk_dist > 1e-6:
            gain_dist = (exit_price - entry_price) if direction == TradeDirection.LONG else (entry_price - exit_price)
            r_val = gain_dist / risk_dist
            r_ppm = int(round(r_val * 1_000_000))
            if r_val > 0.05:
                outcome = TradeOutcome.WIN
            elif r_val < -0.05:
                outcome = TradeOutcome.LOSS
            else:
                outcome = TradeOutcome.BREAKEVEN

        return cls(
            trade_id=t_id,
            instrument=instrument.upper(),
            direction=direction,
            setup_id=setup_id,
            strategy_version=strategy_version,
            entry_timestamp_utc=entry_timestamp_utc,
            entry_price=entry_price,
            stop_loss_price=stop_loss_price,
            take_profit_price=take_profit_price,
            exit_timestamp_utc=exit_timestamp_utc,
            exit_price=exit_price,
            outcome=outcome,
            risk_r_multiple_ppm=r_ppm,
            net_pnl_usd_scaled=int(round(pnl_usd * 100)),
            commission_usd_scaled=int(round(commission_usd * 100)),
            slippage_pips_scaled=int(round(slippage_pips * 100)),
            market_regime_tag=market_regime_tag,
            operator_notes=operator_notes,
            source_file_sha256=source_sha256,
        )
