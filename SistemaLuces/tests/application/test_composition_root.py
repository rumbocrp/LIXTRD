"""Suite de Pruebas Exhaustiva del Composition Root Unificado y Puertos (RF-L010, RF-L011, RNF-L003).

Verifica la arquitectura hexagonal, el orquestador PipelineCompositionRoot, la propagación
de anomalías a amarillo seguro, la generación causal de casos S30/S60, la inferencia de modelos,
el ciclo de vida de simulación en papel (take profit y stop loss), la emisión de ProyeccionLecturaV1
y el determinismo estricto byte-a-byte.
"""

from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import uuid

from sistema_luces.application.composition_root import (
    PipelineCompositionRoot,
    ResumenPasoPipeline,
    crear_pipeline_replay,
    crear_pipeline_shadow,
    generar_uuid_determinista,
)
from sistema_luces.application.ports import (
    AlmacenPuerto,
    EvaluadorSaludFeedPuerto,
    FuentePuerto,
    GeneradorCasosPuerto,
    MotorPoliticaLucesPuerto,
    MotorSimulacionPuerto,
    ProyectorVistasPuerto,
    RegistroModelosPuerto,
    SesionFuentePuerto,
)
from sistema_luces.cases.builder import ConstructorCaso
from sistema_luces.domain.api import (
    ProyeccionLecturaV1,
    ResumenEjecucion,
    validar_proyeccion_lectura_v1,
)
from sistema_luces.domain.event import (
    SobreEventoV1,
    compute_payload_hash,
)
from sistema_luces.feed.quality import MonitorCalidadFeed
from sistema_luces.models.baseline import ModeloBaseV1
from sistema_luces.models.calibration import CalibradorLogistico
from sistema_luces.models.registry import RegistroModelos
from sistema_luces.observability.projections import ProyectorVistas
from sistema_luces.policy.lights import PoliticaLuces
from sistema_luces.simulation.paper import SimuladorPapel
from sistema_luces.sources.clock import RelojDominio
from sistema_luces.sources.replay import FuenteReplay, SesionReplay, SolicitudFuente
from sistema_luces.storage.event_store import ArchivoEventos


