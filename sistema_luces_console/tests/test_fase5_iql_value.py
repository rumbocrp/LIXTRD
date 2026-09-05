"""Pruebas unitarias para el motor de Valor y Q-Learning IQL (Fase 5)."""

import numpy as np
import pytest
from sistema_luces.learning.iql_engine import ImplicitQLearningValueNet, expectile_loss

def test_expectile_loss_asymmetry():
    # Error positivo +2.0 (peso tau = 0.75) vs Error negativo -2.0 (peso 1-tau = 0.25)
    loss_pos = expectile_loss(np.array([2.0]), tau=0.75)
    loss_neg = expectile_loss(np.array([-2.0]), tau=0.75)
    
    assert loss_pos == 0.75 * 4.0 # 3.0
    assert loss_neg == 0.25 * 4.0 # 1.0
    assert loss_pos == 3.0 * loss_neg

def test_iql_value_network_gradient_step():
    iql = ImplicitQLearningValueNet(state_dim=64, tau_expectile=0.75, learning_rate=0.05)
    s = np.random.randn(64)
    s_next = np.random.randn(64)
    
    # Entrenar un paso con recompensa positiva r = +1.0
    metrics = iql.train_step(s=s, a_idx=1, r=1.0, s_next=s_next, done=False)
    
    assert "loss_v" in metrics
    assert "loss_q1" in metrics
    assert "advantage" in metrics
    assert isinstance(metrics["loss_v"], float)
