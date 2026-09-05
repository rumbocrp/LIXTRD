"""Pruebas para purga, embargo y particiones walk-forward sin fuga (WP-06, CA-26)."""

from datetime import datetime, timedelta, timezone
import unittest

from sistema_luces.learning.splits import (
    GeneradorParticionesWalkForward,
    ParticionFoldV1,
    SolicitudParticionWalkForward,
    verificar_cero_fuga,
)


class PurgedEmbargoedSplitsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.t0 = datetime(2026, 8, 29, 14, 30, 0, tzinfo=timezone.utc)
        # 100 muestras separadas por 30 segundos = 3000s = 50 minutos de datos
        self.sample_times = [self.t0 + timedelta(seconds=i * 30) for i in range(100)]
        self.horizon_seconds = 300  # 5 minutos (10 muestras de 30s)
        self.embargo_seconds = 300  # 5 minutos de embargo

    def test_purged_and_embargoed_split_prevents_leakage(self) -> None:
        """CA-26: Purga del traslape de horizonte y embargo posterior para evitar fuga de datos."""
        solicitud = SolicitudParticionWalkForward(
            n_samples=len(self.sample_times),
            sample_timestamps_utc=tuple(self.sample_times),
            horizon_seconds=self.horizon_seconds,
            embargo_seconds=self.embargo_seconds,
            n_folds=3,
            min_train_samples=40,
        )

        generador = GeneradorParticionesWalkForward()
        res = generador.generar_folds(solicitud)
        self.assertTrue(res.exito)
        folds = res.datos
        self.assertEqual(3, len(folds))

        for fold in folds:
            self.assertGreater(len(fold.train_indices), 0)
            self.assertGreater(len(fold.test_indices), 0)

            # Verificar que no hay intersección entre train y test
            train_set = set(fold.train_indices)
            test_set = set(fold.test_indices)
            self.assertEqual(0, len(train_set.intersection(test_set)))

            # Verificar con la regla estricta de cero fuga
            res_leak = verificar_cero_fuga(
                train_indices=fold.train_indices,
                test_indices=fold.test_indices,
                sample_timestamps_utc=self.sample_times,
                horizon_seconds=self.horizon_seconds,
                embargo_seconds=self.embargo_seconds,
            )
            self.assertTrue(res_leak.exito, f"Falla de fuga en fold {fold.fold_index}: {res_leak.error if not res_leak.exito else ''}")

    def test_detection_of_leakage_when_purge_is_omitted(self) -> None:
        """Verifica que el verificador detecta fuga si una muestra de train traslapa con test."""
        train_indices = (0, 1, 2, 3, 4, 5, 6, 7, 8, 9)  # muestra 9 termina en t0 + 9*30 + 300 = t0 + 570
        test_indices = (10, 11, 12)  # muestra 10 empieza en t0 + 10*30 = t0 + 300 (< 570 -> traslape!)

        res = verificar_cero_fuga(
            train_indices=train_indices,
            test_indices=test_indices,
            sample_timestamps_utc=self.sample_times,
            horizon_seconds=self.horizon_seconds,
            embargo_seconds=0,
        )
        self.assertFalse(res.exito)
        self.assertEqual("VALIDATION_ERROR", res.error.codigo)
        self.assertIn("Fuga de datos detectada", res.error.mensaje_seguro)


if __name__ == "__main__":
    unittest.main()
