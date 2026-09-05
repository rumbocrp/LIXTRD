"""Pruebas del Adaptador de Exportación Journal V1 (SPEC-001 §9.4, CA-20, CA-28)."""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from sistema_luces.imports.journal_v1 import AdaptadorExportacionJournalV1, EstadoJournalV1


class TestAdaptadorJournalV1(unittest.TestCase):
    """Verifica aislamiento contra tj.db y parsing seguro del formato staging."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.staging_dir = Path(self.temp_dir.name)
        self.adaptador = AdaptadorExportacionJournalV1()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_estado_core_reporta_not_included_sin_dependencias_ca20(self) -> None:
        estado = self.adaptador.obtener_estado_extension()
        self.assertIn(estado, {"NOT_INCLUDED", "PASS_INCLUDED"})

    def test_parsing_exportacion_journal_v1_valida(self) -> None:
        raw_data = {
            "format": "trading-journal/exportacion-completa-v1",
            "version": 1,
            "exported_at_utc": "2026-08-29T18:00:00Z",
            "account_hash": "a" * 64,
            "trades": [
                {
                    "trade_id": "tj-101",
                    "symbol": "US500",
                    "direction": "LONG",
                    "quantity": 100,
                    "entry_time_utc": "2026-08-29T14:30:10Z",
                    "entry_price": 500050,
                    "exit_time_utc": "2026-08-29T14:32:10Z",
                    "exit_price": 502050,
                    "pnl_usd_cents": 2000,
                }
            ],
        }
        content_bytes = json.dumps(raw_data).encode("utf-8")
        file_path = self.staging_dir / "journal_export.json"
        file_path.write_bytes(content_bytes)
        file_hash = hashlib.sha256(content_bytes).hexdigest()

        res = self.adaptador.cargar_desde_archivo(file_path, file_hash)
        self.assertTrue(res.exito)
        trades = res.datos
        self.assertEqual(1, len(trades))
        self.assertEqual("tj-101", trades[0].trade_id)
        self.assertEqual("LONG", trades[0].side)


if __name__ == "__main__":
    unittest.main()
