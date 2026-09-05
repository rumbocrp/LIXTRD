"""Pruebas de configuracion SQLite, WAL, FK y triggers inmutables."""
import sqlite3
import unittest
from pathlib import Path
import tempfile

from sistema_luces.storage.sqlite import inicializar_db, conectar_db


class SqliteConnectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_luces.db"

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_inicializar_db_activa_wal_y_foreign_keys(self) -> None:
        res = inicializar_db(self.db_path)
        self.assertTrue(res.exito)
        with conectar_db(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute("PRAGMA foreign_keys;")
            fk_val = cur.fetchone()[0]
            self.assertEqual(fk_val, 1)

            cur.execute("PRAGMA journal_mode;")
            mode = cur.fetchone()[0]
            self.assertIn(mode.upper(), ["WAL", "MEMORY"])

    def test_trg_prevent_update_delete_en_event_log(self) -> None:
        inicializar_db(self.db_path)
        with conectar_db(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO event_log (
                    event_id, event_type, schema_version, occurred_at_utc, received_at_utc,
                    persisted_at_utc, source, environment, instrument, correlation_id,
                    payload_hash, payload_json
                ) VALUES (
                    '00000000-0000-0000-0000-000000000001', 'HEARTBEAT', 1,
                    '2026-08-29T12:00:00Z', '2026-08-29T12:00:00Z', '2026-08-29T12:00:00Z',
                    'replay', 'REPLAY', 'US500', '00000000-0000-0000-0000-000000000001',
                    'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855', '{}'
                )
                """
            )
            conn.commit()

            # UPDATE must fail
            with self.assertRaises(sqlite3.IntegrityError):
                cur.execute("UPDATE event_log SET event_type='QUOTE_TICK' WHERE row_id=1;")

            # DELETE must fail
            with self.assertRaises(sqlite3.IntegrityError):
                cur.execute("DELETE FROM event_log WHERE row_id=1;")
