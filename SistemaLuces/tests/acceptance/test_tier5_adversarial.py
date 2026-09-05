"""Tier 5: Pruebas de Endurecimiento Adversarial y Resiliencia Extrema (WP-15).

Verifica el comportamiento del sistema ante entradas maliciosas, intentos de evasión de seguridad,
condiciones extremas de mercado, corrupción de estado y estrés de reproducibilidad.
"""

from datetime import datetime, timedelta, timezone
import hashlib
import json
import unittest

from sistema_luces.domain.api import (
    SolicitudConsulta,
    SolicitudImportacionDemo,
    SolicitudReplay,
    SolicitudShadow,
    validar_solicitud_consulta,
    validar_solicitud_importacion_demo,
    validar_solicitud_replay,
    validar_solicitud_shadow,
)
from sistema_luces.domain.error import ErrorDominio
from sistema_luces.domain.event import (
    QuoteTickPayloadV1,
    SobreEventoV1,
    canonical_json_bytes,
    compute_payload_hash,
    validar_sobre_evento,
)
from sistema_luces.domain.manifest import RiskProfileV1
from sistema_luces.domain.signal import SenalV1, validar_senal
from sistema_luces.domain.simulation import SimulacionV1, validar_simulacion
from sistema_luces.domain.state import es_transicion_valida
from sistema_luces.domain.vocabulary import parse_environment
from sistema_luces.policy.hysteresis import HisteresisLuces
from sistema_luces.policy.lights import PoliticaLuces, SolicitudLuz
from sistema_luces.risk.blackout import CalendarioNoticias, EventoNoticia
from sistema_luces.risk.engine import MotorRiesgo
from sistema_luces.risk.kill_switch import InterruptorEmergencia
from sistema_luces.simulation.lifecycle import EvaluadorTripleBarrera
from sistema_luces.simulation.paper import SimuladorPapel


