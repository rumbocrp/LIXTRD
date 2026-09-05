"""Pruebas del Caso de Uso consultar_vista (SPEC-001 §5.2)."""

import unittest

from sistema_luces.application.query_use_case import ConsultorVistas
from sistema_luces.domain.api import SolicitudConsulta


class TestConsultarVista(unittest.TestCase):
    """Verifica la consulta de vistas del sistema a través del caso de uso raíz."""

    def setUp(self) -> None:
        self.consultor = ConsultorVistas()

    def test_consulta_vista_feed_vacia(self) -> None:
        solicitud = SolicitudConsulta(
            correlation_id="00000000-0000-0000-0000-000000000001",
            environment="REPLAY",
            view="FEED",
            as_of_event_id=None,
            cursor=None,
            limit=50,
        )
        res = self.consultor.consultar(solicitud)
        self.assertTrue(res.exito)
        vista = res.datos
        self.assertEqual("US500", vista.instrument)
        self.assertEqual("NO_DATA", vista.health_state)
        self.assertEqual("YELLOW", vista.light)
        self.assertEqual((), vista.documents)

    def test_consulta_vista_feed_con_eventos(self) -> None:
        from datetime import datetime, timezone
        import hashlib
        from sistema_luces.domain.event import SobreEventoV1, canonical_json_bytes

        payload = {"bid": 500000, "ask": 500040, "instrument": "US500"}
        c_bytes = canonical_json_bytes(payload)
        now = datetime.now(timezone.utc)
        evento = SobreEventoV1(
            event_id="00000000-0000-0000-0000-000000000010",
            event_type="QUOTE_TICK",
            schema_version=1,
            occurred_at_utc=now,
            received_at_utc=now,
            persisted_at_utc=None,
            source="replay",
            environment="REPLAY",
            source_account_id_hash=None,
            instrument="US500",
            symbol_id="US500",
            source_sequence=1,
            correlation_id="00000000-0000-0000-0000-000000000001",
            causation_id=None,
            payload_hash=hashlib.sha256(c_bytes).hexdigest(),
            previous_hash=None,
            payload=payload,
        )
        self.consultor.proyector.actualizar_desde_evento(evento)

        solicitud = SolicitudConsulta(
            correlation_id="00000000-0000-0000-0000-000000000001",
            environment="REPLAY",
            view="FEED",
            as_of_event_id=None,
            cursor=None,
            limit=50,
        )
        res = self.consultor.consultar(solicitud)
        self.assertTrue(res.exito)
        vista = res.datos
        self.assertEqual("US500", vista.instrument)
        self.assertEqual("REPLAY", vista.environment)
        self.assertEqual("HEALTHY", vista.health_state)
        self.assertEqual(1, len(vista.documents))


if __name__ == "__main__":
    unittest.main()
