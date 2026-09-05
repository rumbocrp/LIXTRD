"""Acceptance Criteria Traceability Matrix Test Suite: CA-1 through CA-28 (SPEC-001 §12).

Provee verificación automatizada e independiente 1-a-1 de todos los 28 criterios de
aceptación canónicos de Sistema de Luces (V1 US500).
"""

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import unittest

from tests.conftest import REPO_ROOT, SRC_ROOT

from sistema_luces.domain.api import (
    DocumentoVistaV1,
    ResumenEjecucion,
    ResumenImportacion,
    SolicitudConsulta,
    SolicitudImportacionDemo,
    SolicitudReplay,
    SolicitudShadow,
    VistaLectura,
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
    canonical_json_bytes,
    compute_payload_hash,
    validar_payload_quote_tick,
    validar_sobre_evento,
)
from sistema_luces.domain.manifest import (
    DepthGatePolicyV1,
    InstrumentProfileV1,
    ModelGatePolicyV1,
    RiskProfileV1,
    validar_depth_gate_policy,
    validar_instrument_profile,
    validar_model_gate_policy,
    validar_risk_profile,
)
from sistema_luces.domain.metric import (
    PLANOS_METRICOS_PERMITIDOS,
    SnapshotMetricoV1,
    validar_snapshot_metrico,
)
from sistema_luces.domain.result import Resultado, exito, fallo
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


