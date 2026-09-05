"""Motor de conexion SQLite inmutable y esquemas (SPEC-001 §4.3, CA-4, CA-5)."""

from pathlib import Path
import sqlite3
from typing import Any

from sistema_luces.domain.error import ErrorDominio
from sistema_luces.domain.result import Resultado, exito, fallo

_SCHEMA_SQL = """
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;
PRAGMA busy_timeout = 5000;
PRAGMA synchronous = NORMAL;

CREATE TABLE IF NOT EXISTS event_log (
    row_id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT UNIQUE NOT NULL,
    event_type TEXT NOT NULL,
    schema_version INTEGER NOT NULL,
    occurred_at_utc TEXT NOT NULL,
    received_at_utc TEXT NOT NULL,
    persisted_at_utc TEXT NOT NULL,
    source TEXT NOT NULL,
    environment TEXT NOT NULL,
    source_account_id_hash TEXT,
    instrument TEXT NOT NULL,
    symbol_id TEXT,
    source_sequence INTEGER,
    correlation_id TEXT NOT NULL,
    causation_id TEXT,
    payload_hash TEXT NOT NULL,
    previous_hash TEXT,
    payload_json TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_event_log_occurred ON event_log (occurred_at_utc);
CREATE INDEX IF NOT EXISTS idx_event_log_type ON event_log (event_type);
CREATE INDEX IF NOT EXISTS idx_event_log_correlation ON event_log (correlation_id);
CREATE INDEX IF NOT EXISTS idx_event_log_sequence ON event_log (source_sequence);

CREATE TRIGGER IF NOT EXISTS trg_prevent_update_event_log
BEFORE UPDATE ON event_log
BEGIN
    SELECT RAISE(ABORT, 'Fact mutation forbidden: event_log is append-only');
END;

CREATE TRIGGER IF NOT EXISTS trg_prevent_delete_event_log
BEFORE DELETE ON event_log
BEGIN
    SELECT RAISE(ABORT, 'Fact deletion forbidden: event_log is append-only');
END;

CREATE TABLE IF NOT EXISTS audit_log (
    row_id INTEGER PRIMARY KEY AUTOINCREMENT,
    audit_id TEXT UNIQUE NOT NULL,
    actor TEXT NOT NULL,
    operation TEXT NOT NULL,
    result TEXT NOT NULL,
    persisted_at_utc TEXT NOT NULL,
    correlation_id TEXT NOT NULL,
    details_json TEXT NOT NULL,
    entry_hash TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_audit_log_correlation ON audit_log (correlation_id);

CREATE TRIGGER IF NOT EXISTS trg_prevent_update_audit_log
BEFORE UPDATE ON audit_log
BEGIN
    SELECT RAISE(ABORT, 'Audit mutation forbidden: audit_log is append-only');
END;

CREATE TRIGGER IF NOT EXISTS trg_prevent_delete_audit_log
BEFORE DELETE ON audit_log
BEGIN
    SELECT RAISE(ABORT, 'Audit deletion forbidden: audit_log is append-only');
END;
"""


def conectar_db(db_path: str | Path) -> sqlite3.Connection:
    """Establece conexion con SQLite aplicando PRAGMAs seguros."""
    path_str = str(db_path)
    conn = sqlite3.connect(path_str, timeout=5.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA busy_timeout = 5000;")
    return conn


def inicializar_db(db_path: str | Path) -> Resultado[bool]:
    """Inicializa el esquema y los triggers inmutables en la base de datos."""
    try:
        if isinstance(db_path, Path):
            db_path.parent.mkdir(parents=True, exist_ok=True)
        with conectar_db(db_path) as conn:
            conn.executescript(_SCHEMA_SQL)
            conn.commit()
        return exito(True)
    except Exception as e:
        return fallo(
            ErrorDominio(
                codigo="STORAGE_UNAVAILABLE",
                mensaje_seguro=f"Error al inicializar base de datos SQLite: {e}",
                reintentable=True,
                correlation_id="",
                detalles={"error": str(e)},
            )
        )
