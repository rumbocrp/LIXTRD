"""Modelos predictivos base y de regresión logística (SPEC-001 §6.8, WP-07)."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import math
import re
from typing import Any, Literal, Sequence
import uuid

from sistema_luces.domain.error import ErrorDominio
from sistema_luces.domain.event import canonical_json_bytes
from sistema_luces.domain.result import Resultado, exito, fallo

_UUID_REGEX = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE)
_HASH_REGEX = re.compile(r"^[0-9a-f]{64}$", re.IGNORECASE)


def sigmoid(z: float) -> float:
    """Función sigmoide numéricamente estable."""
    if z >= 35.0:
        return 1.0
    if z <= -35.0:
        return 0.0
    return 1.0 / (1.0 + math.exp(-z))


@dataclass(frozen=True)
class ModeloPredictivoV1:
    """Artefacto inmutable de modelo predictivo indexado por SHA-256 (SPEC-001 §6.8)."""

    model_id: str
    model_name: str
    model_version: str
    model_hash: str
    feature_names: tuple[str, ...]
    feature_set_version: str
    model_type: Literal["BASELINE", "LOGISTIC_REGRESSION", "CUSTOM"]
    parameters: dict[str, Any]
    created_at_utc: datetime
    schema_version: int = 1

    def predecir_raw(self, features: dict[str, Any] | Sequence[float]) -> Resultado[tuple[int, int]]:
        """Calcula scores crudos LONG y SHORT como enteros escalados 0..1_000_000."""
        raise NotImplementedError

    def predecir_calibrado(self, features: dict[str, Any] | Sequence[float]) -> Resultado[tuple[int, int]]:
        """Calcula probabilidades calibradas LONG y SHORT como enteros escalados 0..1_000_000."""
        raise NotImplementedError


def calcular_hash_modelo(
    model_name: str,
    model_version: str,
    feature_names: Sequence[str],
    feature_set_version: str,
    model_type: str,
    parameters: dict[str, Any],
) -> str:
    """Calcula el hash SHA-256 canónico del modelo a partir de sus parámetros."""
    canonical_repr = {
        "model_name": model_name,
        "model_version": model_version,
        "feature_names": sorted(list(feature_names)),
        "feature_set_version": feature_set_version,
        "model_type": model_type,
        "parameters": parameters,
    }
    return hashlib.sha256(canonical_json_bytes(canonical_repr)).hexdigest()


@dataclass(frozen=True)
class ModeloBaseV1(ModeloPredictivoV1):
    """Modelo base de tasa previa / heurística de momentum predeclarada."""

    def __init__(
        self,
        model_id: str | None = None,
        model_name: str = "baseline-prior-v1",
        model_version: str = "1.0.0",
        feature_names: Sequence[str] = ("order_imbalance", "price_return_points"),
        feature_set_version: str = "features-v1",
        prior_long_scaled: int = 500_000,
        prior_short_scaled: int = 500_000,
        momentum_factor: float = 0.0,
        created_at_utc: datetime | None = None,
    ) -> None:
        actual_id = model_id or str(uuid.uuid4())
        created_dt = created_at_utc or datetime.now(timezone.utc)
        params = {
            "prior_long_scaled": prior_long_scaled,
            "prior_short_scaled": prior_short_scaled,
            "momentum_factor": momentum_factor,
        }
        computed_hash = calcular_hash_modelo(
            model_name=model_name,
            model_version=model_version,
            feature_names=feature_names,
            feature_set_version=feature_set_version,
            model_type="BASELINE",
            parameters=params,
        )
        object.__setattr__(self, "model_id", actual_id)
        object.__setattr__(self, "model_name", model_name)
        object.__setattr__(self, "model_version", model_version)
        object.__setattr__(self, "model_hash", computed_hash)
        object.__setattr__(self, "feature_names", tuple(feature_names))
        object.__setattr__(self, "feature_set_version", feature_set_version)
        object.__setattr__(self, "model_type", "BASELINE")
        object.__setattr__(self, "parameters", params)
        object.__setattr__(self, "created_at_utc", created_dt)
        object.__setattr__(self, "schema_version", 1)

    def predecir_raw(self, features: dict[str, Any] | Sequence[float]) -> Resultado[tuple[int, int]]:
        prior_l = self.parameters.get("prior_long_scaled", 500_000)
        prior_s = self.parameters.get("prior_short_scaled", 500_000)
        mom = self.parameters.get("momentum_factor", 0.0)

        score_l = float(prior_l)
        score_s = float(prior_s)

        if mom != 0.0 and isinstance(features, dict):
            imb = features.get("order_imbalance")
            if isinstance(imb, (int, float)):
                # imb is in -1_000_000..1_000_000
                delta = float(imb) * mom * 0.1
                score_l += delta
                score_s -= delta

        raw_l = max(0, min(1_000_000, int(round(score_l))))
        raw_s = max(0, min(1_000_000, int(round(score_s))))
        return exito((raw_l, raw_s))

    def predecir_calibrado(self, features: dict[str, Any] | Sequence[float]) -> Resultado[tuple[int, int]]:
        return self.predecir_raw(features)


@dataclass(frozen=True)
class ModeloRegresionLogisticaV1(ModeloPredictivoV1):
    """Modelo de Regresión Logística multivariada con soporte direccional LONG y SHORT."""

    def __init__(
        self,
        model_id: str | None = None,
        model_name: str = "logreg-us500-v1",
        model_version: str = "1.0.0",
        feature_names: Sequence[str] = (),
        feature_set_version: str = "features-v1",
        weights_long: Sequence[float] = (),
        bias_long: float = 0.0,
        weights_short: Sequence[float] = (),
        bias_short: float = 0.0,
        means: Sequence[float] | None = None,
        stds: Sequence[float] | None = None,
        created_at_utc: datetime | None = None,
    ) -> None:
        actual_id = model_id or str(uuid.uuid4())
        created_dt = created_at_utc or datetime.now(timezone.utc)
        f_names = tuple(feature_names)
        n_feats = len(f_names)

        w_long = tuple(float(w) for w in weights_long) if weights_long else tuple(0.0 for _ in range(n_feats))
        w_short = tuple(float(w) for w in weights_short) if weights_short else tuple(0.0 for _ in range(n_feats))
        mean_tup = tuple(float(m) for m in means) if means else tuple(0.0 for _ in range(n_feats))
        std_tup = tuple(float(s) for s in stds) if stds else tuple(1.0 for _ in range(n_feats))

        params = {
            "weights_long": list(w_long),
            "bias_long": float(bias_long),
            "weights_short": list(w_short),
            "bias_short": float(bias_short),
            "means": list(mean_tup),
            "stds": list(std_tup),
        }
        computed_hash = calcular_hash_modelo(
            model_name=model_name,
            model_version=model_version,
            feature_names=f_names,
            feature_set_version=feature_set_version,
            model_type="LOGISTIC_REGRESSION",
            parameters=params,
        )

        object.__setattr__(self, "model_id", actual_id)
        object.__setattr__(self, "model_name", model_name)
        object.__setattr__(self, "model_version", model_version)
        object.__setattr__(self, "model_hash", computed_hash)
        object.__setattr__(self, "feature_names", f_names)
        object.__setattr__(self, "feature_set_version", feature_set_version)
        object.__setattr__(self, "model_type", "LOGISTIC_REGRESSION")
        object.__setattr__(self, "parameters", params)
        object.__setattr__(self, "created_at_utc", created_dt)
        object.__setattr__(self, "schema_version", 1)

    def _extraer_vector(self, features: dict[str, Any] | Sequence[float]) -> list[float]:
        vec: list[float] = []
        if isinstance(features, dict):
            for fname in self.feature_names:
                val = features.get(fname)
                if val is None or not isinstance(val, (int, float)):
                    vec.append(0.0)
                else:
                    vec.append(float(val))
        else:
            vec = [float(v) for v in features[: len(self.feature_names)]]
            while len(vec) < len(self.feature_names):
                vec.append(0.0)
        return vec

    def _estandarizar(self, vec: Sequence[float]) -> list[float]:
        means = self.parameters.get("means", [])
        stds = self.parameters.get("stds", [])
        out: list[float] = []
        for i, val in enumerate(vec):
            m = means[i] if i < len(means) else 0.0
            s = stds[i] if i < len(stds) and stds[i] > 1e-12 else 1.0
            out.append((val - m) / s)
        return out

    def predecir_raw(self, features: dict[str, Any] | Sequence[float]) -> Resultado[tuple[int, int]]:
        """Calcula probabilidades crudas sigmoides escaladas 0..1_000_000."""
        vec = self._extraer_vector(features)
        vec_norm = self._estandarizar(vec)

        w_long = self.parameters.get("weights_long", [])
        b_long = self.parameters.get("bias_long", 0.0)
        w_short = self.parameters.get("weights_short", [])
        b_short = self.parameters.get("bias_short", 0.0)

        logit_l = b_long + sum(w * x for w, x in zip(w_long, vec_norm))
        logit_s = b_short + sum(w * x for w, x in zip(w_short, vec_norm))

        p_long = sigmoid(logit_l)
        p_short = sigmoid(logit_s)

        scaled_l = max(0, min(1_000_000, int(round(p_long * 1_000_000))))
        scaled_s = max(0, min(1_000_000, int(round(p_short * 1_000_000))))
        return exito((scaled_l, scaled_s))

    def predecir_calibrado(self, features: dict[str, Any] | Sequence[float]) -> Resultado[tuple[int, int]]:
        return self.predecir_raw(features)

    @classmethod
    def entrenar(
        cls,
        feature_names: Sequence[str],
        X: Sequence[Sequence[float]],
        y_long: Sequence[int],
        y_short: Sequence[int],
        feature_set_version: str = "features-v1",
        model_name: str = "logreg-us500-v1",
        model_version: str = "1.0.0",
        learning_rate: float = 0.05,
        l2_reg: float = 0.01,
        max_epochs: int = 150,
    ) -> Resultado["ModeloRegresionLogisticaV1"]:
        """Entrena un modelo de regresión logística usando descenso de gradiente determinista."""
        n_samples = len(X)
        if n_samples == 0:
            return fallo(
                ErrorDominio(
                    codigo="VALIDATION_ERROR",
                    mensaje_seguro="Se requieren muestras de entrenamiento para ajustar el modelo",
                    reintentable=False,
                    correlation_id="",
                    detalles={"n_samples": 0},
                )
            )

        n_features = len(feature_names)

        # 1. Estandarización de variables
        means: list[float] = [0.0] * n_features
        stds: list[float] = [1.0] * n_features

        for j in range(n_features):
            col = [row[j] for row in X]
            m = sum(col) / n_samples
            var = sum((v - m) ** 2 for v in col) / n_samples
            s = math.sqrt(var) if var > 1e-12 else 1.0
            means[j] = m
            stds[j] = s

        X_norm: list[list[float]] = []
        for row in X:
            row_norm = [(row[j] - means[j]) / stds[j] for j in range(n_features)]
            X_norm.append(row_norm)

        # 2. Descenso de gradiente para LONG
        w_l = [0.0] * n_features
        b_l = 0.0

        for _ in range(max_epochs):
            grad_w = [0.0] * n_features
            grad_b = 0.0
            for i in range(n_samples):
                xi = X_norm[i]
                yi = y_long[i]
                z = b_l + sum(w * x for w, x in zip(w_l, xi))
                p = sigmoid(z)
                err = p - yi
                grad_b += err
                for j in range(n_features):
                    grad_w[j] += err * xi[j]

            # Actualizar con L2 penalty
            b_l -= learning_rate * (grad_b / n_samples)
            for j in range(n_features):
                w_l[j] -= learning_rate * ((grad_w[j] / n_samples) + l2_reg * w_l[j])

        # 3. Descenso de gradiente para SHORT
        w_s = [0.0] * n_features
        b_s = 0.0

        for _ in range(max_epochs):
            grad_w = [0.0] * n_features
            grad_b = 0.0
            for i in range(n_samples):
                xi = X_norm[i]
                yi = y_short[i]
                z = b_s + sum(w * x for w, x in zip(w_s, xi))
                p = sigmoid(z)
                err = p - yi
                grad_b += err
                for j in range(n_features):
                    grad_w[j] += err * xi[j]

            b_s -= learning_rate * (grad_b / n_samples)
            for j in range(n_features):
                w_s[j] -= learning_rate * ((grad_w[j] / n_samples) + l2_reg * w_s[j])

        modelo = cls(
            model_name=model_name,
            model_version=model_version,
            feature_names=feature_names,
            feature_set_version=feature_set_version,
            weights_long=w_l,
            bias_long=b_l,
            weights_short=w_s,
            bias_short=b_s,
            means=means,
            stds=stds,
        )
        return exito(modelo)
