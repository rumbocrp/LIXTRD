"""Manifiestos complementarios y politicas de gate (SPEC-001 §6.8, §12.7)."""

from dataclasses import dataclass
from datetime import datetime
import re
from typing import Literal

from sistema_luces.domain.error import ErrorDominio
from sistema_luces.domain.result import Resultado, exito, fallo
from sistema_luces.domain.vocabulary import (
    parse_instrument,
    validate_cost_scaled,
    validate_price_scaled,
    validate_probability_scaled,
    validate_quantity_scaled,
    validate_scale_factor,
)

_HASH_REGEX = re.compile(r"^[0-9a-f]{64}$", re.IGNORECASE)


def _is_valid_hash(h: str) -> bool:
    return isinstance(h, str) and bool(_HASH_REGEX.match(h))


@dataclass(frozen=True)
class InstrumentProfileV1:
    profile_version: str
    instrument: Literal["US500"]
    provider: str
    symbol_id: str
    price_scale: int
    point_size: int
    lot_min: int
    lot_step: int
    lot_max: int
    currency: str
    point_value: int
    economic_ready: bool
    validation_evidence_hash: str | None
    schema_id: str | None = None


def validar_instrument_profile(prof: InstrumentProfileV1) -> Resultado[InstrumentProfileV1]:
    inst_res = parse_instrument(prof.instrument)
    if not inst_res.exito:
        return fallo(inst_res.error)
    for name, val in [
        ("price_scale", prof.price_scale),
        ("point_size", prof.point_size),
        ("lot_min", prof.lot_min),
        ("lot_step", prof.lot_step),
        ("lot_max", prof.lot_max),
        ("point_value", prof.point_value),
    ]:
        res = validate_scale_factor(val)
        if not res.exito:
            return fallo(res.error)
    if prof.validation_evidence_hash is not None and not _is_valid_hash(prof.validation_evidence_hash):
        return fallo(
            ErrorDominio(
                codigo="VALIDATION_ERROR",
                mensaje_seguro="validation_evidence_hash debe ser SHA-256 valido",
                reintentable=False,
                correlation_id="",
                detalles={},
            )
        )
    return exito(prof)


@dataclass(frozen=True)
class CostProfileV1:
    profile_version: str
    spread_points_base: int
    spread_points_adverse: int
    spread_points_stress: int
    slippage_points_base: int
    slippage_points_adverse: int
    slippage_points_stress: int
    commission_per_lot_usd_cents: int
    carry_per_night_usd_cents: int
    latency_ms_base: int
    latency_ms_stress: int
    schema_id: str | None = None


def validar_cost_profile(cost: CostProfileV1) -> Resultado[CostProfileV1]:
    for name, val in [
        ("spread_points_base", cost.spread_points_base),
        ("spread_points_adverse", cost.spread_points_adverse),
        ("spread_points_stress", cost.spread_points_stress),
        ("slippage_points_base", cost.slippage_points_base),
        ("slippage_points_adverse", cost.slippage_points_adverse),
        ("slippage_points_stress", cost.slippage_points_stress),
        ("commission_per_lot_usd_cents", cost.commission_per_lot_usd_cents),
        ("carry_per_night_usd_cents", cost.carry_per_night_usd_cents),
        ("latency_ms_base", cost.latency_ms_base),
        ("latency_ms_stress", cost.latency_ms_stress),
    ]:
        res = validate_cost_scaled(val)
        if not res.exito:
            return fallo(res.error)
    return exito(cost)


@dataclass(frozen=True)
class RiskProfileV1:
    profile_version: str = "risk-us500-demo-v1"
    max_risk_per_trade_usd_cents: int = 5000
    max_daily_loss_usd_cents: int = 25000
    max_daily_drawdown_usd_cents: int = 25000
    max_consecutive_losses: int = 3
    max_daily_openings: int = 10
    max_concurrent_positions: int = 1
    max_reference_lots: int = 500
    stale_threshold_ms: int = 5000
    news_blackout_minutes: int = 15
    kill_switch_active: bool = False
    schema_id: str | None = None
    version: int = 1
    max_risk_per_trade_usd: int = 50
    max_daily_loss_usd: int = 250
    max_daily_drawdown_usd: int = 250
    max_loss_streak: int = 3
    max_open_positions: int = 1
    max_lots_per_trade: int = 5
    news_blackout_minutes_before: int = 5
    news_blackout_minutes_after: int = 5


def validar_risk_profile(risk: RiskProfileV1) -> Resultado[RiskProfileV1]:
    for name, val in [
        ("max_risk_per_trade_usd_cents", risk.max_risk_per_trade_usd_cents),
        ("max_daily_loss_usd_cents", risk.max_daily_loss_usd_cents),
        ("max_daily_drawdown_usd_cents", risk.max_daily_drawdown_usd_cents),
        ("max_consecutive_losses", risk.max_consecutive_losses),
        ("max_daily_openings", risk.max_daily_openings),
        ("max_concurrent_positions", risk.max_concurrent_positions),
        ("max_reference_lots", risk.max_reference_lots),
        ("stale_threshold_ms", risk.stale_threshold_ms),
        ("news_blackout_minutes", risk.news_blackout_minutes),
    ]:
        if not isinstance(val, int) or val <= 0:
            return fallo(
                ErrorDominio(
                    codigo="VALIDATION_ERROR",
                    mensaje_seguro=f"Parametro de riesgo {name} debe ser mayor a 0",
                    reintentable=False,
                    correlation_id="",
                    detalles={"parametro": name, "valor": str(val)},
                )
            )
    return exito(risk)


