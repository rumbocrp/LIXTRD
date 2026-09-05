"""Motor de Microestructura de Alta Fidelidad (Fase 1).
Implementa:
- Order Flow Imbalance Multi-Nivel (K=5) con decaimiento espacial kappa = 0.65 (Cont, Kukanov & Stoikov, 2014; Cont & Lu, 2023).
- Micro-Price Analítico de Stoikov (2018) con ponderación de colas opuestas y trigger de desbalance.
- Detector de Toxicidad VPIN con 50 cubos de volumen y Bulk Volume Classification (Easley, Lopez de Prado & O'Hara, 2012).
"""

from __future__ import annotations
import math
from typing import List, Tuple, Dict, Any, Optional

class StoikovMicroPriceEngine:
    """Estimador de Micro-Precio analítico de primer orden según Stoikov (2018)."""
    
    @staticmethod
    def compute_level1(bid_p: float, bid_v: float, ask_p: float, ask_v: float) -> Tuple[float, float, float]:
        """
        P_micro = P_mid + (Spread / 2) * ((v_b - v_a) / (v_b + v_a))
        Retorna: (mid_price, micro_price, micro_delta_ppm)
        """
        mid = (bid_p + ask_p) / 2.0
        spread = max(1e-4, ask_p - bid_p)
        tot_v = max(1e-4, bid_v + ask_v)
        
        imbalance_ratio = (bid_v - ask_v) / tot_v
        micro_price = mid + (spread / 2.0) * imbalance_ratio
        
        # Desplazamiento respecto a mid expresado en PPM de spread
        delta_ppm = int(round(((micro_price - mid) / spread) * 1_000_000))
        return mid, micro_price, delta_ppm

class VPINDetector:
    """
    Detector de toxicidad de flujo de órdenes por Volumen Sincronizado (VPIN).
    Mantiene N=50 cubos de volumen constante.
    """
    def __init__(self, num_buckets: int = 50, bucket_volume: float = 100.0, sigma_norm: float = 1.0):
        self.num_buckets = num_buckets
        self.bucket_volume = bucket_volume
        self.sigma_norm = sigma_norm
        self.current_bucket_vol = 0.0
        self.current_bucket_imbalance = 0.0
        self.vpin_history: List[float] = [0.1] * num_buckets
        self.current_vpin = 0.1

    def update(self, trade_vol: float, delta_price: float) -> float:
        """
        Aplica Bulk Volume Classification (BVC) vía CDF normal:
        v_buy = V * Phi(delta_p / sigma)
        v_sell = V - v_buy
        """
        if trade_vol <= 0:
            return self.current_vpin

        # Aproximación rápida de CDF Normal estándar Phi(z)
        z = delta_price / max(1e-4, self.sigma_norm)
        # Aproximación logística de la normal: Phi(z) ≈ 1 / (1 + exp(-1.702 * z))
        phi_z = 1.0 / (1.0 + math.exp(-max(-10.0, min(10.0, 1.702 * z))))
        
        v_buy = trade_vol * phi_z
        v_sell = trade_vol - v_buy
        imbalance = abs(v_buy - v_sell)

        remaining_vol = trade_vol
        while remaining_vol > 0:
            space_in_bucket = self.bucket_volume - self.current_bucket_vol
            if remaining_vol < space_in_bucket:
                self.current_bucket_vol += remaining_vol
                self.current_bucket_imbalance += imbalance * (remaining_vol / trade_vol)
                remaining_vol = 0.0
            else:
                fraction = space_in_bucket / remaining_vol
                self.current_bucket_imbalance += imbalance * fraction
                
                # Cerrar cubo y rotar en historial VPIN
                self.vpin_history.append(self.current_bucket_imbalance / self.bucket_volume)
                if len(self.vpin_history) > self.num_buckets:
                    self.vpin_history.pop(0)

                # Recalcular VPIN: promedio de desbalances en N cubos
                self.current_vpin = sum(self.vpin_history) / len(self.vpin_history)
                
                remaining_vol -= space_in_bucket
                self.current_bucket_vol = 0.0
                self.current_bucket_imbalance = 0.0

        return min(1.0, max(0.01, self.current_vpin))

