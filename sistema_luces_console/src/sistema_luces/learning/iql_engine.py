"""Motor de Aprendizaje Offline RL IQL (Implicit Q-Learning) (Fase 5).
Implementa:
- Red de Valor V_psi entrenada con pérdida expectil L_tau_e (tau = 0.75) (Kostrikov, Nair & Levine, 2021).
- Redes gemelas Q_theta_1, Q_theta_2 con descuento gamma = 0.99 y clipping de sobreestimación.
- Estimación no paramétrica de ventaja A(s, a) = Q(s, a) - V(s) sin consultar acciones fuera del dataset.
"""

from __future__ import annotations
import math
import numpy as np
from typing import Tuple, List, Dict, Any, Optional

def expectile_loss(diff: np.ndarray, tau: float = 0.75) -> float:
    """
    L_tau(u) = |tau - I(u < 0)| * u^2
    Pondera los residuos positivos con peso tau (0.75) y los negativos con (1 - tau) (0.25).
    """
    weight = np.where(diff > 0, tau, 1.0 - tau)
    return float(np.mean(weight * (diff ** 2)))

class ImplicitQLearningValueNet:
    """Estimador de Valor V(s) y Twin-Q(s, a) con expectil tau = 0.75 sobre espacio latente D=256."""
    def __init__(
        self,
        state_dim: int = 256,
        num_actions: int = 3, # 0: HOLD/MONITOR, 1: BUY, 2: SELL
        tau_expectile: float = 0.75,
        discount_gamma: float = 0.99,
        learning_rate: float = 0.01,
        seed: int = 42,
    ):
        self.state_dim = state_dim
        self.num_actions = num_actions
        self.tau = tau_expectile
        self.gamma = discount_gamma
        self.lr = learning_rate

        np.random.seed(seed)
        scale = math.sqrt(2.0 / state_dim)
        
        # Red de Valor V_psi(s)
        self.w_v = np.random.randn(state_dim, 1) * scale
        self.b_v = 0.0

        # Twin Q-Networks: Q1(s, a) y Q2(s, a)
        self.w_q1 = np.random.randn(state_dim, num_actions) * scale
        self.b_q1 = np.zeros(num_actions)
        self.w_q2 = np.random.randn(state_dim, num_actions) * scale
        self.b_q2 = np.zeros(num_actions)

    def predict_v(self, s: np.ndarray) -> np.ndarray:
        """Estima V(s) in R."""
        s_mat = s.reshape(-1, self.state_dim)
        return (s_mat @ self.w_v + self.b_v).flatten()

    def predict_q(self, s: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Retorna: (q_min, q1, q2) para las 3 acciones posibles.
        """
        s_mat = s.reshape(-1, self.state_dim)
        q1 = s_mat @ self.w_q1 + self.b_q1
        q2 = s_mat @ self.w_q2 + self.b_q2
        q_min = np.minimum(q1, q2)
        return q_min, q1, q2

    def compute_advantage(self, s: np.ndarray, a_idx: int) -> float:
        """Calcula A(s, a) = Q_min(s, a) - V(s)."""
        q_min, _, _ = self.predict_q(s)
        v = self.predict_v(s)
        return float(q_min[0, a_idx] - v[0])

    def train_step(
        self,
        s: np.ndarray,
        a_idx: int,
        r: float,
        s_next: np.ndarray,
        done: bool = False,
    ) -> Dict[str, float]:
        """Ejecuta un paso de gradiente estocástico sobre V y Twin-Q."""
        s_vec = s.reshape(1, self.state_dim)
        s_next_vec = s_next.reshape(1, self.state_dim)

        # 1. Target para Q: r + gamma * V(s_next)
        v_next = float(self.predict_v(s_next_vec)[0]) if not done else 0.0
        target_q = r + self.gamma * v_next

        # 2. Actualizar Q1 y Q2 hacia target_q
        _, q1, q2 = self.predict_q(s_vec)
        err_q1 = float(target_q - q1[0, a_idx])
        err_q2 = float(target_q - q2[0, a_idx])

        # Gradiente en la acción ejecutada
        self.w_q1[:, a_idx] += self.lr * err_q1 * s_vec[0]
        self.b_q1[a_idx] += self.lr * err_q1
        self.w_q2[:, a_idx] += self.lr * err_q2 * s_vec[0]
        self.b_q2[a_idx] += self.lr * err_q2

        # 3. Target para V: Q_target(s, a) evaluado con expectil tau = 0.75
        q_target = min(q1[0, a_idx], q2[0, a_idx])
        v_curr = float(self.predict_v(s_vec)[0])
        diff_v = q_target - v_curr
        
        # Ponderación expectil asimétrica
        weight_v = self.tau if diff_v > 0 else (1.0 - self.tau)
        grad_v = weight_v * diff_v

        self.w_v[:, 0] += self.lr * grad_v * s_vec[0]
        self.b_v += self.lr * grad_v

        return {
            "loss_v": float(expectile_loss(np.array([diff_v]), tau=self.tau)),
            "loss_q1": float(err_q1 ** 2),
            "loss_q2": float(err_q2 ** 2),
            "advantage": float(diff_v),
        }
