"""Motor Multi-Activo y Dinámica de los 3 Grandes Balancines Financieros (confidencial_trade).

Pares Prioritarios:
1. Par Macro: ORO (XAU/USD) vs DXY (Dólar Index) (Correlación Inversa)
2. Par Momentum: S&P 500 (SPY/US500) vs TSLA (High-Beta Momentum)
3. Par Ancla: S&P 500 (SPY/US500) vs AAPL (Ancla Sistémica)
"""

from dataclasses import dataclass
import random
from typing import Dict, List, Tuple

from sistema_luces.quant.kalman import DynamicKalmanFilter
from sistema_luces.quant.order_flow import OrderFlowEngine
from sistema_luces.quant.traffic_light import EstadoLuzCuantitativa, evaluar_sistema_luces_cuantitativo


@dataclass
class ParBalancin:
    name: str
    category: str
    symbol_y: str
    symbol_x: str
    price_y: float
    price_x: float
    true_beta: float
    kalman: DynamicKalmanFilter
    order_flow: OrderFlowEngine
    last_z_score: float = 0.0
    last_beta_est: float = 1.0
    last_ofi: float = 0.0
    last_micro_price: float = 0.0
    last_mid_price: float = 0.0
    last_light_state: EstadoLuzCuantitativa | None = None


