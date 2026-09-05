"""Pruebas de Proyecciones Reconstruibles desde el Event Log (SPEC-001 §9.1, CA-21)."""

from datetime import datetime, timezone
import unittest

from sistema_luces.domain.api import DocumentoVistaV1, SolicitudConsulta
from sistema_luces.domain.event import QuoteTickPayloadV1, SobreEventoV1, compute_payload_hash
from sistema_luces.observability.projections import ProyectorVistas


def _crear_evento_tick(seq: int, bid: int = 500000, ask: int = 500040) -> SobreEventoV1:
    t0 = datetime(2026, 8, 29, 14, 30, 0, tzinfo=timezone.utc)
    payload = {
        "bid": bid,
        "ask": ask,
        "price_scale": 100,
        "bid_size": 10,
        "ask_size": 10,
        "source_timestamp_utc": t0.isoformat(),
        "source_sequence": seq,
    }
    return SobreEventoV1(
        event_id=f"00000000-0000-0000-0000-{seq:012d}",
        event_type="QUOTE_TICK",
        schema_version=1,
        occurred_at_utc=t0,
        received_at_utc=t0,
        persisted_at_utc=t0,
        source="replay",
        environment="REPLAY",
        source_account_id_hash=None,
        instrument="US500",
        symbol_id="US500",
        source_sequence=seq,
        payload=payload,
        payload_hash=compute_payload_hash(payload),
        previous_hash=None,
        causation_id=None,
        correlation_id=f"00000000-0000-0000-0000-{seq:012d}",
    )


class TestProyeccionesReconstruibles(unittest.TestCase):
    """Verifica reconstrucción determinista de vistas desde el log de eventos."""

    def setUp(self) -> None:
        self.proyector = ProyectorVistas()

    def test_actualizacion_y_consulta_de_vista(self) -> None:
        ev1 = _crear_evento_tick(1, bid=500000, ask=500040)
        res_act = self.proyector.actualizar_desde_evento(ev1)
        self.assertTrue(res_act.exito)

        solicitud = SolicitudConsulta(
            correlation_id="00000000-0000-0000-0000-000000000001",
            environment="REPLAY",
            view="FEED",
            as_of_event_id=None,
            cursor=None,
            limit=50,
        )
        res_vista = self.proyector.consultar(solicitud)
        self.assertTrue(res_vista.exito)
        vista = res_vista.datos
        self.assertEqual("US500", vista.instrument)
        self.assertEqual("REPLAY", vista.environment)
        self.assertGreater(len(vista.documents), 0)

    def test_reconstruccion_completa_produce_estado_identico(self) -> None:
        eventos = [_crear_evento_tick(i, bid=500000 + i * 10, ask=500040 + i * 10) for i in range(1, 10)]
        for ev in eventos:
            self.proyector.actualizar_desde_evento(ev)

        solicitud = SolicitudConsulta(
            correlation_id="00000000-0000-0000-0000-000000000002",
            environment="REPLAY",
            view="FEED",
            as_of_event_id=None,
            cursor=None,
            limit=50,
        )
        vista1 = self.proyector.consultar(solicitud).datos

        # Reconstruir en una nueva instancia
        nuevo_proyector = ProyectorVistas()
        nuevo_proyector.reconstruir(eventos)
        vista2 = nuevo_proyector.consultar(solicitud).datos

        self.assertEqual(len(vista1.documents), len(vista2.documents))
        self.assertEqual(vista1.documents[0].document_hash, vista2.documents[0].document_hash)


if __name__ == "__main__":
    unittest.main()
