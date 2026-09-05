"""Pruebas del monitor de calidad de feed: gaps, stale, duplicates, out-of-order y clock rollback (CA-7)."""
from datetime import datetime, timezone, timedelta
import unittest

from sistema_luces.domain.event import SobreEventoV1, compute_payload_hash
from sistema_luces.sources.clock import RelojDominio
from sistema_luces.feed.quality import MonitorCalidadFeed


class FeedQualityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.t0 = datetime(2026, 8, 31, 13, 30, 0, tzinfo=timezone.utc)
        self.reloj = RelojDominio(tiempo_inicial_utc=self.t0, clock_seed=20260829)
        self.monitor = MonitorCalidadFeed(stale_threshold_ms=5000)

    def _make_event(self, event_id: str, seq: int, t: datetime) -> SobreEventoV1:
        p = {"bid": 500000, "ask": 500025, "price_scale": 100}
        return SobreEventoV1(
            event_id=event_id,
            event_type="QUOTE_TICK",
            schema_version=1,
            occurred_at_utc=t,
            received_at_utc=t,
            persisted_at_utc=None,
            source="replay",
            environment="REPLAY",
            source_account_id_hash=None,
            instrument="US500",
            symbol_id=None,
            source_sequence=seq,
            correlation_id="feed-quality-corr-01",
            causation_id=None,
            payload_hash=compute_payload_hash(p),
            previous_hash=None,
            payload=p,
        )

    def test_evento_normal_mantiene_feed_saludable(self) -> None:
        ev = self._make_event("30000000-0000-0000-0000-000000000001", 1, self.t0)
        estado, alertas = self.monitor.evaluar_evento(ev, self.reloj)
        self.assertEqual(estado, "HEALTHY")
        self.assertEqual(len(alertas), 0)

    def test_gap_en_secuencia_genera_alerta_y_pasa_a_gapped(self) -> None:
        # Event 1 (seq 1)
        ev1 = self._make_event("30000000-0000-0000-0000-000000000001", 1, self.t0)
        self.monitor.evaluar_evento(ev1, self.reloj)

        # Event 2 (seq 4 -> missing 2 and 3)
        t1 = self.t0 + timedelta(seconds=1)
        self.reloj.avanzar_hasta(t1)
        ev2 = self._make_event("30000000-0000-0000-0000-000000000002", 4, t1)
        estado, alertas = self.monitor.evaluar_evento(ev2, self.reloj)

        self.assertEqual(estado, "GAPPED")
        self.assertEqual(len(alertas), 1)
        self.assertEqual(alertas[0].event_type, "GAP_DETECTED")
        self.assertEqual(alertas[0].payload["missing_count"], 2)
        self.assertEqual(alertas[0].payload["action"], "FORCE_YELLOW_STOP_SIM")

    def test_feed_stale_exacto_en_5000_y_5001_ms(self) -> None:
        # Boundary test: exactly 5000ms is OK, 5001ms is STALE
        ev = self._make_event("30000000-0000-0000-0000-000000000001", 1, self.t0)

        # Clock at t0 + 5000ms (5.0s) -> NOT stale
        reloj_5000 = RelojDominio(tiempo_inicial_utc=self.t0 + timedelta(milliseconds=5000))
        m1 = MonitorCalidadFeed(stale_threshold_ms=5000)
        estado1, alertas1 = m1.evaluar_evento(ev, reloj_5000)
        self.assertEqual(estado1, "HEALTHY")
        self.assertEqual(len(alertas1), 0)

        # Clock at t0 + 5001ms (5.001s) -> STALE
        reloj_5001 = RelojDominio(tiempo_inicial_utc=self.t0 + timedelta(milliseconds=5001))
        m2 = MonitorCalidadFeed(stale_threshold_ms=5000)
        estado2, alertas2 = m2.evaluar_evento(ev, reloj_5001)
        self.assertEqual(estado2, "STALE")
        self.assertEqual(len(alertas2), 1)
        self.assertEqual(alertas2[0].event_type, "STALE")
        self.assertEqual(alertas2[0].payload["action"], "FORCE_YELLOW")

    def test_evento_fuera_de_orden_genera_alerta_y_cuarentena(self) -> None:
        ev1 = self._make_event("30000000-0000-0000-0000-000000000001", 5, self.t0)
        self.monitor.evaluar_evento(ev1, self.reloj)

        t1 = self.t0 + timedelta(seconds=1)
        self.reloj.avanzar_hasta(t1)
        ev2 = self._make_event("30000000-0000-0000-0000-000000000002", 3, t1)  # seq 3 < 5!
        estado, alertas = self.monitor.evaluar_evento(ev2, self.reloj)

        self.assertEqual(len(alertas), 1)
        self.assertEqual(alertas[0].event_type, "OUT_OF_ORDER")
        self.assertEqual(alertas[0].payload["action"], "QUARANTINE")
