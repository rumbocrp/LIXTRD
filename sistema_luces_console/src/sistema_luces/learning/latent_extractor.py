"""Extractor de Estados Latentes en Tiempo Real con Inferencia Sub-Milisegundo (Fase 4)."""

from __future__ import annotations
import time
import numpy as np
from typing import List, Tuple, Optional
from sistema_luces.domain.models import QuantFeatures
from sistema_luces.learning.jepa_encoder import MarketTimeSeriesJEPA

class LatentStateExtractor:
    """
    Mantiene un buffer circular de los últimos 10 ticks de microestructura
    y proyecta el estado del mercado al espacio latente D=256 en <1.5ms.
    """
    def __init__(self, encoder: Optional[MarketTimeSeriesJEPA] = None, window_len: int = 10):
        self.window_len = window_len
        self.encoder = encoder or MarketTimeSeriesJEPA(input_features=8, latent_dim=256)
        # Buffer de características (10, 8)
        self.feature_buffer: List[List[float]] = []

    def push_features(self, feats: QuantFeatures, return_pct: float = 0.0) -> np.ndarray:
        """
        Incorpora el vector de características actual y retorna la incrustación latente D=256.
        """
        spread_val = max(1e-4, feats.spread_pips)
        micro_delta = (feats.micro_price - feats.mid_price) / spread_val

        # Vector de 8 características cuantitativas normalizadas
        row = [
            feats.kalman_beta / 20.0,
            feats.spread_z_score / 3.0,
            feats.order_flow_imbalance / 50.0,
            micro_delta,
            feats.vpin_toxicity,
            feats.cross_asset_correlation,
            feats.spread_pips / max(1e-4, feats.mid_price) * 1000.0,
            return_pct * 100.0,
        ]

        self.feature_buffer.append(row)
        if len(self.feature_buffer) > self.window_len:
            self.feature_buffer.pop(0)

        # Si aún no tenemos 10 ticks, rellenar con réplica del primero
        while len(self.feature_buffer) < self.window_len:
            self.feature_buffer.insert(0, list(row))

        seq_array = np.array(self.feature_buffer, dtype=np.float32)
        
        # Inferencia latente ultra-rápida
        z_latent = self.encoder.encode_context(seq_array)
        return z_latent.flatten()

    def get_compact_latent_summary(self, z_latent: np.ndarray, summary_dim: int = 32) -> List[int]:
        """
        Comprime el vector D=256 a un vector compacto de 32 enteros escalados en PPM
        para interoperabilidad con MLStateVector sin sobrecargar la serialización JSON.
        """
        # Agrupación por promedio de bloques de 8 componentes (256 / 32 = 8)
        reshaped = z_latent.reshape(summary_dim, -1)
        means = reshaped.mean(axis=1)
        # Escalar a PPM [-1,000,000, +1,000,000]
        return [int(round(float(m) * 1_000_000)) for m in means]
