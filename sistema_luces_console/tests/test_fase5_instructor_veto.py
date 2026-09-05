"""Pruebas unitarias para el Guardián de Veto en Tiempo Real del Instructor (Fase 5)."""

import numpy as np
import pytest
from sistema_luces.domain.models import DecisionLuzContract, QuantFeatures
from sistema_luces.domain.vocabulary import TrafficLightColor, ActionType, HealthState, ReasonCode
from sistema_luces.learning.instructor_veto import InstructorVetoGuardrail

def make_teacher_contract(state: TrafficLightColor, action: ActionType):
    feats = QuantFeatures(
        kalman_beta=1.0, kalman_alpha=0.0, spread_z_score=0.0, order_flow_imbalance=0.0,
        mid_price=2050.0, micro_price=2050.0, cross_asset_correlation=0.0,
        vpin_toxicity=0.1, spread_pips=0.2,
    )
    return DecisionLuzContract.create(
        instrument="XAUUSD", timeframe="TICK",
        state=state, action=action,
        net_utility_long=0.0, net_utility_short=0.0,
        confidence_score=0.75, calibration_quality=0.9,
        features=feats, champion_model_id="teacher-v1",
        reason_codes=[], data_health=HealthState.HEALTHY,
    )

def test_veto_on_direct_conflict():
    guard = InstructorVetoGuardrail()
    # Profesor está en GREEN (Comprar)
    teacher = make_teacher_contract(TrafficLightColor.GREEN, ActionType.BUY)
    
    # Estudiante propone SELL (Vender) [p_hold, p_buy, p_sell]
    student_probs = np.array([0.10, 0.05, 0.85])
    
    state, action, reasons, was_vetoed = guard.evaluate_and_intercept(
        student_probs=student_probs, teacher_decision=teacher
    )
    
    # El guardián debe vetar de inmediato y forzar AMARILLO / MONITOR
    assert was_vetoed is True
    assert state == TrafficLightColor.YELLOW
    assert action == ActionType.MONITOR

def test_veto_on_uncertainty_in_teacher_yellow_zone():
    guard = InstructorVetoGuardrail(max_allowed_uncertainty=0.25)
    # Profesor en AMARILLO
    teacher = make_teacher_contract(TrafficLightColor.YELLOW, ActionType.MONITOR)
    
    # Estudiante con alta incertidumbre (40% de incertidumbre: max prob = 0.60)
    student_probs = np.array([0.20, 0.60, 0.20])
    
    state, action, _, was_vetoed = guard.evaluate_and_intercept(
        student_probs=student_probs, teacher_decision=teacher, student_advantage=0.05
    )
    
    # Debe ser vetado por superar el umbral de incertidumbre del 25%
    assert was_vetoed is True
    assert state == TrafficLightColor.YELLOW
    assert action == ActionType.MONITOR

def test_approved_passthrough_when_congruent():
    guard = InstructorVetoGuardrail()
    # Profesor y Estudiante ambos en GREEN (BUY) con alta certeza
    teacher = make_teacher_contract(TrafficLightColor.GREEN, ActionType.BUY)
    student_probs = np.array([0.05, 0.90, 0.05])
    
    state, action, _, was_vetoed = guard.evaluate_and_intercept(
        student_probs=student_probs, teacher_decision=teacher
    )
    
    assert was_vetoed is False
    assert state == TrafficLightColor.GREEN
    assert action == ActionType.BUY
