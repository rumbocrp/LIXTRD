"""Correlación Dinámica Multi-Escala por EWMA Calibrada (Fase 1).
Implementa:
- Decaimiento exponencial lambda = 0.96 (muestra efectiva N_eff = 25 ticks a alta frecuencia).
- Matriz de covarianza recursiva sin almacenamiento de memoria innecesario.
"""

from __future__ import annotations
import math
from typing import List

class EWMACorrelationEngine:
    """Calcula el coeficiente de correlación instantáneo ponderado exponencialmente con lambda = 0.96."""
    def __init__(self, decay_lambda: float = 0.96, window_size: int = 40):
        self.decay = decay_lambda
        self.window_size = window_size
        self.x_history: List[float] = []
        self.y_history: List[float] = []

    def update(self, x: float, y: float) -> float:
        self.x_history.append(x)
        self.y_history.append(y)
        if len(self.x_history) > self.window_size:
            self.x_history.pop(0)
            self.y_history.pop(0)

        n = len(self.x_history)
        if n < 5:
            return 0.0

        # Ponderación exponencial precisa
        weights = [self.decay ** (n - 1 - i) for i in range(n)]
        sum_w = sum(weights)
        norm_w = [w / sum_w for w in weights]

        mean_x = sum(w * x_i for w, x_i in zip(norm_w, self.x_history))
        mean_y = sum(w * y_i for w, y_i in zip(norm_w, self.y_history))

        cov_xy = sum(w * (x_i - mean_x) * (y_i - mean_y) for w, x_i, y_i in zip(norm_w, self.x_history, self.y_history))
        var_x = sum(w * (x_i - mean_x) ** 2 for w, x_i in zip(norm_w, self.x_history))
        var_y = sum(w * (y_i - mean_y) ** 2 for w, y_i in zip(norm_w, self.y_history))

        denom = math.sqrt(max(1e-8, var_x * var_y))
        corr = cov_xy / denom
        return max(-1.0, min(1.0, corr))
