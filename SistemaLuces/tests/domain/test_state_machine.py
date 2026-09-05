"""Pruebas para máquinas de estado y transiciones permitidas (SPEC-001 §6.4, CA-8)."""

from datetime import datetime, timezone
import unittest

from sistema_luces.domain.state import (
    TRANSICIONES_PERMITIDAS,
    TransicionEstadoV1,
    es_transicion_valida,
    validar_transicion_estado,
)


class StateMachineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.now_utc = datetime(2026, 8, 29, 14, 30, 0, tzinfo=timezone.utc)
        self.uuid_1 = "11111111-1111-1111-1111-111111111111"
        self.uuid_2 = "22222222-2222-2222-2222-222222222222"

    def test_transiciones_validas_de_luces(self) -> None:
        # Initial state must start at YELLOW
        self.assertTrue(es_transicion_valida("light", None, "YELLOW"))
        self.assertFalse(es_transicion_valida("light", None, "GREEN"))
        self.assertFalse(es_transicion_valida("light", None, "RED"))

        # From YELLOW to any
        self.assertTrue(es_transicion_valida("light", "YELLOW", "YELLOW"))
        self.assertTrue(es_transicion_valida("light", "YELLOW", "GREEN"))
        self.assertTrue(es_transicion_valida("light", "YELLOW", "RED"))

        # From GREEN: only GREEN or YELLOW
        self.assertTrue(es_transicion_valida("light", "GREEN", "GREEN"))
        self.assertTrue(es_transicion_valida("light", "GREEN", "YELLOW"))
        # CA-8: GREEN -> RED direct is FORBIDDEN
        self.assertFalse(es_transicion_valida("light", "GREEN", "RED"))

        # From RED: only RED or YELLOW
        self.assertTrue(es_transicion_valida("light", "RED", "RED"))
        self.assertTrue(es_transicion_valida("light", "RED", "YELLOW"))
        # CA-8: RED -> GREEN direct is FORBIDDEN
        self.assertFalse(es_transicion_valida("light", "RED", "GREEN"))

    def test_transiciones_validas_de_feed(self) -> None:
        self.assertTrue(es_transicion_valida("feed", None, "INITIALIZING"))
        self.assertTrue(es_transicion_valida("feed", "INITIALIZING", "HEALTHY"))
        self.assertTrue(es_transicion_valida("feed", "HEALTHY", "STALE"))
        self.assertTrue(es_transicion_valida("feed", "STALE", "HEALTHY"))
        self.assertTrue(es_transicion_valida("feed", "HEALTHY", "GAPPED"))
        self.assertTrue(es_transicion_valida("feed", "GAPPED", "RECONNECTING"))
        self.assertTrue(es_transicion_valida("feed", "RECONNECTING", "HEALTHY"))

        # Invalid feed transitions
        self.assertFalse(es_transicion_valida("feed", "GAPPED", "HEALTHY"))  # Must reconnect first
        self.assertFalse(es_transicion_valida("feed", None, "HEALTHY"))

    def test_transiciones_validas_de_simulation(self) -> None:
        self.assertTrue(es_transicion_valida("simulation", None, "PROPOSED"))
        self.assertTrue(es_transicion_valida("simulation", "PROPOSED", "OPEN_SIMULATED"))
        self.assertTrue(es_transicion_valida("simulation", "PROPOSED", "REJECTED"))
        self.assertTrue(es_transicion_valida("simulation", "PROPOSED", "CANCELLED"))
        self.assertTrue(es_transicion_valida("simulation", "OPEN_SIMULATED", "CLOSED_SIMULATED"))

        # Invalid transitions
        self.assertFalse(es_transicion_valida("simulation", None, "OPEN_SIMULATED"))
        self.assertFalse(es_transicion_valida("simulation", "CLOSED_SIMULATED", "OPEN_SIMULATED"))

    def test_validar_transicion_estado_objeto(self) -> None:
        trans_ok = TransicionEstadoV1(
            transition_id=self.uuid_1,
            aggregate_type="light",
            aggregate_id="US500_S30",
            previous_state="YELLOW",
            next_state="GREEN",
            actor="system",
            occurred_at_utc=self.now_utc,
            causation_id=None,
            correlation_id=self.uuid_2,
            policy_version="policy-v1",
            reason_codes=("CONFIRMATION_PASSED",),
            safety_forced=False,
        )
        self.assertTrue(validar_transicion_estado(trans_ok).exito)

        # Forbidden green to red transition
        trans_bad = TransicionEstadoV1(
            transition_id=self.uuid_1,
            aggregate_type="light",
            aggregate_id="US500_S30",
            previous_state="GREEN",
            next_state="RED",
            actor="system",
            occurred_at_utc=self.now_utc,
            causation_id=None,
            correlation_id=self.uuid_2,
            policy_version="policy-v1",
            reason_codes=(),
            safety_forced=False,
        )
        res = validar_transicion_estado(trans_bad)
        self.assertFalse(res.exito)
        self.assertEqual("VALIDATION_ERROR", res.error.codigo)


if __name__ == "__main__":
    unittest.main()
