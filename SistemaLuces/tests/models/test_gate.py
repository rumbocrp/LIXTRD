"""Pruebas de la Matriz de Compuerta de Modelos CA-26 (SPEC-001 §6.8, §12.7, CA-26, WP-07)."""

from datetime import datetime, timezone
import unittest
import uuid

from sistema_luces.domain.manifest import ModelGatePolicyV1
from sistema_luces.models.gate import EvaluacionModeloV1, EvaluadorCompuertaModelo


def make_valid_test_evaluacion(
    cohort_hash: str = "a" * 64,
    cost_hash: str = "b" * 64,
    effective_sample_size: int = 500,
    brier_improvement_scaled: int = 50_000,
    ece_scaled: int = 80_000,  # <= 100_000 (0.10)
    net_utility_base_ci_lower: float = 15.0,  # strictly > 0
    net_utility_adverse: float = 5.0,  # >= 0
    profitable_walk_forward_ratio_scaled: int = 650_000,  # >= 600_000 (60%)
    leakage_violations_count: int = 0,
    is_out_of_fold_calibrated: bool = True,
    has_purged_embargo_splits: bool = True,
    severe_drift_detected: bool = False,
) -> EvaluacionModeloV1:
    now_utc = datetime(2026, 8, 29, 14, 30, 0, tzinfo=timezone.utc)
    return EvaluacionModeloV1(
        model_id=str(uuid.uuid4()),
        model_version="1.0.0",
        model_hash="c" * 64,
        dataset_manifest_hash="d" * 64,
        cohort_hash=cohort_hash,
        cost_hash=cost_hash,
        effective_sample_size=effective_sample_size,
        brier_score_scaled=150_000,
        brier_score_baseline_scaled=200_000,
        brier_improvement_scaled=brier_improvement_scaled,
        ece_scaled=ece_scaled,
        log_loss=0.45,
        net_utility_base=25.0,
        net_utility_base_ci_lower=net_utility_base_ci_lower,
        net_utility_base_ci_upper=35.0,
        net_utility_adverse=net_utility_adverse,
        net_utility_stress=0.0,
        walk_forward_folds_total=5,
        walk_forward_folds_profitable=4,
        profitable_walk_forward_ratio_scaled=profitable_walk_forward_ratio_scaled,
        leakage_violations_count=leakage_violations_count,
        is_out_of_fold_calibrated=is_out_of_fold_calibrated,
        has_purged_embargo_splits=has_purged_embargo_splits,
        severe_drift_detected=severe_drift_detected,
        evaluated_at_utc=now_utc,
    )


def make_valid_test_policy(
    cohort_hash: str = "a" * 64,
    cost_hash: str = "b" * 64,
    approver: str = "lead-architect",
) -> ModelGatePolicyV1:
    now_utc = datetime(2026, 8, 29, 14, 30, 0, tzinfo=timezone.utc)
    return ModelGatePolicyV1(
        policy_version="model-gate-policy-v1",
        leakage_violations_max=0,
        effective_sample_size_min=500,
        brier_improvement_min_scaled=0,
        ece_max_scaled=100_000,
        net_utility_base_ci_lower_exclusive=0,
        net_utility_adverse_min=0,
        profitable_walk_forward_ratio_min_scaled=600_000,
        purge_required=True,
        embargo_required=True,
        out_of_fold_calibration_required=True,
        severe_drift_allowed=False,
        cohort_hash=cohort_hash,
        cost_hash=cost_hash,
        approver=approver,
        approved_at_utc=now_utc,
    )


