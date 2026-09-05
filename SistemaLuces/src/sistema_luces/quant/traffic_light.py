"""Motor de Decisión del Sistema de Luces Cuantitativo (confidencial_trade)."""

from dataclasses import dataclass
import math
from typing import Literal, Tuple

from sistema_luces.domain.vocabulary import Direction, Light


@dataclass(frozen=True)
class EstadoLuzCuantitativa:
    light: Light
    direction: Direction
    composite_score: float
    spread_score: float
    ofi_score: float
    micro_price_score: float
    confidence_pct: float
    error_rate_pct: float
    action_label: str
    reason_codes: Tuple[str, ...]


def evaluar_sistema_luces_cuantitativo(
    z_score: float,
    ofi: float,
    micro_price: float,
    mid_price: float,
    threshold_confluence: float = 0.35,
    threshold_z: float = 1.0,
) -> EstadoLuzCuantitativa:
    """Evalúa la confluencia de Z-Score de Cointegración + Order Flow + Micro-Price.

    Fórmula:
    composite_score = 0.45 * spread_score + 0.35 * ofi_score + 0.20 * mp_score
    """
    # 1. Componente de Reversión a la Media (Spread Z-score)
    # Z negativo indica activo subvalorado (comprar) -> spread_score positivo
    spread_score = -math.tanh(z_score)

    # 2. Componente de Order Flow Momentum
    ofi_score = math.tanh(ofi / 50.0)

    # 3. Componente de Presión Micro-Price
    if micro_price > mid_price:
        mp_score = 1.0
    elif micro_price < mid_price:
        mp_score = -1.0
    else:
        mp_score = 0.0

    # Score ponderado final [-1.0, +1.0]
    composite_score = (0.45 * spread_score) + (0.35 * ofi_score) + (0.20 * mp_score)

    confidence = round(min(98.5, max(50.0, 50.0 + abs(composite_score) * 48.5)), 1)
    error_rate = round(100.0 - confidence, 1)

    if composite_score >= threshold_confluence and z_score < -threshold_z:
        light: Light = "GREEN"
        direction: Direction = "LONG"
        action = "COMPRA FUERTE (LONG)"
        reasons = ("KALMAN_UNDERVALUED_LONG", "OFI_BULLISH_FLOW", "MICROPRICE_PRESSURE_BUY")
    elif composite_score <= -threshold_confluence and z_score > threshold_z:
        light: Light = "RED"
        direction: Direction = "SHORT"
        action = "VENTA FUERTE (SHORT)"
        reasons = ("KALMAN_OVERVALUED_SHORT", "OFI_BEARISH_FLOW", "MICROPRICE_PRESSURE_SELL")
    else:
        light = "YELLOW"
        direction = "MONITOR"
        action = "NEUTRAL / ESPERAR"
        reasons = ("MIXED_SIGNALS_WAIT", "LOW_CONFLUENCE_MONITOR")

    return EstadoLuzCuantitativa(
        light=light,
        direction=direction,
        composite_score=round(composite_score, 4),
        spread_score=round(spread_score, 4),
        ofi_score=round(ofi_score, 4),
        micro_price_score=round(mp_score, 4),
        confidence_pct=confidence,
        error_rate_pct=error_rate,
        action_label=action,
        reason_codes=reasons,
    )
