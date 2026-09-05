"""Vocabulario canónico y códigos de razón para el Sistema de Luces."""

from enum import Enum

class TrafficLightColor(str, Enum):
    GREEN = "GREEN"
    YELLOW = "YELLOW"
    RED = "RED"

class ActionType(str, Enum):
    BUY = "BUY"
    MONITOR = "MONITOR"
    SELL = "SELL"

class HealthState(str, Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    STALE = "STALE"
    NO_DATA = "NO_DATA"

class ReasonCode(str, Enum):
    # Razones de Entrada / Activación
    KALMAN_Z_OVERSOLD = "KALMAN_Z_OVERSOLD"
    KALMAN_Z_OVERBOUGHT = "KALMAN_Z_OVERBOUGHT"
    OFI_BUY_IMBALANCE = "OFI_BUY_IMBALANCE"
    OFI_SELL_IMBALANCE = "OFI_SELL_IMBALANCE"
    MICRO_PRICE_PREMIUM = "MICRO_PRICE_PREMIUM"
    MICRO_PRICE_DISCOUNT = "MICRO_PRICE_DISCOUNT"
    CROSS_ASSET_DIVERGENCE = "CROSS_ASSET_DIVERGENCE"
    
    # Razones de Neutralidad / Monitor
    MONITOR_HYSTERESIS_HOLD = "MONITOR_HYSTERESIS_HOLD"
    MONITOR_SPREAD_EXPANSION = "MONITOR_SPREAD_EXPANSION"
    MONITOR_UNCERTAINTY = "MONITOR_UNCERTAINTY"
    MONITOR_DATA_STALE = "MONITOR_DATA_STALE"
    MONITOR_HIGH_TOXICITY = "MONITOR_HIGH_TOXICITY"
    MONITOR_POLICY = "MONITOR_POLICY"

REASON_DESCRIPTIONS = {
    ReasonCode.KALMAN_Z_OVERSOLD: "Spread cointegrado con subvaloración estadística severa (Z < -1.2)",
    ReasonCode.KALMAN_Z_OVERBOUGHT: "Spread cointegrado con sobrevaloración estadística severa (Z > +1.2)",
    ReasonCode.OFI_BUY_IMBALANCE: "Presión compradora institucional agresiva en el Bid",
    ReasonCode.OFI_SELL_IMBALANCE: "Presión vendedora masiva descargando sobre el Ask",
    ReasonCode.MICRO_PRICE_PREMIUM: "Micro-Price por encima del Mid-Price (Probabilidad alcista en próximo tick)",
    ReasonCode.MICRO_PRICE_DISCOUNT: "Micro-Price por debajo del Mid-Price (Probabilidad bajista en próximo tick)",
    ReasonCode.CROSS_ASSET_DIVERGENCE: "Ruptura de correlación multi-activo con potencial de reversión a la media",
    ReasonCode.MONITOR_HYSTERESIS_HOLD: "Convicción insuficiente para superar el umbral de entrada de política",
    ReasonCode.MONITOR_SPREAD_EXPANSION: "Spread superior a 3σ; costo de fricción supera el alfa estimado",
    ReasonCode.MONITOR_UNCERTAINTY: "Señales mixtas entre Filtro de Kalman y Order Flow",
    ReasonCode.MONITOR_DATA_STALE: "Latencia excesiva o fuente de datos desactualizada (>250ms)",
    ReasonCode.MONITOR_HIGH_TOXICITY: "Flujo tóxico adverso detectado (VPIN elevado)",
    ReasonCode.MONITOR_POLICY: "Estado de reposo seguro por defecto",
}
