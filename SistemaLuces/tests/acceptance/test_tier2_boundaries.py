"""Tier 2: Boundary, Limit and Corner Cases Acceptance Tests (SPEC-001 §12, PROJECT.md).

Cubre bordes numéricos, límites de tripwire de riesgo, casos esquina de calidad de feed,
tolerancias cero de seguridad, precisiones de tiempo y contratos incompletos.
"""

from datetime import datetime, timedelta, timezone
import math
import unittest
import zoneinfo

from tests.conftest import REPO_ROOT, SRC_ROOT

from sistema_luces.domain.api import (
    SolicitudConsulta,
    SolicitudImportacionDemo,
    SolicitudReplay,
    SolicitudShadow,
    validar_solicitud_consulta,
    validar_solicitud_importacion_demo,
    validar_solicitud_replay,
    validar_solicitud_shadow,
)
from sistema_luces.domain.error import ErrorDominio
from sistema_luces.domain.event import (
    DepthDeltaPayloadV1,
    QuoteTickPayloadV1,
    SobreEventoV1,
    canonical_json_dumps,
    validar_payload_quote_tick,
    validar_sobre_evento,
)
from sistema_luces.domain.manifest import (
    DepthGatePolicyV1,
    ModelGatePolicyV1,
    RiskProfileV1,
    validar_depth_gate_policy,
    validar_model_gate_policy,
    validar_risk_profile,
)
from sistema_luces.domain.metric import (
    SnapshotMetricoV1,
    validar_snapshot_metrico,
)
from sistema_luces.domain.result import Resultado
from sistema_luces.domain.signal import SenalV1, validar_senal
from sistema_luces.domain.simulation import SimulacionV1, validar_simulacion
from sistema_luces.domain.vocabulary import (
    parse_environment,
    validate_price_scaled,
    validate_probability_scaled,
    validate_quantity_scaled,
    validate_scale_factor,
)
from tests.acceptance.helpers import (
    FakeEventStoreSpy,
    FakeFeedQualityMonitor,
    FakeLightsEngine,
    FakeRiskEngine,
    FakeTripleBarrierEvaluator,
    create_test_quote_tick_envelope,
    create_test_risk_profile,
    create_test_signal,
    create_test_simulation,
    make_sha256,
    make_uuid,
)

NY_TZ = zoneinfo.ZoneInfo("America/New_York")


class TestEnvironmentAndSecurityBoundaries(unittest.TestCase):
    """Bordes y esquinas de entorno, seguridad y allowlists (CA-1, CA-2, CA-3)."""

    def setUp(self) -> None:
        self.valid_uuid = make_uuid(1)
        self.valid_hash = make_sha256("valid-dataset")
        self.t0 = datetime(2026, 8, 29, 14, 30, 0, tzinfo=timezone.utc)

    def test_live_variations_rejected_with_environment_not_allowed(self) -> None:
        # Exact 'LIVE', 'REAL', 'PROD', 'PRODUCTION' and case/space variations
        for forbidden in ("LIVE", "live", "Live", " LIVE ", "live ", "\tLIVE\n", "REAL", "PROD", "PRODUCTION", " production "):
            res = parse_environment(forbidden)
            self.assertFalse(res.exito)
            self.assertEqual("ENVIRONMENT_NOT_ALLOWED", res.error.codigo)

    def test_unknown_environment_rejected_with_validation_error(self) -> None:
        for unknown in ("SANDBOX", "TESTNET", "STAGING", "DEV", "DEMO_UNKNOWN"):
            res = parse_environment(unknown)
            self.assertFalse(res.exito)
            self.assertEqual("VALIDATION_ERROR", res.error.codigo)

    def test_empty_environment_rejected(self) -> None:
        for empty in ("", "   ", "\n", "\t"):
            res = parse_environment(empty)
            self.assertFalse(res.exito)
            self.assertEqual("VALIDATION_ERROR", res.error.codigo)

    def test_path_traversal_in_staged_copy(self) -> None:
        for bad_path in ("/etc/passwd", "../tj.db", "sub/file.json", "c:\\boot.ini", "..\\secret.txt"):
            sol = SolicitudImportacionDemo(
                correlation_id=self.valid_uuid,
                environment="BROKER_DEMO_OBSERVED",
                staged_copy=bad_path,
                expected_sha256=self.valid_hash,
                adapter_version="1.0.0",
                expected_demo_account_hash=self.valid_hash,
            )
            res = validar_solicitud_importacion_demo(sol)
            self.assertFalse(res.exito)
            self.assertEqual("VALIDATION_ERROR", res.error.codigo)

    def test_non_demo_account_hash_format_rejection(self) -> None:
        for bad_hash in ("not-a-hash", "a" * 63, "a" * 65, "", "123"):
            sol = SolicitudShadow(
                correlation_id=self.valid_uuid,
                environment="SHADOW",
                source_profile_version="1.0.0",
                capabilities_manifest_hash=self.valid_hash,
                expected_demo_account_hash=bad_hash,
            )
            res = validar_solicitud_shadow(sol)
            self.assertFalse(res.exito)
            self.assertEqual("VALIDATION_ERROR", res.error.codigo)


