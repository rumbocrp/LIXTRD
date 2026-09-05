"""Pruebas del Simulador Paper (SPEC-001 §5.3, §6.6, CA-11, CA-12, CA-15, CA-16)."""

from datetime import datetime, timedelta, timezone
import unittest

from sistema_luces.domain.event import QuoteTickPayloadV1
from sistema_luces.domain.signal import SenalV1, validar_senal
from sistema_luces.domain.simulation import validar_simulacion
from sistema_luces.risk.engine import MotorRiesgo
from sistema_luces.simulation.paper import SimuladorPapel


def _crear_senal_prueba(
    signal_id: str = "00000000-0000-0000-0000-000000000001",
    light: str = "GREEN",
    direction: str = "LONG",
    valid_until_utc: datetime | None = None,
    created_at_utc: datetime | None = None,
) -> SenalV1:
    t0 = created_at_utc or datetime(2026, 8, 29, 14, 30, 0, tzinfo=timezone.utc)
    v_until = valid_until_utc or (t0 + timedelta(seconds=30))
    return SenalV1(
        signal_id=signal_id,
        case_id="00000000-0000-0000-0000-000000000100",
        created_at_utc=t0,
        valid_until_utc=v_until,
        environment="REPLAY",
        instrument="US500",
        decision_window="S30",
        market_event_cutoff=t0,
        reference_bid=500000,
        reference_ask=500040,
        price_scale=100,
        data_age_ms=100,
        direction=direction,  # type: ignore[arg-type]
        light=light,  # type: ignore[arg-type]
        reason_codes=("MODEL_EDGE_LONG",) if light == "GREEN" else ("LOW_CONFIDENCE_MONITOR",),
        health_state="HEALTHY",
        safety_forced=False,
        strategy_id="strat-v1",
        strategy_version="1.0.0",
        feature_set_version="features-v1",
        feature_snapshot_hash="a" * 64,
        model_id="logreg-v1",
        model_version="1.0.0",
        model_hash="b" * 64,
        calibration_version="calib-v1",
        policy_version="policy-v1",
        raw_score_long=750000,
        raw_score_short=250000,
        calibrated_probability_long=700000,
        calibrated_probability_short=300000,
        expected_value_long_net=15000,
        expected_value_short_net=-5000,
        cost_profile_version="cost-v1",
        correlation_id=signal_id,
        causation_id="00000000-0000-0000-0000-000000000100",
        code_hash="c" * 64,
        schema_version=1,
    )


class TestSimuladorPapel(unittest.TestCase):
    """Verifica proposición, apertura paper, avance de ticks, cálculo de P&L y cierres."""

    def setUp(self) -> None:
        self.t0 = datetime(2026, 8, 29, 14, 30, 0, tzinfo=timezone.utc)
        self.motor_riesgo = MotorRiesgo()
        self.simulador = SimuladorPapel(motor_riesgo=self.motor_riesgo)

    def test_proposicion_y_apertura_simulacion_long(self) -> None:
        senal = _crear_senal_prueba(light="GREEN", direction="LONG")
        res = self.simulador.proponer_y_abrir(
            senal=senal,
            current_bid=500000,
            current_ask=500040,
            now_utc=self.t0 + timedelta(seconds=5),
        )
        self.assertTrue(res.exito)
        sim = res.datos
        self.assertEqual("OPEN_SIMULATED", sim.status)
        self.assertEqual("LONG", sim.direction)
        self.assertEqual(500040, sim.planned_entry)
        self.assertEqual(500040, sim.fill_entry)
        self.assertEqual(500040 - 500, sim.stop)
        self.assertEqual(500040 + 2000, sim.target)

        val_res = validar_simulacion(sim)
        self.assertTrue(val_res.exito)

    def test_senal_expirada_rechaza_simulacion_ca11(self) -> None:
        senal = _crear_senal_prueba(
            light="GREEN",
            direction="LONG",
            created_at_utc=self.t0,
            valid_until_utc=self.t0 + timedelta(seconds=30),
        )
        # Intento de proponer a los 35 segundos (> 30s)
        res = self.simulador.proponer_y_abrir(
            senal=senal,
            current_bid=500000,
            current_ask=500040,
            now_utc=self.t0 + timedelta(seconds=35),
        )
        self.assertFalse(res.exito)
        self.assertEqual("SIGNAL_EXPIRED", res.error.codigo)

    def test_senal_amarilla_monitor_rechaza_simulacion_ca12(self) -> None:
        senal = _crear_senal_prueba(
            light="YELLOW",
            direction="MONITOR",
        )
        res = self.simulador.proponer_y_abrir(
            senal=senal,
            current_bid=500000,
            current_ask=500040,
            now_utc=self.t0 + timedelta(seconds=5),
        )
        self.assertFalse(res.exito)
        self.assertEqual("VALIDATION_ERROR", res.error.codigo)

    def test_avance_tick_cierre_por_target_y_calculo_pnl(self) -> None:
        senal = _crear_senal_prueba(light="GREEN", direction="LONG")
        res_open = self.simulador.proponer_y_abrir(
            senal=senal,
            current_bid=500000,
            current_ask=500040,
            now_utc=self.t0 + timedelta(seconds=5),
        )
        self.assertTrue(res_open.exito)
        sim_id = res_open.datos.simulation_id

        # Tick 1: Inside barrier
        tick1 = QuoteTickPayloadV1(
            ask=501000,
            bid=500960,
            price_scale=100,
            bid_size=10,
            ask_size=10,
            source_timestamp_utc=self.t0 + timedelta(minutes=1),
            source_sequence=1,
        )
        res_tick1 = self.simulador.avanzar_tick(sim_id, tick1, self.t0 + timedelta(minutes=1))
        self.assertTrue(res_tick1.exito)
        self.assertEqual("OPEN_SIMULATED", res_tick1.datos.status)

        # Tick 2: Hits target (entry=500040, target=502040, bid=502100)
        tick2 = QuoteTickPayloadV1(
            ask=502140,
            bid=502100,
            price_scale=100,
            bid_size=10,
            ask_size=10,
            source_timestamp_utc=self.t0 + timedelta(minutes=2),
            source_sequence=2,
        )
        res_tick2 = self.simulador.avanzar_tick(sim_id, tick2, self.t0 + timedelta(minutes=2))
        self.assertTrue(res_tick2.exito)
        sim_closed = res_tick2.datos

        self.assertEqual("CLOSED_SIMULATED", sim_closed.status)
        self.assertEqual("target", sim_closed.exit_reason)
        self.assertIsNotNone(sim_closed.fill_exit)
        self.assertIsNotNone(sim_closed.gross_pnl)
        self.assertIsNotNone(sim_closed.net_pnl)
        self.assertGreater(sim_closed.net_pnl, 0)  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
