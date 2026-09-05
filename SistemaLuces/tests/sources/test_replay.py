"""Pruebas de la fuente y sesion de replay, stepping progresivo y cortes temporales."""
from datetime import datetime, timezone, timedelta
import unittest

from sistema_luces.domain.event import SobreEventoV1, compute_payload_hash
from sistema_luces.sources.clock import RelojDominio
from sistema_luces.sources.replay import FuenteReplay, SolicitudFuente, SesionReplay


class ReplayEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.t0 = datetime(2026, 8, 31, 13, 30, 0, tzinfo=timezone.utc)
        self.t_end = self.t0 + timedelta(hours=1)
        self.events = []
        for i in range(1, 11):
            t = self.t0 + timedelta(minutes=i)
            p = {"tick": i, "bid": 500000 + i * 10, "ask": 500025 + i * 10, "price_scale": 100}
            ev = SobreEventoV1(
                event_id=f"10000000-0000-0000-0000-{i:012d}",
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
                correlation_id="10000000-0000-0000-0000-000000000000",
                causation_id=None,
                payload_hash=compute_payload_hash(p),
                previous_hash=None,
                payload=p,
            )
            self.events.append(ev)

        self.solicitud = SolicitudFuente(
            correlation_id="10000000-0000-0000-0000-000000000000",
            environment="REPLAY",
            source_profile_version="replay-v1",
            instrument="US500",
            range_start_utc=self.t0,
            range_end_utc=self.t_end,
            clock_seed=20260829,
            event_cutoff_utc=None,
        )
        self.fuente = FuenteReplay()

    def test_abrir_sesion_replay_y_recorrer_eventos(self) -> None:
        res = self.fuente.abrir(self.solicitud, dataset=self.events)
        self.assertTrue(res.exito)
        sesion = res.datos

        emitted = list(sesion.eventos_sync())
        self.assertEqual(len(emitted), 10)
        for i, item in enumerate(emitted, start=1):
            self.assertTrue(item.exito)
            self.assertEqual(item.datos.source_sequence, i)

        res_close = sesion.cerrar()
        self.assertTrue(res_close.exito)
        self.assertEqual(res_close.datos.total_received, 10)

    def test_cutoff_temporal_evita_look_ahead_bias(self) -> None:
        # Cutoff at t0 + 5 minutes
        cutoff = self.t0 + timedelta(minutes=5)
        sol_cutoff = SolicitudFuente(
            correlation_id="10000000-0000-0000-0000-000000000000",
            environment="REPLAY",
            source_profile_version="replay-v1",
            instrument="US500",
            range_start_utc=self.t0,
            range_end_utc=self.t_end,
            clock_seed=20260829,
            event_cutoff_utc=cutoff,
        )
        res = self.fuente.abrir(sol_cutoff, dataset=self.events)
        self.assertTrue(res.exito)
        sesion = res.datos
        emitted = list(sesion.eventos_sync())
        self.assertEqual(len(emitted), 5)

    def test_pausa_y_reanudacion_de_sesion(self) -> None:
        res = self.fuente.abrir(self.solicitud, dataset=self.events)
        sesion = res.datos

        # Step 3 events
        ev1 = sesion.paso()
        self.assertTrue(ev1.exito and ev1.datos is not None)
        ev2 = sesion.paso()
        self.assertTrue(ev2.exito and ev2.datos is not None)
        ev3 = sesion.paso()
        self.assertTrue(ev3.exito and ev3.datos is not None)

        sesion.pausar()
        self.assertTrue(sesion.esta_pausada())

        # When paused, paso returns None or stays paused
        ev_paused = sesion.paso()
        self.assertTrue(ev_paused.exito and ev_paused.datos is None)

        sesion.reanudar()
        self.assertFalse(sesion.esta_pausada())
        ev4 = sesion.paso()
        self.assertTrue(ev4.exito and ev4.datos is not None)
        self.assertEqual(ev4.datos.source_sequence, 4)
