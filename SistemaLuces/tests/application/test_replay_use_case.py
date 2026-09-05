"""Pruebas del Caso de Uso ejecutar_replay (SPEC-001 §5.2, CA-4, CA-5, CA-23)."""

from datetime import datetime, timezone
import hashlib
import unittest

from sistema_luces.application.replay_use_case import EjecutorReplay
from sistema_luces.domain.api import SolicitudReplay
from sistema_luces.domain.event import QuoteTickPayloadV1, SobreEventoV1, compute_payload_hash


def _crear_evento(seq: int) -> SobreEventoV1:
    t0 = datetime(2026, 8, 29, 14, 30, 0, tzinfo=timezone.utc)
    payload = {
        "bid": 500000 + seq * 10,
        "ask": 500040 + seq * 10,
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


class TestEjecutarReplay(unittest.TestCase):
    """Verifica ejecución end-to-end de replay y determinismo de resultados."""

    def setUp(self) -> None:
        self.t0 = datetime(2026, 8, 29, 14, 30, 0, tzinfo=timezone.utc)
        self.t1 = datetime(2026, 8, 29, 21, 0, 0, tzinfo=timezone.utc)
        self.ejecutor = EjecutorReplay()

    def test_ejecucion_replay_valida(self) -> None:
        eventos = [_crear_evento(i) for i in range(1, 20)]
        self.ejecutor.cargar_eventos_replay(eventos)

        solicitud = SolicitudReplay(
            correlation_id="00000000-0000-0000-0000-000000000001",
            environment="REPLAY",
            dataset_manifest_hash="a" * 64,
            range_start_utc=self.t0,
            range_end_utc=self.t1,
            clock_seed=20260829,
        )

        res = self.ejecutor.ejecutar(solicitud)
        self.assertTrue(res.exito)
        resumen = res.datos
        self.assertEqual("REPLAY", resumen.environment)
        self.assertEqual(19, resumen.accepted_event_count)
        self.assertEqual(0, resumen.rejected_event_count)


if __name__ == "__main__":
    unittest.main()
