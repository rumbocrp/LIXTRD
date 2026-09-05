"""Pruebas del Calendario de Noticias y Ventanas de Blackout (SPEC-001 §8, CA-17)."""

from datetime import datetime, timedelta, timezone
import unittest

from sistema_luces.risk.blackout import CalendarioNoticias, EventoNoticia


class TestCalendarioNoticias(unittest.TestCase):
    """Verifica detección de ventanas de noticias [inicio, fin] inclusive."""

    def setUp(self) -> None:
        self.t_event = datetime(2026, 8, 29, 14, 30, 0, tzinfo=timezone.utc)
        self.calendario = CalendarioNoticias(blackout_minutes=15)
        self.calendario.registrar_evento(
            EventoNoticia(
                event_id="nfp-20260829",
                nombre="Non-Farm Payrolls",
                impacto="HIGH",
                moneda="USD",
                timestamp_utc=self.t_event,
            )
        )

    def test_en_ventana_de_blackout_exacta_inclusive(self) -> None:
        # Exactamente 15 min antes
        self.assertTrue(self.calendario.esta_en_blackout(self.t_event - timedelta(minutes=15)))
        # En el momento del evento
        self.assertTrue(self.calendario.esta_en_blackout(self.t_event))
        # Exactamente 15 min después
        self.assertTrue(self.calendario.esta_en_blackout(self.t_event + timedelta(minutes=15)))

    def test_fuera_de_ventana_de_blackout(self) -> None:
        # 15 min y 1 segundo antes
        self.assertFalse(self.calendario.esta_en_blackout(self.t_event - timedelta(minutes=15, seconds=1)))
        # 15 min y 1 segundo después
        self.assertFalse(self.calendario.esta_en_blackout(self.t_event + timedelta(minutes=15, seconds=1)))


if __name__ == "__main__":
    unittest.main()
