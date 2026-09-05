"""Pruebas unitarias para la Arquitectura I-JEPA & Barlow Twins (Fase 4)."""

import time
import numpy as np
import pytest
from sistema_luces.learning.jepa_encoder import MarketTimeSeriesJEPA, BarlowTwinsLoss

def test_barlow_twins_loss_computation():
    loss_fn = BarlowTwinsLoss(latent_dim=64, lambda_offdiag=5e-3)
    
    # 1. Caso de representaciones idénticas e independientes (pérdida mínima)
    z_a = np.random.randn(32, 64)
    z_b = z_a + np.random.randn(32, 64) * 0.01
    
    total_loss, on_diag, off_diag = loss_fn.compute_loss(z_a, z_b)
    assert on_diag < 10.0
    assert total_loss >= 0.0

def test_jepa_encoder_shape_and_normalization():
    jepa = MarketTimeSeriesJEPA(input_features=8, latent_dim=256)
    dummy_sequence = np.random.randn(10, 8)
    
    z_context = jepa.encode_context(dummy_sequence)
    assert z_context.shape == (1, 256)
    
    # Debe tener norma L2 unitaria
    norm = np.linalg.norm(z_context)
    assert abs(norm - 1.0) < 1e-4

def test_jepa_target_ema_schedule():
    jepa = MarketTimeSeriesJEPA(ema_alpha_0=0.996, ema_alpha_max=0.9999)
    
    # Paso 1: alpha debe estar cerca de alpha_0
    alpha_1 = jepa.update_target_ema(max_steps=100)
    assert alpha_1 >= 0.996
    
    # Avanzar 100 pasos: alpha debe converger hacia alpha_max
    for _ in range(99):
        alpha_final = jepa.update_target_ema(max_steps=100)
        
    assert abs(alpha_final - 0.9999) < 1e-4
