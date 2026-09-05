"""Pruebas para gestión y alineación de ventanas temporales S30 y S60 (WP-05)."""

from datetime import datetime, timezone
import unittest

from sistema_luces.cases.windows import (
    alinear_ventana,
    es_cierre_de_ventana,
    obtener_limites_ventana,
    siguiente_cierre_de_ventana,
)


class WindowManagementTests(unittest.TestCase):
    def test_s30_window_boundaries(self) -> None:
        t1 = datetime(2026, 8, 29, 14, 30, 15, 123456, tzinfo=timezone.utc)
        start, end = obtener_limites_ventana(t1, "S30")
        self.assertEqual(datetime(2026, 8, 29, 14, 30, 0, tzinfo=timezone.utc), start)
        self.assertEqual(datetime(2026, 8, 29, 14, 30, 30, tzinfo=timezone.utc), end)

        t2 = datetime(2026, 8, 29, 14, 30, 45, tzinfo=timezone.utc)
        start2, end2 = obtener_limites_ventana(t2, "S30")
        self.assertEqual(datetime(2026, 8, 29, 14, 30, 30, tzinfo=timezone.utc), start2)
        self.assertEqual(datetime(2026, 8, 29, 14, 31, 0, tzinfo=timezone.utc), end2)

    def test_s60_window_boundaries(self) -> None:
        t1 = datetime(2026, 8, 29, 14, 30, 45, 999999, tzinfo=timezone.utc)
        start, end = obtener_limites_ventana(t1, "S60")
        self.assertEqual(datetime(2026, 8, 29, 14, 30, 0, tzinfo=timezone.utc), start)
        self.assertEqual(datetime(2026, 8, 29, 14, 31, 0, tzinfo=timezone.utc), end)

    def test_es_cierre_de_ventana(self) -> None:
        # Exact 30s boundaries
        cierre_s30_1 = datetime(2026, 8, 29, 14, 30, 0, tzinfo=timezone.utc)
        cierre_s30_2 = datetime(2026, 8, 29, 14, 30, 30, tzinfo=timezone.utc)
        no_cierre_s30 = datetime(2026, 8, 29, 14, 30, 15, tzinfo=timezone.utc)

        self.assertTrue(es_cierre_de_ventana(cierre_s30_1, "S30"))
        self.assertTrue(es_cierre_de_ventana(cierre_s30_2, "S30"))
        self.assertFalse(es_cierre_de_ventana(no_cierre_s30, "S30"))

        # Exact 60s boundaries
        cierre_s60 = datetime(2026, 8, 29, 14, 31, 0, tzinfo=timezone.utc)
        no_cierre_s60 = datetime(2026, 8, 29, 14, 30, 30, tzinfo=timezone.utc)

        self.assertTrue(es_cierre_de_ventana(cierre_s60, "S60"))
        self.assertFalse(es_cierre_de_ventana(no_cierre_s60, "S60"))

    def test_siguiente_cierre_de_ventana(self) -> None:
        t = datetime(2026, 8, 29, 14, 30, 10, tzinfo=timezone.utc)
        next_s30 = siguiente_cierre_de_ventana(t, "S30")
        self.assertEqual(datetime(2026, 8, 29, 14, 30, 30, tzinfo=timezone.utc), next_s30)

        next_s60 = siguiente_cierre_de_ventana(t, "S60")
        self.assertEqual(datetime(2026, 8, 29, 14, 31, 0, tzinfo=timezone.utc), next_s60)

    def test_alinear_ventana(self) -> None:
        t = datetime(2026, 8, 29, 14, 30, 30, tzinfo=timezone.utc)
        w = alinear_ventana(t, "S30")
        self.assertEqual("S30", w.decision_window)
        self.assertEqual(datetime(2026, 8, 29, 14, 30, 0, tzinfo=timezone.utc), w.start_utc)
        self.assertEqual(datetime(2026, 8, 29, 14, 30, 30, tzinfo=timezone.utc), w.end_utc)


if __name__ == "__main__":
    unittest.main()
