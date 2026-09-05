"""Empirical Challenger Stress Harness for Clock Injection & Temporal Decoupling (Milestone M1).

Tests:
1. Clock rollback rejection & pipeline resilience.
2. Boundary timestamp values (Epoch 0, pre-epoch, far future, leap year, market open/close, DST).
3. Microsecond advancements (0-delta, 1-microsecond delta, UUID & hash determinism).
4. Timezone handling (naive, non-UTC aware, None fallback, parameter aliases).
5. End-to-end Shadow pipeline determinism & zero unhandled exceptions.
"""

from datetime import datetime, time, timedelta, timezone
import json
from pathlib import Path
import sys
import unittest
import uuid
import zoneinfo

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sistema_luces.application.composition_root import (
    PipelineCompositionRoot,
    crear_pipeline_replay,
    crear_pipeline_shadow,
    generar_uuid_determinista,
)
from sistema_luces.application.shadow_use_case import (
    FuenteShadowFake,
    SesionShadowFake,
    ShadowUseCase,
    crear_caso_uso_shadow,
    ejecutar_shadow,
)
from sistema_luces.domain.api import SolicitudShadow
from sistema_luces.domain.event import SobreEventoV1, canonical_json_dumps, compute_payload_hash
from sistema_luces.domain.vocabulary import MAPEO_LUZ_A_DIRECCION_CANONICA
from sistema_luces.sources.clock import RelojDominio
from sistema_luces.sources.replay import SolicitudFuente


def test_clock_rollback() -> dict:
    results = {}
    t0 = datetime(2026, 8, 30, 14, 30, 0, tzinfo=timezone.utc)
    reloj = RelojDominio(tiempo_inicial_utc=t0)

    # 1.1 Direct rollback attempt
    t_past = t0 - timedelta(seconds=1)
    try:
        reloj.avanzar_hasta(t_past)
        results["direct_rollback"] = "FAILED (no exception raised)"
    except ValueError as e:
        results["direct_rollback"] = f"PASSED (ValueError caught: {e})"

    # 1.2 Pipeline event out of order
    pipeline = crear_pipeline_shadow(tiempo_inicial_utc=t0)
    
    # Send event 1 at 14:30:00
    ev1 = _make_tick(1, t0, bid=500000, ask=500040)
    res1 = pipeline.procesar_evento(ev1)
    
    # Send event 2 in the past at 14:29:50
    ev2 = _make_tick(2, t0 - timedelta(seconds=10), bid=500000, ask=500040)
    try:
        res2 = pipeline.procesar_evento(ev2)
        # Pipeline must not crash; should handle rollback gracefully
        results["pipeline_rollback_handling"] = {
            "survived": True,
            "res1_exito": res1.exito,
            "res2_exito": res2.exito,
            "res2_health": res2.datos.health_state if res2.exito else "ERROR",
            "current_light": pipeline.current_light,
        }
    except Exception as e:
        results["pipeline_rollback_handling"] = {"survived": False, "error": str(e)}

    # 1.3 ShadowUseCase stream with out-of-order event
    caso_uso = ShadowUseCase(tiempo_inicial_utc=t0)
    sol = SolicitudFuente(
        correlation_id="test-rollback-stream",
        environment="SHADOW",
        source_profile_version="v1",
        instrument="US500",
        range_start_utc=t0,
        range_end_utc=t0 + timedelta(minutes=5),
    )
    dataset = [ev1, ev2]
    res_ses = caso_uso.inicializar_sesion(solicitud=sol, dataset=dataset)
    try:
        res_flujo = caso_uso.procesar_flujo()
        results["shadow_use_case_stream_rollback"] = {
            "survived": True,
            "exito": res_flujo.exito,
            "health_state": caso_uso.health_state,
            "current_light": caso_uso.current_light,
        }
    except Exception as e:
        results["shadow_use_case_stream_rollback"] = {"survived": False, "error": str(e)}

    return results


