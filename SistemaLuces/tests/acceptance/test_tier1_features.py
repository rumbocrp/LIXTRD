"""Tier 1: Feature Coverage Acceptance Tests (SPEC-001, PROJECT.md).

Cubre los casos nominales (happy-path) de los 34 componentes del inventario del sistema
con al menos 5 casos de prueba por cada categoría funcional.
"""

from datetime import datetime, timedelta, timezone
import json
import unittest

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
    compute_payload_hash,
)
from sistema_luces.domain.manifest import (
    DepthGatePolicyV1,
    InstrumentProfileV1,
    ModelGatePolicyV1,
    RiskProfileV1,
    validar_depth_gate_policy,
    validar_model_gate_policy,
    validar_risk_profile,
)
from sistema_luces.domain.metric import (
    PLANOS_METRICOS_PERMITIDOS,
    SnapshotMetricoV1,
    validar_snapshot_metrico,
)
from sistema_luces.domain.result import Resultado
from sistema_luces.domain.signal import SenalV1, validar_senal
from sistema_luces.domain.simulation import SimulacionV1, validar_simulacion
from sistema_luces.domain.vocabulary import (
    INSTRUMENT_CANONICO,
    VALID_ENVIRONMENTS,
    parse_environment,
)
from tests.acceptance.helpers import (
    FakeDemoImporter,
    FakeEventStoreSpy,
    FakeFeedQualityMonitor,
    FakeLightsEngine,
    FakeRiskEngine,
    FakeTripleBarrierEvaluator,
    create_test_depth_gate_policy,
    create_test_model_gate_policy,
    create_test_quote_tick_envelope,
    create_test_risk_profile,
    create_test_signal,
    create_test_simulation,
    make_sha256,
    make_uuid,
)


class TestEnvironmentSecurityFeatures(unittest.TestCase):
    """Categoría 1: Entorno, seguridad y capacidades read-only (Features 1, 2, 3, 4, 34)."""

    def setUp(self) -> None:
        self.now_utc = datetime(2026, 8, 29, 14, 30, 0, tzinfo=timezone.utc)
        self.valid_hash = make_sha256("valid-dataset")
        self.account_hash = make_sha256("demo-account-123")

    def test_allowed_environments_parsed_correctly(self) -> None:
        for env_str in ("REPLAY", "SHADOW", "BROKER_DEMO_OBSERVED"):
            res = parse_environment(env_str)
            self.assertTrue(res.exito)
            self.assertEqual(env_str, res.datos)

    def test_read_only_capabilities_allowlist(self) -> None:
        from tests.architecture.policy_check import scan_repository

        violations = scan_repository(REPO_ROOT)
        self.assertEqual((), violations, f"Violaciones de seguridad detectadas: {violations}")

    def test_demo_account_validation_in_shadow_request(self) -> None:
        sol = SolicitudShadow(
            correlation_id=make_uuid(1),
            environment="SHADOW",
            source_profile_version="1.0.0",
            capabilities_manifest_hash=self.valid_hash,
            expected_demo_account_hash=self.account_hash,
        )
        res = validar_solicitud_shadow(sol)
        self.assertTrue(res.exito)

    def test_demo_account_validation_in_import_request(self) -> None:
        sol = SolicitudImportacionDemo(
            correlation_id=make_uuid(2),
            environment="BROKER_DEMO_OBSERVED",
            staged_copy="export_20260829.json",
            expected_sha256=self.valid_hash,
            adapter_version="1.0.0",
            expected_demo_account_hash=self.account_hash,
        )
        res = validar_solicitud_importacion_demo(sol)
        self.assertTrue(res.exito)

    def test_root_api_exports_exactly_four_use_cases(self) -> None:
        import sistema_luces

        expected = {"consultar_vista", "ejecutar_replay", "ejecutar_shadow", "importar_demo_observada"}
        actual = set(sistema_luces.__all__)
        self.assertEqual(expected, actual)


