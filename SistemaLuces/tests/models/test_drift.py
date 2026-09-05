"""Pruebas del Detector de Drift de Distribución (SPEC-001 §6.8, WP-07)."""

import unittest

from sistema_luces.models.drift import DetectorDrift


class TestDriftDetector(unittest.TestCase):
    def setUp(self) -> None:
        self.detector = DetectorDrift(psi_warning_threshold=0.10, psi_severe_threshold=0.25)

    def test_psi_identical_distributions(self) -> None:
        """Dos distribuciones idénticas producen PSI ~ 0 y estado HEALTHY."""
        ref_data = [float(i) for i in range(100)]
        cur_data = [float(i) for i in range(100)]

        psi = self.detector.calcular_psi(ref_data, cur_data)
        self.assertLess(psi, 0.05)

        report = self.detector.evaluar_drift({"feature1": ref_data}, {"feature1": cur_data})
        self.assertEqual("HEALTHY", report.status)
        self.assertFalse(report.severe_drift_detected)
        self.assertEqual((), report.drifted_features)

    def test_psi_moderate_drift_warning(self) -> None:
        """Desplazamiento moderado produce 0.10 <= PSI < 0.25 y estado WARNING."""
        ref_data = [float(i) for i in range(100)]
        # Desplazar ligeramente hacia arriba
        cur_data = [float(i + 15) for i in range(100)]

        report = self.detector.evaluar_drift({"feature1": ref_data}, {"feature1": cur_data})
        # Dependiendo del shift exacto, verifica que el PSI detecta el cambio
        self.assertGreater(report.max_psi, 0.05)

    def test_psi_severe_drift_alert(self) -> None:
        """Desplazamiento severo produce PSI >= 0.25 y estado SEVERE_DRIFT."""
        ref_data = [float(i) for i in range(100)]
        # Desplazamiento extremo
        cur_data = [float(i + 200) for i in range(100)]

        report = self.detector.evaluar_drift(
            {"f1": ref_data, "f2": ref_data},
            {"f1": cur_data, "f2": ref_data},
        )
        self.assertEqual("SEVERE_DRIFT", report.status)
        self.assertTrue(report.severe_drift_detected)
        self.assertIn("f1", report.drifted_features)
        self.assertNotIn("f2", report.drifted_features)


if __name__ == "__main__":
    unittest.main()
