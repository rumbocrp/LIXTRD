"""Pruebas unitarias para el Motor de Order Flow (OFI) y Micro-Price."""

import pytest
from sistema_luces.quant.order_flow import OrderFlowEngine

def test_order_flow_imbalance_bid_surge():
    engine = OrderFlowEngine()
    # Inicialización
    engine.compute(bid_p=100.0, bid_v=10.0, ask_p=100.1, ask_v=10.0)
    
    # Subida agresiva de volumen en Bid
    ofi, mid_p, micro_p, vpin = engine.compute(bid_p=100.0, bid_v=60.0, ask_p=100.1, ask_v=10.0)
    assert ofi == 50.0
    assert micro_p > mid_p # Presión compradora empuja el microprecio hacia el Ask

def test_micro_price_asymmetry():
    engine = OrderFlowEngine()
    engine.compute(bid_p=50.0, bid_v=10.0, ask_p=50.2, ask_v=10.0)
    
    # Mayor volumen en Ask -> microprecio presiona a la baja hacia el Bid
    _, mid_p, micro_p, _ = engine.compute(bid_p=50.0, bid_v=10.0, ask_p=50.2, ask_v=90.0)
    assert micro_p < mid_p
