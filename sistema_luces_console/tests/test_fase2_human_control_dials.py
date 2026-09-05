"""Pruebas unitarias para los Diales de Control Humano y Parada de Pánico (Fase 2)."""

import pytest
from sistema_luces.domain.human_control import HumanControlDials
from sistema_luces.domain.state_machine import DecisionStateMachine
from sistema_luces.domain.vocabulary import TrafficLightColor, ActionType, HealthState
from sistema_luces.domain.models import QuantFeatures

def make_strong_buy_features(spread=0.20):
    mid = 2050.0
    return QuantFeatures(
        kalman_beta=-18.5,
        kalman_alpha=0.0,
        spread_z_score=-2.0,
        order_flow_imbalance=45.0,
        mid_price=mid,
        micro_price=mid + 0.08,
        cross_asset_correlation=-0.85,
        vpin_toxicity=0.10,
        spread_pips=spread,
    )

def test_human_hard_panic_veto():
    dials = HumanControlDials()
    sm = DecisionStateMachine(dials=dials)
    feats = make_strong_buy_features()

    # En condiciones normales, debe dar GREEN
    state, action, _ = sm.evaluate(feats, HealthState.HEALTHY, 0.05, -0.05, composite_score=0.80)
    assert state == TrafficLightColor.GREEN

    # Activar Hard Veto manual del operador
    dials.toggle_hard_veto()
    state_veto, action_veto, _ = sm.evaluate(feats, HealthState.HEALTHY, 0.05, -0.05, composite_score=0.80)
    
    # Debe forzar inmediatamente AMARILLO / MONITOR
    assert state_veto == TrafficLightColor.YELLOW
    assert action_veto == ActionType.MONITOR

def test_human_dial_dynamic_threshold_tuning():
    dials = HumanControlDials(t_entry=0.45)
    sm = DecisionStateMachine(dials=dials)
    feats = make_strong_buy_features()

    # Score moderado 0.50 supera T_in 0.45 -> GREEN
    state1, _, _ = sm.evaluate(feats, HealthState.HEALTHY, 0.02, -0.02, composite_score=0.50)
    assert state1 == TrafficLightColor.GREEN

    # Operador sube el dial T_in a 0.60 en caliente (modo más conservador)
    dials.set_t_entry(0.60)
    sm.current_state = TrafficLightColor.YELLOW # Reset para probar entrada
    state2, _, _ = sm.evaluate(feats, HealthState.HEALTHY, 0.02, -0.02, composite_score=0.50)
    
    # Con el nuevo dial, el score 0.50 no es suficiente -> se queda en YELLOW
    assert state2 == TrafficLightColor.YELLOW

def test_spread_cost_friction_filter():
    dials = HumanControlDials(max_spread_friction_ratio=0.35)
    sm = DecisionStateMachine(dials=dials)
    
    # Spread anómalo gigante de 15.0 pips (noticia salvaje)
    feats_wide_spread = make_strong_buy_features(spread=15.0)
    state, action, reasons = sm.evaluate(feats_wide_spread, HealthState.HEALTHY, 0.01, -0.01, composite_score=0.70)
    
    # El filtro de fricción debe bloquear la entrada y forzar AMARILLO
    assert state == TrafficLightColor.YELLOW
    assert any("MONITOR_SPREAD_EXPANSION" in str(r) for r in reasons)
