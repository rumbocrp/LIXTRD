"""Pruebas de Métricas Predictivas y Calibración (Brier, ECE, Log Loss, Wilson CI, WP-07)."""

import unittest

from sistema_luces.models.metrics import (
    calcular_brier_score,
    calcular_ece,
    calcular_intervalo_wilson_95,
    calcular_log_loss,
    calcular_utilidad_neta_con_ci,
)


class TestPredictiveMetrics(unittest.TestCase):
    def test_brier_score_exact_calculation(self) -> None:
        """Brier score: (0.72 - 1.0)^2 = 0.0784 -> 78400."""
        y_true = [1]
        probs = [720_000]
        brier = calcular_brier_score(y_true, probs)
        self.assertEqual(78400, brier)

        # Múltiples predicciones
        y_true_multi = [1, 0]
        probs_multi = [800_000, 200_000]
        # (0.8-1)^2 = 0.04; (0.2-0)^2 = 0.04 -> mean = 0.04 -> 40_000
        brier_multi = calcular_brier_score(y_true_multi, probs_multi)
        self.assertEqual(40_000, brier_multi)

    def test_expected_calibration_error_ece(self) -> None:
        """ECE con predicciones perfectamente calibradas debe ser ~0."""
        # 10 muestras con probabilidad 0.8 de las cuales 8 son positivas
        y_true = [1] * 8 + [0] * 2
        probs = [800_000] * 10
        ece = calcular_ece(y_true, probs, n_bins=10)
        self.assertEqual(0, ece)

        # Predicciones mal calibradas
        # 10 muestras con probabilidad 0.9 de las cuales 5 son positivas (acc=0.5, conf=0.9 -> gap=0.4 -> 400_000)
        y_mis = [1] * 5 + [0] * 5
        probs_mis = [900_000] * 10
        ece_mis = calcular_ece(y_mis, probs_mis, n_bins=10)
        self.assertEqual(400_000, ece_mis)

    def test_log_loss(self) -> None:
        y_true = [1, 0]
        probs = [800_000, 200_000]
        loss = calcular_log_loss(y_true, probs)
        self.assertGreater(loss, 0.0)
        self.assertLess(loss, 0.5)

    def test_wilson_interval_95(self) -> None:
        """Calcula el intervalo de Wilson 95% y verifica propiedades matemáticas."""
        # 70 éxitos de 100 pruebas
        lower, upper = calcular_intervalo_wilson_95(70, 100)
        self.assertGreater(lower, 0.55)
        self.assertLess(lower, 0.70)
        self.assertGreater(upper, 0.70)
        self.assertLess(upper, 0.85)

        # Casos de borde
        l_zero, u_zero = calcular_intervalo_wilson_95(0, 50)
        self.assertEqual(0.0, l_zero)
        self.assertGreater(u_zero, 0.0)

        l_all, u_all = calcular_intervalo_wilson_95(50, 50)
        self.assertLess(l_all, 1.0)
        self.assertEqual(1.0, u_all)

    def test_utilidad_neta_con_ci(self) -> None:
        # Ganancias en puntos realizadas
        realized = [2000, 2000, 2000, -500, 2000]  # 4 targets de 20 pts, 1 stop de 5 pts
        mean_net, ci_low, ci_high = calcular_utilidad_neta_con_ci(realized, cost_points_per_trade=40)
        self.assertGreater(mean_net, 0.0)
        self.assertGreater(ci_high, mean_net)


if __name__ == "__main__":
    unittest.main()
