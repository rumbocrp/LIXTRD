"""Pruebas del Evaluador de Triple-Barrera y Ciclo de Vida (SPEC-001 §7.1, CA-13, CA-14)."""

import unittest

from sistema_luces.simulation.lifecycle import EvaluadorTripleBarrera


class TestEvaluadorTripleBarrera(unittest.TestCase):
    """Verifica reglas ejecutables de bid/ask, STOP_FIRST en ambigüedad y horizontes."""

    def setUp(self) -> None:
        self.evaluador = EvaluadorTripleBarrera(stop_loss_points=500, take_profit_points=2000)

    def test_long_take_profit_alcanzado_en_bid(self) -> None:
        # Entrada ask=500100 -> stop=499600 (bid), target=502100 (bid)
        estado, precio = self.evaluador.evaluar_tick_long(
            entry_ask=500100,
            tick_bid=502150,
            tick_ask=502190,
        )
        self.assertEqual("TAKE_PROFIT", estado)
        self.assertEqual(502100, precio)

    def test_long_stop_loss_alcanzado_en_bid(self) -> None:
        estado, precio = self.evaluador.evaluar_tick_long(
            entry_ask=500100,
            tick_bid=499550,
            tick_ask=499590,
        )
        self.assertEqual("STOP_LOSS", estado)
        self.assertEqual(499600, precio)

    def test_long_ambiguo_resuelve_stop_first_ca14(self) -> None:
        # Tick abarca tanto stop como target
        estado, precio = self.evaluador.evaluar_tick_long(
            entry_ask=500100,
            tick_bid=499500,
            tick_ask=502500,
        )
        self.assertEqual("AMBIGUOUS_STOP_FIRST", estado)
        self.assertEqual(499600, precio)

    def test_short_take_profit_alcanzado_en_ask(self) -> None:
        # Entrada bid=500000 -> stop=500500 (ask), target=498000 (ask)
        estado, precio = self.evaluador.evaluar_tick_short(
            entry_bid=500000,
            tick_bid=497950,
            tick_ask=497990,
        )
        self.assertEqual("TAKE_PROFIT", estado)
        self.assertEqual(498000, precio)

    def test_short_stop_loss_alcanzado_en_ask(self) -> None:
        estado, precio = self.evaluador.evaluar_tick_short(
            entry_bid=500000,
            tick_bid=500520,
            tick_ask=500550,
        )
        self.assertEqual("STOP_LOSS", estado)
        self.assertEqual(500500, precio)

    def test_short_ambiguo_resuelve_stop_first_ca14(self) -> None:
        estado, precio = self.evaluador.evaluar_tick_short(
            entry_bid=500000,
            tick_bid=497500,
            tick_ask=501000,
        )
        self.assertEqual("AMBIGUOUS_STOP_FIRST", estado)
        self.assertEqual(500500, precio)


if __name__ == "__main__":
    unittest.main()
