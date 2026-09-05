"""Pruebas del Motor de Riesgo y Tripwires (SPEC-001 §8, CA-15, CA-16, CA-17, CA-18, DM-12)."""

from datetime import datetime, timedelta, timezone
import unittest

from sistema_luces.domain.manifest import RiskProfileV1
from sistema_luces.domain.simulation import SimulacionV1
from sistema_luces.risk.blackout import CalendarioNoticias, EventoNoticia
from sistema_luces.risk.engine import MotorRiesgo


def _crear_simulacion(
    sim_id: str = "00000000-0000-0000-0000-000000000001",
    signal_id: str = "00000000-0000-0000-0000-000000000002",
    direction: str = "LONG",
    planned_entry: int = 500000,
    stop: int = 499500,
    target: int = 502000,
    qty: int = 1000,
    t_utc: datetime | None = None,
) -> SimulacionV1:
    t = t_utc or datetime(2026, 8, 29, 14, 30, 0, tzinfo=timezone.utc)
    return SimulacionV1(
        simulation_id=sim_id,
        signal_id=signal_id,
        environment="REPLAY",
        demo_account_hash=None,
        status="PROPOSED",
        proposed_at_utc=t,
        opened_at_utc=None,
        closed_at_utc=None,
        horizon_end_utc=t + timedelta(minutes=5),
        direction=direction,  # type: ignore[arg-type]
        planned_entry=planned_entry,
        stop=stop,
        target=target,
        risk_profile_version="risk-us500-v1",
        instrument_profile_version="us500-v1",
        requested_quantity_simulated=qty,
        effective_quantity_simulated=qty,
        quantity_scale=100,
        fill_entry=None,
        fill_exit=None,
        fill_source="simulator",
        source_execution_ids=(),
        spread_cost=40,
        slippage_cost=0,
        commission_cost=0,
        carry_cost=0,
        money_scale=100,
        currency="USD",
        exit_reason=None,
        gross_pnl=None,
        net_pnl=None,
        realized_r=None,
        mfe=None,
        mae=None,
        reconciliation_status="PENDING",
        reconciliation_reason_codes=(),
        market_event_cutoff=t,
        cost_profile_version="cost-v1",
        correlation_id=sim_id,
        causation_id=signal_id,
        schema_version=1,
    )


class TestMotorRiesgo(unittest.TestCase):
    """Verifica todos los tripwires de riesgo y guardias de seguridad."""

    def setUp(self) -> None:
        self.t0 = datetime(2026, 8, 29, 14, 30, 0, tzinfo=timezone.utc)
        self.profile = RiskProfileV1(
            profile_version="risk-us500-v1",
            max_risk_per_trade_usd_cents=5000,   # $50.00
            max_daily_loss_usd_cents=25000,       # $250.00
            max_daily_drawdown_usd_cents=25000,   # $250.00
            max_consecutive_losses=3,
            max_daily_openings=10,
            max_concurrent_positions=1,
        )
        self.motor = MotorRiesgo(profile=self.profile)

    def test_riesgo_por_operacion_limite_50_usd(self) -> None:
        # 500 pts * 1000 qty / 10000 = $50.00 -> OK
        sim_ok = _crear_simulacion(planned_entry=500000, stop=499500, qty=1000)
        res_ok = self.motor.evaluar_propuesta(sim_ok, self.t0)
        self.assertTrue(res_ok.exito)

        # 510 pts * 1000 qty / 10000 = $51.00 -> REJECT
        sim_fail = _crear_simulacion(
            sim_id="00000000-0000-0000-0000-000000000010",
            planned_entry=500000,
            stop=499490,
            qty=1000,
        )
        res_fail = self.motor.evaluar_propuesta(sim_fail, self.t0)
        self.assertFalse(res_fail.exito)
        self.assertEqual("RISK_LIMIT_HIT", res_fail.error.codigo)

    def test_invariante_posicion_unica_y_rechazo_solapada_ca16(self) -> None:
        sim1 = _crear_simulacion(sim_id="00000000-0000-0000-0000-000000000001")
        self.assertTrue(self.motor.evaluar_propuesta(sim1, self.t0).exito)
        self.motor.registrar_apertura(sim1)

        sim2 = _crear_simulacion(sim_id="00000000-0000-0000-0000-000000000002")
        res2 = self.motor.evaluar_propuesta(sim2, self.t0 + timedelta(seconds=10))
        self.assertFalse(res2.exito)
        self.assertEqual("RISK_LIMIT_HIT", res2.error.codigo)
        self.assertEqual("OVERLAPPING_POSITION", res2.error.detalles["reason"])

    def test_pausa_por_racha_de_3_perdidas(self) -> None:
        for i in range(3):
            sim = _crear_simulacion(sim_id=f"00000000-0000-0000-0000-{i+1:012d}")
            self.assertTrue(self.motor.evaluar_propuesta(sim, self.t0).exito)
            self.motor.registrar_apertura(sim)
            self.motor.registrar_cierre(sim, pnl_usd_cents=-5000)

        sim_next = _crear_simulacion(sim_id="00000000-0000-0000-0000-000000000099")
        res_next = self.motor.evaluar_propuesta(sim_next, self.t0 + timedelta(minutes=15))
        self.assertFalse(res_next.exito)
        self.assertEqual("RISK_LIMIT_HIT", res_next.error.codigo)

    def test_perdida_diaria_maxima_250_usd_dispara_kill_switch(self) -> None:
        # 5 trades of -$50 = -$250
        for i in range(5):
            sim = _crear_simulacion(sim_id=f"00000000-0000-0000-0000-{i+1:012d}")
            self.motor.registrar_apertura(sim)
            self.motor.registrar_cierre(sim, pnl_usd_cents=-5000)
            self.motor.reset_loss_streak_for_test()

        self.assertTrue(self.motor.interruptor.activo)
        sim_blocked = _crear_simulacion(sim_id="00000000-0000-0000-0000-000000000100")
        res = self.motor.evaluar_propuesta(sim_blocked, self.t0 + timedelta(hours=1))
        self.assertFalse(res.exito)
        self.assertEqual("RISK_LIMIT_HIT", res.error.codigo)

    def test_limite_10_aperturas_diarias(self) -> None:
        for i in range(10):
            sim = _crear_simulacion(sim_id=f"00000000-0000-0000-0000-{i+1:012d}")
            self.motor.registrar_apertura(sim)
            self.motor.registrar_cierre(sim, pnl_usd_cents=1000)

        sim_11 = _crear_simulacion(sim_id="00000000-0000-0000-0000-000000000011")
        res_11 = self.motor.evaluar_propuesta(sim_11, self.t0 + timedelta(hours=2))
        self.assertFalse(res_11.exito)
        self.assertEqual("RISK_LIMIT_HIT", res_11.error.codigo)

    def test_reseteo_medianoche_ny_dm12(self) -> None:
        # Day 1: 10 openings
        for i in range(10):
            sim = _crear_simulacion(sim_id=f"00000000-0000-0000-0000-{i+1:012d}", t_utc=self.t0)
            self.motor.registrar_apertura(sim)
            self.motor.registrar_cierre(sim, pnl_usd_cents=1000)

        # Next day in NY timezone (e.g. +24 hours)
        t_next_day = self.t0 + timedelta(days=1)
        sim_new_day = _crear_simulacion(sim_id="00000000-0000-0000-0000-000000000050", t_utc=t_next_day)
        res_new_day = self.motor.evaluar_propuesta(sim_new_day, t_next_day)
        self.assertTrue(res_new_day.exito)


if __name__ == "__main__":
    unittest.main()
