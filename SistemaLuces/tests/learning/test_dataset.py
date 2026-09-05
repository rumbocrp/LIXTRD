"""Pruebas para construcción de matrices y dataset causal (WP-06)."""

from datetime import datetime, timedelta, timezone
import unittest

from tests.acceptance.helpers import make_uuid

from sistema_luces.cases.builder import CasoV1
from sistema_luces.learning.dataset import (
    ConstructorDatasetCausal,
    DatasetCausalV1,
    MuestraAprendizajeV1,
)
from sistema_luces.learning.labels import EtiquetaV1


class DatasetBuilderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.t0 = datetime(2026, 8, 29, 14, 30, 0, tzinfo=timezone.utc)
        self.constructor = ConstructorDatasetCausal()

    def test_construir_dataset_causal_con_features_y_labels(self) -> None:
        casos: list[CasoV1] = []
        etiquetas_long: list[EtiquetaV1] = []
        etiquetas_short: list[EtiquetaV1] = []

        for i in range(10):
            cid = make_uuid(i + 1)
            t = self.t0 + timedelta(seconds=i * 30)
            caso = CasoV1(
                case_id=cid,
                decision_window="S30",
                window_start_utc=t - timedelta(seconds=30),
                window_end_utc=t,
                market_event_cutoff=t,
                reference_bid=500000 + i * 10,
                reference_ask=500040 + i * 10,
                price_scale=100,
                feature_set_version="features-v1",
                feature_snapshot={
                    "tick_count": 10,
                    "spread_last": 40,
                    "spread_mean": 40,
                    "price_return_points": 10,
                    "price_high": 500050,
                    "price_low": 500000,
                },
                feature_snapshot_hash="f" * 64,
                feed_health_state="HEALTHY",
                eligible_for_signal=True,
                event_count_in_window=10,
                reason_codes=(),
                correlation_id=cid,
                causation_id=None,
                created_at_utc=t,
                environment="REPLAY",
                instrument="US500",
            )
            casos.append(caso)

            eti_l = EtiquetaV1(
                label_id=make_uuid(100 + i),
                case_id=cid,
                direction="LONG",
                status="MATURE",
                outcome="TAKE_PROFIT" if i % 2 == 0 else "STOP_LOSS",
                entry_price=500040 + i * 10,
                exit_price=502040 + i * 10,
                stop_barrier_price=499540 + i * 10,
                target_barrier_price=502040 + i * 10,
                price_scale=100,
                first_touch_at_utc=t + timedelta(seconds=60),
                horizon_end_utc=t + timedelta(seconds=300),
                realized_points=2000 if i % 2 == 0 else -500,
                is_ambiguous_tie=False,
                reason_codes=(),
                correlation_id=cid,
                causation_id=None,
                created_at_utc=t + timedelta(seconds=60),
            )
            etiquetas_long.append(eti_l)

            eti_s = EtiquetaV1(
                label_id=make_uuid(200 + i),
                case_id=cid,
                direction="SHORT",
                status="MATURE",
                outcome="STOP_LOSS" if i % 2 == 0 else "TAKE_PROFIT",
                entry_price=500000 + i * 10,
                exit_price=500500 + i * 10,
                stop_barrier_price=500500 + i * 10,
                target_barrier_price=498000 + i * 10,
                price_scale=100,
                first_touch_at_utc=t + timedelta(seconds=60),
                horizon_end_utc=t + timedelta(seconds=300),
                realized_points=-500 if i % 2 == 0 else 2000,
                is_ambiguous_tie=False,
                reason_codes=(),
                correlation_id=cid,
                causation_id=None,
                created_at_utc=t + timedelta(seconds=60),
            )
            etiquetas_short.append(eti_s)

        res = self.constructor.construir_dataset(
            casos=casos,
            etiquetas_long=etiquetas_long,
            etiquetas_short=etiquetas_short,
            feature_keys=("price_high", "price_low", "price_return_points", "spread_last", "spread_mean", "tick_count"),
        )
        self.assertTrue(res.exito)
        ds = res.datos
        self.assertEqual(10, ds.n_samples)
        self.assertEqual(6, len(ds.feature_names))
        self.assertEqual(10, len(ds.X))
        self.assertEqual(10, len(ds.y_long))
        self.assertEqual(10, len(ds.y_short))
        self.assertIsNotNone(ds.dataset_manifest_hash)


if __name__ == "__main__":
    unittest.main()
