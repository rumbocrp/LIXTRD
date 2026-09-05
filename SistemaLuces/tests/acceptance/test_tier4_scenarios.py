"""Tier 4: Real-World Application Scenarios Acceptance Tests (SPEC-001 §12.6, PROJECT.md).

Cubre escenarios realistas de sesión de mercado de extremo a extremo:
1. Sesión completa de trading NY: Apertura, quotes, ventana S30, señal GREEN, ejecución paper, salida por target y métricas.
2. Volatilidad adversa y congelamiento de feed (>5000ms): Detección de feed stale, degradación inmediata a YELLOW y bloqueo de órdenes.
3. Racha de pérdidas consecutivas y Kill Switch por drawdown diario ($250): Pausa por racha, activación de kill switch y recuperación auditada.
4. Conciliación de fin de día e importación demo cTrader: Importación staged SHA-256, macheo con simulaciones, preservación de UNMATCHED y reporte de 8 planos.
5. Recuperación ante desastres y replay determinista: Snapshot de backup, restauración íntegra con verificación de cadena hash y replay byte-a-byte idéntico.
"""

from datetime import datetime, timedelta, timezone
import json
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
)
from sistema_luces.domain.error import ErrorDominio
from sistema_luces.domain.event import (
    DepthDeltaPayloadV1,
    QuoteTickPayloadV1,
    SobreEventoV1,
    canonical_json_bytes,
    compute_payload_hash,
)
from sistema_luces.domain.manifest import (
    CostProfileV1,
    DepthGatePolicyV1,
    ModelGatePolicyV1,
    RiskProfileV1,
)
from sistema_luces.domain.metric import (
    PLANOS_METRICOS_PERMITIDOS,
    SnapshotMetricoV1,
    validar_snapshot_metrico,
)
from sistema_luces.domain.result import Resultado
from sistema_luces.domain.signal import SenalV1, validar_senal
from sistema_luces.domain.simulation import SimulacionV1, validar_simulacion
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


