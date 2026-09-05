"""Detector de Drift de Distribución y Alertas de Degradación (SPEC-001 §6.8, WP-07)."""

from dataclasses import dataclass
from datetime import datetime, timezone
import math
from typing import Any, Literal, Sequence
import uuid


@dataclass(frozen=True)
class InformeDriftV1:
    """Informe inmutable de evaluación de drift sobre distribuciones de features."""

    report_id: str
    feature_psi: dict[str, float]
    max_psi: float
    status: Literal["HEALTHY", "WARNING", "SEVERE_DRIFT"]
    severe_drift_detected: bool
    drifted_features: tuple[str, ...]
    evaluated_at_utc: datetime


class DetectorDrift:
    """Calcula el Population Stability Index (PSI) y detecta cambios de distribución en features."""

    def __init__(self, psi_warning_threshold: float = 0.10, psi_severe_threshold: float = 0.25) -> None:
        self.psi_warning_threshold = psi_warning_threshold
        self.psi_severe_threshold = psi_severe_threshold

    def calcular_psi(
        self,
        reference_values: Sequence[float | int],
        current_values: Sequence[float | int],
        n_bins: int = 10,
        eps: float = 1e-4,
    ) -> float:
        """Calcula el PSI entre la distribución de referencia (baseline) y la actual."""
        n_ref = len(reference_values)
        n_cur = len(current_values)
        if n_ref == 0 or n_cur == 0:
            return 0.0

        ref_floats = sorted([float(v) for v in reference_values])
        cur_floats = [float(v) for v in current_values]

        # Determinar cortes de bins basados en cuantiles de referencia
        bin_edges: list[float] = []
        for i in range(1, n_bins):
            idx = int(i * (n_ref / n_bins))
            bin_edges.append(ref_floats[idx])

        # Conteo en bins
        ref_counts = [0] * n_bins
        cur_counts = [0] * n_bins

        for val in ref_floats:
            placed = False
            for b_idx, edge in enumerate(bin_edges):
                if val <= edge:
                    ref_counts[b_idx] += 1
                    placed = True
                    break
            if not placed:
                ref_counts[-1] += 1

        for val in cur_floats:
            placed = False
            for b_idx, edge in enumerate(bin_edges):
                if val <= edge:
                    cur_counts[b_idx] += 1
                    placed = True
                    break
            if not placed:
                cur_counts[-1] += 1

        # Calcular PSI con suavizado epsilon
        psi_total = 0.0
        for r_count, c_count in zip(ref_counts, cur_counts):
            p_ref = max(eps, r_count / n_ref)
            p_cur = max(eps, c_count / n_cur)
            term = (p_cur - p_ref) * math.log(p_cur / p_ref)
            psi_total += term

        return max(0.0, psi_total)

    def evaluar_drift(
        self,
        reference_dataset: dict[str, Sequence[float | int]],
        current_dataset: dict[str, Sequence[float | int]],
        report_id: str | None = None,
    ) -> InformeDriftV1:
        """Evalúa todas las features comunes y genera un informe integral de drift."""
        r_id = report_id or str(uuid.uuid4())
        now_utc = datetime.now(timezone.utc)

        feature_psi_map: dict[str, float] = {}
        drifted: list[str] = []
        max_psi = 0.0

        for fname, ref_vals in reference_dataset.items():
            if fname in current_dataset:
                cur_vals = current_dataset[fname]
                psi = self.calcular_psi(ref_vals, cur_vals)
                feature_psi_map[fname] = round(psi, 6)
                if psi > max_psi:
                    max_psi = psi
                if psi >= self.psi_severe_threshold:
                    drifted.append(fname)

        if max_psi >= self.psi_severe_threshold:
            status: Literal["HEALTHY", "WARNING", "SEVERE_DRIFT"] = "SEVERE_DRIFT"
            severe = True
        elif max_psi >= self.psi_warning_threshold:
            status = "WARNING"
            severe = False
        else:
            status = "HEALTHY"
            severe = False

        return InformeDriftV1(
            report_id=r_id,
            feature_psi=feature_psi_map,
            max_psi=round(max_psi, 6),
            status=status,
            severe_drift_detected=severe,
            drifted_features=tuple(drifted),
            evaluated_at_utc=now_utc,
        )
