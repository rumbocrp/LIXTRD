"""Compuerta de evaluación de modelos y promoción formal (SPEC-001 §6.8, §12.7, CA-26, WP-07)."""

from dataclasses import dataclass
from datetime import datetime, timezone
import re
from typing import Any, Literal
import uuid

from sistema_luces.domain.error import ErrorDominio
from sistema_luces.domain.manifest import ModelGatePolicyV1, validar_model_gate_policy
from sistema_luces.domain.result import Resultado, exito, fallo

_UUID_REGEX = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE)


@dataclass(frozen=True)
class EvaluacionModeloV1:
    """Documento inmutable con los resultados de evaluación predictiva y económica de un modelo candidato."""

    model_id: str
    model_version: str
    model_hash: str
    dataset_manifest_hash: str
    cohort_hash: str
    cost_hash: str
    effective_sample_size: int
    brier_score_scaled: int
    brier_score_baseline_scaled: int
    brier_improvement_scaled: int  # brier_score_baseline_scaled - brier_score_scaled
    ece_scaled: int  # Expected Calibration Error escalado 0..1_000_000
    log_loss: float
    net_utility_base: float
    net_utility_base_ci_lower: float  # Cota inferior 95% CI
    net_utility_base_ci_upper: float
    net_utility_adverse: float
    net_utility_stress: float
    walk_forward_folds_total: int
    walk_forward_folds_profitable: int
    profitable_walk_forward_ratio_scaled: int  # 0..1_000_000
    leakage_violations_count: int
    is_out_of_fold_calibrated: bool
    has_purged_embargo_splits: bool
    severe_drift_detected: bool
    evaluated_at_utc: datetime
    evaluation_id: str = ""

    def __post_init__(self) -> None:
        if not self.evaluation_id:
            object.__setattr__(self, "evaluation_id", str(uuid.uuid4()))


@dataclass(frozen=True)
class DecisionCompuertaModelo:
    """Resultado formal de la evaluación de compuerta para promoción de modelo a producción/simulación."""

    decision_id: str
    model_id: str
    model_hash: str
    policy_version: str
    decision: Literal["PROMOTION", "REJECTED"]
    promoted: bool
    passed_checks: tuple[str, ...]
    failed_checks: tuple[str, ...]
    reason_codes: tuple[str, ...]
    evaluated_at_utc: datetime


