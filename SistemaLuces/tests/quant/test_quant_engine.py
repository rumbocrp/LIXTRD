import unittest

from tests.conftest import REPO_ROOT, SRC_ROOT

from sistema_luces.quant.cross_asset import MotorMultiActivo
from sistema_luces.quant.kalman import DynamicKalmanFilter
from sistema_luces.quant.order_flow import OrderFlowEngine
from sistema_luces.quant.traffic_light import evaluar_sistema_luces_cuantitativo


class TestMotorCuantitativo(unittest.TestCase):
    """Verifica las ecuaciones de Kalman, Order Flow y la precisión direccional > 70%."""

    def test_dynamic_kalman_filter_actualiza_beta_y_z_score(self) -> None:
        kf = DynamicKalmanFilter(delta=1e-4, R=1e-2, initial_alpha=3974.0, initial_beta=-18.5)
        # Par XAU vs DXY con beta real = -18.5
        x = 104.0
        y = 2050.0
        for _ in range(20):
            x += 0.05
            y += (-18.5 * 0.05)  # Variación inversa
            alpha, beta, z = kf.update(y, x)

        self.assertIsInstance(alpha, float)
        self.assertIsInstance(beta, float)
        self.assertIsInstance(z, float)
        self.assertLess(beta, 0.0, "Beta de ORO/DXY debe ser negativo")

    def test_order_flow_engine_calcula_ofi_y_micro_price(self) -> None:
        of = OrderFlowEngine()
        # Primer tick
        ofi_0, mid_0, mp_0 = of.compute(bid_p=5000.0, bid_v=10.0, ask_p=5000.4, ask_v=10.0)
        self.assertEqual(0.0, ofi_0)
        self.assertAlmostEqual(5000.2, mid_0, places=2)

        # Segundo tick con fuerte presión compradora en Bid
        ofi_1, mid_1, mp_1 = of.compute(bid_p=5000.2, bid_v=50.0, ask_p=5000.4, ask_v=10.0)
        self.assertGreater(ofi_1, 0.0, "OFI debe ser positivo ante subida de Bid")
        self.assertGreater(mp_1, mid_1, "Micro-Price debe ser mayor a Mid-Price con mayor volumen en Bid")

    def test_evaluar_sistema_luces_verde_amarillo_rojo(self) -> None:
        # Condición Verde (LONG): Z < -1.0, OFI positivo, micro-price > mid
        res_verde = evaluar_sistema_luces_cuantitativo(
            z_score=-1.8, ofi=45.0, micro_price=5000.35, mid_price=5000.20
        )
        self.assertEqual("GREEN", res_verde.light)
        self.assertEqual("LONG", res_verde.direction)
        self.assertGreaterEqual(res_verde.composite_score, 0.35)
        self.assertGreaterEqual(res_verde.confidence_pct, 70.0)

        # Condición Roja (SHORT): Z > +1.0, OFI negativo, micro-price < mid
        res_rojo = evaluar_sistema_luces_cuantitativo(
            z_score=1.8, ofi=-45.0, micro_price=5000.05, mid_price=5000.20
        )
        self.assertEqual("RED", res_rojo.light)
        self.assertEqual("SHORT", res_rojo.direction)
        self.assertLessEqual(res_rojo.composite_score, -0.35)
        self.assertGreaterEqual(res_rojo.confidence_pct, 70.0)

        # Condición Amarilla (NEUTRAL / ESPERA): Señales intermedias o mixtas
        res_amarillo = evaluar_sistema_luces_cuantitativo(
            z_score=0.1, ofi=2.0, micro_price=5000.20, mid_price=5000.20
        )
        self.assertEqual("YELLOW", res_amarillo.light)
        self.assertEqual("MONITOR", res_amarillo.direction)

    def test_motor_multi_activo_los_tres_balancines(self) -> None:
        motor = MotorMultiActivo()
        snapshot = motor.paso_simulacion()

        self.assertIn("us500_price", snapshot)
        self.assertIn("balancines", snapshot)
        self.assertEqual(3, len(snapshot["balancines"]))

        nombres_balancines = [b["name"] for b in snapshot["balancines"]]
        self.assertIn("ORO vs. DÓLAR (DXY)", nombres_balancines)
        self.assertIn("S&P 500 vs. TSLA", nombres_balancines)
        self.assertIn("S&P 500 vs. AAPL", nombres_balancines)

        self.assertIn(snapshot["global_light"], {"GREEN", "YELLOW", "RED"})
        self.assertGreaterEqual(snapshot["hit_rate_pct"], 70.0)
        self.assertLessEqual(snapshot["error_rate_pct"], 30.0)


if __name__ == "__main__":
    unittest.main()
