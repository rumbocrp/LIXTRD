"""Pruebas unitarias para la Compuerta de Confluencia Bayesiana (Fase 2)."""

import pytest
from sistema_luces.quant.bayesian_gate import BayesianConfluenceGate
from sistema_luces.domain.models import QuantFeatures

def make_features(z_score=0.0, ofi=0.0, micro_delta=0.0, corr=0.85):
    mid = 2050.0
    return QuantFeatures(
        kalman_beta=-18.5,
        kalman_alpha=0.0,
        spread_z_score=z_score,
        order_flow_imbalance=ofi,
        mid_price=mid,
        micro_price=mid + micro_delta,
        cross_asset_correlation=corr,
        vpin_toxicity=0.10,
        spread_pips=0.20,
    )

def test_bayesian_confluence_strong_buy_boost():
    gate = BayesianConfluenceGate(base_prior_win_rate=0.50, z_critical=1.20, ofi_critical=20.0)
    
    # Condición de compra óptima con confluencia plena
    feats = make_features(z_score=-2.2, ofi=50.0, micro_delta=0.08, corr=-0.85)
    prob_long, odds_long, lrs = gate.evaluate_confluence(feats, direction="LONG")
    
    # Todas las verosimilitudes deben multiplicarse favorablemente
    assert lrs["lr_kalman"] > 1.5
    assert lrs["lr_ofi"] > 1.4
    assert lrs["lr_micro"] == 1.48
    assert lrs["composite_lr"] > 4.0
    assert prob_long > 0.80 # Probabilidad a posteriori > 80%

def test_bayesian_confluence_conflicting_signals_penalty():
    gate = BayesianConfluenceGate()
    
    # Z negativo (compra) pero OFI negativo (ventas descargando)
    feats = make_features(z_score=-2.0, ofi=-30.0, micro_delta=-0.05)
    prob_long, _, lrs = gate.evaluate_confluence(feats, direction="LONG")
    
    # La penalización por desacuerdo debe derribar la probabilidad
    assert lrs["lr_ofi"] < 0.60
    assert prob_long < 0.65
