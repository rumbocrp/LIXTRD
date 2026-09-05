"""Pruebas Cuantitativas y de Integración del Espectro Agudo de Ejecución y Operativas Simuladas."""

import os
import time
import pytest
import numpy as np
from fastapi.testclient import TestClient

from sistema_luces.domain.vocabulary import TrafficLightColor, ActionType, HealthState
from sistema_luces.domain.operator_trade import TradeDirection
from sistema_luces.domain.models import DecisionLuzContract, QuantFeatures
from sistema_luces.domain.simulated_trade import SimulatedOperation, AcuteExecutionResult, SimulatedRiskMetrics
from sistema_luces.quant.execution_spectrum import AcuteExecutionSpectrumEngine
from sistema_luces.quant.simulated_risk import SimulatedRiskEngine
from sistema_luces.simulation.operations_engine import SimulatedOperationsEngine
from sistema_luces.simulation.runner import CrossAssetMarketSimulator
from sistema_luces.storage.database import DecisionDatabase
from sistema_luces.ui.server import app
from sistema_luces.ui.templates import render_industrial_console_html

client = TestClient(app)

def test_acute_execution_spectrum_levels():
    """Verifica el barrido multi-nivel en el libro L2 y la penalización no lineal por selección adversa."""
    engine = AcuteExecutionSpectrumEngine(eta_friction=0.20)
    
    # 5 niveles de Asks: [(precio, volumen)]
    asks_depth = [
        (2050.20, 5.0),   # Nivel 1: 5 unidades a 2050.20
        (2050.40, 10.0),  # Nivel 2: 10 unidades a 2050.40
        (2050.70, 20.0),  # Nivel 3: 20 unidades a 2050.70
        (2051.10, 30.0),  # Nivel 4: 30 unidades a 2051.10
        (2051.60, 50.0),  # Nivel 5: 50 unidades a 2051.60
    ]
    bids_depth = [
        (2050.00, 5.0),
        (2049.80, 10.0),
        (2049.50, 20.0),
        (2049.10, 30.0),
        (2048.60, 50.0),
    ]

    # 1. Ejecución pequeña (tamaño = 4u): cabe en nivel 1
    res_small = engine.simulate_fill(
        direction="LONG",
        spread=0.20,
        vpin=0.10,
        ofi=5.0,
        asks_depth=asks_depth,
        size=4.0,
    )
    assert res_small.direction == "LONG"
    assert res_small.nominal_price == 2050.20
    assert res_small.book_depth_slippage == 0.0 # No penetra niveles profundos
    assert res_small.spectrum_tier in ["OPTIMAL_TOUCH", "MODERATE_SLIP"]

    # 2. Ejecución profunda (tamaño = 25u): barre niveles 1, 2 y 3
    res_deep = engine.simulate_fill(
        direction="LONG",
        spread=0.20,
        vpin=0.85, # Flujo altamente tóxico
        ofi=-25.0, # Fuerte presión contraria
        asks_depth=asks_depth,
        size=25.0,
    )
    assert res_deep.book_depth_slippage > 0.0 # Penetra en el libro
    assert res_deep.effective_fill_price > res_small.effective_fill_price
    assert res_deep.adverse_selection_slippage > res_small.adverse_selection_slippage
    assert res_deep.spectrum_sharpness_score > res_small.spectrum_sharpness_score
    assert res_deep.spectrum_tier in ["DEEP_SWEEP", "ACUTE_ADVERSE"]

    # 3. Ejecución SHORT
    res_short = engine.simulate_fill(
        direction="SHORT",
        spread=0.20,
        vpin=0.20,
        ofi=-10.0,
        bids_depth=bids_depth,
        size=10.0,
    )
    assert res_short.direction == "SHORT"
    assert res_short.effective_fill_price <= 2050.00

