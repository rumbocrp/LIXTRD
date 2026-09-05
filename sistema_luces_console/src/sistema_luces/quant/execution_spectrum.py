"""Motor Cuantitativo del Espectro Agudo de Ejecución y Microestructura L2."""

from __future__ import annotations
import math
from typing import List, Tuple, Optional
from sistema_luces.domain.simulated_trade import AcuteExecutionResult

class AcuteExecutionSpectrumEngine:
    """
    Simula la ejecución aguda en microestructura con penetración multi-nivel
    y penalizaciones no lineales por selección adversa (VPIN y OFI).
    """
    def __init__(
        self,
        eta_friction: float = 0.18,        # Coeficiente base de fricción aguda
        depth_power_exponent: float = 0.65, # Exponente de impacto de liquidez
        default_order_size: float = 15.0,  # Tamaño estándar de orden simulada
    ):
        self.eta = eta_friction
        self.depth_exp = depth_power_exponent
        self.default_order_size = default_order_size

    def simulate_fill(
        self,
        direction: str, # "LONG" (compra en Ask) o "SHORT" (venta en Bid)
        spread: float,
        vpin: float,
        ofi: float,
        ofi_critical: float = 20.0,
        bids_depth: Optional[List[Tuple[float, float]]] = None,
        asks_depth: Optional[List[Tuple[float, float]]] = None,
        size: Optional[float] = None,
    ) -> AcuteExecutionResult:
        order_size = size or self.default_order_size
        direction_upper = direction.upper()

        if direction_upper == "LONG":
            # Compra barriendo el libro de Asks
            depth = asks_depth if asks_depth else [(100.0, 50.0)]
            touch_price = depth[0][0]
            nominal_price = touch_price

            # 1. Barrido ponderado por volumen en niveles de profundidad (VWAP)
            accum_vol = 0.0
            accum_cost = 0.0
            remaining = order_size

            for level_price, level_vol in depth:
                v_fill = min(remaining, level_vol)
                accum_vol += v_fill
                accum_cost += v_fill * level_price
                remaining -= v_fill
                if remaining <= 1e-6:
                    break

            if accum_vol > 0:
                vwap_price = accum_cost / accum_vol
            else:
                vwap_price = touch_price

            # Fricción por barrido de profundidad
            depth_slippage = max(0.0, vwap_price - touch_price)

            # 2. Penalización no lineal de Selección Adversa (Acute Adverse Selection)
            # Si compramos y el OFI es fuertemente vendedor o VPIN es alto, el riesgo de ejecución se agudiza
            ofi_ratio = max(0.0, abs(ofi) / max(1.0, ofi_critical))
            vpin_factor = max(0.1, vpin / 0.40)
            
            # Penalización aguda en pips
            adverse_penalty = (
                self.eta
                * spread
                * vpin_factor
                * (1.0 + (ofi_ratio ** self.depth_exp))
            )

            # Precio de ejecución final
            effective_fill = vwap_price + adverse_penalty
            total_slippage = max(0.0, effective_fill - touch_price)

        else: # SHORT
            # Venta barriendo el libro de Bids
            depth = bids_depth if bids_depth else [(100.0, 50.0)]
            touch_price = depth[0][0]
            nominal_price = touch_price

            accum_vol = 0.0
            accum_cost = 0.0
            remaining = order_size

            for level_price, level_vol in depth:
                v_fill = min(remaining, level_vol)
                accum_vol += v_fill
                accum_cost += v_fill * level_price
                remaining -= v_fill
                if remaining <= 1e-6:
                    break

            if accum_vol > 0:
                vwap_price = accum_cost / accum_vol
            else:
                vwap_price = touch_price

            # Fricción por barrido de profundidad
            depth_slippage = max(0.0, touch_price - vwap_price)

            # Penalización por selección adversa
            ofi_ratio = max(0.0, abs(ofi) / max(1.0, ofi_critical))
            vpin_factor = max(0.1, vpin / 0.40)
            
            adverse_penalty = (
                self.eta
                * spread
                * vpin_factor
                * (1.0 + (ofi_ratio ** self.depth_exp))
            )

            effective_fill = vwap_price - adverse_penalty
            total_slippage = max(0.0, touch_price - effective_fill)

        # 3. Índice de Agudeza del Espectro [0.0 - 100.0]
        # Pondera la ratio de slippage sobre spread, la toxicidad de flujo y el desbalance
        friction_ratio = total_slippage / max(1e-4, spread)
        sharpness_raw = (
            (friction_ratio * 40.0)
            + (vpin * 35.0)
            + (min(1.0, abs(ofi) / max(1.0, ofi_critical)) * 25.0)
        )
        sharpness_score = max(0.0, min(100.0, sharpness_raw))

        # 4. Clasificación en Tiers de Espectro
        if sharpness_score <= 25.0:
            tier = "OPTIMAL_TOUCH"
        elif sharpness_score <= 50.0:
            tier = "MODERATE_SLIP"
        elif sharpness_score <= 75.0:
            tier = "DEEP_SWEEP"
        else:
            tier = "ACUTE_ADVERSE"

        return AcuteExecutionResult(
            direction=direction_upper,
            nominal_price=nominal_price,
            effective_fill_price=effective_fill,
            slippage_pips=total_slippage,
            book_depth_slippage=depth_slippage,
            adverse_selection_slippage=adverse_penalty,
            spectrum_sharpness_score=sharpness_score,
            spectrum_tier=tier,
            spread_friction_ratio=friction_ratio,
        )
