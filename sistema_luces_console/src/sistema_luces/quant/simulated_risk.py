"""Motor Cuantitativo de Estimación de Riesgo Simulado y Métricas Estadísticas (VaR / CVaR)."""

from __future__ import annotations
import math
from typing import List, Optional
import numpy as np
from sistema_luces.domain.simulated_trade import SimulatedRiskMetrics, SimulatedOperation, AcuteExecutionResult

class SimulatedRiskEngine:
    """
    Calcula y audita el espectro de riesgo simulado bajo el modelo del Sistema de Luces:
    - Riesgo de ejecución instantáneo ponderado por agudeza microestructural.
    - Value-at-Risk (VaR 95%) y Conditional VaR (Expected Shortfall) mediante cuantiles empíricos NumPy.
    - Factor de asignación dinámica de capital por operación.
    - Drawdown acumulado y perfil de rendimiento de las operativas simuladas.
    """
    def __init__(
        self,
        base_position_risk_pct: float = 1.50, # 1.5% de riesgo base por trade
        initial_equity_usd: float = 10_000.0, # Capital simulado de referencia
        history_window: int = 100,            # Ventana de operaciones para VaR/CVaR
    ):
        self.base_position_risk_pct = base_position_risk_pct
        self.initial_equity_usd = initial_equity_usd
        self.current_equity_usd = initial_equity_usd
        self.peak_equity_usd = initial_equity_usd
        self.max_drawdown_pct = 0.0

        self.returns_history: List[float] = []
        self.closed_operations_count = 0
        self.winning_operations_count = 0
        self.gross_profit_usd = 0.0
        self.gross_loss_usd = 0.0
        self.realized_pnl_usd = 0.0
        self.history_window = history_window

    def record_closed_operation(self, op: SimulatedOperation) -> None:
        """Registra una operación simulada cerrada y actualiza la curva de equity y estadísticas."""
        self.closed_operations_count += 1
        pnl = op.pnl_usd
        self.realized_pnl_usd += pnl
        self.current_equity_usd += pnl

        if self.current_equity_usd > self.peak_equity_usd:
            self.peak_equity_usd = self.current_equity_usd

        # Cálculo de drawdown histórico
        if self.peak_equity_usd > 0:
            dd = ((self.peak_equity_usd - self.current_equity_usd) / self.peak_equity_usd) * 100.0
            if dd > self.max_drawdown_pct:
                self.max_drawdown_pct = dd

        # Retorno porcentual de la operación
        self.returns_history.append(op.return_pct)
        if len(self.returns_history) > self.history_window:
            self.returns_history.pop(0)

        # Estadísticas de ganancia / pérdida
        if pnl > 0:
            self.winning_operations_count += 1
            self.gross_profit_usd += pnl
        elif pnl < 0:
            self.gross_loss_usd += abs(pnl)

    def compute_risk_metrics(
        self,
        acute_result: AcuteExecutionResult,
        z_score: float,
        vpin: float,
        confidence_ppm: int,
        open_operations: List[SimulatedOperation],
    ) -> SimulatedRiskMetrics:
        """
        Calcula el conjunto completo de métricas de riesgo simulado en tiempo real.
        """
        sharpness = acute_result.spectrum_sharpness_score

        # 1. Riesgo instantáneo de ejecución [0.0 - 100.0%]
        # La divergencia extrema de Kalman (|Z| > 1.2) amplifica el riesgo de fricción
        z_divergence = max(0.0, abs(z_score) - 1.2)
        instant_exec_risk = min(100.0, sharpness * (1.0 + (0.50 * z_divergence)))

        # 2. Asignación de riesgo por posición [0.5% - 3.0%]
        # Convicción alta aumenta asignación; agudeza alta (fricción severa) la reduce defensivamente
        conf_ratio = max(0.2, min(1.0, confidence_ppm / 1_000_000.0))
        friction_defense = 1.0 - (0.45 * (sharpness / 100.0))
        pos_risk_pct = max(0.50, min(3.0, self.base_position_risk_pct * conf_ratio * friction_defense))

        # 3. Value-at-Risk (VaR 95%) y Conditional VaR (CVaR / Expected Shortfall) mediante NumPy
        if len(self.returns_history) >= 5:
            arr = np.array(self.returns_history)
            # El cuantil 5% representa la cola de pérdidas
            q05 = float(np.quantile(arr, 0.05))
            var_95 = max(0.0, -q05) # Pérdida esperada en el peor 5%
            tail_losses = arr[arr <= q05]
            if len(tail_losses) > 0:
                cvar_95 = max(var_95, float(-np.mean(tail_losses)))
            else:
                cvar_95 = var_95
        else:
            # Estimación a priori calibrada en base a la fricción instantánea
            var_95 = round(0.85 + (sharpness * 0.025), 2)
            cvar_95 = round(var_95 * 1.35, 2)

        # 4. Porcentaje Total de Riesgo Simulado Compuesto [0.0 - 100.0%]
        # Combina riesgo de ejecución, toxicidad VPIN y riesgo de cola histórico
        comp_risk = (
            (instant_exec_risk * 0.40)
            + (vpin * 100.0 * 0.35)
            + (min(100.0, var_95 * 10.0) * 0.25)
        )
        total_risk_pct = max(1.0, min(100.0, comp_risk))

        # 5. PnL no realizado de posiciones abiertas
        unrealized = sum(op.pnl_usd for op in open_operations)

        # 6. Win Rate y Profit Factor
        total_closed = self.closed_operations_count
        if total_closed > 0:
            win_rate = (self.winning_operations_count / total_closed) * 100.0
        else:
            win_rate = 50.0

        if self.gross_loss_usd > 1e-4:
            profit_factor = round(self.gross_profit_usd / self.gross_loss_usd, 2)
        elif self.gross_profit_usd > 0:
            profit_factor = 9.99
        else:
            profit_factor = 1.00

        return SimulatedRiskMetrics(
            instantaneous_execution_risk_pct=instant_exec_risk,
            position_risk_pct=pos_risk_pct,
            rolling_simulated_var_95_pct=var_95,
            rolling_simulated_cvar_95_pct=cvar_95,
            total_simulated_risk_pct=total_risk_pct,
            max_simulated_drawdown_pct=self.max_drawdown_pct,
            win_rate_pct=win_rate,
            profit_factor=profit_factor,
            total_trades_count=total_closed + len(open_operations),
            open_trades_count=len(open_operations),
            realized_pnl_usd=round(self.realized_pnl_usd, 2),
            unrealized_pnl_usd=round(unrealized, 2),
        )
