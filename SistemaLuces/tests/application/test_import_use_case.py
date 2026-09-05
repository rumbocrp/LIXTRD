"""Pruebas del Caso de Uso importar_demo_observada (SPEC-001 §5.2, CA-19)."""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from sistema_luces.application.import_use_case import EjecutorImportacionDemo
from sistema_luces.domain.api import SolicitudImportacionDemo
from sistema_luces.imports.staging import ValidadorStaging


class TestImportarDemoObservada(unittest.TestCase):
    """Verifica el flujo público de importación y reconciliación."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.staging_dir = Path(self.temp_dir.name)
        self.validador = ValidadorStaging(base_dir=self.staging_dir)
        self.ejecutor = EjecutorImportacionDemo(validador_staging=self.validador)
        self.account_hash = hashlib.sha256(b"demo-account-789").hexdigest()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_importacion_y_reconciliacion_completa(self) -> None:
        data = [
            {
                "trade_id": "t-1",
                "symbol": "US500",
                "side": "BUY",
                "quantity": 100,
                "entry_time": "2026-08-29T14:30:00Z",
                "entry_price": 500040,
                "exit_time": "2026-08-29T14:32:00Z",
                "exit_price": 502040,
                "pnl": 20.0,
            }
        ]
        raw_bytes = json.dumps(data).encode("utf-8")
        file_hash = hashlib.sha256(raw_bytes).hexdigest()
        (self.staging_dir / "trades.json").write_bytes(raw_bytes)

        solicitud = SolicitudImportacionDemo(
            correlation_id="00000000-0000-0000-0000-000000000001",
            environment="BROKER_DEMO_OBSERVED",
            staged_copy="trades.json",
            expected_sha256=file_hash,
            adapter_version="ctrader-json-v1",
            expected_demo_account_hash=self.account_hash,
        )

        res = self.ejecutor.ejecutar(solicitud)
        self.assertTrue(res.exito)
        resumen = res.datos
        self.assertEqual("BROKER_DEMO_OBSERVED", resumen.environment)
        self.assertEqual(1, resumen.accepted_count)


if __name__ == "__main__":
    unittest.main()
