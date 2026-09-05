"""Filtro de Kalman Dinámico 2D para estimación de spread cointegrado y Z-score (confidencial_trade).

Modelo en espacio de estados:
theta_t = [alpha_t, beta_t]^T
Y_t = alpha_t + beta_t * X_t + v_t
"""

import math
from typing import List, Tuple


class DynamicKalmanFilter:
    """Filtro de Kalman recursivo 2D para calcular el ratio de cobertura dinámico (Beta_t) y Z-Score."""

    def __init__(
        self,
        delta: float = 1e-4,
        R: float = 1e-2,
        initial_alpha: float = 0.0,
        initial_beta: float = 1.0,
        memory_window: int = 50,
    ) -> None:
        self.theta: List[float] = [initial_alpha, initial_beta]  # [alpha, beta inicial]
        self.P: List[List[float]] = [[1.0, 0.0], [0.0, 1.0]]  # Covarianza del estado
        self.Q: List[List[float]] = [[delta / (1.0 - delta), 0.0], [0.0, delta / (1.0 - delta)]]  # Ruido de proceso
        self.R: float = R  # Varianza de observación
        self.error_history: List[float] = []
        self.memory_window = memory_window

    def update(self, y: float, x: float) -> Tuple[float, float, float]:
        """Actualiza el estado de Kalman y retorna (alpha, beta_est, z_score)."""
        # 1. Predicción a priori
        P_prior = [
            [self.P[0][0] + self.Q[0][0], self.P[0][1] + self.Q[0][1]],
            [self.P[1][0] + self.Q[1][0], self.P[1][1] + self.Q[1][1]],
        ]

        # 2. Innovación / Error de Spread
        H = [1.0, x]
        y_pred = self.theta[0] + self.theta[1] * x
        error = y - y_pred
        self.error_history.append(error)
        if len(self.error_history) > self.memory_window:
            self.error_history.pop(0)

        # 3. Varianza de la Innovación S = H P H^T + R
        S = (H[0] * P_prior[0][0] + H[1] * P_prior[1][0]) * H[0] + (
            H[0] * P_prior[0][1] + H[1] * P_prior[1][1]
        ) * H[1] + self.R

        # 4. Ganancia de Kalman K = P H^T / S
        K = [
            (P_prior[0][0] * H[0] + P_prior[0][1] * H[1]) / S,
            (P_prior[1][0] * H[0] + P_prior[1][1] * H[1]) / S,
        ]

        # 5. Actualización del Estado a posteriori
        self.theta[0] += K[0] * error
        self.theta[1] += K[1] * error

        # 6. Actualización de la Covarianza P = (I - K H) P_prior
        self.P = [
            [
                P_prior[0][0] - K[0] * (H[0] * P_prior[0][0] + H[1] * P_prior[1][0]),
                P_prior[0][1] - K[0] * (H[0] * P_prior[0][1] + H[1] * P_prior[1][1]),
            ],
            [
                P_prior[1][0] - K[1] * (H[0] * P_prior[0][0] + H[1] * P_prior[1][0]),
                P_prior[1][1] - K[1] * (H[0] * P_prior[0][1] + H[1] * P_prior[1][1]),
            ],
        ]

        # 7. Cálculo del Z-Score del Spread
        mean_err = sum(self.error_history) / len(self.error_history)
        var_err = sum((e - mean_err) ** 2 for e in self.error_history) / max(1, len(self.error_history) - 1)
        std_err = math.sqrt(var_err) if var_err > 1e-6 else 1.0
        z_score = (error - mean_err) / std_err

        return self.theta[0], self.theta[1], z_score