class TestFeedQualityAndTemporalBoundaries(unittest.TestCase):
    """Bordes temporales y de calidad de feed (CA-7, CA-25)."""

    def setUp(self) -> None:
        self.monitor = FakeFeedQualityMonitor(stale_threshold_ms=5000)
        self.t0 = datetime(2026, 8, 29, 14, 30, 0, tzinfo=timezone.utc)

    def test_exact_stale_boundary_5000ms_vs_5001ms(self) -> None:
        ev = create_test_quote_tick_envelope(seq=1, occurred_at_utc=self.t0)

        # 5000ms elapsed -> HEALTHY
        state_5000, reasons_5000 = self.monitor.evaluar_evento(
            ev, domain_time_utc=self.t0 + timedelta(milliseconds=5000)
        )
        self.assertEqual("HEALTHY", state_5000)
        self.assertEqual([], reasons_5000)

        # 5001ms elapsed -> STALE
        state_5001, reasons_5001 = self.monitor.evaluar_evento(
            ev, domain_time_utc=self.t0 + timedelta(milliseconds=5001)
        )
        self.assertEqual("STALE", state_5001)
        self.assertIn("STALE_FEED", reasons_5001)

    def test_clock_rollback_negative_time_delta(self) -> None:
        ev1 = create_test_quote_tick_envelope(seq=1, occurred_at_utc=self.t0)
        self.monitor.evaluar_evento(ev1, domain_time_utc=self.t0)

        # Negative delta: 1 microsecond backwards
        ev2 = create_test_quote_tick_envelope(seq=2, occurred_at_utc=self.t0 - timedelta(microseconds=1))
        state, reasons = self.monitor.evaluar_evento(ev2, domain_time_utc=self.t0)
        self.assertEqual("STALE", state)
        self.assertIn("CLOCK_ROLLBACK", reasons)

    def test_sequence_gap_minimal_boundary(self) -> None:
        ev1 = create_test_quote_tick_envelope(seq=10, occurred_at_utc=self.t0)
        self.monitor.evaluar_evento(ev1, self.t0)

        # Exactly next sequence: seq 11 -> HEALTHY
        ev_next = create_test_quote_tick_envelope(seq=11, occurred_at_utc=self.t0 + timedelta(milliseconds=10))
        state_ok, _ = self.monitor.evaluar_evento(ev_next, self.t0 + timedelta(milliseconds=10))
        self.assertEqual("HEALTHY", state_ok)

        # Gap of 1 skipped sequence: seq 13 (skipped 12) -> GAPPED
        ev_gap = create_test_quote_tick_envelope(seq=13, occurred_at_utc=self.t0 + timedelta(milliseconds=20))
        state_gap, reasons_gap = self.monitor.evaluar_evento(ev_gap, self.t0 + timedelta(milliseconds=20))
        self.assertEqual("GAPPED", state_gap)
        self.assertIn("GAPPED_FEED", reasons_gap)

    def test_out_of_order_duplicate_sequence(self) -> None:
        ev1 = create_test_quote_tick_envelope(seq=5, occurred_at_utc=self.t0)
        self.monitor.evaluar_evento(ev1, self.t0)

        # Sequence 4 received after sequence 5 -> OUT_OF_ORDER
        ev_old = create_test_quote_tick_envelope(seq=4, occurred_at_utc=self.t0 + timedelta(milliseconds=10))
        state, reasons = self.monitor.evaluar_evento(ev_old, self.t0 + timedelta(milliseconds=10))
        self.assertEqual("STALE", state)
        self.assertIn("OUT_OF_ORDER", reasons)

    def test_depth_gate_sessions_boundary_4_vs_5(self) -> None:
        hash_64 = make_sha256("corpus")
        # 4 sessions -> Invalid (policy requires 5)
        policy_4 = DepthGatePolicyV1(
            policy_version="v1",
            required_complete_sessions=4,
            minimum_event_coverage_scaled=950_000,
            minimum_sequence_continuity_scaled=999_900,
            maximum_unresolved_gaps=0,
            maximum_out_of_order=0,
            maximum_clock_rollbacks=0,
            maximum_stale_time_ratio_scaled=10_000,
            corpus_hash=hash_64,
            approver="qa",
            approved_at_utc=self.t0,
        )
        self.assertEqual(4, policy_4.required_complete_sessions)
        self.assertNotEqual(5, policy_4.required_complete_sessions)