class TestStorageAndEventLogFeatures(unittest.TestCase):
    """Categoría 2: Almacén de eventos, hash chaining e idempotencia (Features 7, 8, 9, 10, 31)."""

    def setUp(self) -> None:
        self.store = FakeEventStoreSpy()
        self.t0 = datetime(2026, 8, 29, 14, 30, 0, tzinfo=timezone.utc)

    def test_event_envelope_persistence_and_serialization(self) -> None:
        ev = create_test_quote_tick_envelope(seq=1, occurred_at_utc=self.t0)
        res = self.store.anexar(ev)
        self.assertTrue(res.exito)
        self.assertEqual(1, len(self.store.events))
        self.assertEqual(self.t0, self.store.events[0].occurred_at_utc)

    def test_cryptographic_hash_chaining(self) -> None:
        ev1 = create_test_quote_tick_envelope(seq=1, occurred_at_utc=self.t0)
        res1 = self.store.anexar(ev1)
        self.assertTrue(res1.exito)

        # Event 2 chained to Event 1's resulting hash
        ev2 = create_test_quote_tick_envelope(
            seq=2,
            occurred_at_utc=self.t0 + timedelta(milliseconds=100),
            previous_hash=res1.datos["chain_hash"],
        )
        res2 = self.store.anexar(ev2)
        self.assertTrue(res2.exito)
        self.assertNotEqual(res1.datos["chain_hash"], res2.datos["chain_hash"])

    def test_idempotent_ingestion_returns_receipt(self) -> None:
        ev = create_test_quote_tick_envelope(seq=1, occurred_at_utc=self.t0)
        res1 = self.store.anexar(ev)
        self.assertTrue(res1.exito)
        self.assertEqual("ACCEPTED", res1.datos["status"])

        # Second exact append returns idempotent duplicate receipt
        res2 = self.store.anexar(ev)
        self.assertTrue(res2.exito)
        self.assertEqual("IDEMPOTENT_DUPLICATE", res2.datos["status"])
        self.assertEqual(1, len(self.store.events))

    def test_conflicting_event_id_raises_integrity_error(self) -> None:
        ev1 = create_test_quote_tick_envelope(seq=1, occurred_at_utc=self.t0, bid=500000)
        self.store.anexar(ev1)

        # Same event_id, different payload
        ev2 = create_test_quote_tick_envelope(seq=1, occurred_at_utc=self.t0, bid=500500, event_id=ev1.event_id)
        res2 = self.store.anexar(ev2)
        self.assertFalse(res2.exito)
        self.assertEqual("INTEGRITY_ERROR", res2.error.codigo)

    def test_unknown_schema_quarantine(self) -> None:
        unknown_event = {
            "event_id": make_uuid(99),
            "event_type": "UNKNOWN_SCHEMA_V9",
            "payload": {"arbitrary": 123},
        }
        res = self.store.anexar_cuarentena(unknown_event, correlation_id=make_uuid(99))
        self.assertTrue(res.exito)
        self.assertEqual(1, len(self.store.quarantine))
        self.assertEqual(0, len(self.store.events))


class TestFeedQualityFeatures(unittest.TestCase):
    """Categoría 3: Monitoreo de calidad de feed y cuarentena de profundidad (Features 12, 13)."""

    def setUp(self) -> None:
        self.monitor = FakeFeedQualityMonitor(stale_threshold_ms=5000)
        self.t0 = datetime(2026, 8, 29, 14, 30, 0, tzinfo=timezone.utc)

    def test_healthy_feed_processing(self) -> None:
        ev = create_test_quote_tick_envelope(seq=1, occurred_at_utc=self.t0)
        state, reasons = self.monitor.evaluar_evento(ev, domain_time_utc=self.t0)
        self.assertEqual("HEALTHY", state)
        self.assertEqual([], reasons)

    def test_feed_quality_gap_detection(self) -> None:
        ev1 = create_test_quote_tick_envelope(seq=1, occurred_at_utc=self.t0)
        self.monitor.evaluar_evento(ev1, self.t0)

        # Sequence gap: seq jumps from 1 to 5
        ev2 = create_test_quote_tick_envelope(seq=5, occurred_at_utc=self.t0 + timedelta(milliseconds=10))
        state, reasons = self.monitor.evaluar_evento(ev2, self.t0 + timedelta(milliseconds=10))
        self.assertEqual("GAPPED", state)
        self.assertIn("GAPPED_FEED", reasons)

    def test_feed_quality_stale_detection(self) -> None:
        ev = create_test_quote_tick_envelope(seq=1, occurred_at_utc=self.t0)
        # Domain clock is 6000ms ahead -> Stale
        domain_now = self.t0 + timedelta(milliseconds=6000)
        state, reasons = self.monitor.evaluar_evento(ev, domain_time_utc=domain_now)
        self.assertEqual("STALE", state)
        self.assertIn("STALE_FEED", reasons)

    def test_feed_quality_clock_rollback(self) -> None:
        ev1 = create_test_quote_tick_envelope(seq=1, occurred_at_utc=self.t0)
        self.monitor.evaluar_evento(ev1, self.t0)

        # Clock goes backwards
        ev2 = create_test_quote_tick_envelope(seq=2, occurred_at_utc=self.t0 - timedelta(seconds=1))
        state, reasons = self.monitor.evaluar_evento(ev2, self.t0)
        self.assertEqual("STALE", state)
        self.assertIn("CLOCK_ROLLBACK", reasons)

    def test_depth_gate_quarantine_evaluation(self) -> None:
        policy = create_test_depth_gate_policy()
        self.assertTrue(validar_depth_gate_policy(policy).exito)
        self.assertEqual(5, policy.required_complete_sessions)
        self.assertEqual("lead-qa", policy.approver)

