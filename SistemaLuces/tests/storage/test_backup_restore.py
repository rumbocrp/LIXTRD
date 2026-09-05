"""Pruebas de verificacion de backup, restore y reconstruccion de proyecciones (CA-21)."""
from datetime import datetime, timezone
import unittest
from pathlib import Path
import tempfile

from sistema_luces.domain.event import SobreEventoV1, compute_payload_hash
from sistema_luces.storage.event_store import ArchivoEventos
from sistema_luces.storage.sqlite import inicializar_db
from sistema_luces.storage.backup import copiar_base_segura, verificar_backup_integro, restaurar_backup
from sistema_luces.storage import RangoEventos


class BackupRestoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.src_db = Path(self.temp_dir.name) / "source.db"
        self.backup_db = Path(self.temp_dir.name) / "backup.db"
        self.restored_db = Path(self.temp_dir.name) / "restored.db"
        inicializar_db(self.src_db)
        self.store = ArchivoEventos(self.src_db)

        now = datetime(2026, 8, 29, 14, 30, 0, tzinfo=timezone.utc)
        for i in range(1, 6):
            p = {"k": i}
            e = SobreEventoV1(
                event_id=f"88888888-8888-8888-8888-88888888{i:04d}",
                event_type="HEARTBEAT",
                schema_version=1,
                occurred_at_utc=now,
                received_at_utc=now,
                persisted_at_utc=None,
                source="replay",
                environment="REPLAY",
                source_account_id_hash=None,
                instrument="US500",
                symbol_id=None,
                source_sequence=i,
                correlation_id="88888888-8888-8888-8888-000000000000",
                causation_id=None,
                payload_hash=compute_payload_hash(p),
                previous_hash=None,
                payload=p,
            )
            self.store.anexar(e)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_copiar_verificar_y_restaurar_backup(self) -> None:
        # Step 1: Backup
        copy_res = copiar_base_segura(self.src_db, self.backup_db)
        self.assertTrue(copy_res.exito)

        # Step 2: Verify backup
        ver_res = verificar_backup_integro(self.backup_db)
        self.assertTrue(ver_res.exito)
        self.assertTrue(ver_res.datos["is_valid"])
        self.assertEqual(ver_res.datos["event_count"], 5)

        # Step 3: Restore
        rest_res = restaurar_backup(self.backup_db, self.restored_db)
        self.assertTrue(rest_res.exito)

        restored_store = ArchivoEventos(self.restored_db)
        inf_res = restored_store.verificar_integridad(RangoEventos(start_row_id=1, end_row_id=5))
        self.assertTrue(inf_res.exito)
        self.assertTrue(inf_res.datos.is_valid)
        self.assertEqual(inf_res.datos.event_count, 5)
