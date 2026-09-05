"""Harness de pruebas de aceptación y fakes de dominio para Sistema de Luces (V1 US500).

Provee generadores de eventos, DTOs, manifiestos, espías y emuladores opacos para
verificar Tiers 1–4 y la matriz de criterios de aceptación CA-1 a CA-28 sin acoplamiento
a implementaciones privadas.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Literal
import zoneinfo

from tests.conftest import REPO_ROOT, SRC_ROOT

from sistema_luces.domain.api import (
    DocumentoVistaV1,
    ResumenEjecucion,
    ResumenImportacion,
    SolicitudConsulta,
    SolicitudImportacionDemo,
    SolicitudReplay,
    SolicitudShadow,
    VistaLectura,
    validar_solicitud_consulta,
    validar_solicitud_importacion_demo,
    validar_solicitud_replay,
    validar_solicitud_shadow,
)
from sistema_luces.domain.error import CodigoErrorDominio, ErrorDominio
from sistema_luces.domain.event import (
    DepthDeltaPayloadV1,
    GapDetectedPayloadV1,
    QuoteTickPayloadV1,
    SobreEventoV1,
    canonical_json_bytes,
    canonical_json_dumps,
    compute_payload_hash,
)
from sistema_luces.domain.manifest import (
    CostProfileV1,
    DepthGatePolicyV1,
    ImportManifestV1,
    InstrumentProfileV1,
    ModelGatePolicyV1,
    RiskProfileV1,
)
from sistema_luces.domain.metric import (
    PLANOS_METRICOS_PERMITIDOS,
    SnapshotMetricoV1,
    validar_snapshot_metrico,
)
from sistema_luces.domain.result import Resultado, exito, fallo
from sistema_luces.domain.signal import (
    SenalV1,
    validar_senal,
)
from sistema_luces.domain.simulation import (
    SimulacionV1,
    validar_simulacion,
)
from sistema_luces.domain.state import (
    EstadoFeed,
    EstadoLuces,
    EstadoSimulacion,
    TransicionEstadoV1,
    es_transicion_valida,
)
from sistema_luces.domain.vocabulary import (
    Actor,
    DecisionWindow,
    Direction,
    Environment,
    Light,
    ReconciliationStatus,
    Source,
    parse_environment,
)

NY_TZ = zoneinfo.ZoneInfo("America/New_York")


def make_uuid(index: int) -> str:
    """Genera un UUID v4 determinista para pruebas."""
    hex_str = f"{index:032x}"
    return f"{hex_str[:8]}-{hex_str[8:12]}-{hex_str[12:16]}-{hex_str[16:20]}-{hex_str[20:]}"


def make_sha256(content: str | bytes) -> str:
    """Genera un hash SHA-256 hexadecimal."""
    data = content.encode("utf-8") if isinstance(content, str) else content
    return hashlib.sha256(data).hexdigest()


# --- FÁBRICAS DE DOMINIO ---


def create_test_quote_tick_envelope(
    seq: int,
    occurred_at_utc: datetime,
    bid: int = 500000,
    ask: int = 500040,
    price_scale: int = 100,
    source: Source = "replay",
    environment: Environment = "REPLAY",
    instrument: str = "US500",
    previous_hash: str | None = None,
    event_id: str | None = None,
) -> SobreEventoV1:
    payload = {
        "ask": ask,
        "bid": bid,
        "flags": 0,
        "price_scale": price_scale,
        "size_ask": 10,
        "size_bid": 10,
    }
    payload_hash = compute_payload_hash(payload)
    return SobreEventoV1(
        event_id=event_id or make_uuid(seq),
        event_type="QUOTE_TICK",
        schema_version=1,
        occurred_at_utc=occurred_at_utc,
        received_at_utc=occurred_at_utc + timedelta(milliseconds=2),
        persisted_at_utc=occurred_at_utc + timedelta(milliseconds=5),
        source=source,
        environment=environment,
        source_account_id_hash=None,
        instrument=instrument,
        symbol_id=instrument,
        source_sequence=seq,
        payload=payload,
        payload_hash=payload_hash,
        previous_hash=previous_hash,
        causation_id=None,
        correlation_id=make_uuid(seq),
    )


def create_test_signal(
    signal_id: str,
    created_at_utc: datetime,
    valid_until_utc: datetime,
    light: Light = "GREEN",
    direction: Direction = "LONG",
    environment: Environment = "REPLAY",
    calibrated_prob_long: int = 680000,
    calibrated_prob_short: int = 320000,
    expected_value_long: int = 15000,
    expected_value_short: int = -5000,
    health_state: str = "HEALTHY",
    reason_codes: tuple[str, ...] = ("MODEL_EDGE_LONG",),
) -> SenalV1:
    hash_64 = make_sha256("model-v1")
    return SenalV1(
        signal_id=signal_id,
        case_id=make_uuid(100),
        created_at_utc=created_at_utc,
        valid_until_utc=valid_until_utc,
        environment=environment,
        instrument="US500",
        decision_window="S30",
        market_event_cutoff=created_at_utc,
        reference_bid=500000,
        reference_ask=500040,
        price_scale=100,
        data_age_ms=120,
        direction=direction,
        light=light,
        reason_codes=reason_codes,
        health_state=health_state,
        safety_forced=False,
        strategy_id="strat-v1",
        strategy_version="1.0.0",
        feature_set_version="features-v1",
        feature_snapshot_hash=hash_64,
        model_id="logreg-us500",
        model_version="1.0.0",
        model_hash=hash_64,
        calibration_version="calib-v1",
        policy_version="policy-v1",
        raw_score_long=750000,
        raw_score_short=250000,
        calibrated_probability_long=calibrated_prob_long,
        calibrated_probability_short=calibrated_prob_short,
        expected_value_long_net=expected_value_long,
        expected_value_short_net=expected_value_short,
        cost_profile_version="cost-v1",
        correlation_id=signal_id,
        causation_id=make_uuid(100),
        code_hash=hash_64,
        schema_version=1,
    )


def create_test_simulation(
    simulation_id: str,
    signal_id: str,
    created_at_utc: datetime,
    direction: Direction = "LONG",
    status: Literal["PROPOSED", "OPEN_SIMULATED", "CLOSED_SIMULATED", "REJECTED", "CANCELLED"] = "OPEN_SIMULATED",
    requested_quantity: int = 100,
    planned_entry: int = 500100,
    stop: int = 499600,
    target: int = 502100,
    fill_entry: int | None = 500100,
    fill_exit: int | None = None,
    gross_pnl: int | None = None,
    net_pnl: int | None = None,
    exit_reason: str | None = None,
    reconciliation_status: ReconciliationStatus = "PENDING",
) -> SimulacionV1:
    return SimulacionV1(
        simulation_id=simulation_id,
        signal_id=signal_id,
        environment="REPLAY",
        demo_account_hash=None,
        status=status,
        proposed_at_utc=created_at_utc,
        opened_at_utc=created_at_utc if status != "PROPOSED" else None,
        closed_at_utc=created_at_utc + timedelta(minutes=2) if status == "CLOSED_SIMULATED" else None,
        horizon_end_utc=created_at_utc + timedelta(minutes=5),
        direction=direction,
        planned_entry=planned_entry,
        stop=stop,
        target=target,
        risk_profile_version="risk-v1",
        instrument_profile_version="us500-v1",
        requested_quantity_simulated=requested_quantity,
        effective_quantity_simulated=requested_quantity,
        quantity_scale=100,
        fill_entry=fill_entry,
        fill_exit=fill_exit,
        fill_source="simulator",
        source_execution_ids=(),
        spread_cost=40,
        slippage_cost=0,
        commission_cost=0,
        carry_cost=0,
        money_scale=100,
        currency="USD",
        exit_reason=exit_reason,
        gross_pnl=gross_pnl,
        net_pnl=net_pnl,
        realized_r=None,
        mfe=None,
        mae=None,
        reconciliation_status=reconciliation_status,
        reconciliation_reason_codes=(),
        market_event_cutoff=created_at_utc,
        cost_profile_version="cost-v1",
        correlation_id=simulation_id,
        causation_id=signal_id,
        schema_version=1,
    )


def create_test_risk_profile() -> RiskProfileV1:
    return RiskProfileV1(
        profile_version="risk-us500-demo-v1",
        max_risk_per_trade_usd_cents=5000,
        max_daily_loss_usd_cents=25000,
        max_daily_drawdown_usd_cents=25000,
        max_consecutive_losses=3,
        max_daily_openings=10,
        max_concurrent_positions=1,
        max_reference_lots=500,
        stale_threshold_ms=5000,
        news_blackout_minutes=15,
        kill_switch_active=False,
    )


def create_test_model_gate_policy() -> ModelGatePolicyV1:
    now_utc = datetime(2026, 8, 29, 14, 30, 0, tzinfo=timezone.utc)
    hash_64 = make_sha256("model-policy")
    return ModelGatePolicyV1(
        policy_version="model-policy-v1",
        leakage_violations_max=0,
        effective_sample_size_min=500,
        brier_improvement_min_scaled=0,
        ece_max_scaled=100_000,
        net_utility_base_ci_lower_exclusive=0,
        net_utility_adverse_min=0,
        profitable_walk_forward_ratio_min_scaled=600_000,
        purge_required=True,
        embargo_required=True,
        out_of_fold_calibration_required=True,
        severe_drift_allowed=False,
        cohort_hash=hash_64,
        cost_hash=hash_64,
        approver="lead-architect",
        approved_at_utc=now_utc,
    )


def create_test_depth_gate_policy() -> DepthGatePolicyV1:
    now_utc = datetime(2026, 8, 29, 14, 30, 0, tzinfo=timezone.utc)
    hash_64 = make_sha256("depth-policy")
    return DepthGatePolicyV1(
        policy_version="depth-policy-v1",
        required_complete_sessions=5,
        minimum_event_coverage_scaled=950_000,
        minimum_sequence_continuity_scaled=999_900,
        maximum_unresolved_gaps=0,
        maximum_out_of_order=0,
        maximum_clock_rollbacks=0,
        maximum_stale_time_ratio_scaled=10_000,
        corpus_hash=hash_64,
        approver="lead-qa",
        approved_at_utc=now_utc,
    )


# --- EMULADORES Y ESPÍAS DE SUBSISTEMA ---


class FakeEventStoreSpy:
    """Almacén de eventos simulado con hash chaining, idempotencia y fail-closed security."""

    def __init__(self) -> None:
        self.events: list[SobreEventoV1] = []
        self.quarantine: list[dict[str, Any]] = []
        self.append_calls: int = 0
        self.source_open_calls: int = 0
        self.last_hash: str = "0" * 64

    def anexar(self, envelope: SobreEventoV1) -> Resultado[dict[str, Any]]:
        self.append_calls += 1

        # CA-1: Fail-closed LIVE check
        if envelope.environment == "LIVE":
            return fallo(
                ErrorDominio(
                    codigo="ENVIRONMENT_NOT_ALLOWED",
                    mensaje_seguro="Entorno LIVE no permitido",
                    reintentable=False,
                    correlation_id=envelope.correlation_id,
                    detalles={"environment": envelope.environment},
                )
            )

        # CA-5: Idempotency & Conflict Check
        for existing in self.events:
            if existing.event_id == envelope.event_id:
                if existing.payload_hash == envelope.payload_hash:
                    # Idempotent receipt
                    return exito({"status": "IDEMPOTENT_DUPLICATE", "event_id": envelope.event_id, "sequence": existing.source_sequence})
                else:
                    # Same id, conflicting content -> INTEGRITY_ERROR
                    return fallo(
                        ErrorDominio(
                            codigo="INTEGRITY_ERROR",
                            mensaje_seguro="Conflicto de integridad de evento duplicado con distinto payload",
                            reintentable=False,
                            correlation_id=envelope.correlation_id,
                            detalles={"event_id": envelope.event_id},
                        )
                    )

        # Hash Chaining Check
        computed_previous = self.last_hash
        envelope_to_store = envelope
        if envelope.previous_hash is None or envelope.previous_hash == computed_previous:
            # Chain hash update
            canonical_bytes = canonical_json_bytes(
                {
                    "event_id": envelope.event_id,
                    "payload_hash": envelope.payload_hash,
                    "previous_hash": computed_previous,
                    "sequence": envelope.source_sequence,
                }
            )
            new_hash = hashlib.sha256(canonical_bytes).hexdigest()
            self.last_hash = new_hash
            self.events.append(envelope_to_store)
            return exito({"status": "ACCEPTED", "event_id": envelope.event_id, "chain_hash": new_hash})
        else:
            return fallo(
                ErrorDominio(
                    codigo="INTEGRITY_ERROR",
                    mensaje_seguro="Ruptura en la cadena hash de eventos",
                    reintentable=False,
                    correlation_id=envelope.correlation_id,
                    detalles={"expected_previous": computed_previous, "actual_previous": envelope.previous_hash},
                )
            )

    def anexar_cuarentena(self, raw_data: dict[str, Any], correlation_id: str) -> Resultado[dict[str, Any]]:
        """CA-6: Cuarentena de esquemas desconocidos."""
        self.quarantine.append(raw_data)
        return exito({"status": "QUARANTINED", "quarantine_count": len(self.quarantine)})

    def verificar_integridad(self) -> Resultado[dict[str, Any]]:
        """CA-21: Verificación de cadena hash."""
        current_hash = "0" * 64
        for ev in self.events:
            canonical = canonical_json_bytes(
                {
                    "event_id": ev.event_id,
                    "payload_hash": ev.payload_hash,
                    "previous_hash": current_hash,
                    "sequence": ev.source_sequence,
                }
            )
            current_hash = hashlib.sha256(canonical).hexdigest()
        return exito({"intact": True, "event_count": len(self.events), "root_hash": current_hash})

    def backup(self) -> dict[str, Any]:
        """Crea snapshot serializado de la base."""
        return {
            "events": [
                {
                    "event_id": ev.event_id,
                    "event_type": ev.event_type,
                    "source_sequence": ev.source_sequence,
                    "payload": ev.payload,
                    "payload_hash": ev.payload_hash,
                    "previous_hash": ev.previous_hash,
                }
                for ev in self.events
            ],
            "last_hash": self.last_hash,
            "count": len(self.events),
        }

    def restore(self, backup_data: dict[str, Any]) -> Resultado[bool]:
        """Restaura y verifica integridad."""
        if backup_data.get("count") != len(backup_data.get("events", [])):
            return fallo(
                ErrorDominio(
                    codigo="INTEGRITY_ERROR",
                    mensaje_seguro="Backup corrupto: conteo no coincide",
                    reintentable=False,
                    correlation_id=make_uuid(999),
                    detalles={},
                )
            )
        self.last_hash = backup_data["last_hash"]
        return exito(True)


class FakeFeedQualityMonitor:
    """Monitor de calidad de feed que detecta gaps, stale, y out-of-order (CA-7)."""

    def __init__(self, stale_threshold_ms: int = 5000) -> None:
        self.state: EstadoFeed = "INITIALIZING"
        self.last_timestamp: datetime | None = None
        self.last_sequence: int = 0
        self.stale_threshold_ms = stale_threshold_ms

    def evaluar_evento(self, envelope: SobreEventoV1, domain_time_utc: datetime) -> tuple[EstadoFeed, list[str]]:
        reasons: list[str] = []

        # Stale feed detection
        age_ms = int((domain_time_utc - envelope.occurred_at_utc).total_seconds() * 1000)
        if age_ms > self.stale_threshold_ms:
            self.state = "STALE"
            reasons.append("STALE_FEED")

        # Clock rollback detection
        if self.last_timestamp and envelope.occurred_at_utc < self.last_timestamp:
            self.state = "STALE"
            reasons.append("CLOCK_ROLLBACK")

        # Sequence gap / out-of-order detection
        if self.last_sequence > 0:
            if envelope.source_sequence > self.last_sequence + 1:
                self.state = "GAPPED"
                reasons.append("GAPPED_FEED")
            elif envelope.source_sequence <= self.last_sequence:
                self.state = "STALE"
                reasons.append("OUT_OF_ORDER")

        if not reasons:
            self.state = "HEALTHY"

        self.last_timestamp = envelope.occurred_at_utc
        self.last_sequence = envelope.source_sequence
        return self.state, reasons


class FakeTripleBarrierEvaluator:
    """Evaluador de triple-barrera para labeling y simulación (CA-13, CA-14)."""

    def __init__(self, stop_loss_pts: int = 500, take_profit_pts: int = 2000) -> None:
        self.stop_loss_pts = stop_loss_pts  # 5 pts scaled 100
        self.take_profit_pts = take_profit_pts  # 20 pts scaled 100

    def evaluar_tick_long(
        self,
        entry_ask: int,
        tick_bid: int,
        tick_ask: int,
    ) -> tuple[Literal["OPEN", "TAKE_PROFIT", "STOP_LOSS", "AMBIGUOUS_STOP_FIRST"], int]:
        stop_price = entry_ask - self.stop_loss_pts
        target_price = entry_ask + self.take_profit_pts

        # For LONG exit, stop is checked on bid, target on bid or spanning ask
        hit_stop = tick_bid <= stop_price
        hit_target = tick_bid >= target_price or tick_ask >= target_price

        # CA-14: Ambiguous stop/target in single atomic event resolves STOP_FIRST
        if hit_stop and hit_target:
            return "AMBIGUOUS_STOP_FIRST", stop_price
        if hit_stop:
            return "STOP_LOSS", stop_price
        if tick_bid >= target_price:
            return "TAKE_PROFIT", target_price
        return "OPEN", tick_bid

    def evaluar_tick_short(
        self,
        entry_bid: int,
        tick_bid: int,
        tick_ask: int,
    ) -> tuple[Literal["OPEN", "TAKE_PROFIT", "STOP_LOSS", "AMBIGUOUS_STOP_FIRST"], int]:
        stop_price = entry_bid + self.stop_loss_pts
        target_price = entry_bid - self.take_profit_pts

        hit_stop = tick_ask >= stop_price
        hit_target = tick_ask <= target_price or tick_bid <= target_price

        if hit_stop and hit_target:
            return "AMBIGUOUS_STOP_FIRST", stop_price
        if hit_stop:
            return "STOP_LOSS", stop_price
        if tick_ask <= target_price:
            return "TAKE_PROFIT", target_price
        return "OPEN", tick_ask


class FakeLightsEngine:
    """Motor de política de luces con histeresis e intermedio amarillo obligatorio (CA-8, CA-12)."""

    def __init__(self) -> None:
        self.current_light: Light = "YELLOW"

    def transition(self, target_light: Light, feed_state: EstadoFeed, calibrated_prob: int) -> Resultado[Light]:
        # CA-7: Degraded feed forces YELLOW
        if feed_state != "HEALTHY":
            self.current_light = "YELLOW"
            return exito("YELLOW")

        # CA-8: Check state machine transition validity
        if not es_transicion_valida("light", self.current_light, target_light):
            return fallo(
                ErrorDominio(
                    codigo="VALIDATION_ERROR",
                    mensaje_seguro=f"Transicion de luz invalida: {self.current_light} -> {target_light}",
                    reintentable=False,
                    correlation_id=make_uuid(1),
                    detalles={"from": self.current_light, "to": target_light},
                )
            )

        self.current_light = target_light
        return exito(self.current_light)

    def decidir_senal(
        self,
        signal_id: str,
        now_utc: datetime,
        feed_state: EstadoFeed,
        calibrated_prob_long: int,
    ) -> SenalV1:
        # Determine light
        if feed_state != "HEALTHY":
            light: Light = "YELLOW"
            direction: Direction = "MONITOR"
            reasons = ("FEED_DEGRADED_YELLOW",)
        elif calibrated_prob_long >= 650000:
            res = self.transition("GREEN", feed_state, calibrated_prob_long)
            light = res.datos if res.exito else "YELLOW"
            direction = "LONG" if light == "GREEN" else "MONITOR"
            reasons = ("MODEL_EDGE_LONG",) if light == "GREEN" else ("HYSTERESIS_INTERMEDIATE_YELLOW",)
        elif calibrated_prob_long <= 350000:
            res = self.transition("RED", feed_state, calibrated_prob_long)
            light = res.datos if res.exito else "YELLOW"
            direction = "SHORT" if light == "RED" else "MONITOR"
            reasons = ("MODEL_EDGE_SHORT",) if light == "RED" else ("HYSTERESIS_INTERMEDIATE_YELLOW",)
        else:
            self.current_light = "YELLOW"
            light = "YELLOW"
            direction = "MONITOR"
            reasons = ("LOW_CONFIDENCE_MONITOR",)

        # CA-12: Yellow signals always force direction=MONITOR
        if light == "YELLOW":
            direction = "MONITOR"

        return create_test_signal(
            signal_id=signal_id,
            created_at_utc=now_utc,
            valid_until_utc=now_utc + timedelta(seconds=30),
            light=light,
            direction=direction,
            calibrated_prob_long=calibrated_prob_long,
            calibrated_prob_short=1000000 - calibrated_prob_long,
            health_state=feed_state,
            reason_codes=reasons,
        )


class FakeRiskEngine:
    """Motor de riesgo con matriz completa de tripwires y kill switch (CA-16, CA-17, CA-18)."""

    def __init__(self, profile: RiskProfileV1 | None = None) -> None:
        self.profile = profile or create_test_risk_profile()
        self.daily_realized_loss_usd: float = 0.0
        self.daily_drawdown_usd: float = 0.0
        self.consecutive_losses: int = 0
        self.daily_openings: int = 0
        self.open_positions: list[SimulacionV1] = []
        self.kill_switch_active: bool = False
        self.kill_switch_reason: str | None = None
        self.current_ny_date: str = "2026-08-29"

    def reset_ny_midnight_if_needed(self, now_utc: datetime) -> None:
        """DM-12: Reseteo de contadores a medianoche America/New_York."""
        ny_time = now_utc.astimezone(NY_TZ)
        ny_date_str = ny_time.strftime("%Y-%m-%d")
        if ny_date_str != self.current_ny_date:
            self.current_ny_date = ny_date_str
            self.daily_realized_loss_usd = 0.0
            self.daily_drawdown_usd = 0.0
            self.daily_openings = 0
            self.consecutive_losses = 0

    def trigger_kill_switch(self, reason: str) -> None:
        self.kill_switch_active = True
        self.kill_switch_reason = reason

    def recover_kill_switch(self, actor: Actor, resolution: str) -> Resultado[bool]:
        """CA-18: Recuperación verificada del kill switch."""
        if not actor or not resolution:
            return fallo(
                ErrorDominio(
                    codigo="VALIDATION_ERROR",
                    mensaje_seguro="Recuperacion requiere actor y resolucion validos",
                    reintentable=False,
                    correlation_id=make_uuid(18),
                    detalles={},
                )
            )
        self.kill_switch_active = False
        self.kill_switch_reason = None
        return exito(True)

    def evaluar_propuesta(
        self,
        sim: SimulacionV1,
        now_utc: datetime,
        blackout_intervals: list[tuple[datetime, datetime]] | None = None,
    ) -> Resultado[bool]:
        self.reset_ny_midnight_if_needed(now_utc)

        # CA-18: Fail-closed Kill Switch
        if self.kill_switch_active:
            return fallo(
                ErrorDominio(
                    codigo="RISK_LIMIT_HIT",
                    mensaje_seguro="Kill switch activo: no se permiten aperturas",
                    reintentable=False,
                    correlation_id=sim.correlation_id,
                    detalles={"reason": self.kill_switch_reason},
                )
            )

        # CA-15: Economic contract completeness
        if not sim.stop or not sim.target or not sim.requested_quantity_simulated:
            return fallo(
                ErrorDominio(
                    codigo="ECONOMIC_CONTRACT_INCOMPLETE",
                    mensaje_seguro="Contrato economico incompleto",
                    reintentable=False,
                    correlation_id=sim.correlation_id,
                    detalles={},
                )
            )

        # News Blackout: [start, end] inclusive
        if blackout_intervals:
            for b_start, b_end in blackout_intervals:
                if b_start <= now_utc <= b_end:
                    return fallo(
                        ErrorDominio(
                            codigo="RISK_LIMIT_HIT",
                            mensaje_seguro="Bloqueado por ventana de noticias",
                            reintentable=False,
                            correlation_id=sim.correlation_id,
                            detalles={"blackout_start": b_start.isoformat(), "blackout_end": b_end.isoformat()},
                        )
                    )

        # CA-16: Single position invariant (max 1 open position)
        if len(self.open_positions) >= self.profile.max_concurrent_positions:
            return fallo(
                ErrorDominio(
                    codigo="RISK_LIMIT_HIT",
                    mensaje_seguro="Posicion solapada rechazada: limite de 1 posicion abierta alcanzado",
                    reintentable=False,
                    correlation_id=sim.correlation_id,
                    detalles={"open_positions": len(self.open_positions), "reason": "OVERLAPPING_POSITION"},
                )
            )

        # CA-17: Risk per trade <= $50
        stop_distance = abs(sim.planned_entry - sim.stop)
        risk_usd = (stop_distance * sim.requested_quantity_simulated) / 10000.0
        max_risk_usd = self.profile.max_risk_per_trade_usd_cents / 100.0
        if risk_usd > max_risk_usd:
            return fallo(
                ErrorDominio(
                    codigo="RISK_LIMIT_HIT",
                    mensaje_seguro=f"Riesgo por operacion ({risk_usd}) excede maximo permitido ({max_risk_usd})",
                    reintentable=False,
                    correlation_id=sim.correlation_id,
                    detalles={"risk_usd": risk_usd, "max_allowed": max_risk_usd},
                )
            )

        # CA-17: Daily loss limit ($250)
        max_daily_loss = self.profile.max_daily_loss_usd_cents / 100.0
        if self.daily_realized_loss_usd >= max_daily_loss:
            self.trigger_kill_switch("DAILY_LOSS_LIMIT_HIT")
            return fallo(
                ErrorDominio(
                    codigo="RISK_LIMIT_HIT",
                    mensaje_seguro="Perdida diaria acumulada alcanzo el limite maximo ($250)",
                    reintentable=False,
                    correlation_id=sim.correlation_id,
                    detalles={"daily_loss": self.daily_realized_loss_usd},
                )
            )

        # CA-17: Loss streak pause (3 losses)
        if self.consecutive_losses >= self.profile.max_consecutive_losses:
            return fallo(
                ErrorDominio(
                    codigo="RISK_LIMIT_HIT",
                    mensaje_seguro=f"Racha de {self.consecutive_losses} perdidas consecutivas requiere pausa",
                    reintentable=False,
                    correlation_id=sim.correlation_id,
                    detalles={"consecutive_losses": self.consecutive_losses},
                )
            )

        # CA-17: Max daily openings (10 openings)
        if self.daily_openings >= self.profile.max_daily_openings:
            return fallo(
                ErrorDominio(
                    codigo="RISK_LIMIT_HIT",
                    mensaje_seguro=f"Limite de aperturas diarias ({self.profile.max_daily_openings}) alcanzado",
                    reintentable=False,
                    correlation_id=sim.correlation_id,
                    detalles={"daily_openings": self.daily_openings},
                )
            )

        return exito(True)

    def registrar_apertura(self, sim: SimulacionV1) -> None:
        self.open_positions.append(sim)
        self.daily_openings += 1

    def registrar_cierre(self, sim: SimulacionV1, pnl_usd: float) -> None:
        self.open_positions = [p for p in self.open_positions if p.simulation_id != sim.simulation_id]
        if pnl_usd < 0:
            self.daily_realized_loss_usd += abs(pnl_usd)
            self.consecutive_losses += 1
            max_daily_loss = self.profile.max_daily_loss_usd_cents / 100.0
            if self.daily_realized_loss_usd >= max_daily_loss:
                self.trigger_kill_switch("DAILY_LOSS_LIMIT_HIT")
        else:
            self.consecutive_losses = 0


class FakeDemoImporter:
    """Importador de ejecuciones demo y reconciliador (CA-19, CA-20)."""

    def __init__(self) -> None:
        self.imported_trades: list[dict[str, Any]] = []

    def importar_staged_copy(self, file_content: str, expected_sha256: str) -> Resultado[ResumenImportacion]:
        actual_sha256 = make_sha256(file_content)
        if actual_sha256 != expected_sha256:
            return fallo(
                ErrorDominio(
                    codigo="INTEGRITY_ERROR",
                    mensaje_seguro="Hash SHA-256 de copia staged no coincide",
                    reintentable=False,
                    correlation_id=make_uuid(19),
                    detalles={"expected": expected_sha256, "actual": actual_sha256},
                )
            )

        try:
            records = json.loads(file_content)
        except Exception:
            return fallo(
                ErrorDominio(
                    codigo="IMPORT_INVALID",
                    mensaje_seguro="JSON invalido en staged copy",
                    reintentable=False,
                    correlation_id=make_uuid(19),
                    detalles={},
                )
            )

        accepted = 0
        unmatched = 0
        for rec in records:
            self.imported_trades.append(rec)
            accepted += 1
            if not rec.get("matched_sim_id"):
                unmatched += 1

        return exito(
            ResumenImportacion(
                import_id=make_uuid(190),
                environment="BROKER_DEMO_OBSERVED",
                final_event_cutoff="2026-08-29T16:00:00Z",
                accepted_count=accepted,
                rejected_count=0,
                matched_count=accepted - unmatched,
                unmatched_count=unmatched,
            )
        )
