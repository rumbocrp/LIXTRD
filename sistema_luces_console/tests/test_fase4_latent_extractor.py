"""Pruebas unitarias para el Extractor de Estados Latentes en Tiempo Real (Fase 4)."""

import time
import numpy as np
import pytest
from sistema_luces.domain.models import QuantFeatures
from sistema_luces.learning.latent_extractor import LatentStateExtractor

def make_dummy_features(i: int):
    mid = 2050.0 + float(i) * 0.1
    return QuantFeatures(
        kalman_beta=-18.5,
        kalman_alpha=0.0,
        spread_z_score=float(i % 5) - 2.0,
        order_flow_imbalance=float(i * 5 - 20),
        mid_price=mid,
        micro_price=mid + 0.05,
        cross_asset_correlation=-0.80,
        vpin_toxicity=0.15,
        spread_pips=0.20,
    )

def test_latent_extractor_inference_speed_and_shape():
    extractor = LatentStateExtractor()
    
    # Warmup
    for i in range(10):
        extractor.push_features(make_dummy_features(i))
        
    # Medir latencia de inferencia
    start_t = time.perf_counter()
    z_latent = extractor.push_features(make_dummy_features(11), return_pct=0.0005)
    duration_ms = (time.perf_counter() - start_t) * 1000.0
    
    assert z_latent.shape == (256,)
    # Presupuesto de latencia: debe ejecutarse en menos de 1.5ms
    assert duration_ms < 1.5

def test_latent_non_collapse_rank_check():
    extractor = LatentStateExtractor()
    embeddings = []
    
    # Generar 50 embeddings con datos dinámicos
    for i in range(50):
        z = extractor.push_features(make_dummy_features(i), return_pct=0.0001 * (i % 3))
        embeddings.append(z)
        
    matrix = np.array(embeddings)
    # Matriz de covarianza de dimensión (256, 256)
    cov = np.cov(matrix, rowvar=False)
    
    # La traza de covarianza debe ser positiva y los valores singulares no nulos
    singular_values = np.linalg.svd(cov, compute_uv=False)
    effective_rank = np.sum(singular_values > 1e-6)
    
    # No hay colapso dimensional: el rango efectivo debe ser amplio
    assert effective_rank >= 8

def test_compact_latent_summary_scaling():
    extractor = LatentStateExtractor()
    z = extractor.push_features(make_dummy_features(1))
    summary_32 = extractor.get_compact_latent_summary(z, summary_dim=32)
    
    assert len(summary_32) == 32
    assert all(isinstance(val, int) for val in summary_32)
    # Verificar que los valores en PPM están dentro del rango [-1_000_000, +1_000_000]
    assert all(-1_000_000 <= val <= 1_000_000 for val in summary_32)
