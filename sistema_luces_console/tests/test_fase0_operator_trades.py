"""Pruebas unitarias para los modelos de operativa del operador y persistencia (Fase 0)."""

import pytest
from sistema_luces.domain.operator_trade import OperatorTradeRecord, TradeDirection, TradeOutcome
from sistema_luces.domain.strategy import StrategyDefinition, CANONICAL_STRATEGIES
from sistema_luces.storage.database import DecisionDatabase

def test_operator_trade_r_multiple_calculation():
    # Long trade ganador: entrada 2000, stop 1990 (riesgo 10), salida 2030 (ganancia 30 -> 3.0 R)
    t = OperatorTradeRecord.create(
        instrument="XAUUSD",
        direction=TradeDirection.LONG,
        setup_id="GOLD_DXY_MACRO_REVERSION",
        strategy_version="v1.0",
        entry_timestamp_utc=1700000000000,
        entry_price=2000.0,
        stop_loss_price=1990.0,
        take_profit_price=2030.0,
        exit_timestamp_utc=1700000300000,
        exit_price=2030.0,
        pnl_usd=300.0,
    )
    assert t.outcome == TradeOutcome.WIN
    assert t.risk_r_multiple_ppm == 3_000_000 # 3.0 R en PPM
    assert t.is_closed is True

def test_operator_trade_loss_calculation():
    # Short trade perdedor: entrada 100, stop 105 (riesgo 5), salida 105 (-1.0 R)
    t = OperatorTradeRecord.create(
        instrument="TSLA",
        direction=TradeDirection.SHORT,
        setup_id="SP500_TSLA_BETA_MOMENTUM",
        strategy_version="v1.0",
        entry_timestamp_utc=1700000000000,
        entry_price=100.0,
        stop_loss_price=105.0,
        take_profit_price=90.0,
        exit_timestamp_utc=1700000300000,
        exit_price=105.0,
        pnl_usd=-100.0,
    )
    assert t.outcome == TradeOutcome.LOSS
    assert t.risk_r_multiple_ppm == -1_000_000 # -1.0 R en PPM

def test_database_operator_trade_persistence(tmp_path):
    db_file = str(tmp_path / "test_fase0.db")
    db = DecisionDatabase(db_path=db_file)

    t1 = OperatorTradeRecord.create(
        instrument="XAUUSD",
        direction=TradeDirection.LONG,
        setup_id="GOLD_DXY_MACRO_REVERSION",
        strategy_version="v1.0",
        entry_timestamp_utc=1700000000000,
        entry_price=2050.0,
        stop_loss_price=2040.0,
        take_profit_price=2080.0,
        exit_timestamp_utc=1700000300000,
        exit_price=2080.0,
        pnl_usd=600.0,
        trade_id="t-001",
    )
    db.save_operator_trade(t1)

    trades = db.get_operator_trades(setup_id="GOLD_DXY_MACRO_REVERSION")
    assert len(trades) == 1
    assert trades[0]["trade_id"] == "t-001"
    assert trades[0]["outcome"] == "WIN"

    perf = db.get_operator_performance_by_setup()
    assert "GOLD_DXY_MACRO_REVERSION" in perf
    assert perf["GOLD_DXY_MACRO_REVERSION"]["win_rate_pct"] == 100.0
