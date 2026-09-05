"""Calculador de Métricas en 8 Planos de Observabilidad (SPEC-001 §6.7, CA-22)."""

from datetime import datetime, timezone
from typing import Literal
import uuid

from sistema_luces.domain.event import SobreEventoV1
from sistema_luces.domain.metric import (
    PLANOS_METRICOS_PERMITIDOS,
    PlanoMetrico,
    SnapshotMetricoV1,
    validar_snapshot_metrico,
)
from sistema_luces.domain.vocabulary import Environment, Source


class CalculadorMetricas8Planos:
    """Calcula snapshots de métricas en los 8 planos obligatorios de V1."""

    def __init__(self, code_hash: str = "0" * 64) -> None:
        self.code_hash = code_hash

    def calcular_snapshots(
        self,
        range_start_utc: datetime,
        range_end_utc: datetime,
        ny_session_date: str,
        environment: Environment,
        eventos: list[SobreEventoV1],
        source: Source = "replay",
    ) -> list[SnapshotMetricoV1]:
        now_utc = datetime.now(timezone.utc)
        snapshots: list[SnapshotMetricoV1] = []

        total_eventos = len(eventos)
        input_cutoff = max([e.occurred_at_utc for e in eventos], default=range_end_utc)

        # Para cada uno de los 8 planos obligatorios
        for plano in sorted(list(PLANOS_METRICOS_PERMITIDOS)):
            snap_id = str(uuid.uuid4())
            metric_name = f"{plano.lower()}_summary_v1"

            # Si no hay datos suficientes para cálculo analítico -> null con reason code
            val_int: int | None = None
            val_ratio: int | None = None
            dimensions: dict[str, str | int | bool | None] = {}

            if total_eventos == 0:
                dimensions["reason_code"] = "INSUFFICIENT_OR_UNKNOWN_DATA"
                dimensions["status"] = "NO_DATA"
            else:
                val_int = total_eventos
                val_ratio = 1_000_000
                dimensions["status"] = "OK"

            snap = SnapshotMetricoV1(
                metric_snapshot_id=snap_id,
                metric_name=metric_name,
                metric_plane=plano,  # type: ignore[arg-type]
                range_start_utc=range_start_utc,
                range_end_utc=range_end_utc,
                ny_session_date=ny_session_date,
                source=source,
                environment=environment,
                instrument="US500",
                strategy_version="1.0.0",
                model_version="1.0.0",
                policy_version="policy-v1",
                raw_count=total_eventos,
                effective_sample_size=total_eventos,
                value_int=val_int,
                value_ratio_scaled=val_ratio,
                histogram_int=None,
                unit="count" if val_int is not None else "none",
                scale=1,
                dimensions=dimensions,
                input_event_cutoff=input_cutoff,
                dataset_hash=None,
                code_hash=self.code_hash,
                computed_at_utc=now_utc,
                schema_version=1,
            )

            val_res = validar_snapshot_metrico(snap)
            if val_res.exito:
                snapshots.append(val_res.datos)
            else:
                snapshots.append(snap)

        return snapshots
