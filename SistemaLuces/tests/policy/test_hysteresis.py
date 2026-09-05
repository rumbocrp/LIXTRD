"""Pruebas de la máquina de estados e histéresis de luces (SPEC-001 §6.4, CA-8)."""

from datetime import datetime, timezone
import unittest

from sistema_luces.domain.state import es_transicion_valida
from sistema_luces.policy.hysteresis import HisteresisLuces


class TestHisteresisLuces(unittest.TestCase):
    """Verifica transiciones, histéresis y la prohibición estricta de saltos directos GREEN <-> RED."""

    def setUp(self) -> None:
        self.t0 = datetime(2026, 8, 29, 14, 30, 0, tzinfo=timezone.utc)
        self.histeresis = HisteresisLuces(
            threshold_green=650_000,
            threshold_red=350_000,
            initial_light="YELLOW",
        )

    def test_estado_inicial_es_yellow(self) -> None:
        self.assertEqual("YELLOW", self.histeresis.luz_actual)

    def test_transicion_yellow_a_green_permitida(self) -> None:
        res = self.histeresis.transicionar("GREEN", "HEALTHY", self.t0, "corr-1")
        self.assertTrue(res.exito)
        self.assertEqual("GREEN", self.histeresis.luz_actual)

    def test_transicion_yellow_a_red_permitida(self) -> None:
        res = self.histeresis.transicionar("RED", "HEALTHY", self.t0, "corr-2")
        self.assertTrue(res.exito)
        self.assertEqual("RED", self.histeresis.luz_actual)

    def test_salto_directo_green_a_red_prohibido_ca8(self) -> None:
        # Poner en GREEN primero
        res_g = self.histeresis.transicionar("GREEN", "HEALTHY", self.t0, "corr-g")
        self.assertTrue(res_g.exito)
        self.assertEqual("GREEN", self.histeresis.luz_actual)

        # Intento directo a RED
        res_r = self.histeresis.transicionar("RED", "HEALTHY", self.t0, "corr-r")
        self.assertFalse(res_r.exito)
        self.assertEqual("VALIDATION_ERROR", res_r.error.codigo)
        self.assertEqual("GREEN", self.histeresis.luz_actual)

    def test_salto_directo_red_a_green_prohibido_ca8(self) -> None:
        # Poner en RED primero
        res_r = self.histeresis.transicionar("RED", "HEALTHY", self.t0, "corr-r")
        self.assertTrue(res_r.exito)
        self.assertEqual("RED", self.histeresis.luz_actual)

        # Intento directo a GREEN
        res_g = self.histeresis.transicionar("GREEN", "HEALTHY", self.t0, "corr-g")
        self.assertFalse(res_g.exito)
        self.assertEqual("VALIDATION_ERROR", res_g.error.codigo)
        self.assertEqual("RED", self.histeresis.luz_actual)

    def test_paso_por_yellow_intermedio_permite_cambio_de_sesgo(self) -> None:
        # GREEN -> YELLOW -> RED
        self.assertTrue(self.histeresis.transicionar("GREEN", "HEALTHY", self.t0, "c1").exito)
        self.assertTrue(self.histeresis.transicionar("YELLOW", "HEALTHY", self.t0, "c2").exito)
        self.assertEqual("YELLOW", self.histeresis.luz_actual)
        self.assertTrue(self.histeresis.transicionar("RED", "HEALTHY", self.t0, "c3").exito)
        self.assertEqual("RED", self.histeresis.luz_actual)

    def test_feed_degradado_fuerza_yellow(self) -> None:
        self.assertTrue(self.histeresis.transicionar("GREEN", "HEALTHY", self.t0, "c1").exito)
        # Feed pasa a STALE
        res_stale = self.histeresis.transicionar("GREEN", "STALE", self.t0, "c2")
        self.assertTrue(res_stale.exito)
        self.assertEqual("YELLOW", self.histeresis.luz_actual)


if __name__ == "__main__":
    unittest.main()
