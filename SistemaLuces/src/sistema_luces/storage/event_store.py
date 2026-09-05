"""Event Store inmutable, append atomico, verificacion de hashes y paginacion (SPEC-001 §5.3, §6.1, CA-4, CA-5, CA-21)."""

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Any

from sistema_luces.domain.error import ErrorDominio
from sistema_luces.domain.event import (
    SobreEventoV1,
    canonical_json_dumps,
    canonical_json_bytes,
    compute_payload_hash,
    validar_sobre_evento,
)
from sistema_luces.domain.result import Resultado, exito, fallo
from sistema_luces.storage.sqlite import conectar_db, inicializar_db


def _parse_iso_utc(val: str) -> datetime:
    val_clean = val.replace("Z", "+00:00")
    return datetime.fromisoformat(val_clean).astimezone(timezone.utc)


def _format_iso_utc(dt: datetime) -> str:
    utc_dt = dt.astimezone(timezone.utc)
    if utc_dt.microsecond > 0:
        return utc_dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    return utc_dt.strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass(frozen=True)
class ReciboEvento:
    event_id: str
    row_id: int
    persisted_at_utc: datetime
    payload_hash: str
    previous_hash: str | None
    idempotent: bool


@dataclass(frozen=True)
class LoteEventosV1:
    batch_id: str
    root_hash: str
    events: tuple[SobreEventoV1, ...]


@dataclass(frozen=True)
class ReciboLote:
    batch_id: str
    first_row_id: int
    last_row_id: int
    accepted_count: int
    rejected_count: int
    reason_codes: tuple[str, ...]


@dataclass(frozen=True)
class ConsultaEventos:
    range_start_utc: datetime | None = None
    range_end_utc: datetime | None = None
    event_types: tuple[str, ...] | None = None
    cutoff_event_id: str | None = None
    cursor: str | None = None
    limit: int = 100


@dataclass(frozen=True)
class PaginaEventos:
    events: tuple[SobreEventoV1, ...]
    cutoff_event_id: str | None
    next_cursor: str | None


@dataclass(frozen=True)
class RangoEventos:
    start_row_id: int | None = None
    end_row_id: int | None = None
    start_event_id: str | None = None
    end_event_id: str | None = None


@dataclass(frozen=True)
class InformeIntegridad:
    range_checked: RangoEventos
    event_count: int
    root_hash: str
    violations: tuple[str, ...]
    is_valid: bool


@dataclass(frozen=True)
class EntradaAuditoriaV1:
    audit_id: str
    actor: str
    operation: str
    result: str
    correlation_id: str
    details: dict[str, Any]


@dataclass(frozen=True)
class ReciboAuditoria:
    audit_id: str
    row_id: int
    persisted_at_utc: datetime
    entry_hash: str