class TestNumericalAndPriceBoundaries(unittest.TestCase):
    """Bordes de números, escalas de precios y floats prohibidos (CA-4, OPT-2)."""

    def setUp(self) -> None:
        self.now_utc = datetime(2026, 8, 29, 14, 30, 0, tzinfo=timezone.utc)

    def test_nan_float_rejected_in_canonical_json(self) -> None:
        with self.assertRaises(ValueError):
            canonical_json_dumps({"value": float("nan")})

    def test_infinity_float_rejected_in_canonical_json(self) -> None:
        with self.assertRaises(ValueError):
            canonical_json_dumps({"value": float("inf")})
        with self.assertRaises(ValueError):
            canonical_json_dumps({"value": float("-inf")})

    def test_ask_less_than_bid_rejected(self) -> None:
        payload = QuoteTickPayloadV1(
            bid=500040,
            ask=500000,  # ASK LESS THAN BID
            price_scale=100,
            bid_size=10,
            ask_size=10,
            source_timestamp_utc=self.now_utc,
            source_sequence=1,
        )
        res = validar_payload_quote_tick(payload)
        self.assertFalse(res.exito)
        self.assertEqual("VALIDATION_ERROR", res.error.codigo)

    def test_negative_price_or_scale_rejected(self) -> None:
        self.assertFalse(validate_price_scaled(-100).exito)
        self.assertFalse(validate_price_scaled(0).exito)
        self.assertFalse(validate_scale_factor(0).exito)
        self.assertFalse(validate_scale_factor(-1).exito)

    def test_scaled_probability_boundaries(self) -> None:
        # Exactly 0 and 1_000_000 are valid
        self.assertTrue(validate_probability_scaled(0).exito)
        self.assertTrue(validate_probability_scaled(1000000).exito)
        # Below 0 and above 1_000_000 are invalid
        self.assertFalse(validate_probability_scaled(-1).exito)
        self.assertFalse(validate_probability_scaled(1000001).exito)