def test_simulated_risk_engine_metrics():
    """Verifica el cálculo de riesgo instantáneo, asignación de posición y VaR/CVaR 95% mediante NumPy."""
    risk_engine = SimulatedRiskEngine(base_position_risk_pct=1.50)
    exec_engine = AcuteExecutionSpectrumEngine()

    acute_res = exec_engine.simulate_fill(
        direction="LONG",
        spread=0.20,
        vpin=0.25,
        ofi=10.0,
    )

    # 1. Cálculo inicial sin historial
    metrics = risk_engine.compute_risk_metrics(
        acute_result=acute_res,
        z_score=-1.5,
        vpin=0.25,
        confidence_ppm=750_000,
        open_operations=[],
    )
    assert 0.0 <= metrics.total_simulated_risk_pct <= 100.0
    assert 0.5 <= metrics.position_risk_pct <= 3.0
    assert metrics.rolling_simulated_var_95_pct > 0.0
    assert metrics.rolling_simulated_cvar_95_pct >= metrics.rolling_simulated_var_95_pct

    # 2. Registrar historial de 20 operaciones (distribución de retornos)
    for i in range(20):
        op = SimulatedOperation.create(
            instrument="XAUUSD",
            direction=TradeDirection.LONG,
            entry_price=2050.0,
            stop_loss_price=2048.0,
            take_profit_price=2054.0,
            size=1.0,
        )
        # Ganancia o pérdida alternada
        ret = 0.80 if i % 2 == 0 else -0.50
        exit_p = 2050.0 + (ret * 20.5)
        op.close(exit_price=exit_p)
        risk_engine.record_closed_operation(op)

    metrics_updated = risk_engine.compute_risk_metrics(
        acute_result=acute_res,
        z_score=-1.8,
        vpin=0.30,
        confidence_ppm=850_000,
        open_operations=[],
    )
    assert metrics_updated.total_trades_count == 20
    assert metrics_updated.win_rate_pct == 50.0
    assert metrics_updated.profit_factor > 0.0
    assert metrics_updated.rolling_simulated_var_95_pct > 0.0

def test_simulated_operations_lifecycle(tmp_path):
    """Verifica el ciclo completo de apertura, flotante y cierre de una operativa simulada bajo el semáforo."""
    db_file = str(tmp_path / "test_lifecycle.db")
    db = DecisionDatabase(db_path=db_file)
    op_engine = SimulatedOperationsEngine(db=db)

    # Crear características de prueba
    features = QuantFeatures(
        kalman_beta=-18.5,
        kalman_alpha=0.0,
        spread_z_score=-1.5,
        order_flow_imbalance=25.0,
        mid_price=2050.0,
        micro_price=2050.3,
        cross_asset_correlation=-0.85,
        vpin_toxicity=0.15,
        spread_pips=0.20,
    )

    # Decisión VERDE (BUY)
    dec_green = DecisionLuzContract.create(
        instrument="XAUUSD",
        timeframe="TICK",
        state=TrafficLightColor.GREEN,
        action=ActionType.BUY,
        net_utility_long=0.0025,
        net_utility_short=-0.0010,
        confidence_score=0.78,
        calibration_quality=0.92,
        features=features,
        champion_model_id="kalman-v2",
        reason_codes=[],
        data_health=HealthState.HEALTHY,
    )

    # 1. Tick con VERDE -> Debe abrir posición LONG
    active_op, closed_op, acute_res, risk_metrics = op_engine.on_tick(
        instrument="XAUUSD",
        decision=dec_green,
        bid_p=2049.90,
        ask_p=2050.10,
        features=features,
    )
    assert active_op is not None
    assert active_op.direction == TradeDirection.LONG
    assert active_op.status == "OPEN"
    assert active_op.entry_price >= 2050.10 # Precio agudo incluye Ask + fricción
    assert closed_op is None

    # 2. Tick siguiente con precio más alto dentro del rango (flotante positivo)
    active_op, closed_op, _, _ = op_engine.on_tick(
        instrument="XAUUSD",
        decision=dec_green,
        bid_p=2050.40,
        ask_p=2050.60,
        features=features,
    )
    assert active_op is not None
    assert active_op.pnl_usd > 0.0

    # 3. Decisión AMARILLO (STANDBY) -> Debe cerrar la posición
    dec_yellow = DecisionLuzContract.create(
        instrument="XAUUSD",
        timeframe="TICK",
        state=TrafficLightColor.YELLOW,
        action=ActionType.MONITOR,
        net_utility_long=0.0,
        net_utility_short=0.0,
        confidence_score=0.50,
        calibration_quality=0.90,
        features=features,
        champion_model_id="kalman-v2",
        reason_codes=[],
        data_health=HealthState.HEALTHY,
    )
    active_op, closed_op, _, _ = op_engine.on_tick(
        instrument="XAUUSD",
        decision=dec_yellow,
        bid_p=2050.60,
        ask_p=2050.80,
        features=features,
    )
    assert active_op is None
    assert closed_op is not None
    assert closed_op.status == "CLOSED"
    assert closed_op.close_reason == "SIGNAL_STANDBY"
    assert closed_op.pnl_usd > 0.0
    assert closed_op.r_multiple > 0.0

    # Verificar persistencia en base de datos
    saved_ops = db.get_simulated_operations(instrument="XAUUSD")
    assert len(saved_ops) >= 1
    assert saved_ops[0]["status"] == "CLOSED"
    assert saved_ops[0]["pnl_usd"] > 0.0