class ArchivoEventos:
    """Almacen inmutable de eventos con encadenamiento de hashes e idempotencia."""

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path) if isinstance(db_path, str) else db_path
        inicializar_db(self.db_path)

    def anexar(self, evento: SobreEventoV1) -> Resultado[ReciboEvento]:
        """Anexa un sobre de evento validando integridad, idempotencia y hashes."""
        # 1. Validar sobre de dominio
        val_res = validar_sobre_evento(evento)
        if not val_res.exito:
            return fallo(val_res.error)

        try:
            with conectar_db(self.db_path) as conn:
                return self._anexar_en_transaccion(conn, evento)
        except sqlite3.Error as e:
            return fallo(
                ErrorDominio(
                    codigo="STORAGE_UNAVAILABLE",
                    mensaje_seguro=f"Error de persistencia SQLite: {e}",
                    reintentable=True,
                    correlation_id=evento.correlation_id,
                    detalles={"error": str(e)},
                )
            )

    def _anexar_en_transaccion(
        self, conn: sqlite3.Connection, evento: SobreEventoV1, auto_commit: bool = True
    ) -> Resultado[ReciboEvento]:
        cur = conn.cursor()

        # 2. Comprobar si ya existe el event_id (Idempotencia / Conflicto OPT-6)
        cur.execute("SELECT * FROM event_log WHERE event_id = ?;", (evento.event_id,))
        existente = cur.fetchone()
        if existente is not None:
            # Comparar payload_hash y contenido
            if existente["payload_hash"].lower() == evento.payload_hash.lower():
                persisted_dt = _parse_iso_utc(existente["persisted_at_utc"])
                return exito(
                    ReciboEvento(
                        event_id=existente["event_id"],
                        row_id=existente["row_id"],
                        persisted_at_utc=persisted_dt,
                        payload_hash=existente["payload_hash"],
                        previous_hash=existente["previous_hash"],
                        idempotent=True,
                    )
                )
            else:
                return fallo(
                    ErrorDominio(
                        codigo="INTEGRITY_ERROR",
                        mensaje_seguro="Conflicto de clave idempotente con contenido diferente",
                        reintentable=False,
                        correlation_id=evento.correlation_id,
                        detalles={
                            "event_id": evento.event_id,
                            "hash_existente": existente["payload_hash"],
                            "hash_nuevo": evento.payload_hash,
                        },
                    )
                )

        # 3. Obtener el hash del ultimo evento persistido
        cur.execute("SELECT payload_hash FROM event_log ORDER BY row_id DESC LIMIT 1;")
        last_row = cur.fetchone()
        expected_previous_hash = last_row["payload_hash"] if last_row is not None else None

        if evento.previous_hash is not None and evento.previous_hash != expected_previous_hash:
            return fallo(
                ErrorDominio(
                    codigo="INTEGRITY_ERROR",
                    mensaje_seguro="previous_hash del sobre no coincide con el hash del ultimo evento",
                    reintentable=False,
                    correlation_id=evento.correlation_id,
                    detalles={
                        "esperado": expected_previous_hash,
                        "recibido": evento.previous_hash,
                    },
                )
            )

        final_previous_hash = expected_previous_hash

        # 4. Asignar persisted_at_utc
        persisted_at = evento.persisted_at_utc or datetime.now(timezone.utc)
        persisted_iso = _format_iso_utc(persisted_at)
        occurred_iso = _format_iso_utc(evento.occurred_at_utc)
        received_iso = _format_iso_utc(evento.received_at_utc)
        payload_json_str = canonical_json_dumps(evento.payload)

        cur.execute(
            """
            INSERT INTO event_log (
                event_id, event_type, schema_version, occurred_at_utc, received_at_utc,
                persisted_at_utc, source, environment, source_account_id_hash, instrument,
                symbol_id, source_sequence, correlation_id, causation_id, payload_hash,
                previous_hash, payload_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                evento.event_id,
                evento.event_type,
                evento.schema_version,
                occurred_iso,
                received_iso,
                persisted_iso,
                evento.source,
                evento.environment,
                evento.source_account_id_hash,
                evento.instrument,
                evento.symbol_id,
                evento.source_sequence,
                evento.correlation_id,
                evento.causation_id,
                evento.payload_hash,
                final_previous_hash,
                payload_json_str,
            ),
        )
        row_id = cur.lastrowid
        if auto_commit:
            conn.commit()

        return exito(
            ReciboEvento(
                event_id=evento.event_id,
                row_id=row_id,
                persisted_at_utc=persisted_at,
                payload_hash=evento.payload_hash,
                previous_hash=final_previous_hash,
                idempotent=False,
            )
        )

    def anexar_lote(self, lote: LoteEventosV1) -> Resultado[ReciboLote]:
        """Anexa un lote de eventos de forma atomica en una sola transaccion."""
        if not lote.events:
            return exito(
                ReciboLote(
                    batch_id=lote.batch_id,
                    first_row_id=0,
                    last_row_id=0,
                    accepted_count=0,
                    rejected_count=0,
                    reason_codes=(),
                )
            )

        try:
            with conectar_db(self.db_path) as conn:
                first_row_id: int | None = None
                last_row_id: int | None = None
                for ev in lote.events:
                    res = self._anexar_en_transaccion(conn, ev, auto_commit=False)
                    if not res.exito:
                        conn.rollback()
                        return fallo(res.error)
                    if first_row_id is None:
                        first_row_id = res.datos.row_id
                    last_row_id = res.datos.row_id

                conn.commit()
                return exito(
                    ReciboLote(
                        batch_id=lote.batch_id,
                        first_row_id=first_row_id or 0,
                        last_row_id=last_row_id or 0,
                        accepted_count=len(lote.events),
                        rejected_count=0,
                        reason_codes=(),
                    )
                )
        except Exception as e:
            return fallo(
                ErrorDominio(
                    codigo="STORAGE_UNAVAILABLE",
                    mensaje_seguro=f"Error al anexar lote: {e}",
                    reintentable=True,
                    correlation_id=lote.batch_id,
                    detalles={"error": str(e)},
                )
            )

    def leer(self, consulta: ConsultaEventos) -> Resultado[PaginaEventos]:
        """Consulta eventos paginados con filtros de tiempo, tipo y cursor."""
        try:
            with conectar_db(self.db_path) as conn:
                cur = conn.cursor()
                query = ["SELECT * FROM event_log WHERE 1=1"]
                params: list[Any] = []

                if consulta.cursor:
                    try:
                        cursor_row = int(consulta.cursor)
                        query.append("AND row_id > ?")
                        params.append(cursor_row)
                    except ValueError:
                        pass

                if consulta.range_start_utc:
                    query.append("AND occurred_at_utc >= ?")
                    params.append(_format_iso_utc(consulta.range_start_utc))

                if consulta.range_end_utc:
                    query.append("AND occurred_at_utc <= ?")
                    params.append(_format_iso_utc(consulta.range_end_utc))

                if consulta.event_types:
                    placeholders = ",".join(["?"] * len(consulta.event_types))
                    query.append(f"AND event_type IN ({placeholders})")
                    params.extend(consulta.event_types)

                effective_limit = min(max(consulta.limit, 1), 1000)
                query.append(f"ORDER BY row_id ASC LIMIT {effective_limit + 1}")

                cur.execute(" ".join(query), params)
                rows = cur.fetchall()

                has_more = len(rows) > effective_limit
                selected_rows = rows[:effective_limit]

                events: list[SobreEventoV1] = []
                for r in selected_rows:
                    payload = json.loads(r["payload_json"])
                    ev = SobreEventoV1(
                        event_id=r["event_id"],
                        event_type=r["event_type"],
                        schema_version=r["schema_version"],
                        occurred_at_utc=_parse_iso_utc(r["occurred_at_utc"]),
                        received_at_utc=_parse_iso_utc(r["received_at_utc"]),
                        persisted_at_utc=_parse_iso_utc(r["persisted_at_utc"]),
                        source=r["source"],
                        environment=r["environment"],
                        source_account_id_hash=r["source_account_id_hash"],
                        instrument=r["instrument"],
                        symbol_id=r["symbol_id"],
                        source_sequence=r["source_sequence"],
                        correlation_id=r["correlation_id"],
                        causation_id=r["causation_id"],
                        payload_hash=r["payload_hash"],
                        previous_hash=r["previous_hash"],
                        payload=payload,
                    )
                    events.append(ev)

                next_cursor = str(selected_rows[-1]["row_id"]) if has_more and selected_rows else None
                cutoff_id = events[-1].event_id if events else None

                return exito(
                    PaginaEventos(
                        events=tuple(events),
                        cutoff_event_id=cutoff_id,
                        next_cursor=next_cursor,
                    )
                )
        except Exception as e:
            return fallo(
                ErrorDominio(
                    codigo="STORAGE_UNAVAILABLE",
                    mensaje_seguro=f"Error al leer eventos: {e}",
                    reintentable=True,
                    correlation_id="",
                    detalles={"error": str(e)},
                )
            )

    def verificar_integridad(self, rango: RangoEventos) -> Resultado[InformeIntegridad]:
        """Verifica la cadena criptografica de hashes y consistencia de payloads."""
        try:
            with conectar_db(self.db_path) as conn:
                cur = conn.cursor()
                query = ["SELECT * FROM event_log WHERE 1=1"]
                params: list[Any] = []

                if rango.start_row_id is not None:
                    query.append("AND row_id >= ?")
                    params.append(rango.start_row_id)
                if rango.end_row_id is not None:
                    query.append("AND row_id <= ?")
                    params.append(rango.end_row_id)

                query.append("ORDER BY row_id ASC")
                cur.execute(" ".join(query), params)
                rows = cur.fetchall()

                violations: list[str] = []
                hash_chain: list[str] = []
                prev_expected_hash: str | None = None

                # If start_row_id > 1, find the previous row to check initial previous_hash
                if rows and rows[0]["row_id"] > 1:
                    cur.execute("SELECT payload_hash FROM event_log WHERE row_id = ?;", (rows[0]["row_id"] - 1,))
                    pre_row = cur.fetchone()
                    if pre_row is not None:
                        prev_expected_hash = pre_row["payload_hash"]

                for r in rows:
                    # 1. Payload hash check
                    try:
                        payload = json.loads(r["payload_json"])
                        computed_h = compute_payload_hash(payload)
                        if computed_h.lower() != r["payload_hash"].lower():
                            violations.append(
                                f"Row {r['row_id']} payload hash mismatch: declared={r['payload_hash']} computed={computed_h}"
                            )
                    except Exception as e:
                        violations.append(f"Row {r['row_id']} payload json invalid: {e}")

                    # 2. Previous hash chain check
                    if r["previous_hash"] != prev_expected_hash:
                        violations.append(
                            f"Row {r['row_id']} previous_hash mismatch: declared={r['previous_hash']} expected={prev_expected_hash}"
                        )

                    prev_expected_hash = r["payload_hash"]
                    hash_chain.append(r["payload_hash"])

                # Root hash = SHA-256 of combined payload hashes
                combined_hashes = "".join(hash_chain).encode("utf-8")
                root_hash = hashlib.sha256(combined_hashes).hexdigest()

                return exito(
                    InformeIntegridad(
                        range_checked=rango,
                        event_count=len(rows),
                        root_hash=root_hash,
                        violations=tuple(violations),
                        is_valid=len(violations) == 0,
                    )
                )
        except Exception as e:
            return fallo(
                ErrorDominio(
                    codigo="STORAGE_UNAVAILABLE",
                    mensaje_seguro=f"Error al verificar integridad: {e}",
                    reintentable=True,
                    correlation_id="",
                    detalles={"error": str(e)},
                )
            )

    def reconstruir_proyecciones(self) -> Resultado[dict[str, int]]:
        """Reconstruye el conteo y proyecciones base a partir del log de eventos."""
        try:
            with conectar_db(self.db_path) as conn:
                cur = conn.cursor()
                cur.execute("SELECT event_type, COUNT(*) as cnt FROM event_log GROUP BY event_type;")
                counts = {row["event_type"]: row["cnt"] for row in cur.fetchall()}
                cur.execute("SELECT COUNT(*) as total FROM event_log;")
                counts["_total"] = cur.fetchone()["total"]
                return exito(counts)
        except Exception as e:
            return fallo(
                ErrorDominio(
                    codigo="STORAGE_UNAVAILABLE",
                    mensaje_seguro=f"Error al reconstruir proyecciones: {e}",
                    reintentable=True,
                    correlation_id="",
                    detalles={"error": str(e)},
                )
            )


class RegistroAuditoria:
    """Registro inmutable de auditoria administrativa y del sistema."""

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path) if isinstance(db_path, str) else db_path
        inicializar_db(self.db_path)

    def registrar(self, entrada: EntradaAuditoriaV1) -> Resultado[ReciboAuditoria]:
        """Registra una entrada de auditoria append-only."""
        try:
            details_json = canonical_json_dumps(entrada.details)
            entry_bytes = canonical_json_bytes(
                {
                    "audit_id": entrada.audit_id,
                    "actor": entrada.actor,
                    "operation": entrada.operation,
                    "result": entrada.result,
                    "correlation_id": entrada.correlation_id,
                    "details": entrada.details,
                }
            )
            entry_hash = hashlib.sha256(entry_bytes).hexdigest()
            now = datetime.now(timezone.utc)
            now_iso = _format_iso_utc(now)

            with conectar_db(self.db_path) as conn:
                cur = conn.cursor()
                cur.execute(
                    """
                    INSERT INTO audit_log (
                        audit_id, actor, operation, result, persisted_at_utc,
                        correlation_id, details_json, entry_hash
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    (
                        entrada.audit_id,
                        entrada.actor,
                        entrada.operation,
                        entrada.result,
                        now_iso,
                        entrada.correlation_id,
                        details_json,
                        entry_hash,
                    ),
                )
                row_id = cur.lastrowid
                conn.commit()

                return exito(
                    ReciboAuditoria(
                        audit_id=entrada.audit_id,
                        row_id=row_id,
                        persisted_at_utc=now,
                        entry_hash=entry_hash,
                    )
                )
        except Exception as e:
            return fallo(
                ErrorDominio(
                    codigo="STORAGE_UNAVAILABLE",
                    mensaje_seguro=f"Error al registrar auditoria: {e}",
                    reintentable=True,
                    correlation_id=entrada.correlation_id,
                    detalles={"error": str(e)},
                )
            )
