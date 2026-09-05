"""Pruebas de Trazabilidad y Árbol Causal (SPEC-001 §6.2, §6.7, CA-23)."""

from datetime import datetime, timezone
import unittest

from sistema_luces.observability.trace import ArbolTrazabilidad, NodoTraza


class TestTrazabilidad(unittest.TestCase):
    """Verifica encadenamiento causal (correlation_id, causation_id) y reproducibilidad."""

    def setUp(self) -> None:
        self.t0 = datetime(2026, 8, 29, 14, 30, 0, tzinfo=timezone.utc)
        self.arbol = ArbolTrazabilidad()

    def test_registro_y_recorrido_causal(self) -> None:
        self.arbol.registrar_nodo(
            NodoTraza(
                node_id="ev-01",
                node_type="QUOTE_TICK",
                correlation_id="corr-1",
                causation_id=None,
                timestamp_utc=self.t0,
                details={"seq": 1},
            )
        )
        self.arbol.registrar_nodo(
            NodoTraza(
                node_id="case-01",
                node_type="CASE_CREATED",
                correlation_id="corr-1",
                causation_id="ev-01",
                timestamp_utc=self.t0,
                details={"window": "S30"},
            )
        )
        self.arbol.registrar_nodo(
            NodoTraza(
                node_id="sig-01",
                node_type="SIGNAL_EMITTED",
                correlation_id="corr-1",
                causation_id="case-01",
                timestamp_utc=self.t0,
                details={"light": "GREEN"},
            )
        )

        linaje = self.arbol.obtener_linaje_ascendente("sig-01")
        self.assertEqual(["sig-01", "case-01", "ev-01"], [n.node_id for n in linaje])


if __name__ == "__main__":
    unittest.main()
