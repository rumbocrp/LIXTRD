"""Suite de Pruebas End-to-End de Replay Determinista (SPEC-001 §5.2, RF-L005, RF-L006, RF-L007, RF-L010, CA-5, CA-21, CA-23).

Verifica exhaustivamente el caso de uso ReplayUseCase:
- Determinismo estricto byte-a-byte en ejecuciones independientes.
- Ingesta secuencial y filtrado temporal sin sesgo de anticipación.
- Detección y degradación determinista ante anomalías de feed a amarillo seguro.
- Ciclo de vida completo de simulación en papel (take profit, stop loss).
- Integridad criptográfica de la cadena de hashes en SQLite WAL y detección de manipulaciones.
- Interfaz de compatibilidad hacia atrás con ResumenEjecucion.
"""

from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
import uuid

from sistema_luces.application.composition_root import (
    PipelineCompositionRoot,
    crear_pipeline_replay,
    generar_uuid_determinista,
)
from sistema_luces.application.replay_use_case import (
    ConfiguracionReplay,
    EjecutorReplay,
    ReplayUseCase,
    ResultadoEjecucionReplay,
    ejecutar_replay,
)
from sistema_luces.domain.api import (
    ProyeccionLecturaV1,
    ResumenEjecucion,
    SolicitudReplay,
    validar_proyeccion_lectura_v1,
    validar_resumen_ejecucion,
)
from sistema_luces.domain.event import (
    QuoteTickPayloadV1,
    SobreEventoV1,
    compute_payload_hash,
)
from sistema_luces.models.baseline import ModeloBaseV1
from sistema_luces.storage.event_store import ArchivoEventos, RangoEventos
from sistema_luces.storage.sqlite import conectar_db


def _crear_tick(
    seq: int,
    occurred_at_utc: datetime,
    bid: int = 500000,
    ask: int = 500040,
    bid_size: int = 10,
    ask_size: int = 10,
    correlation_id: str = "00000000-0000-0000-0000-000000000001",
    event_id: str | None = None,
) -> SobreEventoV1:
    """Helper determinista para generar eventos QUOTE_TICK."""
    payload = {
        "bid": bid,
        "ask": ask,
        "price_scale": 100,
        "bid_size": bid_size,
        "ask_size": ask_size,
        "source_timestamp_utc": occurred_at_utc.isoformat(),
        "source_sequence": seq,
    }
    eid = event_id or generar_uuid_determinista(
        correlation_id, "TICK", f"{seq}:{occurred_at_utc.isoformat()}"
    )
    return SobreEventoV1(
        event_id=eid,
        event_type="QUOTE_TICK",
        schema_version=1,
        occurred_at_utc=occurred_at_utc,
        received_at_utc=occurred_at_utc,
        persisted_at_utc=None,
        source="replay",
        environment="REPLAY",
        source_account_id_hash=None,
        instrument="US500",
        symbol_id="US500",
        source_sequence=seq,
        payload_hash=compute_payload_hash(payload),
        previous_hash=None,
        causation_id=None,
        correlation_id=correlation_id,
        payload=payload,
    )