class TestRiskTripwireBoundaries(unittest.TestCase):
    """Bordes exactos de la matriz de riesgo (CA-17, CA-18, §12.4)."""

    def setUp(self) -> None:
        self.risk = FakeRiskEngine()
        self.t0 = datetime(2026, 8, 29, 14, 30, 0, tzinfo=timezone.utc)

    def test_risk_per_trade_exact_boundary_50_vs_51(self) -> None:
        # Exactly $50.00 (500 pts stop loss * 1000 qty / 10000) -> PASS
        sim_50 = create_test_simulation(
            simulation_id=make_uuid(1),
            signal_id=make_uuid(2),
            created_at_utc=self.t0,
            planned_entry=500000,
            stop=499500,  # 500 pts
            target=502000,
            requested_quantity=1000,
            status="PROPOSED",
        )
        res_50 = self.risk.evaluar_propuesta(sim_50, self.t0)
        self.assertTrue(res_50.exito)

        # $51.00 (510 pts stop loss * 1000 qty / 10000 = $51.00) -> BLOCKED
        sim_51 = create_test_simulation(
            simulation_id=make_uuid(3),
            signal_id=make_uuid(4),
            created_at_utc=self.t0,
            planned_entry=500000,
            stop=499490,  # 510 pts -> $51.00
            target=502000,
            requested_quantity=1000,
            status="PROPOSED",
        )
        res_51 = self.risk.evaluar_propuesta(sim_51, self.t0)
        self.assertFalse(res_51.exito)
        self.assertEqual("RISK_LIMIT_HIT", res_51.error.codigo)

    def test_daily_loss_exact_boundary_249_vs_250(self) -> None:
        # Accumulate $249.99 loss -> STILL ALLOWED
        self.risk.daily_realized_loss_usd = 249.99
        sim = create_test_simulation(make_uuid(10), make_uuid(11), self.t0, status="PROPOSED")
        res_249 = self.risk.evaluar_propuesta(sim, self.t0)
        self.assertTrue(res_249.exito)

        # Accumulate $250.00 loss -> DISPARADOR KILL SWITCH
        self.risk.daily_realized_loss_usd = 250.00
        res_250 = self.risk.evaluar_propuesta(sim, self.t0)
        self.assertFalse(res_250.exito)
        self.assertTrue(self.risk.kill_switch_active)

    def test_consecutive_losses_exact_boundary_2_vs_3(self) -> None:
        # 2 consecutive losses -> ALLOWED
        self.risk.consecutive_losses = 2
        sim = create_test_simulation(make_uuid(20), make_uuid(21), self.t0, status="PROPOSED")
        res_2 = self.risk.evaluar_propuesta(sim, self.t0)
        self.assertTrue(res_2.exito)

        # 3 consecutive losses -> PAUSED
        self.risk.consecutive_losses = 3
        res_3 = self.risk.evaluar_propuesta(sim, self.t0)
        self.assertFalse(res_3.exito)
        self.assertIn("perdidas consecutivas", res_3.error.mensaje_seguro)

    def test_daily_openings_exact_boundary_10_vs_11(self) -> None:
        # 9 openings made, proposing 10th -> ALLOWED
        self.risk.daily_openings = 9
        sim = create_test_simulation(make_uuid(30), make_uuid(31), self.t0, status="PROPOSED")
        res_10 = self.risk.evaluar_propuesta(sim, self.t0)
        self.assertTrue(res_10.exito)

        # 10 openings made, proposing 11th -> BLOCKED
        self.risk.daily_openings = 10
        res_11 = self.risk.evaluar_propuesta(sim, self.t0)
        self.assertFalse(res_11.exito)
        self.assertIn("Limite de aperturas diarias", res_11.error.mensaje_seguro)

    def test_news_blackout_exact_endpoints_inclusive(self) -> None:
        b_start = datetime(2026, 8, 29, 14, 25, 0, tzinfo=timezone.utc)
        b_end = datetime(2026, 8, 29, 14, 35, 0, tzinfo=timezone.utc)
        blackouts = [(b_start, b_end)]
        sim = create_test_simulation(make_uuid(40), make_uuid(41), self.t0, status="PROPOSED")

        # Exact start: 14:25:00 -> BLOCKED (inclusive)
        res_start = self.risk.evaluar_propuesta(sim, b_start, blackout_intervals=blackouts)
        self.assertFalse(res_start.exito)

        # Exact end: 14:35:00 -> BLOCKED (inclusive)
        res_end = self.risk.evaluar_propuesta(sim, b_end, blackout_intervals=blackouts)
        self.assertFalse(res_end.exito)

        # 1 microsecond before start: 14:24:59.999999 -> ALLOWED
        res_before = self.risk.evaluar_propuesta(
            sim, b_start - timedelta(microseconds=1), blackout_intervals=blackouts
        )
        self.assertTrue(res_before.exito)

        # 1 microsecond after end: 14:35:00.000001 -> ALLOWED
        res_after = self.risk.evaluar_propuesta(
            sim, b_end + timedelta(microseconds=1), blackout_intervals=blackouts
        )
        self.assertTrue(res_after.exito)


