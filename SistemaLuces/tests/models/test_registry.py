"""Pruebas del Registro de Modelos Inmutable (SPEC-001 §6.8, WP-07)."""

from datetime import datetime, timezone
import unittest
import uuid

from sistema_luces.cases.builder import CasoV1
from sistema_luces.models.baseline import ModeloBaseV1, ModeloRegresionLogisticaV1
from sistema_luces.models.calibration import CalibradorLogistico
from sistema_luces.models.registry import RegistroModelos


class TestRegistroModelos(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = RegistroModelos()
        self.t0 = datetime(2026, 8, 29, 14, 30, 0, tzinfo=timezone.utc)

    def test_registrar_y_obtener_modelo_base(self) -> None:
        model_id = str(uuid.uuid4())
        model = ModeloBaseV1(
            model_id=model_id,
            model_name="baseline-test",
            model_version="1.0.0",
            prior_long_scaled=550_000,
            prior_short_scaled=450_000,
            created_at_utc=self.t0,
        )

        res_reg = self.registry.registrar(model)
        self.assertTrue(res_reg.exito)
        self.assertEqual(model_id, res_reg.datos)

        # Obtener por ID
        res_get_id = self.registry.obtener(model_id)
        self.assertTrue(res_get_id.exito)
        self.assertEqual(model.model_hash, res_get_id.datos.model_hash)

        # Obtener por Hash
        res_get_hash = self.registry.obtener(model.model_hash)
        self.assertTrue(res_get_hash.exito)
        self.assertEqual(model_id, res_get_hash.datos.model_id)

    def test_idempotencia_registro_mismo_hash(self) -> None:
        model_id = str(uuid.uuid4())
        model1 = ModeloBaseV1(
            model_id=model_id,
            model_name="baseline-test",
            model_version="1.0.0",
            prior_long_scaled=500_000,
            created_at_utc=self.t0,
        )
        model2 = ModeloBaseV1(
            model_id=model_id,
            model_name="baseline-test",
            model_version="1.0.0",
            prior_long_scaled=500_000,
            created_at_utc=self.t0,
        )

        res1 = self.registry.registrar(model1)
        self.assertTrue(res1.exito)

        res2 = self.registry.registrar(model2)
        self.assertTrue(res2.exito)
        self.assertEqual(model_id, res2.datos)

    def test_conflicto_integridad_mismo_id_distinto_hash(self) -> None:
        model_id = str(uuid.uuid4())
        model1 = ModeloBaseV1(
            model_id=model_id,
            model_name="baseline-test",
            model_version="1.0.0",
            prior_long_scaled=500_000,
            created_at_utc=self.t0,
        )
        model2 = ModeloBaseV1(
            model_id=model_id,
            model_name="baseline-test",
            model_version="2.0.0",
            prior_long_scaled=700_000,
            created_at_utc=self.t0,
        )

        self.assertTrue(self.registry.registrar(model1).exito)
        res_conflict = self.registry.registrar(model2)
        self.assertFalse(res_conflict.exito)
        self.assertEqual("INTEGRITY_ERROR", res_conflict.error.codigo)

    def test_obtener_modelo_inexistente_retorna_error(self) -> None:
        res = self.registry.obtener("modelo-inexistente-123")
        self.assertFalse(res.exito)
        self.assertEqual("MODEL_UNAVAILABLE", res.error.codigo)

    def test_listar_modelos(self) -> None:
        id1 = "model-a-" + str(uuid.uuid4())[:8]
        id2 = "model-b-" + str(uuid.uuid4())[:8]
        m1 = ModeloBaseV1(model_id=id1, model_name="m1", created_at_utc=self.t0)
        m2 = ModeloBaseV1(model_id=id2, model_name="m2", created_at_utc=self.t0)

        self.registry.registrar(m1)
        self.registry.registrar(m2)

        res_list = self.registry.listar()
        self.assertTrue(res_list.exito)
        self.assertIn(id1, res_list.datos)
        self.assertIn(id2, res_list.datos)

    def test_predecir_calibrado_con_calibrador_registrado(self) -> None:
        model_id = str(uuid.uuid4())
        model = ModeloBaseV1(
            model_id=model_id,
            model_name="baseline-test",
            prior_long_scaled=600_000,
            prior_short_scaled=400_000,
            created_at_utc=self.t0,
        )
        self.registry.registrar(model)

        # Crear y registrar calibrador OOF
        oof_scores = [300_000, 400_000, 500_000, 600_000, 700_000, 800_000] * 3
        y_true = [0, 0, 0, 1, 1, 1] * 3
        res_calib = CalibradorLogistico.ajustar_oof(oof_scores, y_true, is_out_of_fold=True)
        self.assertTrue(res_calib.exito)
        calibrador = res_calib.datos

        res_reg_calib = self.registry.registrar_calibrador(model_id, calibrador)
        self.assertTrue(res_reg_calib.exito)

        caso = CasoV1(
            case_id=str(uuid.uuid4()),
            decision_window="S30",
            window_start_utc=self.t0,
            window_end_utc=self.t0,
            market_event_cutoff=self.t0,
            reference_bid=500000,
            reference_ask=500040,
            price_scale=100,
            feature_set_version="features-v1",
            feature_snapshot={"tick_count": 10, "order_imbalance": 0},
            feature_snapshot_hash="a" * 64,
            feed_health_state="HEALTHY",
            eligible_for_signal=True,
            event_count_in_window=10,
            reason_codes=(),
            correlation_id=str(uuid.uuid4()),
            causation_id=None,
            created_at_utc=self.t0,
        )

        res_pred = self.registry.predecir_calibrado(model_id, caso)
        self.assertTrue(res_pred.exito)
        self.assertIsInstance(res_pred.datos, int)
        self.assertGreaterEqual(res_pred.datos, 0)
        self.assertLessEqual(res_pred.datos, 1_000_000)


if __name__ == "__main__":
    unittest.main()
