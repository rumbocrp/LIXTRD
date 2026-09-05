"""Pruebas unitarias para la Matriz de Filtrado Personalizada (Fase 3)."""

import pytest
from sistema_luces.domain.models import DecisionLuzContract, QuantFeatures
from sistema_luces.domain.vocabulary import TrafficLightColor, ActionType, HealthState, ReasonCode
from sistema_luces.domain.strategy import StrategyDefinition
from sistema_luces.domain.operator_trade import OperatorTradeRecord, TradeDirection
from sistema_luces.learning.operator_profiler import OperatorBehavioralProfiler
from sistema_luces.learning.personalized_filter import PersonalizedFilterMatrix

def make_test_trade(setup_id: str, is_win: bool, r_val: float):
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
        market_regime_tag="NORMAL",
    )

def make_dummy_decision(confidence_ppm=750_000):
    feats = QuantFeatures(
        kalman_beta=1.0, kalman_alpha=0.0, spread_z_score=-1.5, order_flow_imbalance=25.0,
        mid_price=2050.0, micro_price=2050.1, cross_asset_correlation=0.8,
        vpin_toxicity=0.1, spread_pips=0.2,
    )
    return DecisionLuzContract.create(
        instrument="XAUUSD", timeframe="TICK",
        state=TrafficLightColor.GREEN, action=ActionType.BUY,
        net_utility_long=0.002, net_utility_short=-0.002,
        confidence_score=confidence_ppm / 1_000_000,
        calibration_quality=0.9, features=feats,
        champion_model_id="champ-v1", reason_codes=[ReasonCode.OFI_BUY_IMBALANCE],
        data_health=HealthState.HEALTHY,
    )

def test_personalized_filter_defensive_veto_on_negative_edge():
    profiler = OperatorBehavioralProfiler()
    # Simular historial negativo en el setup
    trades = [
        make_test_trade("BAD_SETUP", False, -1.0),
        make_test_trade("BAD_SETUP", False, -1.0),
        make_test_trade("BAD_SETUP", False, -1.0),
    ]
    profiler.load_trades(trades)
    
    filter_matrix = PersonalizedFilterMatrix(profiler=profiler)
    strategy = StrategyDefinition(
        strategy_id="BAD_SETUP", version="v1.0", name="Setup Inestable",
        instrument="XAUUSD", allowed_directions=["LONG"], session_window="ALL",
        cadences=["1S"], default_stop_atr_mult=1.0, default_target_atr_mult=1.0,
        max_horizon_seconds=300, cost_profile_pips=0.2,
    )

    decision = make_dummy_decision(confidence_ppm=750_000) # Confianza normal 75%
    filtered = filter_matrix.apply_filter(decision, active_strategy=strategy)

    # Debe degradar forzosamente a AMARILLO para proteger al operador
    assert filtered.state == TrafficLightColor.YELLOW
    assert filtered.action == ActionType.MONITOR
    assert ReasonCode.MONITOR_POLICY in filtered.reason_codes