@dataclass(frozen=True)
class ImportManifestV1:
    import_id: str
    format: str
    adapter_version: str
    timestamp_utc: datetime
    file_sha256: str
    file_size_bytes: int
    accepted_rows: int
    rejected_rows: int
    source_origin_hash: str
    schema_id: str | None = None


def validar_import_manifest(imp: ImportManifestV1) -> Resultado[ImportManifestV1]:
    if not _is_valid_hash(imp.file_sha256) or not _is_valid_hash(imp.source_origin_hash):
        return fallo(
            ErrorDominio(
                codigo="VALIDATION_ERROR",
                mensaje_seguro="Los hashes del manifiesto de importacion deben ser SHA-256 validos",
                reintentable=False,
                correlation_id="",
                detalles={},
            )
        )
    if imp.file_size_bytes <= 0:
        return fallo(
            ErrorDominio(
                codigo="VALIDATION_ERROR",
                mensaje_seguro="El tamano de archivo debe ser mayor a 0",
                reintentable=False,
                correlation_id="",
                detalles={"tamano": imp.file_size_bytes},
            )
        )
    return exito(imp)


@dataclass(frozen=True)
class DepthGatePolicyV1:
    policy_version: str = "depth-policy-v1"
    required_complete_sessions: int = 5
    minimum_event_coverage_scaled: int = 950_000
    minimum_sequence_continuity_scaled: int = 999_900
    maximum_unresolved_gaps: int = 0
    maximum_out_of_order: int = 0
    maximum_clock_rollbacks: int = 0
    maximum_stale_time_ratio_scaled: int = 10_000
    corpus_hash: str = "a" * 64
    approver: str = "lead"
    approved_at_utc: datetime | None = None
    schema_id: str | None = None
    version: int = 1
    min_consecutive_sessions: int = 5
    max_sequence_gap_rate: int = 1000
    max_stale_rate: int = 5000
    require_explicit_approver: bool = True


def validar_depth_gate_policy(policy: DepthGatePolicyV1) -> Resultado[DepthGatePolicyV1]:
    if not _is_valid_hash(policy.corpus_hash):
        return fallo(
            ErrorDominio(
                codigo="VALIDATION_ERROR",
                mensaje_seguro="corpus_hash debe ser SHA-256 valido",
                reintentable=False,
                correlation_id="",
                detalles={},
            )
        )
    if not policy.approver.strip():
        return fallo(
            ErrorDominio(
                codigo="VALIDATION_ERROR",
                mensaje_seguro="Se requiere aprobador explicito para depth gate policy",
                reintentable=False,
                correlation_id="",
                detalles={},
            )
        )
    return exito(policy)


@dataclass(frozen=True)
class ModelGatePolicyV1:
    policy_version: str = "model-policy-v1"
    leakage_violations_max: int = 0
    effective_sample_size_min: int = 500
    brier_improvement_min_scaled: int = 0
    ece_max_scaled: int = 100_000
    net_utility_base_ci_lower_exclusive: int = 0
    net_utility_adverse_min: int = 0
    profitable_walk_forward_ratio_min_scaled: int = 600_000
    purge_required: bool = True
    embargo_required: bool = True
    out_of_fold_calibration_required: bool = True
    severe_drift_allowed: bool = False
    cohort_hash: str = "a" * 64
    cost_hash: str = "a" * 64
    approver: str = "lead"
    approved_at_utc: datetime | None = None
    schema_id: str | None = None
    version: int = 1
    min_effective_sample_size: int = 500
    max_calibration_ece: int = 100000
    min_walk_forward_positive_ratio: int = 600000
    require_out_of_fold_calibration: bool = True
    require_purged_embargo_splits: bool = True
    max_leakage_violations: int = 0


def validar_model_gate_policy(policy: ModelGatePolicyV1) -> Resultado[ModelGatePolicyV1]:
    if not _is_valid_hash(policy.cohort_hash) or not _is_valid_hash(policy.cost_hash):
        return fallo(
            ErrorDominio(
                codigo="VALIDATION_ERROR",
                mensaje_seguro="cohort_hash y cost_hash deben ser SHA-256 validos",
                reintentable=False,
                correlation_id="",
                detalles={},
            )
        )
    if not policy.approver.strip():
        return fallo(
            ErrorDominio(
                codigo="VALIDATION_ERROR",
                mensaje_seguro="Se requiere aprobador explicito para model gate policy",
                reintentable=False,
                correlation_id="",
                detalles={},
            )
        )
    return exito(policy)