class EvaluadorCompuertaModelo:
    """Evalúa candidatos a modelo contra la política estricta model-gate-policy-v1 (CA-26, §12.7)."""

    def evaluar(
        self,
        evaluacion: EvaluacionModeloV1,
        politica: ModelGatePolicyV1 | None,
        decision_id: str | None = None,
    ) -> Resultado[DecisionCompuertaModelo]:
        """Aplica la matriz de evaluación y retorna la decisión de promoción o rechazo."""
        now_utc = datetime.now(timezone.utc)
        d_id = decision_id or str(uuid.uuid4())

        # 1. Validación de presencia y validez de la política
        if politica is None:
            return exito(
                DecisionCompuertaModelo(
                    decision_id=d_id,
                    model_id=evaluacion.model_id,
                    model_hash=evaluacion.model_hash,
                    policy_version="UNKNOWN",
                    decision="REJECTED",
                    promoted=False,
                    passed_checks=(),
                    failed_checks=("POLICY_PRESENT",),
                    reason_codes=("MODEL_POLICY_MISSING",),
                    evaluated_at_utc=now_utc,
                )
            )

        res_pol = validar_model_gate_policy(politica)
        if not res_pol.exito:
            return exito(
                DecisionCompuertaModelo(
                    decision_id=d_id,
                    model_id=evaluacion.model_id,
                    model_hash=evaluacion.model_hash,
                    policy_version=politica.policy_version,
                    decision="REJECTED",
                    promoted=False,
                    passed_checks=(),
                    failed_checks=("POLICY_VALID",),
                    reason_codes=("MODEL_POLICY_MISSING",),
                    evaluated_at_utc=now_utc,
                )
            )

        passed: list[str] = []
        failed: list[str] = []
        reasons: list[str] = []

        # 2. Verificación de cero fuga de datos (CA-26)
        if evaluacion.leakage_violations_count <= politica.leakage_violations_max:
            passed.append("ZERO_DATA_LEAKAGE")
        else:
            failed.append("ZERO_DATA_LEAKAGE")
            reasons.append("LEAKAGE_VIOLATION")

        # 3. Verificación de tamaño de muestra efectivo
        min_samples = politica.effective_sample_size_min or politica.min_effective_sample_size
        if evaluacion.effective_sample_size >= min_samples:
            passed.append("SAMPLE_SIZE")
        else:
            failed.append("SAMPLE_SIZE")
            reasons.append("INSUFFICIENT_SAMPLE_SIZE")

        # 4. Verificación de mejora de Brier score contra referencia
        if evaluacion.brier_improvement_scaled >= politica.brier_improvement_min_scaled:
            passed.append("BRIER_IMPROVEMENT")
        else:
            failed.append("BRIER_IMPROVEMENT")
            reasons.append("INSUFFICIENT_BRIER_IMPROVEMENT")

        # 5. Verificación de error de calibración ECE <= 0.10 (100_000)
        max_ece = politica.ece_max_scaled or politica.max_calibration_ece
        if evaluacion.ece_scaled <= max_ece:
            passed.append("CALIBRATION_ECE")
        else:
            failed.append("CALIBRATION_ECE")
            reasons.append("EXCESSIVE_CALIBRATION_ERROR")

        # 6. Verificación de utilidad neta en escenario base: CI inferior estrictamente > 0
        if evaluacion.net_utility_base_ci_lower > politica.net_utility_base_ci_lower_exclusive:
            passed.append("NET_UTILITY_BASE_CI")
        else:
            failed.append("NET_UTILITY_BASE_CI")
            reasons.append("NON_POSITIVE_NET_UTILITY_CI_LOWER")

        # 7. Verificación de utilidad neta en escenario adverso >= 0
        if evaluacion.net_utility_adverse >= politica.net_utility_adverse_min:
            passed.append("NET_UTILITY_ADVERSE")
        else:
            failed.append("NET_UTILITY_ADVERSE")
            reasons.append("NEGATIVE_ADVERSE_NET_UTILITY")

        # 8. Verificación de ratio de folds positivos en walk-forward (>= 600_000)
        min_wf = politica.profitable_walk_forward_ratio_min_scaled or politica.min_walk_forward_positive_ratio
        if evaluacion.profitable_walk_forward_ratio_scaled >= min_wf:
            passed.append("WALK_FORWARD_RATIO")
        else:
            failed.append("WALK_FORWARD_RATIO")
            reasons.append("INSUFFICIENT_WALK_FORWARD_RATIO")

        # 9. Verificación de calibración Out-of-Fold obligatoria (in-fold prohibida)
        if politica.out_of_fold_calibration_required or politica.require_out_of_fold_calibration:
            if evaluacion.is_out_of_fold_calibrated:
                passed.append("OUT_OF_FOLD_CALIBRATION")
            else:
                failed.append("OUT_OF_FOLD_CALIBRATION")
                reasons.append("IN_FOLD_CALIBRATION_FORBIDDEN")

        # 10. Verificación de purga y embargo en splits
        if (politica.purge_required and politica.embargo_required) or politica.require_purged_embargo_splits:
            if evaluacion.has_purged_embargo_splits:
                passed.append("PURGE_EMBARGO_SPLITS")
            else:
                failed.append("PURGE_EMBARGO_SPLITS")
                reasons.append("PURGE_EMBARGO_SPLITS_REQUIRED")

        # 11. Verificación de drift severo
        if not politica.severe_drift_allowed:
            if not evaluacion.severe_drift_detected:
                passed.append("DRIFT_CHECK")
            else:
                failed.append("DRIFT_CHECK")
                reasons.append("SEVERE_DRIFT_DETECTED")

        # 12. Verificación de concordancia de hashes de cohortes y costos
        if evaluacion.cohort_hash.lower() == politica.cohort_hash.lower():
            passed.append("COHORT_HASH")
        else:
            failed.append("COHORT_HASH")
            reasons.append("COHORT_HASH_MISMATCH")

        if evaluacion.cost_hash.lower() == politica.cost_hash.lower():
            passed.append("COST_HASH")
        else:
            failed.append("COST_HASH")
            reasons.append("COST_HASH_MISMATCH")

        # Decisión final: PROMOTION solo si 100% de los checks pasan
        is_promoted = len(failed) == 0
        decision_str: Literal["PROMOTION", "REJECTED"] = "PROMOTION" if is_promoted else "REJECTED"

        decision = DecisionCompuertaModelo(
            decision_id=d_id,
            model_id=evaluacion.model_id,
            model_hash=evaluacion.model_hash,
            policy_version=politica.policy_version,
            decision=decision_str,
            promoted=is_promoted,
            passed_checks=tuple(passed),
            failed_checks=tuple(failed),
            reason_codes=tuple(reasons) if not is_promoted else ("MODEL_GATE_PASSED",),
            evaluated_at_utc=now_utc,
        )

        return exito(decision)
