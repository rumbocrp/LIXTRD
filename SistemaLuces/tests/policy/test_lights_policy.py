"""Pruebas de la Política de Luces (SPEC-001 §6.4, §6.5, CA-8, CA-11, CA-12, CA-27)."""

from datetime import datetime, timedelta, timezone
import unittest

from sistema_luces.domain.signal import validar_senal
from sistema_luces.domain.state import validar_transicion_estado
from sistema_luces.policy.lights import PoliticaLuces, SolicitudLuz


class TestPoliticaLuces(unittest.TestCase):
    """Verifica la generación de señales, expiración en 30s, abstención amarilla y no-cuota."""

    def setUp(self) -> None:
        self.t0 = datetime(2026, 8, 29, 14, 30, 0, tzinfo=timezone.utc)
        self.politica = PoliticaLuces(
            policy_version="policy-us500-v1",
            strategy_id="strat-v1",
            strategy_version="1.0.0",
            feature_set_version="features-v1",
            threshold_green=650_000,
            threshold_red=350_000,
        )

    def _crear_solicitud(
        self,
        calibrated_prob_long: int = 700_000,
        calibrated_prob_short: int | None = None,
        feed_health: str = "HEALTHY",
        reference_bid: int = 500000,
        reference_ask: int = 500040,
        time_utc: datetime | None = None,
    ) -> SolicitudLuz:
        t = time_utc or self.t0
        if calibrated_prob_short is None:
            calibrated_prob_short = 1_000_000 - calibrated_prob_long
        return SolicitudLuz(
            case_id="00000000-0000-0000-0000-000000000001",
            created_at_utc=t,
            environment="REPLAY",
            instrument="US500",
            decision_window="S30",
            market_event_cutoff=t,
            reference_bid=reference_bid,
            reference_ask=reference_ask,
            price_scale=100,
            data_age_ms=100,
            feed_health_state=feed_health,
            model_id="logreg-v1",
            model_version="1.0.0",
            model_hash="a" * 64,
            calibration_version="calib-v1",
            feature_snapshot_hash="b" * 64,
            raw_score_long=750_000,
            raw_score_short=250_000,
            calibrated_probability_long=calibrated_prob_long,
            calibrated_probability_short=calibrated_prob_short,
            expected_value_long_net=15000,
            expected_value_short_net=-5000,
            cost_profile_version="cost-v1",
            correlation_id="00000000-0000-0000-0000-000000000002",
            causation_id="00000000-0000-0000-0000-000000000001",
            code_hash="c" * 64,
        )

    def test_green_signal_generation(self) -> None:
        sol = self._crear_solicitud(calibrated_prob_long=700_000)
        res = self.politica.decidir(sol)
        self.assertTrue(res.exito)
        decision = res.datos
        senal = decision.senal
        transicion = decision.transicion

        self.assertEqual("GREEN", senal.light)
        self.assertEqual("LONG", senal.direction)
        self.assertEqual(sol.created_at_utc + timedelta(seconds=30), senal.valid_until_utc)
        self.assertIn("MODEL_EDGE_LONG", senal.reason_codes)

        # Validar dominio
        val_sig = validar_senal(senal)
        self.assertTrue(val_sig.exito)
        val_trans = validar_transicion_estado(transicion)
        self.assertTrue(val_trans.exito)

    def test_red_signal_generation(self) -> None:
        sol = self._crear_solicitud(calibrated_prob_long=300_000)
        res = self.politica.decidir(sol)
        self.assertTrue(res.exito)
        decision = res.datos
        senal = decision.senal

        self.assertEqual("RED", senal.light)
        self.assertEqual("SHORT", senal.direction)
        self.assertEqual(sol.created_at_utc + timedelta(seconds=30), senal.valid_until_utc)
        self.assertIn("MODEL_EDGE_SHORT", senal.reason_codes)

        val_sig = validar_senal(senal)
        self.assertTrue(val_sig.exito)

    def test_yellow_abstention_on_neutral_probability(self) -> None:
        sol = self._crear_solicitud(calibrated_prob_long=500_000)
        res = self.politica.decidir(sol)
        self.assertTrue(res.exito)
        senal = res.datos.senal

        self.assertEqual("YELLOW", senal.light)
        self.assertEqual("MONITOR", senal.direction)
        self.assertIn("LOW_CONFIDENCE_MONITOR", senal.reason_codes)

    def test_degraded_feed_forces_yellow_ca7(self) -> None:
        for bad_feed in ["STALE", "GAPPED", "RECONNECTING", "STOPPED"]:
            sol = self._crear_solicitud(calibrated_prob_long=800_000, feed_health=bad_feed)
            res = self.politica.decidir(sol)
            self.assertTrue(res.exito)
            senal = res.datos.senal

            self.assertEqual("YELLOW", senal.light)
            self.assertEqual("MONITOR", senal.direction)
            self.assertTrue(senal.safety_forced)
            self.assertIn("FEED_DEGRADED_YELLOW", senal.reason_codes)

    def test_direct_transition_reversal_passes_through_intermediate_yellow_ca8(self) -> None:
        # 1. First decision: GREEN
        sol1 = self._crear_solicitud(calibrated_prob_long=750_000, time_utc=self.t0)
        res1 = self.politica.decidir(sol1)
        self.assertTrue(res1.exito)
        self.assertEqual("GREEN", res1.datos.senal.light)

        # 2. Immediate jump to RED: Policy must safely drop to YELLOW first
        sol2 = self._crear_solicitud(calibrated_prob_long=200_000, time_utc=self.t0 + timedelta(seconds=30))
        res2 = self.politica.decidir(sol2)
        self.assertTrue(res2.exito)
        self.assertEqual("YELLOW", res2.datos.senal.light)
        self.assertEqual("MONITOR", res2.datos.senal.direction)
        self.assertIn("HYSTERESIS_INTERMEDIATE_YELLOW", res2.datos.senal.reason_codes)

        # 3. Next step from YELLOW to RED: Now allowed
        sol3 = self._crear_solicitud(calibrated_prob_long=200_000, time_utc=self.t0 + timedelta(seconds=60))
        res3 = self.politica.decidir(sol3)
        self.assertTrue(res3.exito)
        self.assertEqual("RED", res3.datos.senal.light)
        self.assertEqual("SHORT", res3.datos.senal.direction)

    def test_daily_signal_target_non_quota_invariance_ca27(self) -> None:
        # Decision depends strictly on data and policy, not daily count
        for i in range(20):
            t = self.t0 + timedelta(minutes=i)
            sol = self._crear_solicitud(calibrated_prob_long=700_000, time_utc=t)
            res = self.politica.decidir(sol)
            self.assertTrue(res.exito)
            self.assertEqual("GREEN", res.datos.senal.light)
            self.assertEqual("LONG", res.datos.senal.direction)


if __name__ == "__main__":
    unittest.main()
