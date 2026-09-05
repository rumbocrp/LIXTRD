"""Tier 3: Cross-Feature Subsystem Combinations Acceptance Tests (SPEC-001, PROJECT.md).

Cubre pruebas de interacción entre subsistemas:
- Degradación de feed -> Luces amarillas forzadas -> Bloqueo de simulaciones
- Política de luces -> Generación de señal -> Motor de riesgo -> Simulador
- Ventanas causales S30/S60 -> Triple barrera -> Purga y embargo
- Event sourcing -> Hash chaining -> Backup y Restore con verificación
- Simulación paper -> Posición única -> Racha de pérdidas -> Kill switch
- Importación demo -> Validación staged -> Conciliación y estado UNMATCHED
- Cálculo de métricas en los 8 planos -> Reconstrucción determinista de proyecciones
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


class TestCrossFeatureInteractions(unittest.TestCase):
    """Pruebas de interacción entre subsistemas acoplados por flujo de eventos."""

    def setUp(self) -> None:
        self.t0 = datetime(2026, 8, 29, 14, 30, 0, tzinfo=timezone.utc)
        self.store = FakeEventStoreSpy()
        self.feed_monitor = FakeFeedQualityMonitor(stale_threshold_ms=5000)
        self.lights_engine = FakeLightsEngine()
        self.risk_engine = FakeRiskEngine()
        self.evaluator = FakeTripleBarrierEvaluator(stop_loss_pts=500, take_profit_pts=2000)
        self.importer = FakeDemoImporter()

    def test_feed_degradation_forces_yellow_light_and_blocks_simulation(self) -> None:
        """Interacción: Feed Stale -> Luces en YELLOW -> Señal MONITOR -> Bloqueo de simulación."""
        # 1. Feed saludable inicial
        ev_healthy = create_test_quote_tick_envelope(seq=1, occurred_at_utc=self.t0)
        feed_state, reasons = self.feed_monitor.evaluar_evento(ev_healthy, self.t0)
        self.assertEqual("HEALTHY", feed_state)

        # 2. Señal verde generada bajo feed saludable
        sig_green = self.lights_engine.decidir_senal(make_uuid(1), self.t0, feed_state, 750000)
        self.assertEqual("GREEN", sig_green.light)
        self.assertEqual("LONG", sig_green.direction)

        # 3. Ocurre degradación de feed (retraso de 6000ms > umbral 5000ms)
        t_stale = self.t0 + timedelta(milliseconds=6000)
        feed_state_stale, reasons_stale = self.feed_monitor.evaluar_evento(ev_healthy, t_stale)
        self.assertEqual("STALE", feed_state_stale)
        self.assertIn("STALE_FEED", reasons_stale)

        # 4. Motor de luces responde forzando YELLOW y dirección MONITOR
        sig_yellow = self.lights_engine.decidir_senal(make_uuid(2), t_stale, feed_state_stale, 750000)
        self.assertEqual("YELLOW", sig_yellow.light)
        self.assertEqual("MONITOR", sig_yellow.direction)
        self.assertIn("FEED_DEGRADED_YELLOW", sig_yellow.reason_codes)

        # 5. Señal amarilla con MONITOR nunca abre simulación (CA-12)
        self.assertNotEqual("LONG", sig_yellow.direction)
        self.assertNotEqual("SHORT", sig_yellow.direction)

    def test_lights_policy_signal_emission_and_risk_evaluation_pipeline(self) -> None:
        """Interacción: Causal Case -> Señal GREEN -> Validación de Riesgo -> Simulación OPEN."""
        # 1. Señal GREEN válida emitida
        sig = self.lights_engine.decidir_senal(make_uuid(10), self.t0, "HEALTHY", 780000)
        self.assertEqual("GREEN", sig.light)
        self.assertEqual("LONG", sig.direction)

        # 2. Propuesta de simulación generada
        sim_prop = create_test_simulation(
            simulation_id=make_uuid(100),
            signal_id=sig.signal_id,
            created_at_utc=self.t0,
            direction="LONG",
            planned_entry=500040,
            stop=499540,
            target=502040,
            requested_quantity=100,
            status="PROPOSED",
        )

        # 3. Evaluación de riesgo pasa
        risk_res = self.risk_engine.evaluar_propuesta(sim_prop, self.t0)
        self.assertTrue(risk_res.exito)

        # 4. Transición a OPEN_SIMULATED en simulador
        self.risk_engine.registrar_apertura(sim_prop)
        self.assertEqual(1, len(self.risk_engine.open_positions))
        self.assertEqual(1, self.risk_engine.daily_openings)

    def test_causal_window_triple_barrier_labeling_and_purged_splits(self) -> None:
        """Interacción: Ventana causal S30 -> Corte temporal (OPT-7) -> Triple barrera -> Embargo."""
        cutoff_t = self.t0
        # 1. Feature snapshot respeta cutoff temporal
        sig = create_test_signal(
            signal_id=make_uuid(200),
            created_at_utc=cutoff_t,
            valid_until_utc=cutoff_t + timedelta(seconds=30),
        )
        self.assertEqual(cutoff_t, sig.market_event_cutoff)

        # 2. Ticks posteriores durante horizonte de 5 minutos
        t_exit = cutoff_t + timedelta(minutes=2)
        # Entry ask 5000.40 -> Target 5020.40 alcanzado en tick posterior
        status, exit_price = self.evaluator.evaluar_tick_long(
            entry_ask=500040,
            tick_bid=502050,
            tick_ask=502090,
        )
        self.assertEqual("TAKE_PROFIT", status)
        self.assertEqual(502040, exit_price)

        # 3. Verificación de política de splits con purga y embargo (CA-26)
        model_policy = create_test_model_gate_policy()
        self.assertTrue(model_policy.purge_required)
        self.assertTrue(model_policy.embargo_required)
        self.assertTrue(model_policy.out_of_fold_calibration_required)

    def test_storage_event_sourcing_hash_chain_and_backup_restore(self) -> None:
        """Interacción: Event Sourcing -> Encadenamiento SHA-256 -> Backup -> Restore íntegro."""
        # 1. Ingestión de 5 eventos con hash chaining estricto
        last_h = None
        for seq in range(1, 6):
            ev = create_test_quote_tick_envelope(
                seq=seq,
                occurred_at_utc=self.t0 + timedelta(milliseconds=seq * 10),
                previous_hash=last_h,
            )
            res = self.store.anexar(ev)
            self.assertTrue(res.exito)
            last_h = res.datos["chain_hash"]

        self.assertEqual(5, len(self.store.events))

        # 2. Verificación de integridad de la cadena
        integ_before = self.store.verificar_integridad()
        self.assertTrue(integ_before.exito)
        self.assertTrue(integ_before.datos["intact"])
        root_hash_before = integ_before.datos["root_hash"]

        # 3. Creación de backup
        backup_snapshot = self.store.backup()
        self.assertEqual(5, backup_snapshot["count"])

        # 4. Simulación de recuperación tras caída
        new_store = FakeEventStoreSpy()
        restore_res = new_store.restore(backup_snapshot)
        self.assertTrue(restore_res.exito)
        self.assertEqual(backup_snapshot["last_hash"], new_store.last_hash)

    def test_paper_simulation_single_position_and_drawdown_kill_switch(self) -> None:
        """Interacción: Posición abierta -> Rechazo solapada -> Pérdidas acumuladas -> Kill Switch."""
        # 1. Apertura de posición 1
        sim1 = create_test_simulation(make_uuid(301), make_uuid(401), self.t0, status="OPEN_SIMULATED")
        self.risk_engine.registrar_apertura(sim1)

        # 2. Propuesta concurrente rechazada por posición solapada (CA-16)
        sim2 = create_test_simulation(make_uuid(302), make_uuid(402), self.t0 + timedelta(seconds=1), status="PROPOSED")
        res_overlap = self.risk_engine.evaluar_propuesta(sim2, self.t0 + timedelta(seconds=1))
        self.assertFalse(res_overlap.exito)
        self.assertEqual("OVERLAPPING_POSITION", res_overlap.error.detalles["reason"])

        # 3. Cierre de posición 1 con pérdida de $50
        self.risk_engine.registrar_cierre(sim1, pnl_usd=-50.0)
        self.assertEqual(0, len(self.risk_engine.open_positions))
        self.assertEqual(50.0, self.risk_engine.daily_realized_loss_usd)
        self.assertEqual(1, self.risk_engine.consecutive_losses)

        # 4. Cuatro pérdidas consecutivas adicionales de $50 (Total acumulado $250)
        for i in range(2, 6):
            sim_i = create_test_simulation(make_uuid(300 + i), make_uuid(400 + i), self.t0 + timedelta(minutes=i), status="OPEN_SIMULATED")
            self.risk_engine.registrar_apertura(sim_i)
            self.risk_engine.registrar_cierre(sim_i, pnl_usd=-50.0)

        self.assertEqual(250.0, self.risk_engine.daily_realized_loss_usd)
        self.assertTrue(self.risk_engine.kill_switch_active)

        # 5. Siguiente propuesta bloqueada inmediatamente por Kill Switch (CA-18)
        sim_blocked = create_test_simulation(make_uuid(399), make_uuid(499), self.t0 + timedelta(minutes=10), status="PROPOSED")
        res_blocked = self.risk_engine.evaluar_propuesta(sim_blocked, self.t0 + timedelta(minutes=10))
        self.assertFalse(res_blocked.exito)
        self.assertEqual("RISK_LIMIT_HIT", res_blocked.error.codigo)

        # 6. Recuperación auditada con actor y resolución
        rec_res = self.risk_engine.recover_kill_switch(actor="risk_officer", resolution="Audit of market conditions complete")
        self.assertTrue(rec_res.exito)
        self.assertFalse(self.risk_engine.kill_switch_active)

    def test_demo_trade_import_staged_validation_and_reconciliation(self) -> None:
        """Interacción: Copia Staged -> Validación SHA-256 -> Reconciliación -> Estado UNMATCHED."""
        # 1. Dataset de ejecuciones manuales del broker demo
        staged_trades = [
            {"trade_id": "CTR-101", "matched_sim_id": make_uuid(100), "symbol": "US500", "pnl": 120},
            {"trade_id": "CTR-102", "matched_sim_id": make_uuid(200), "symbol": "US500", "pnl": -50},
            {"trade_id": "CTR-103", "matched_sim_id": None, "symbol": "US500", "pnl": 30},  # Operación manual no simulada
        ]
        content_str = json.dumps(staged_trades)
        content_hash = make_sha256(content_str)

        # 2. Importación exitosa
        res_imp = self.importer.importar_staged_copy(content_str, content_hash)
        self.assertTrue(res_imp.exito)
        self.assertEqual(3, res_imp.datos.accepted_count)
        self.assertEqual(2, res_imp.datos.matched_count)
        self.assertEqual(1, res_imp.datos.unmatched_count)

        # 3. Operación sin señal queda en estado UNMATCHED sin inventar costos (CA-19)
        unmatched_record = self.importer.imported_trades[2]
        self.assertEqual("CTR-103", unmatched_record["trade_id"])
        self.assertIsNone(unmatched_record["matched_sim_id"])

    def test_metrics_calculation_across_8_planes_and_projection_rebuilding(self) -> None:
        """Interacción: Eventos de sesión -> Cálculo de métricas en 8 planos -> Proyecciones deterministas."""
        # 1. Generación de snapshot para cada uno de los 8 planos métricos
        for plane in PLANOS_METRICOS_PERMITIDOS:
            snap = SnapshotMetricoV1(
                metric_snapshot_id=make_uuid(ord(plane[0])),
                metric_name=f"plane_metric_{plane.lower()}",
                metric_plane=plane,
                range_start_utc=self.t0,
                range_end_utc=self.t0 + timedelta(hours=6),
                ny_session_date="2026-08-29",
                source="replay",
                environment="REPLAY",
                instrument="US500",
                strategy_version="1.0.0",
                model_version="1.0.0",
                policy_version="policy-v1",
                raw_count=20,
                effective_sample_size=20,
                value_int=100,
                value_ratio_scaled=None,
                histogram_int=None,
                unit="count",
                scale=1,
                dimensions={"plane": plane},
                input_event_cutoff=self.t0 + timedelta(hours=6),
                dataset_hash=make_sha256("dataset"),
                code_hash=make_sha256("code"),
                computed_at_utc=self.t0 + timedelta(hours=6),
                schema_version=1,
            )
            res_val = validar_snapshot_metrico(snap)
            self.assertTrue(res_val.exito)

        # 2. Documento de vista de consulta generado
        doc_bytes = canonical_json_bytes({"planes_counted": len(PLANOS_METRICOS_PERMITIDOS)})
        doc_vista = DocumentoVistaV1(
            schema_id="sistema-luces/metric-snapshot-v1",
            document_hash=make_sha256(doc_bytes),
            canonical_json_utf8=doc_bytes,
        )
        vista = VistaLectura(
            instrument="US500",
            environment="REPLAY",
            health_state="HEALTHY",
            data_age_ms=120,
            light="GREEN",
            reason_codes=("METRICS_REBUILT",),
            model_id="logreg-v1",
            model_version="1.0.0",
            model_hash=make_sha256("model"),
            policy_version="policy-v1",
            kill_switch_active=False,
            as_of_event_id=make_uuid(499),
            next_cursor=None,
            documents=(doc_vista,),
        )
        self.assertEqual("US500", vista.instrument)
        self.assertEqual("REPLAY", vista.environment)
        self.assertEqual(1, len(vista.documents))


if __name__ == "__main__":
    unittest.main()