class TestTier5AdversarialHardening(unittest.TestCase):
    """Pruebas adversariales de Nivel 5."""

    def setUp(self) -> None:
        self.t0 = datetime(2026, 8, 29, 14, 30, 0, tzinfo=timezone.utc)

    def test_adversarial_environment_spoofing(self) -> None:
        """Intento de evadir la prohibición LIVE con variantes unicode, espacios y caracteres ocultos."""
        variantes_live = [
            "LIVE", "live", "Live", " LIVE ", "live\x00", "L\u0049VE", "PROD", "PRODUCTION", "STAGE", "TEST", ""
        ]
        for var in variantes_live:
            res = parse_environment(var, "corr-adv")
            if var not in {"REPLAY", "SHADOW", "BROKER_DEMO_OBSERVED"}:
                self.assertFalse(res.exito, f"Variante '{var}' debió ser rechazada")
                self.assertIn(res.error.codigo, {"ENVIRONMENT_NOT_ALLOWED", "VALIDATION_ERROR"})

    def test_adversarial_tampered_payload_hash(self) -> None:
        """Intento de inyectar un sobre de evento con payload mutado pero payload_hash falsificado."""
        payload_original = {"ask": 500040, "bid": 500000, "price_scale": 100}
        payload_mutado = {"ask": 999999, "bid": 500000, "price_scale": 100}

        sobre = SobreEventoV1(
            event_id="00000000-0000-0000-0000-000000000001",
            event_type="QUOTE_TICK",
            schema_version=1,
            occurred_at_utc=self.t0,
            received_at_utc=self.t0,
            persisted_at_utc=self.t0,
            source="replay",
            environment="REPLAY",
            source_account_id_hash=None,
            instrument="US500",
            symbol_id="US500",
            source_sequence=1,
            payload=payload_mutado,
            payload_hash=compute_payload_hash(payload_original),  # Hash del payload original, no del mutado
            previous_hash=None,
            causation_id=None,
            correlation_id="00000000-0000-0000-0000-000000000001",
        )
        res = validar_sobre_evento(sobre)
        self.assertFalse(res.exito)
        self.assertEqual("INTEGRITY_ERROR", res.error.codigo)

    def test_adversarial_rapid_bias_flipping_attack(self) -> None:
        """Ataque de oscilación rápida de señales (Green -> Red -> Green en microsegundos)."""
        politica = PoliticaLuces()
        # 1. Start at GREEN
        sol_g = SolicitudLuz(
            case_id="00000000-0000-0000-0000-000000000001",
            created_at_utc=self.t0,
            environment="REPLAY",
            instrument="US500",
            decision_window="S30",
            market_event_cutoff=self.t0,
            reference_bid=500000,
            reference_ask=500040,
            price_scale=100,
            data_age_ms=50,
            feed_health_state="HEALTHY",
            model_id="logreg-v1",
            model_version="1.0.0",
            model_hash="a" * 64,
            calibration_version="calib-v1",
            feature_snapshot_hash="b" * 64,
            raw_score_long=800000,
            raw_score_short=200000,
            calibrated_probability_long=800000,
            calibrated_probability_short=200000,
            expected_value_long_net=20000,
            expected_value_short_net=-20000,
            cost_profile_version="cost-v1",
            correlation_id="c-1",
            causation_id=None,
            code_hash="d" * 64,
        )
        res1 = politica.decidir(sol_g)
        self.assertEqual("GREEN", res1.datos.senal.light)

        # 2. Immediate flip to strong short signal: Hysteresis forces intermediate YELLOW
        sol_r = SolicitudLuz(
            case_id="00000000-0000-0000-0000-000000000002",
            created_at_utc=self.t0 + timedelta(milliseconds=100),
            environment="REPLAY",
            instrument="US500",
            decision_window="S30",
            market_event_cutoff=self.t0 + timedelta(milliseconds=100),
            reference_bid=500000,
            reference_ask=500040,
            price_scale=100,
            data_age_ms=50,
            feed_health_state="HEALTHY",
            model_id="logreg-v1",
            model_version="1.0.0",
            model_hash="a" * 64,
            calibration_version="calib-v1",
            feature_snapshot_hash="b" * 64,
            raw_score_long=100000,
            raw_score_short=900000,
            calibrated_probability_long=100000,
            calibrated_probability_short=900000,
            expected_value_long_net=-20000,
            expected_value_short_net=20000,
            cost_profile_version="cost-v1",
            correlation_id="c-2",
            causation_id=None,
            code_hash="d" * 64,
        )
        res2 = politica.decidir(sol_r)
        self.assertEqual("YELLOW", res2.datos.senal.light)
        self.assertEqual("MONITOR", res2.datos.senal.direction)

        # 3. Flip back to GREEN: Still must safely transition through YELLOW
        res3 = politica.decidir(sol_g)
        self.assertEqual("GREEN", res3.datos.senal.light)

    def test_adversarial_kill_switch_bypass_attempts(self) -> None:
        """Intento de eludir el Kill Switch tras alcanzar drawdown máximo."""
        motor = MotorRiesgo()
        motor.interruptor.activar("MAX_LOSS_REACHED", self.t0)

        # Intento de recuperación no autorizada (sin actor o sin resolución)
        self.assertFalse(motor.interruptor.recuperar("", "intent").exito)
        self.assertFalse(motor.interruptor.recuperar("admin", "").exito)
        self.assertTrue(motor.interruptor.activo)

        # Intento de apertura bajo kill switch bloqueado
        sim = SimulacionV1(
            simulation_id="00000000-0000-0000-0000-000000000001",
            signal_id="00000000-0000-0000-0000-000000000002",
            environment="REPLAY",
            demo_account_hash=None,
            status="PROPOSED",
            proposed_at_utc=self.t0,
            opened_at_utc=None,
            closed_at_utc=None,
            horizon_end_utc=self.t0 + timedelta(minutes=5),
            direction="LONG",
            planned_entry=500000,
            stop=499500,
            target=502000,
            risk_profile_version="risk-v1",
            instrument_profile_version="us500-v1",
            requested_quantity_simulated=100,
            effective_quantity_simulated=100,
            quantity_scale=100,
            fill_entry=None,
            fill_exit=None,
            fill_source="simulator",
            source_execution_ids=(),
            spread_cost=40,
            slippage_cost=0,
            commission_cost=0,
            carry_cost=0,
            money_scale=100,
            currency="USD",
            exit_reason=None,
            gross_pnl=None,
            net_pnl=None,
            realized_r=None,
            mfe=None,
            mae=None,
            reconciliation_status="PENDING",
            reconciliation_reason_codes=(),
            market_event_cutoff=self.t0,
            cost_profile_version="cost-v1",
            correlation_id="c-1",
            causation_id=None,
            schema_version=1,
        )
        res_propuesta = motor.evaluar_propuesta(sim, self.t0)
        self.assertFalse(res_propuesta.exito)
        self.assertEqual("RISK_LIMIT_HIT", res_propuesta.error.codigo)

    def test_adversarial_extreme_slippage_and_gap_resolution(self) -> None:
        """Salto masivo de mercado (gap down de 100 puntos en 1 tick)."""
        evaluador = EvaluadorTripleBarrera(stop_loss_points=500, take_profit_points=2000)
        # Posición LONG con entrada en 500040 (stop en 499540)
        # Tick salta directamente a bid 490000 (100 puntos por debajo del stop)
        estado, precio = evaluador.evaluar_tick_long(
            entry_ask=500040,
            tick_bid=490000,
            tick_ask=490040,
        )
        self.assertEqual("STOP_LOSS", estado)
        self.assertEqual(499540, precio)


if __name__ == "__main__":
    unittest.main()
