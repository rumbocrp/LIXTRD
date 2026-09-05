"""Pruebas del Kill Switch e Interruptor de Emergencia (SPEC-001 §8, CA-18)."""

from datetime import datetime, timezone
import unittest

from sistema_luces.risk.kill_switch import InterruptorEmergencia


class TestInterruptorEmergencia(unittest.TestCase):
    """Verifica activación fail-closed y procedimiento de recuperación verificado."""

    def setUp(self) -> None:
        self.t0 = datetime(2026, 8, 29, 14, 30, 0, tzinfo=timezone.utc)
        self.ks = InterruptorEmergencia()

    def test_inicia_desactivado(self) -> None:
        self.assertFalse(self.ks.activo)
        self.assertIsNone(self.ks.motivo)

    def test_activacion_fail_closed(self) -> None:
        self.ks.activar("DAILY_DRAWDOWN_LIMIT_EXCEEDED", self.t0)
        self.assertTrue(self.ks.activo)
        self.assertEqual("DAILY_DRAWDOWN_LIMIT_EXCEEDED", self.ks.motivo)

    def test_recuperacion_exitosa_con_actor_y_resolucion(self) -> None:
        self.ks.activar("TECHNICAL_DRIFT", self.t0)
        res = self.ks.recuperar(actor="lead-risk", resolucion="DRIFT_RESOLVED_AFTER_RETRAIN")
        self.assertTrue(res.exito)
        self.assertFalse(self.ks.activo)
        self.assertIsNone(self.ks.motivo)

    def test_recuperacion_fallida_sin_actor_o_resolucion(self) -> None:
        self.ks.activar("FEED_CORRUPTION", self.t0)
        res_vacio = self.ks.recuperar(actor="", resolucion="TEST")
        self.assertFalse(res_vacio.exito)
        self.assertEqual("VALIDATION_ERROR", res_vacio.error.codigo)
        self.assertTrue(self.ks.activo)


if __name__ == "__main__":
    unittest.main()
