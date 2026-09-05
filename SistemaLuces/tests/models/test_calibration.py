"""Pruebas de Calibración Out-of-Fold y Platt Scaling (SPEC-001 §6.8, CA-26, WP-07)."""

from datetime import datetime, timezone
import unittest

from sistema_luces.models.calibration import CalibradorLogistico


class TestCalibrationOOF(unittest.TestCase):
    def setUp(self) -> None:
        self.t0 = datetime(2026, 8, 29, 14, 30, 0, tzinfo=timezone.utc)

    def test_in_fold_calibration_strictly_forbidden_ca26(self) -> None:
        """CA-26: La calibración in-fold está estrictamente prohibida por política de gate."""
        scores = [500_000, 600_000, 700_000] * 5
        labels = [0, 1, 1] * 5
        res = CalibradorLogistico.ajustar_oof(scores, labels, is_out_of_fold=False)
        self.assertFalse(res.exito)
        self.assertEqual("VALIDATION_ERROR", res.error.codigo)
        self.assertIn("in-fold", res.error.mensaje_seguro.lower())

    def test_out_of_fold_calibration_fitting_and_scaling(self) -> None:
        """Ajusta Platt scaling sobre predicciones OOF y produce probabilidades en 0..1_000_000."""
        # Conjunto sintético de predicciones OOF y etiquetas reales
        scores = [200_000, 300_000, 400_000, 600_000, 700_000, 800_000] * 5
        labels = [0, 0, 0, 1, 1, 1] * 5

        res = CalibradorLogistico.ajustar_oof(scores, labels, is_out_of_fold=True)
        self.assertTrue(res.exito)
        calibrator = res.datos

        self.assertTrue(calibrator.is_out_of_fold)
        self.assertEqual(64, len(calibrator.calibration_hash))

        # Calibrar score bajo -> probabilidad baja
        p_low = calibrator.calibrar(200_000)
        self.assertIsInstance(p_low, int)
        self.assertLess(p_low, 500_000)
        self.assertGreaterEqual(p_low, 0)

        # Calibrar score alto -> probabilidad alta
        p_high = calibrator.calibrar(800_000)
        self.assertIsInstance(p_high, int)
        self.assertGreater(p_high, 500_000)
        self.assertLessEqual(p_high, 1_000_000)

    def test_calibrar_par_directional(self) -> None:
        scores = [200_000, 400_000, 600_000, 800_000] * 5
        labels = [0, 0, 1, 1] * 5
        res = CalibradorLogistico.ajustar_oof(scores, labels, is_out_of_fold=True)
        self.assertTrue(res.exito)
        calibrator = res.datos

        p_long, p_short = calibrator.calibrar_par(750_000, 250_000)
        self.assertGreaterEqual(p_long, 0)
        self.assertLessEqual(p_long, 1_000_000)
        self.assertGreaterEqual(p_short, 0)
        self.assertLessEqual(p_short, 1_000_000)

    def test_calibrar_boundary_values_integer_zero_and_million(self) -> None:
        """Verifica que el score entero 0 y 1_000_000 se calibren en los extremos adecuados."""
        scores = [100_000, 300_000, 700_000, 900_000] * 5
        labels = [0, 0, 1, 1] * 5
        res = CalibradorLogistico.ajustar_oof(scores, labels, is_out_of_fold=True)
        self.assertTrue(res.exito)
        calibrator = res.datos

        p_zero = calibrator.calibrar(0)
        p_million = calibrator.calibrar(1_000_000)

        self.assertIsInstance(p_zero, int)
        self.assertIsInstance(p_million, int)
        self.assertLessEqual(p_zero, 50_000)
        self.assertGreaterEqual(p_million, 950_000)
        self.assertLess(p_zero, p_million)

    def test_calibrar_monotonicity_and_ordering(self) -> None:
        """Verifica que scores crecientes produzcan probabilidades calibradas crecientes."""
        scores = [100_000, 200_000, 400_000, 600_000, 800_000, 900_000] * 5
        labels = [0, 0, 0, 1, 1, 1] * 5
        res = CalibradorLogistico.ajustar_oof(scores, labels, is_out_of_fold=True)
        self.assertTrue(res.exito)
        calibrator = res.datos

        test_points = [0, 100_000, 300_000, 500_000, 700_000, 900_000, 1_000_000]
        calibrated = [calibrator.calibrar(pt) for pt in test_points]

        for i in range(len(calibrated) - 1):
            self.assertLessEqual(calibrated[i], calibrated[i + 1])


if __name__ == "__main__":
    unittest.main()
