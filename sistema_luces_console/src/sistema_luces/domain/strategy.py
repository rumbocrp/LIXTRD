"""Definición y versionado de estrategias y setups del operador (Fase 0)."""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
import hashlib
import json

@dataclass(frozen=True)
class StrategyDefinition:
    """Contrato formal de una estrategia o setup del operador."""
    strategy_id: str
    version: str
    name: str
    instrument: str
    allowed_directions: List[str] # ["LONG", "SHORT"]
    session_window: str # e.g. "LONDON_OPEN", "NY_OPEN", "ALL"
    cadences: List[str] # ["TICK", "1S", "5S", "15S", "30S", "60S"]
    
    # Parámetros cuantitativos de referencia
    default_stop_atr_mult: float
    default_target_atr_mult: float
    max_horizon_seconds: int
    cost_profile_pips: float
    
    description: str = ""
    is_active: bool = True
    created_at_utc: int = 0

    def compute_hash(self) -> str:
        payload = json.dumps({
            "strategy_id": self.strategy_id,
            "version": self.version,
            "instrument": self.instrument,
            "directions": self.allowed_directions,
            "cadences": self.cadences,
            "stop_atr": self.default_stop_atr_mult,
            "target_atr": self.default_target_atr_mult,
            "max_horizon": self.max_horizon_seconds,
        }, sort_keys=True)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

# Setups canónicos predefinidos de referencia
CANONICAL_STRATEGIES: Dict[str, StrategyDefinition] = {
    "GOLD_DXY_MACRO_REVERSION": StrategyDefinition(
        strategy_id="GOLD_DXY_MACRO_REVERSION",
        version="v1.0",
        name="Reversión Macro Oro vs. DXY",
        instrument="XAUUSD",
        allowed_directions=["LONG", "SHORT"],
        session_window="NY_OPEN",
        cadences=["TICK", "1S", "5S", "60S"],
        default_stop_atr_mult=2.0,
        default_target_atr_mult=3.5,
        max_horizon_seconds=1800, # 30 min
        cost_profile_pips=0.20,
        description="Aprovecha desacoples temporales severos entre el Oro y el Índice Dólar con confluencia de OFI.",
    ),
    "SP500_TSLA_BETA_MOMENTUM": StrategyDefinition(
        strategy_id="SP500_TSLA_BETA_MOMENTUM",
        version="v1.0",
        name="Momentum High-Beta TSLA / S&P 500",
        instrument="TSLA",
        allowed_directions=["LONG", "SHORT"],
        session_window="NY_OPEN",
        cadences=["1S", "5S", "15S", "60S"],
        default_stop_atr_mult=1.8,
        default_target_atr_mult=3.0,
        max_horizon_seconds=900, # 15 min
        cost_profile_pips=0.05,
        description="Captura el desbalance de flujo en futuros /ES transmitido a TSLA en horizontes sub-segundo.",
    ),
    "SP500_AAPL_ANCHOR_PULLBACK": StrategyDefinition(
        strategy_id="SP500_AAPL_ANCHOR_PULLBACK",
        version="v1.0",
        name="Pullback Ancla Sistémica AAPL / S&P 500",
        instrument="AAPL",
        allowed_directions=["LONG", "SHORT"],
        session_window="ALL",
        cadences=["5S", "15S", "60S"],
        default_stop_atr_mult=1.5,
        default_target_atr_mult=2.5,
        max_horizon_seconds=1200,
        cost_profile_pips=0.04,
        description="Arbitraje estadístico de cesta de índice cuando AAPL lidera el flujo del sector tecnológico.",
    )
}
