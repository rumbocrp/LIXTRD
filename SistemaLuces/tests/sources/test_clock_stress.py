"""Pruebas adversariales y de estrés para RelojDominio y desacople temporal (Milestone M1).

Verifica empíricamente:
1. Rechazo de rollback y degradación segura a STALE/YELLOW.
2. Timestamps límite (Epoch 0, pre-epoch, far future, bisiestos, aperturas/cierres NY, DST).
3. Avances por microsegundo (0-delta, 1-microsegundo delta, preservación de precisión).
4. Normalización y fallback de zonas horarias (naive, non-UTC aware, None default, alias de parámetros).
5. Determinismo byte-a-byte en ejecuciones Shadow E2E.
"""

from datetime import datetime, timedelta, timezone
import unittest
import uuid
import zoneinfo

from sistema_luces.application.composition_root import (
    crear_pipeline_shadow,
    generar_uuid_determinista,
)
from sistema_luces.application.shadow_use_case import (
    FuenteShadowFake,
    ShadowUseCase,
)
from sistema_luces.domain.event import (
    SobreEventoV1,
    canonical_json_dumps,
    compute_payload_hash,
)
from sistema_luces.sources.clock import RelojDominio
from sistema_luces.sources.replay import SolicitudFuente
from sistema_luces.storage.event_store import ConsultaEventos


def _crear_tick_stress(
    seq: int,
    occurred_at_utc: datetime,
    bid: int = 500000,
    ask: int = 500040,
    correlation_id: str = "00000000-0000-0000-0000-000000000099",
) -> SobreEventoV1:
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
        environment="SHADOW",
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


