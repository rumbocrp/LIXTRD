"""Pruebas del Caso de Uso ejecutar_shadow (SPEC-001 §5.2, CA-1, CA-2, CA-3)."""

from datetime import datetime, timezone
import hashlib
import unittest

from sistema_luces.application.shadow_use_case import EjecutorShadow
from sistema_luces.domain.api import SolicitudShadow


class TestEjecutarShadow(unittest.TestCase):
    """Verifica ejecución de shadow mode con adaptador read-only y sin emisión de órdenes."""

    def setUp(self) -> None:
        self.ejecutor = EjecutorShadow()
        self.account_hash = hashlib.sha256(b"demo-account-456").hexdigest()

    def test_ejecucion_shadow_valida(self) -> None:
        solicitud = SolicitudShadow(
            correlation_id="00000000-0000-0000-0000-000000000001",
            environment="SHADOW",
            source_profile_version="ctrader-demo-v1",
            capabilities_manifest_hash="a" * 64,
            expected_demo_account_hash=self.account_hash,
        )

        res = self.ejecutor.ejecutar(solicitud)
        self.assertTrue(res.exito)
        resumen = res.datos
        self.assertEqual("SHADOW", resumen.environment)
        self.assertEqual(0, resumen.rejected_event_count)


if __name__ == "__main__":
    unittest.main()
