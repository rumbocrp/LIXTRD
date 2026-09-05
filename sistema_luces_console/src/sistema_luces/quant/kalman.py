"""Filtro de Kalman 2D Robusto y Adaptativo (Fase 1).
Implementa:
- Ruido de proceso adaptativo Q_t con factor delta = 1e-4 (Triantafyllopoulos & Montana, 2011).
- Varianza de observación adaptativa R_t por Innovation Matching de Mehra (1970).
- Rechazo de outliers en dos etapas: M-estimador de Huber (c=2.576) y compuerta de Mahalanobis (gamma=3.891).
"""

from __future__ import annotations
import math
from typing import List, Tuple, Optional

class DynamicKalmanFilter:
    """
    Filtro de Kalman 2D en espacio de estados con M-estimador robusto:
    theta_t = [alpha_t, beta_t]^T
    Y_t = alpha_t + beta_t * X_t + v_t
    """
    def __init__(
        self,
        delta: float = 1.0e-4, # Vida media de 6,931 ticks (~17.3 min)
        R_0: float = 1.0e-2,   # Varianza base inicial
        R: Optional[float] = None, # Alias para compatibilidad
        R_min: float = 1.0e-5, # Piso de singularidad
        lambda_R: float = 0.95,# Decaimiento de memoria de innovación
        c_huber: float = 2.576,# 99% Intervalo de confianza Huber
        gamma_mahalanobis: float = 3.891, # 99.99% CI Chi-cuadrado
        memory_window: int = 50,
    ):
        self.delta = delta
        initial_r = R if R is not None else R_0
        self.R = initial_r
        self.R_min = R_min
        self.lambda_R = lambda_R
        self.c_huber = c_huber
        self.gamma_mahalanobis = gamma_mahalanobis
        self.memory_window = memory_window

        self.theta = [0.0, 1.0] # [alpha_0, beta_0]
        self.P = [[1.0, 0.0], [0.0, 1.0]] # Covarianza a posteriori
        self.innov_sq_ewma = initial_r
        self.error_history: List[float] = []

    def update(self, y: float, x: float) -> Tuple[float, float, float]:
        """
        Ejecuta el ciclo recursivo a priori -> innovación robusta -> actualización a posteriori.
        Retorna: (alpha_t, beta_t, z_score_spread)
        """
        # 1. Predicción a priori con factor delta adaptativo
        # P_{t|t-1} = P_{t-1|t-1} / (1 - delta)
        scale_p = 1.0 / max(1e-6, 1.0 - self.delta)
        P_prior = [
            [self.P[0][0] * scale_p, self.P[0][1] * scale_p],
            [self.P[1][0] * scale_p, self.P[1][1] * scale_p]
        ]

        # 2. Innovación Cruda: nu_t = y_t - (alpha_{t-1} + beta_{t-1} * x_t)
        H = [1.0, x]
        y_pred = self.theta[0] + self.theta[1] * x
        raw_error = y - y_pred

        # 3. Varianza teórica de la Innovación S_t = H P H^T + R_t
        HP0 = H[0] * P_prior[0][0] + H[1] * P_prior[1][0]
        HP1 = H[0] * P_prior[0][1] + H[1] * P_prior[1][1]
        H_P_HT = HP0 * H[0] + HP1 * H[1]
        S = H_P_HT + self.R

        std_S = math.sqrt(max(1e-9, S))
        normalized_error = raw_error / std_S

        # 4. Rechazo de Outliers Etapa 1: Compuerta de Mahalanobis dura
        if abs(normalized_error) > self.gamma_mahalanobis:
            # Anomalía severa (salto falso o tick corrupto): no deformar el estado
            z_ret = self._calc_z_score(raw_error)
            return self.theta[0], self.theta[1], z_ret

        # 5. Atenuación Robusta Etapa 2: Ponderación M-estimador de Huber
        if abs(normalized_error) <= self.c_huber:
            psi_error = raw_error
        else:
            # Atenuar error cuadrático a lineal
            psi_error = self.c_huber * std_S * math.copysign(1.0, raw_error)

        # 6. Adaptación de Varianza de Observación R_t
        # Actualización recursiva ponderada de la varianza residual
        self.innov_sq_ewma = self.lambda_R * self.innov_sq_ewma + (1.0 - self.lambda_R) * (psi_error ** 2)
        self.R = max(self.R_min, self.innov_sq_ewma)
        S = max(1e-9, H_P_HT + self.R)

        # 7. Ganancia de Kalman K_t = P_{t|t-1} H^T / S
        K = [
            (P_prior[0][0] * H[0] + P_prior[0][1] * H[1]) / S,
            (P_prior[1][0] * H[0] + P_prior[1][1] * H[1]) / S
        ]

        # 8. Actualización a posteriori del Estado con error Huber
        self.theta[0] += K[0] * psi_error
        self.theta[1] += K[1] * psi_error

        # 9. Actualización de Covarianza P = (I - K H) P_{prior}
        KH = [
            [K[0] * H[0], K[0] * H[1]],
            [K[1] * H[0], K[1] * H[1]]
        ]
        self.P = [
            [P_prior[0][0] - (KH[0][0] * P_prior[0][0] + KH[0][1] * P_prior[1][0]),
             P_prior[0][1] - (KH[0][0] * P_prior[0][1] + KH[0][1] * P_prior[1][0])],
            [P_prior[1][0] - (KH[1][0] * P_prior[0][0] + KH[1][1] * P_prior[1][0]),
             P_prior[1][1] - (KH[1][0] * P_prior[0][0] + KH[1][1] * P_prior[1][0])]
        ]

        # 10. Historial y Z-Score Normalizado
        self.error_history.append(raw_error)
        if len(self.error_history) > self.memory_window:
            self.error_history.pop(0)

        z_score = self._calc_z_score(raw_error)
        return self.theta[0], self.theta[1], z_score

    def _calc_z_score(self, current_err: float) -> float:
        if len(self.error_history) < 2:
            return 0.0
        mean_e = sum(self.error_history) / len(self.error_history)
        var_e = sum((e - mean_e) ** 2 for e in self.error_history) / max(1, len(self.error_history) - 1)
        std_e = math.sqrt(var_e) if var_e > 1e-6 else 1.0
        return (current_err - mean_e) / std_e
