"""Pruebas para extracción de features causales y hashing de snapshots (WP-05)."""

from datetime import datetime, timedelta, timezone
import unittest

from tests.acceptance.helpers import create_test_quote_tick_envelope, make_uuid

from sistema_luces.cases.features import (
    calcular_snapshot_features,
    calcular_snapshot_hash,
)
from sistema_luces.domain.event import SobreEventoV1, canonical_json_bytes


class CausalFeaturesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.t0 = datetime(2026, 8, 29, 14, 30, 0, tzinfo=timezone.utc)
        self.cutoff = datetime(2026, 8, 29, 14, 30, 30, tzinfo=timezone.utc)

    def test_features_calculo_basico(self) -> None:
        # Generar 5 quote ticks dentro de la ventana de 30s
        events: list[SobreEventoV1] = []
        for i in range(5):
            t = self.t0 + timedelta(seconds=i * 5)
            bid = 500000 + (i * 10)  # 5000.00, 5000.10, 5000.20, 5000.30, 5000.40
            ask = bid + 40  # spread 40 pts
            events.append(
                create_test_quote_tick_envelope(
                    seq=i + 1,
                    occurred_at_utc=t,
                    bid=bid,
                    ask=ask,
                    price_scale=100,
                )
            )

        snapshot = calcular_snapshot_features(
            events=events,
            window_start_utc=self.t0,
            window_end_utc=self.cutoff,
            market_event_cutoff=self.cutoff,
        )

        self.assertEqual(5, snapshot["tick_count"])
        self.assertEqual(40, snapshot["spread_last"])
        self.assertEqual(40, snapshot["spread_mean"])
        self.assertEqual(500000, snapshot["price_first_bid"])
        self.assertEqual(500040, snapshot["price_last_bid"])
        self.assertEqual(500080, snapshot["price_last_ask"])
        self.assertEqual(40, snapshot["price_return_points"])  # 500040 - 500000
        self.assertEqual(500080, snapshot["price_high"])
        self.assertEqual(500000, snapshot["price_low"])
        self.assertIsNotNone(snapshot["feature_snapshot_hash"])

    def test_missing_data_preserves_none(self) -> None:
        """SPEC-001 & ADR-001: Datos no computables o ausentes se preservan como None, nunca como 0 inventado."""
        # 0 ticks en ventana
        snapshot = calcular_snapshot_features(
            events=[],
            window_start_utc=self.t0,
            window_end_utc=self.cutoff,
            market_event_cutoff=self.cutoff,
        )

        self.assertEqual(0, snapshot["tick_count"])
        self.assertIsNone(snapshot["spread_last"])
        self.assertIsNone(snapshot["spread_mean"])
        self.assertIsNone(snapshot["price_first_bid"])
        self.assertIsNone(snapshot["price_last_bid"])
        self.assertIsNone(snapshot["price_last_ask"])
        self.assertIsNone(snapshot["price_return_points"])
        self.assertIsNone(snapshot["price_high"])
        self.assertIsNone(snapshot["price_low"])
        self.assertIsNone(snapshot["order_imbalance"])
        self.assertIsNone(snapshot["volume_total"])

    def test_feature_snapshot_hash_is_deterministic(self) -> None:
        """CA-9: El snapshot se reproduce al mismo hash byte-a-byte."""
        events: list[SobreEventoV1] = [
            create_test_quote_tick_envelope(
                seq=1,
                occurred_at_utc=self.t0 + timedelta(seconds=2),
                bid=500000,
                ask=500050,
            ),
            create_test_quote_tick_envelope(
                seq=2,
                occurred_at_utc=self.t0 + timedelta(seconds=10),
                bid=500020,
                ask=500060,
            ),
        ]

        snap1 = calcular_snapshot_features(
            events=events,
            window_start_utc=self.t0,
            window_end_utc=self.cutoff,
            market_event_cutoff=self.cutoff,
        )
        snap2 = calcular_snapshot_features(
            events=events,
            window_start_utc=self.t0,
            window_end_utc=self.cutoff,
            market_event_cutoff=self.cutoff,
        )

        hash1 = calcular_snapshot_hash(snap1)
        hash2 = calcular_snapshot_hash(snap2)

        self.assertEqual(hash1, hash2)
        self.assertEqual(64, len(hash1))
        self.assertEqual(snap1["feature_snapshot_hash"], snap2["feature_snapshot_hash"])


if __name__ == "__main__":
    unittest.main()
