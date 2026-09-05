"""Servidor Web FastAPI y Hub de Telemetría de Alta Frecuencia para el Sistema de Luces 2.0 (Fase 6)."""

import asyncio
import time
from pathlib import Path
from typing import List, Dict, Any, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from sistema_luces.domain.vocabulary import HealthState, ActionType, TrafficLightColor
from sistema_luces.domain.models import DecisionLuzContract
from sistema_luces.domain.human_control import HumanControlDials
from sistema_luces.domain.strategy_registry import StrategyProfileRegistry
from sistema_luces.domain.strategy import StrategyDefinition
from sistema_luces.quant.engine import QuantitativeDecisionEngine
from sistema_luces.learning.evidence_treasury import EvidenceTreasury
from sistema_luces.learning.champion_gate import ChampionChallengerGate
from sistema_luces.storage.database import DecisionDatabase
from sistema_luces.simulation.runner import CrossAssetMarketSimulator
from sistema_luces.ui.templates import generate_console_html

app = FastAPI(title="Sistema de Luces 2.0 - Consola de Operaciones Cuantitativas")

# Instancias compartidas del sistema
db = DecisionDatabase(db_path="luces.db")
dials = HumanControlDials()
treasury = EvidenceTreasury(daily_loss_budget_usd=200.0)
champion_gate = ChampionChallengerGate(min_shadow_ticks=10_000)
strategy_registry = StrategyProfileRegistry(db=db)
simulator = CrossAssetMarketSimulator(db=db)

# Montar archivos estáticos
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# Modelos Pydantic para los endpoints
class DialsUpdateRequest(BaseModel):
    t_entry: Optional[float] = None
    t_exit: Optional[float] = None
    z_critical: Optional[float] = None
    ofi_critical: Optional[float] = None
    max_confidence_clamp: Optional[float] = None

class PromotionAuthorizeRequest(BaseModel):
    challenger_model_id: str
    timestamp_utc: int
    signature_hex: str

@app.get("/", response_class=HTMLResponse)
async def get_console():
    return HTMLResponse(content=generate_console_html())

@app.get("/api/state")
async def get_current_state(symbol: str = "XAUUSD"):
    engine = simulator.get_engine(symbol)
    latest = engine.last_decision
    if not latest:
        sim_res = simulator.step()
        latest = sim_res[symbol]["decision"]
    
    op_engine = simulator.get_operations_engine()
    active_op = simulator.get_active_operation(symbol)
    recent_ops = [op.to_dict() for op in op_engine.get_recent_operations(symbol, limit=10)]
    stats = db.get_simulated_operations_stats(symbol)
    
    pair_data = simulator.pairs.get(symbol, {})
    spread = pair_data.get("spread_base", 0.20)
    acute_res = op_engine.execution_engine.simulate_fill(
        direction="LONG" if latest.state == TrafficLightColor.GREEN else "SHORT",
        spread=spread,
        vpin=0.15,
        ofi=latest.ofi_imbalance_scaled / 10.0,
    )
    risk_metrics = op_engine.risk_engine.compute_risk_metrics(
        acute_result=acute_res,
        z_score=latest.kalman_z_score_scaled / 100.0,
        vpin=0.15,
        confidence_ppm=latest.confidence_score_ppm,
        open_operations=op_engine.get_open_operations(),
    )

    return {
        "decision": {
            "decision_id": latest.decision_id,
            "instrument": latest.instrument,
            "state": latest.state.value,
            "action": latest.action.value,
            "confidence_score_ppm": latest.confidence_score_ppm,
            "net_utility_long_ppm": latest.net_utility_long_ppm,
            "net_utility_short_ppm": latest.net_utility_short_ppm,
            "kalman_beta_scaled": latest.kalman_beta_scaled,
            "kalman_z_score_scaled": latest.kalman_z_score_scaled,
            "ofi_imbalance_scaled": latest.ofi_imbalance_scaled,
            "micro_price_mid_delta_ppm": latest.micro_price_mid_delta_ppm,
            "reason_codes": [r.value for r in latest.reason_codes],
            "data_health": latest.data_health.value,
            "timestamp_utc": latest.data_timestamp_utc,
        },
        "dials": dials.to_dict(),
        "treasury": treasury.get_status().__dict__,
        "simulated_risk_pct": risk_metrics.total_simulated_risk_pct,
        "risk_metrics": risk_metrics.to_dict(),
        "acute_spectrum": acute_res.to_dict(),
        "active_operation": active_op,
        "recent_operations": recent_ops,
        "simulated_stats": stats,
    }

@app.get("/api/simulation/operations")
async def get_simulation_operations(symbol: Optional[str] = None, limit: int = 50):
    ops = db.get_simulated_operations(instrument=symbol, limit=limit)
    stats = db.get_simulated_operations_stats(instrument=symbol)
    active = simulator.get_active_operation(symbol) if symbol else [op.to_dict() for op in simulator.operations_engine.get_open_operations()]
    return {
        "active": active,
        "history": ops,
        "stats": stats,
    }