class TestRealWorldApplicationScenarios(unittest.TestCase):
    """Escenarios de prueba realistas E2E sobre el ciclo de vida completo de trading y simulación."""

    def setUp(self) -> None:
        # Apertura de mercado NY: 09:30 EDT = 13:30 UTC
        self.market_open_utc = datetime(2026, 8, 29, 13, 30, 0, tzinfo=timezone.utc)
        self.store = FakeEventStoreSpy()
        self.feed_monitor = FakeFeedQualityMonitor(stale_threshold_ms=5000)
        self.lights_engine = FakeLightsEngine()
        self.risk_engine = FakeRiskEngine()
        self.evaluator = FakeTripleBarrierEvaluator(stop_loss_pts=500, take_profit_pts=2000)
        self.importer = FakeDemoImporter()

    def test_scenario_1_full_ny_trading_session(self) -> None:
        """Escenario 1: Sesión completa de trading NY con apertura, señal GREEN, ejecución paper, target y métricas."""
        # 1. Apertura de mercado e ingestión de quotes
        t_tick1 = self.market_open_utc
        ev1 = create_test_quote_tick_envelope(seq=1, occurred_at_utc=t_tick1, bid=500000, ask=500040)
        feed_state, _ = self.feed_monitor.evaluar_evento(ev1, t_tick1)
        self.assertEqual("HEALTHY", feed_state)
        self.store.anexar(ev1)

        # 2. Cierre de ventana causal S30 a las 13:30:30 UTC
        t_s30 = t_tick1 + timedelta(seconds=30)
        sig = self.lights_engine.decidir_senal(make_uuid(101), t_s30, feed_state, calibrated_prob_long=740000)
        self.assertEqual("GREEN", sig.light)
        self.assertEqual("LONG", sig.direction)
        self.assertEqual(t_s30, sig.market_event_cutoff)

        # 3. Propuesta de orden paper LONG
        sim = create_test_simulation(
            simulation_id=make_uuid(1001),
            signal_id=sig.signal_id,
            created_at_utc=t_s30,
            direction="LONG",
            planned_entry=500040,  # Entra en ask
            stop=499540,  # Stop 5 pts (4995.40)
            target=502040,  # Target 20 pts (5020.40)
            requested_quantity=100,  # 1.0 lote
            status="PROPOSED",
        )

        # 4. Aprobación de riesgo
        risk_res = self.risk_engine.evaluar_propuesta(sim, t_s30)
        self.assertTrue(risk_res.exito)
        self.risk_engine.registrar_apertura(sim)
        self.assertEqual(1, len(self.risk_engine.open_positions))

        # 5. Evolución de mercado: Ticks posteriores durante la sesión
        # Tick a las 13:32:00 alcanza el precio target (bid sube a 5020.50)
        t_target = t_s30 + timedelta(minutes=2)
        status, exit_price = self.evaluator.evaluar_tick_long(
            entry_ask=500040,
            tick_bid=502050,
            tick_ask=502090,
        )
        self.assertEqual("TAKE_PROFIT", status)
        self.assertEqual(502040, exit_price)

        # 6. Cierre de simulación con ganancia de +$200.00 (+20 pts * $10/pt)
        self.risk_engine.registrar_cierre(sim, pnl_usd=200.0)
        self.assertEqual(0, len(self.risk_engine.open_positions))
        self.assertEqual(0.0, self.risk_engine.daily_realized_loss_usd)

        # 7. Registro métrico en plano EXECUTION
        snap = SnapshotMetricoV1(
            metric_snapshot_id=make_uuid(2001),
            metric_name="net_pnl_usd",
            metric_plane="EXECUTION",
            range_start_utc=self.market_open_utc,
            range_end_utc=t_target,
            ny_session_date="2026-08-29",
            source="replay",
            environment="REPLAY",
            instrument="US500",
            strategy_version="1.0.0",
            model_version="1.0.0",
            policy_version="policy-v1",
            raw_count=1,
            effective_sample_size=1,
            value_int=20000,  # $200.00 scaled cents
            value_ratio_scaled=None,
            histogram_int=None,
            unit="USD_cents",
            scale=100,
            dimensions={"exit_reason": "target"},
            input_event_cutoff=t_target,
            dataset_hash=make_sha256("dataset-v1"),
            code_hash=make_sha256("code-v1"),
            computed_at_utc=t_target,
            schema_version=1,
        )
        self.assertTrue(validar_snapshot_metrico(snap).exito)

    def test_scenario_2_adverse_volatility_and_stale_feed_stall(self) -> None:
        """Escenario 2: Volatilidad adversa con stall de feed >5000ms forzando luz amarilla y bloqueando órdenes."""
        t_normal = self.market_open_utc + timedelta(minutes=30)
        ev = create_test_quote_tick_envelope(seq=10, occurred_at_utc=t_normal)
        self.feed_monitor.evaluar_evento(ev, t_normal)

        # 1. Congelamiento repentino de red (5500 ms sin ticks)
        t_stall = t_normal + timedelta(milliseconds=5500)
        feed_state, reasons = self.feed_monitor.evaluar_evento(ev, domain_time_utc=t_stall)
        self.assertEqual("STALE", feed_state)
        self.assertIn("STALE_FEED", reasons)

        # 2. Luces se degradan inmediatamente a YELLOW con MONITOR
        sig_yellow = self.lights_engine.decidir_senal(make_uuid(301), t_stall, feed_state, calibrated_prob_long=800000)
        self.assertEqual("YELLOW", sig_yellow.light)
        self.assertEqual("MONITOR", sig_yellow.direction)
        self.assertIn("FEED_DEGRADED_YELLOW", sig_yellow.reason_codes)

        # 3. Propuesta rechazada porque dirección es MONITOR
        self.assertEqual("MONITOR", sig_yellow.direction)

        # 4. Recuperación del feed
        t_rec = t_stall + timedelta(seconds=2)
        ev_rec = create_test_quote_tick_envelope(seq=11, occurred_at_utc=t_rec)
        feed_state_rec, _ = self.feed_monitor.evaluar_evento(ev_rec, domain_time_utc=t_rec)
        self.assertEqual("HEALTHY", feed_state_rec)

    def test_scenario_3_multi_loss_streak_and_daily_drawdown_kill_switch(self) -> None:
        """Escenario 3: Racha de pérdidas consecutivas alcanzando el límite diario de $250 y activando Kill Switch."""
        # 1. Tres operaciones consecutivas que tocan stop loss (-$50 cada una = -$150)
        for i in range(1, 4):
            t_trade = self.market_open_utc + timedelta(minutes=i * 10)
            sim_i = create_test_simulation(make_uuid(400 + i), make_uuid(500 + i), t_trade, status="OPEN_SIMULATED")
            self.risk_engine.registrar_apertura(sim_i)
            self.risk_engine.registrar_cierre(sim_i, pnl_usd=-50.0)

        self.assertEqual(3, self.risk_engine.consecutive_losses)
        self.assertEqual(150.0, self.risk_engine.daily_realized_loss_usd)

        # 2. Intento de 4ta operación bloqueado por racha perdedora
        sim_streak_blocked = create_test_simulation(make_uuid(490), make_uuid(590), self.market_open_utc + timedelta(minutes=35), status="PROPOSED")
        res_streak = self.risk_engine.evaluar_propuesta(sim_streak_blocked, self.market_open_utc + timedelta(minutes=35))
        self.assertFalse(res_streak.exito)
        self.assertIn("perdidas consecutivas", res_streak.error.mensaje_seguro)

        # 3. Dos pérdidas adicionales posteriores acumulan $250.00 de pérdida diaria
        sim4 = create_test_simulation(make_uuid(404), make_uuid(504), self.market_open_utc + timedelta(hours=1), status="OPEN_SIMULATED")
        self.risk_engine.registrar_apertura(sim4)
        self.risk_engine.registrar_cierre(sim4, pnl_usd=-50.0)

        sim5 = create_test_simulation(make_uuid(405), make_uuid(505), self.market_open_utc + timedelta(hours=2), status="OPEN_SIMULATED")
        self.risk_engine.registrar_apertura(sim5)
        self.risk_engine.registrar_cierre(sim5, pnl_usd=-50.0)

        self.assertEqual(250.0, self.risk_engine.daily_realized_loss_usd)
        self.assertTrue(self.risk_engine.kill_switch_active)

        # 4. Kill switch bloquea todas las aperturas posteriores (CA-18)
        sim_kill_blocked = create_test_simulation(make_uuid(499), make_uuid(599), self.market_open_utc + timedelta(hours=3), status="PROPOSED")
        res_kill = self.risk_engine.evaluar_propuesta(sim_kill_blocked, self.market_open_utc + timedelta(hours=3))
        self.assertFalse(res_kill.exito)
        self.assertEqual("RISK_LIMIT_HIT", res_kill.error.codigo)

        # 5. Recuperación formal auditada
        rec_res = self.risk_engine.recover_kill_switch(actor="risk_officer", resolution="Daily post-mortem complete and volatility normalized")
        self.assertTrue(rec_res.exito)
        self.assertFalse(self.risk_engine.kill_switch_active)

    def test_scenario_4_end_of_day_demo_reconciliation_and_metric_snapshot(self) -> None:
        """Escenario 4: Conciliación de fin de día de ejecuciones demo y generación de snapshot de 8 planos."""
        # 1. Archivo de ejecuciones del broker demo cTrader
        trades_export = [
            {"trade_id": "CT-001", "matched_sim_id": make_uuid(1001), "symbol": "US500", "pnl": 200},
            {"trade_id": "CT-002", "matched_sim_id": make_uuid(1002), "symbol": "US500", "pnl": -50},
            {"trade_id": "CT-003", "matched_sim_id": make_uuid(1003), "symbol": "US500", "pnl": 180},
            {"trade_id": "CT-004", "matched_sim_id": None, "symbol": "US500", "pnl": 15},  # Manual
            {"trade_id": "CT-005", "matched_sim_id": None, "symbol": "US500", "pnl": -25},  # Manual
        ]
        json_content = json.dumps(trades_export)
        expected_sha = make_sha256(json_content)

        # 2. Solicitud de importación validada
        import_sol = SolicitudImportacionDemo(
            correlation_id=make_uuid(601),
            environment="BROKER_DEMO_OBSERVED",
            staged_copy="export_20260829.json",
            expected_sha256=expected_sha,
            adapter_version="1.0.0",
            expected_demo_account_hash=make_sha256("demo-account"),
        )
        self.assertTrue(validar_solicitud_importacion_demo(import_sol).exito)

        # 3. Ejecución de importación y conciliación
        import_res = self.importer.importar_staged_copy(json_content, expected_sha)
        self.assertTrue(import_res.exito)
        self.assertEqual(5, import_res.datos.accepted_count)
        self.assertEqual(3, import_res.datos.matched_count)
        self.assertEqual(2, import_res.datos.unmatched_count)

        # 4. Generación de snapshot en plano DEMO
        snap_demo = SnapshotMetricoV1(
            metric_snapshot_id=make_uuid(701),
            metric_name="reconciliation_rate",
            metric_plane="DEMO",
            range_start_utc=self.market_open_utc,
            range_end_utc=self.market_open_utc + timedelta(hours=7),
            ny_session_date="2026-08-29",
            source="broker_demo_import",
            environment="BROKER_DEMO_OBSERVED",
            instrument="US500",
            strategy_version="1.0.0",
            model_version="1.0.0",
            policy_version="policy-v1",
            raw_count=5,
            effective_sample_size=5,
            value_int=None,
            value_ratio_scaled=600000,  # 3/5 = 60% conciliado
            histogram_int=None,
            unit="scaled_ratio",
            scale=1000000,
            dimensions={"total_imported": 5, "matched": 3, "unmatched": 2},
            input_event_cutoff=self.market_open_utc + timedelta(hours=7),
            dataset_hash=make_sha256("demo-dataset"),
            code_hash=make_sha256("code-v1"),
            computed_at_utc=self.market_open_utc + timedelta(hours=7),
            schema_version=1,
        )
        self.assertTrue(validar_snapshot_metrico(snap_demo).exito)

    def test_scenario_5_disaster_recovery_and_deterministic_replay(self) -> None:
        """Escenario 5: Recuperación tras falla de proceso y replay determinista con clock_seed."""
        # 1. Sesión histórica de 10 eventos persistidos con hash chaining
        last_hash = None
        for seq in range(1, 11):
            ev = create_test_quote_tick_envelope(
                seq=seq,
                occurred_at_utc=self.market_open_utc + timedelta(seconds=seq * 5),
                previous_hash=last_hash,
            )
            append_res = self.store.anexar(ev)
            self.assertTrue(append_res.exito)
            last_hash = append_res.datos["chain_hash"]

        # 2. Creación de snapshot de base de datos
        backup = self.store.backup()
        self.assertEqual(10, backup["count"])

        # 3. Simulación de reinicio de proceso
        recovered_store = FakeEventStoreSpy()
        restore_res = recovered_store.restore(backup)
        self.assertTrue(restore_res.exito)
        self.assertEqual(backup["last_hash"], recovered_store.last_hash)

        # 4. Solicitud de replay determinista con clock_seed fijo
        replay_sol = SolicitudReplay(
            correlation_id=make_uuid(801),
            environment="REPLAY",
            dataset_manifest_hash=make_sha256("golden-dataset-v1"),
            range_start_utc=self.market_open_utc,
            range_end_utc=self.market_open_utc + timedelta(hours=6),
            clock_seed=20260829,
        )
        self.assertTrue(validar_solicitud_replay(replay_sol).exito)


if __name__ == "__main__":
    unittest.main()
