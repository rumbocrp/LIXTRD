"""Pruebas unitarias para el importador de operativas (Fase 0)."""

import json
import pytest
from pathlib import Path
from sistema_luces.imports.trade_importer import TradeImporter
from sistema_luces.domain.operator_trade import TradeDirection, TradeOutcome
from sistema_luces.storage.database import DecisionDatabase

def test_import_trades_from_json_idempotency(tmp_path):
    importer = TradeImporter()
    json_file = tmp_path / "sample_trades.json"
    
    trades_data = [
        {
            "trade_id": "trade-101",
            "symbol": "XAUUSD",
            "side": "BUY",
            "setup_id": "GOLD_DXY_MACRO_REVERSION",
            "entry_price": 2045.5,
            "stop_loss": 2040.0,
            "take_profit": 2060.0,
            "entry_timestamp_utc": 1700000000000,
            "exit_price": 2060.0,
            "exit_timestamp_utc": 1700000600000,
            "pnl_usd": 350.0,
        },
        {
            "trade_id": "trade-102",
            "symbol": "TSLA",
            "side": "SELL",
            "setup_id": "SP500_TSLA_BETA_MOMENTUM",
            "entry_price": 220.0,
            "stop_loss": 225.0,
            "take_profit": 210.0,
            "entry_timestamp_utc": 1700000100000,
            "exit_price": 225.0,
            "exit_timestamp_utc": 1700000400000,
            "pnl_usd": -120.0,
        }
    ]
    json_file.write_text(json.dumps(trades_data), encoding="utf-8")

    # 1. Primera importación: debe importar 2 registros
    report1 = importer.import_from_json(json_file)
    assert report1.valid_records_imported == 2
    assert report1.skipped_duplicates == 0
    assert len(report1.records) == 2

    # 2. Segunda importación (mismo archivo): debe saltar duplicados (idempotencia)
    report2 = importer.import_from_json(json_file)
    assert report2.valid_records_imported == 0
    assert report2.skipped_duplicates == 2

def test_import_trades_from_csv(tmp_path):
    importer = TradeImporter()
    csv_file = tmp_path / "sample_trades.csv"
    
    csv_content = """symbol,direction,setup_id,entry_price,stop_loss_price,take_profit_price,entry_timestamp_utc,exit_price,exit_timestamp_utc,pnl_usd
AAPL,BUY,SP500_AAPL_ANCHOR_PULLBACK,185.0,183.5,190.0,1700000000000,190.0,1700001000000,250.0
"""
    csv_file.write_text(csv_content, encoding="utf-8")

    report = importer.import_from_csv(csv_file)
    assert report.valid_records_imported == 1
    assert report.records[0].instrument == "AAPL"
    assert report.records[0].outcome == TradeOutcome.WIN
