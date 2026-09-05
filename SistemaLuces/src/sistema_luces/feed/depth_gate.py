"""Evaluador de compuerta de depth y cuarentena de sesiones (SPEC-001 §6.8, §12.7, CA-25)."""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal
import uuid

from sistema_luces.domain.manifest import DepthGatePolicyV1
from sistema_luces.domain.result import Resultado, exito, fallo


@dataclass(frozen=True)
class ResumenSesionDepth:
    session_id: str
    is_complete: bool
    has_unknown_segment: bool
    event_coverage_scaled: int
    sequence_continuity_scaled: int
    unresolved_gaps: int
    out_of_order_count: int
    clock_rollbacks_count: int
    stale_time_ratio_scaled: int
    metrics_persisted: bool


@dataclass(frozen=True)
class DecisionCompuertaDepth:
    decision_id: str
    status: Literal["ACCEPTED", "REJECTED", "QUARANTINED"]
    reason_codes: tuple[str, ...]
    policy_version: str
    evaluated_at_utc: datetime


class EvaluadorCompuertaDepth:
    """Comprueba politicas de calidad para autorizar o poner en cuarentena el libro L2/Depth."""

    def evaluar_sesiones(
        self,
        sesiones: list[ResumenSesionDepth],
        policy: DepthGatePolicyV1 | None,
    ) -> Resultado[DecisionCompuertaDepth]:
        now_utc = datetime.now(timezone.utc)
        decision_id = str(uuid.uuid4())

        # 1. Comprobar existencia y aprobacion de politica
        if policy is None or not getattr(policy, "approver", "").strip():
            return exito(
                DecisionCompuertaDepth(
                    decision_id=decision_id,
                    status="QUARANTINED",
                    reason_codes=("DEPTH_POLICY_MISSING",),
                    policy_version="none",
                    evaluated_at_utc=now_utc,
                )
            )

        # 2. Filtrar sesiones completas y validas
        sesiones_completas = [
            s for s in sesiones
            if s.is_complete and not s.has_unknown_segment and s.metrics_persisted
        ]

        if len(sesiones_completas) < policy.required_complete_sessions:
            return exito(
                DecisionCompuertaDepth(
                    decision_id=decision_id,
                    status="QUARANTINED",
                    reason_codes=("DEPTH_SESSIONS_INSUFFICIENT",),
                    policy_version=policy.policy_version,
                    evaluated_at_utc=now_utc,
                )
            )

        # 3. Evaluar umbrales de politica para cada sesion
        rejections: list[str] = []
        for s in sesiones_completas:
            if s.event_coverage_scaled < policy.minimum_event_coverage_scaled:
                rejections.append("DEPTH_COVERAGE_BELOW_MINIMUM")
            if s.sequence_continuity_scaled < policy.minimum_sequence_continuity_scaled:
                rejections.append("DEPTH_CONTINUITY_BELOW_MINIMUM")
            if s.unresolved_gaps > policy.maximum_unresolved_gaps:
                rejections.append("DEPTH_UNRESOLVED_GAPS_EXCEEDED")
            if s.out_of_order_count > policy.maximum_out_of_order:
                rejections.append("DEPTH_OUT_OF_ORDER_EXCEEDED")
            if s.clock_rollbacks_count > policy.maximum_clock_rollbacks:
                rejections.append("DEPTH_CLOCK_ROLLBACKS_EXCEEDED")
            if s.stale_time_ratio_scaled > policy.maximum_stale_time_ratio_scaled:
                rejections.append("DEPTH_STALE_RATIO_EXCEEDED")

        if rejections:
            unique_rejections = sorted(set(rejections))
            return exito(
                DecisionCompuertaDepth(
                    decision_id=decision_id,
                    status="REJECTED",
                    reason_codes=("DEPTH_GATE_REJECTED", *unique_rejections),
                    policy_version=policy.policy_version,
                    evaluated_at_utc=now_utc,
                )
            )

        return exito(
            DecisionCompuertaDepth(
                decision_id=decision_id,
                status="ACCEPTED",
                reason_codes=("DEPTH_GATE_ACCEPTED",),
                policy_version=policy.policy_version,
                evaluated_at_utc=now_utc,
            )
        )