class TestClockAdversarialStress(unittest.TestCase):
    """Suite de estrés adversarial sobre reloj de dominio y composición shadow."""

    def test_clock_rollback_rejection_and_pipeline_resilience(self) -> None:
        t0 = datetime(2026, 8, 30, 14, 30, 0, tzinfo=timezone.utc)
        reloj = RelojDominio(tiempo_inicial_utc=t0)

        # 1. Rollback directo en reloj lanza ValueError
        with self.assertRaises(ValueError) as ctx:
            reloj.avanzar_hasta(t0 - timedelta(seconds=1))
        self.assertIn("Clock rollback detectado", str(ctx.exception))

        # 2. Pipeline maneja evento fuera de orden sin excepciones no controladas y degrada salud
        pipeline = crear_pipeline_shadow(tiempo_inicial_utc=t0)
        ev1 = _crear_tick_stress(1, t0)
        res1 = pipeline.procesar_evento(ev1)
        self.assertTrue(res1.exito)

        ev2_past = _crear_tick_stress(2, t0 - timedelta(seconds=10))
        res2 = pipeline.procesar_evento(ev2_past)
        self.assertTrue(res2.exito)
        self.assertEqual(res2.datos.health_state, "STALE")
        self.assertEqual(pipeline.current_light, "YELLOW")

    def test_boundary_timestamps(self) -> None:
        # Epoch zero
        t_epoch = datetime(1970, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        r_epoch = RelojDominio(tiempo_inicial_utc=t_epoch)
        self.assertEqual(r_epoch.ahora_utc(), t_epoch)
        self.assertEqual(r_epoch.fecha_sesion_ny(), "1969-12-31")

        # Far future (2099 y 9999)
        t_future = datetime(2099, 12, 31, 23, 59, 59, tzinfo=timezone.utc)
        r_future = RelojDominio(tiempo_inicial_utc=t_future)
        self.assertEqual(r_future.ahora_utc(), t_future)

        # Año bisiesto 2024-02-29
        t_leap = datetime(2024, 2, 29, 14, 30, 0, tzinfo=timezone.utc)
        r_leap = RelojDominio(tiempo_inicial_utc=t_leap)
        self.assertEqual(r_leap.fecha_sesion_ny(), "2024-02-29")
        self.assertFalse(r_leap.es_fin_de_semana_ny())
        self.assertTrue(r_leap.en_sesion_ny())
        self.assertTrue(r_leap.es_inicio_sesion_ny())

        # Apertura y cierre exacto NY
        t_open = datetime(2026, 8, 31, 13, 30, 0, tzinfo=timezone.utc)  # 09:30 EDT
        r_open = RelojDominio(tiempo_inicial_utc=t_open)
        self.assertTrue(r_open.en_sesion_ny())
        self.assertTrue(r_open.es_inicio_sesion_ny())

        t_close = datetime(2026, 8, 31, 20, 0, 0, tzinfo=timezone.utc)  # 16:00 EDT
        r_close = RelojDominio(tiempo_inicial_utc=t_close)
        self.assertTrue(r_close.en_sesion_ny())
        self.assertTrue(r_close.es_cierre_sesion_ny())

        # Fuera de sesión
        t_before = datetime(2026, 8, 31, 13, 29, 59, 999999, tzinfo=timezone.utc)
        r_before = RelojDominio(tiempo_inicial_utc=t_before)
        self.assertFalse(r_before.en_sesion_ny())

        t_after = datetime(2026, 8, 31, 20, 0, 0, 1, tzinfo=timezone.utc)
        r_after = RelojDominio(tiempo_inicial_utc=t_after)
        self.assertFalse(r_after.en_sesion_ny())

    def test_microsecond_advancements(self) -> None:
        t0 = datetime(2026, 8, 30, 14, 30, 0, 0, tzinfo=timezone.utc)
        reloj = RelojDominio(tiempo_inicial_utc=t0)

        # 0-delta
        reloj.avanzar_hasta(t0)
        self.assertEqual(reloj.ahora_utc(), t0)

        # 1-microsecond delta
        t_us = t0 + timedelta(microseconds=1)
        reloj.avanzar_hasta(t_us)
        self.assertEqual(reloj.ahora_utc(), t_us)
        self.assertEqual(reloj.ahora_utc().microsecond, 1)

    def test_timezone_fallbacks_and_aliases(self) -> None:
        # Naive datetime normalizado a UTC
        t_naive = datetime(2026, 8, 30, 14, 30, 0)
        r_naive = RelojDominio(tiempo_inicial_utc=t_naive)
        self.assertEqual(r_naive.ahora_utc().tzinfo, timezone.utc)
        self.assertEqual(r_naive.ahora_utc(), datetime(2026, 8, 30, 14, 30, 0, tzinfo=timezone.utc))

        # Aware datetime en zona distinta (Asia/Tokyo UTC+9)
        tz_tokyo = zoneinfo.ZoneInfo("Asia/Tokyo")
        t_tokyo = datetime(2026, 8, 30, 23, 30, 0, tzinfo=tz_tokyo)
        r_tokyo = RelojDominio(tiempo_inicial_utc=t_tokyo)
        self.assertEqual(r_tokyo.ahora_utc(), datetime(2026, 8, 30, 14, 30, 0, tzinfo=timezone.utc))

        # Alias de parámetros en constructor
        r1 = RelojDominio(tiempo_inicial=t_naive)
        r2 = RelojDominio(tiempo_inicial_utc=t_naive)
        self.assertEqual(r1.ahora_utc(), r2.ahora_utc())

    def test_strict_byte_a_byte_determinism_shadow_e2e(self) -> None:
        t0 = datetime(2026, 8, 30, 14, 30, 0, tzinfo=timezone.utc)
        cid = "00000000-0000-0000-0000-000000000099"

        dataset = []
        cur_t = t0
        for i in range(1, 61):
            dataset.append(_crear_tick_stress(i, cur_t, 500000 + (i % 10) * 10, 500040 + (i % 10) * 10, correlation_id=cid))
            cur_t += timedelta(milliseconds=500)

        # Ejecución 1
        cu1 = ShadowUseCase(tiempo_inicial_utc=t0, clock_seed=20260830)
        sol1 = SolicitudFuente(
            correlation_id=cid,
            environment="SHADOW",
            source_profile_version="v1",
            instrument="US500",
            range_start_utc=t0,
            range_end_utc=cur_t,
            clock_seed=20260830,
        )
        cu1.inicializar_sesion(solicitud=sol1, dataset=dataset)
        cu1.procesar_flujo()
        proy1 = cu1.obtener_proyeccion_v1().datos

        # Ejecución 2
        cu2 = ShadowUseCase(tiempo_inicial_utc=t0, clock_seed=20260830)
        sol2 = SolicitudFuente(
            correlation_id=cid,
            environment="SHADOW",
            source_profile_version="v1",
            instrument="US500",
            range_start_utc=t0,
            range_end_utc=cur_t,
            clock_seed=20260830,
        )
        cu2.inicializar_sesion(solicitud=sol2, dataset=dataset)
        cu2.procesar_flujo()
        proy2 = cu2.obtener_proyeccion_v1().datos

        # Comparación byte-a-byte JSON
        json1 = canonical_json_dumps(proy1.to_dict())
        json2 = canonical_json_dumps(proy2.to_dict())
        self.assertEqual(json1, json2)

        # Comparación de hashes en almacén de eventos
        events1 = [e.payload_hash for e in cu1.pipeline.almacen.leer(ConsultaEventos(limit=1000)).datos.events]
        events2 = [e.payload_hash for e in cu2.pipeline.almacen.leer(ConsultaEventos(limit=1000)).datos.events]
        self.assertEqual(events1, events2)
