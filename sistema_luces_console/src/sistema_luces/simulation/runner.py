"""Simulador Estocástico de Microestructura L2 de Alta Energía y Flujo Institucional en Ráfagas."""

import math
import random
import time
from typing import Dict, Any, Callable, Optional, List, Tuple
from sistema_luces.domain.models import DecisionLuzContract
from sistema_luces.domain.vocabulary import HealthState
from sistema_luces.quant.engine import QuantitativeDecisionEngine
from sistema_luces.simulation.operations_engine import SimulatedOperationsEngine

class CrossAssetMarketSimulator:
    """Genera procesos estocásticos de mercado con ráfagas institucionales (Hawkes) y saltos de libro L2."""
    def __init__(self, db: Optional[Any] = None):
        self.db = db
        self.operations_engine = SimulatedOperationsEngine(db=db)
        self.pairs: Dict[str, Dict[str, Any]] = {
            "XAUUSD": {
                "name": "GOLD / DXY (Macro)",
                "engine": QuantitativeDecisionEngine(instrument="XAUUSD", champion_model_id="kalman-macro-bayesian-v2.0"),
                "price_y": 2050.40,
                "price_x": 104.25,
                "true_beta": -18.5,
                "spread_base": 0.20,
                "momentum": 0.0,
                "burst_counter": 0,
                "burst_direction": 1,
            },
            "TSLA": {
                "name": "SP500 / TSLA (Momentum)",
                "engine": QuantitativeDecisionEngine(instrument="TSLA", champion_model_id="kalman-momentum-bayesian-v2.0"),
                "price_y": 218.50,
                "price_x": 5012.00,
                "true_beta": 0.045,
                "spread_base": 0.05,
                "momentum": 0.0,
                "burst_counter": 0,
                "burst_direction": 1,
            },
            "AAPL": {
                "name": "SP500 / AAPL (Ancla)",
                "engine": QuantitativeDecisionEngine(instrument="AAPL", champion_model_id="kalman-anchor-bayesian-v2.0"),
                "price_y": 184.30,
                "price_x": 5012.00,
                "true_beta": 0.037,
                "spread_base": 0.04,
                "momentum": 0.0,
                "burst_counter": 0,
                "burst_direction": 1,
            }
        }
        self.active_symbol = "XAUUSD"

    def get_engine(self, symbol: Optional[str] = None) -> QuantitativeDecisionEngine:
        sym = symbol or self.active_symbol
        return self.pairs[sym]["engine"]

    def set_active_symbol(self, symbol: str) -> None:
        if symbol in self.pairs:
            self.active_symbol = symbol

    def step(self) -> Dict[str, Any]:
        """Avanza 1 tick de simulación estocástica en alta resolución con ráfagas institucionales."""
        now_ms = int(time.time() * 1000)
        
        # 1. Macro shocks estocásticos
        dxy_ret = random.gauss(-0.00003, 0.0020)
        sp500_ret = random.gauss(0.00004, 0.0030)

        self.pairs["XAUUSD"]["price_x"] *= (1.0 + dxy_ret)
        self.pairs["TSLA"]["price_x"] *= (1.0 + sp500_ret)
        self.pairs["AAPL"]["price_x"] = self.pairs["TSLA"]["price_x"]

        results = {}

        for sym, data in self.pairs.items():
            beta = data["true_beta"]
            engine: QuantitativeDecisionEngine = data["engine"]

            # Generador de ráfagas institucionales (Hawkes process simulator)
            if data["burst_counter"] <= 0:
                if random.random() < 0.12: # 12% probabilidad de iniciar ráfaga de barrido
                    data["burst_counter"] = random.randint(8, 25) # 8 a 25 ticks consecutivos de presión
                    data["burst_direction"] = 1 if random.random() > 0.50 else -1
                    data["momentum"] = data["burst_direction"] * random.uniform(0.6, 1.8)
                else:
                    data["momentum"] *= 0.85 # Decaimiento natural
            else:
                data["burst_counter"] -= 1

            # Shock de precio con momentum de microestructura
            shock = data["momentum"] + random.gauss(0, 0.35)
            
            if sym == "XAUUSD":
                data["price_y"] += beta * (data["price_x"] * dxy_ret * 1.5) + (shock * 0.40)
            elif sym == "TSLA":
                data["price_y"] += beta * (data["price_x"] * sp500_ret * 2.5) + (shock * 0.25)
            else: # AAPL
                data["price_y"] += beta * (data["price_x"] * sp500_ret * 1.2) + (shock * 0.10)

            mid = data["price_y"]
            spread = data["spread_base"] * (1.0 + random.uniform(0.0, 0.25))
            spread_half = spread / 2.0
            bid_p = mid - spread_half
            ask_p = mid + spread_half

            # Generar profundidad de 5 niveles del libro L2 con sesgo institucional en ráfaga
            bids_l: List[Tuple[float, float]] = []
            asks_l: List[Tuple[float, float]] = []

            for k in range(5):
                level_spread = k * (spread * 0.8)
                bp = bid_p - level_spread
                ap = ask_p + level_spread
                
                # Desbalance agresivo en función de la ráfaga
                if data["burst_direction"] > 0:
                    bv = random.uniform(40.0, 120.0) * math.exp(-0.3 * k)
                    av = random.uniform(10.0, 45.0) * math.exp(-0.3 * k)
                else:
                    bv = random.uniform(10.0, 45.0) * math.exp(-0.3 * k)
                    av = random.uniform(40.0, 120.0) * math.exp(-0.3 * k)

                bids_l.append((bp, round(bv, 1)))
                asks_l.append((ap, round(av, 1)))

            decision = engine.process_tick(
                bid_p=bid_p,
                bid_v=bids_l[0][1],
                ask_p=ask_p,
                ask_v=asks_l[0][1],
                cross_asset_price=data["price_x"],
                source_ts=now_ms,
                health=HealthState.HEALTHY,
                bids_depth=bids_l,
                asks_depth=asks_l,
            )

            # 2. Ejecución simulada con espectro agudo y medición de riesgo simulado
            active_op, just_closed_op, acute_spectrum, risk_metrics = self.operations_engine.on_tick(
                instrument=sym,
                decision=decision,
                bid_p=bid_p,
                ask_p=ask_p,
                bids_depth=bids_l,
                asks_depth=asks_l,
            )

            results[sym] = {
                "pair_name": data["name"],
                "decision": decision,
                "price_y": data["price_y"],
                "price_x": data["price_x"],
                "bid_p": bid_p,
                "bid_v": bids_l[0][1],
                "ask_p": ask_p,
                "ask_v": asks_l[0][1],
                "bids_depth": bids_l,
                "asks_depth": asks_l,
                "acute_spectrum": acute_spectrum.to_dict(),
                "simulated_risk_pct": risk_metrics.total_simulated_risk_pct,
                "risk_metrics": risk_metrics.to_dict(),
                "active_operation": active_op.to_dict() if active_op else None,
                "just_closed_operation": just_closed_op.to_dict() if just_closed_op else None,
            }

        return results

    def get_operations_engine(self) -> SimulatedOperationsEngine:
        return self.operations_engine

    def get_active_operation(self, symbol: Optional[str] = None) -> Optional[Dict[str, Any]]:
        sym = (symbol or self.active_symbol).upper()
        op = self.operations_engine.active_positions.get(sym)
        return op.to_dict() if op else None

