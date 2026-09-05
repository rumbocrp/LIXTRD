"""Pruebas unitarias para la Tesorería de Evidencia y Presupuesto de Riesgo (Fase 6)."""

import pytest
from sistema_luces.learning.evidence_treasury import EvidenceTreasury

def test_evidence_treasury_risk_budget_exhaustion():
    treasury = EvidenceTreasury(daily_loss_budget_usd=200.0)
    
    # Pérdida de $120
    treasury.record_pnl(-120.0)
    status1 = treasury.get_status()
    assert status1.is_risk_budget_exhausted is False
    assert status1.remaining_budget_usd == 80.0

    # Pérdida adicional de $90 (total $210 > $200)
    treasury.record_pnl(-90.0)
    status2 = treasury.get_status()
    assert status2.is_risk_budget_exhausted is True
    assert status2.remaining_budget_usd == 0.0
    assert status2.should_force_yellow_standby is True

def test_evidence_token_consumption_limits():
    treasury = EvidenceTreasury(max_daily_evidence_tokens=3)
    assert treasury.consume_evidence_token() is True
    assert treasury.consume_evidence_token() is True
    assert treasury.consume_evidence_token() is True
    # Cuarto intento debe ser denegado para evitar sobreajuste
    assert treasury.consume_evidence_token() is False

def test_brier_score_degradation_alarm():
    treasury = EvidenceTreasury(brier_alarm_threshold=0.165)
    
    # Inyectar 10 predicciones totalmente erradas (p=0.9 pero resultado=0 -> BS=0.81)
    for _ in range(10):
        treasury.record_prediction_outcome(predicted_prob=0.90, actual_win=False)
        
    status = treasury.get_status()
    assert status.rolling_brier_score > 0.165
    assert status.is_brier_score_degraded is True
    assert status.should_force_yellow_standby is True
