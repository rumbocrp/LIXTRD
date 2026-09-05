"""Pruebas de determinismo estricto de replay (CA-9, CA-23)."""
from datetime import datetime, timezone, timedelta
import hashlib
import unittest

from sistema_luces.domain.event import SobreEventoV1, compute_payload_hash, canonical_json_bytes
from sistema_luces.sources.replay import FuenteReplay, SolicitudFuente


class ReplayDeterminismTests(unittest.TestCase):
    def setUp(self) -> None:
        self.t0 = datetime(2026, 8, 31, 13, 30, 0, tzinfo=timezone.utc)
        self.t_end = self.t0 + timedelta(hours=2)
        self.events = []
        for i in range(1, 21):
            t = self.t0 + timedelta(seconds=i * 30)
            p = {"tick": i, "price": 500000 + i * 25}
            ev = SobreEventoV1(
                event_id=f"20000000-0000-0000-0000-{i:012d}",
                event_type="QUOTE_TICK",
                schema_version=1,
                occurred_at_utc=t,
                received_at_utc=t,
                persisted_at_utc=None,
                source="replay",
                environment="REPLAY",
                source_account_id_hash=None,
                instrument="US500",
                symbol_id=None,
                source_sequence=i,
                correlation_id="20000000-0000-0000-0000-000000000000",
                causation_id=None,
                payload_hash=compute_payload_hash(p),
                previous_hash=None,
                payload=p,
            )
            self.events.append(ev)

        self.sol = SolicitudFuente(
            correlation_id="20000000-0000-0000-0000-000000000000",
            environment="REPLAY",
            source_profile_version="replay-v1",
            instrument="US500",
            range_start_utc=self.t0,
            range_end_utc=self.t_end,
            clock_seed=20260829,
        )

    def test_dos_ejecuciones_de_replay_producen_salida_identica_byte_a_byte(self) -> None:
        fuente = FuenteReplay()

        # Run 1
        sesion1 = fuente.abrir(self.sol, dataset=self.events).datos
        bytes1 = b"".join([canonical_json_bytes(e.datos.payload) for e in sesion1.eventos_sync()])
        hash1 = hashlib.sha256(bytes1).hexdigest()

        # Run 2
        sesion2 = fuente.abrir(self.sol, dataset=self.events).datos
        bytes2 = b"".join([canonical_json_bytes(e.datos.payload) for e in sesion2.eventos_sync()])
        hash2 = hashlib.sha256(bytes2).hexdigest()

        self.assertEqual(bytes1, bytes2)
        self.assertEqual(hash1, hash2)
