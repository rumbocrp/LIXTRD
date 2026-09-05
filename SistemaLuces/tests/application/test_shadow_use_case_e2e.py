"""Suite de Pruebas End-to-End de Shadow con Fuente Fake Explícita (RF-L011, RNF-L001, RNF-L002, RNF-L011).

Verifica la orquestación integral de ShadowUseCase, el adaptador FuenteShadowFake,
la ausencia de bifurcación lógica con Replay, la propagación de anomalías a amarillo seguro,
el ciclo de vida de simulación en papel (take profit y stop loss), el kill switch
y la emisión de ProyeccionLecturaV1 canónica validada.
"""

from datetime import datetime, timedelta, timezone
import hashlib
from pathlib import Path
import tempfile
import unittest
import uuid

from sistema_luces.application.composition_root import (
    PipelineCompositionRoot,
    crear_pipeline_replay,
    crear_pipeline_shadow,
    generar_uuid_determinista,
)
from sistema_luces.application.ports import (
    FuentePuerto,
    SesionFuentePuerto,
)
from sistema_luces.application.shadow_use_case import (
    EjecutorShadow,
    FuenteShadowFake,
    ResumenEjecucionShadow,
    SesionShadowFake,
    ShadowUseCase,
    crear_caso_uso_shadow,
    ejecutar_shadow,
)
from sistema_luces.domain.api import (
    ProyeccionLecturaV1,
    ResumenEjecucion,
    SolicitudShadow,
    validar_proyeccion_lectura_v1,
    validar_resumen_ejecucion,
)
from sistema_luces.domain.event import (
    QuoteTickPayloadV1,
    SobreEventoV1,
    compute_payload_hash,
)
from sistema_luces.models.baseline import ModeloBaseV1
from sistema_luces.sources.clock import RelojDominio
from sistema_luces.sources.ctrader_demo import (
    AdaptadorCTraderDemoReadOnly,
    MetadatosCuentaCTrader,
    SolicitudConexionCTrader,
)
from sistema_luces.sources.replay import SolicitudFuente


