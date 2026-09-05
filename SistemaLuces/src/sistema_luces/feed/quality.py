"""Monitor de calidad de feed: deteccion de gaps, duplicados, out-of-order, stale y clock rollback (SPEC-001 §6.3, CA-7)."""

from datetime import datetime, timezone
import uuid

from sistema_luces.domain.event import SobreEventoV1, compute_payload_hash
from sistema_luces.sources.clock import RelojDominio


class MonitorCalidadFeed:
    """Inspecciona el flujo entrante de eventos para auditar anomalias de calidad."""

    def __init__(self, stale_threshold_ms: int = 5000) -> None:
        self._stale_threshold_ms = stale_threshold_ms
        self._last_sequence: int | None = None
        self._last_occurred_at: datetime | None = None
        self._seen_ids: dict[str, str] = {}
        self._feed_state: str = "INITIALIZING"

    @property
    def feed_state(self) -> str:
        return self._feed_state

    def evaluar_evento(
        self,
        evento: SobreEventoV1,
        reloj: RelojDominio,
    ) -> tuple[str, list[SobreEventoV1]]:
        """Evalua un evento entrante y retorna el nuevo estado del feed y la lista de alertas generadas."""
        alertas: list[SobreEventoV1] = []
        now_utc = reloj.ahora_utc()

        # 1. Deteccion de duplicados (CA-7)
        if evento.event_id in self._seen_ids:
            p_dup = {
                "duplicate_key": evento.event_id,
                "retained_event_id": self._seen_ids[evento.event_id],
                "action": "IGNORE",
            }
            alertas.append(
                SobreEventoV1(
                    event_id=str(uuid.uuid4()),
                    event_type="DUPLICATE",
                    schema_version=1,
                    occurred_at_utc=now_utc,
                    received_at_utc=now_utc,
                    persisted_at_utc=None,
                    source="system",
                    environment=evento.environment,
                    source_account_id_hash=None,
                    instrument=evento.instrument,
                    symbol_id=None,
                    source_sequence=None,
                    correlation_id=evento.correlation_id,
                    causation_id=evento.event_id,
                    payload_hash=compute_payload_hash(p_dup),
                    previous_hash=None,
                    payload=p_dup,
                )
            )
        else:
            self._seen_ids[evento.event_id] = evento.event_id

        # 2. Deteccion de clock rollback (CA-7)
        if self._last_occurred_at is not None and evento.occurred_at_utc < self._last_occurred_at:
            delta_ms = int((self._last_occurred_at - evento.occurred_at_utc).total_seconds() * 1000)
            p_rollback = {
                "previous_time_utc": self._last_occurred_at.isoformat(),
                "new_time_utc": evento.occurred_at_utc.isoformat(),
                "delta_ms": delta_ms,
                "action": "FAIL_CLOSED",
            }
            alertas.append(
                SobreEventoV1(
                    event_id=str(uuid.uuid4()),
                    event_type="CLOCK_ROLLBACK",
                    schema_version=1,
                    occurred_at_utc=now_utc,
                    received_at_utc=now_utc,
                    persisted_at_utc=None,
                    source="system",
                    environment=evento.environment,
                    source_account_id_hash=None,
                    instrument=evento.instrument,
                    symbol_id=None,
                    source_sequence=None,
                    correlation_id=evento.correlation_id,
                    causation_id=evento.event_id,
                    payload_hash=compute_payload_hash(p_rollback),
                    previous_hash=None,
                    payload=p_rollback,
                )
            )

        # 3. Deteccion de gaps de secuencia y fuera de orden (CA-7)
        if evento.source_sequence is not None:
            if self._last_sequence is not None:
                if evento.source_sequence > self._last_sequence + 1:
                    missing = evento.source_sequence - self._last_sequence - 1
                    p_gap = {
                        "start_sequence": self._last_sequence + 1,
                        "end_sequence": evento.source_sequence - 1,
                        "missing_count": missing,
                        "action": "FORCE_YELLOW_STOP_SIM",
                    }
                    alertas.append(
                        SobreEventoV1(
                            event_id=str(uuid.uuid4()),
                            event_type="GAP_DETECTED",
                            schema_version=1,
                            occurred_at_utc=now_utc,
                            received_at_utc=now_utc,
                            persisted_at_utc=None,
                            source="system",
                            environment=evento.environment,
                            source_account_id_hash=None,
                            instrument=evento.instrument,
                            symbol_id=None,
                            source_sequence=None,
                            correlation_id=evento.correlation_id,
                            causation_id=evento.event_id,
                            payload_hash=compute_payload_hash(p_gap),
                            previous_hash=None,
                            payload=p_gap,
                        )
                    )
                    self._feed_state = "GAPPED"
                elif evento.source_sequence < self._last_sequence:
                    p_ooo = {
                        "expected_sequence": self._last_sequence + 1,
                        "received_sequence": evento.source_sequence,
                        "action": "QUARANTINE",
                    }
                    alertas.append(
                        SobreEventoV1(
                            event_id=str(uuid.uuid4()),
                            event_type="OUT_OF_ORDER",
                            schema_version=1,
                            occurred_at_utc=now_utc,
                            received_at_utc=now_utc,
                            persisted_at_utc=None,
                            source="system",
                            environment=evento.environment,
                            source_account_id_hash=None,
                            instrument=evento.instrument,
                            symbol_id=None,
                            source_sequence=None,
                            correlation_id=evento.correlation_id,
                            causation_id=evento.event_id,
                            payload_hash=compute_payload_hash(p_ooo),
                            previous_hash=None,
                            payload=p_ooo,
                        )
                    )
            self._last_sequence = evento.source_sequence

        # 4. Deteccion de stale (antiguedad > umbral_ms) (CA-7)
        age_ms = int((now_utc - evento.occurred_at_utc).total_seconds() * 1000)
        if age_ms > self._stale_threshold_ms:
            p_stale = {
                "data_age_ms": age_ms,
                "threshold_ms": self._stale_threshold_ms,
                "action": "FORCE_YELLOW",
            }
            alertas.append(
                SobreEventoV1(
                    event_id=str(uuid.uuid4()),
                    event_type="STALE",
                    schema_version=1,
                    occurred_at_utc=now_utc,
                    received_at_utc=now_utc,
                    persisted_at_utc=None,
                    source="system",
                    environment=evento.environment,
                    source_account_id_hash=None,
                    instrument=evento.instrument,
                    symbol_id=None,
                    source_sequence=None,
                    correlation_id=evento.correlation_id,
                    causation_id=evento.event_id,
                    payload_hash=compute_payload_hash(p_stale),
                    previous_hash=None,
                    payload=p_stale,
                )
            )
            self._feed_state = "STALE"
        elif self._feed_state != "GAPPED":
            self._feed_state = "HEALTHY"

        self._last_occurred_at = evento.occurred_at_utc
        return (self._feed_state, alertas)
