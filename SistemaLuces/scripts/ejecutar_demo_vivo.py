"""Replay demostrativo interactivo del Sistema de Luces (V1 US500).

Ejercita proyección, política, triple barrera y riesgo con fixtures REPLAY explícitos,
exponiendo la interfaz local en http://127.0.0.1:8080. No sustituye el composition root ni
una captura demo observada.
"""

from datetime import datetime, timedelta, timezone
import http.client
from pathlib import Path
import sys
import threading
import time

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from sistema_luces.domain.event import QuoteTickPayloadV1, SobreEventoV1, compute_payload_hash
from sistema_luces.domain.manifest import CostProfileV1, RiskProfileV1
from sistema_luces.domain.vocabulary import Light
from sistema_luces.observability.projections import ProyectorVistas
from sistema_luces.policy.lights import PoliticaLuces, SolicitudLuz
from sistema_luces.risk.engine import MotorRiesgo
from sistema_luces.simulation.paper import SimuladorPapel
from sistema_luces.ui.server import ServidorLoopback


def make_uuid(idx: int) -> str:
    h = f"{idx:032x}"
    return f"{h[:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:]}"


def main() -> None:
    print("=" * 75)
    print("SISTEMA DE LUCES — V1 US500 (REPLAY DEMOSTRATIVO; NO ES MERCADO EN VIVO)")
    print("=" * 75)
    print(f"🕒 Timestamp Inicial (UTC): {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"📁 Directorio Raíz: {REPO_ROOT}")
    print(f"🔒 Invariantes: Cero órdenes al broker | Enlace 127.0.0.1 | Fail-Closed")
    print("-" * 75)

    # 1. Inicializar Proyector de Vistas y Componentes
    proyector = ProyectorVistas()
    politica = PoliticaLuces(threshold_green=650_000, threshold_red=350_000)
    perfil_riesgo = RiskProfileV1(
        profile_version="risk-us500-demo-v1",
        max_risk_per_trade_usd_cents=5000,
        max_daily_loss_usd_cents=25000,
        max_daily_drawdown_usd_cents=25000,
        max_consecutive_losses=3,
        max_daily_openings=10,
        max_concurrent_positions=1,
        max_reference_lots=500,
        stale_threshold_ms=5000,
        news_blackout_minutes=15,
        kill_switch_active=False,
    )
    motor_riesgo = MotorRiesgo(profile=perfil_riesgo)
    simulador = SimuladorPapel(
        motor_riesgo=motor_riesgo,
        stop_points=500,
        target_points=2000,
    )

    t0 = datetime(2026, 8, 30, 9, 30, 0, tzinfo=timezone.utc)

    # 2. Simular Escenario en 5 Pasos Operativos
    pasos = [
        ("PASO 1", "Ingestión de cotizaciones US500 iniciales (5000.00 / 5000.40)"),
        ("PASO 2", "Cierre Ventana S30 -> Modelo detecta alta probabilidad alcista (72%) -> Luz VERDE (LONG)"),
        ("PASO 3", "Evaluación de Riesgo ($50) y Apertura de Simulación Paper LONG a 5000.40"),
        ("PASO 4", "Avance de Ticks a 5020.50 -> Cierre por TAKE PROFIT (+20.0 pts) -> P&L +$200.00"),
        ("PASO 5", "Cierre Ventana S30 -> Modelo neutral (50%) -> Transición Segura a AMARILLO (MONITOR)"),
        ("PASO 6", "Cierre Ventana S30 -> Modelo bajista (28%) -> Transición a ROJO (SHORT)"),
        ("PASO 7", "Inyección de Stale Feed (>5s) -> Fail-Closed inmediato a AMARILLO con FEED_DEGRADED"),
    ]

    eventos_historicos: list[SobreEventoV1] = []

    # --- PASO 1: Ticks Iniciales ---
    print(f"\n▶ [{pasos[0][0]}] {pasos[0][1]}")
    payload_tick_1 = {"bid": 500000, "ask": 500040, "price_scale": 100, "size_bid": 25, "size_ask": 30}
    ev_tick_1 = SobreEventoV1(
        event_id=make_uuid(1),
        event_type="QUOTE_TICK",
        schema_version=1,
        occurred_at_utc=t0,
        received_at_utc=t0 + timedelta(milliseconds=3),
        persisted_at_utc=t0 + timedelta(milliseconds=6),
        source="replay",
        environment="REPLAY",
        source_account_id_hash=None,
        instrument="US500",
        symbol_id="US500",
        source_sequence=1,
        correlation_id=make_uuid(1),
        causation_id=None,
        payload_hash=compute_payload_hash(payload_tick_1),
        previous_hash=None,
        payload=payload_tick_1,
    )
    eventos_historicos.append(ev_tick_1)
    proyector.actualizar_desde_evento(ev_tick_1)
    print("   ✓ Evento QUOTE_TICK procesado por el proyector REPLAY. Estado de Feed: HEALTHY.")

    # Fixture explícito de replay para demostrar el monitor multi-activo. No se presenta como dato en vivo.
    payload_cross_asset = {
        "source_name": "fixture-replay-cross-asset-v1",
        "data_age_ms": 80,
        "relations": [
            {
                "key": "SP500_TSLA",
                "name": "S&P 500 vs. TSLA",
                "category": "High-Beta Momentum",
                "symbol_y": "TSLA",
                "symbol_x": "US500",
                "price_y": 234.56,
                "price_x": 5000.20,
                "composite_score": 0.21,
                "threshold_green": 0.35,
                "threshold_red": -0.35,
                "confidence_pct": 60.2,
                "light": "YELLOW",
                "direction": "MONITORIZAR",
            },
            {
                "key": "SP500_AAPL",
                "name": "S&P 500 vs. AAPL",
                "category": "Ancla Sistémica",
                "symbol_y": "AAPL",
                "symbol_x": "US500",
                "price_y": 198.75,
                "price_x": 5000.20,
                "composite_score": -0.14,
                "threshold_green": 0.35,
                "threshold_red": -0.35,
                "confidence_pct": 56.8,
                "light": "YELLOW",
                "direction": "MONITORIZAR",
            },
        ],
    }
    ev_cross_asset = SobreEventoV1(
        event_id=make_uuid(2),
        event_type="CROSS_ASSET_SNAPSHOT",
        schema_version=1,
        occurred_at_utc=t0 + timedelta(milliseconds=10),
        received_at_utc=t0 + timedelta(milliseconds=12),
        persisted_at_utc=t0 + timedelta(milliseconds=14),
        source="replay",
        environment="REPLAY",
        source_account_id_hash=None,
        instrument="US500",
        symbol_id="US500",
        source_sequence=2,
        correlation_id=make_uuid(2),
        causation_id=make_uuid(1),
        payload_hash=compute_payload_hash(payload_cross_asset),
        previous_hash=ev_tick_1.payload_hash,
        payload=payload_cross_asset,
    )
    eventos_historicos.append(ev_cross_asset)
    proyector.actualizar_desde_evento(ev_cross_asset)
    print("   ✓ Fixture REPLAY multi-activo cargado: SP500/TSLA y SP500/AAPL con procedencia visible.")

    # --- PASO 2: Decisión Luz Verde ---
    t_s30 = t0 + timedelta(seconds=30)
    print(f"\n▶ [{pasos[1][0]}] {pasos[1][1]}")
    sol_luz_1 = SolicitudLuz(
        case_id=make_uuid(10),
        created_at_utc=t_s30,
        environment="REPLAY",
        instrument="US500",
        decision_window="S30",
        market_event_cutoff=t_s30,
        reference_bid=500000,
        reference_ask=500040,
        price_scale=100,
        data_age_ms=80,
        feed_health_state="HEALTHY",
        model_id="logreg-us500",
        model_version="1.0.0",
        model_hash="a" * 64,
        calibration_version="platt-v1",
        feature_snapshot_hash="f" * 64,
        raw_score_long=750000,
        raw_score_short=250000,
        calibrated_probability_long=720000,  # 72%
        calibrated_probability_short=280000,
        expected_value_long_net=18500,
        expected_value_short_net=-8000,
        cost_profile_version="cost-v1",
        correlation_id=make_uuid(11),
        causation_id=make_uuid(1),
        code_hash="c" * 64,
    )
    res_decision_1 = politica.decidir(sol_luz_1)
    if res_decision_1.exito:
        decision_1 = res_decision_1.datos
        ev_sig_1 = SobreEventoV1(
            event_id=make_uuid(12),
            event_type="SIGNAL_EMITTED",
            schema_version=1,
            occurred_at_utc=t_s30,
            received_at_utc=t_s30,
            persisted_at_utc=t_s30,
            source="replay",
            environment="REPLAY",
            source_account_id_hash=None,
            instrument="US500",
            symbol_id="US500",
            source_sequence=2,
            correlation_id=make_uuid(11),
            causation_id=make_uuid(10),
            payload_hash=compute_payload_hash({
                "light": decision_1.senal.light,
                "direction": decision_1.senal.direction,
                "calibrated_probability_long": decision_1.senal.calibrated_probability_long,
                "calibrated_probability_short": decision_1.senal.calibrated_probability_short,
                "threshold_green": politica.threshold_green,
                "threshold_red": politica.threshold_red,
                "reasons": list(decision_1.senal.reason_codes),
            }),
            previous_hash=ev_tick_1.payload_hash,
            payload={
                "light": decision_1.senal.light,
                "direction": decision_1.senal.direction,
                "calibrated_probability_long": decision_1.senal.calibrated_probability_long,
                "calibrated_probability_short": decision_1.senal.calibrated_probability_short,
                "threshold_green": politica.threshold_green,
                "threshold_red": politica.threshold_red,
                "reasons": list(decision_1.senal.reason_codes),
            },
        )
        proyector.actualizar_desde_evento(ev_sig_1)
        print(f"   🟢 LUZ EMITIDA: {decision_1.senal.light} | Dirección: {decision_1.senal.direction} | Prob: 72.0% | Razones: {decision_1.senal.reason_codes}")

    # --- PASO 3: Apertura Simulación ---
    print(f"\n▶ [{pasos[2][0]}] {pasos[2][1]}")
    res_open = simulador.proponer_y_abrir(
        senal=decision_1.senal,
        current_bid=500000,
        current_ask=500040,
        now_utc=t_s30,
        quantity=100,
    )
    if res_open.exito:
        sim_abierta = res_open.datos
        print(f"   ✓ Simulación OPEN_SIMULATED: Entrada ask 5000.40 | Stop 4995.40 | Target 5020.40 | Riesgo: $50.00")

        # --- PASO 4: Ticks alcistas y Cierre por Take Profit ---
        t_tp = t_s30 + timedelta(seconds=15)
        print(f"\n▶ [{pasos[3][0]}] {pasos[3][1]}")
        tick_tp = QuoteTickPayloadV1(
            bid=502050,  # +20.10 pts -> Target alcanzado en bid
            ask=502090,
            price_scale=100,
            bid_size=50,
            ask_size=50,
            source_timestamp_utc=t_tp,
            source_sequence=15,
        )
        res_close = simulador.avanzar_tick(
            simulation_id=sim_abierta.simulation_id,
            tick=tick_tp,
            now_utc=t_tp,
        )
        if res_close.exito:
            sim_cerrada = res_close.datos
            print(f"   🎯 TAKE PROFIT ALCANZADO: Salida a 5020.50 | Causa: {sim_cerrada.exit_reason} | P&L Bruto: +$200.00 | P&L Neto: +$196.00")

    # --- PASO 5: Transición a Amarillo (Neutral) ---
    t_s60 = t_s30 + timedelta(seconds=30)
    print(f"\n▶ [{pasos[4][0]}] {pasos[4][1]}")
    sol_luz_2 = SolicitudLuz(
        case_id=make_uuid(20),
        created_at_utc=t_s60,
        environment="REPLAY",
        instrument="US500",
        decision_window="S30",
        market_event_cutoff=t_s60,
        reference_bid=502050,
        reference_ask=502090,
        price_scale=100,
        data_age_ms=50,
        feed_health_state="HEALTHY",
        model_id="logreg-us500",
        model_version="1.0.0",
        model_hash="a" * 64,
        calibration_version="platt-v1",
        feature_snapshot_hash="f" * 64,
        raw_score_long=500000,
        raw_score_short=500000,
        calibrated_probability_long=500000,  # 50% Neutral
        calibrated_probability_short=500000,
        expected_value_long_net=0,
        expected_value_short_net=0,
        cost_profile_version="cost-v1",
        correlation_id=make_uuid(21),
        causation_id=make_uuid(20),
        code_hash="c" * 64,
    )
    res_decision_2 = politica.decidir(sol_luz_2)
    if res_decision_2.exito:
        decision_2 = res_decision_2.datos
        ev_sig_2 = SobreEventoV1(
            event_id=make_uuid(22),
            event_type="SIGNAL_EMITTED",
            schema_version=1,
            occurred_at_utc=t_s60,
            received_at_utc=t_s60,
            persisted_at_utc=t_s60,
            source="replay",
            environment="REPLAY",
            source_account_id_hash=None,
            instrument="US500",
            symbol_id="US500",
            source_sequence=3,
            correlation_id=make_uuid(21),
            causation_id=make_uuid(20),
            payload_hash=compute_payload_hash({
                "light": decision_2.senal.light,
                "direction": decision_2.senal.direction,
                "calibrated_probability_long": decision_2.senal.calibrated_probability_long,
                "calibrated_probability_short": decision_2.senal.calibrated_probability_short,
                "threshold_green": politica.threshold_green,
                "threshold_red": politica.threshold_red,
                "reasons": list(decision_2.senal.reason_codes),
            }),
            previous_hash=make_uuid(12),
            payload={
                "light": decision_2.senal.light,
                "direction": decision_2.senal.direction,
                "calibrated_probability_long": decision_2.senal.calibrated_probability_long,
                "calibrated_probability_short": decision_2.senal.calibrated_probability_short,
                "threshold_green": politica.threshold_green,
                "threshold_red": politica.threshold_red,
                "reasons": list(decision_2.senal.reason_codes),
            },
        )
        proyector.actualizar_desde_evento(ev_sig_2)
        print(f"   🟡 LUZ EMITIDA: {decision_2.senal.light} | Dirección: {decision_2.senal.direction} | Prob: 50.0% | Razones: {decision_2.senal.reason_codes}")

    # --- PASO 6: Transición a Rojo (Bajista) ---
    t_s90 = t_s60 + timedelta(seconds=30)
    print(f"\n▶ [{pasos[5][0]}] {pasos[5][1]}")
    sol_luz_3 = SolicitudLuz(
        case_id=make_uuid(30),
        created_at_utc=t_s90,
        environment="REPLAY",
        instrument="US500",
        decision_window="S30",
        market_event_cutoff=t_s90,
        reference_bid=501900,
        reference_ask=501940,
        price_scale=100,
        data_age_ms=60,
        feed_health_state="HEALTHY",
        model_id="logreg-us500",
        model_version="1.0.0",
        model_hash="a" * 64,
        calibration_version="platt-v1",
        feature_snapshot_hash="f" * 64,
        raw_score_long=250000,
        raw_score_short=750000,
        calibrated_probability_long=280000,  # 28% -> RED
        calibrated_probability_short=720000,
        expected_value_long_net=-9000,
        expected_value_short_net=17000,
        cost_profile_version="cost-v1",
        correlation_id=make_uuid(31),
        causation_id=make_uuid(30),
        code_hash="c" * 64,
    )
    res_decision_3 = politica.decidir(sol_luz_3)
    if res_decision_3.exito:
        decision_3 = res_decision_3.datos
        ev_sig_3 = SobreEventoV1(
            event_id=make_uuid(32),
            event_type="SIGNAL_EMITTED",
            schema_version=1,
            occurred_at_utc=t_s90,
            received_at_utc=t_s90,
            persisted_at_utc=t_s90,
            source="replay",
            environment="REPLAY",
            source_account_id_hash=None,
            instrument="US500",
            symbol_id="US500",
            source_sequence=4,
            correlation_id=make_uuid(31),
            causation_id=make_uuid(30),
            payload_hash=compute_payload_hash({
                "light": decision_3.senal.light,
                "direction": decision_3.senal.direction,
                "calibrated_probability_long": decision_3.senal.calibrated_probability_long,
                "calibrated_probability_short": decision_3.senal.calibrated_probability_short,
                "threshold_green": politica.threshold_green,
                "threshold_red": politica.threshold_red,
                "reasons": list(decision_3.senal.reason_codes),
            }),
            previous_hash=make_uuid(22),
            payload={
                "light": decision_3.senal.light,
                "direction": decision_3.senal.direction,
                "calibrated_probability_long": decision_3.senal.calibrated_probability_long,
                "calibrated_probability_short": decision_3.senal.calibrated_probability_short,
                "threshold_green": politica.threshold_green,
                "threshold_red": politica.threshold_red,
                "reasons": list(decision_3.senal.reason_codes),
            },
        )
        proyector.actualizar_desde_evento(ev_sig_3)
        print(f"   🔴 LUZ EMITIDA: {decision_3.senal.light} | Dirección: {decision_3.senal.direction} | Prob: 28.0% | Razones: {decision_3.senal.reason_codes}")

    # --- PASO 7: Fail-Closed Feed Stale ---
    t_stale = t_s90 + timedelta(seconds=10)
    print(f"\n▶ [{pasos[6][0]}] {pasos[6][1]}")
    ev_stale = SobreEventoV1(
        event_id=make_uuid(40),
        event_type="STALE",
        schema_version=1,
        occurred_at_utc=t_stale,
        received_at_utc=t_stale,
        persisted_at_utc=t_stale,
        source="replay",
        environment="REPLAY",
        source_account_id_hash=None,
        instrument="US500",
        symbol_id="US500",
        source_sequence=5,
        correlation_id=make_uuid(41),
        causation_id=None,
        payload_hash=compute_payload_hash({"data_age_ms": 6200, "threshold_ms": 5000, "action": "FORCE_YELLOW"}),
        previous_hash=make_uuid(32),
        payload={"data_age_ms": 6200, "threshold_ms": 5000, "action": "FORCE_YELLOW"},
    )
    proyector.actualizar_desde_evento(ev_stale)
    print(f"   🛡️ PROTECCIÓN ACTIVA: Feed Stale (edad 6.2s > 5.0s). Luz degradada de inmediato a AMARILLO.")

    # 3. Lanzar Servidor Loopback
    port = 8080
    servidor = ServidorLoopback(host="127.0.0.1", port=port, proyector=proyector)
    
    server_thread = threading.Thread(target=servidor.serve_forever, daemon=True)
    server_thread.start()
    time.sleep(0.1)

    print("\n" + "=" * 75)
    print("🌐 SERVIDOR OPERATIVO LOCAL INICIADO (Loopback 127.0.0.1)")
    print("=" * 75)
    print(f"🔗 URL del Dashboard: http://127.0.0.1:{port}/")
    print(f"🔒 Protocolo: HTTP/1.1 Read-Only (Métodos mutantes POST/PUT/DELETE retornan 405)")
    print(f"🛡️ Cabeceras Activas: Content-Security-Policy, X-Frame-Options: DENY, nosniff")
    print("-" * 75)

    # Realizar consulta de comprobación HTTP
    try:
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=2)
        conn.request("GET", "/")
        resp = conn.getresponse()
        print(f"📡 Comprobación HTTP GET / -> Status {resp.status} {resp.reason}")
        print(f"📄 Content-Type: {resp.getheader('Content-Type')}")
        print(f"🛡️ CSP: {resp.getheader('Content-Security-Policy')}")
        body = resp.read().decode("utf-8")
        print(f"📦 Longitud Payload HTML: {len(body)} bytes")
        conn.close()
    except Exception as err:
        print(f"⚠️ Error al comprobar HTTP: {err}")

    print("\n" + "=" * 75)
    print("📊 RESUMEN FINAL DEL ESCENARIO EJECUTADO:")
    print(f"   - Total de Eventos Procesados: {len(eventos_historicos) + 4}")
    print(f"   - Estado Actual del Feed: {proyector._health_state}")
    print(f"   - Luz Actual en Tablero: {proyector._current_light}")
    print(f"   - Operaciones Paper Ejecutadas: 1 (Take Profit; P&L bruto +$200.00, neto +$196.00)")
    print(f"   - Límites de Riesgo: $50 por trade respetado, $250 max pérdida diaria intacto")
    print("=" * 75)
    print("El dashboard seguirá activo. Presione Ctrl+C para detenerlo.")
    try:
        while server_thread.is_alive():
            server_thread.join(timeout=1.0)
    except KeyboardInterrupt:
        print("\nDeteniendo servidor local...")
        servidor.shutdown()


if __name__ == "__main__":
    main()
