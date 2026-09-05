"""Pruebas unitarias para el Registro y Gestión de Perfiles de Estrategia (Fase 3)."""

import pytest
from sistema_luces.domain.strategy import StrategyDefinition
from sistema_luces.domain.strategy_registry import StrategyProfileRegistry
from sistema_luces.storage.database import DecisionDatabase

def test_strategy_registry_canonical_loading():
    registry = StrategyProfileRegistry()
    strats = registry.list_strategies()
    assert len(strats) >= 3
    
    gold_strat = registry.get_strategy("GOLD_DXY_MACRO_REVERSION")
    assert gold_strat is not None
    assert gold_strat.instrument == "XAUUSD"
    assert gold_strat.default_stop_atr_mult == 2.0

def test_strategy_registry_custom_registration_and_persistence(tmp_path):
    db_file = str(tmp_path / "test_strats.db")
    db = DecisionDatabase(db_path=db_file)
    registry = StrategyProfileRegistry(db=db)

    custom_strat = StrategyDefinition(
        strategy_id="CUSTOM_BREAKOUT_LONDON",
        version="v1.0",
        name="Breakout de Rango Londres",
        instrument="XAUUSD",
        allowed_directions=["LONG"],
        session_window="LONDON_OPEN",
        cadences=["1S", "5S"],
        default_stop_atr_mult=1.5,
        default_target_atr_mult=3.0,
        max_horizon_seconds=600,
        cost_profile_pips=0.15,
        description="Estrategia discrecional del operador en apertura europea.",
    )

    registry.register_strategy(custom_strat, persist=True)
    retrieved = registry.get_strategy("CUSTOM_BREAKOUT_LONDON")
    assert retrieved is not None
    assert retrieved.name == "Breakout de Rango Londres"

    # Desactivar estrategia
    success = registry.set_active_state("CUSTOM_BREAKOUT_LONDON", "v1.0", False)
    assert success is True
    active_strats = registry.list_strategies(active_only=True)
    assert not any(s.strategy_id == "CUSTOM_BREAKOUT_LONDON" for s in active_strats)
