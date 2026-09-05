"""Pruebas de integración para los Endpoints de la API y Control Humano (Fase 6)."""

import time
import pytest
from fastapi.testclient import TestClient
from sistema_luces.ui.server import app, champion_gate

client = TestClient(app)

def test_api_get_state_and_dials():
    res = client.get("/api/state")
    assert res.status_code == 200
    data = res.json()
    assert "decision" in data
    assert "dials" in data
    assert "treasury" in data

def test_api_update_dials_and_veto():
    # 1. Actualizar diales
    res_dial = client.post("/api/dials/update", json={"t_entry": 0.55, "z_critical": 1.5})
    assert res_dial.status_code == 200
    data_dial = res_dial.json()
    assert data_dial["dials"]["t_entry"] == 0.55
    assert data_dial["dials"]["z_critical"] == 1.5

    # 2. Conmutar Hard Veto
    res_veto = client.post("/api/veto")
    assert res_veto.status_code == 200
    assert "is_hard_veto_active" in res_veto.json()

def test_api_promotion_cryptographic_authorization():
    ts = int(time.time() * 1000)
    challenger_id = "model-iql-student-jepa-v1.0"
    valid_sig = champion_gate.generate_authorization_signature(challenger_id, ts)

    # Intento con firma válida
    res_auth = client.post("/api/promotion/authorize", json={
        "challenger_model_id": challenger_id,
        "timestamp_utc": ts,
        "signature_hex": valid_sig,
    })
    assert res_auth.status_code == 200
    assert res_auth.json()["status"] == "PROMOTED_TO_PRODUCTION"

    # Intento con firma inválida
    res_bad = client.post("/api/promotion/authorize", json={
        "challenger_model_id": challenger_id,
        "timestamp_utc": ts,
        "signature_hex": "bad-signature",
    })
    assert res_bad.status_code == 403
