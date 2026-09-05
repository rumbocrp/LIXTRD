"""Pruebas unitarias para el Filtro de Kalman Robusto y Adaptativo (Fase 1)."""

import pytest
from sistema_luces.quant.kalman import DynamicKalmanFilter

def test_kalman_huber_attenuation():
    kf = DynamicKalmanFilter(delta=1e-4, R_0=1e-2, c_huber=2.576)
    true_beta = 1.5
    
    # Entrenar modelo con datos limpios
    for i in range(40):
        kf.update(y=true_beta * float(i), x=float(i))
    
    # Inyectar error moderado (dentro de Huber pero mayor a 2.576 std)
    alpha_pre, beta_pre = kf.theta[0], kf.theta[1]
    _, beta_post, _ = kf.update(y=true_beta * 40.0 + 8.0, x=40.0)
    
    # El beta no debe saltar descontroladamente gracias a la atenuación Huber
    assert abs(beta_post - beta_pre) < 0.25

def test_kalman_mahalanobis_outlier_hard_rejection():
    kf = DynamicKalmanFilter(delta=1e-4, R_0=1e-2, gamma_mahalanobis=3.891)
    # Calibrar relación estable
    for i in range(40):
        kf.update(y=2.0 * float(i), x=float(i))
    
    beta_stable = kf.theta[1]
    
    # Inyectar outlier extremo (ej. error de cotización x100)
    _, beta_after_shock, z_score = kf.update(y=2.0 * 41.0 + 5000.0, x=41.0)
    
    # El estado no se corrompe porque la compuerta de Mahalanobis rechaza el tick
    assert abs(beta_after_shock - beta_stable) < 0.05
    assert z_score > 3.0

def test_kalman_mehra_variance_adaptation():
    kf = DynamicKalmanFilter(delta=1e-4, R_0=1e-2, R_min=1e-5)
    initial_R = kf.R
    
    # Inyectar ticks con mayor volatilidad de spread
    for i in range(30):
        noise = 0.5 if i % 2 == 0 else -0.5
        kf.update(y=1.0 * float(i) + noise, x=float(i))
        
    # La varianza R debe adaptarse al alza reflejando el mayor ruido observado
    assert kf.R > initial_R
