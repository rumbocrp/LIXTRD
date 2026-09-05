"""Pruebas de consulta de eventos, filtrado y paginacion (CA-4)."""
from datetime import datetime, timezone, timedelta
import unittest
from pathlib import Path
import tempfile

from sistema_luces.domain.event import SobreEventoV1, compute_payload_hash
from sistema_luces.storage.event_store import ArchivoEventos
from sistema_luces.storage.sqlite import inicializar_db
from sistema_luces.storage import ConsultaEventos


class EventQueryAndPaginationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "luces.db"
        inicializar_db(self.db_path)
        self.store = ArchivoEventos(self.db_path)
        self.start = datetime(2026, 8, 29, 14, 0, 0, tzinfo=timezone.utc)
        # Populate 15 events
        for i in range(1, 16):
            t = self.start + timedelta(seconds=i * 10)
            p = {"tick": i}
            e = SobreEventoV1(
                event_id=f"77777777-7777-7777-7777-77777777{i:04d}",
                event_type="QUOTE_TICK" if i % 2 == 1 else "HEARTBEAT",
                schema_version=1,
                occurred_at_utc=t,
                received_at_utc=t,
                persisted_at_utc=None,
                source="replay",
                environment="REPLAY",
                source_account_id_hash=None,
                instrument="US500",
                symbol_id=None,
                source_sequence=i,
                correlation_id="77777777-7777-7777-7777-000000000000",
                causation_id=None,
                payload_hash=compute_payload_hash(p),
                previous_hash=None,
                payload=p,
            )
            self.store.anexar(e)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_consulta_con_limite_y_paginacion_por_cursor(self) -> None:
        q1 = ConsultaEventos(limit=5)
        r1 = self.store.leer(q1)
        self.assertTrue(r1.exito)
        self.assertEqual(len(r1.datos.events), 5)
        self.assertIsNotNone(r1.datos.next_cursor)

        q2 = ConsultaEventos(cursor=r1.datos.next_cursor, limit=5)
        r2 = self.store.leer(q2)
        self.assertTrue(r2.exito)
        self.assertEqual(len(r2.datos.events), 5)
        self.assertNotEqual(r1.datos.events[0].event_id, r2.datos.events[0].event_id)

    def test_consulta_filtra_por_tipo_de_evento(self) -> None:
        q = ConsultaEventos(event_types=("QUOTE_TICK",), limit=20)
        r = self.store.leer(q)
        self.assertTrue(r.exito)
        self.assertEqual(len(r.datos.events), 8)  # 1, 3, 5, 7, 9, 11, 13, 15
        for ev in r.datos.events:
            self.assertEqual(ev.event_type, "QUOTE_TICK")