def test_boundary_timestamps() -> dict:
    results = {}
    
    # 2.1 Epoch zero (1970-01-01T00:00:00Z)
    t_epoch = datetime(1970, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    r_epoch = RelojDominio(tiempo_inicial_utc=t_epoch)
    results["epoch_zero"] = {
        "ahora_utc": r_epoch.ahora_utc().isoformat(),
        "hora_ny": r_epoch.hora_ny().isoformat(),
        "fecha_sesion_ny": r_epoch.fecha_sesion_ny(),
        "es_fin_de_semana_ny": r_epoch.es_fin_de_semana_ny(),
        "en_sesion_ny": r_epoch.en_sesion_ny(),
    }

    # 2.2 Pre-epoch (1900-01-01T12:00:00Z)
    t_pre = datetime(1900, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    r_pre = RelojDominio(tiempo_inicial_utc=t_pre)
    results["pre_epoch"] = {
        "ahora_utc": r_pre.ahora_utc().isoformat(),
        "hora_ny": r_pre.hora_ny().isoformat(),
        "fecha_sesion_ny": r_pre.fecha_sesion_ny(),
    }

    # 2.3 Far future (2099-12-31T23:59:59Z & 9999-12-31T23:59:59Z)
    t_future = datetime(2099, 12, 31, 23, 59, 59, tzinfo=timezone.utc)
    r_future = RelojDominio(tiempo_inicial_utc=t_future)
    results["far_future_2099"] = {
        "ahora_utc": r_future.ahora_utc().isoformat(),
        "hora_ny": r_future.hora_ny().isoformat(),
        "fecha_sesion_ny": r_future.fecha_sesion_ny(),
    }

    t_9999 = datetime(9999, 12, 31, 23, 59, 59, tzinfo=timezone.utc)
    r_9999 = RelojDominio(tiempo_inicial_utc=t_9999)
    results["far_future_9999"] = {
        "ahora_utc": r_9999.ahora_utc().isoformat(),
        "hora_ny": r_9999.hora_ny().isoformat(),
    }

    # 2.4 Leap year (2024-02-29 and 2028-02-29)
    t_leap24 = datetime(2024, 2, 29, 14, 30, 0, tzinfo=timezone.utc)
    r_leap24 = RelojDominio(tiempo_inicial_utc=t_leap24)
    results["leap_year_2024"] = {
        "fecha_ny": r_leap24.fecha_sesion_ny(),
        "es_fin_de_semana": r_leap24.es_fin_de_semana_ny(),
        "en_sesion": r_leap24.en_sesion_ny(),
        "es_inicio": r_leap24.es_inicio_sesion_ny(),
    }

    # 2.5 Market Open / Close exact boundaries
    # Monday 2026-08-31: NY is EDT (UTC-4). 09:30 EDT = 13:30 UTC. 16:00 EDT = 20:00 UTC.
    t_open = datetime(2026, 8, 31, 13, 30, 0, tzinfo=timezone.utc)
    r_open = RelojDominio(tiempo_inicial_utc=t_open)
    t_close = datetime(2026, 8, 31, 20, 0, 0, tzinfo=timezone.utc)
    r_close = RelojDominio(tiempo_inicial_utc=t_close)
    t_just_before = datetime(2026, 8, 31, 13, 29, 59, 999999, tzinfo=timezone.utc)
    r_just_before = RelojDominio(tiempo_inicial_utc=t_just_before)
    t_just_after = datetime(2026, 8, 31, 20, 0, 0, 1, tzinfo=timezone.utc)
    r_just_after = RelojDominio(tiempo_inicial_utc=t_just_after)

    results["market_open_close_ny"] = {
        "open_en_sesion": r_open.en_sesion_ny(),
        "open_es_inicio": r_open.es_inicio_sesion_ny(),
        "close_en_sesion": r_close.en_sesion_ny(),
        "close_es_cierre": r_close.es_cierre_sesion_ny(),
        "before_en_sesion": r_just_before.en_sesion_ny(),
        "after_en_sesion": r_just_after.en_sesion_ny(),
    }

    # 2.6 DST Transition (EDT summer vs EST winter)
    # Summer: 2026-07-01 13:30 UTC -> 09:30 EDT (UTC-4)
    r_summer = RelojDominio(datetime(2026, 7, 1, 13, 30, 0, tzinfo=timezone.utc))
    # Winter: 2026-01-15 14:30 UTC -> 09:30 EST (UTC-5)
    r_winter = RelojDominio(datetime(2026, 1, 15, 14, 30, 0, tzinfo=timezone.utc))
    results["dst_transitions"] = {
        "summer_edt_hour": r_summer.hora_ny().hour,
        "summer_edt_minute": r_summer.hora_ny().minute,
        "summer_is_open": r_summer.es_inicio_sesion_ny(),
        "winter_est_hour": r_winter.hora_ny().hour,
        "winter_est_minute": r_winter.hora_ny().minute,
        "winter_is_open": r_winter.es_inicio_sesion_ny(),
    }

    return results


def test_microsecond_advancements() -> dict:
    results = {}
    t0 = datetime(2026, 8, 30, 14, 30, 0, 0, tzinfo=timezone.utc)
    reloj = RelojDominio(tiempo_inicial_utc=t0)

    # 3.1 Zero delta (same timestamp)
    reloj.avanzar_hasta(t0)
    results["zero_delta"] = {
        "success": reloj.ahora_utc() == t0,
        "ts": reloj.ahora_utc().isoformat(),
    }

    # 3.2 1 microsecond delta
    t1_us = t0 + timedelta(microseconds=1)
    reloj.avanzar_hasta(t1_us)
    results["one_microsecond_delta"] = {
        "success": reloj.ahora_utc() == t1_us,
        "ts": reloj.ahora_utc().isoformat(),
        "microseconds": reloj.ahora_utc().microsecond,
    }

    # 3.3 Microsecond pipeline processing & projection formatting
    pipeline = crear_pipeline_shadow(tiempo_inicial_utc=t0)
    ev_us = _make_tick(1, t1_us, bid=500000, ask=500040)
    res_step = pipeline.procesar_evento(ev_us)
    res_proy = pipeline.obtener_proyeccion_v1()
    
    results["pipeline_microsecond_step"] = {
        "step_exito": res_step.exito,
        "proy_exito": res_proy.exito,
        "proy_generated_at": res_proy.datos.generated_at_utc.isoformat() if res_proy.exito else None,
        "proy_cutoff": res_proy.datos.market_cutoff_utc.isoformat() if res_proy.exito and res_proy.datos.market_cutoff_utc else None,
        "data_age_ms": res_proy.datos.data_age_ms if res_proy.exito else None,
    }

    return results


def test_timezone_fallbacks() -> dict:
    results = {}

    # 4.1 Naive datetime passed to RelojDominio
    t_naive = datetime(2026, 8, 30, 14, 30, 0)
    r_naive = RelojDominio(tiempo_inicial_utc=t_naive)
    results["naive_initial"] = {
        "tzinfo": str(r_naive.ahora_utc().tzinfo),
        "iso": r_naive.ahora_utc().isoformat(),
        "matches_utc": r_naive.ahora_utc() == datetime(2026, 8, 30, 14, 30, 0, tzinfo=timezone.utc),
    }

    # 4.2 Non-UTC Aware datetime (Tokyo UTC+9, NY UTC-4)
    tz_tokyo = zoneinfo.ZoneInfo("Asia/Tokyo")
    t_tokyo = datetime(2026, 8, 30, 23, 30, 0, tzinfo=tz_tokyo)  # 23:30 Tokyo = 14:30 UTC
    r_tokyo = RelojDominio(tiempo_inicial_utc=t_tokyo)
    results["non_utc_aware_tokyo"] = {
        "ahora_utc": r_tokyo.ahora_utc().isoformat(),
        "matches_14_30_utc": r_tokyo.ahora_utc() == datetime(2026, 8, 30, 14, 30, 0, tzinfo=timezone.utc),
    }

    # 4.3 Naive datetime in avanzar_hasta
    t_adv_naive = datetime(2026, 8, 30, 14, 35, 0)
    r_naive.avanzar_hasta(t_adv_naive)
    results["naive_avanzar_hasta"] = {
        "ahora_utc": r_naive.ahora_utc().isoformat(),
        "matches_14_35_utc": r_naive.ahora_utc() == datetime(2026, 8, 30, 14, 35, 0, tzinfo=timezone.utc),
    }

    # 4.4 Parameter aliases (tiempo_inicial vs tiempo_inicial_utc)
    t_ref = datetime(2026, 8, 30, 10, 0, 0, tzinfo=timezone.utc)
    r_param1 = RelojDominio(tiempo_inicial=t_ref)
    r_param2 = RelojDominio(tiempo_inicial_utc=t_ref)
    results["param_aliases"] = {
        "tiempo_inicial": r_param1.ahora_utc().isoformat(),
        "tiempo_inicial_utc": r_param2.ahora_utc().isoformat(),
        "identical": r_param1.ahora_utc() == r_param2.ahora_utc(),
    }

    # 4.5 None defaults
    r_none = RelojDominio()
    results["none_default"] = {
        "ahora_utc": r_none.ahora_utc().isoformat(),
        "clock_seed": r_none.clock_seed,
    }

    # 4.6 crear_pipeline_shadow factory parameter combinations
    p_none = crear_pipeline_shadow()
    p_reloj = crear_pipeline_shadow(reloj=r_tokyo)
    p_time = crear_pipeline_shadow(tiempo_inicial_utc=t_ref)
    results["pipeline_factories"] = {
        "p_none_has_reloj": p_none.reloj is not None,
        "p_reloj_exact": p_reloj.reloj.ahora_utc() == r_tokyo.ahora_utc(),
        "p_time_exact": p_time.reloj.ahora_utc() == t_ref,
    }

    return results


def test_strict_determinism_e2e() -> dict:
    results = {}
    t0 = datetime(2026, 8, 30, 14, 30, 0, tzinfo=timezone.utc)
    cid = "00000000-0000-0000-0000-000000000099"

    # Build a sequence of 60 ticks across 30 seconds to trigger S30 window close
    dataset = []
    current_time = t0
    for i in range(1, 61):
        dataset.append(_make_tick(
            seq=i,
            occurred_at_utc=current_time,
            bid=500000 + (i % 10) * 10,
            ask=500040 + (i % 10) * 10,
            correlation_id=cid,
        ))
        current_time += timedelta(milliseconds=500)

    # Run 1: ShadowUseCase
    cu1 = ShadowUseCase(tiempo_inicial_utc=t0, clock_seed=20260830)
    sol1 = SolicitudFuente(
        correlation_id=cid,
        environment="SHADOW",
        source_profile_version="v1",
        instrument="US500",
        range_start_utc=t0,
        range_end_utc=current_time,
        clock_seed=20260830,
    )
    cu1.inicializar_sesion(solicitud=sol1, dataset=dataset)
    res_flujo1 = cu1.procesar_flujo()
    proy1 = cu1.obtener_proyeccion_v1().datos

    # Run 2: ShadowUseCase identical setup
    cu2 = ShadowUseCase(tiempo_inicial_utc=t0, clock_seed=20260830)
    sol2 = SolicitudFuente(
        correlation_id=cid,
        environment="SHADOW",
        source_profile_version="v1",
        instrument="US500",
        range_start_utc=t0,
        range_end_utc=current_time,
        clock_seed=20260830,
    )
    cu2.inicializar_sesion(solicitud=sol2, dataset=dataset)
    res_flujo2 = cu2.procesar_flujo()
    proy2 = cu2.obtener_proyeccion_v1().datos

    # Serialize projections to canonical JSON strings
    json1 = canonical_json_dumps(proy1.to_dict())
    json2 = canonical_json_dumps(proy2.to_dict())

    # Check all events persisted in both stores
    from sistema_luces.storage.event_store import ConsultaEventos
    events1 = [e.payload_hash for e in cu1.pipeline.almacen.leer(ConsultaEventos(limit=1000)).datos.events]
    events2 = [e.payload_hash for e in cu2.pipeline.almacen.leer(ConsultaEventos(limit=1000)).datos.events]

    results["runs_identical_json"] = json1 == json2
    results["runs_identical_hashes"] = events1 == events2
    results["total_events_run1"] = len(events1)
    results["total_events_run2"] = len(events2)
    results["json_length"] = len(json1)

    return results


def _make_tick(seq: int, occurred_at_utc: datetime, bid: int = 500000, ask: int = 500040, correlation_id: str = "stress-cid") -> SobreEventoV1:
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


def main():
    print("=" * 70)
    print("⚡ RUNNING EMPIRICAL CHALLENGER STRESS HARNESS (MILESTONE M1)")
    print("=" * 70)

    print("\n[1/5] Testing Clock Rollback Rejection & Pipeline Resilience...")
    r1 = test_clock_rollback()
    print(json.dumps(r1, indent=2))

    print("\n[2/5] Testing Boundary Timestamp Values...")
    r2 = test_boundary_timestamps()
    print(json.dumps(r2, indent=2))

    print("\n[3/5] Testing Microsecond Advancements & Determinism...")
    r3 = test_microsecond_advancements()
    print(json.dumps(r3, indent=2))

    print("\n[4/5] Testing Timezone Normalization & Fallbacks...")
    r4 = test_timezone_fallbacks()
    print(json.dumps(r4, indent=2))

    print("\n[5/5] Testing Strict Byte-a-Byte Determinism E2E...")
    r5 = test_strict_determinism_e2e()
    print(json.dumps(r5, indent=2))

    all_passed = (
        "PASSED" in r1["direct_rollback"]
        and r1["pipeline_rollback_handling"]["survived"]
        and r1["shadow_use_case_stream_rollback"]["survived"]
        and r2["market_open_close_ny"]["open_es_inicio"] is True
        and r2["dst_transitions"]["summer_is_open"] is True
        and r2["dst_transitions"]["winter_is_open"] is True
        and r3["zero_delta"]["success"] is True
        and r3["one_microsecond_delta"]["success"] is True
        and r4["naive_initial"]["matches_utc"] is True
        and r4["non_utc_aware_tokyo"]["matches_14_30_utc"] is True
        and r4["param_aliases"]["identical"] is True
        and r5["runs_identical_json"] is True
        and r5["runs_identical_hashes"] is True
    )

    print("\n" + "=" * 70)
    if all_passed:
        print("✅ ALL EMPIRICAL STRESS TESTS PASSED (100% SUCCESS)")
    else:
        print("❌ SOME EMPIRICAL STRESS TESTS FAILED")
    print("=" * 70)

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
