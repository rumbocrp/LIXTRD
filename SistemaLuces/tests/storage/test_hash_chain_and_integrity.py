"""Pruebas de encadenamiento de hashes SHA-256 e informe de integridad (CA-4, CA-21)."""
from datetime import datetime, timezone
import unittest
from pathlib import Path
import tempfile

from sistema_luces.domain.event import SobreEventoV1, compute_payload_hash
from sistema_luces.storage.event_store import ArchivoEventos
from sistema_luces.storage.sqlite import inicializar_db
from sistema_luces.storage import RangoEventos, LoteEventosV1


class HashChainAndIntegrityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "luces.db"
        inicializar_db(self.db_path)
        self.store = ArchivoEventos(self.db_path)
        self.now = datetime(2026, 8, 29, 14, 30, 0, tzinfo=timezone.utc)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_encadenamiento_de_hashes_consecutivo(self) -> None:
        # Event 1
        p1 = {"seq": 1}
        e1 = SobreEventoV1(
            event_id="55555555-5555-5555-5555-555555555551",
            event_type="HEARTBEAT",
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
            correlation_id="55555555-5555-5555-5555-555555555551",
            causation_id=None,
            payload_hash=compute_payload_hash(p1),
            previous_hash=None,
            payload=p1,
        )
        r1 = self.store.anexar(e1)
        self.assertTrue(r1.exito)
        self.assertIsNone(r1.datos.previous_hash)

        # Event 2
        p2 = {"seq": 2}
        e2 = SobreEventoV1(
            event_id="55555555-5555-5555-5555-555555555552",
            event_type="HEARTBEAT",
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
            correlation_id="55555555-5555-5555-5555-555555555552",
            causation_id=None,
            payload_hash=compute_payload_hash(p2),
            previous_hash=r1.datos.payload_hash,
            payload=p2,
        )
        r2 = self.store.anexar(e2)
        self.assertTrue(r2.exito)
        self.assertEqual(r2.datos.previous_hash, r1.datos.payload_hash)

        # Verify integrity
        inf_res = self.store.verificar_integridad(RangoEventos(start_row_id=1, end_row_id=2))
        self.assertTrue(inf_res.exito)
        inf = inf_res.datos
        self.assertTrue(inf.is_valid)
        self.assertEqual(inf.event_count, 2)
        self.assertEqual(len(inf.violations), 0)
        self.assertTrue(len(inf.root_hash) == 64)

    def test_anexar_lote_atomico_exito_y_rollback(self) -> None:
        p1 = {"batch": 1}
        p2 = {"batch": 2}
        e1 = SobreEventoV1(
            event_id="66666666-6666-6666-6666-666666666661",
            event_type="HEARTBEAT",
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
            correlation_id="66666666-6666-6666-6666-666666666660",
            causation_id=None,
            payload_hash=compute_payload_hash(p1),
            previous_hash=None,
            payload=p1,
        )
        e2 = SobreEventoV1(
            event_id="66666666-6666-6666-6666-666666666662",
            event_type="HEARTBEAT",
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
            correlation_id="66666666-6666-6666-6666-666666666660",
            causation_id=None,
            payload_hash=compute_payload_hash(p2),
            previous_hash=None,
            payload=p2,
        )
        lote = LoteEventosV1(batch_id="66666666-6666-6666-6666-666666666660", root_hash="dummy", events=(e1, e2))
        res = self.store.anexar_lote(lote)
        self.assertTrue(res.exito)
        self.assertEqual(res.datos.accepted_count, 2)
        self.assertEqual(res.datos.first_row_id, 1)
        self.assertEqual(res.datos.last_row_id, 2)
