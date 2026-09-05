"""Pruebas unitarias para el motor de Order Flow Imbalance Multi-Nivel (Fase 1)."""

import pytest
from sistema_luces.quant.order_flow import MultiLevelOrderFlowEngine, StoikovMicroPriceEngine, VPINDetector

def test_multilevel_ofi_depth_decay_weighting():
    # 3 niveles de profundidad
    engine = MultiLevelOrderFlowEngine(num_levels=3, kappa=0.65)
    
    bids_t0 = [(100.0, 10.0), (99.9, 20.0), (99.8, 30.0)]
    asks_t0 = [(100.1, 10.0), (100.2, 20.0), (100.3, 30.0)]
    
    # Inicializar t0
    engine.compute(bids_t0, asks_t0)
    
    # t1: Subida de 50 contratos en Bid Nivel 1
    bids_t1 = [(100.0, 60.0), (99.9, 20.0), (99.8, 30.0)]
    ofi_lvl1, _, _, _ = engine.compute(bids_t1, asks_t0)
    
    # t2: Subida de 50 contratos en Bid Nivel 3 (debe tener menor impacto por el decaimiento kappa)
    bids_t2 = [(100.0, 60.0), (99.9, 20.0), (99.8, 80.0)]
    ofi_lvl3, _, _, _ = engine.compute(bids_t2, asks_t0)
    
    assert ofi_lvl1 > ofi_lvl3
    assert ofi_lvl1 > 0

def test_stoikov_microprice_queue_imbalance():
    # Bid con 90 contratos, Ask con 10 contratos -> Micro-Price se desplaza hacia el Ask
    mid, micro, delta_ppm = StoikovMicroPriceEngine.compute_level1(
        bid_p=2050.0, bid_v=90.0,
        ask_p=2050.2, ask_v=10.0
    )
    assert mid == 2050.10
    assert micro > mid
    assert delta_ppm > 0 # Desplazamiento positivo significativo

def test_vpin_toxicity_detection():
    vpin_detector = VPINDetector(num_buckets=10, bucket_volume=100.0)
    
    # Simular flujo altamente tóxico y unidireccional (compras masivas con saltos de precio)
    for _ in range(30):
        vpin_val = vpin_detector.update(trade_vol=50.0, delta_price=1.5)
        
    # El VPIN debe registrar toxicidad elevada
    assert vpin_val > 0.60