def _crear_tick_shadow(
    seq: int,
    occurred_at_utc: datetime,
    bid: int = 500000,
    ask: int = 500040,
    environment: str = "SHADOW",
    correlation_id: str = "00000000-0000-0000-0000-000000000001",
) -> SobreEventoV1:
    """Helper para crear SobreEventoV1 de tipo QUOTE_TICK para pruebas de shadow."""
    payload = {
        "bid": bid,
        "ask": ask,
        "price_scale": 100,
        "bid_size": 10,
        "ask_size": 10,
        "source_timestamp_utc": occurred_at_utc.isoformat(),
        "source_sequence": seq,
    }
    eid = generar_uuid_determinista(correlation_id, "SHADOW_TICK", f"{seq}:{occurred_at_utc.isoformat()}")
    return SobreEventoV1(
        event_id=eid,
        event_type="QUOTE_TICK",
        schema_version=1,
        occurred_at_utc=occurred_at_utc,
        received_at_utc=occurred_at_utc,
        persisted_at_utc=None,
        source="ctrader_demo",
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


class TestShadowProtocolosYFactorias(unittest.TestCase):
    """Verifica conformidad de protocolos, inicialización y rechazo de entornos inválidos."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_shadow_protocols.db"
        self.t0 = datetime(2026, 8, 30, 14, 30, 0, tzinfo=timezone.utc)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_conformidad_protocolos_fuente_y_sesion(self) -> None:
        """Verifica que FuenteShadowFake y SesionShadowFake implementan los protocolos hexagonales."""
        fuente = FuenteShadowFake()
        self.assertTrue(isinstance(fuente, FuentePuerto))

        sol = SolicitudFuente(
            correlation_id="00000000-0000-0000-0000-000000000010",
            environment="SHADOW",
            source_profile_version="v1",
            instrument="US500",
            range_start_utc=self.t0,
            range_end_utc=self.t0 + timedelta(minutes=10),
            clock_seed=20260830,
        )
        res_ses = fuente.abrir(solicitud=sol)
        self.assertTrue(res_ses.exito)
        sesion = res_ses.datos
        self.assertTrue(isinstance(sesion, SesionFuentePuerto))
        self.assertIsInstance(sesion.reloj, RelojDominio)

    def test_rechazo_entornos_invalidos(self) -> None:
        """Verifica que FuenteShadowFake rechaza entornos no permitidos con error tipado."""
        fuente = FuenteShadowFake()

        # Entornos prohibidos
        for env_invalido in ["PROD", "REAL", "REPLAY"]:
            sol = SolicitudFuente(
                correlation_id="00000000-0000-0000-0000-000000000011",
                environment=env_invalido,  # type: ignore[arg-type]
                source_profile_version="v1",
                instrument="US500",
                range_start_utc=self.t0,
                range_end_utc=self.t0 + timedelta(minutes=10),
            )
            res = fuente.abrir(sol)
            self.assertFalse(res.exito)
            self.assertEqual(res.error.codigo, "ENVIRONMENT_NOT_ALLOWED")

    def test_estado_inicial_shadow_sin_datos(self) -> None:
        """Verifica que ShadowUseCase abre inicialmente en NO_DATA y luz YELLOW segura."""
        caso_uso = ShadowUseCase(db_path=self.db_path, tiempo_inicial_utc=self.t0)
        self.assertEqual(caso_uso.health_state, "NO_DATA")
        self.assertEqual(caso_uso.current_light, "YELLOW")
        self.assertFalse(caso_uso.kill_switch_active)

        res_proy = caso_uso.obtener_proyeccion_v1()
        self.assertTrue(res_proy.exito)
        proy = res_proy.datos
        self.assertEqual(proy.environment, "NO_DATA")
        self.assertEqual(proy.health_state, "NO_DATA")
        self.assertEqual(proy.light, "YELLOW")
        self.assertEqual(proy.direction, "MONITORIZAR")
        self.assertIn("NO_DATA_YELLOW", proy.reason_codes)


class TestShadowStreamingPasoAPaso(unittest.TestCase):
    """Verifica ingesta paso a paso, inyección dinámica de ticks y actualización reactiva."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_shadow_streaming.db"
        self.t0 = datetime(2026, 8, 30, 14, 30, 0, tzinfo=timezone.utc)
        self.caso_uso = ShadowUseCase(db_path=self.db_path, tiempo_inicial_utc=self.t0)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_procesar_tick_individual_actualiza_estado_y_vistas(self) -> None:
        """Verifica el procesamiento secuencial de ticks individuales y actualización de vistas."""
        t1 = self.t0 + timedelta(seconds=1)
        res_paso = self.caso_uso.procesar_tick(
            bid=500000,
            ask=500040,
            occurred_at_utc=t1,
            seq=1,
            correlation_id="00000000-0000-0000-0000-000000000020",
        )
        self.assertTrue(res_paso.exito)
        paso = res_paso.datos
        self.assertEqual(paso.event_type, "QUOTE_TICK")
        self.assertEqual(paso.health_state, "HEALTHY")
        self.assertEqual(self.caso_uso.health_state, "HEALTHY")

        # Proyección de lectura actualizada
        res_proy = self.caso_uso.obtener_proyeccion_v1()
        self.assertTrue(res_proy.exito)
        proy = res_proy.datos
        self.assertEqual(proy.environment, "SHADOW")
        self.assertEqual(proy.health_state, "HEALTHY")
        self.assertEqual(proy.as_of_event_id, paso.event_id)

        # Consulta de vista FEED
        res_vista = self.caso_uso.obtener_vista_lectura("FEED", limit=10)
        self.assertTrue(res_vista.exito)
        self.assertEqual(len(res_vista.datos.documents), 1)

    def test_streaming_con_sesion_shadow_fake_inyectada(self) -> None:
        """Verifica la inyección dinámica de eventos en SesionShadowFake y consumo con procesar_paso()."""
        res_ses = self.caso_uso.inicializar_sesion()
        self.assertTrue(res_ses.exito)
        sesion: SesionShadowFake = res_ses.datos  # type: ignore[assignment]

        # Inyectar 3 ticks en streaming
        for i in range(1, 4):
            t_ev = self.t0 + timedelta(seconds=i * 2)
            res_inj = sesion.inyectar_tick(
                bid=500000 + i * 10,
                ask=500040 + i * 10,
                occurred_at_utc=t_ev,
                seq=i,
            )
            self.assertTrue(res_inj.exito)

        # Consumir paso 1
        paso1 = self.caso_uso.procesar_paso()
        self.assertTrue(paso1.exito)
        self.assertIsNotNone(paso1.datos)
        self.assertEqual(paso1.datos.health_state, "HEALTHY")

        # Consumir paso 2
        paso2 = self.caso_uso.procesar_paso()
        self.assertTrue(paso2.exito)
        self.assertIsNotNone(paso2.datos)

        # Consumir paso 3
        paso3 = self.caso_uso.procesar_paso()
        self.assertTrue(paso3.exito)
        self.assertIsNotNone(paso3.datos)

        # Cola agotada
        paso_fin = self.caso_uso.procesar_paso()
        self.assertTrue(paso_fin.exito)
        self.assertIsNone(paso_fin.datos)


class TestShadowDegradacionSaludYAmarilloSeguro(unittest.TestCase):
    """Verifica detección de anomalías de feed y fail-closed a amarillo seguro."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_shadow_health.db"
        self.t0 = datetime(2026, 8, 30, 14, 30, 0, tzinfo=timezone.utc)
        self.caso_uso = ShadowUseCase(db_path=self.db_path, tiempo_inicial_utc=self.t0)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_tick_retrasado_stale_fuerza_amarillo_seguro(self) -> None:
        """Inyección de tick con antigüedad > 5000ms entra en estado STALE y fuerza luz YELLOW."""
        # 1. Primer tick a t0
        ev1 = _crear_tick_shadow(seq=1, occurred_at_utc=self.t0)
        self.caso_uso.procesar_evento(ev1)

        # 2. Reloj avanza 10s en el sistema
        if self.caso_uso.pipeline.reloj:
            self.caso_uso.pipeline.reloj.avanzar_hasta(self.t0 + timedelta(seconds=10))

        # 3. Tick retrasado a t0 (antigüedad de 10s > 5s)
        ev_stale = _crear_tick_shadow(seq=2, occurred_at_utc=self.t0)
        res_paso = self.caso_uso.procesar_evento(ev_stale)
        self.assertTrue(res_paso.exito)
        paso = res_paso.datos

        self.assertEqual(paso.health_state, "STALE")
        self.assertEqual(paso.light, "YELLOW")
        self.assertEqual(paso.direction, "MONITORIZAR")
        self.assertTrue(any(a.event_type == "STALE" for a in paso.alerts_generated))

        # Proyección refleja estado obsoleto y razón de retraso
        res_proy = self.caso_uso.obtener_proyeccion_v1()
        self.assertTrue(res_proy.exito)
        proy = res_proy.datos
        self.assertEqual(proy.light, "YELLOW")
        self.assertEqual(proy.direction, "MONITORIZAR")
        self.assertEqual(proy.ui_state, "obsoleto")

    def test_salto_de_secuencia_gapped_fuerza_amarillo(self) -> None:
        """Inyección de salto en secuencia genera alerta GAP_DETECTED y fuerza amarillo."""
        ev1 = _crear_tick_shadow(seq=1, occurred_at_utc=self.t0)
        self.caso_uso.procesar_evento(ev1)

        # Salto de seq 1 a seq 10
        t1 = self.t0 + timedelta(milliseconds=200)
        ev_gap = _crear_tick_shadow(seq=10, occurred_at_utc=t1)
        res_paso = self.caso_uso.procesar_evento(ev_gap)
        self.assertTrue(res_paso.exito)
        paso = res_paso.datos

        self.assertEqual(paso.health_state, "GAPPED")
        self.assertEqual(paso.light, "YELLOW")
        self.assertTrue(any(a.event_type == "GAP_DETECTED" for a in paso.alerts_generated))

    def test_retroceso_reloj_rollback_genera_alerta(self) -> None:
        """Inyección de tick con timestamp en el pasado genera alerta CLOCK_ROLLBACK."""
        ev1 = _crear_tick_shadow(seq=1, occurred_at_utc=self.t0)
        self.caso_uso.procesar_evento(ev1)

        t_past = self.t0 - timedelta(seconds=2)
        ev_rb = _crear_tick_shadow(seq=2, occurred_at_utc=t_past)
        res_paso = self.caso_uso.procesar_evento(ev_rb)
        self.assertTrue(res_paso.exito)
        paso = res_paso.datos

        self.assertTrue(any(a.event_type == "CLOCK_ROLLBACK" for a in paso.alerts_generated))

    def test_evento_duplicado_genera_alerta(self) -> None:
        """Inyección de evento exactamente duplicado genera alerta DUPLICATE."""
        ev1 = _crear_tick_shadow(seq=1, occurred_at_utc=self.t0)
        self.caso_uso.procesar_evento(ev1)

        res_dup = self.caso_uso.procesar_evento(ev1)
        self.assertTrue(res_dup.exito)
        paso = res_dup.datos

        self.assertTrue(any(a.event_type == "DUPLICATE" for a in paso.alerts_generated))


class TestShadowInferenciaYSimulacionPaper(unittest.TestCase):
    """Verifica inferencia con modelo campeón y ciclo de vida de simulación en papel."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_shadow_sim.db"
        self.t0 = datetime(2026, 8, 30, 14, 30, 0, tzinfo=timezone.utc)
        self.caso_uso = ShadowUseCase(db_path=self.db_path, tiempo_inicial_utc=self.t0)

        # Registrar modelo campeón con sesgo largo para activar GREEN
        self.modelo = ModeloBaseV1(
            model_id="00000000-0000-0000-0000-000000000099",
            model_name="baseline-champion-shadow-v1",
            model_version="1.0.0",
            prior_long_scaled=800_000,
            prior_short_scaled=200_000,
        )
        self.caso_uso.pipeline.registro_modelos.registrar(self.modelo)
        self.caso_uso.pipeline.model_id_campeon = self.modelo.model_id

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_cierre_s30_emite_senal_y_abre_simulacion_paper(self) -> None:
        """Al cerrar ventana S30, se genera CasoV1, se evalúa modelo y abre simulación paper."""
        # 1. Ticks dentro de la ventana S30
        t1 = self.t0 + timedelta(seconds=1)
        self.caso_uso.procesar_tick(bid=500000, ask=500040, occurred_at_utc=t1, seq=1)

        t15 = self.t0 + timedelta(seconds=15)
        self.caso_uso.procesar_tick(bid=500020, ask=500060, occurred_at_utc=t15, seq=2)

        # Cierre exacto a los 30s (:30)
        t30 = self.t0 + timedelta(seconds=30)
        res_paso = self.caso_uso.procesar_tick(bid=500050, ask=500090, occurred_at_utc=t30, seq=3)
        self.assertTrue(res_paso.exito)
        paso = res_paso.datos

        # Caso S30 generado
        self.assertIsNotNone(paso.case_generated)
        self.assertEqual(paso.case_generated.decision_window, "S30")

        # Señal GREEN / LONG
        self.assertIsNotNone(paso.signal_emitted)
        self.assertEqual(paso.signal_emitted.light, "GREEN")
        self.assertEqual(paso.signal_emitted.direction, "LONG")

        # Simulación paper abierta
        self.assertIsNotNone(paso.simulation_opened)
        sim = paso.simulation_opened
        self.assertEqual(sim.status, "OPEN_SIMULATED")
        self.assertEqual(sim.direction, "LONG")
        self.assertEqual(sim.fill_entry, 500090)

        # Proyección V1 refleja luz verde y simulación activa
        res_proy = self.caso_uso.obtener_proyeccion_v1()
        self.assertTrue(res_proy.exito)
        proy = res_proy.datos
        self.assertEqual(proy.light, "GREEN")
        self.assertEqual(proy.direction, "LARGO")
        self.assertEqual(len(proy.simulations), 1)

    def test_ciclo_completo_take_profit_en_shadow(self) -> None:
        """Verifica apertura y cierre por take profit (+2000 puntos) en shadow."""
        # Abrir posición a t0 = 14:30:00
        ev_open = _crear_tick_shadow(seq=1, occurred_at_utc=self.t0, bid=500000, ask=500040)
        res_paso1 = self.caso_uso.procesar_evento(ev_open)
        self.assertTrue(res_paso1.exito)
        self.assertIsNotNone(res_paso1.datos.simulation_opened)

        # Avanzar tick al objetivo de take profit
        t_tp = self.t0 + timedelta(seconds=10)
        ev_tp = _crear_tick_shadow(seq=2, occurred_at_utc=t_tp, bid=502200, ask=502240)
        res_paso2 = self.caso_uso.procesar_evento(ev_tp)
        self.assertTrue(res_paso2.exito)
        paso2 = res_paso2.datos

        self.assertEqual(len(paso2.simulations_closed), 1)
        sim_cerrada = paso2.simulations_closed[0]
        self.assertEqual(sim_cerrada.status, "CLOSED_SIMULATED")
        self.assertEqual(sim_cerrada.exit_reason, "target")
        self.assertGreater(sim_cerrada.net_pnl, 0)
        self.assertGreater(sim_cerrada.realized_r, 0)

    def test_ciclo_completo_stop_loss_en_shadow(self) -> None:
        """Verifica cierre por stop loss ante movimiento adverso (-500 puntos) en shadow."""
        # Abrir posición a t0
        ev_open = _crear_tick_shadow(seq=1, occurred_at_utc=self.t0, bid=500000, ask=500040)
        self.caso_uso.procesar_evento(ev_open)

        # Caída brusca de precio
        t_sl = self.t0 + timedelta(seconds=10)
        ev_sl = _crear_tick_shadow(seq=2, occurred_at_utc=t_sl, bid=499400, ask=499440)
        res_paso2 = self.caso_uso.procesar_evento(ev_sl)
        self.assertTrue(res_paso2.exito)
        paso2 = res_paso2.datos

        self.assertEqual(len(paso2.simulations_closed), 1)
        sim_cerrada = paso2.simulations_closed[0]
        self.assertEqual(sim_cerrada.status, "CLOSED_SIMULATED")
        self.assertEqual(sim_cerrada.exit_reason, "stop")
        self.assertLess(sim_cerrada.net_pnl, 0)


class TestShadowSeguridadYKillSwitch(unittest.TestCase):
    """Verifica cumplimiento de RNF-L001, RNF-L002, RNF-L011 y switches de corte."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_shadow_safety.db"
        self.t0 = datetime(2026, 8, 30, 14, 30, 0, tzinfo=timezone.utc)
        self.caso_uso = ShadowUseCase(db_path=self.db_path, tiempo_inicial_utc=self.t0)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_cero_capacidades_mutantes_de_broker(self) -> None:
        """Demuestra ausencia de endpoints mutantes o emisión de órdenes en ShadowUseCase."""
        # Verificar atributos públicos del caso de uso
        atributos = dir(self.caso_uso)
        for attr in atributos:
            attr_lower = attr.lower().replace("_", "")
            self.assertNotIn("placeorder", attr_lower)
            self.assertNotIn("sendorder", attr_lower)
            self.assertNotIn("modifyorder", attr_lower)
            self.assertNotIn("cancelorder", attr_lower)
            self.assertNotIn("deleteorder", attr_lower)

    def test_kill_switch_bloquea_simulaciones_y_fuerza_amarillo(self) -> None:
        """La activación del kill switch impone amarillo inmediato y bloquea simulación."""
        # 1. Configurar modelo con alta convicción
        modelo = ModeloBaseV1(
            model_id="00000000-0000-0000-0000-000000000088",
            prior_long_scaled=900_000,
        )
        self.caso_uso.pipeline.registro_modelos.registrar(modelo)
        self.caso_uso.pipeline.model_id_campeon = modelo.model_id

        # 2. Activar kill switch
        res_ks = self.caso_uso.activar_kill_switch("Prueba de corte de emergencia")
        self.assertTrue(res_ks.exito)
        self.assertTrue(self.caso_uso.kill_switch_active)
        self.assertEqual(self.caso_uso.current_light, "YELLOW")

        # 3. Procesar tick en ventana S30
        ev = _crear_tick_shadow(seq=1, occurred_at_utc=self.t0)
        res_paso = self.caso_uso.procesar_evento(ev)
        self.assertTrue(res_paso.exito)
        paso = res_paso.datos

        # Simulación bloqueada
        self.assertIsNone(paso.simulation_opened)
        self.assertEqual(paso.light, "YELLOW")
        self.assertEqual(paso.direction, "MONITORIZAR")

        # Proyección refleja kill switch activado y luz amarilla forzada
        res_proy = self.caso_uso.obtener_proyeccion_v1()
        self.assertTrue(res_proy.exito)
        proy = res_proy.datos
        self.assertTrue(proy.kill_switch_active)
        self.assertEqual(proy.light, "YELLOW")
        self.assertEqual(proy.direction, "MONITORIZAR")
        self.assertIn("KILL_SWITCH_ACTIVE", proy.reason_codes)

    def test_forzar_amarillo_manual(self) -> None:
        """Prueba forzar_amarillo manual en ShadowUseCase."""
        res_fa = self.caso_uso.forzar_amarillo("DESCONEXION_OPERADOR")
        self.assertTrue(res_fa.exito)
        self.assertEqual(self.caso_uso.current_light, "YELLOW")
        self.assertTrue(res_fa.datos.safety_forced)


class TestShadowFlujoPorLotesYResumen(unittest.TestCase):
    """Verifica ejecución de lotes completos, resumen operativo y validación de esquema."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_shadow_batch.db"
        self.t0 = datetime(2026, 8, 30, 14, 30, 0, tzinfo=timezone.utc)
        self.caso_uso = ShadowUseCase(db_path=self.db_path, tiempo_inicial_utc=self.t0)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_procesar_flujo_completo_con_dataset(self) -> None:
        """Verifica procesar_flujo() sobre un dataset de streaming y validación de ProyeccionLecturaV1."""
        dataset = [
            _crear_tick_shadow(
                seq=i,
                occurred_at_utc=self.t0 + timedelta(seconds=i * 5),
                bid=500000 + i * 10,
                ask=500040 + i * 10,
                correlation_id="00000000-0000-0000-0000-000000000055",
            )
            for i in range(1, 15)
        ]

        res_ses = self.caso_uso.inicializar_sesion(
            solicitud=SolicitudShadow(
                correlation_id="00000000-0000-0000-0000-000000000055",
                environment="SHADOW",
                source_profile_version="v1",
                capabilities_manifest_hash="a" * 64,
                expected_demo_account_hash="b" * 64,
            ),
            dataset=dataset,
        )
        self.assertTrue(res_ses.exito)

        res_flujo = self.caso_uso.procesar_flujo()
        self.assertTrue(res_flujo.exito, msg=f"Error en flujo: {res_flujo.error if not res_flujo.exito else ''}")
        resumen: ResumenEjecucionShadow = res_flujo.datos

        self.assertEqual(resumen.environment, "SHADOW")
        self.assertEqual(resumen.accepted_event_count, 14)
        self.assertEqual(resumen.rejected_event_count, 0)
        self.assertEqual(resumen.current_health_state, "HEALTHY")

        # Proyección válida
        self.assertIsNotNone(resumen.proyeccion)
        res_val = validar_proyeccion_lectura_v1(resumen.proyeccion)
        self.assertTrue(res_val.exito)

        # Conversión a ResumenEjecucion canónico
        res_ej = resumen.to_resumen_ejecucion()
        self.assertEqual(res_ej.environment, "SHADOW")
        self.assertEqual(res_ej.accepted_event_count, 14)
        val_res_ej = validar_resumen_ejecucion(res_ej)
        self.assertTrue(val_res_ej.exito)

    def test_ejecutar_shadow_funcion_top_level(self) -> None:
        """Verifica la función ejecutar_shadow de nivel superior."""
        solicitud = SolicitudShadow(
            correlation_id="00000000-0000-0000-0000-000000000066",
            environment="SHADOW",
            source_profile_version="ctrader-demo-v1",
            capabilities_manifest_hash="c" * 64,
            expected_demo_account_hash="d" * 64,
        )

        dataset = [
            _crear_tick_shadow(
                seq=1,
                occurred_at_utc=self.t0,
                correlation_id=solicitud.correlation_id,
            )
        ]

        res = ejecutar_shadow(
            solicitud=solicitud,
            dataset=dataset,
            db_path=self.db_path,
            tiempo_inicial_utc=self.t0,
        )
        self.assertTrue(res.exito)
        resumen = res.datos
        self.assertEqual(resumen.environment, "SHADOW")
        self.assertEqual(resumen.accepted_event_count, 1)
        self.assertEqual(resumen.rejected_event_count, 0)


class TestShadowCeroBifurcacionEquivalencia(unittest.TestCase):
    """Verifica que Replay y Shadow producen idéntica secuencia de estados y decisiones (RF-L011)."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_replay = Path(self.temp_dir.name) / "replay.db"
        self.db_shadow = Path(self.temp_dir.name) / "shadow.db"
        self.t0 = datetime(2026, 8, 30, 14, 30, 0, tzinfo=timezone.utc)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_equivalencia_estricta_replay_y_shadow(self) -> None:
        """Demuestra cero bifurcación: Replay y Shadow procesan idéntico dataset y producen idénticas decisiones."""
        modelo = ModeloBaseV1(
            model_id="00000000-0000-0000-0000-000000000077",
            prior_long_scaled=800_000,
        )

        p_replay = crear_pipeline_replay(db_path=self.db_replay, clock_seed=20260830)
        p_replay.registro_modelos.registrar(modelo)
        p_replay.model_id_campeon = modelo.model_id

        p_shadow = crear_caso_uso_shadow(
            db_path=self.db_shadow,
            model_id_campeon=modelo.model_id,
            tiempo_inicial_utc=self.t0,
        )
        p_shadow.pipeline.registro_modelos.registrar(modelo)

        # Generar 6 ticks (incluyendo cierre S30 a los 30s)
        dataset_r = [
            _crear_tick_shadow(
                seq=i,
                occurred_at_utc=self.t0 + timedelta(seconds=i * 6),
                bid=500000 + i * 10,
                ask=500040 + i * 10,
                environment="REPLAY",
                correlation_id="00000000-0000-0000-0000-000000000088",
            )
            for i in range(1, 7)
        ]

        dataset_s = [
            _crear_tick_shadow(
                seq=i,
                occurred_at_utc=self.t0 + timedelta(seconds=i * 6),
                bid=500000 + i * 10,
                ask=500040 + i * 10,
                environment="SHADOW",
                correlation_id="00000000-0000-0000-0000-000000000088",
            )
            for i in range(1, 7)
        ]

        # Procesar en Replay
        pasos_r = []
        for ev in dataset_r:
            res_r = p_replay.procesar_evento(ev)
            self.assertTrue(res_r.exito)
            pasos_r.append(res_r.datos)

        # Procesar en Shadow
        pasos_s = []
        for ev in dataset_s:
            res_s = p_shadow.procesar_evento(ev)
            self.assertTrue(res_s.exito)
            pasos_s.append(res_s.datos)

        self.assertEqual(len(pasos_r), len(pasos_s))
        for pr, ps in zip(pasos_r, pasos_s):
            self.assertEqual(pr.health_state, ps.health_state)
            self.assertEqual(pr.light, ps.light)
            self.assertEqual(pr.direction, ps.direction)
            self.assertEqual(bool(pr.case_generated), bool(ps.case_generated))
            self.assertEqual(bool(pr.signal_emitted), bool(ps.signal_emitted))
            self.assertEqual(bool(pr.simulation_opened), bool(ps.simulation_opened))


class TestShadowCTraderDemoAdaptadorIntegracion(unittest.TestCase):
    """Verifica la integración con AdaptadorCTraderDemoReadOnly y eventos de reconexión."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_shadow_ctrader.db"
        self.t0 = datetime(2026, 8, 30, 14, 30, 0, tzinfo=timezone.utc)
        self.account_hash = hashlib.sha256(b"demo-shadow-account").hexdigest()
        self.caso_uso = ShadowUseCase(db_path=self.db_path, tiempo_inicial_utc=self.t0)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_streaming_desde_adaptador_ctrader_demo_readonly(self) -> None:
        """Verifica ingesta desde AdaptadorCTraderDemoReadOnly con validación de metadatos demo."""
        adaptador = AdaptadorCTraderDemoReadOnly()
        sol_cnx = SolicitudConexionCTrader(
            correlation_id="00000000-0000-0000-0000-000000000099",
            environment="SHADOW",
            capabilities=("market_data.read", "account_metadata.read"),
            expected_demo_account_hash=self.account_hash,
            symbol_id="US500",
        )
        res_ses = adaptador.conectar(solicitud=sol_cnx)
        self.assertTrue(res_ses.exito)
        sesion_ctrader = res_ses.datos

        # Inyectar mensaje raw de tick
        raw_msg = {
            "type": "QUOTE_TICK",
            "timestamp_utc": self.t0,
            "sequence": 1,
            "bid": 500000,
            "ask": 500040,
            "price_scale": 100,
        }
        res_raw = sesion_ctrader.recibir_mensaje_raw(raw_msg)
        self.assertTrue(res_raw.exito)
        sobre = res_raw.datos
        self.assertIsNotNone(sobre)

        # Procesar a través de ShadowUseCase
        res_paso = self.caso_uso.procesar_evento(sobre)
        self.assertTrue(res_paso.exito)
        self.assertEqual(res_paso.datos.health_state, "HEALTHY")

        # Inyectar reconexión tras pérdida de enlace
        t_rec = self.t0 + timedelta(seconds=5)
        res_rec = sesion_ctrader.registrar_reconexion(reconnected_at_utc=t_rec, duration_ms=250)
        self.assertTrue(res_rec.exito)
        sobre_rec = res_rec.datos
        self.assertEqual(sobre_rec.event_type, "RECONNECTED")

        res_paso_rec = self.caso_uso.procesar_evento(sobre_rec)
        self.assertTrue(res_paso_rec.exito)


if __name__ == "__main__":
    unittest.main()
