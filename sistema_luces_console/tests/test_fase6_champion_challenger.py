"""Pruebas unitarias para la Puerta Campeón / Retador y Aprobación Criptográfica (Fase 6)."""

import time
import pytest
from sistema_luces.learning.champion_gate import ChampionChallengerGate

def test_champion_gate_rejects_insufficient_sample():
    gate = ChampionChallengerGate(min_shadow_ticks=10_000)
    
    # Registrar solo 50 ticks
    for _ in range(50):
        gate.record_shadow_tick(champion_pred=0.7, challenger_pred=0.8, actual_outcome=1.0)
        
    res = gate.evaluate_promotion("champ-v1", "chall-v1")
    assert res.is_ready_for_promotion is False
    assert "Muestra insuficiente" in res.rejection_reason

def test_champion_gate_diebold_mariano_statistical_superiority():
    # Probar con muestra sintética de 1,000 ticks para el test
    gate = ChampionChallengerGate(min_shadow_ticks=500, significance_level=0.01)
    
    # Simular retador con precisión claramente superior (menor error cuadrático)
    for _ in range(500):
        gate.record_shadow_tick(champion_pred=0.60, challenger_pred=0.90, actual_outcome=1.0)
        
    res = gate.evaluate_promotion("champ-v1", "chall-v1")
    assert res.is_statistically_superior is True
    assert res.p_value < 0.01
    assert res.is_ready_for_promotion is True

def test_operator_cryptographic_signature_authorization():
    gate = ChampionChallengerGate()
    ts = int(time.time() * 1000)
    model_id = "model-iql-student-jepa-v1.0"

    # Generar firma válida del operador
    valid_sig = gate.generate_authorization_signature(model_id, ts)
    assert gate.verify_operator_authorization_signature(model_id, ts, valid_sig) is True

    # Firma adulterada / inválida
    assert gate.verify_operator_authorization_signature(model_id, ts, "invalid-hex-signature-123") is False
