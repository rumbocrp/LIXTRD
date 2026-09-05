"""Operaciones de backup, restore y verificacion de integridad SQLite (SPEC-001 §9.3, CA-21)."""

from pathlib import Path
import sqlite3
from typing import Any

from sistema_luces.domain.error import ErrorDominio
from sistema_luces.domain.result import Resultado, exito, fallo
from sistema_luces.storage.sqlite import conectar_db


def copiar_base_segura(source_path: str | Path, target_path: str | Path) -> Resultado[dict[str, Any]]:
    """Realiza backup en caliente usando la API backup de SQLite."""
    src_p = Path(source_path)
    dst_p = Path(target_path)
    if not src_p.exists():
        return fallo(
            ErrorDominio(
                codigo="STORAGE_UNAVAILABLE",
                mensaje_seguro=f"Archivo de origen no existe: {src_p}",
                reintentable=False,
                correlation_id="",
                detalles={"source_path": str(src_p)},
            )
        )
    dst_p.parent.mkdir(parents=True, exist_ok=True)

    try:
        with conectar_db(src_p) as src_conn, conectar_db(dst_p) as dst_conn:
            src_conn.backup(dst_conn)
        return exito({"source": str(src_p), "target": str(dst_p), "status": "COPIED"})
    except Exception as e:
        return fallo(
            ErrorDominio(
                codigo="STORAGE_UNAVAILABLE",
                mensaje_seguro=f"Error durante el backup de base de datos: {e}",
                reintentable=True,
                correlation_id="",
                detalles={"error": str(e)},
            )
        )


def verificar_backup_integro(backup_path: str | Path) -> Resultado[dict[str, Any]]:
    """Verifica PRAGMA integrity_check y consistencia del log de eventos."""
    b_path = Path(backup_path)
    if not b_path.exists():
        return fallo(
            ErrorDominio(
                codigo="STORAGE_UNAVAILABLE",
                mensaje_seguro=f"Archivo de backup no existe: {b_path}",
                reintentable=False,
                correlation_id="",
                detalles={"backup_path": str(b_path)},
            )
        )

    try:
        with conectar_db(b_path) as conn:
            cur = conn.cursor()
            cur.execute("PRAGMA integrity_check;")
            res = cur.fetchone()[0]
            if res != "ok":
                return fallo(
                    ErrorDominio(
                        codigo="INTEGRITY_ERROR",
                        mensaje_seguro=f"Fallo de PRAGMA integrity_check: {res}",
                        reintentable=False,
                        correlation_id="",
                        detalles={"integrity_check": res},
                    )
                )

            cur.execute("SELECT COUNT(*) as cnt FROM event_log;")
            cnt = cur.fetchone()["cnt"]
            return exito({"integrity_check": "ok", "event_count": cnt, "is_valid": True})
    except Exception as e:
        return fallo(
            ErrorDominio(
                codigo="STORAGE_UNAVAILABLE",
                mensaje_seguro=f"Error al verificar backup: {e}",
                reintentable=False,
                correlation_id="",
                detalles={"error": str(e)},
            )
        )


def restaurar_backup(backup_path: str | Path, target_path: str | Path) -> Resultado[dict[str, Any]]:
    """Restaura una base de datos desde un backup verificado."""
    # 1. Verificar integridad del backup antes de restaurar
    ver_res = verificar_backup_integro(backup_path)
    if not ver_res.exito:
        return ver_res

    return copiar_base_segura(backup_path, target_path)
