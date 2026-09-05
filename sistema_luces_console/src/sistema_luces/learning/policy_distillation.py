"""Destilación de Políticas por Clonación Ponderada por Ventaja (AWBC) (Fase 5).
Implementa:
- AWBC (Advantage-Weighted Behavioral Cloning) con temperatura beta_T = 1.50 (Peng et al., 2019; Nair et al., 2020).
- Regularización de Divergencia KL lambda_KL = 0.10 anclada a la política del Sistema de Luces (Instructor).
- Salida probabilística softmax sobre [MONITOR/HOLD, BUY, SELL].
"""

from __future__ import annotations
import math
import numpy as np
from typing import Tuple, List, Dict, Any, Optional

class AdvantageWeightedPolicy:
    """Red de Políticas del Estudiante guiada por las ventajas de IQL y anclada al Sistema de Luces."""
    def __init__(
        self,
        state_dim: int = 256,
        num_actions: int = 3,
        temperature_beta: float = 1.50,
        advantage_clip: float = 100.0,
        lambda_kl_teacher: float = 0.10,
        learning_rate: float = 0.01,
        seed: int = 42,
    ):
        self.state_dim = state_dim
        self.num_actions = num_actions
        self.beta = temperature_beta
        self.clip = advantage_clip
        self.lambda_kl = lambda_kl_teacher
        self.lr = learning_rate

        np.random.seed(seed)
        scale = math.sqrt(2.0 / state_dim)
        self.w_pi = np.random.randn(state_dim, num_actions) * scale
        self.b_pi = np.zeros(num_actions)

    def predict_logits(self, s: np.ndarray) -> np.ndarray:
        s_mat = s.reshape(-1, self.state_dim)
        return s_mat @ self.w_pi + self.b_pi

    def predict_probabilities(self, s: np.ndarray) -> np.ndarray:
        """Aplica Softmax numéricamente estable sobre los logits."""
        logits = self.predict_logits(s)
        exp_logits = np.exp(logits - np.max(logits, axis=-1, keepdims=True))
        return exp_logits / (np.sum(exp_logits, axis=-1, keepdims=True) + 1e-9)

    def train_step(
        self,
        s: np.ndarray,
        a_idx: int,
        advantage: float,
        teacher_distribution: np.ndarray, # [p_hold, p_buy, p_sell]
    ) -> Dict[str, float]:
        """
        Actualiza los parámetros de la política con peso de ventaja y penalización KL contra el instructor.
        w_adv = min(exp(A / beta), M_clip)
        """
        s_vec = s.reshape(1, self.state_dim)
        probs = self.predict_probabilities(s_vec)[0]

        # 1. Ponderación exponencial de ventaja
        adv_clamped = min(self.clip, max(-self.clip, advantage / self.beta))
        w_adv = min(self.clip, math.exp(adv_clamped))

        # 2. Gradiente de Log-Likelihood ponderado por ventaja: w_adv * (probs - e_a)
        target_one_hot = np.zeros(self.num_actions)
        target_one_hot[a_idx] = 1.0
        grad_policy = w_adv * (probs - target_one_hot)

        # 3. Gradiente de Divergencia KL contra el Instructor: lambda_KL * (probs - teacher_dist)
        grad_kl = self.lambda_kl * (probs - teacher_distribution)

        total_grad = grad_policy + grad_kl

        # Actualización de pesos (descenso por gradiente)
        self.w_pi -= self.lr * (s_vec.T @ total_grad.reshape(1, -1))
        self.b_pi -= self.lr * total_grad

        # Cálculo de métricas
        nll = -math.log(max(1e-6, probs[a_idx]))
        kl_div = float(np.sum(teacher_distribution * np.log((teacher_distribution + 1e-9) / (probs + 1e-9))))

        return {
            "policy_loss": float(w_adv * nll),
            "kl_divergence": kl_div,
            "weight_adv": float(w_adv),
        }