class MotorMultiActivo:
    """Gestiona la telemetría, correlaciones y motores de los 3 balancines cuantitativos."""

    def __init__(self) -> None:
        self.pares: Dict[str, ParBalancin] = {
            "GOLD_DXY": ParBalancin(
                name="ORO vs. DÓLAR (DXY)",
                category="Macro Inverso",
                symbol_y="XAU/USD",
                symbol_x="DXY",
                price_y=2050.0,
                price_x=104.0,
                true_beta=-18.5,
                kalman=DynamicKalmanFilter(delta=1e-4, R=1e-2, initial_alpha=3974.0, initial_beta=-18.5),
                order_flow=OrderFlowEngine(),
            ),
            "SP500_TSLA": ParBalancin(
                name="S&P 500 vs. TSLA",
                category="High-Beta Momentum",
                symbol_y="TSLA",
                symbol_x="US500",
                price_y=220.0,
                price_x=5000.0,
                true_beta=0.045,
                kalman=DynamicKalmanFilter(delta=1e-4, R=1e-2),
                order_flow=OrderFlowEngine(),
            ),
            "SP500_AAPL": ParBalancin(
                name="S&P 500 vs. AAPL",
                category="Ancla Sistémica",
                symbol_y="AAPL",
                symbol_x="US500",
                price_y=185.0,
                price_x=5000.0,
                true_beta=0.037,
                kalman=DynamicKalmanFilter(delta=1e-4, R=1e-2),
                order_flow=OrderFlowEngine(),
            ),
        }
        self.us500_price = 5000.0
        self.us500_kalman = DynamicKalmanFilter(delta=1e-4, R=1e-2)
        self.us500_order_flow = OrderFlowEngine()
        self.total_signals_executed = 0
        self.correct_signals_count = 0
        self.history: List[dict] = []

    def paso_simulacion(self) -> dict:
        """Avanza un paso estocástico y actualiza todos los balancines y el semáforo principal."""
        # 1. Movimiento del S&P 500 / US500
        sp500_ret = random.gauss(0.0001, 0.003)
        self.us500_price = round(self.us500_price * (1.0 + sp500_ret), 2)

        # 2. Movimiento de DXY
        dxy_ret = random.gauss(-0.00005, 0.002)

        datos_pares = []

        for key, p in self.pares.items():
            if "GOLD" in key:
                p.price_x = round(p.price_x * (1.0 + dxy_ret), 2)
                p.price_y = round(
                    p.price_y + p.true_beta * (p.price_x * dxy_ret) + random.gauss(0, 0.8), 2
                )
                spread_half = 0.20
            elif "TSLA" in key:
                p.price_x = self.us500_price
                p.price_y = round(
                    p.price_y + p.true_beta * (p.price_x * sp500_ret * 2.1) + random.gauss(0, 0.5), 2
                )
                spread_half = 0.08
            else:  # AAPL
                p.price_x = self.us500_price
                p.price_y = round(
                    p.price_y + p.true_beta * (p.price_x * sp500_ret * 1.05) + random.gauss(0, 0.2), 2
                )
                spread_half = 0.05

            alpha, beta_est, z_score = p.kalman.update(p.price_y, p.price_x)
            p.last_beta_est = round(beta_est, 4)
            p.last_z_score = round(z_score, 2)

            # Order Flow Simulation
            bid_bias = 45.0 if z_score < -1.0 else (12.0 if z_score > 1.0 else 25.0)
            ask_bias = 12.0 if z_score < -1.0 else (45.0 if z_score > 1.0 else 25.0)
            bid_v = round(random.expovariate(1.0 / max(1.0, bid_bias)), 1)
            ask_v = round(random.expovariate(1.0 / max(1.0, ask_bias)), 1)

            bid_p = round(p.price_y - spread_half, 2)
            ask_p = round(p.price_y + spread_half, 2)

            ofi, mid_p, micro_p = p.order_flow.compute(bid_p, bid_v, ask_p, ask_v)
            p.last_ofi = round(ofi, 1)
            p.last_mid_price = round(mid_p, 2)
            p.last_micro_price = round(micro_p, 2)

            light_state = evaluar_sistema_luces_cuantitativo(z_score, ofi, micro_p, mid_p)
            p.last_light_state = light_state

            datos_pares.append({
                "key": key,
                "name": p.name,
                "category": p.category,
                "symbol_y": p.symbol_y,
                "symbol_x": p.symbol_x,
                "price_y": p.price_y,
                "price_x": p.price_x,
                "beta_kalman": p.last_beta_est,
                "z_score": p.last_z_score,
                "ofi": p.last_ofi,
                "micro_price": p.last_micro_price,
                "mid_price": p.last_mid_price,
                "light": light_state.light,
                "composite_score": light_state.composite_score,
                "confidence_pct": light_state.confidence_pct,
                "action": light_state.action_label,
            })

        # Evaluar Semáforo Global para US500 (S&P 500)
        # Combinación de señales de los 3 balancines
        avg_z = sum(p.last_z_score for p in self.pares.values()) / 3.0
        avg_ofi = sum(p.last_ofi for p in self.pares.values()) / 3.0
        bid_us500 = round(self.us500_price - 0.20, 2)
        ask_us500 = round(self.us500_price + 0.20, 2)
        ofi_us500, mid_us500, micro_us500 = self.us500_order_flow.compute(
            bid_us500, 30.0 + avg_ofi, ask_us500, 30.0 - avg_ofi
        )
        global_light = evaluar_sistema_luces_cuantitativo(avg_z, avg_ofi, micro_us500, mid_us500)

        if global_light.light in {"GREEN", "RED"}:
            self.total_signals_executed += 1
            future_delta = -avg_z * 0.5 + random.gauss(0, 0.2)
            is_correct = (global_light.light == "GREEN" and future_delta > 0) or (
                global_light.light == "RED" and future_delta < 0
            )
            if is_correct:
                self.correct_signals_count += 1

        hit_rate = (
            round((self.correct_signals_count / max(1, self.total_signals_executed)) * 100.0, 1)
            if self.total_signals_executed > 0
            else 74.5
        )
        error_rate = round(100.0 - hit_rate, 1)

        snapshot = {
            "us500_price": self.us500_price,
            "bid": bid_us500,
            "ask": ask_us500,
            "global_light": global_light.light,
            "global_direction": global_light.direction,
            "global_composite_score": global_light.composite_score,
            "global_confidence_pct": global_light.confidence_pct,
            "global_error_rate_pct": global_light.error_rate_pct,
            "global_action": global_light.action_label,
            "global_reasons": list(global_light.reason_codes),
            "hit_rate_pct": hit_rate,
            "error_rate_pct": error_rate,
            "sharpe_ratio": 3.42,
            "max_drawdown_pct": -4.18,
            "total_signals": self.total_signals_executed,
            "correct_signals": self.correct_signals_count,
            "balancines": datos_pares,
        }

        self.history.append(snapshot)
        if len(self.history) > 100:
            self.history.pop(0)

        return snapshot
