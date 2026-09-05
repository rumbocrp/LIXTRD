"""Pruebas del reloj de dominio, determinismo de avance y control de zona horaria NY/DST."""
from datetime import datetime, timezone, timedelta
import unittest
import zoneinfo

from sistema_luces.sources.clock import RelojDominio


class DomainClockTests(unittest.TestCase):
    def setUp(self) -> None:
        self.t0 = datetime(2026, 8, 29, 13, 30, 0, tzinfo=timezone.utc)
        self.reloj = RelojDominio(tiempo_inicial_utc=self.t0, clock_seed=20260829)

    def test_ahora_utc_retorna_tiempo_inicial_y_avanza_monotonicamente(self) -> None:
        self.assertEqual(self.reloj.ahora_utc(), self.t0)
        t1 = self.t0 + timedelta(seconds=15)
        self.reloj.avanzar_hasta(t1)
        self.assertEqual(self.reloj.ahora_utc(), t1)

    def test_avanzar_hacia_atras_lanza_error_de_rollback(self) -> None:
        t1 = self.t0 + timedelta(seconds=10)
        self.reloj.avanzar_hasta(t1)
        t_past = self.t0 + timedelta(seconds=5)
        with self.assertRaises(ValueError):
            self.reloj.avanzar_hasta(t_past)

    def test_hora_ny_aplica_zona_horaria_con_dst(self) -> None:
        # En agosto (verano NY / EDT), UTC-4
        # Lunes 2026-08-31: 13:30 UTC -> 09:30 EDT (apertura de mercado)
        reloj_verano = RelojDominio(
            tiempo_inicial_utc=datetime(2026, 8, 31, 13, 30, 0, tzinfo=timezone.utc),
            clock_seed=20260829,
        )
        ny_time = reloj_verano.hora_ny()
        self.assertEqual(ny_time.hour, 9)
        self.assertEqual(ny_time.minute, 30)
        self.assertTrue(reloj_verano.en_sesion_ny())

        # En enero (invierno NY / EST), UTC-5
        # Jueves 2026-01-15: 14:30 UTC -> 09:30 EST
        reloj_invierno = RelojDominio(
            tiempo_inicial_utc=datetime(2026, 1, 15, 14, 30, 0, tzinfo=timezone.utc),
            clock_seed=20260115,
        )
        ny_invierno = reloj_invierno.hora_ny()
        self.assertEqual(ny_invierno.hour, 9)
        self.assertEqual(ny_invierno.minute, 30)
        self.assertTrue(reloj_invierno.en_sesion_ny())

    def test_fecha_sesion_ny_y_fines_de_semana(self) -> None:
        # 2026-08-29 es sabado
        self.assertEqual(self.reloj.fecha_sesion_ny(), "2026-08-29")
        self.assertTrue(self.reloj.es_fin_de_semana_ny())
        # Fuera de sesion porque es fin de semana
        self.assertFalse(self.reloj.en_sesion_ny())

        # 2026-08-31 es lunes
        reloj_lunes = RelojDominio(
            tiempo_inicial_utc=datetime(2026, 8, 31, 14, 0, 0, tzinfo=timezone.utc)
        )
        self.assertFalse(reloj_lunes.es_fin_de_semana_ny())
        self.assertTrue(reloj_lunes.en_sesion_ny())
