"""Pruebas unitarias para la Destilación de Políticas AWBC (Fase 5)."""

import numpy as np
import pytest
from sistema_luces.learning.policy_distillation import AdvantageWeightedPolicy

def test_awbc_policy_advantage_weighting():
    policy = AdvantageWeightedPolicy(state_dim=64, temperature_beta=1.50, lambda_kl_teacher=0.10)
    s = np.random.randn(64)
    
    teacher_dist = np.array([0.10, 0.85, 0.05]) # Profesor indica compra clara
    
    # Entrenar con ventaja fuertemente positiva A = +3.0
    metrics = policy.train_step(s=s, a_idx=1, advantage=3.0, teacher_distribution=teacher_dist)
    
    assert metrics["weight_adv"] > 1.0 # exp(3.0 / 1.5) = exp(2.0) ≈ 7.38
    assert metrics["kl_divergence"] >= 0.0

def test_awbc_policy_kl_regularization_anchor():
    policy = AdvantageWeightedPolicy(state_dim=64, lambda_kl_teacher=0.50, learning_rate=0.1)
    s = np.random.randn(64)
    teacher_dist = np.array([0.05, 0.90, 0.05]) # Compra casi unánime del profesor
    
    # Entrenar múltiples pasos anclando la distribución al profesor
    for _ in range(25):
        policy.train_step(s=s, a_idx=1, advantage=1.5, teacher_distribution=teacher_dist)
        
    probs = policy.predict_probabilities(s)[0]
    # La probabilidad de BUY (idx 1) debe ser dominante gracias a la destilación
    assert probs[1] > 0.60
