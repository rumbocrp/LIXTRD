"""Pruebas de la Importación de Ejecuciones Demo (SPEC-001 §5.2.1, CA-3, CA-19)."""

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest

from sistema_luces.domain.api import SolicitudImportacionDemo
from sistema_luces.imports.demo import ImportadorDemo
from sistema_luces.imports.staging import ValidadorStaging


class TestImportacionDemo(unittest.TestCase):
    """Verifica validación de copia staged, hash SHA-256, límites de tamaño y parsing."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.staging_path = Path(self.temp_dir.name)
        self.validador = ValidadorStaging(base_dir=self.staging_path, max_size_bytes=52_428_800)
        self.importador = ImportadorDemo(validador_staging=self.validador)
        self.account_hash = hashlib.sha256(b"demo-account-123").hexdigest()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_validacion_staging_seguro_y_hash_sha256(self) -> None:
        file_content = json.dumps([
            {
                "trade_id": "tr-001",
                "symbol": "US500",
                "side": "BUY",
                "quantity": 100,
                "entry_time": "2026-08-29T14:30:05Z",
                "entry_price": 500040,
                "exit_time": "2026-08-29T14:32:00Z",
                "exit_price": 502040,
                "pnl": 20.0,
            }
        ]).encode("utf-8")
        file_hash = hashlib.sha256(file_content).hexdigest()

        # Guardar en staging
        target_file = self.staging_path / "demo_trades_20260829.json"
        target_file.write_bytes(file_content)

        solicitud = SolicitudImportacionDemo(
            correlation_id="00000000-0000-0000-0000-000000000001",
            environment="BROKER_DEMO_OBSERVED",
            staged_copy="demo_trades_20260829.json",
            expected_sha256=file_hash,
            adapter_version="ctrader-json-v1",
            expected_demo_account_hash=self.account_hash,
        )

        res = self.importador.importar(solicitud)
        self.assertTrue(res.exito)
        resumen = res.datos
        self.assertEqual("BROKER_DEMO_OBSERVED", resumen.environment)
        self.assertEqual(1, resumen.accepted_count)
        self.assertEqual(0, resumen.rejected_count)

    def test_rechazo_por_hash_sha256_invalido(self) -> None:
        target_file = self.staging_path / "corrupt_trades.json"
        target_file.write_bytes(b"corrupted content")

        solicitud = SolicitudImportacionDemo(
            correlation_id="00000000-0000-0000-0000-000000000002",
            environment="BROKER_DEMO_OBSERVED",
            staged_copy="corrupt_trades.json",
            expected_sha256="a" * 64,
            adapter_version="ctrader-json-v1",
            expected_demo_account_hash=self.account_hash,
        )

        res = self.importador.importar(solicitud)
        self.assertFalse(res.exito)
        self.assertEqual("INTEGRITY_ERROR", res.error.codigo)

    def test_rechazo_path_traversal(self) -> None:
        solicitud = SolicitudImportacionDemo(
            correlation_id="00000000-0000-0000-0000-000000000003",
            environment="BROKER_DEMO_OBSERVED",
            staged_copy="../etc/passwd",
            expected_sha256="a" * 64,
            adapter_version="ctrader-json-v1",
            expected_demo_account_hash=self.account_hash,
        )
        res = self.importador.importar(solicitud)
        self.assertFalse(res.exito)
        self.assertEqual("VALIDATION_ERROR", res.error.codigo)


if __name__ == "__main__":
    unittest.main()
