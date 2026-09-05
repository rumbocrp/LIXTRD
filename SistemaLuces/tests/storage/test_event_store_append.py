"""Pruebas de append atomico, recepcion de sobre y recibo en ArchivoEventos."""
from datetime import datetime, timezone
import unittest
from pathlib import Path
import tempfile

from sistema_luces.domain.event import SobreEventoV1, compute_payload_hash
from sistema_luces.storage.event_store import ArchivoEventos
from sistema_luces.storage.sqlite import inicializar_db


class EventStoreAppendTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "luces.db"
        inicializar_db(self.db_path)
        self.store = ArchivoEventos(self.db_path)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_anexar_evento_valido_retorna_recibo_y_persiste(self) -> None:
        payload = {"bid": 500000, "ask": 500025, "price_scale": 100, "source_timestamp_utc": "2026-08-29T14:30:00Z"}
        payload_h = compute_payload_hash(payload)
        now = datetime(2026, 8, 29, 14, 30, 0, tzinfo=timezone.utc)
        evento = SobreEventoV1(
            event_id="11111111-1111-1111-1111-111111111111",
            event_type="QUOTE_TICK",
            schema_version=1,
            occurred_at_utc=now,
            received_at_utc=now,
            persisted_at_utc=None,
            source="replay",
            environment="REPLAY",
            source_account_id_hash=None,
            instrument="US500",
            symbol_id=None,
            source_sequence=1,
            correlation_id="11111111-1111-1111-1111-111111111111",
            causation_id=None,
            payload_hash=payload_h,
            previous_hash=None,
            payload=payload,
        )

        res = self.store.anexar(evento)
        self.assertTrue(res.exito)
        recibo = res.datos
        self.assertEqual(recibo.event_id, evento.event_id)
        self.assertEqual(recibo.row_id, 1)
        self.assertEqual(recibo.payload_hash, payload_h)
        self.assertFalse(recibo.idempotent)
        self.assertIsNotNone(recibo.persisted_at_utc)

    def test_anexar_evento_live_rechazado_con_environment_not_allowed(self) -> None:
        payload = {"status": "OPEN"}
        now = datetime(2026, 8, 29, 14, 30, 0, tzinfo=timezone.utc)
        evento = SobreEventoV1(
            event_id="22222222-2222-2222-2222-222222222222",
            event_type="SESSION_STATUS",
            schema_version=1,
            occurred_at_utc=now,
            received_at_utc=now,
            persisted_at_utc=None,
            source="replay",
            environment="LIVE",  # type: ignore
            source_account_id_hash=None,
            instrument="US500",
            symbol_id=None,
            source_sequence=1,
            correlation_id="22222222-2222-2222-2222-222222222222",
            causation_id=None,
            payload_hash=compute_payload_hash(payload),
            previous_hash=None,
            payload=payload,
        )
        res = self.store.anexar(evento)
        self.assertFalse(res.exito)
        self.assertEqual(res.error.codigo, "ENVIRONMENT_NOT_ALLOWED")
