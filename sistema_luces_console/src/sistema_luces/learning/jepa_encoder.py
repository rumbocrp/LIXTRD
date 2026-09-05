"""Arquitectura Auto-Supervisada I-JEPA & Barlow Twins para Series Temporales de Microestructura (Fase 4).
Implementa:
- I-JEPA (Joint-Embedding Predictive Architecture) con codificador de contexto f_theta y objetivo g_xi.
- Actualización del codificador objetivo vía EMA cosenoidal (alpha = 0.996 -> 0.9999) (Assran et al., 2023).
- Regularización de Reducción de Redundancia de Barlow Twins (lambda = 5e-3) (Zbontar et al., 2021).
- Extracción de representaciones latentes D=256 invariantes al ruido de microestructura.
"""

from __future__ import annotations
import math
import numpy as np
from typing import Tuple, List, Dict, Any, Optional

class BarlowTwinsLoss:
    """Calcula la pérdida de reducción de redundancia e invarianza de Barlow Twins."""
    def __init__(self, latent_dim: int = 256, lambda_offdiag: float = 5.0e-3):
        self.latent_dim = latent_dim
        self.lambda_offdiag = lambda_offdiag

    def compute_loss(self, z_a: np.ndarray, z_b: np.ndarray) -> Tuple[float, float, float]:
        """
        z_a, z_b: tensores (N, D) donde N es el tamaño del lote y D es la dimensión latente.
        Retorna: (total_loss, invariance_on_diag, redundancy_off_diag)
        """
        N, D = z_a.shape
        if N < 2:
            return 0.0, 0.0, 0.0

        # 1. Normalización por batch (media 0, std 1)
        z_a_norm = (z_a - z_a.mean(axis=0)) / (z_a.std(axis=0) + 1e-6)
        z_b_norm = (z_b - z_b.mean(axis=0)) / (z_b.std(axis=0) + 1e-6)

        # 2. Matriz de correlación cruzada C = (z_a^T @ z_b) / N
        c_matrix = (z_a_norm.T @ z_b_norm) / float(N)

        # 3. Término en la diagonal (Invarianza: C_ii -> 1)
        diag = np.diag(c_matrix)
        on_diag_loss = np.sum((1.0 - diag) ** 2)

        # 4. Término fuera de la diagonal (Reducción de redundancia: C_ij -> 0)
        off_diag = c_matrix - np.diag(diag)
        off_diag_loss = np.sum(off_diag ** 2)

        total_loss = float(on_diag_loss + self.lambda_offdiag * off_diag_loss)
        return total_loss, float(on_diag_loss), float(off_diag_loss)

class MarketTimeSeriesJEPA:
    """
    Codificador I-JEPA para secuencias multiescala de microestructura.
    Mantiene pesos f_theta (contexto) y g_xi (objetivo con actualización EMA).
    """
    def __init__(
        self,
        input_features: int = 8,
        latent_dim: int = 256,
        ema_alpha_0: float = 0.996,
        ema_alpha_max: float = 0.9999,
        seed: int = 42,
    ):
        self.input_features = input_features
        self.latent_dim = latent_dim
        self.ema_alpha_0 = ema_alpha_0
        self.ema_alpha_max = ema_alpha_max
        self.step_count = 0

        np.random.seed(seed)
        # Inicialización He/Kaiming para proyección de contexto
        scale_in = math.sqrt(2.0 / (input_features * 10))
        self.w_context = np.random.randn(input_features * 10, latent_dim) * scale_in
        self.b_context = np.zeros(latent_dim)

        # Red de predicción latente p_phi
        scale_p = math.sqrt(2.0 / latent_dim)
        self.w_pred = np.random.randn(latent_dim, latent_dim) * scale_p
        self.b_pred = np.zeros(latent_dim)

        # Codificador objetivo g_xi (inicialmente clon de theta)
        self.w_target = self.w_context.copy()
        self.b_target = self.b_context.copy()

        self.barlow_loss_calc = BarlowTwinsLoss(latent_dim=latent_dim, lambda_offdiag=5e-3)

    def encode_context(self, sequence_window: np.ndarray) -> np.ndarray:
        """
        sequence_window: array de forma (10, input_features) o (N, 10, input_features)
        Retorna: vector latente z in R^256
        """
        flat = sequence_window.reshape(-1, self.input_features * 10)
        # Proyección lineal + activación GELU rápida
        hidden = flat @ self.w_context + self.b_context
        # GELU approximation: 0.5 * x * (1 + tanh(sqrt(2/pi) * (x + 0.044715 * x^3)))
        z = 0.5 * hidden * (1.0 + np.tanh(0.79788456 * (hidden + 0.044715 * (hidden ** 3))))
        # Normalización L2
        norm = np.linalg.norm(z, axis=-1, keepdims=True) + 1e-8
        return z / norm

    def encode_target(self, sequence_window: np.ndarray) -> np.ndarray:
        flat = sequence_window.reshape(-1, self.input_features * 10)
        hidden = flat @ self.w_target + self.b_target
        z = 0.5 * hidden * (1.0 + np.tanh(0.79788456 * (hidden + 0.044715 * (hidden ** 3))))
        norm = np.linalg.norm(z, axis=-1, keepdims=True) + 1e-8
        return z / norm

    def predict_latent(self, z_context: np.ndarray) -> np.ndarray:
        pred = z_context @ self.w_pred + self.b_pred
        norm = np.linalg.norm(pred, axis=-1, keepdims=True) + 1e-8
        return pred / norm

    def update_target_ema(self, max_steps: int = 10000) -> float:
        """Actualiza g_xi con programa cosenoidal de decaimiento EMA."""
        self.step_count += 1
        progress = min(1.0, self.step_count / max_steps)
        alpha_t = self.ema_alpha_max - (self.ema_alpha_max - self.ema_alpha_0) * (0.5 * (1.0 + math.cos(math.pi * progress)))
        
        self.w_target = alpha_t * self.w_target + (1.0 - alpha_t) * self.w_context
        self.b_target = alpha_t * self.b_target + (1.0 - alpha_t) * self.b_context
        return alpha_t
