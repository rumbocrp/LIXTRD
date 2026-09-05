"""Pruebas de integración del motor cuantitativo y persistencia SQLite."""

import os
import pytest
from sistema_luces.quant.engine import QuantitativeDecisionEngine
from sistema_luces.storage.database import DecisionDatabase
from sistema_luces.domain.vocabulary import HealthState, TrafficLightColor

def test_engine_tick_processing_and_storage(tmp_path):
    db_file = str(tmp_path / "test_luces.db")
    db = DecisionDatabase(db_path=db_file)
    engine = QuantitativeDecisionEngine(instrument="XAUUSD")

    # Inyectar 10 ticks
    for i in range(10):
        decision = engine.process_tick(
            bid_p=2050.0 + i * 0.1,
            bid_v=25.0,
            ask_p=2050.2 + i * 0.1,
            ask_v=25.0,
            cross_asset_price=104.0 + i * 0.05,
            source_ts=1700000000000 + i * 150,
            health=HealthState.HEALTHY,
        )
        db.save_decision(decision)

    history = db.get_recent_transitions(limit=10)
    assert len(history) == 10
    assert history[0]["instrument"] == "XAUUSD"
    assert history[0]["state"] in ["GREEN", "YELLOW", "RED"]