@app.get("/api/simulation/risk")
async def get_simulation_risk(symbol: str = "XAUUSD"):
    state = await get_current_state(symbol=symbol)
    return {
        "instrument": symbol,
        "simulated_risk_pct": state["simulated_risk_pct"],
        "acute_spectrum": state["acute_spectrum"],
        "risk_metrics": state["risk_metrics"],
    }

@app.get("/api/dials")
async def get_dials():
    return dials.to_dict()

@app.post("/api/dials/update")
async def update_dials(req: DialsUpdateRequest):
    if req.t_entry is not None:
        dials.set_t_entry(req.t_entry)
    if req.t_exit is not None:
        dials.set_t_exit(req.t_exit)
    if req.z_critical is not None:
        dials.set_z_critical(req.z_critical)
    if req.ofi_critical is not None:
        dials.set_ofi_critical(req.ofi_critical)
    if req.max_confidence_clamp is not None:
        dials.set_confidence_clamp(req.max_confidence_clamp)
    return {"status": "SUCCESS", "dials": dials.to_dict()}

@app.post("/api/veto")
async def toggle_panic_veto():
    is_active = dials.toggle_hard_veto()
    return {"status": "SUCCESS", "is_hard_veto_active": is_active}

@app.get("/api/treasury")
async def get_treasury_status():
    return treasury.get_status().__dict__

@app.get("/api/operator/stats")
async def get_operator_stats():
    return db.get_operator_performance_by_setup()

@app.get("/api/strategies")
async def list_strategies():
    strats = strategy_registry.list_strategies()
    return [s.__dict__ for s in strats]

@app.post("/api/promotion/evaluate")
async def evaluate_promotion(
    champion_id: str = "model-kalman-ofi-bayesian-v2.0",
    challenger_id: str = "model-iql-student-jepa-v1.0"
):
    result = champion_gate.evaluate_promotion(champion_id, challenger_id)
    return result.__dict__

@app.post("/api/promotion/authorize")
async def authorize_promotion(req: PromotionAuthorizeRequest):
    is_valid = champion_gate.verify_operator_authorization_signature(
        challenger_model_id=req.challenger_model_id,
        timestamp_utc=req.timestamp_utc,
        signature_hex=req.signature_hex,
    )
    if not is_valid:
        raise HTTPException(status_code=403, detail="Firma criptográfica del operador inválida")
    
    # Promover modelo
    for pair in simulator.pairs.values():
        pair["engine"].champion_model_id = req.challenger_model_id
        
    return {
        "status": "PROMOTED_TO_PRODUCTION",
        "new_champion_model_id": req.challenger_model_id,
        "authorized_at_utc": int(time.time() * 1000)
    }

@app.get("/api/history")
async def get_history(limit: int = 20):
    return db.get_recent_transitions(limit=limit)

@app.websocket("/ws/telemetry")
async def websocket_telemetry_hub(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            # Flujo dinámico de alta velocidad (100ms -> 10 ticks por segundo con ráfagas)
            sim_res = simulator.step()
            active_sym = simulator.active_symbol
            tick_data = sim_res[active_sym]
            decision: DecisionLuzContract = tick_data["decision"]
            
            # Actualizar tesorería si es necesario
            t_status = treasury.get_status()
            if t_status.should_force_yellow_standby and not dials.is_hard_veto_active:
                dials.is_hard_veto_active = True

            payload = {
                "decision_id": decision.decision_id,
                "instrument": decision.instrument,
                "state": decision.state.value,
                "action": decision.action.value,
                "price_y": round(tick_data["price_y"], 2),
                "price_x": round(tick_data["price_x"], 2),
                "bid_p": round(tick_data["bid_p"], 2),
                "ask_p": round(tick_data["ask_p"], 2),
                "bid_v": round(tick_data["bid_v"], 1),
                "ask_v": round(tick_data["ask_v"], 1),
                "net_utility_long_ppm": decision.net_utility_long_ppm,
                "net_utility_short_ppm": decision.net_utility_short_ppm,
                "confidence_score_ppm": decision.confidence_score_ppm,
                "kalman_beta_scaled": decision.kalman_beta_scaled,
                "kalman_z_score_scaled": decision.kalman_z_score_scaled,
                "ofi_imbalance_scaled": decision.ofi_imbalance_scaled,
                "micro_price_mid_delta_ppm": decision.micro_price_mid_delta_ppm,
                "reason_codes": [r.value for r in decision.reason_codes],
                "data_health": decision.data_health.value,
                "timestamp_utc": decision.data_timestamp_utc,
                "dials": dials.to_dict(),
                "treasury": t_status.__dict__,
                "acute_spectrum": tick_data.get("acute_spectrum"),
                "simulated_risk_pct": tick_data.get("simulated_risk_pct"),
                "risk_metrics": tick_data.get("risk_metrics"),
                "active_operation": tick_data.get("active_operation"),
                "just_closed_operation": tick_data.get("just_closed_operation"),
            }
            await websocket.send_json(payload)
            await asyncio.sleep(0.10) # 100ms = 10 ticks por segundo
    except WebSocketDisconnect:
        pass
