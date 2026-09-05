"""Gestor de Base de Datos SQLite Inmutable (Append-Only) para el Sistema de Luces 2.0."""

import sqlite3
import json
import time
from pathlib import Path
from typing import List, Dict, Any, Optional
from sistema_luces.domain.models import DecisionLuzContract
from sistema_luces.domain.operator_trade import OperatorTradeRecord, TradeDirection, TradeOutcome
from sistema_luces.domain.strategy import StrategyDefinition
from sistema_luces.domain.simulated_trade import SimulatedOperation

class DecisionDatabase:
    """Base de datos local append-only para auditoría, telemetría, decisiones y operativa del usuario."""
    def __init__(self, db_path: str = "luces.db"):
        self.db_path = db_path
        self._init_schema()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        return conn

    def _init_schema(self) -> None:
        with self._get_conn() as conn:
            # 1. Tabla de Decisiones y Transiciones de Semáforo
            conn.execute("""
            CREATE TABLE IF NOT EXISTS transicion_luz (
                decision_id TEXT PRIMARY KEY,
                instrument TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                data_timestamp_utc INTEGER NOT NULL,
                created_at_utc INTEGER NOT NULL,
                state TEXT NOT NULL,
                action TEXT NOT NULL,
                net_utility_long_ppm INTEGER NOT NULL,
                net_utility_short_ppm INTEGER NOT NULL,
                confidence_score_ppm INTEGER NOT NULL,
                calibration_quality_ppm INTEGER NOT NULL,
                kalman_beta_scaled INTEGER NOT NULL,
                kalman_z_score_scaled INTEGER NOT NULL,
                ofi_imbalance_scaled INTEGER NOT NULL,
                micro_price_mid_delta_ppm INTEGER NOT NULL,
                champion_model_id TEXT NOT NULL,
                valid_until_utc INTEGER NOT NULL,
                reason_codes TEXT NOT NULL,
                data_health TEXT NOT NULL
            );
            """)
            conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_transicion_timestamp 
            ON transicion_luz(data_timestamp_utc DESC);
            """)

            # 2. Tabla de Operativa del Operador (Fase 0)
            conn.execute("""
            CREATE TABLE IF NOT EXISTS operativa_operador (
                trade_id TEXT PRIMARY KEY,
                instrument TEXT NOT NULL,
                direction TEXT NOT NULL,
                setup_id TEXT NOT NULL,
                strategy_version TEXT NOT NULL,
                entry_timestamp_utc INTEGER NOT NULL,
                entry_price REAL NOT NULL,
                stop_loss_price REAL NOT NULL,
                take_profit_price REAL NOT NULL,
                exit_timestamp_utc INTEGER,
                exit_price REAL,
                outcome TEXT NOT NULL,
                risk_r_multiple_ppm INTEGER NOT NULL,
                net_pnl_usd_scaled INTEGER NOT NULL,
                commission_usd_scaled INTEGER NOT NULL,
                slippage_pips_scaled INTEGER NOT NULL,
                market_regime_tag TEXT NOT NULL,
                operator_notes TEXT,
                source_file_sha256 TEXT NOT NULL,
                record_sha256 TEXT NOT NULL
            );
            """)
            conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_operativa_setup 
            ON operativa_operador(setup_id, entry_timestamp_utc DESC);
            """)

            # 3. Tabla de Estrategias y Setups Versionados
            conn.execute("""
            CREATE TABLE IF NOT EXISTS estrategia_version (
                strategy_id TEXT NOT NULL,
                version TEXT NOT NULL,
                name TEXT NOT NULL,
                instrument TEXT NOT NULL,
                allowed_directions TEXT NOT NULL,
                session_window TEXT NOT NULL,
                cadences TEXT NOT NULL,
                default_stop_atr_mult REAL NOT NULL,
                default_target_atr_mult REAL NOT NULL,
                max_horizon_seconds INTEGER NOT NULL,
                cost_profile_pips REAL NOT NULL,
                description TEXT,
                strategy_hash TEXT NOT NULL,
                is_active INTEGER NOT NULL,
                PRIMARY KEY (strategy_id, version)
            );
            """)

            # 4. Tabla de Operativas Simuladas bajo el Modelo
            conn.execute("""
            CREATE TABLE IF NOT EXISTS operativa_simulada (
                operation_id TEXT PRIMARY KEY,
                instrument TEXT NOT NULL,
                direction TEXT NOT NULL,
                entry_timestamp_utc INTEGER NOT NULL,
                entry_price REAL NOT NULL,
                stop_loss_price REAL NOT NULL,
                take_profit_price REAL NOT NULL,
                size REAL NOT NULL,
                exit_timestamp_utc INTEGER,
                exit_price REAL,
                status TEXT NOT NULL,
                pnl_usd REAL NOT NULL,
                return_pct REAL NOT NULL,
                r_multiple REAL NOT NULL,
                slippage_pips REAL NOT NULL,
                commission_usd REAL NOT NULL,
                acute_slippage_penalty REAL NOT NULL,
                execution_spectrum_tier TEXT NOT NULL,
                simulated_risk_pct REAL NOT NULL,
                close_reason TEXT
            );
            """)
            conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_simulada_instrument
            ON operativa_simulada(instrument, entry_timestamp_utc DESC);
            """)
            conn.commit()

    # --- Operaciones de Decisiones del Semáforo ---
    def save_decision(self, d: DecisionLuzContract) -> None:
        reasons_json = json.dumps([r.value for r in d.reason_codes])
        with self._get_conn() as conn:
            conn.execute("""
            INSERT OR REPLACE INTO transicion_luz (
                decision_id, instrument, timeframe, data_timestamp_utc, created_at_utc,
                state, action, net_utility_long_ppm, net_utility_short_ppm,
                confidence_score_ppm, calibration_quality_ppm, kalman_beta_scaled,
                kalman_z_score_scaled, ofi_imbalance_scaled, micro_price_mid_delta_ppm,
                champion_model_id, valid_until_utc, reason_codes, data_health
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                d.decision_id, d.instrument, d.timeframe, d.data_timestamp_utc, d.created_at_utc,
                d.state.value, d.action.value, d.net_utility_long_ppm, d.net_utility_short_ppm,
                d.confidence_score_ppm, d.calibration_quality_ppm, d.kalman_beta_scaled,
                d.kalman_z_score_scaled, d.ofi_imbalance_scaled, d.micro_price_mid_delta_ppm,
                d.champion_model_id, d.valid_until_utc, reasons_json, d.data_health.value
            ))
            conn.commit()

    def get_recent_transitions(self, limit: int = 20) -> List[Dict[str, Any]]:
        with self._get_conn() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
            SELECT * FROM transicion_luz 
            ORDER BY data_timestamp_utc DESC LIMIT ?;
            """, (limit,))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    # --- Operaciones de Trades del Operador (Fase 0) ---
    def save_operator_trade(self, t: OperatorTradeRecord) -> None:
        rec_hash = t.compute_sha256()
        with self._get_conn() as conn:
            conn.execute("""
            INSERT OR REPLACE INTO operativa_operador (
                trade_id, instrument, direction, setup_id, strategy_version,
                entry_timestamp_utc, entry_price, stop_loss_price, take_profit_price,
                exit_timestamp_utc, exit_price, outcome, risk_r_multiple_ppm,
                net_pnl_usd_scaled, commission_usd_scaled, slippage_pips_scaled,
                market_regime_tag, operator_notes, source_file_sha256, record_sha256
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                t.trade_id, t.instrument, t.direction.value, t.setup_id, t.strategy_version,
                t.entry_timestamp_utc, t.entry_price, t.stop_loss_price, t.take_profit_price,
                t.exit_timestamp_utc, t.exit_price, t.outcome.value, t.risk_r_multiple_ppm,
                t.net_pnl_usd_scaled, t.commission_usd_scaled, t.slippage_pips_scaled,
                t.market_regime_tag, t.operator_notes, t.source_file_sha256, rec_hash
            ))
            conn.commit()

    def save_operator_trades_batch(self, trades: List[OperatorTradeRecord]) -> int:
        with self._get_conn() as conn:
            for t in trades:
                rec_hash = t.compute_sha256()
                conn.execute("""
                INSERT OR REPLACE INTO operativa_operador (
                    trade_id, instrument, direction, setup_id, strategy_version,
                    entry_timestamp_utc, entry_price, stop_loss_price, take_profit_price,
                    exit_timestamp_utc, exit_price, outcome, risk_r_multiple_ppm,
                    net_pnl_usd_scaled, commission_usd_scaled, slippage_pips_scaled,
                    market_regime_tag, operator_notes, source_file_sha256, record_sha256
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """, (
                    t.trade_id, t.instrument, t.direction.value, t.setup_id, t.strategy_version,
                    t.entry_timestamp_utc, t.entry_price, t.stop_loss_price, t.take_profit_price,
                    t.exit_timestamp_utc, t.exit_price, t.outcome.value, t.risk_r_multiple_ppm,
                    t.net_pnl_usd_scaled, t.commission_usd_scaled, t.slippage_pips_scaled,
                    t.market_regime_tag, t.operator_notes, t.source_file_sha256, rec_hash
                ))
            conn.commit()
        return len(trades)

    def get_operator_trades(self, setup_id: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        with self._get_conn() as conn:
            conn.row_factory = sqlite3.Row
            if setup_id:
                cursor = conn.execute("""
                SELECT * FROM operativa_operador 
                WHERE setup_id = ? 
                ORDER BY entry_timestamp_utc DESC LIMIT ?;
                """, (setup_id, limit))
            else:
                cursor = conn.execute("""
                SELECT * FROM operativa_operador 
                ORDER BY entry_timestamp_utc DESC LIMIT ?;
                """, (limit,))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def get_operator_performance_by_setup(self) -> Dict[str, Any]:
        """Calcula el rendimiento cuantitativo agrupado por setup del operador."""
        with self._get_conn() as conn:
            cursor = conn.execute("""
            SELECT 
                setup_id,
                COUNT(*) as total_trades,
                SUM(CASE WHEN outcome = 'WIN' THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN outcome = 'LOSS' THEN 1 ELSE 0 END) as losses,
                AVG(risk_r_multiple_ppm) as avg_r_ppm,
                SUM(net_pnl_usd_scaled) as total_pnl_cents
            FROM operativa_operador
            WHERE outcome IN ('WIN', 'LOSS', 'BREAKEVEN')
            GROUP BY setup_id;
            """)
            stats = {}
            for row in cursor.fetchall():
                setup, total, wins, losses, avg_r, pnl_cents = row
                win_rate = (wins / max(1, total)) * 100.0
                stats[setup] = {
                    "total_trades": total,
                    "wins": wins,
                    "losses": losses,
                    "win_rate_pct": round(win_rate, 2),
                    "avg_r_multiple": round(avg_r / 1_000_000, 2) if avg_r else 0.0,
                    "total_pnl_usd": round(pnl_cents / 100, 2) if pnl_cents else 0.0,
                }
            return stats

    # --- Operaciones de Operativas Simuladas bajo el Modelo ---
    def save_simulated_operation(self, op: SimulatedOperation) -> None:
        with self._get_conn() as conn:
            conn.execute("""
            INSERT OR REPLACE INTO operativa_simulada (
                operation_id, instrument, direction, entry_timestamp_utc, entry_price,
                stop_loss_price, take_profit_price, size, exit_timestamp_utc, exit_price,
                status, pnl_usd, return_pct, r_multiple, slippage_pips, commission_usd,
                acute_slippage_penalty, execution_spectrum_tier, simulated_risk_pct, close_reason
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                op.operation_id, op.instrument, op.direction.value, op.entry_timestamp_utc,
                op.entry_price, op.stop_loss_price, op.take_profit_price, op.size,
                op.exit_timestamp_utc, op.exit_price, op.status, op.pnl_usd, op.return_pct,
                op.r_multiple, op.slippage_pips, op.commission_usd, op.acute_slippage_penalty,
                op.execution_spectrum_tier, op.simulated_risk_pct_at_entry, op.close_reason
            ))
            conn.commit()

    def get_simulated_operations(self, instrument: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        with self._get_conn() as conn:
            conn.row_factory = sqlite3.Row
            if instrument:
                cursor = conn.execute("""
                SELECT * FROM operativa_simulada
                WHERE instrument = ?
                ORDER BY entry_timestamp_utc DESC LIMIT ?;
                """, (instrument.upper(), limit))
            else:
                cursor = conn.execute("""
                SELECT * FROM operativa_simulada
                ORDER BY entry_timestamp_utc DESC LIMIT ?;
                """, (limit,))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def get_simulated_operations_stats(self, instrument: Optional[str] = None) -> Dict[str, Any]:
        with self._get_conn() as conn:
            query = """
            SELECT
                COUNT(*) as total_ops,
                SUM(CASE WHEN status = 'CLOSED' AND pnl_usd > 0 THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN status = 'CLOSED' AND pnl_usd < 0 THEN 1 ELSE 0 END) as losses,
                SUM(pnl_usd) as total_pnl,
                AVG(return_pct) as avg_return_pct,
                AVG(simulated_risk_pct) as avg_risk_pct,
                AVG(slippage_pips) as avg_slippage
            FROM operativa_simulada
            """
            params: tuple = ()
            if instrument:
                query += " WHERE instrument = ?"
                params = (instrument.upper(),)
            cursor = conn.execute(query, params)
            row = cursor.fetchone()
            total, wins, losses, pnl, avg_ret, avg_risk, avg_slip = row
            total = total or 0
            wins = wins or 0
            losses = losses or 0
            win_rate = (wins / max(1, wins + losses)) * 100.0 if (wins + losses) > 0 else 50.0
            return {
                "total_operations": total,
                "wins": wins,
                "losses": losses,
                "win_rate_pct": round(win_rate, 2),
                "total_pnl_usd": round(pnl or 0.0, 2),
                "avg_return_pct": round(avg_ret or 0.0, 3),
                "avg_simulated_risk_pct": round(avg_risk or 0.0, 2),
                "avg_slippage_pips": round(avg_slip or 0.0, 4),
            }