class TestModelGateEvaluatorMatrixCA26(unittest.TestCase):
    """Matriz exhaustiva de CA-26 según SPEC-001 §12.7."""

    def setUp(self) -> None:
        self.evaluator = EvaluadorCompuertaModelo()
        self.policy = make_valid_test_policy()

    def test_promotion_when_all_thresholds_met(self) -> None:
        """Candidato exactamente en todos los umbrales inclusivos y CI base estrictamente > 0 -> PROMOTION."""
        eval_candidate = make_valid_test_evaluacion(
            effective_sample_size=500,
            brier_improvement_scaled=0,
            ece_scaled=100_000,
            net_utility_base_ci_lower=0.001,
            net_utility_adverse=0.0,
            profitable_walk_forward_ratio_scaled=600_000,
            leakage_violations_count=0,
            is_out_of_fold_calibrated=True,
            has_purged_embargo_splits=True,
            severe_drift_detected=False,
        )
        res = self.evaluator.evaluar(eval_candidate, self.policy)
        self.assertTrue(res.exito)
        self.assertEqual("PROMOTION", res.datos.decision)
        self.assertTrue(res.datos.promoted)
        self.assertIn("MODEL_GATE_PASSED", res.datos.reason_codes)

    def test_rejection_missing_policy(self) -> None:
        """Política ausente -> REJECTED con MODEL_POLICY_MISSING."""
        eval_candidate = make_valid_test_evaluacion()
        res = self.evaluator.evaluar(eval_candidate, None)
        self.assertTrue(res.exito)
        self.assertEqual("REJECTED", res.datos.decision)
        self.assertFalse(res.datos.promoted)
        self.assertIn("MODEL_POLICY_MISSING", res.datos.reason_codes)

    def test_rejection_leakage_violation(self) -> None:
        """Fuga = 1 -> REJECTED con LEAKAGE_VIOLATION."""
        eval_candidate = make_valid_test_evaluacion(leakage_violations_count=1)
        res = self.evaluator.evaluar(eval_candidate, self.policy)
        self.assertTrue(res.exito)
        self.assertEqual("REJECTED", res.datos.decision)
        self.assertFalse(res.datos.promoted)
        self.assertIn("LEAKAGE_VIOLATION", res.datos.reason_codes)

    def test_rejection_insufficient_sample_size(self) -> None:
        """Muestra = 499 -> REJECTED con INSUFFICIENT_SAMPLE_SIZE."""
        eval_candidate = make_valid_test_evaluacion(effective_sample_size=499)
        res = self.evaluator.evaluar(eval_candidate, self.policy)
        self.assertTrue(res.exito)
        self.assertEqual("REJECTED", res.datos.decision)
        self.assertFalse(res.datos.promoted)
        self.assertIn("INSUFFICIENT_SAMPLE_SIZE", res.datos.reason_codes)

    def test_rejection_excessive_ece(self) -> None:
        """ECE = 100_001 -> REJECTED con EXCESSIVE_CALIBRATION_ERROR."""
        eval_candidate = make_valid_test_evaluacion(ece_scaled=100_001)
        res = self.evaluator.evaluar(eval_candidate, self.policy)
        self.assertTrue(res.exito)
        self.assertEqual("REJECTED", res.datos.decision)
        self.assertFalse(res.datos.promoted)
        self.assertIn("EXCESSIVE_CALIBRATION_ERROR", res.datos.reason_codes)

    def test_rejection_insufficient_walk_forward_ratio(self) -> None:
        """Ratio folds = 599_999 -> REJECTED con INSUFFICIENT_WALK_FORWARD_RATIO."""
        eval_candidate = make_valid_test_evaluacion(profitable_walk_forward_ratio_scaled=599_999)
        res = self.evaluator.evaluar(eval_candidate, self.policy)
        self.assertTrue(res.exito)
        self.assertEqual("REJECTED", res.datos.decision)
        self.assertFalse(res.datos.promoted)
        self.assertIn("INSUFFICIENT_WALK_FORWARD_RATIO", res.datos.reason_codes)

    def test_rejection_non_positive_net_utility_ci_lower(self) -> None:
        """CI base = 0 -> REJECTED con NON_POSITIVE_NET_UTILITY_CI_LOWER."""
        eval_candidate = make_valid_test_evaluacion(net_utility_base_ci_lower=0.0)
        res = self.evaluator.evaluar(eval_candidate, self.policy)
        self.assertTrue(res.exito)
        self.assertEqual("REJECTED", res.datos.decision)
        self.assertFalse(res.datos.promoted)
        self.assertIn("NON_POSITIVE_NET_UTILITY_CI_LOWER", res.datos.reason_codes)

    def test_rejection_negative_adverse_utility(self) -> None:
        """Utilidad adversa < 0 -> REJECTED con NEGATIVE_ADVERSE_NET_UTILITY."""
        eval_candidate = make_valid_test_evaluacion(net_utility_adverse=-0.01)
        res = self.evaluator.evaluar(eval_candidate, self.policy)
        self.assertTrue(res.exito)
        self.assertEqual("REJECTED", res.datos.decision)
        self.assertFalse(res.datos.promoted)
        self.assertIn("NEGATIVE_ADVERSE_NET_UTILITY", res.datos.reason_codes)

    def test_rejection_in_fold_calibration(self) -> None:
        """Calibración in-fold -> REJECTED con IN_FOLD_CALIBRATION_FORBIDDEN."""
        eval_candidate = make_valid_test_evaluacion(is_out_of_fold_calibrated=False)
        res = self.evaluator.evaluar(eval_candidate, self.policy)
        self.assertTrue(res.exito)
        self.assertEqual("REJECTED", res.datos.decision)
        self.assertFalse(res.datos.promoted)
        self.assertIn("IN_FOLD_CALIBRATION_FORBIDDEN", res.datos.reason_codes)

    def test_rejection_missing_purge_or_embargo(self) -> None:
        """Falta purga/embargo -> REJECTED con PURGE_EMBARGO_SPLITS_REQUIRED."""
        eval_candidate = make_valid_test_evaluacion(has_purged_embargo_splits=False)
        res = self.evaluator.evaluar(eval_candidate, self.policy)
        self.assertTrue(res.exito)
        self.assertEqual("REJECTED", res.datos.decision)
        self.assertFalse(res.datos.promoted)
        self.assertIn("PURGE_EMBARGO_SPLITS_REQUIRED", res.datos.reason_codes)

    def test_rejection_severe_drift(self) -> None:
        """Drift severo -> REJECTED con SEVERE_DRIFT_DETECTED."""
        eval_candidate = make_valid_test_evaluacion(severe_drift_detected=True)
        res = self.evaluator.evaluar(eval_candidate, self.policy)
        self.assertTrue(res.exito)
        self.assertEqual("REJECTED", res.datos.decision)
        self.assertFalse(res.datos.promoted)
        self.assertIn("SEVERE_DRIFT_DETECTED", res.datos.reason_codes)

    def test_rejection_cohort_and_cost_hash_mismatch(self) -> None:
        """Hash de cohorte o costos no coincide -> REJECTED con COHORT_HASH_MISMATCH / COST_HASH_MISMATCH."""
        eval_candidate = make_valid_test_evaluacion(cohort_hash="f" * 64, cost_hash="e" * 64)
        res = self.evaluator.evaluar(eval_candidate, self.policy)
        self.assertTrue(res.exito)
        self.assertEqual("REJECTED", res.datos.decision)
        self.assertFalse(res.datos.promoted)
        self.assertIn("COHORT_HASH_MISMATCH", res.datos.reason_codes)
        self.assertIn("COST_HASH_MISMATCH", res.datos.reason_codes)


if __name__ == "__main__":
    unittest.main()
