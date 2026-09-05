"""Calibración Logística Out-of-Fold y Escalado Entero de Probabilidades (SPEC-001 §6.8, CA-26, WP-07)."""

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import math
from typing import Any, Sequence
import uuid

from sistema_luces.domain.error import ErrorDominio
from sistema_luces.domain.event import canonical_json_bytes
from sistema_luces.domain.result import Resultado, exito, fallo
from sistema_luces.models.baseline import sigmoid


@dataclass(frozen=True)
class CalibradorLogistico:
    """Calibrador logístico de Platt scaling ajustado estrictamente sobre predicciones Out-Of-Fold (CA-26)."""

    calibration_id: str
    calibration_version: str
    param_a: float  # Pendiente de Platt
    param_b: float  # Intercepto de Platt
    is_out_of_fold: bool
    created_at_utc: datetime
    calibration_hash: str
    schema_version: int = 1

    def calibrar(self, raw_score: float | int) -> int:
        """Aplica la calibración de Platt a un score o probabilidad cruda y retorna entero 0..1_000_000."""
        # Si la entrada es un entero escalado 0..1_000_000, convertimos a [0, 1] y luego a logit
        if isinstance(raw_score, int) and not isinstance(raw_score, bool) and raw_score >= 0:
            p_raw = max(1e-6, min(1.0 - 1e-6, raw_score / 1_000_000.0))
            z = math.log(p_raw / (1.0 - p_raw))
        else:
            z = float(raw_score)

        # Regresión logística de Platt: P = 1 / (1 + exp(A * z + B))
        f_val = self.param_a * z + self.param_b
        p_calib = sigmoid(-f_val)  # Note: 1 / (1 + exp(A*z + B)) = sigmoid(-(A*z + B))

        scaled_int = int(round(p_calib * 1_000_000))
        return max(0, min(1_000_000, scaled_int))

    def calibrar_par(self, raw_score_long: float | int, raw_score_short: float | int) -> tuple[int, int]:
        """Calibra un par de scores direccionales asegurando límites válidos 0..1_000_000."""
        p_long = self.calibrar(raw_score_long)
        p_short = self.calibrar(raw_score_short)
        return p_long, p_short

    @classmethod
    def ajustar_oof(
        cls,
        out_of_fold_scores: Sequence[float | int],
        y_true: Sequence[int],
        is_out_of_fold: bool = True,
        calibration_version: str = "calib-platt-v1",
        calibration_id: str | None = None,
        max_iters: int = 100,
    ) -> Resultado["CalibradorLogistico"]:
        """Ajusta los parámetros de Platt scaling sobre predicciones out-of-fold.

        Invariante CA-26: La calibración in-fold está estrictamente prohibida.
        """
        if not is_out_of_fold:
            return fallo(
                ErrorDominio(
                    codigo="VALIDATION_ERROR",
                    mensaje_seguro="Calibracion in-fold estrictamente prohibida por politica de gate (CA-26)",
                    reintentable=False,
                    correlation_id="",
                    detalles={"is_out_of_fold": False},
                )
            )

        n = len(out_of_fold_scores)
        if n < 10:
            return fallo(
                ErrorDominio(
                    codigo="VALIDATION_ERROR",
                    mensaje_seguro=f"Muestras OOF insuficientes ({n}) para calibracion de Platt",
                    reintentable=False,
                    correlation_id="",
                    detalles={"n_samples": n},
                )
            )

        # 1. Convertir scores a logits z
        z_list: list[float] = []
        for s in out_of_fold_scores:
            if isinstance(s, int) and not isinstance(s, bool) and s >= 0:
                p = max(1e-6, min(1.0 - 1e-6, s / 1_000_000.0))
                z = math.log(p / (1.0 - p))
            else:
                z = float(s)
            z_list.append(z)

        # 2. Objetivos suavizados de Platt (1999) para evitar sobreajuste
        n_pos = sum(1 for y in y_true if y == 1)
        n_neg = n - n_pos
        t_pos = (n_pos + 1.0) / (n_pos + 2.0) if n_pos > 0 else 0.9
        t_neg = 1.0 / (n_neg + 2.0) if n_neg > 0 else 0.1

        t_targets = [t_pos if y == 1 else t_neg for y in y_true]

        # 3. Optimización determinista de A y B (Platt scaling con descenso de gradiente / Newton)
        # Queremos minimizar cross-entropy: L(A, B) = - sum( t*log(p) + (1-t)*log(1-p) )
        # donde p = 1 / (1 + exp(A*z + B)) = sigmoid(-(A*z + B))
        # Inicialización estándar de Platt: A = -1.0, B = log((n_neg+1)/(n_pos+1))
        A = -1.0
        B = math.log((n_neg + 1.0) / (n_pos + 1.0)) if n_pos > 0 else 0.0

        lr = 0.05
        for _ in range(max_iters):
            grad_A = 0.0
            grad_B = 0.0
            for i in range(n):
                zi = z_list[i]
                ti = t_targets[i]
                # f = A * zi + B
                # p = 1 / (1 + exp(f)) = sigmoid(-f)
                f = A * zi + B
                p = sigmoid(-f)
                diff = p - ti  # dL/df = -(t - p) => dL/dA = -(p - t) * z
                grad_A += diff * zi
                grad_B += diff

            # Descenso de gradiente: A <- A - lr * dL/dA = A + lr * (sum (p - t) * z / n)
            A += lr * (grad_A / n)
            B += lr * (grad_B / n)

        actual_id = calibration_id or str(uuid.uuid4())
        created_dt = datetime.now(timezone.utc)

        params_dict = {
            "calibration_id": actual_id,
            "calibration_version": calibration_version,
            "param_a": float(A),
            "param_b": float(B),
            "is_out_of_fold": True,
            "n_samples": n,
        }
        calib_hash = hashlib.sha256(canonical_json_bytes(params_dict)).hexdigest()

        calibrador = cls(
            calibration_id=actual_id,
            calibration_version=calibration_version,
            param_a=A,
            param_b=B,
            is_out_of_fold=True,
            created_at_utc=created_dt,
            calibration_hash=calib_hash,
            schema_version=1,
        )
        return exito(calibrador)
