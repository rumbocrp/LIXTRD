"""Contratos de datos inmutables y modelos de dominio en PPM (Parts Per Million)."""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional
import time
import uuid

from sistema_luces.domain.vocabulary import TrafficLightColor, ActionType, HealthState, ReasonCode

@dataclass(frozen=True)
class MarketQuoteTick:
    instrument: str
    bid: float
    ask: float
    bid_vol: float
    ask_vol: float
    source_timestamp_utc: int # ms
    received_timestamp_utc: int # ms

    @property
    def mid_price(self) -> float:
        return (self.bid + self.ask) / 2.0

    @property
    def spread(self) -> float:
        return max(0.0, self.ask - self.bid)

@dataclass(frozen=True)
class QuantFeatures:
    kalman_beta: float
    kalman_alpha: float
    spread_z_score: float
    order_flow_imbalance: float
    mid_price: float
    micro_price: float
    cross_asset_correlation: float
    vpin_toxicity: float
    spread_pips: float

@dataclass(frozen=True)
class DecisionLuzContract:
    decision_id: str
    instrument: str
    timeframe: str
    data_timestamp_utc: int
    created_at_utc: int
    
    state: TrafficLightColor
    action: ActionType
    
    net_utility_long_ppm: int
    net_utility_short_ppm: int
    confidence_score_ppm: int
    calibration_quality_ppm: int
    
    kalman_beta_scaled: int
    kalman_z_score_scaled: int
    ofi_imbalance_scaled: int
    micro_price_mid_delta_ppm: int
    
    champion_model_id: str
    valid_until_utc: int
    reason_codes: List[ReasonCode]
    data_health: HealthState

    @classmethod
    def create(
        cls,
        instrument: str,
        timeframe: str,
        state: TrafficLightColor,
        action: ActionType,
        net_utility_long: float,
        net_utility_short: float,
        confidence_score: float,
        calibration_quality: float,
        features: QuantFeatures,
        champion_model_id: str,
        reason_codes: List[ReasonCode],
        data_health: HealthState,
        data_timestamp_utc: Optional[int] = None,
        validity_duration_ms: int = 2000,
    ) -> DecisionLuzContract:
        now_ms = int(time.time() * 1000)
        d_ts = data_timestamp_utc or now_ms
        
        # Escalamiento preciso a PPM (Parts Per Million: 1.0 = 1,000,000 ppm)
        u_long_ppm = int(round(net_utility_long * 1_000_000))
        u_short_ppm = int(round(net_utility_short * 1_000_000))
        conf_ppm = int(round(confidence_score * 1_000_000))
        calib_ppm = int(round(calibration_quality * 1_000_000))
        
        beta_scaled = int(round(features.kalman_beta * 10_000))
        z_scaled = int(round(features.spread_z_score * 100))
        ofi_scaled = int(round(features.order_flow_imbalance * 10))
        
        spread_val = max(1e-4, features.spread_pips)
        delta_p = (features.micro_price - features.mid_price) / spread_val
        delta_ppm = int(round(delta_p * 10_000))

        return cls(
            decision_id=str(uuid.uuid4()),
            instrument=instrument,
            timeframe=timeframe,
            data_timestamp_utc=d_ts,
            created_at_utc=now_ms,
            state=state,
            action=action,
            net_utility_long_ppm=u_long_ppm,
            net_utility_short_ppm=u_short_ppm,
            confidence_score_ppm=conf_ppm,
            calibration_quality_ppm=calib_ppm,
            kalman_beta_scaled=beta_scaled,
            kalman_z_score_scaled=z_scaled,
            ofi_imbalance_scaled=ofi_scaled,
            micro_price_mid_delta_ppm=delta_ppm,
            champion_model_id=champion_model_id,
            valid_until_utc=now_ms + validity_duration_ms,
            reason_codes=reason_codes,
            data_health=data_health,
        )
