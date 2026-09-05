"""Pruebas de Modelos Predictivos Base y Regresión Logística (SPEC-001 §6.8, WP-07)."""

from datetime import datetime, timezone
import unittest
import uuid

from sistema_luces.models.baseline import (
    ModeloBaseV1,
    ModeloRegresionLogisticaV1,
    calcular_hash_modelo,
    sigmoid,
)


class TestBaselineAndLogisticModels(unittest.TestCase):
    def setUp(self) -> None:
        self.t0 = datetime(2026, 8, 29, 14, 30, 0, tzinfo=timezone.utc)

    def test_sigmoid_numerical_stability(self) -> None:
        self.assertAlmostEqual(1.0, sigmoid(100.0))
        self.assertAlmostEqual(0.0, sigmoid(-100.0))
        self.assertAlmostEqual(0.5, sigmoid(0.0))

    def test_modelo_base_prior_probabilities(self) -> None:
        model = ModeloBaseV1(
            prior_long_scaled=650_000,
            prior_short_scaled=350_000,
            created_at_utc=self.t0,
        )
        self.assertEqual("BASELINE", model.model_type)
        self.assertEqual(64, len(model.model_hash))

        res = model.predecir_raw({"order_imbalance": 0})
        self.assertTrue(res.exito)
        raw_l, raw_s = res.datos
        self.assertEqual(650_000, raw_l)
        self.assertEqual(350_000, raw_s)

    def test_modelo_base_momentum_adjustment(self) -> None:
        model = ModeloBaseV1(
            prior_long_scaled=500_000,
            prior_short_scaled=500_000,
            momentum_factor=0.5,
            created_at_utc=self.t0,
        )
        # Positive order imbalance pushes LONG score higher
        res = model.predecir_raw({"order_imbalance": 500_000})
        self.assertTrue(res.exito)
        raw_l, raw_s = res.datos
        self.assertGreater(raw_l, 500_000)
        self.assertLess(raw_s, 500_000)

    def test_modelo_regresion_logistica_entrenar_y_predecir(self) -> None:
        feature_names = ("spread_mean", "order_imbalance", "price_return_points")
        # Generar datos sintéticos separables
        X: list[list[float]] = []
        y_l: list[int] = []
        y_s: list[int] = []

        for i in range(50):
            # Clase LONG dominante
            X.append([40.0, 500_000.0, 300.0])
            y_l.append(1)
            y_s.append(0)
            # Clase SHORT dominante
            X.append([40.0, -500_000.0, -300.0])
            y_l.append(0)
            y_s.append(1)

        res_train = ModeloRegresionLogisticaV1.entrenar(
            feature_names=feature_names,
            X=X,
            y_long=y_l,
            y_short=y_s,
            learning_rate=0.1,
            max_epochs=100,
        )
        self.assertTrue(res_train.exito)
        model = res_train.datos

        self.assertEqual(64, len(model.model_hash))
        self.assertEqual("LOGISTIC_REGRESSION", model.model_type)

        # Predicción sobre caso alcista
        res_pred_l = model.predecir_raw({"spread_mean": 40, "order_imbalance": 600_000, "price_return_points": 400})
        self.assertTrue(res_pred_l.exito)
        pred_l, pred_s = res_pred_l.datos
        self.assertGreater(pred_l, 500_000)
        self.assertLess(pred_s, 500_000)

        # Predicción sobre caso bajista
        res_pred_s = model.predecir_raw({"spread_mean": 40, "order_imbalance": -600_000, "price_return_points": -400})
        self.assertTrue(res_pred_s.exito)
        pred_l2, pred_s2 = res_pred_s.datos
        self.assertLess(pred_l2, 500_000)
        self.assertGreater(pred_s2, 500_000)


if __name__ == "__main__":
    unittest.main()