class MultiLevelOrderFlowEngine:
    """
    Calcula OFI multi-nivel sobre K=5 niveles con decaimiento espacial kappa = 0.65.
    OFI_t = sum_{k=1}^K w_k * OFI_{k, t}
    """
    def __init__(self, num_levels: int = 5, kappa: float = 0.65):
        self.num_levels = num_levels
        self.kappa = kappa
        
        # Precomputar pesos espaciales normalizados w_k
        raw_weights = [math.exp(-kappa * k) for k in range(num_levels)]
        sum_w = sum(raw_weights)
        self.weights = [w / sum_w for w in raw_weights]

        self.prev_bids: List[Tuple[float, float]] = [(0.0, 0.0)] * num_levels
        self.prev_asks: List[Tuple[float, float]] = [(0.0, 0.0)] * num_levels
        self.vpin_detector = VPINDetector(num_buckets=50, bucket_volume=500.0)

    def compute(
        self,
        bids: List[Tuple[float, float]], # [(price, vol), ...]
        asks: List[Tuple[float, float]],
    ) -> Tuple[float, float, float, float]:
        """
        Calcula OFI multi-nivel ponderado, mid-price, micro-price y VPIN.
        Retorna: (ofi_composite, mid_price, micro_price, vpin)
        """
        if not bids or not asks:
            return 0.0, 0.0, 0.0, 0.1

        bid_p0, bid_v0 = bids[0]
        ask_p0, ask_v0 = asks[0]
        mid_p, micro_p, _ = StoikovMicroPriceEngine.compute_level1(bid_p0, bid_v0, ask_p0, ask_v0)

        # Si es el primer tick, inicializar estados previos
        if self.prev_bids[0][0] == 0.0:
            for k in range(min(self.num_levels, len(bids))):
                self.prev_bids[k] = bids[k]
            for k in range(min(self.num_levels, len(asks))):
                self.prev_asks[k] = asks[k]
            return 0.0, mid_p, micro_p, 0.1

        ofi_total = 0.0
        n_levels = min(self.num_levels, len(bids), len(asks))

        for k in range(n_levels):
            curr_bp, curr_bv = bids[k]
            prev_bp, prev_bv = self.prev_bids[k]
            curr_ap, curr_av = asks[k]
            prev_ap, prev_av = self.prev_asks[k]

            # Flujo en Bid nivel k
            if curr_bp > prev_bp:
                i_bid = curr_bv
            elif curr_bp == prev_bp:
                i_bid = curr_bv - prev_bv
            else:
                i_bid = 0.0

            # Flujo en Ask nivel k
            if curr_ap < prev_ap:
                i_ask = curr_av
            elif curr_ap == prev_ap:
                i_ask = curr_av - prev_av
            else:
                i_ask = 0.0

            level_ofi = i_bid - i_ask
            ofi_total += self.weights[k] * level_ofi

            # Guardar estado
            self.prev_bids[k] = (curr_bp, curr_bv)
            self.prev_asks[k] = (curr_ap, curr_av)

        # Actualizar detector VPIN
        vol_activity = abs(bid_v0 - self.prev_bids[0][1]) + abs(ask_v0 - self.prev_asks[0][1]) + abs(ofi_total)
        delta_p = mid_p - ((self.prev_bids[0][0] + self.prev_asks[0][0]) / 2.0)
        vpin = self.vpin_detector.update(trade_vol=vol_activity, delta_price=delta_p)

        return ofi_total, mid_p, micro_p, vpin

# Wrapper compatible para Nivel 1 (Bid/Ask simple)
class OrderFlowEngine:
    """Wrapper compatible de nivel 1 que delega al motor multi-nivel."""
    def __init__(self):
        self.multilevel_engine = MultiLevelOrderFlowEngine(num_levels=1)

    def compute(self, bid_p: float, bid_v: float, ask_p: float, ask_v: float) -> Tuple[float, float, float, float]:
        return self.multilevel_engine.compute(bids=[(bid_p, bid_v)], asks=[(ask_p, ask_v)])