def test_database_persistence_and_stats(tmp_path):
    """Verifica el guardado y consulta de estadísticas de operativas simuladas en SQLite."""
    db_file = str(tmp_path / "test_db_stats.db")
    db = DecisionDatabase(db_path=db_file)

    op1 = SimulatedOperation.create(
        instrument="TSLA",
        direction=TradeDirection.LONG,
        entry_price=220.00,
        stop_loss_price=218.00,
        take_profit_price=224.00,
        size=2.0,
        simulated_risk_pct=15.2,
    )
    op1.close(exit_price=223.00, close_reason="TAKE_PROFIT_HIT")
    db.save_simulated_operation(op1)

    op2 = SimulatedOperation.create(
        instrument="TSLA",
        direction=TradeDirection.SHORT,
        entry_price=222.00,
        stop_loss_price=224.00,
        take_profit_price=218.00,
        size=2.0,
        simulated_risk_pct=22.8,
    )
    op2.close(exit_price=223.50, close_reason="STOP_LOSS_HIT")
    db.save_simulated_operation(op2)

    stats = db.get_simulated_operations_stats(instrument="TSLA")
    assert stats["total_operations"] == 2
    assert stats["wins"] == 1
    assert stats["losses"] == 1
    assert stats["win_rate_pct"] == 50.0

def test_api_state_and_simulation_endpoints():
    """Verifica que /api/state y las nuevas rutas /api/simulation devuelvan métricas completas."""
    # 1. /api/state
    res_state = client.get("/api/state?symbol=XAUUSD")
    assert res_state.status_code == 200
    data_state = res_state.json()
    assert "decision" in data_state
    assert "dials" in data_state
    assert "treasury" in data_state
    assert "simulated_risk_pct" in data_state
    assert "acute_spectrum" in data_state
    assert "risk_metrics" in data_state
    assert "active_operation" in data_state
    assert "recent_operations" in data_state
    assert 0.0 <= data_state["simulated_risk_pct"] <= 100.0

    # 2. /api/simulation/operations
    res_ops = client.get("/api/simulation/operations?symbol=XAUUSD")
    assert res_ops.status_code == 200
    data_ops = res_ops.json()
    assert "active" in data_ops
    assert "history" in data_ops
    assert "stats" in data_ops

    # 3. /api/simulation/risk
    res_risk = client.get("/api/simulation/risk?symbol=XAUUSD")
    assert res_risk.status_code == 200
    data_risk = res_risk.json()
    assert data_risk["instrument"] == "XAUUSD"
    assert "simulated_risk_pct" in data_risk
    assert "acute_spectrum" in data_risk
    assert "risk_metrics" in data_risk

def test_anti_ai_slop_compliance_with_new_markup():
    """Garantiza cumplimiento estricto del estándar Anti-AI Slop con los nuevos componentes."""
    html = render_industrial_console_html()
    # Sin emojis
    import re
    emoji_pattern = re.compile(
        r"[\U0001F300-\U0001F6FF\U0001F900-\U0001F9FF\U0001F600-\U0001F64F\U0001F680-\U0001F6FF\U00002600-\U000026FF\U00002700-\U000027BF]"
    )
    assert len(emoji_pattern.findall(html)) == 0
    # Elementos de riesgo y operativas simuladas
    assert "val-simulated-risk-pct" in html
    assert "badge-risk-tier" in html
    assert "val-sim-op-status" in html
    assert "val-sim-op-pnl" in html
    assert "tabular-nums" in html