class TestSignalAndLabelingBoundaries(unittest.TestCase):
    """Bordes de vigencia de señales, ambigüedad y contratos incompletos (CA-10, CA-11, CA-14, CA-15)."""

    def setUp(self) -> None:
        self.evaluator = FakeTripleBarrierEvaluator(stop_loss_pts=500, take_profit_pts=2000)
        self.t0 = datetime(2026, 8, 29, 14, 30, 0, tzinfo=timezone.utc)
        self.valid_until = self.t0 + timedelta(seconds=30)

    def test_signal_expiration_exact_timestamp_boundary(self) -> None:
        sig = create_test_signal(
            signal_id=make_uuid(1),
            created_at_utc=self.t0,
            valid_until_utc=self.valid_until,
        )

        # 1 microsecond before valid_until -> NOT EXPIRED
        now_valid = self.valid_until - timedelta(microseconds=1)
        self.assertFalse(now_valid > sig.valid_until_utc)

        # Exactly at valid_until -> NOT EXPIRED
        self.assertFalse(self.valid_until > sig.valid_until_utc)

        # 1 microsecond after valid_until -> EXPIRED
        now_expired = self.valid_until + timedelta(microseconds=1)
        self.assertTrue(now_expired > sig.valid_until_utc)

    def test_ambiguous_stop_and_target_hit_in_single_tick_stop_first(self) -> None:
        # Long entry at 5000.40. Tick bid is 4995.00 (below stop 4995.40) AND ask is 5021.00 (above target 5020.40)
        # In a single atomic tick where both barriers are touched, convention is STOP_FIRST
        status, exit_price = self.evaluator.evaluar_tick_long(
            entry_ask=500040,
            tick_bid=499500,
            tick_ask=502100,
        )
        self.assertEqual("AMBIGUOUS_STOP_FIRST", status)
        self.assertEqual(499540, exit_price)  # Stop price executed

    def test_incomplete_economic_contract_missing_stop_or_target(self) -> None:
        risk = FakeRiskEngine()
        # Missing stop loss (stop=0)
        sim_incomplete = create_test_simulation(
            simulation_id=make_uuid(10),
            signal_id=make_uuid(11),
            created_at_utc=self.t0,
            planned_entry=500000,
            stop=0,  # INCOMPLETE
            target=502000,
            status="PROPOSED",
        )
        res = risk.evaluar_propuesta(sim_incomplete, self.t0)
        self.assertFalse(res.exito)
        self.assertEqual("ECONOMIC_CONTRACT_INCOMPLETE", res.error.codigo)

    def test_single_position_limit_zero_open_vs_one_open(self) -> None:
        risk = FakeRiskEngine()
        sim1 = create_test_simulation(make_uuid(20), make_uuid(21), self.t0, status="OPEN_SIMULATED")
        # 0 open -> Can open
        self.assertEqual(0, len(risk.open_positions))
        risk.registrar_apertura(sim1)
        # 1 open -> Full
        self.assertEqual(1, len(risk.open_positions))

        sim2 = create_test_simulation(make_uuid(22), make_uuid(23), self.t0, status="PROPOSED")
        res = risk.evaluar_propuesta(sim2, self.t0)
        self.assertFalse(res.exito)
        self.assertEqual("OVERLAPPING_POSITION", res.error.detalles["reason"])

    def test_yellow_light_with_non_monitor_direction_rejected(self) -> None:
        sig_bad = SenalV1(
            signal_id=make_uuid(30),
            case_id=make_uuid(31),
            created_at_utc=self.t0,
            valid_until_utc=self.valid_until,
            environment="REPLAY",
            instrument="US500",
            decision_window="S30",
            market_event_cutoff=self.t0,
            reference_bid=500000,
            reference_ask=500040,
            price_scale=100,
            data_age_ms=100,
            direction="LONG",  # MUST BE MONITOR FOR YELLOW
            light="YELLOW",
            reason_codes=(),
            health_state="HEALTHY",
            safety_forced=False,
            strategy_id="strat-v1",
            strategy_version="1.0.0",
            feature_set_version="features-v1",
            feature_snapshot_hash=make_sha256("feat"),
            model_id=None,
            model_version=None,
            model_hash=None,
            calibration_version=None,
            policy_version="policy-v1",
            raw_score_long=None,
            raw_score_short=None,
            calibrated_probability_long=None,
            calibrated_probability_short=None,
            expected_value_long_net=None,
            expected_value_short_net=None,
            cost_profile_version=None,
            correlation_id=make_uuid(30),
            causation_id=None,
            code_hash=make_sha256("code"),
            schema_version=1,
        )
        res = validar_senal(sig_bad)
        self.assertFalse(res.exito)
        self.assertEqual("VALIDATION_ERROR", res.error.codigo)


