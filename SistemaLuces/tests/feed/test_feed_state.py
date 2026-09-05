"""Pruebas de la maquina de estados de feed (SPEC-001 §6.4)."""
from datetime import datetime, timezone
import unittest

from sistema_luces.feed.state import GestorEstadoFeed


class FeedStateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.gestor = GestorEstadoFeed()

    def test_estado_inicial_y_transiciones_permitidas(self) -> None:
        self.assertEqual(self.gestor.estado_actual, "INITIALIZING")

        # INITIALIZING -> HEALTHY
        res1 = self.gestor.transicionar("HEALTHY")
        self.assertTrue(res1.exito)
        self.assertEqual(self.gestor.estado_actual, "HEALTHY")

        # HEALTHY -> STALE
        res2 = self.gestor.transicionar("STALE")
        self.assertTrue(res2.exito)
        self.assertEqual(self.gestor.estado_actual, "STALE")

        # STALE -> HEALTHY
        res3 = self.gestor.transicionar("HEALTHY")
        self.assertTrue(res3.exito)

    def test_transicion_invalida_retorna_fallo(self) -> None:
        self.gestor.transicionar("HEALTHY")
        self.gestor.transicionar("GAPPED")

        # GAPPED cannot transition directly to HEALTHY (must go through RECONNECTING or STOPPED)
        res = self.gestor.transicionar("HEALTHY")
        self.assertFalse(res.exito)
        self.assertEqual(res.error.codigo, "VALIDATION_ERROR")