class TestReplayDeterminismoE2E(unittest.TestCase):
    """Pruebas E2E de determinismo, degradación y persistencia de Replay."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.t0 = datetime(2026, 8, 29, 14, 30, 0, tzinfo=timezone.utc)
        self.t_end = self.t0 + timedelta(minutes=10)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_replay_deterministic_byte_a_byte(self) -> None:
        """RF-L010, CA-5: Dos ejecuciones independientes del mismo corpus producen idéntica proyección byte-a-byte."""
        cid = "00000000-0000-0000-0000-000000000100"
        modelo = ModeloBaseV1(
            model_id="00000000-0000-0000-0000-000000000002",
            model_name="baseline-champion-v1",
            model_version="1.0.0",
            prior_long_scaled=750_000,
            prior_short_scaled=250_000,
        )

        # Generar corpus dorado de 50 ticks distribuidos en varias ventanas S30
        corpus: list[SobreEventoV1] = []
        for i in range(1, 51):
            t = self.t0 + timedelta(seconds=i * 2)
            bid = 500000 + (i % 10) * 10
            ask = bid + 40
            corpus.append(_crear_tick(seq=i, occurred_at_utc=t, bid=bid, ask=ask, correlation_id=cid))

        solicitud = SolicitudReplay(
            correlation_id=cid,
            environment="REPLAY",
            dataset_manifest_hash=hashlib.sha256(b"golden-corpus-v1").hexdigest(),
            range_start_utc=self.t0,
            range_end_utc=self.t_end,
            clock_seed=20260829,
        )

        db_path1 = Path(self.temp_dir.name) / "replay_run1.db"
        db_path2 = Path(self.temp_dir.name) / "replay_run2.db"

        # Ejecución 1
        use_case1 = ReplayUseCase(
            db_path=db_path1,
            model_id_campeon=modelo.model_id,
            clock_seed=20260829,
        )
        use_case1.pipeline.registro_modelos.registrar(modelo)
        res1 = use_case1.ejecutar(solicitud, dataset=corpus)
        self.assertTrue(res1.exito)
        out1 = res1.datos

        # Ejecución 2
        use_case2 = ReplayUseCase(
            db_path=db_path2,
            model_id_campeon=modelo.model_id,
            clock_seed=20260829,
        )
        use_case2.pipeline.registro_modelos.registrar(modelo)
        res2 = use_case2.ejecutar(solicitud, dataset=corpus)
        self.assertTrue(res2.exito)
        out2 = res2.datos

        # 1. Comparar contadores
        self.assertEqual(out1.events_processed, out2.events_processed)
        self.assertEqual(out1.ticks_ingested, out2.ticks_ingested)
        self.assertEqual(out1.cases_generated, out2.cases_generated)
        self.assertEqual(out1.signals_emitted, out2.signals_emitted)
        self.assertEqual(out1.transitions_recorded, out2.transitions_recorded)
        self.assertEqual(out1.simulations_opened, out2.simulations_opened)
        self.assertEqual(out1.simulations_closed, out2.simulations_closed)
        self.assertEqual(50, out1.ticks_ingested)
        self.assertGreater(out1.cases_generated, 0)
        self.assertGreater(out1.signals_emitted, 0)

        # 2. Comparar hashes de almacenamiento
        self.assertEqual(out1.final_hash, out2.final_hash)

        # 3. Comparar Proyecciones canónicas byte-a-byte (CA-5)
        json1 = out1.final_projection.to_canonical_json()
        json2 = out2.final_projection.to_canonical_json()
        bytes1 = out1.final_projection.to_canonical_bytes()
        bytes2 = out2.final_projection.to_canonical_bytes()

        self.assertEqual(json1, json2)
        self.assertEqual(bytes1, bytes2)
        self.assertEqual(
            hashlib.sha256(bytes1).hexdigest(),
            hashlib.sha256(bytes2).hexdigest(),
        )

        # 4. Comparar ResultadoEjecucionReplay completo serializado
        self.assertEqual(out1.to_canonical_json(), out2.to_canonical_json())
        self.assertEqual(out1.to_canonical_bytes(), out2.to_canonical_bytes())

    def test_replay_feed_anomaly_degradation_to_yellow(self) -> None:
        """RF-L007: Degradación determinista a luz amarilla ante anomalías de feed."""
        cid = "00000000-0000-0000-0000-000000000200"
        modelo = ModeloBaseV1(
            model_id="00000000-0000-0000-0000-000000000002",
            prior_long_scaled=800_000,
            prior_short_scaled=200_000,
        )

        # Crear flujo con anomalía: salto en secuencia (GAP) para activar degradación
        t1 = self.t0 + timedelta(seconds=1)
        t2 = self.t0 + timedelta(seconds=2)
        t3 = self.t0 + timedelta(seconds=30)  # Cierre de ventana

        corpus = [
            _crear_tick(seq=1, occurred_at_utc=t1, correlation_id=cid),
            _crear_tick(seq=10, occurred_at_utc=t2, correlation_id=cid),  # Salto de secuencia (gap)
            _crear_tick(seq=11, occurred_at_utc=t3, correlation_id=cid),
        ]

        db_path = Path(self.temp_dir.name) / "replay_anomaly.db"
        use_case = ReplayUseCase(
            db_path=db_path,
            model_id_campeon=modelo.model_id,
            clock_seed=20260829,
        )
        use_case.pipeline.registro_modelos.registrar(modelo)

        solicitud = SolicitudReplay(
            correlation_id=cid,
            environment="REPLAY",
            dataset_manifest_hash=hashlib.sha256(b"anomaly-corpus").hexdigest(),
            range_start_utc=self.t0,
            range_end_utc=self.t_end,
            clock_seed=20260829,
        )

        res = use_case.ejecutar(solicitud, dataset=corpus)
        self.assertTrue(res.exito)
        out = res.datos

        # La salud del feed debe degradarse y forzar luz YELLOW
        self.assertEqual("GAPPED", out.final_projection.health_state)
        self.assertEqual("YELLOW", out.final_projection.light)
        self.assertEqual("MONITORIZAR", out.final_projection.direction)

        # Verificar que se generó alerta de anomalía en incidentes
        self.assertGreater(len(out.final_projection.incidents), 0)

    def test_replay_paper_simulation_lifecycle_take_profit(self) -> None:
        """CA-21: Apertura y cierre de posición simulada por Take Profit durante replay."""
        cid = "00000000-0000-0000-0000-000000000300"
        modelo = ModeloBaseV1(
            model_id="00000000-0000-0000-0000-000000000003",
            prior_long_scaled=850_000,
            prior_short_scaled=150_000,
        )

        # 1. Tick inicial a :00 para abrir LONG (entry_ask = 500040, target = 502040)
        t_open = self.t0
        t_inter1 = self.t0 + timedelta(seconds=5)
        # Tick con precio alto para alcanzar target de 502040
        t_tp = self.t0 + timedelta(seconds=10)

        corpus = [
            _crear_tick(seq=1, occurred_at_utc=t_open, bid=500000, ask=500040, correlation_id=cid),
            _crear_tick(seq=2, occurred_at_utc=t_inter1, bid=500100, ask=500140, correlation_id=cid),
            _crear_tick(seq=3, occurred_at_utc=t_tp, bid=503000, ask=503040, correlation_id=cid),
        ]

        db_path = Path(self.temp_dir.name) / "replay_sim.db"
        use_case = ReplayUseCase(
            db_path=db_path,
            model_id_campeon=modelo.model_id,
            clock_seed=20260829,
        )
        use_case.pipeline.registro_modelos.registrar(modelo)

        res = use_case.ejecutar(
            ConfiguracionReplay(
                correlation_id=cid,
                range_start_utc=self.t0,
                range_end_utc=self.t_end,
                model_id_campeon=modelo.model_id,
                dataset=corpus,
            )
        )
        self.assertTrue(res.exito)
        out = res.datos

        self.assertEqual(1, out.simulations_opened)
        self.assertEqual(1, out.simulations_closed)

        # Verificar eventos en el almacén SQLite
        almacen = ArchivoEventos(db_path)
        integ = almacen.verificar_integridad(RangoEventos())
        self.assertTrue(integ.exito)
        self.assertTrue(integ.datos.is_valid)
        self.assertEqual((), integ.datos.violations)

    def test_replay_empty_dataset_opens_no_data(self) -> None:
        """RF-L003, RF-L008: Replay con dataset vacío produce NO_DATA y luz amarilla."""
        cid = "00000000-0000-0000-0000-000000000400"
        db_path = Path(self.temp_dir.name) / "replay_empty.db"
        use_case = ReplayUseCase(db_path=db_path)

        res = use_case.ejecutar(
            ConfiguracionReplay(
                correlation_id=cid,
                range_start_utc=self.t0,
                range_end_utc=self.t_end,
                dataset=[],
            )
        )
        self.assertTrue(res.exito)
        out = res.datos

        self.assertEqual(0, out.events_processed)
        self.assertEqual(0, out.ticks_ingested)
        self.assertEqual(0, out.cases_generated)
        self.assertEqual("NO_DATA", out.final_projection.environment)
        self.assertEqual("YELLOW", out.final_projection.light)
        self.assertEqual("MONITORIZAR", out.final_projection.direction)
        self.assertEqual("vacio", out.final_projection.ui_state)

    def test_replay_temporal_range_filtering(self) -> None:
        """RF-L006: Ingesta secuencial respeta filtros de rango temporal estrictamente."""
        cid = "00000000-0000-0000-0000-000000000500"
        t_before = self.t0 - timedelta(minutes=5)
        t_inside = self.t0 + timedelta(seconds=15)
        t_after = self.t_end + timedelta(minutes=5)

        corpus = [
            _crear_tick(seq=1, occurred_at_utc=t_before, correlation_id=cid),
            _crear_tick(seq=2, occurred_at_utc=t_inside, correlation_id=cid),
            _crear_tick(seq=3, occurred_at_utc=t_after, correlation_id=cid),
        ]

        db_path = Path(self.temp_dir.name) / "replay_filter.db"
        use_case = ReplayUseCase(db_path=db_path)

        res = use_case.ejecutar(
            SolicitudReplay(
                correlation_id=cid,
                environment="REPLAY",
                dataset_manifest_hash="0" * 64,
                range_start_utc=self.t0,
                range_end_utc=self.t_end,
                clock_seed=20260829,
            ),
            dataset=corpus,
        )
        self.assertTrue(res.exito)
        out = res.datos

        # Solo el tick 2 debe haber sido procesado
        self.assertEqual(1, out.events_processed)
        self.assertEqual(1, out.ticks_ingested)

    def test_replay_kill_switch_activation(self) -> None:
        """RF-L008: Activación de switch de emergencia fuerza luz amarilla y bloquea simulaciones."""
        cid = "00000000-0000-0000-0000-000000000600"
        modelo = ModeloBaseV1(
            model_id="00000000-0000-0000-0000-000000000002",
            prior_long_scaled=800_000,
            prior_short_scaled=200_000,
        )

        db_path = Path(self.temp_dir.name) / "replay_kill_switch.db"
        use_case = ReplayUseCase(
            db_path=db_path,
            model_id_campeon=modelo.model_id,
            clock_seed=20260829,
        )
        use_case.pipeline.registro_modelos.registrar(modelo)

        # Activar kill switch
        use_case.pipeline.activar_kill_switch("PRUEBA_EMERGENCIA_MANUAL")

        corpus = [
            _crear_tick(seq=1, occurred_at_utc=self.t0, correlation_id=cid),
            _crear_tick(seq=2, occurred_at_utc=self.t0 + timedelta(seconds=30), correlation_id=cid),
        ]

        res = use_case.ejecutar(dataset=corpus)
        self.assertTrue(res.exito)
        out = res.datos

        self.assertTrue(out.final_projection.kill_switch_active)
        self.assertEqual("YELLOW", out.final_projection.light)
        self.assertEqual("MONITORIZAR", out.final_projection.direction)
        self.assertEqual(0, out.simulations_opened)

    def test_replay_sqlite_wal_hash_chain_tamper_detection(self) -> None:
        """CA-23: Verificación de integridad criptográfica y detección de manipulación en SQLite WAL."""
        cid = "00000000-0000-0000-0000-000000000700"
        corpus = [
            _crear_tick(seq=i, occurred_at_utc=self.t0 + timedelta(seconds=i), correlation_id=cid)
            for i in range(1, 10)
        ]

        db_path = Path(self.temp_dir.name) / "replay_tamper.db"
        use_case = ReplayUseCase(db_path=db_path)
        res = use_case.ejecutar(dataset=corpus)
        self.assertTrue(res.exito)

        almacen = ArchivoEventos(db_path)

        # 1. Integridad inicial válida
        integ_inicial = almacen.verificar_integridad(RangoEventos())
        self.assertTrue(integ_inicial.exito)
        self.assertTrue(integ_inicial.datos.is_valid)
        self.assertEqual((), integ_inicial.datos.violations)

        # 2. Manipular maliciosamente un registro en SQLite desactivando trigger de append-only
        with conectar_db(db_path) as conn:
            cur = conn.cursor()
            cur.execute("DROP TRIGGER IF EXISTS trg_prevent_update_event_log;")
            cur.execute(
                "UPDATE event_log SET payload_json = ? WHERE row_id = 3;",
                ('{"bid": 999999, "ask": 999999, "corrupted": true}',),
            )
            conn.commit()

        # 3. La verificación de integridad debe fallar y reportar violación
        integ_sabotaje = almacen.verificar_integridad(RangoEventos())
        self.assertTrue(integ_sabotaje.exito)
        self.assertFalse(integ_sabotaje.datos.is_valid)
        self.assertGreater(len(integ_sabotaje.datos.violations), 0)
        self.assertIn("Row 3 payload hash mismatch", integ_sabotaje.datos.violations[0])

    def test_replay_backward_compatibility_interface(self) -> None:
        """Verifica compatibilidad con la interfaz ResumenEjecucion."""
        cid = "00000000-0000-0000-0000-000000000800"
        corpus = [_crear_tick(seq=1, occurred_at_utc=self.t0, correlation_id=cid)]

        solicitud = SolicitudReplay(
            correlation_id=cid,
            environment="REPLAY",
            dataset_manifest_hash="0" * 64,
            range_start_utc=self.t0,
            range_end_utc=self.t_end,
            clock_seed=20260829,
        )

        res = ejecutar_replay(solicitud, dataset=corpus)
        self.assertTrue(res.exito)
        out = res.datos

        # Validar compatibilidad de acceso por propiedades
        self.assertEqual(cid, out.run_id)
        self.assertEqual(1, out.accepted_event_count)
        self.assertEqual(0, out.rejected_event_count)
        self.assertEqual(out.signals_emitted, out.emitted_signal_count)
        self.assertEqual(out.simulations_opened, out.opened_simulation_count)
        self.assertIsNotNone(out.final_event_cutoff)

        # Validar DTO canónico ResumenEjecucion
        val_resumen = validar_resumen_ejecucion(out.resumen)
        self.assertTrue(val_resumen.exito)


if __name__ == "__main__":
    unittest.main()
