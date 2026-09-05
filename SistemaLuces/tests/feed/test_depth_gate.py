"""Pruebas del evaluador de compuerta de depth y politica de cuarentena (SPEC-001 §6.8, §12.7, CA-25)."""
from datetime import datetime, timezone
import unittest

from sistema_luces.domain.manifest import DepthGatePolicyV1
from sistema_luces.feed.depth_gate import EvaluadorCompuertaDepth, ResumenSesionDepth


class DepthGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.now = datetime(2026, 8, 29, 14, 30, 0, tzinfo=timezone.utc)
        self.hash_64 = "b" * 64
        self.policy = DepthGatePolicyV1(
            policy_version="depth-policy-v1",
            required_complete_sessions=5,
            minimum_event_coverage_scaled=950_000,
            minimum_sequence_continuity_scaled=999_900,
            maximum_unresolved_gaps=0,
            maximum_out_of_order=0,
            maximum_clock_rollbacks=0,
            maximum_stale_time_ratio_scaled=10_000,
            corpus_hash=self.hash_64,
            approver="lead-qa",
            approved_at_utc=self.now,
        )
        self.evaluador = EvaluadorCompuertaDepth()

    def _make_perfect_session(self, sid: str) -> ResumenSesionDepth:
        return ResumenSesionDepth(
            session_id=sid,
            is_complete=True,
            has_unknown_segment=False,
            event_coverage_scaled=950_000,
            sequence_continuity_scaled=999_900,
            unresolved_gaps=0,
            out_of_order_count=0,
            clock_rollbacks_count=0,
            stale_time_ratio_scaled=10_000,
            metrics_persisted=True,
        )

    def test_politica_ausente_mantiene_cuarentena(self) -> None:
        sesiones = [self._make_perfect_session(f"s-{i}") for i in range(5)]
        res = self.evaluador.evaluar_sesiones(sesiones, policy=None)
        self.assertTrue(res.exito)
        decision = res.datos
        self.assertEqual(decision.status, "QUARANTINED")
        self.assertIn("DEPTH_POLICY_MISSING", decision.reason_codes)

    def test_sesiones_insuficientes_mantiene_cuarentena(self) -> None:
        # Only 4 perfect sessions
        sesiones = [self._make_perfect_session(f"s-{i}") for i in range(4)]
        res = self.evaluador.evaluar_sesiones(sesiones, policy=self.policy)
        self.assertTrue(res.exito)
        decision = res.datos
        self.assertEqual(decision.status, "QUARANTINED")
        self.assertIn("DEPTH_SESSIONS_INSUFFICIENT", decision.reason_codes)

    def test_5_sesiones_en_el_umbral_exacto_aprobadas_pasa_gate(self) -> None:
        sesiones = [self._make_perfect_session(f"s-{i}") for i in range(5)]
        res = self.evaluador.evaluar_sesiones(sesiones, policy=self.policy)
        self.assertTrue(res.exito)
        decision = res.datos
        self.assertEqual(decision.status, "ACCEPTED")
        self.assertIn("DEPTH_GATE_ACCEPTED", decision.reason_codes)

    def test_un_valor_bajo_el_minimo_rechaza_gate_depth(self) -> None:
        # 1 unit below coverage threshold: 949_999 < 950_000
        bad_session = ResumenSesionDepth(
            session_id="s-bad",
            is_complete=True,
            has_unknown_segment=False,
            event_coverage_scaled=949_999,  # failed by 1 unit
            sequence_continuity_scaled=999_900,
            unresolved_gaps=0,
            out_of_order_count=0,
            clock_rollbacks_count=0,
            stale_time_ratio_scaled=10_000,
            metrics_persisted=True,
        )
        sesiones = [self._make_perfect_session(f"s-{i}") for i in range(4)] + [bad_session]
        res = self.evaluador.evaluar_sesiones(sesiones, policy=self.policy)
        self.assertTrue(res.exito)
        decision = res.datos
        self.assertEqual(decision.status, "REJECTED")
        self.assertIn("DEPTH_GATE_REJECTED", decision.reason_codes)
