"""Pruebas de la Reconciliación de Ejecuciones Demo vs Simulaciones (SPEC-001 §6.6, CA-19)."""

from datetime import datetime, timedelta, timezone
import unittest

from sistema_luces.domain.simulation import SimulacionV1
from sistema_luces.imports.demo import EjecucionDemoObservada
from sistema_luces.imports.reconciliation import ReconciliadorDemo


def _crear_simulacion_prueba(
    sim_id: str,
    direction: str = "LONG",
    opened_at_utc: datetime | None = None,
    planned_entry: int = 500040,
) -> SimulacionV1:
    t0 = opened_at_utc or datetime(2026, 8, 29, 14, 30, 0, tzinfo=timezone.utc)
    return SimulacionV1(
        simulation_id=sim_id,
        signal_id="00000000-0000-0000-0000-000000000099",
        environment="REPLAY",
        demo_account_hash=None,
        status="CLOSED_SIMULATED",
        proposed_at_utc=t0,
        opened_at_utc=t0,
        closed_at_utc=t0 + timedelta(minutes=2),
        horizon_end_utc=t0 + timedelta(minutes=5),
        direction=direction,  # type: ignore[arg-type]
        planned_entry=planned_entry,
        stop=planned_entry - 500,
        target=planned_entry + 2000,
        risk_profile_version="risk-v1",
        instrument_profile_version="us500-v1",
        requested_quantity_simulated=100,
        effective_quantity_simulated=100,
        quantity_scale=100,
        fill_entry=planned_entry,
        fill_exit=planned_entry + 2000,
        fill_source="simulator",
        source_execution_ids=(),
        spread_cost=40,
        slippage_cost=0,
        commission_cost=0,
        carry_cost=0,
        money_scale=100,
        currency="USD",
        exit_reason="target",
        gross_pnl=2000,
        net_pnl=1960,
        realized_r=1000000,
        mfe=2000,
        mae=0,
        reconciliation_status="PENDING",
        reconciliation_reason_codes=(),
        market_event_cutoff=t0,
        cost_profile_version="cost-v1",
        correlation_id=sim_id,
        causation_id="00000000-0000-0000-0000-000000000099",
        schema_version=1,
    )


class TestReconciliacionDemo(unittest.TestCase):
    """Verifica el cruce temporal de ejecuciones y marcado UNMATCHED de trades huérfanos."""

    def setUp(self) -> None:
        self.reconciliador = ReconciliadorDemo(tolerancia_tiempo_segundos=15, tolerancia_precio_pts=200)
        self.t0 = datetime(2026, 8, 29, 14, 30, 0, tzinfo=timezone.utc)

    def test_reconciliacion_trade_coincidente(self) -> None:
        sim = _crear_simulacion_prueba("00000000-0000-0000-0000-000000000001", opened_at_utc=self.t0)
        demo_exec = EjecucionDemoObservada(
            execution_id="exec-demo-001",
            trade_id="tr-001",
            account_hash="a" * 64,
            symbol="US500",
            side="LONG",
            quantity=100,
            entry_time_utc=self.t0 + timedelta(seconds=2),  # +2s de latencia
            entry_price=500050,  # 10 pts slippage
            exit_time_utc=self.t0 + timedelta(minutes=2, seconds=2),
            exit_price=502050,
            gross_pnl_cents=2000,
            net_pnl_cents=1950,
        )

        informe = self.reconciliador.reconciliar(
            simulaciones=[sim],
            ejecuciones_demo=[demo_exec],
        )

        self.assertEqual(1, informe.matched_count)
        self.assertEqual(0, informe.unmatched_count)
        self.assertEqual("MATCHED", informe.simulaciones_reconciliadas[0].reconciliation_status)
        self.assertIn("exec-demo-001", informe.simulaciones_reconciliadas[0].source_execution_ids)

    def test_trade_huerfano_marcado_unmatched_ca19(self) -> None:
        sim = _crear_simulacion_prueba("00000000-0000-0000-0000-000000000002", opened_at_utc=self.t0)
        # Trade demo en horario completamente distinto (sin simulación correspondiente)
        demo_exec = EjecucionDemoObservada(
            execution_id="exec-demo-unmatched",
            trade_id="tr-999",
            account_hash="a" * 64,
            symbol="US500",
            side="SHORT",
            quantity=100,
            entry_time_utc=self.t0 + timedelta(hours=3),
            entry_price=501000,
            exit_time_utc=self.t0 + timedelta(hours=3, minutes=1),
            exit_price=500500,
            gross_pnl_cents=500,
            net_pnl_cents=450,
        )

        informe = self.reconciliador.reconciliar(
            simulaciones=[sim],
            ejecuciones_demo=[demo_exec],
        )

        self.assertEqual(0, informe.matched_count)
        self.assertEqual(1, informe.unmatched_count)
        self.assertEqual(1, len(informe.ejecuciones_no_conciliadas))
        self.assertEqual("exec-demo-unmatched", informe.ejecuciones_no_conciliadas[0].execution_id)
        self.assertEqual("UNMATCHED", informe.ejecuciones_no_conciliadas[0].reconciliation_status)


if __name__ == "__main__":
    unittest.main()
