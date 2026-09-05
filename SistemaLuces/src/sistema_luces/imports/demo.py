"""Importador de ejecuciones de broker demo (SPEC-001 §5.2.1, CA-3, CA-19)."""

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from typing import Any, Literal
import uuid

from sistema_luces.domain.api import (
    ResumenImportacion,
    SolicitudImportacionDemo,
    validar_resumen_importacion,
    validar_solicitud_importacion_demo,
)
from sistema_luces.domain.error import ErrorDominio
from sistema_luces.domain.result import Resultado, exito, fallo
from sistema_luces.domain.vocabulary import ReconciliationStatus
from sistema_luces.imports.staging import ValidadorStaging


@dataclass(frozen=True)
class EjecucionDemoObservada:
    execution_id: str
    trade_id: str
    account_hash: str
    symbol: str
    side: Literal["LONG", "SHORT"]
    quantity: int
    entry_time_utc: datetime
    entry_price: int
    exit_time_utc: datetime | None
    exit_price: int | None
    gross_pnl_cents: int | None
    net_pnl_cents: int | None
    reconciliation_status: ReconciliationStatus = "UNMATCHED"


class ImportadorDemo:
    """Importa registros de trading demo desde archivos en copia staged."""

    def __init__(self, validador_staging: ValidadorStaging | None = None) -> None:
        self.validador_staging = validador_staging or ValidadorStaging()
        self.ejecuciones_importadas: list[EjecucionDemoObservada] = []

    def importar(self, solicitud: SolicitudImportacionDemo) -> Resultado[ResumenImportacion]:
        """Procesa una solicitud de importación validada."""
        val_sol = validar_solicitud_importacion_demo(solicitud)
        if not val_sol.exito:
            return fallo(val_sol.error)

        res_bytes = self.validador_staging.validar_y_leer(
            staged_copy=solicitud.staged_copy,
            expected_sha256=solicitud.expected_sha256,
            correlation_id=solicitud.correlation_id,
        )
        if not res_bytes.exito:
            return fallo(res_bytes.error)

        content_bytes = res_bytes.datos
        try:
            raw_data = json.loads(content_bytes.decode("utf-8"))
        except Exception as e:
            return fallo(
                ErrorDominio(
                    codigo="IMPORT_INVALID",
                    mensaje_seguro=f"Error al decodificar JSON de importación: {e}",
                    reintentable=False,
                    correlation_id=solicitud.correlation_id,
                    detalles={},
                )
            )

        if not isinstance(raw_data, list):
            raw_data = [raw_data]

        accepted_trades: list[EjecucionDemoObservada] = []
        rejected_count = 0
        reasons: list[str] = []

        for item in raw_data:
            if not isinstance(item, dict):
                rejected_count += 1
                continue

            trade_id = str(item.get("trade_id", str(uuid.uuid4())))
            symbol = item.get("symbol", "US500")
            raw_side = str(item.get("side", "")).upper()
            side: Literal["LONG", "SHORT"] = "LONG" if raw_side in {"BUY", "LONG"} else "SHORT"
            quantity = int(item.get("quantity", 100))

            try:
                entry_time_str = item.get("entry_time") or item.get("entry_time_utc")
                entry_time = (
                    datetime.fromisoformat(entry_time_str.replace("Z", "+00:00"))
                    if entry_time_str
                    else datetime.now(timezone.utc)
                )
                exit_time_str = item.get("exit_time") or item.get("exit_time_utc")
                exit_time = (
                    datetime.fromisoformat(exit_time_str.replace("Z", "+00:00"))
                    if exit_time_str
                    else None
                )
            except Exception:
                rejected_count += 1
                continue

            entry_price = int(item.get("entry_price", 0))
            exit_price = int(item.get("exit_price")) if item.get("exit_price") is not None else None
            pnl_val = item.get("pnl") or item.get("pnl_usd_cents") or item.get("net_pnl")
            net_pnl_cents = int(pnl_val * 100) if isinstance(pnl_val, float) else (int(pnl_val) if pnl_val is not None else None)

            ejecucion = EjecucionDemoObservada(
                execution_id=str(uuid.uuid4()),
                trade_id=trade_id,
                account_hash=solicitud.expected_demo_account_hash,
                symbol=symbol,
                side=side,
                quantity=quantity,
                entry_time_utc=entry_time,
                entry_price=entry_price,
                exit_time_utc=exit_time,
                exit_price=exit_price,
                gross_pnl_cents=net_pnl_cents,
                net_pnl_cents=net_pnl_cents,
                reconciliation_status="UNMATCHED",
            )
            accepted_trades.append(ejecucion)

        self.ejecuciones_importadas.extend(accepted_trades)

        import_id = str(uuid.uuid4())
        resumen = ResumenImportacion(
            import_id=import_id,
            environment=solicitud.environment,
            final_event_cutoff=datetime.now(timezone.utc).isoformat(),
            accepted_count=len(accepted_trades),
            rejected_count=rejected_count,
            matched_count=0,
            unmatched_count=len(accepted_trades),
            reason_codes=tuple(reasons),
        )

        val_resumen = validar_resumen_importacion(resumen)
        if not val_resumen.exito:
            return fallo(val_resumen.error)

        return exito(resumen)