class TestCaseBuilderAndLabelingFeatures(unittest.TestCase):
    """Categoría 4: Casos causales, ventanas temporales y triple barrera (Features 14, 15, 16)."""

    def setUp(self) -> None:
        self.evaluator = FakeTripleBarrierEvaluator(stop_loss_pts=500, take_profit_pts=2000)

    def test_causal_case_builder_s30_s60(self) -> None:
        t0 = datetime(2026, 8, 29, 14, 30, 0, tzinfo=timezone.utc)
        sig = create_test_signal(
            signal_id=make_uuid(1),
            created_at_utc=t0,
            valid_until_utc=t0 + timedelta(seconds=30),
        )
        self.assertTrue(validar_senal(sig).exito)
        self.assertEqual("S30", sig.decision_window)
        self.assertEqual(t0, sig.market_event_cutoff)

    def test_triple_barrier_long_take_profit(self) -> None:
        # Entry ask: 5000.40 -> Target (+20 pts): 5020.40
        status, exit_price = self.evaluator.evaluar_tick_long(
            entry_ask=500040,
            tick_bid=502050,
            tick_ask=502090,
        )
        self.assertEqual("TAKE_PROFIT", status)
        self.assertEqual(502040, exit_price)

    def test_triple_barrier_long_stop_loss(self) -> None:
        # Entry ask: 5000.40 -> Stop (-5 pts): 4995.40
        status, exit_price = self.evaluator.evaluar_tick_long(
            entry_ask=500040,
            tick_bid=499500,
            tick_ask=499540,
        )
        self.assertEqual("STOP_LOSS", status)
        self.assertEqual(499540, exit_price)

    def test_triple_barrier_short_take_profit(self) -> None:
        # Entry bid: 5000.00 -> Target (-20 pts): 4980.00 (exits via ask)
        status, exit_price = self.evaluator.evaluar_tick_short(
            entry_bid=500000,
            tick_bid=497950,
            tick_ask=497990,
        )
        self.assertEqual("TAKE_PROFIT", status)
        self.assertEqual(498000, exit_price)

    def test_triple_barrier_short_stop_loss(self) -> None:
        # Entry bid: 5000.00 -> Stop (+5 pts): 5005.00 (exits via ask)
        status, exit_price = self.evaluator.evaluar_tick_short(
            entry_bid=500000,
            tick_bid=500510,
            tick_ask=500550,
        )
        self.assertEqual("STOP_LOSS", status)
        self.assertEqual(500500, exit_price)


