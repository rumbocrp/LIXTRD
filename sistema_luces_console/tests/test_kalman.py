"""Pruebas unitarias para el Filtro de Kalman Dinámico 2D."""

import pytest
from sistema_luces.quant.kalman import DynamicKalmanFilter

def test_kalman_filter_convergence():
    kf = DynamicKalmanFilter(delta=1e-4, R=1e-2)
    true_beta = 2.5
    true_alpha = 10.0

    for i in range(100):
        x = float(i)
        noise = 0.05 if i % 2 == 0 else -0.05
        y = true_alpha + true_beta * x + noise
        alpha_est, beta_est, z_score = kf.update(y, x)

    # Debe converger cerca del beta verdadero
    assert abs(beta_est - true_beta) < 0.15
    assert isinstance(z_score, float)

def test_kalman_z_score_deviation():
    kf = DynamicKalmanFilter(delta=1e-4, R=1e-2)
    # Calibrar con relación lineal estable
    for i in range(50):
        kf.update(float(i), float(i))
    
    # Inyectar anomalía severa
    _, _, z_shock = kf.update(100.0, 50.0)
    assert z_shock > 2.0