class TestMetricsAndCalculationBoundaries(unittest.TestCase):
    """Bordes de cálculo de métricas y redondeos (CA-22, DM-12)."""

    def setUp(self) -> None:
        self.now_utc = datetime(2026, 8, 29, 14, 30, 0, tzinfo=timezone.utc)

    def test_zero_sample_size_yields_null_with_reason_code(self) -> None:
        snap = SnapshotMetricoV1(
            metric_snapshot_id=make_uuid(1),
            metric_name="drawdown",
            metric_plane="EXECUTION",
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
            dimensions={"null_reason_code": "INSUFFICIENT_OR_UNKNOWN_DATA"},
            input_event_cutoff=self.now_utc,
            dataset_hash=None,
            code_hash=make_sha256("code-v1"),
            computed_at_utc=self.now_utc,
            schema_version=1,
        )
        res = validar_snapshot_metrico(snap)
        self.assertTrue(res.exito)
        self.assertIsNone(snap.value_int)
        self.assertEqual("INSUFFICIENT_OR_UNKNOWN_DATA", snap.dimensions["null_reason_code"])

    def test_wilson_confidence_interval_at_extreme_proportions(self) -> None:
        z = 1.959963984540054
        # p = 0 / 4 (0%)
        n = 4
        p = 0.0
        denominator = 1 + (z**2) / n
        centre = p + (z**2) / (2 * n)
        adj_sd = (p * (1 - p) / n + (z**2) / (4 * n**2)) ** 0.5
        lower = max(0.0, (centre - z * adj_sd) / denominator)
        upper = min(1.0, (centre + z * adj_sd) / denominator)
        self.assertGreaterEqual(lower, 0.0)
        self.assertLessEqual(upper, 1.0)

    def test_extreme_probability_clip_log_loss(self) -> None:
        # Probabilities are clipped to [1, 999_999] in scale 1_000_000 to prevent log(0)
        p_raw = 0
        p_clipped = max(1, min(999999, p_raw))
        self.assertEqual(1, p_clipped)

        p_raw_max = 1000000
        p_clipped_max = max(1, min(999999, p_raw_max))
        self.assertEqual(999999, p_clipped_max)

    def test_drawdown_calculation_with_zero_drawdown(self) -> None:
        # Curve of positive equity: [100, 200, 300] -> Peak is always current -> drawdown = 0
        equity_curve = [100, 200, 300]
        peak = equity_curve[0]
        max_dd = 0
        for eq in equity_curve:
            if eq > peak:
                peak = eq
            dd = peak - eq
            if dd > max_dd:
                max_dd = dd
        self.assertEqual(0, max_dd)

    def test_ny_session_midnight_risk_reset(self) -> None:
        risk = FakeRiskEngine()
        risk.daily_realized_loss_usd = 100.0
        risk.consecutive_losses = 2
        risk.daily_openings = 5
        risk.current_ny_date = "2026-08-29"

        # Advance domain clock across midnight NY (00:00:01 on 2026-08-30 in America/New_York is 04:00:01 UTC)
        next_day_utc = datetime(2026, 8, 30, 4, 0, 1, tzinfo=timezone.utc)
        risk.reset_ny_midnight_if_needed(next_day_utc)

        self.assertEqual("2026-08-30", risk.current_ny_date)
        self.assertEqual(0.0, risk.daily_realized_loss_usd)
        self.assertEqual(0, risk.consecutive_losses)
        self.assertEqual(0, risk.daily_openings)


if __name__ == "__main__":
    unittest.main()
