"""Pruebas unitarias para el Perfilador de Comportamiento del Operador (Fase 3)."""

import pytest
from sistema_luces.domain.operator_trade import OperatorTradeRecord, TradeDirection
from sistema_luces.learning.operator_profiler import OperatorBehavioralProfiler

def make_test_trade(setup_id: str, is_win: bool, r_val: float, regime: str = "NORMAL"):
    entry = 2000.0
    risk = 10.0
    stop = entry - risk
    exit_p = (entry + risk * r_val) if is_win else (entry - risk * abs(r_val))
    pnl = 100.0 * r_val
    return OperatorTradeRecord.create(
        instrument="XAUUSD",
        direction=TradeDirection.LONG,
        setup_id=setup_id,
        strategy_version="v1.0",
        entry_timestamp_utc=1700000000000,
        entry_price=entry,
        stop_loss_price=stop,
        take_profit_price=entry + 20.0,
        exit_timestamp_utc=1700000600000,
        exit_price=exit_p,
        pnl_usd=pnl,
        market_regime_tag=regime,
    )

def test_operator_profiler_strong_edge_detection():
    profiler = OperatorBehavioralProfiler()
    # 5 trades ganadores con 2.5 R de ganancia promedio y 1 perdedor de 1.0 R
    trades = [
        make_test_trade("GOLD_DXY_MACRO_REVERSION", True, 2.5),
        make_test_trade("GOLD_DXY_MACRO_REVERSION", True, 2.0),
        make_test_trade("GOLD_DXY_MACRO_REVERSION", True, 3.0),
        make_test_trade("GOLD_DXY_MACRO_REVERSION", True, 2.2),
        make_test_trade("GOLD_DXY_MACRO_REVERSION", True, 2.8),
        make_test_trade("GOLD_DXY_MACRO_REVERSION", False, -1.0),
    ]
    profiler.load_trades(trades)
    profiles = profiler.compute_setup_profiles()
    
    gold_profile = profiles["GOLD_DXY_MACRO_REVERSION"]
    assert gold_profile["total_trades"] == 6
    assert gold_profile["wins"] == 5
    assert gold_profile["win_rate_pct"] > 80.0
    assert gold_profile["expectancy_r"] > 1.5
    assert gold_profile["edge_tag"] == "STRONG_EDGE"

def test_operator_profiler_negative_edge_detection():
    profiler = OperatorBehavioralProfiler()
    # 1 ganador pequeño (0.5 R) y 4 perdedores (1.0 R)
    trades = [
        make_test_trade("LOSING_SETUP", True, 0.5),
        make_test_trade("LOSING_SETUP", False, -1.0),
        make_test_trade("LOSING_SETUP", False, -1.0),
        make_test_trade("LOSING_SETUP", False, -1.0),
        make_test_trade("LOSING_SETUP", False, -1.0),
    ]
    profiler.load_trades(trades)
    profiles = profiler.compute_setup_profiles()
    
    losing_profile = profiles["LOSING_SETUP"]
    assert losing_profile["expectancy_r"] < 0
    assert losing_profile["edge_tag"] == "NEGATIVE_EDGE"
