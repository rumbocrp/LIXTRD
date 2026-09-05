"""Pruebas para documentos de Señal y Simulación (SPEC-001 §6.5, §6.6, CA-10, CA-12, OPT-7)."""

from datetime import datetime, timedelta, timezone
import unittest

from sistema_luces.domain.signal import SenalV1, validar_senal
from sistema_luces.domain.simulation import SimulacionV1, validar_simulacion


class SignalAndSimulationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.now_utc = datetime(2026, 8, 29, 14, 30, 0, tzinfo=timezone.utc)
        self.valid_until = self.now_utc + timedelta(seconds=30)
        self.uuid_1 = "11111111-1111-1111-1111-111111111111"
        self.uuid_2 = "22222222-2222-2222-2222-222222222222"
        self.hash_64 = "a" * 64

    def test_senal_valida_correctamente(self) -> None:
        senal_ok = SenalV1(
            signal_id=self.uuid_1,
            case_id=self.uuid_2,
            created_at_utc=self.now_utc,
            valid_until_utc=self.valid_until,
            environment="REPLAY",
            instrument="US500",
            decision_window="S30",
            market_event_cutoff=self.now_utc,
            reference_bid=500000,
            reference_ask=500040,
            price_scale=100,
            data_age_ms=120,
            direction="LONG",
            light="GREEN",
            reason_codes=("MODEL_EDGE_LONG",),
            health_state="HEALTHY",
            safety_forced=False,
            strategy_id="strat-v1",
            strategy_version="1.0.0",
            feature_set_version="features-v1",
            feature_snapshot_hash=self.hash_64,
            model_id="logreg-us500",
            model_version="1.0.0",
            model_hash=self.hash_64,
            calibration_version="calib-v1",
            policy_version="policy-v1",
            raw_score_long=750000,
            raw_score_short=250000,
            calibrated_probability_long=680000,
            calibrated_probability_short=320000,
            expected_value_long_net=15000,
            expected_value_short_net=-5000,
            cost_profile_version="cost-v1",
            correlation_id=self.uuid_1,
            causation_id=self.uuid_2,
            code_hash=self.hash_64,
            schema_version=1,
        )
        self.assertTrue(validar_senal(senal_ok).exito)

    def test_senal_amarilla_fuerza_direction_monitor(self) -> None:
        senal_yellow = SenalV1(
            signal_id=self.uuid_1,
            case_id=self.uuid_2,
            created_at_utc=self.now_utc,
            valid_until_utc=self.valid_until,
            environment="REPLAY",
            instrument="US500",
            decision_window="S30",
            market_event_cutoff=self.now_utc,
            reference_bid=500000,
            reference_ask=500040,
            price_scale=100,
            data_age_ms=100,
            direction="MONITOR",
            light="YELLOW",
            reason_codes=("FEED_DEGRADED",),
            health_state="STALE",
            safety_forced=True,
            strategy_id="strat-v1",
            strategy_version="1.0.0",
            feature_set_version="features-v1",
            feature_snapshot_hash=self.hash_64,
            model_id=None,
            model_version=None,
            model_hash=None,
            calibration_version=None,
            policy_version="policy-v1",
            raw_score_long=None,
            raw_score_short=None,
            calibrated_probability_long=None,
            calibrated_probability_short=None,
            expected_value_long_net=None,
            expected_value_short_net=None,
            cost_profile_version=None,
            correlation_id=self.uuid_1,
            causation_id=None,
            code_hash=self.hash_64,
            schema_version=1,
        )
        self.assertTrue(validar_senal(senal_yellow).exito)

        # Inconsistent yellow with LONG
        senal_bad = SenalV1(
            signal_id=self.uuid_1,
            case_id=self.uuid_2,
            created_at_utc=self.now_utc,
            valid_until_utc=self.valid_until,
            environment="REPLAY",
            instrument="US500",
            decision_window="S30",
            market_event_cutoff=self.now_utc,
            reference_bid=500000,
            reference_ask=500040,
            price_scale=100,
            data_age_ms=100,
            direction="LONG",  # MUST BE MONITOR FOR YELLOW
            light="YELLOW",
            reason_codes=(),
            health_state="HEALTHY",
            safety_forced=False,
            strategy_id="strat-v1",
            strategy_version="1.0.0",
            feature_set_version="features-v1",
            feature_snapshot_hash=self.hash_64,
            model_id=None,
            model_version=None,
            model_hash=None,
            calibration_version=None,
            policy_version="policy-v1",
            raw_score_long=None,
            raw_score_short=None,
            calibrated_probability_long=None,
            calibrated_probability_short=None,
            expected_value_long_net=None,
            expected_value_short_net=None,
            cost_profile_version=None,
            correlation_id=self.uuid_1,
            causation_id=None,
            code_hash=self.hash_64,
            schema_version=1,
        )
        res = validar_senal(senal_bad)
        self.assertFalse(res.exito)
        self.assertEqual("VALIDATION_ERROR", res.error.codigo)

    def test_opt7_causalidad_temporal_de_la_senal(self) -> None:
        # created_at must be >= market_event_cutoff and < valid_until_utc
        senal_past_valid = SenalV1(
            signal_id=self.uuid_1,
            case_id=self.uuid_2,
            created_at_utc=self.now_utc,
            valid_until_utc=self.now_utc - timedelta(seconds=1),  # Invalid expired
            environment="REPLAY",
            instrument="US500",
            decision_window="S30",
            market_event_cutoff=self.now_utc,
            reference_bid=500000,
            reference_ask=500040,
            price_scale=100,
            data_age_ms=100,
            direction="LONG",
            light="GREEN",
            reason_codes=(),
            health_state="HEALTHY",
            safety_forced=False,
            strategy_id="strat-v1",
            strategy_version="1.0.0",
            feature_set_version="features-v1",
            feature_snapshot_hash=self.hash_64,
            model_id=None,
            model_version=None,
            model_hash=None,
            calibration_version=None,
            policy_version="policy-v1",
            raw_score_long=None,
            raw_score_short=None,
            calibrated_probability_long=None,
            calibrated_probability_short=None,
            expected_value_long_net=None,
            expected_value_short_net=None,
            cost_profile_version=None,
            correlation_id=self.uuid_1,
            causation_id=None,
            code_hash=self.hash_64,
            schema_version=1,
        )
        self.assertFalse(validar_senal(senal_past_valid).exito)

    def test_simulacion_valida_direcciones_y_barreras(self) -> None:
        # Long: planned_entry 500100, stop 499600, target 502100 (5 pts stop, 20 pts target, price_scale 100)
        sim_long = SimulacionV1(
            simulation_id=self.uuid_1,
            signal_id=self.uuid_2,
            environment="REPLAY",
            demo_account_hash=None,
            status="OPEN_SIMULATED",
            proposed_at_utc=self.now_utc,
            opened_at_utc=self.now_utc,
            closed_at_utc=None,
            horizon_end_utc=self.now_utc + timedelta(minutes=5),
            direction="LONG",
            planned_entry=500100,
            stop=499600,
            target=502100,
            risk_profile_version="risk-v1",
            instrument_profile_version="us500-v1",
            requested_quantity_simulated=100,
            effective_quantity_simulated=100,
            quantity_scale=100,
            fill_entry=500100,
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
            market_event_cutoff=self.now_utc,
            cost_profile_version="cost-v1",
            correlation_id=self.uuid_1,
            causation_id=self.uuid_2,
            schema_version=1,
        )
        self.assertTrue(validar_simulacion(sim_long).exito)

        # Inverted barriers for LONG (stop > entry)
        sim_bad = SimulacionV1(
            simulation_id=self.uuid_1,
            signal_id=self.uuid_2,
            environment="REPLAY",
            demo_account_hash=None,
            status="OPEN_SIMULATED",
            proposed_at_utc=self.now_utc,
            opened_at_utc=self.now_utc,
            closed_at_utc=None,
            horizon_end_utc=self.now_utc + timedelta(minutes=5),
            direction="LONG",
            planned_entry=500100,
            stop=500500,  # STOP ABOVE ENTRY IN LONG
            target=502100,
            risk_profile_version="risk-v1",
            instrument_profile_version="us500-v1",
            requested_quantity_simulated=100,
            effective_quantity_simulated=100,
            quantity_scale=100,
            fill_entry=500100,
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
            market_event_cutoff=self.now_utc,
            cost_profile_version="cost-v1",
            correlation_id=self.uuid_1,
            causation_id=self.uuid_2,
            schema_version=1,
        )
        self.assertFalse(validar_simulacion(sim_bad).exito)


if __name__ == "__main__":
    unittest.main()
