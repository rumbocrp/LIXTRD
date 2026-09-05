"""Pruebas de auditoria y casos de borde transaccionales de almacenamiento."""
from datetime import datetime, timezone
import unittest
from pathlib import Path
import tempfile
import sqlite3

from sistema_luces.domain.event import SobreEventoV1, compute_payload_hash
from sistema_luces.storage.event_store import ArchivoEventos, RegistroAuditoria, EntradaAuditoriaV1, LoteEventosV1, RangoEventos
from sistema_luces.storage.sqlite import inicializar_db, conectar_db


class AuditAndEdgeCaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "luces.db"
        inicializar_db(self.db_path)
        self.store = ArchivoEventos(self.db_path)
        self.audit = RegistroAuditoria(self.db_path)
        self.now = datetime(2026, 8, 29, 14, 30, 0, tzinfo=timezone.utc)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_registro_auditoria_anexa_y_calcula_hash(self) -> None:
        entrada = EntradaAuditoriaV1(
            audit_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            actor="operator",
            operation="KILL_SWITCH_ACTIVATE",
            result="SUCCESS",
            correlation_id="bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
            details={"reason": "Manual intervention"},
        )
        res = self.audit.registrar(entrada)
        self.assertTrue(res.exito)
        recibo = res.datos
        self.assertEqual(recibo.audit_id, entrada.audit_id)
        self.assertEqual(recibo.row_id, 1)
        self.assertEqual(len(recibo.entry_hash), 64)

        # Trigger check on audit_log
        with conectar_db(self.db_path) as conn:
            cur = conn.cursor()
            with self.assertRaises(sqlite3.IntegrityError):
                cur.execute("UPDATE audit_log SET result='FAILED' WHERE row_id=1;")
            with self.assertRaises(sqlite3.IntegrityError):
                cur.execute("DELETE FROM audit_log WHERE row_id=1;")

    def test_lote_con_evento_conflictivo_revierte_completamente(self) -> None:
        # First append event 1
        p1 = {"v": 100}
        e1 = SobreEventoV1(
            event_id="99999999-9999-9999-9999-999999990001",
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
            correlation_id="99999999-9999-9999-9999-000000000000",
            causation_id=None,
            payload_hash=compute_payload_hash(p1),
            previous_hash=None,
            payload=p1,
        )
        self.store.anexar(e1)

        # Batch with e2 (new) and e1_conflicting (same id, different payload)
        p2 = {"v": 200}
        e2 = SobreEventoV1(
            event_id="99999999-9999-9999-9999-999999990002",
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
            correlation_id="99999999-9999-9999-9999-000000000000",
            causation_id=None,
            payload_hash=compute_payload_hash(p2),
            previous_hash=None,
            payload=p2,
        )
        p1_conflict = {"v": 999}
        e1_conflict = SobreEventoV1(
            event_id="99999999-9999-9999-9999-999999990001",
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
            source_sequence=3,
            correlation_id="99999999-9999-9999-9999-000000000000",
            causation_id=None,
            payload_hash=compute_payload_hash(p1_conflict),
            previous_hash=None,
            payload=p1_conflict,
        )
        lote = LoteEventosV1(batch_id="batch-conflict-01", root_hash="dummy", events=(e2, e1_conflict))
        batch_res = self.store.anexar_lote(lote)
        self.assertFalse(batch_res.exito)
        self.assertEqual(batch_res.error.codigo, "INTEGRITY_ERROR")

        # Check that e2 was NOT committed (rollback was atomic)
        counts = self.store.reconstruir_proyecciones().datos
        self.assertEqual(counts["_total"], 1)
