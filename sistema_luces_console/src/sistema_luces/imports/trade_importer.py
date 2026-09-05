"""Importador idempotente y validador de operativas y exportaciones de trades (Fase 0)."""

from __future__ import annotations
import csv
import hashlib
import json
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass

from sistema_luces.domain.operator_trade import OperatorTradeRecord, TradeDirection, TradeOutcome

@dataclass(frozen=True)
class ImportReport:
    file_path: str
    file_sha256: str
    total_records_found: int
    valid_records_imported: int
    skipped_duplicates: int
    rejected_invalid: int
    error_details: List[str]
    records: List[OperatorTradeRecord]

class TradeImporter:
    """Importador idempotente para incorporar historial de trades del operador sin tocar bases externas."""
    def __init__(self):
        self.seen_hashes: set[str] = set()

    @staticmethod
    def compute_file_sha256(file_path: str | Path) -> str:
        h = hashlib.sha256()
        with open(file_path, "rb") as f:
            while chunk := f.read(65536):
                h.update(chunk)
        return h.hexdigest()

    def import_from_json(self, file_path: str | Path) -> ImportReport:
        p = Path(file_path)
        if not p.exists():
            return ImportReport(str(p), "", 0, 0, 0, 0, [f"El archivo no existe: {p}"], [])

        file_sha = self.compute_file_sha256(p)
        errors: List[str] = []
        valid_records: List[OperatorTradeRecord] = []
        skipped = 0
        rejected = 0

        try:
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            return ImportReport(str(p), file_sha, 0, 0, 0, 0, [f"Error al leer JSON: {str(e)}"], [])

        if not isinstance(data, list):
            data = [data]

        for idx, item in enumerate(data):
            try:
                rec = self._parse_dict_record(item, file_sha)
                h = rec.compute_sha256()
                if h in self.seen_hashes:
                    skipped += 1
                else:
                    self.seen_hashes.add(h)
                    valid_records.append(rec)
            except Exception as e:
                rejected += 1
                errors.append(f"Registro #{idx}: {str(e)}")

        return ImportReport(
            file_path=str(p),
            file_sha256=file_sha,
            total_records_found=len(data),
            valid_records_imported=len(valid_records),
            skipped_duplicates=skipped,
            rejected_invalid=rejected,
            error_details=errors,
            records=valid_records,
        )

    def import_from_csv(self, file_path: str | Path) -> ImportReport:
        p = Path(file_path)
        if not p.exists():
            return ImportReport(str(p), "", 0, 0, 0, 0, [f"El archivo no existe: {p}"], [])

        file_sha = self.compute_file_sha256(p)
        errors: List[str] = []
        valid_records: List[OperatorTradeRecord] = []
        skipped = 0
        rejected = 0
        total_rows = 0

        try:
            with open(p, "r", encoding="utf-8", newline="") as f:
                reader = csv.DictReader(f)
                for idx, row in enumerate(reader):
                    total_rows += 1
                    try:
                        rec = self._parse_dict_record(row, file_sha)
                        h = rec.compute_sha256()
                        if h in self.seen_hashes:
                            skipped += 1
                        else:
                            self.seen_hashes.add(h)
                            valid_records.append(rec)
                    except Exception as e:
                        rejected += 1
                        errors.append(f"Fila CSV #{idx+1}: {str(e)}")
        except Exception as e:
            return ImportReport(str(p), file_sha, total_rows, 0, 0, total_rows, [f"Error al procesar CSV: {str(e)}"], [])

        return ImportReport(
            file_path=str(p),
            file_sha256=file_sha,
            total_records_found=total_rows,
            valid_records_imported=len(valid_records),
            skipped_duplicates=skipped,
            rejected_invalid=rejected,
            error_details=errors,
            records=valid_records,
        )

    def _parse_dict_record(self, d: Dict[str, Any], source_sha: str) -> OperatorTradeRecord:
        # Validación de campos obligatorios
        inst = str(d.get("instrument") or d.get("symbol") or "").strip().upper()
        if not inst:
            raise ValueError("Campo obligatorio faltante: 'instrument' / 'symbol'")

        dir_str = str(d.get("direction") or d.get("side") or "").strip().upper()
        if dir_str not in {"LONG", "BUY", "SHORT", "SELL"}:
            raise ValueError(f"Dirección inválida: {dir_str}")
        direction = TradeDirection.LONG if dir_str in {"LONG", "BUY"} else TradeDirection.SHORT

        entry_raw = d.get("entry_price") or d.get("price")
        if entry_raw is None:
            raise ValueError("Campo obligatorio faltante: 'entry_price'")
        entry_p = float(entry_raw)

        stop_raw = d.get("stop_loss_price") or d.get("stop_loss") or d.get("sl")
        if stop_raw is None:
            raise ValueError("Campo obligatorio faltante: 'stop_loss_price' / 'stop_loss'")
        stop_p = float(stop_raw)

        tp_raw = d.get("take_profit_price") or d.get("take_profit") or d.get("tp")
        tp_p = float(tp_raw) if tp_raw is not None else 0.0
        
        entry_ts = int(d.get("entry_timestamp_utc") or d.get("timestamp") or 0)

        if entry_p <= 0 or stop_p <= 0:
            raise ValueError("Los precios de entrada y stop loss deben ser estrictamente positivos")

        exit_raw = d.get("exit_price") or d.get("close_price")
        exit_p = float(exit_raw) if exit_raw is not None else None
        
        exit_ts_raw = d.get("exit_timestamp_utc") or d.get("close_timestamp_utc")
        exit_ts = int(exit_ts_raw) if exit_ts_raw is not None else None
        
        pnl = float(d.get("pnl_usd") or d.get("pnl") or 0.0)
        comm = float(d.get("commission_usd") or d.get("commission") or 0.0)
        slip = float(d.get("slippage_pips") or d.get("slippage") or 0.0)

        setup = str(d.get("setup_id") or d.get("setup") or "GENERIC_DISCRETIONARY")
        ver = str(d.get("strategy_version") or d.get("version") or "v1.0")
        notes = str(d.get("operator_notes") or d.get("notes") or "")
        regime = str(d.get("market_regime_tag") or d.get("regime") or "NORMAL")
        t_id = str(d.get("trade_id") or d.get("id") or "") or None

        return OperatorTradeRecord.create(
            instrument=inst,
            direction=direction,
            setup_id=setup,
            strategy_version=ver,
            entry_timestamp_utc=entry_ts,
            entry_price=entry_p,
            stop_loss_price=stop_p,
            take_profit_price=tp_p,
            exit_timestamp_utc=exit_ts,
            exit_price=exit_p,
            pnl_usd=pnl,
            commission_usd=comm,
            slippage_pips=slip,
            market_regime_tag=regime,
            operator_notes=notes,
            source_sha256=source_sha,
            trade_id=t_id,
        )
