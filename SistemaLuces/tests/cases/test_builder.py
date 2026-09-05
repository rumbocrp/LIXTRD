"""Pruebas para ConstructorCaso e invariantes de causalidad y elegibilidad (WP-05, CA-9, OPT-7)."""

from datetime import datetime, timedelta, timezone
import unittest

from tests.acceptance.helpers import create_test_quote_tick_envelope, make_uuid

from sistema_luces.cases.builder import ConstructorCaso, SolicitudCaso, validar_solicitud_caso
from sistema_luces.domain.event import SobreEventoV1


class CaseBuilderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.t0 = datetime(2026, 8, 29, 14, 30, 0, tzinfo=timezone.utc)
        self.cutoff = datetime(2026, 8, 29, 14, 30, 30, tzinfo=timezone.utc)
        self.builder = ConstructorCaso()

    def test_solicitud_caso_validacion(self) -> None:
        sol = SolicitudCaso(
            case_id=make_uuid(1),
            correlation_id=make_uuid(1),
            decision_window="S30",
            window_start_utc=self.t0,
            window_end_utc=self.cutoff,
            market_event_cutoff=self.cutoff,
            feed_health_state="HEALTHY",
            feature_set_version="features-v1",
            environment="REPLAY",
        )
        res = validar_solicitud_caso(sol)
        self.assertTrue(res.exito)

    def test_opt7_causal_cutoff_strict_exclusion(self) -> None:
        """CA-9 / OPT-7: Dado un corte de mercado, el caso no contiene eventos posteriores al corte."""
        events: list[SobreEventoV1] = [
            create_test_quote_tick_envelope(
                seq=1,
                occurred_at_utc=self.t0 + timedelta(seconds=10),
                bid=500000,
                ask=500040,
            ),
            create_test_quote_tick_envelope(
                seq=2,
                occurred_at_utc=self.t0 + timedelta(seconds=25),
                bid=500020,
                ask=500060,
            ),
            # Evento posterior al corte (debe ser ignorado)
            create_test_quote_tick_envelope(
                seq=3,
                occurred_at_utc=self.cutoff + timedelta(seconds=1),
                bid=500100,
                ask=500140,
            ),
        ]

        sol = SolicitudCaso(
            case_id=make_uuid(10),
            correlation_id=make_uuid(10),
            decision_window="S30",
            window_start_utc=self.t0,
            window_end_utc=self.cutoff,
            market_event_cutoff=self.cutoff,
            feed_health_state="HEALTHY",
            feature_set_version="features-v1",
            environment="REPLAY",
        )

        res = self.builder.construir(sol, events)
        self.assertTrue(res.exito)
        caso = res.datos
        self.assertEqual(2, caso.event_count_in_window)
        self.assertEqual(500020, caso.reference_bid)
        self.assertEqual(500060, caso.reference_ask)
        self.assertTrue(caso.eligible_for_signal)

    def test_feed_degraded_marks_case_ineligible(self) -> None:
        """Si el feed está degradado (STALE, GAPPED, etc.), el caso se construye como NO elegible para señal."""
        events: list[SobreEventoV1] = [
            create_test_quote_tick_envelope(
                seq=1,
                occurred_at_utc=self.t0 + timedelta(seconds=10),
                bid=500000,
                ask=500040,
            )
        ]

        sol = SolicitudCaso(
            case_id=make_uuid(11),
            correlation_id=make_uuid(11),
            decision_window="S30",
            window_start_utc=self.t0,
            window_end_utc=self.cutoff,
            market_event_cutoff=self.cutoff,
            feed_health_state="STALE",
            feature_set_version="features-v1",
            environment="REPLAY",
        )

        res = self.builder.construir(sol, events)
        self.assertTrue(res.exito)
        caso = res.datos
        self.assertFalse(caso.eligible_for_signal)
        self.assertIn("FEED_NOT_HEALTHY", caso.reason_codes)

    def test_insufficient_data_marks_case_ineligible(self) -> None:
        """Si no hay ticks en la ventana, el caso es no elegible para emitir señal."""
        sol = SolicitudCaso(
            case_id=make_uuid(12),
            correlation_id=make_uuid(12),
            decision_window="S30",
            window_start_utc=self.t0,
            window_end_utc=self.cutoff,
            market_event_cutoff=self.cutoff,
            feed_health_state="HEALTHY",
            feature_set_version="features-v1",
            environment="REPLAY",
        )

        res = self.builder.construir(sol, [])
        self.assertTrue(res.exito)
        caso = res.datos
        self.assertFalse(caso.eligible_for_signal)
        self.assertIn("INSUFFICIENT_DATA", caso.reason_codes)
        self.assertIsNone(caso.reference_bid)
        self.assertIsNone(caso.reference_ask)

    def test_reproducibility_identical_payload_hash(self) -> None:
        """CA-9: Reconstrucción idéntica genera el mismo feature_snapshot_hash."""
        events: list[SobreEventoV1] = [
            create_test_quote_tick_envelope(
                seq=1,
                occurred_at_utc=self.t0 + timedelta(seconds=15),
                bid=500000,
                ask=500040,
            )
        ]

        sol1 = SolicitudCaso(
            case_id=make_uuid(100),
            correlation_id=make_uuid(100),
            decision_window="S30",
            window_start_utc=self.t0,
            window_end_utc=self.cutoff,
            market_event_cutoff=self.cutoff,
            feed_health_state="HEALTHY",
            feature_set_version="features-v1",
            environment="REPLAY",
        )
        sol2 = SolicitudCaso(
            case_id=make_uuid(100),
            correlation_id=make_uuid(100),
            decision_window="S30",
            window_start_utc=self.t0,
            window_end_utc=self.cutoff,
            market_event_cutoff=self.cutoff,
            feed_health_state="HEALTHY",
            feature_set_version="features-v1",
            environment="REPLAY",
        )

        res1 = self.builder.construir(sol1, events)
        res2 = self.builder.construir(sol2, events)

        self.assertTrue(res1.exito)
        self.assertTrue(res2.exito)
        self.assertEqual(res1.datos.feature_snapshot_hash, res2.datos.feature_snapshot_hash)


if __name__ == "__main__":
    unittest.main()
