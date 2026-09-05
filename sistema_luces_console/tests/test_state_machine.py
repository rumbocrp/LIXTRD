"""Pruebas de la Máquina de Estados con Histéresis y Política Fail-Safe."""

import pytest
from sistema_luces.domain.state_machine import DecisionStateMachine
from sistema_luces.domain.models import QuantFeatures
from sistema_luces.domain.vocabulary import TrafficLightColor, ActionType, HealthState, ReasonCode

def make_dummy_features(z_score=0.0, ofi=0.0, micro_delta=0.0, toxicity=0.1):
    mid = 2050.0
    return QuantFeatures(
        kalman_beta=1.0,
        kalman_alpha=0.0,
        spread_z_score=z_score,
        order_flow_imbalance=ofi,
        mid_price=mid,
        micro_price=mid + micro_delta,
        cross_asset_correlation=0.9,
        vpin_toxicity=toxicity,
        spread_pips=0.20,
    )

def test_state_machine_fail_safe_on_stale_data():
    sm = DecisionStateMachine()
    feats = make_dummy_features(z_score=-2.0, ofi=50.0, micro_delta=0.05)
    state, action, reasons = sm.evaluate(
        features=feats,
        health=HealthState.STALE,
        net_u_long=0.05,
        net_u_short=-0.05,
        composite_score=0.8,
    )
    assert state == TrafficLightColor.YELLOW
    assert action == ActionType.MONITOR
    assert ReasonCode.MONITOR_DATA_STALE in reasons

def test_state_machine_hysteresis_entry_and_exit():
    sm = DecisionStateMachine(t_entry=0.45, t_exit=0.15)
    
    # 1. No debe entrar si score es 0.30 (< t_entry 0.45)
    feats = make_dummy_features(z_score=-1.5, ofi=30.0, micro_delta=0.02)
    state, action, _ = sm.evaluate(feats, HealthState.HEALTHY, 0.01, -0.01, composite_score=0.30)
    assert state == TrafficLightColor.YELLOW

    # 2. Entra a GREEN cuando supera t_entry y condiciones
    state, action, _ = sm.evaluate(feats, HealthState.HEALTHY, 0.05, -0.05, composite_score=0.55)
    assert state == TrafficLightColor.GREEN
    assert action == ActionType.BUY

    # 3. Permanece en GREEN si score baja a 0.25 (> t_exit 0.15)
    state, action, _ = sm.evaluate(feats, HealthState.HEALTHY, 0.02, -0.02, composite_score=0.25)
    assert state == TrafficLightColor.GREEN

    # 4. Sale a YELLOW cuando cae por debajo de t_exit (< 0.15)
    state, action, _ = sm.evaluate(feats, HealthState.HEALTHY, 0.0, 0.0, composite_score=0.10)
    assert state == TrafficLightColor.YELLOW
