"""Perfilador de Comportamiento y Análisis Cuantitativo de la Operativa del Operador (Fase 3)."""

from __future__ import annotations
import math
from typing import List, Dict, Any, Optional
from collections import defaultdict
from sistema_luces.domain.operator_trade import OperatorTradeRecord, TradeOutcome

class OperatorBehavioralProfiler:
    """Analiza cuantitativamente los patrones de éxito y ventaja (Edge) del operador por setup y régimen."""
    def __init__(self):
        self.trades: List[OperatorTradeRecord] = []

    def load_trades(self, trades: List[OperatorTradeRecord]) -> int:
        self.trades = [t for t in trades if t.is_closed]
        return len(self.trades)

    def compute_setup_profiles(self) -> Dict[str, Dict[str, Any]]:
        """Genera un perfil cuantitativo detallado para cada setup operado por el usuario."""
        grouped: Dict[str, List[OperatorTradeRecord]] = defaultdict(list)
        for t in self.trades:
            grouped[t.setup_id].append(t)

        profiles = {}
        for setup_id, t_list in grouped.items():
            profiles[setup_id] = self._analyze_trade_group(t_list)
        return profiles

    def compute_regime_profiles(self) -> Dict[str, Dict[str, Any]]:
        """Analiza el rendimiento del operador segmentado por régimen de mercado."""
        grouped: Dict[str, List[OperatorTradeRecord]] = defaultdict(list)
        for t in self.trades:
            grouped[t.market_regime_tag].append(t)

        regime_stats = {}
        for regime, t_list in grouped.items():
            regime_stats[regime] = self._analyze_trade_group(t_list)
        return regime_stats

    def _analyze_trade_group(self, trades: List[OperatorTradeRecord]) -> Dict[str, Any]:
        total = len(trades)
        if total == 0:
            return {"total_trades": 0, "win_rate_pct": 0.0, "expectancy_r": 0.0, "edge_tag": "NO_DATA"}

        wins = [t for t in trades if t.outcome == TradeOutcome.WIN]
        losses = [t for t in trades if t.outcome == TradeOutcome.LOSS]
        bes = [t for t in trades if t.outcome == TradeOutcome.BREAKEVEN]

        win_rate = len(wins) / total
        loss_rate = len(losses) / total

        # R-múltiplos en unidades reales (PPM / 1_000_000)
        r_wins = [t.risk_r_multiple_ppm / 1_000_000 for t in wins]
        r_losses = [abs(t.risk_r_multiple_ppm / 1_000_000) for t in losses]

        avg_win_r = (sum(r_wins) / len(wins)) if wins else 0.0
        avg_loss_r = (sum(r_losses) / len(losses)) if losses else 1.0

        # Esperanza matemática en R: E[R] = (WinRate * AvgWin) - (LossRate * AvgLoss)
        expectancy_r = (win_rate * avg_win_r) - (loss_rate * avg_loss_r)
        
        # Profit Factor en R
        gross_win_r = sum(r_wins)
        gross_loss_r = sum(r_losses)
        profit_factor = (gross_win_r / gross_loss_r) if gross_loss_r > 0 else (99.0 if gross_win_r > 0 else 1.0)

        # Clasificación del Edge
        if total >= 5 and expectancy_r >= 0.50 and profit_factor >= 1.8:
            edge_tag = "STRONG_EDGE"
        elif total >= 3 and expectancy_r >= 0.15 and profit_factor >= 1.2:
            edge_tag = "MODERATE_EDGE"
        elif expectancy_r < -0.10:
            edge_tag = "NEGATIVE_EDGE"
        else:
            edge_tag = "NEUTRAL"

        return {
            "total_trades": total,
            "wins": len(wins),
            "losses": len(losses),
            "breakevens": len(bes),
            "win_rate_pct": round(win_rate * 100.0, 2),
            "avg_win_r": round(avg_win_r, 2),
            "avg_loss_r": round(avg_loss_r, 2),
            "expectancy_r": round(expectancy_r, 2),
            "profit_factor": round(profit_factor, 2),
            "edge_tag": edge_tag,
        }