def _crear_tick_evento(
    seq: int,
    occurred_at_utc: datetime,
    bid: int = 500000,
    ask: int = 500040,
    environment: str = "REPLAY",
    correlation_id: str = "00000000-0000-0000-0000-000000000001",
    event_id: str | None = None,
) -> SobreEventoV1:
    """Helper para crear SobreEventoV1 de tipo QUOTE_TICK."""
    payload = {
        "bid": bid,
        "ask": ask,
        "price_scale": 100,
        "bid_size": 10,
        "ask_size": 10,
        "source_timestamp_utc": occurred_at_utc.isoformat(),
        "source_sequence": seq,
    }
    eid = event_id or generar_uuid_determinista(correlation_id, "TICK", f"{seq}:{occurred_at_utc.isoformat()}")
    return SobreEventoV1(
        event_id=eid,
        event_type="QUOTE_TICK",
        schema_version=1,
        occurred_at_utc=occurred_at_utc,
        received_at_utc=occurred_at_utc,
        persisted_at_utc=None,
        source="replay" if environment == "REPLAY" else "ctrader_demo",
        environment=environment,  # type: ignore[arg-type]
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


class TestPuertosHexagonales(unittest.TestCase):
    """Verifica que todos los puertos cumplen los protocolos tipados y @runtime_checkable."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_ports.db"

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_conformidad_protocolos(self) -> None:
        almacen = ArchivoEventos(self.db_path)
        evaluador = MonitorCalidadFeed()
        generador = ConstructorCaso()
        registro = RegistroModelos()
        politica = PoliticaLuces()
        simulador = SimuladorPapel()
        proyector = ProyectorVistas()
        fuente = FuenteReplay()

        self.assertTrue(isinstance(fuente, FuentePuerto))
        self.assertTrue(isinstance(almacen, AlmacenPuerto))
        self.assertTrue(isinstance(evaluador, EvaluadorSaludFeedPuerto))
        self.assertTrue(isinstance(generador, GeneradorCasosPuerto))
        self.assertTrue(isinstance(registro, RegistroModelosPuerto))
        self.assertTrue(isinstance(politica, MotorPoliticaLucesPuerto))
        self.assertTrue(isinstance(simulador, MotorSimulacionPuerto))
        self.assertTrue(isinstance(proyector, ProyectorVistasPuerto))


class TestPipelineCompositionRoot(unittest.TestCase):
    """Pruebas unitarias e integrales del orquestador PipelineCompositionRoot."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_pipeline.db"
        self.t0 = datetime(2026, 8, 29, 14, 30, 0, tzinfo=timezone.utc)
        self.pipeline = crear_pipeline_replay(
            db_path=self.db_path,
            clock_seed=20260829,
            policy_version="policy-us500-v1",
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_estado_inicial_sin_datos(self) -> None:
        """Verifica que el estado inicial abre en NO_DATA, luz YELLOW y dirección MONITORIZAR."""
        res_proy = self.pipeline.obtener_proyeccion_v1()
        self.assertTrue(res_proy.exito)
        proy = res_proy.datos

        self.assertEqual(proy.environment, "NO_DATA")
        self.assertEqual(proy.health_state, "NO_DATA")
        self.assertEqual(proy.light, "YELLOW")
        self.assertEqual(proy.direction, "MONITORIZAR")
        self.assertIn("NO_DATA_YELLOW", proy.reason_codes)
        self.assertIsNone(proy.as_of_event_id)

    def test_procesar_evento_unico_tick(self) -> None:
        """Verifica el procesamiento secuencial de un tick y actualización de estado."""
        ev = _crear_tick_evento(seq=1, occurred_at_utc=self.t0)
        res_paso = self.pipeline.procesar_evento(ev)
        self.assertTrue(res_paso.exito)
        paso = res_paso.datos

        self.assertEqual(paso.event_id, ev.event_id)
        self.assertEqual(paso.event_type, "QUOTE_TICK")
        self.assertEqual(paso.health_state, "HEALTHY")
        self.assertEqual(self.pipeline.health_state, "HEALTHY")
        self.assertEqual(self.pipeline._last_event_id, ev.event_id)

        # Proyección actualizada
        res_proy = self.pipeline.obtener_proyeccion_v1()
        self.assertTrue(res_proy.exito)
        proy = res_proy.datos
        self.assertEqual(proy.environment, "REPLAY")
        self.assertEqual(proy.health_state, "HEALTHY")
        self.assertEqual(proy.as_of_event_id, ev.event_id)

    def test_degradacion_salud_stale_fuerza_amarillo(self) -> None:
        """Inyección de tick con retraso >5000ms genera alerta STALE y fuerza luz YELLOW."""
        # 1. Primer tick a t0
        ev1 = _crear_tick_evento(seq=1, occurred_at_utc=self.t0)
        self.pipeline.procesar_evento(ev1)

        # 2. Tick con retraso de 10 segundos respecto al tiempo de reloj
        t_stale = self.t0 + timedelta(seconds=10)
        if self.pipeline.reloj:
            self.pipeline.reloj.avanzar_hasta(t_stale)

        # Evento que ocurrió en el pasado (hace 10s)
        ev2 = _crear_tick_evento(seq=2, occurred_at_utc=self.t0)
        res_paso = self.pipeline.procesar_evento(ev2)
        self.assertTrue(res_paso.exito)
        paso = res_paso.datos

        self.assertEqual(paso.health_state, "STALE")
        self.assertEqual(paso.light, "YELLOW")
        self.assertEqual(paso.direction, "MONITORIZAR")
        self.assertTrue(any(a.event_type == "STALE" for a in paso.alerts_generated))

        # Proyección debe reflejar amarillo seguro
        res_proy = self.pipeline.obtener_proyeccion_v1()
        self.assertTrue(res_proy.exito)
        self.assertEqual(res_proy.datos.light, "YELLOW")
        self.assertEqual(res_proy.datos.direction, "MONITORIZAR")

    def test_degradacion_salud_gap_secuencia(self) -> None:
        """Inyección de salto en source_sequence genera GAP_DETECTED y fuerza amarillo."""
        ev1 = _crear_tick_evento(seq=1, occurred_at_utc=self.t0)
        self.pipeline.procesar_evento(ev1)

        t1 = self.t0 + timedelta(milliseconds=100)
        ev2 = _crear_tick_evento(seq=5, occurred_at_utc=t1)  # Gap de seq 2..4
        res_paso = self.pipeline.procesar_evento(ev2)
        self.assertTrue(res_paso.exito)
        paso = res_paso.datos

        self.assertEqual(paso.health_state, "GAPPED")
        self.assertEqual(paso.light, "YELLOW")
        self.assertEqual(paso.direction, "MONITORIZAR")
        self.assertTrue(any(a.event_type == "GAP_DETECTED" for a in paso.alerts_generated))

    def test_degradacion_salud_clock_rollback(self) -> None:
        """Inyección de retroceso en reloj genera alerta CLOCK_ROLLBACK."""
        ev1 = _crear_tick_evento(seq=1, occurred_at_utc=self.t0)
        self.pipeline.procesar_evento(ev1)

        t_anterior = self.t0 - timedelta(seconds=1)
        ev2 = _crear_tick_evento(seq=2, occurred_at_utc=t_anterior)
        res_paso = self.pipeline.procesar_evento(ev2)
        self.assertTrue(res_paso.exito)
        paso = res_paso.datos

        self.assertTrue(any(a.event_type == "CLOCK_ROLLBACK" for a in paso.alerts_generated))

    def test_degradacion_salud_duplicate(self) -> None:
        """Inyección de evento exactamente duplicado genera alerta DUPLICATE."""
        ev1 = _crear_tick_evento(seq=1, occurred_at_utc=self.t0)
        self.pipeline.procesar_evento(ev1)

        # Reenviar el mismo evento idéntico
        res_paso = self.pipeline.procesar_evento(ev1)
        self.assertTrue(res_paso.exito)
        paso = res_paso.datos

        self.assertTrue(any(a.event_type == "DUPLICATE" for a in paso.alerts_generated))

    def test_cierre_causal_ventana_s30_e_inferencia_modelo(self) -> None:
        """Al alcanzar el límite de ventana S30 (:00 / :30), se construye CasoV1 e infiere modelo."""
        # 1. Registrar modelo campeón con sesgo largo
        modelo = ModeloBaseV1(
            model_id="00000000-0000-0000-0000-000000000002",
            model_name="baseline-champion-v1",
            model_version="1.0.0",
            prior_long_scaled=800_000,  # Alta probabilidad LONG > 650_000 -> GREEN
            prior_short_scaled=200_000,
        )
        self.pipeline.registro_modelos.registrar(modelo)
        self.pipeline.model_id_campeon = modelo.model_id

        # 2. Enviar ticks dentro de la ventana [14:30:00, 14:30:30]
        # Iniciar a 14:30:01 (para no cerrar en el segundo 00)
        t1 = self.t0 + timedelta(seconds=1)
        ev1 = _crear_tick_evento(seq=1, occurred_at_utc=t1, bid=500000, ask=500040)
        self.pipeline.procesar_evento(ev1)

        # Tick intermedio a los 15s
        t15 = self.t0 + timedelta(seconds=15)
        ev2 = _crear_tick_evento(seq=2, occurred_at_utc=t15, bid=500020, ask=500060)
        self.pipeline.procesar_evento(ev2)

        # Tick de cierre exacto a los 30s (:30)
        t30 = self.t0 + timedelta(seconds=30)
        ev3 = _crear_tick_evento(seq=3, occurred_at_utc=t30, bid=500050, ask=500090)
        res_paso = self.pipeline.procesar_evento(ev3)
        self.assertTrue(res_paso.exito)
        paso = res_paso.datos

        # 3. Verificar que se construyó el CasoV1 y se emitieron Señal y Transición
        self.assertIsNotNone(paso.case_generated)
        self.assertEqual(paso.case_generated.decision_window, "S30")
        self.assertTrue(paso.case_generated.eligible_for_signal)

        self.assertIsNotNone(paso.signal_emitted)
        self.assertEqual(paso.signal_emitted.light, "GREEN")
        self.assertEqual(paso.signal_emitted.direction, "LONG")

        self.assertIsNotNone(paso.transition_emitted)
        self.assertEqual(paso.transition_emitted.next_state, "GREEN")

        # 4. Verificar que se abrió una simulación paper en LONG
        self.assertIsNotNone(paso.simulation_opened)
        self.assertEqual(paso.simulation_opened.status, "OPEN_SIMULATED")
        self.assertEqual(paso.simulation_opened.direction, "LONG")

        # 5. Proyección V1 debe reflejar luz GREEN y dirección LARGO
        res_proy = self.pipeline.obtener_proyeccion_v1()
        self.assertTrue(res_proy.exito)
        proy = res_proy.datos
        self.assertEqual(proy.light, "GREEN")
        self.assertEqual(proy.direction, "LARGO")
        self.assertEqual(proy.model_id, modelo.model_id)

    def test_ciclo_vida_simulacion_paper_take_profit(self) -> None:
        """Verifica que una posición simulada abierta cierra por take profit al avanzar ticks."""
        # 1. Registrar modelo para abrir posición LONG
        modelo = ModeloBaseV1(
            model_id="00000000-0000-0000-0000-000000000003",
            prior_long_scaled=850_000,
            prior_short_scaled=150_000,
        )
        self.pipeline.registro_modelos.registrar(modelo)
        self.pipeline.model_id_campeon = modelo.model_id

        # 2. Generar cierre de ventana S30 para abrir LONG (a t0 = 14:30:00)
        ev_close = _crear_tick_evento(seq=1, occurred_at_utc=self.t0, bid=500000, ask=500040)
        res_paso1 = self.pipeline.procesar_evento(ev_close)
        self.assertTrue(res_paso1.exito)
        sim_abierta = res_paso1.datos.simulation_opened
        self.assertIsNotNone(sim_abierta)
        entry_ask = sim_abierta.fill_entry
        self.assertEqual(entry_ask, 500040)

        # 3. Avanzar tick por encima del take profit (+2000 puntos = 502040)
        t_tp = self.t0 + timedelta(seconds=5)
        ev_tp = _crear_tick_evento(seq=2, occurred_at_utc=t_tp, bid=502140, ask=502180)
        res_paso2 = self.pipeline.procesar_evento(ev_tp)
        self.assertTrue(res_paso2.exito)
        paso2 = res_paso2.datos

        self.assertEqual(len(paso2.simulations_closed), 1)
        sim_cerrada = paso2.simulations_closed[0]
        self.assertEqual(sim_cerrada.status, "CLOSED_SIMULATED")
        self.assertEqual(sim_cerrada.exit_reason, "target")
        self.assertGreater(sim_cerrada.net_pnl, 0)
        self.assertGreater(sim_cerrada.realized_r, 0)

    def test_ciclo_vida_simulacion_paper_stop_loss(self) -> None:
        """Verifica que una posición simulada abierta cierra por stop loss ante movimiento adverso."""
        # 1. Registrar modelo para abrir posición LONG
        modelo = ModeloBaseV1(
            model_id="00000000-0000-0000-0000-000000000033",
            prior_long_scaled=850_000,
            prior_short_scaled=150_000,
        )
        self.pipeline.registro_modelos.registrar(modelo)
        self.pipeline.model_id_campeon = modelo.model_id

        # 2. Generar cierre de ventana S30 para abrir LONG
        ev_close = _crear_tick_evento(seq=1, occurred_at_utc=self.t0, bid=500000, ask=500040)
        res_paso1 = self.pipeline.procesar_evento(ev_close)
        self.assertTrue(res_paso1.exito)

        # 3. Avanzar tick por debajo del stop loss (-500 puntos = 499540)
        t_sl = self.t0 + timedelta(seconds=5)
        ev_sl = _crear_tick_evento(seq=2, occurred_at_utc=t_sl, bid=499400, ask=499440)
        res_paso2 = self.pipeline.procesar_evento(ev_sl)
        self.assertTrue(res_paso2.exito)
        paso2 = res_paso2.datos

        self.assertEqual(len(paso2.simulations_closed), 1)
        sim_cerrada = paso2.simulations_closed[0]
        self.assertEqual(sim_cerrada.status, "CLOSED_SIMULATED")
        self.assertEqual(sim_cerrada.exit_reason, "stop")
        self.assertLess(sim_cerrada.net_pnl, 0)

    def test_kill_switch_fuerza_amarillo_y_bloquea_simulaciones(self) -> None:
        """La activación del kill switch impone amarillo inmediato e impide nuevas aperturas."""
        modelo = ModeloBaseV1(
            model_id="00000000-0000-0000-0000-000000000004",
            prior_long_scaled=900_000,
        )
        self.pipeline.registro_modelos.registrar(modelo)
        self.pipeline.model_id_campeon = modelo.model_id

        # Activar kill switch
        res_ks = self.pipeline.activar_kill_switch("Prueba de corte de emergencia")
        self.assertTrue(res_ks.exito)
        self.assertTrue(self.pipeline.kill_switch_active)
        self.assertEqual(self.pipeline.current_light, "YELLOW")

        # Intentar procesar ventana
        ev = _crear_tick_evento(seq=1, occurred_at_utc=self.t0)
        res_paso = self.pipeline.procesar_evento(ev)
        self.assertTrue(res_paso.exito)
        paso = res_paso.datos

        # No debe abrir simulación
        self.assertIsNone(paso.simulation_opened)
        self.assertEqual(paso.light, "YELLOW")
        self.assertEqual(paso.direction, "MONITORIZAR")

    def test_forzar_amarillo_manual(self) -> None:
        """Prueba la función explícita forzar_amarillo."""
        res_fa = self.pipeline.forzar_amarillo("DESCONEXION_MANUAL")
        self.assertTrue(res_fa.exito)
        trans = res_fa.datos
        self.assertEqual(trans.next_state, "YELLOW")
        self.assertTrue(trans.safety_forced)
        self.assertEqual(self.pipeline.current_light, "YELLOW")

    def test_obtener_vista_lectura(self) -> None:
        """Verifica la consulta de VistaLectura a través del proyector."""
        ev = _crear_tick_evento(seq=1, occurred_at_utc=self.t0)
        res_paso = self.pipeline.procesar_evento(ev)
        self.assertTrue(res_paso.exito)

        res_vista = self.pipeline.obtener_vista_lectura(view="FEED", limit=10)
        self.assertTrue(res_vista.exito)
        vista = res_vista.datos
        self.assertEqual(vista.instrument, "US500")
        self.assertEqual(vista.environment, "REPLAY")
        self.assertEqual(len(vista.documents), 1)

    def test_procesar_flujo_con_fuente_replay(self) -> None:
        """Verifica la ejecución de un lote de ticks usando procesar_flujo(sesion)."""
        sol = SolicitudFuente(
            correlation_id="00000000-0000-0000-0000-000000000009",
            environment="REPLAY",
            source_profile_version="v1",
            instrument="US500",
            range_start_utc=self.t0,
            range_end_utc=self.t0 + timedelta(minutes=5),
            clock_seed=20260829,
        )
        eventos = [
            _crear_tick_evento(
                seq=i,
                occurred_at_utc=self.t0 + timedelta(seconds=i * 5),
                correlation_id=sol.correlation_id,
            )
            for i in range(1, 10)
        ]
        fuente = FuenteReplay()
        res_ses = fuente.abrir(solicitud=sol, dataset=eventos)
        self.assertTrue(res_ses.exito)
        sesion = res_ses.datos

        res_flujo = self.pipeline.procesar_flujo(sesion)
        self.assertTrue(res_flujo.exito, msg=f"Error: {res_flujo.error if not res_flujo.exito else ''}")
        resumen = res_flujo.datos

        self.assertEqual(resumen.run_id, sol.correlation_id)
        self.assertEqual(resumen.environment, "REPLAY")
        self.assertEqual(resumen.accepted_event_count, 9)
        self.assertEqual(resumen.rejected_event_count, 0)

    def test_cero_bifurcacion_logica_replay_shadow(self) -> None:
        """Verifica que Replay y Shadow utilizan idéntica lógica de decisión (RF-L011)."""
        db1 = Path(self.temp_dir.name) / "replay.db"
        db2 = Path(self.temp_dir.name) / "shadow.db"
        p_replay = crear_pipeline_replay(db_path=db1, clock_seed=123)
        p_shadow = crear_pipeline_shadow(db_path=db2)

        self.assertIsInstance(p_replay, PipelineCompositionRoot)
        self.assertIsInstance(p_shadow, PipelineCompositionRoot)
        self.assertEqual(type(p_replay), type(p_shadow))

        # Enviar mismo tick a ambos con sus respectivos relojes sincronizados
        t_tick = p_shadow.reloj.ahora_utc() if p_shadow.reloj else self.t0
        if p_replay.reloj:
            p_replay.reloj.avanzar_hasta(t_tick)

        ev_r = _crear_tick_evento(seq=1, occurred_at_utc=t_tick, environment="REPLAY")
        ev_s = _crear_tick_evento(seq=1, occurred_at_utc=t_tick, environment="SHADOW")

        res_r = p_replay.procesar_evento(ev_r)
        res_s = p_shadow.procesar_evento(ev_s)

        self.assertTrue(res_r.exito)
        self.assertTrue(res_s.exito)
        self.assertEqual(res_r.datos.health_state, res_s.datos.health_state)
        self.assertEqual(res_r.datos.light, res_s.datos.light)
        self.assertEqual(res_r.datos.direction, res_s.datos.direction)

    def test_determinismo_estricto_byte_a_byte(self) -> None:
        """Dos ejecuciones independientes sobre el mismo dataset generan exactamente idénticos bytes (RF-L010)."""
        modelo = ModeloBaseV1(
            model_id="00000000-0000-0000-0000-000000000005",
            prior_long_scaled=700_000,
        )

        dataset = [
            _crear_tick_evento(
                seq=i,
                occurred_at_utc=self.t0 + timedelta(seconds=i * 10),
                bid=500000 + i * 10,
                ask=500040 + i * 10,
                correlation_id="00000000-0000-0000-0000-000000000077",
            )
            for i in range(1, 10)
        ]

        db1 = Path(self.temp_dir.name) / "run1.db"
        db2 = Path(self.temp_dir.name) / "run2.db"

        # Pasada 1
        p1 = crear_pipeline_replay(db_path=db1, clock_seed=20260829)
        p1.registro_modelos.registrar(modelo)
        p1.model_id_campeon = modelo.model_id
        for ev in dataset:
            p1.procesar_evento(ev)
        res_proy1 = p1.obtener_proyeccion_v1()
        self.assertTrue(res_proy1.exito)
        json1 = res_proy1.datos.to_canonical_json()
        bytes1 = res_proy1.datos.to_canonical_bytes()

        # Pasada 2
        p2 = crear_pipeline_replay(db_path=db2, clock_seed=20260829)
        p2.registro_modelos.registrar(modelo)
        p2.model_id_campeon = modelo.model_id
        for ev in dataset:
            p2.procesar_evento(ev)
        res_proy2 = p2.obtener_proyeccion_v1()
        self.assertTrue(res_proy2.exito)
        json2 = res_proy2.datos.to_canonical_json()
        bytes2 = res_proy2.datos.to_canonical_bytes()

        self.assertEqual(json1, json2)
        self.assertEqual(bytes1, bytes2)
        self.assertEqual(hashlib.sha256(bytes1).hexdigest(), hashlib.sha256(bytes2).hexdigest())


if __name__ == "__main__":
    unittest.main()