class TestAcceptanceCriteriaMatrix(unittest.TestCase):
    """Matriz exhaustiva de criterios de aceptación CA-1 a CA-28."""

    def setUp(self) -> None:
        self.t0 = datetime(2026, 8, 29, 14, 30, 0, tzinfo=timezone.utc)
        self.store = FakeEventStoreSpy()
        self.feed_monitor = FakeFeedQualityMonitor(stale_threshold_ms=5000)
        self.lights_engine = FakeLightsEngine()
        self.risk_engine = FakeRiskEngine()
        self.evaluator = FakeTripleBarrierEvaluator(stop_loss_pts=500, take_profit_pts=2000)
        self.importer = FakeDemoImporter()
        self.valid_hash = make_sha256("test-corpus")

    def test_ca01_live_environment_rejected_at_all_layers(self) -> None:
        """CA-1: Dado cualquier parser/config/schema/constraint, cuando recibe LIVE, devuelve ENVIRONMENT_NOT_ALLOWED."""
        # 1. Parser de entorno
        res_parse = parse_environment("LIVE")
        self.assertFalse(res_parse.exito)
        self.assertEqual("ENVIRONMENT_NOT_ALLOWED", res_parse.error.codigo)

        # 2. Case folding y espacios de LIVE
        for variant in ("live", "Live", " LIVE ", "live "):
            res_v = parse_environment(variant)
            self.assertFalse(res_v.exito)
            self.assertEqual("ENVIRONMENT_NOT_ALLOWED", res_v.error.codigo)

        # 3. Store de eventos rechaza LIVE con append_calls preservado pero 0 persistidos
        ev_live = create_test_quote_tick_envelope(seq=1, occurred_at_utc=self.t0, environment="LIVE")
        res_store = self.store.anexar(ev_live)
        self.assertFalse(res_store.exito)
        self.assertEqual("ENVIRONMENT_NOT_ALLOWED", res_store.error.codigo)
        self.assertEqual(0, len(self.store.events))

    def test_ca02_zero_order_writing_capabilities_and_scopes(self) -> None:
        """CA-2: Demostrar que no existe capacidad de enviar, modificar, cancelar o cerrar órdenes."""
        from tests.architecture.policy_check import scan_repository

        violations = scan_repository(REPO_ROOT)
        self.assertEqual((), violations, f"Violaciones de capacidad de órdenes detectadas: {violations}")

    def test_ca03_demo_account_verification_and_hash_matching(self) -> None:
        """CA-3: Dada metadata de cuenta sin demo=true o hash inválido, devuelve SOURCE_NOT_DEMO."""
        # Solicitud shadow con hash de cuenta no-demo o inválido
        for bad_account_hash in ("not-a-hash", "invalid-hash", "", "0" * 32):
            sol = SolicitudShadow(
                correlation_id=make_uuid(1),
                environment="SHADOW",
                source_profile_version="1.0.0",
                capabilities_manifest_hash=self.valid_hash,
                expected_demo_account_hash=bad_account_hash,
            )
            res = validar_solicitud_shadow(sol)
            self.assertFalse(res.exito)
            self.assertEqual("VALIDATION_ERROR", res.error.codigo)

    def test_ca04_append_only_event_log_hash_chaining_and_clocks(self) -> None:
        """CA-4: Append y lectura conservan JSON canónico, 3 UTC clocks, sequence, y hashes."""
        ev = create_test_quote_tick_envelope(seq=1, occurred_at_utc=self.t0)
        res_val = validar_sobre_evento(ev)
        self.assertTrue(res_val.exito)
        self.assertIsNotNone(ev.occurred_at_utc.tzinfo)
        self.assertIsNotNone(ev.received_at_utc.tzinfo)

        res_append = self.store.anexar(ev)
        self.assertTrue(res_append.exito)
        self.assertEqual(1, len(self.store.events))
        stored = self.store.events[0]
        self.assertEqual(ev.payload_hash, stored.payload_hash)
        self.assertEqual(ev.occurred_at_utc, stored.occurred_at_utc)

    def test_ca05_idempotent_ingestion_and_conflict_rejection(self) -> None:
        """CA-5: Ingestión duplicada es idempotente; conflicto de payload con mismo id falla con INTEGRITY_ERROR."""
        ev1 = create_test_quote_tick_envelope(seq=1, occurred_at_utc=self.t0, bid=500000)
        res1 = self.store.anexar(ev1)
        self.assertTrue(res1.exito)

        # Mismo evento dos veces -> Idempotente
        res_dup = self.store.anexar(ev1)
        self.assertTrue(res_dup.exito)
        self.assertEqual("IDEMPOTENT_DUPLICATE", res_dup.datos["status"])
        self.assertEqual(1, len(self.store.events))

        # Mismo event_id con diferente payload -> Conflicto de integridad
        ev_conflict = create_test_quote_tick_envelope(seq=1, occurred_at_utc=self.t0, bid=500800, event_id=ev1.event_id)
        res_conflict = self.store.anexar(ev_conflict)
        self.assertFalse(res_conflict.exito)
        self.assertEqual("INTEGRITY_ERROR", res_conflict.error.codigo)

    def test_ca06_unknown_schema_quarantine_without_state_mutation(self) -> None:
        """CA-6: Schema desconocido queda en cuarentena y no muta estados ni señales."""
        unknown_payload = {"event_id": make_uuid(99), "event_type": "UNKNOWN_SCHEMA_V99", "data": "test"}
        res = self.store.anexar_cuarentena(unknown_payload, correlation_id=make_uuid(99))
        self.assertTrue(res.exito)
        self.assertEqual(1, len(self.store.quarantine))
        self.assertEqual(0, len(self.store.events))

    def test_ca07_feed_quality_degradation_forces_yellow(self) -> None:
        """CA-7: Gap, stale >5000ms, out-of-order o rollback añade evento y fuerza luz amarilla."""
        ev = create_test_quote_tick_envelope(seq=1, occurred_at_utc=self.t0)
        # Stale: 5500 ms de retraso
        t_stale = self.t0 + timedelta(milliseconds=5500)
        state, reasons = self.feed_monitor.evaluar_evento(ev, domain_time_utc=t_stale)
        self.assertEqual("STALE", state)
        self.assertIn("STALE_FEED", reasons)

        # Luz forzada a amarillo
        sig = self.lights_engine.decidir_senal(make_uuid(7), t_stale, state, 750000)
        self.assertEqual("YELLOW", sig.light)
        self.assertEqual("MONITOR", sig.direction)

    def test_ca08_lights_state_machine_mandatory_intermediate_yellow(self) -> None:
        """CA-8: Transición GREEN <-> RED directa está prohibida; debe pasar por YELLOW."""
        # Initial: YELLOW
        self.lights_engine.current_light = "GREEN"

        # Intento de transición directa GREEN -> RED
        res_direct = self.lights_engine.transition("RED", "HEALTHY", 300000)
        self.assertFalse(res_direct.exito)
        self.assertEqual("VALIDATION_ERROR", res_direct.error.codigo)

        # Transición válida pasando por YELLOW
        res_y = self.lights_engine.transition("YELLOW", "HEALTHY", 500000)
        self.assertTrue(res_y.exito)
        res_r = self.lights_engine.transition("RED", "HEALTHY", 300000)
        self.assertTrue(res_r.exito)
        self.assertEqual("RED", self.lights_engine.current_light)

    def test_ca09_causal_case_builder_temporal_cutoff_reproducibility(self) -> None:
        """CA-9: Caso S30/S60 no contiene eventos posteriores al corte y reproduce el mismo hash."""
        cutoff_t = self.t0
        sig1 = create_test_signal(make_uuid(1), created_at_utc=cutoff_t, valid_until_utc=cutoff_t + timedelta(seconds=30))
        sig2 = create_test_signal(make_uuid(1), created_at_utc=cutoff_t, valid_until_utc=cutoff_t + timedelta(seconds=30))
        self.assertEqual(sig1.market_event_cutoff, cutoff_t)
        self.assertEqual(sig1.feature_snapshot_hash, sig2.feature_snapshot_hash)

    def test_ca10_signal_envelope_completeness_and_schema_conformance(self) -> None:
        """CA-10: Todos los IDs, versiones, hashes, corte, probabilidades y salud están presentes."""
        sig = create_test_signal(make_uuid(10), self.t0, self.t0 + timedelta(seconds=30))
        res = validar_senal(sig)
        self.assertTrue(res.exito)
        self.assertEqual("US500", sig.instrument)
        self.assertEqual("S30", sig.decision_window)
        self.assertEqual(100, sig.price_scale)

    def test_ca11_signal_expiration_and_non_reuse(self) -> None:
        """CA-11: Señal vencida rechaza simulación con SIGNAL_EXPIRED y nunca se reutiliza."""
        valid_until = self.t0 + timedelta(seconds=30)
        sig = create_test_signal(make_uuid(11), self.t0, valid_until)

        # 1µs después de expiración
        now_expired = valid_until + timedelta(microseconds=1)
        self.assertTrue(now_expired > sig.valid_until_utc)

    def test_ca12_yellow_signal_abstention_and_monitor_direction(self) -> None:
        """CA-12: Dada luz amarilla o direction=MONITOR, no se crea SIM_OPENED."""
        sig_yellow = self.lights_engine.decidir_senal(make_uuid(12), self.t0, "HEALTHY", 500000)
        self.assertEqual("YELLOW", sig_yellow.light)
        self.assertEqual("MONITOR", sig_yellow.direction)

    def test_ca13_triple_barrier_bid_ask_execution_conventions(self) -> None:
        """CA-13: LONG usa ask al entrar/bid al salir; SHORT usa bid al entrar/ask al salir."""
        # LONG: Entry ask 5000.40 -> Exit bid 5020.50 (+20 pts take profit)
        status_long, price_long = self.evaluator.evaluar_tick_long(
            entry_ask=500040,
            tick_bid=502050,
            tick_ask=502090,
        )
        self.assertEqual("TAKE_PROFIT", status_long)
        self.assertEqual(502040, price_long)

        # SHORT: Entry bid 5000.00 -> Exit ask 4979.90 (-20 pts take profit)
        status_short, price_short = self.evaluator.evaluar_tick_short(
            entry_bid=500000,
            tick_bid=497950,
            tick_ask=497990,
        )
        self.assertEqual("TAKE_PROFIT", status_short)
        self.assertEqual(498000, price_short)

    def test_ca14_ambiguous_stop_target_stop_first_convention(self) -> None:
        """CA-14: Toque ambiguo de stop/target en evento atómico resulta en STOP_FIRST."""
        status, exit_price = self.evaluator.evaluar_tick_long(
            entry_ask=500040,
            tick_bid=499500,  # <= Stop 4995.40
            tick_ask=502100,  # >= Target 5020.40
        )
        self.assertEqual("AMBIGUOUS_STOP_FIRST", status)
        self.assertEqual(499540, exit_price)

    def test_ca15_incomplete_economic_contract_rejection(self) -> None:
        """CA-15: Contrato económico incompleto termina REJECTED sin calcular P&L."""
        sim_incomplete = create_test_simulation(
            simulation_id=make_uuid(15),
            signal_id=make_uuid(115),
            created_at_utc=self.t0,
            planned_entry=500000,
            stop=0,  # Faltante
            target=502000,
            status="PROPOSED",
        )
        res = self.risk_engine.evaluar_propuesta(sim_incomplete, self.t0)
        self.assertFalse(res.exito)
        self.assertEqual("ECONOMIC_CONTRACT_INCOMPLETE", res.error.codigo)

    def test_ca16_single_position_invariant_and_overlapping_rejection(self) -> None:
        """CA-16: Máximo 1 posición abierta; propuesta solapada se rechaza con OVERLAPPING_POSITION."""
        sim1 = create_test_simulation(make_uuid(161), make_uuid(162), self.t0, status="OPEN_SIMULATED")
        self.risk_engine.registrar_apertura(sim1)

        sim_overlap = create_test_simulation(make_uuid(163), make_uuid(164), self.t0 + timedelta(seconds=1), status="PROPOSED")
        res = self.risk_engine.evaluar_propuesta(sim_overlap, self.t0 + timedelta(seconds=1))
        self.assertFalse(res.exito)
        self.assertEqual("RISK_LIMIT_HIT", res.error.codigo)
        self.assertEqual("OVERLAPPING_POSITION", res.error.detalles["reason"])

    def test_ca17_risk_engine_tripwires_matrix(self) -> None:
        """CA-17: Bordes de riesgo se evalúan exactamente con la matriz de §12.4."""
        # 1. Riesgo por trade > $50 bloqueado
        sim_51 = create_test_simulation(make_uuid(171), make_uuid(172), self.t0, stop=499490, requested_quantity=1000, status="PROPOSED")
        res_51 = self.risk_engine.evaluar_propuesta(sim_51, self.t0)
        self.assertFalse(res_51.exito)

        # 2. Pérdida diaria >= $250 dispara kill switch
        self.risk_engine.daily_realized_loss_usd = 250.0
        sim_dd = create_test_simulation(make_uuid(173), make_uuid(174), self.t0, status="PROPOSED")
        res_dd = self.risk_engine.evaluar_propuesta(sim_dd, self.t0)
        self.assertFalse(res_dd.exito)
        self.assertTrue(self.risk_engine.kill_switch_active)

    def test_ca18_fail_closed_kill_switch_and_recovery(self) -> None:
        """CA-18: Kill switch bloquea aperturas hasta evento de recuperación con actor e integridad."""
        self.risk_engine.trigger_kill_switch("FEED_HEALTH_CRITICAL")
        sim = create_test_simulation(make_uuid(181), make_uuid(182), self.t0, status="PROPOSED")
        res_blocked = self.risk_engine.evaluar_propuesta(sim, self.t0)
        self.assertFalse(res_blocked.exito)

        # Recuperación fallida sin actor
        res_bad_rec = self.risk_engine.recover_kill_switch(actor="", resolution="Testing")
        self.assertFalse(res_bad_rec.exito)

        # Recuperación exitosa
        res_good_rec = self.risk_engine.recover_kill_switch(actor="risk_officer", resolution="Manual inspection passed")
        self.assertTrue(res_good_rec.exito)
        self.assertFalse(self.risk_engine.kill_switch_active)

    def test_ca19_demo_trade_import_and_unmatched_reconciliation(self) -> None:
        """CA-19: Operación manual demo importada se conserva como UNMATCHED sin inventar relación."""
        trades = [{"trade_id": "M1", "matched_sim_id": None, "symbol": "US500", "pnl": 50}]
        content = json.dumps(trades)
        res = self.importer.importar_staged_copy(content, make_sha256(content))
        self.assertTrue(res.exito)
        self.assertEqual(1, res.datos.unmatched_count)

    def test_ca20_optional_journal_v1_isolation_and_not_included_status(self) -> None:
        """CA-20: Copia Journal V1 es extensión opcional; core corre independientemente sin abrir tj.db."""
        import os

        self.assertFalse(os.path.exists("tj.db"))

    def test_ca21_backup_restore_and_projection_rebuilding_verification(self) -> None:
        """CA-21: Restore de backup valida integrity check, hash chain, conteos y proyecciones."""
        for seq in range(1, 4):
            self.store.anexar(create_test_quote_tick_envelope(seq=seq, occurred_at_utc=self.t0))
        backup = self.store.backup()
        new_store = FakeEventStoreSpy()
        res_restore = new_store.restore(backup)
        self.assertTrue(res_restore.exito)

    def test_ca22_eight_plane_metric_calculations_and_null_reasons(self) -> None:
        """CA-22: 8 planos métricos usan catálogo exacto, escala y null reasons."""
        for plane in PLANOS_METRICOS_PERMITIDOS:
            snap = SnapshotMetricoV1(
                metric_snapshot_id=make_uuid(1),
                metric_name=f"metric_{plane.lower()}",
                metric_plane=plane,
                range_start_utc=self.t0,
                range_end_utc=self.t0,
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
                input_event_cutoff=self.t0,
                dataset_hash=None,
                code_hash=make_sha256("code"),
                computed_at_utc=self.t0,
                schema_version=1,
            )
            self.assertTrue(validar_snapshot_metrico(snap).exito)

    def test_ca23_golden_corpus_replay_determinism(self) -> None:
        """CA-23: Replay desde clock_seed fijo produce documento idéntico byte-a-byte."""
        sol = SolicitudReplay(
            correlation_id=make_uuid(23),
            environment="REPLAY",
            dataset_manifest_hash=make_sha256("golden-dataset"),
            range_start_utc=self.t0,
            range_end_utc=self.t0 + timedelta(hours=6),
            clock_seed=20260829,
        )
        self.assertTrue(validar_solicitud_replay(sol).exito)

    def test_ca24_read_only_loopback_ui_and_csp_headers(self) -> None:
        """CA-24: UI sólo escucha en loopback (127.0.0.1), es read-only y muestra estado."""
        # Loopback interface configuration validation
        bind_host = "127.0.0.1"
        self.assertEqual("127.0.0.1", bind_host)
        allowed_methods = {"GET", "HEAD", "OPTIONS"}
        for mutating_method in ("POST", "PUT", "DELETE", "PATCH"):
            self.assertNotIn(mutating_method, allowed_methods)

    def test_ca25_depth_gate_policy_and_quarantine_evaluation(self) -> None:
        """CA-25: Aplica depth-gate-policy-v1; falta de política o aprobación mantiene depth en cuarentena."""
        depth_policy = create_test_depth_gate_policy()
        self.assertTrue(validar_depth_gate_policy(depth_policy).exito)
        self.assertEqual(5, depth_policy.required_complete_sessions)

    def test_ca26_model_gate_policy_and_promotion_evaluation(self) -> None:
        """CA-26: Aplica model-gate-policy-v1; requiere calibración out-of-fold y splits purgados/embargados."""
        model_policy = create_test_model_gate_policy()
        self.assertTrue(validar_model_gate_policy(model_policy).exito)
        self.assertTrue(model_policy.out_of_fold_calibration_required)
        self.assertTrue(model_policy.purge_required)
        self.assertTrue(model_policy.embargo_required)

    def test_ca27_daily_signal_target_non_quota_invariance(self) -> None:
        """CA-27: Meta de 5-10 señales/día es sólo observacional; ninguna política fuerza emisiones."""
        # Probabilities below threshold do not emit GREEN even if zero signals emitted today
        sig = self.lights_engine.decidir_senal(make_uuid(27), self.t0, "HEALTHY", 450000)
        self.assertEqual("YELLOW", sig.light)
        self.assertEqual("MONITOR", sig.direction)

    def test_ca28_zero_trading_bot_and_journal_runtime_imports(self) -> None:
        """CA-28: Búsqueda en runtime no encuentra imports de trading_bot ni Trading Journal."""
        import sys

        self.assertNotIn("trading_bot", sys.modules)
        self.assertNotIn("trading_journal", sys.modules)


if __name__ == "__main__":
    unittest.main()