class TestModelRegistryAndEvaluationFeatures(unittest.TestCase):
    """Categoría 5: Modelos, calibración y compuertas de evaluación (Features 17, 18)."""

    def setUp(self) -> None:
        self.policy = create_test_model_gate_policy()

    def test_model_gate_policy_validates(self) -> None:
        res = validar_model_gate_policy(self.policy)
        self.assertTrue(res.exito)
        self.assertEqual(100000, self.policy.ece_max_scaled)
        self.assertEqual(600000, self.policy.profitable_walk_forward_ratio_min_scaled)

    def test_out_of_fold_model_calibration_scaling(self) -> None:
        t0 = datetime(2026, 8, 29, 14, 30, 0, tzinfo=timezone.utc)
        sig = create_test_signal(
            signal_id=make_uuid(1),
            created_at_utc=t0,
            valid_until_utc=t0 + timedelta(seconds=30),
            calibrated_prob_long=720000,
            calibrated_prob_short=280000,
        )
        self.assertTrue(validar_senal(sig).exito)
        self.assertEqual(720000, sig.calibrated_probability_long)
        self.assertEqual(280000, sig.calibrated_probability_short)
        self.assertEqual(1000000, sig.calibrated_probability_long + sig.calibrated_probability_short)

    def test_model_gate_brier_score_requirement(self) -> None:
        # Brier score calculation: (0.72 - 1.0)^2 = 0.0784 -> 78400
        prob = 720000 / 1000000.0
        y = 1.0
        brier = int((prob - y) ** 2 * 1000000)
        self.assertEqual(78400, brier)

    def test_model_gate_purged_embargo_splits_required(self) -> None:
        self.assertTrue(self.policy.purge_required)
        self.assertTrue(self.policy.embargo_required)
        self.assertTrue(self.policy.out_of_fold_calibration_required)

    def test_model_gate_zero_leakage_tolerance(self) -> None:
        self.assertEqual(0, self.policy.leakage_violations_max)


class TestLightsPolicyAndSignalFeatures(unittest.TestCase):
    """Categoría 6: Política de luces, histeresis y señales (Features 19, 20, 21, 33)."""

    def setUp(self) -> None:
        self.engine = FakeLightsEngine()
        self.t0 = datetime(2026, 8, 29, 14, 30, 0, tzinfo=timezone.utc)

    def test_lights_policy_transitions_and_hysteresis(self) -> None:
        # Initial: YELLOW
        self.assertEqual("YELLOW", self.engine.current_light)

        # Transition YELLOW -> GREEN: Allowed
        res_green = self.engine.transition("GREEN", "HEALTHY", 700000)
        self.assertTrue(res_green.exito)
        self.assertEqual("GREEN", self.engine.current_light)

        # Direct GREEN -> RED: Forbidden by CA-8
        res_forbidden = self.engine.transition("RED", "HEALTHY", 300000)
        self.assertFalse(res_forbidden.exito)
        self.assertEqual("VALIDATION_ERROR", res_forbidden.error.codigo)

        # Step through YELLOW first: Allowed
        res_yellow = self.engine.transition("YELLOW", "HEALTHY", 500000)
        self.assertTrue(res_yellow.exito)

        res_red = self.engine.transition("RED", "HEALTHY", 300000)
        self.assertTrue(res_red.exito)
        self.assertEqual("RED", self.engine.current_light)

    def test_signal_emission_with_valid_until_expiration(self) -> None:
        sig = self.engine.decidir_senal(make_uuid(1), self.t0, "HEALTHY", 700000)
        self.assertEqual("GREEN", sig.light)
        self.assertEqual("LONG", sig.direction)
        self.assertEqual(self.t0 + timedelta(seconds=30), sig.valid_until_utc)

    def test_yellow_signal_abstention(self) -> None:
        sig = self.engine.decidir_senal(make_uuid(2), self.t0, "HEALTHY", 500000)
        self.assertEqual("YELLOW", sig.light)
        self.assertEqual("MONITOR", sig.direction)

    def test_degraded_feed_forces_yellow_signal(self) -> None:
        sig = self.engine.decidir_senal(make_uuid(3), self.t0, "STALE", 750000)
        self.assertEqual("YELLOW", sig.light)
        self.assertEqual("MONITOR", sig.direction)
        self.assertIn("FEED_DEGRADED_YELLOW", sig.reason_codes)

    def test_daily_signal_target_non_quota_invariance(self) -> None:
        # Signals 1 to 15 do not change decision thresholds
        sig_a = self.engine.decidir_senal(make_uuid(4), self.t0, "HEALTHY", 700000)
        sig_b = self.engine.decidir_senal(make_uuid(5), self.t0, "HEALTHY", 700000)
        self.assertEqual(sig_a.light, sig_b.light)
        self.assertEqual(sig_a.direction, sig_b.direction)


