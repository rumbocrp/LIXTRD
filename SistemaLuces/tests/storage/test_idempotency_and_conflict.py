"""Pruebas de idempotencia exacta y deteccion de conflictos (OPT-6, CA-5)."""
from datetime import datetime, timezone
import unittest
from pathlib import Path
import tempfile

from sistema_luces.domain.event import SobreEventoV1, compute_payload_hash
from sistema_luces.storage.event_store import ArchivoEventos
from sistema_luces.storage.sqlite import inicializar_db


class IdempotencyAndConflictTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "luces.db"
        inicializar_db(self.db_path)
        self.store = ArchivoEventos(self.db_path)
        self.now = datetime(2026, 8, 29, 14, 30, 0, tzinfo=timezone.utc)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_evento_duplicado_identico_devuelve_recibo_original_con_idempotent_true(self) -> None:
        payload = {"bid": 500000, "ask": 500025, "price_scale": 100}
        h = compute_payload_hash(payload)
        evento = SobreEventoV1(
            event_id="33333333-3333-3333-3333-333333333333",
            event_type="QUOTE_TICK",
            schema_version=1,
            occurred_at_utc=self.now,
            received_at_utc=self.now,
            persisted_at_utc=None,
            source="replay",
            environment="REPLAY",
            source_account_id_hash=None,
            instrument="US500",
            symbol_id=None,
            source_sequence=1,
            correlation_id="33333333-3333-3333-3333-333333333333",
            causation_id=None,
            payload_hash=h,
            previous_hash=None,
            payload=payload,
        )
        res1 = self.store.anexar(evento)
        self.assertTrue(res1.exito)
        self.assertFalse(res1.datos.idempotent)
        self.assertEqual(res1.datos.row_id, 1)

        # Second identical append
        res2 = self.store.anexar(evento)
        self.assertTrue(res2.exito)
        self.assertTrue(res2.datos.idempotent)
        self.assertEqual(res2.datos.row_id, 1)
        self.assertEqual(res2.datos.event_id, evento.event_id)

    def test_mismo_event_id_con_contenido_distinto_retorna_integrity_error_y_no_muta(self) -> None:
        p1 = {"bid": 500000, "ask": 500025}
        evento1 = SobreEventoV1(
            event_id="44444444-4444-4444-4444-444444444444",
            event_type="QUOTE_TICK",
            schema_version=1,
            occurred_at_utc=self.now,
            received_at_utc=self.now,
            persisted_at_utc=None,
            source="replay",
            environment="REPLAY",
            source_account_id_hash=None,
            instrument="US500",
            symbol_id=None,
            source_sequence=1,
            correlation_id="44444444-4444-4444-4444-444444444444",
            causation_id=None,
            payload_hash=compute_payload_hash(p1),
            previous_hash=None,
            payload=p1,
        )
        res1 = self.store.anexar(evento1)
        self.assertTrue(res1.exito)

        p2 = {"bid": 500100, "ask": 500125}  # different payload
        evento2 = SobreEventoV1(
            event_id="44444444-4444-4444-4444-444444444444",  # same ID!
            event_type="QUOTE_TICK",
            schema_version=1,
            occurred_at_utc=self.now,
            received_at_utc=self.now,
            persisted_at_utc=None,
            source="replay",
            environment="REPLAY",
            source_account_id_hash=None,
            instrument="US500",
            symbol_id=None,
            source_sequence=2,
            correlation_id="44444444-4444-4444-4444-444444444444",
            causation_id=None,
            payload_hash=compute_payload_hash(p2),
            previous_hash=None,
            payload=p2,
        )
        res2 = self.store.anexar(evento2)
        self.assertFalse(res2.exito)
        self.assertEqual(res2.error.codigo, "INTEGRITY_ERROR")
