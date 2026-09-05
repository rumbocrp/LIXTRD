"""Adaptador aislado para exportaciones de Trading Journal V1 (SPEC-001 §9.4, CA-20, CA-28)."""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Literal

from sistema_luces.domain.error import ErrorDominio
from sistema_luces.domain.result import Resultado, exito, fallo
from sistema_luces.imports.demo import EjecucionDemoObservada

EstadoJournalV1 = Literal["NOT_INCLUDED", "PASS_INCLUDED"]


class AdaptadorExportacionJournalV1:
    """Adaptador de sólo lectura sobre copias de exportación sin acceso a bases externas."""

    def __init__(self, estado_extension: EstadoJournalV1 = "NOT_INCLUDED") -> None:
        self._estado = estado_extension

    def obtener_estado_extension(self) -> EstadoJournalV1:
        """CA-20: Reporta el estado de aislamiento sin abrir conexiones externas."""
        return self._estado

    def cargar_desde_archivo(self, file_path: Path, expected_sha256: str) -> Resultado[list[EjecucionDemoObservada]]:
        """Lee un archivo de exportación JSON estructurado en formato trading-journal/exportacion-completa-v1."""
        if not file_path.exists():
            return fallo(
                ErrorDominio(
                    codigo="IMPORT_INVALID",
                    mensaje_seguro=f"Archivo no encontrado: {file_path}",
                    reintentable=False,
                    correlation_id="",
                    detalles={"path": str(file_path)},
                )
            )

        content = file_path.read_bytes()
        computed_hash = hashlib.sha256(content).hexdigest()
        if computed_hash.lower() != expected_sha256.lower():
            return fallo(
                ErrorDominio(
                    codigo="INTEGRITY_ERROR",
                    mensaje_seguro="Hash de exportación Journal no coincide",
                    reintentable=False,
                    correlation_id="",
                    detalles={"expected": expected_sha256, "computed": computed_hash},
                )
            )

        try:
            data = json.loads(content.decode("utf-8"))
        except Exception as e:
            return fallo(
                ErrorDominio(
                    codigo="IMPORT_INVALID",
                    mensaje_seguro=f"JSON de exportación Journal corrupto: {e}",
                    reintentable=False,
                    correlation_id="",
                    detalles={},
                )
            )

        format_tag = data.get("format")
        if format_tag != "trading-journal/exportacion-completa-v1":
            return fallo(
                ErrorDominio(
                    codigo="SCHEMA_UNSUPPORTED",
                    mensaje_seguro=f"Formato no admitido: {format_tag}",
                    reintentable=False,
                    correlation_id="",
                    detalles={"format": str(format_tag)},
                )
            )

        account_hash = data.get("account_hash", "0" * 64)
        trades_raw = data.get("trades", [])
        trades: list[EjecucionDemoObservada] = []

        for tr in trades_raw:
            trade_id = str(tr.get("trade_id", "tr-0"))
            symbol = str(tr.get("symbol", "US500"))
            side = "LONG" if str(tr.get("direction", "LONG")).upper() == "LONG" else "SHORT"
            qty = int(tr.get("quantity", 100))
            entry_t = datetime.fromisoformat(tr.get("entry_time_utc", "2026-08-29T14:30:00Z").replace("Z", "+00:00"))
            entry_p = int(tr.get("entry_price", 500000))
            exit_t = datetime.fromisoformat(tr.get("exit_time_utc").replace("Z", "+00:00")) if tr.get("exit_time_utc") else None
            exit_p = int(tr.get("exit_price")) if tr.get("exit_price") is not None else None
            pnl_cents = int(tr.get("pnl_usd_cents", 0))

            trades.append(
                EjecucionDemoObservada(
                    execution_id=f"tj-exec-{trade_id}",
                    trade_id=trade_id,
                    account_hash=account_hash,
                    symbol=symbol,
                    side=side,
                    quantity=qty,
                    entry_time_utc=entry_t,
                    entry_price=entry_p,
                    exit_time_utc=exit_t,
                    exit_price=exit_p,
                    gross_pnl_cents=pnl_cents,
                    net_pnl_cents=pnl_cents,
                    reconciliation_status="UNMATCHED",
                )
            )

        return exito(trades)