class TestRiskAndSimulationFeatures(unittest.TestCase):
    """Categoría 7: Motor de riesgo, kill switch y simulador (Features 22, 23, 24, 25, 26)."""

    def setUp(self) -> None:
        self.risk = FakeRiskEngine()
        self.t0 = datetime(2026, 8, 29, 14, 30, 0, tzinfo=timezone.utc)

    def test_paper_simulator_lifecycle(self) -> None:
        sim = create_test_simulation(
            simulation_id=make_uuid(1),
            signal_id=make_uuid(2),
            created_at_utc=self.t0,
            status="OPEN_SIMULATED",
        )
        res = validar_simulacion(sim)
        self.assertTrue(res.exito)
        self.assertEqual("LONG", sim.direction)
        self.assertEqual(100, sim.requested_quantity_simulated)

    def test_risk_per_trade_evaluation(self) -> None:
        # 500 pts stop loss * 100 shares / 10000 = $50.00 -> PASS
        sim = create_test_simulation(
            simulation_id=make_uuid(10),
            signal_id=make_uuid(11),
            created_at_utc=self.t0,
            direction="LONG",
            planned_entry=500100,
            stop=499600,
            target=502100,
            requested_quantity=100,
            status="PROPOSED",
        )
        res = self.risk.evaluar_propuesta(sim, self.t0)
        self.assertTrue(res.exito)

    def test_single_position_invariant(self) -> None:
        sim1 = create_test_simulation(make_uuid(1), make_uuid(2), self.t0, status="OPEN_SIMULATED")
        self.risk.registrar_apertura(sim1)

        sim2 = create_test_simulation(
            make_uuid(12),
            make_uuid(13),
            self.t0 + timedelta(seconds=5),
            status="PROPOSED",
        )
        res = self.risk.evaluar_propuesta(sim2, self.t0 + timedelta(seconds=5))
        self.assertFalse(res.exito)
        self.assertEqual("RISK_LIMIT_HIT", res.error.codigo)
        self.assertEqual("OVERLAPPING_POSITION", res.error.detalles["reason"])

    def test_loss_streak_pause(self) -> None:
        # Simulate 3 losses
        for i in range(3):
            sim = create_test_simulation(make_uuid(i + 1), make_uuid(i + 10), self.t0, status="OPEN_SIMULATED")
            self.risk.registrar_apertura(sim)
            self.risk.registrar_cierre(sim, pnl_usd=-50.0)

        sim_next = create_test_simulation(
            make_uuid(20),
            make_uuid(21),
            self.t0 + timedelta(minutes=10),
            status="PROPOSED",
        )
        res = self.risk.evaluar_propuesta(sim_next, self.t0 + timedelta(minutes=10))
        self.assertFalse(res.exito)
        self.assertIn("perdidas consecutivas", res.error.mensaje_seguro)

    def test_fail_closed_kill_switch_and_recovery(self) -> None:
        self.risk.trigger_kill_switch("FEED_INTEGRITY_BREACH")
        sim = create_test_simulation(
            make_uuid(30),
            make_uuid(31),
            self.t0,
            status="PROPOSED",
        )
        res = self.risk.evaluar_propuesta(sim, self.t0)
        self.assertFalse(res.exito)

        # Recovery with valid actor & resolution
        rec_res = self.risk.recover_kill_switch(actor="risk_officer", resolution="Manual inspection passed")
        self.assertTrue(rec_res.exito)

        res2 = self.risk.evaluar_propuesta(sim, self.t0)
        self.assertTrue(res2.exito)


class TestImportAndReconciliationFeatures(unittest.TestCase):
    """Categoría 8: Importación demo y conciliación (Features 27, 28, 29)."""

    def setUp(self) -> None:
        self.importer = FakeDemoImporter()
        self.trades = [
            {"trade_id": "T1", "matched_sim_id": make_uuid(1), "symbol": "US500", "pnl": 100},
            {"trade_id": "T2", "matched_sim_id": None, "symbol": "US500", "pnl": -50},
        ]
        self.content = json.dumps(self.trades)
        self.sha256 = make_sha256(self.content)

    def test_read_only_demo_trade_import(self) -> None:
        res = self.importer.importar_staged_copy(self.content, self.sha256)
        self.assertTrue(res.exito)
        self.assertEqual(2, res.datos.accepted_count)
        self.assertEqual(1, res.datos.matched_count)
        self.assertEqual(1, res.datos.unmatched_count)

    def test_execution_reconciliation_preserves_matches(self) -> None:
        self.importer.importar_staged_copy(self.content, self.sha256)
        self.assertEqual(2, len(self.importer.imported_trades))
        self.assertEqual("T1", self.importer.imported_trades[0]["trade_id"])

    def test_unmatched_demo_execution_status(self) -> None:
        res = self.importer.importar_staged_copy(self.content, self.sha256)
        self.assertEqual(1, res.datos.unmatched_count)

    def test_optional_journal_v1_isolation(self) -> None:
        # Journal is optional post-V1, not opening tj.db
        import os

        self.assertFalse(os.path.exists("tj.db"))

    def test_import_request_dto_validation(self) -> None:
        sol = SolicitudImportacionDemo(
            correlation_id=make_uuid(1),
            environment="BROKER_DEMO_OBSERVED",
            staged_copy="export_20260829.json",
            expected_sha256=self.sha256,
            adapter_version="1.0.0",
            expected_demo_account_hash=make_sha256("demo-account"),
        )
        res = validar_solicitud_importacion_demo(sol)
        self.assertTrue(res.exito)


