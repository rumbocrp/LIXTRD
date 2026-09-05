"""Registro y Gestión de Perfiles de Estrategia del Operador (Fase 3)."""

from __future__ import annotations
from typing import Dict, List, Optional
from sistema_luces.domain.strategy import StrategyDefinition, CANONICAL_STRATEGIES
from sistema_luces.storage.database import DecisionDatabase

class StrategyProfileRegistry:
    """Registro y catálogo de estrategias parametrizadas y versionadas para el operador."""
    def __init__(self, db: Optional[DecisionDatabase] = None):
        self.db = db
        self.strategies: Dict[str, StrategyDefinition] = {}
        # Cargar estrategias canónicas por defecto
        for strat in CANONICAL_STRATEGIES.values():
            self.register_strategy(strat, persist=False)

    def register_strategy(self, strategy: StrategyDefinition, persist: bool = True) -> StrategyDefinition:
        key = f"{strategy.strategy_id}:{strategy.version}"
        self.strategies[key] = strategy
        
        if persist and self.db:
            with self.db._get_conn() as conn:
                conn.execute("""
                INSERT OR REPLACE INTO estrategia_version (
                    strategy_id, version, name, instrument, allowed_directions,
                    session_window, cadences, default_stop_atr_mult, default_target_atr_mult,
                    max_horizon_seconds, cost_profile_pips, description, strategy_hash, is_active
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """, (
                    strategy.strategy_id, strategy.version, strategy.name, strategy.instrument,
                    ",".join(strategy.allowed_directions), strategy.session_window,
                    ",".join(strategy.cadences), strategy.default_stop_atr_mult,
                    strategy.default_target_atr_mult, strategy.max_horizon_seconds,
                    strategy.cost_profile_pips, strategy.description, strategy.compute_hash(),
                    1 if strategy.is_active else 0
                ))
                conn.commit()
        return strategy

    def get_strategy(self, strategy_id: str, version: str = "v1.0") -> Optional[StrategyDefinition]:
        key = f"{strategy_id}:{version}"
        return self.strategies.get(key)

    def list_strategies(self, active_only: bool = True) -> List[StrategyDefinition]:
        strats = list(self.strategies.values())
        if active_only:
            return [s for s in strats if s.is_active]
        return strats

    def set_active_state(self, strategy_id: str, version: str, is_active: bool) -> bool:
        key = f"{strategy_id}:{version}"
        if key in self.strategies:
            strat = self.strategies[key]
            updated = StrategyDefinition(
                strategy_id=strat.strategy_id,
                version=strat.version,
                name=strat.name,
                instrument=strat.instrument,
                allowed_directions=strat.allowed_directions,
                session_window=strat.session_window,
                cadences=strat.cadences,
                default_stop_atr_mult=strat.default_stop_atr_mult,
                default_target_atr_mult=strat.default_target_atr_mult,
                max_horizon_seconds=strat.max_horizon_seconds,
                cost_profile_pips=strat.cost_profile_pips,
                description=strat.description,
                is_active=is_active,
                created_at_utc=strat.created_at_utc,
            )
            self.register_strategy(updated, persist=True)
            return True
        return False
