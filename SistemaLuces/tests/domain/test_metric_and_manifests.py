"""Pruebas para métricas y manifiestos complementarios (SPEC-001 §6.7, §6.8)."""

from datetime import datetime, timezone
import unittest

from sistema_luces.domain.manifest import (
    CostProfileV1,
    DepthGatePolicyV1,
    ImportManifestV1,
    InstrumentProfileV1,
    ModelGatePolicyV1,
    RiskProfileV1,
    validar_cost_profile,
    validar_depth_gate_policy,
    validar_import_manifest,
    validar_instrument_profile,
    validar_model_gate_policy,
    validar_risk_profile,
)
from sistema_luces.domain.metric import PLANOS_METRICOS_PERMITIDOS, SnapshotMetricoV1, validar_snapshot_metrico


class MetricAndManifestTests(unittest.TestCase):
    def setUp(self) -> None:
        self.now_utc = datetime(2026, 8, 29, 14, 30, 0, tzinfo=timezone.utc)
        self.uuid_1 = "11111111-1111-1111-1111-111111111111"
        self.hash_64 = "a" * 64

    def test_planos_metricos_contiene_los_8_planos(self) -> None:
        expected = {
            "FEED",
            "SIGNALS",
            "PREDICTIVE",
            "ROBUSTNESS",
            "DEMO",
            "EXECUTION",
            "SECURITY",
            "TRACEABILITY",
        }
        self.assertEqual(expected, PLANOS_METRICOS_PERMITIDOS)

    def test_snapshot_metrico_valida_campos_y_preserva_none(self) -> None:
        # Valid computable metric
        snap_ok = SnapshotMetricoV1(
            metric_snapshot_id=self.uuid_1,
            metric_name="brier_score",
            metric_plane="PREDICTIVE",
            range_start_utc=self.now_utc,
            range_end_utc=self.now_utc,
            ny_session_date="2026-08-29",
            source="replay",
            environment="REPLAY",
            instrument="US500",
            strategy_version="1.0.0",
            model_version="1.0.0",
            policy_version="policy-v1",
            raw_count=100,
            effective_sample_size=95,
            value_int=250000,
            value_ratio_scaled=None,
            histogram_int=None,
            unit="scaled_ratio",
            scale=1_000_000,
            dimensions={"model_id": "logreg"},
            input_event_cutoff=self.now_utc,
            dataset_hash=self.hash_64,
            code_hash=self.hash_64,
            computed_at_utc=self.now_utc,
            schema_version=1,
        )
        self.assertTrue(validar_snapshot_metrico(snap_ok).exito)

        # Non-computable metric (value is None, preserve absence faithfully DM-6)
        snap_none = SnapshotMetricoV1(
            metric_snapshot_id=self.uuid_1,
            metric_name="net_pnl",
            metric_plane="DEMO",
            range_start_utc=self.now_utc,
            range_end_utc=self.now_utc,
            ny_session_date="2026-08-29",
            source="replay",
            environment="REPLAY",
            instrument="US500",
            strategy_version="1.0.0",
            model_version="1.0.0",
            policy_version="policy-v1",
            raw_count=0,
            effective_sample_size=0,
            value_int=None,
            value_ratio_scaled=None,
            histogram_int=None,
            unit="USD_cents",
            scale=100,
            dimensions={"reason": "INSUFFICIENT_OR_UNKNOWN_DATA"},
            input_event_cutoff=self.now_utc,
            dataset_hash=self.hash_64,
            code_hash=self.hash_64,
            computed_at_utc=self.now_utc,
            schema_version=1,
        )
        self.assertTrue(validar_snapshot_metrico(snap_none).exito)

    def test_instrument_profile_v1(self) -> None:
        prof_ok = InstrumentProfileV1(
            profile_version="us500-v1",
            instrument="US500",
            provider="Pepperstone",
            symbol_id="US500",
            price_scale=100,
            point_size=100,
            lot_min=10,
            lot_step=10,
            lot_max=500,
            currency="USD",
            point_value=100,
            economic_ready=True,
            validation_evidence_hash=self.hash_64,
        )
        self.assertTrue(validar_instrument_profile(prof_ok).exito)

    def test_risk_profile_v1(self) -> None:
        risk_ok = RiskProfileV1(
            profile_version="risk-us500-demo-v1",
            max_risk_per_trade_usd_cents=5000,
            max_daily_loss_usd_cents=25000,
            max_daily_drawdown_usd_cents=25000,
            max_consecutive_losses=3,
            max_daily_openings=10,
            max_concurrent_positions=1,
            max_reference_lots=500,
            stale_threshold_ms=5000,
            news_blackout_minutes=15,
            kill_switch_active=False,
        )
        self.assertTrue(validar_risk_profile(risk_ok).exito)

    def test_depth_gate_policy_v1(self) -> None:
        depth_ok = DepthGatePolicyV1(
            policy_version="depth-policy-v1",
            required_complete_sessions=5,
            minimum_event_coverage_scaled=950_000,
            minimum_sequence_continuity_scaled=999_900,
            maximum_unresolved_gaps=0,
            maximum_out_of_order=0,
            maximum_clock_rollbacks=0,
            maximum_stale_time_ratio_scaled=10_000,
            corpus_hash=self.hash_64,
            approver="lead-qa",
            approved_at_utc=self.now_utc,
        )
        self.assertTrue(validar_depth_gate_policy(depth_ok).exito)

    def test_model_gate_policy_v1(self) -> None:
        model_ok = ModelGatePolicyV1(
            policy_version="model-policy-v1",
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
            cohort_hash=self.hash_64,
            cost_hash=self.hash_64,
            approver="lead-architect",
            approved_at_utc=self.now_utc,
        )
        self.assertTrue(validar_model_gate_policy(model_ok).exito)


if __name__ == "__main__":
    unittest.main()