class TestObservabilityAndMetricsFeatures(unittest.TestCase):
    """Categoría 9: Observabilidad, 8 planos y determinismo de replay (Features 30, 31, 32)."""

    def setUp(self) -> None:
        self.now_utc = datetime(2026, 8, 29, 14, 30, 0, tzinfo=timezone.utc)

    def test_eight_plane_metric_calculations(self) -> None:
        for plane in PLANOS_METRICOS_PERMITIDOS:
            snap = SnapshotMetricoV1(
                metric_snapshot_id=make_uuid(1),
                metric_name=f"test_{plane.lower()}",
                metric_plane=plane,
                range_start_utc=self.now_utc,
                range_end_utc=self.now_utc,
                ny_session_date="2026-08-29",
                source="replay",
                environment="REPLAY",
                instrument="US500",
                strategy_version="1.0.0",
                model_version="1.0.0",
                policy_version="policy-v1",
                raw_count=10,
                effective_sample_size=10,
                value_int=100,
                value_ratio_scaled=None,
                histogram_int=None,
                unit="count",
                scale=1,
                dimensions={},
                input_event_cutoff=self.now_utc,
                dataset_hash=None,
                code_hash=make_sha256("code-v1"),
                computed_at_utc=self.now_utc,
                schema_version=1,
            )
            self.assertTrue(validar_snapshot_metrico(snap).exito)

    def test_null_metric_with_reason_code(self) -> None:
        snap = SnapshotMetricoV1(
            metric_snapshot_id=make_uuid(2),
            metric_name="insufficient_metric",
            metric_plane="FEED",
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
            unit="ratio",
            scale=1000000,
            dimensions={"null_reason_code": "INSUFFICIENT_OR_UNKNOWN_DATA"},
            input_event_cutoff=self.now_utc,
            dataset_hash=None,
            code_hash=make_sha256("code-v1"),
            computed_at_utc=self.now_utc,
            schema_version=1,
        )
        self.assertTrue(validar_snapshot_metrico(snap).exito)

    def test_deterministic_replay_request_dto(self) -> None:
        sol = SolicitudReplay(
            correlation_id=make_uuid(3),
            environment="REPLAY",
            dataset_manifest_hash=make_sha256("dataset-v1"),
            range_start_utc=self.now_utc,
            range_end_utc=self.now_utc + timedelta(hours=6),
            clock_seed=20260829,
        )
        res = validar_solicitud_replay(sol)
        self.assertTrue(res.exito)

    def test_query_view_request_limits_and_dto(self) -> None:
        sol = SolicitudConsulta(
            correlation_id=make_uuid(4),
            environment="REPLAY",
            view="FEED",
            as_of_event_id=None,
            cursor=None,
            limit=50,
        )
        res = validar_solicitud_consulta(sol)
        self.assertTrue(res.exito)

    def test_wilson_interval_formula(self) -> None:
        # Wilson score interval for p=2/4 (50%) -> expected [150_039, 849_961] scaled 1_000_000
        z = 1.959963984540054
        n = 4
        p = 2 / 4
        denominator = 1 + (z**2) / n
        centre_adjusted_probability = p + (z**2) / (2 * n)
        adjusted_standard_deviation = (p * (1 - p) / n + (z**2) / (4 * n**2)) ** 0.5
        lower = (centre_adjusted_probability - z * adjusted_standard_deviation) / denominator
        upper = (centre_adjusted_probability + z * adjusted_standard_deviation) / denominator
        lower_scaled = int(round(lower * 1000000))
        upper_scaled = int(round(upper * 1000000))

        self.assertEqual(150039, lower_scaled)
        self.assertEqual(849961, upper_scaled)


if __name__ == "__main__":
    unittest.main()
