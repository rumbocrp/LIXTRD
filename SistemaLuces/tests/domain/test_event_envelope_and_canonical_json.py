"""Pruebas para sobre de eventos, JSON canónico y payloads (SPEC-001 §6.1, §6.2, §6.3, CA-4)."""

from datetime import datetime, timezone
import hashlib
import unittest

from sistema_luces.domain.event import (
    DepthDeltaPayloadV1,
    GapDetectedPayloadV1,
    QuoteTickPayloadV1,
    SessionStatusPayloadV1,
    SobreEventoV1,
    canonical_json_bytes,
    canonical_json_dumps,
    compute_payload_hash,
    validar_payload_quote_tick,
    validar_sobre_evento,
)


class EventEnvelopeAndCanonicalJsonTests(unittest.TestCase):
    def setUp(self) -> None:
        self.now_utc = datetime(2026, 8, 29, 14, 30, 0, 123456, tzinfo=timezone.utc)
        self.uuid_1 = "11111111-1111-1111-1111-111111111111"
        self.uuid_2 = "22222222-2222-2222-2222-222222222222"

    def test_canonical_json_ordena_claves_y_elimina_espacios(self) -> None:
        obj = {"z": 1, "a": {"d": 4, "b": 2}, "c": [3, 1]}
        dumped = canonical_json_dumps(obj)
        self.assertEqual('{"a":{"b":2,"d":4},"c":[3,1],"z":1}', dumped)
        self.assertEqual(dumped.encode("utf-8"), canonical_json_bytes(obj))

    def test_canonical_json_formatea_fechas_utc_iso_con_z(self) -> None:
        obj = {"timestamp": self.now_utc}
        dumped = canonical_json_dumps(obj)
        self.assertEqual('{"timestamp":"2026-08-29T14:30:00.123456Z"}', dumped)

    def test_canonical_json_rechaza_nan_e_infinity(self) -> None:
        with self.assertRaises(ValueError):
            canonical_json_dumps({"valor": float("nan")})
        with self.assertRaises(ValueError):
            canonical_json_dumps({"valor": float("inf")})

    def test_sobre_evento_valida_estructura_y_payload_hash(self) -> None:
        payload = {"bid": 500000, "ask": 500040, "price_scale": 100}
        p_hash = compute_payload_hash(payload)

        sobre = SobreEventoV1(
            event_id=self.uuid_1,
            event_type="QUOTE_TICK",
            schema_version=1,
            occurred_at_utc=self.now_utc,
            received_at_utc=self.now_utc,
            persisted_at_utc=None,
            source="replay",
            environment="REPLAY",
            source_account_id_hash=None,
            instrument="US500",
            symbol_id="US500",
            source_sequence=1,
            correlation_id=self.uuid_2,
            causation_id=None,
            payload_hash=p_hash,
            previous_hash=None,
            payload=payload,
        )
        self.assertTrue(validar_sobre_evento(sobre).exito)

        # Inconsistent payload hash
        sobre_bad_hash = SobreEventoV1(
            event_id=self.uuid_1,
            event_type="QUOTE_TICK",
            schema_version=1,
            occurred_at_utc=self.now_utc,
            received_at_utc=self.now_utc,
            persisted_at_utc=None,
            source="replay",
            environment="REPLAY",
            source_account_id_hash=None,
            instrument="US500",
            symbol_id="US500",
            source_sequence=1,
            correlation_id=self.uuid_2,
            causation_id=None,
            payload_hash="b" * 64,
            previous_hash=None,
            payload=payload,
        )
        self.assertFalse(validar_sobre_evento(sobre_bad_hash).exito)

    def test_quote_tick_payload_valida_ask_mayor_igual_bid(self) -> None:
        tick_ok = QuoteTickPayloadV1(
            bid=500000,
            ask=500040,
            price_scale=100,
            bid_size=10,
            ask_size=15,
            source_timestamp_utc=self.now_utc,
            source_sequence=100,
        )
        self.assertTrue(validar_payload_quote_tick(tick_ok).exito)

        # Inverted bid > ask
        tick_bad = QuoteTickPayloadV1(
            bid=500050,
            ask=500040,
            price_scale=100,
            bid_size=10,
            ask_size=15,
            source_timestamp_utc=self.now_utc,
            source_sequence=100,
        )
        self.assertFalse(validar_payload_quote_tick(tick_bad).exito)

        # Zero or negative price
        tick_zero = QuoteTickPayloadV1(
            bid=0,
            ask=500040,
            price_scale=100,
            bid_size=None,
            ask_size=None,
            source_timestamp_utc=self.now_utc,
            source_sequence=None,
        )
        self.assertFalse(validar_payload_quote_tick(tick_zero).exito)


if __name__ == "__main__":
    unittest.main()
