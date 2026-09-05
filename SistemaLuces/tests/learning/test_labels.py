"""Pruebas para etiquetado de triple barrera con precios ejecutables (WP-06, CA-13, CA-14, Tabla 7.2)."""

from datetime import datetime, timedelta, timezone
import unittest

from tests.acceptance.helpers import create_test_quote_tick_envelope, make_uuid

from sistema_luces.cases.builder import CasoV1
from sistema_luces.domain.event import QuoteTickPayloadV1
from sistema_luces.learning.labels import (
    EtiquetaV1,
    Etiquetador,
    SolicitudEtiqueta,
    validar_etiqueta,
)


class TripleBarrierLabelingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.t0 = datetime(2026, 8, 29, 14, 30, 0, tzinfo=timezone.utc)
        self.etiquetador = Etiquetador(
            stop_loss_points=500,  # 5.00 pts con escala 100
            take_profit_points=2000,  # 20.00 pts con escala 100
            horizon_seconds=300,  # 5 minutos
        )

    def _crear_caso_test(self, bid: int = 500000, ask: int = 500100) -> CasoV1:
        return CasoV1(
            case_id=make_uuid(1),
            decision_window="S30",
            window_start_utc=self.t0 - timedelta(seconds=30),
            window_end_utc=self.t0,
            market_event_cutoff=self.t0,
            reference_bid=bid,
            reference_ask=ask,
            price_scale=100,
            feature_set_version="features-v1",
            feature_snapshot={"tick_count": 5},
            feature_snapshot_hash="a" * 64,
            feed_health_state="HEALTHY",
            eligible_for_signal=True,
            event_count_in_window=5,
            reason_codes=(),
            correlation_id=make_uuid(1),
            causation_id=None,
            created_at_utc=self.t0,
            environment="REPLAY",
            instrument="US500",
        )

    def test_tabla_7_2_fila_1_long_target(self) -> None:
        """Tabla 7.2 Fila 1: LONG entra ask 500100 -> Stop 499600, Target 502100. Primer bid 502100 -> TAKE_PROFIT."""
        caso = self._crear_caso_test(bid=500000, ask=500100)

        # Secuencia de ticks en horizonte
        ticks = [
            QuoteTickPayloadV1(
                bid=501000,
                ask=501040,
                price_scale=100,
                bid_size=10,
                ask_size=10,
                source_timestamp_utc=self.t0 + timedelta(seconds=30),
                source_sequence=1,
            ),
            QuoteTickPayloadV1(
                bid=502100,  # Alcanza target exacto
                ask=502140,
                price_scale=100,
                bid_size=10,
                ask_size=10,
                source_timestamp_utc=self.t0 + timedelta(seconds=60),
                source_sequence=2,
            ),
        ]

        res = self.etiquetador.madurar(caso, ticks, direction="LONG")
        self.assertTrue(res.exito)
        eti = res.datos
        self.assertEqual("LONG", eti.direction)
        self.assertEqual("MATURE", eti.status)
        self.assertEqual("TAKE_PROFIT", eti.outcome)
        self.assertEqual(500100, eti.entry_price)
        self.assertEqual(502100, eti.exit_price)
        self.assertEqual(499600, eti.stop_barrier_price)
        self.assertEqual(502100, eti.target_barrier_price)
        self.assertEqual(2000, eti.realized_points)
        self.assertFalse(eti.is_ambiguous_tie)

    def test_tabla_7_2_fila_2_short_stop(self) -> None:
        """Tabla 7.2 Fila 2: SHORT entra bid 500000 -> Stop 500500, Target 498000. Primer ask 500500 -> STOP_LOSS."""
        caso = self._crear_caso_test(bid=500000, ask=500100)

        ticks = [
            QuoteTickPayloadV1(
                bid=500460,
                ask=500500,  # Toca stop
                price_scale=100,
                bid_size=10,
                ask_size=10,
                source_timestamp_utc=self.t0 + timedelta(seconds=45),
                source_sequence=1,
            ),
        ]

        res = self.etiquetador.madurar(caso, ticks, direction="SHORT")
        self.assertTrue(res.exito)
        eti = res.datos
        self.assertEqual("SHORT", eti.direction)
        self.assertEqual("STOP_LOSS", eti.outcome)
        self.assertEqual(500000, eti.entry_price)
        self.assertEqual(500500, eti.exit_price)
        self.assertEqual(500500, eti.stop_barrier_price)
        self.assertEqual(498000, eti.target_barrier_price)
        self.assertEqual(-500, eti.realized_points)
        self.assertFalse(eti.is_ambiguous_tie)

    def test_tabla_7_2_fila_3_empate_stop_first_ambiguo(self) -> None:
        """Tabla 7.2 Fila 3 / CA-14: Tick atómico ambiguo que abarca stop y target resuelve STOP_FIRST con AMBIGUOUS_STOP_FIRST."""
        caso = self._crear_caso_test(bid=500000, ask=500100)

        # Tick con spread anómalo o salto que toca bid <= 499600 y ask >= 502100 simultáneamente
        ticks = [
            QuoteTickPayloadV1(
                bid=499500,  # Cruza stop (<= 499600)
                ask=502200,  # Cruza target (>= 502100)
                price_scale=100,
                bid_size=10,
                ask_size=10,
                source_timestamp_utc=self.t0 + timedelta(seconds=10),
                source_sequence=1,
            )
        ]

        res = self.etiquetador.madurar(caso, ticks, direction="LONG")
        self.assertTrue(res.exito)
        eti = res.datos
        self.assertEqual("STOP_LOSS", eti.outcome)
        self.assertEqual(499600, eti.exit_price)
        self.assertTrue(eti.is_ambiguous_tie)
        self.assertIn("AMBIGUOUS_STOP_FIRST", eti.reason_codes)

    def test_expiracion_de_horizonte_5_minutos(self) -> None:
        """Si no toca stop ni target dentro de los 5 minutos, cierra por expiración de horizonte."""
        caso = self._crear_caso_test(bid=500000, ask=500100)

        # Ticks dentro de barreras hasta el final del horizonte
        ticks = [
            QuoteTickPayloadV1(
                bid=500500,
                ask=500540,
                price_scale=100,
                bid_size=10,
                ask_size=10,
                source_timestamp_utc=self.t0 + timedelta(seconds=299),
                source_sequence=1,
            ),
        ]

        res = self.etiquetador.madurar(caso, ticks, direction="LONG")
        self.assertTrue(res.exito)
        eti = res.datos
        self.assertEqual("HORIZON_EXPIRATION", eti.outcome)
        self.assertEqual(500500, eti.exit_price)
        self.assertEqual(400, eti.realized_points)  # 500500 - 500100 = +400 pts
        self.assertIn("HORIZON_TIMEOUT", eti.reason_codes)

    def test_ticks_vacios_marca_etiqueta_invalida(self) -> None:
        """Sin ticks de horizonte, la etiqueta es INVALID."""
        caso = self._crear_caso_test(bid=500000, ask=500100)

        res = self.etiquetador.madurar(caso, [], direction="LONG")
        self.assertTrue(res.exito)
        eti = res.datos
        self.assertEqual("INVALID", eti.status)
        self.assertEqual("INVALID", eti.outcome)
        self.assertIn("INSUFFICIENT_OR_UNKNOWN_DATA", eti.reason_codes)


if __name__ == "__main__":
    unittest.main()
