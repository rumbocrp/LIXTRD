"""Evaluador de triple barrera y ciclo de vida de órdenes paper (SPEC-001 §7.1, CA-13, CA-14)."""

from typing import Literal


class EvaluadorTripleBarrera:
    """Evalúa ticks de mercado contra las barreras de Stop Loss, Take Profit y tiempo."""

    def __init__(
        self,
        stop_loss_points: int = 500,     # 5 puntos (price_scale = 100)
        take_profit_points: int = 2000,  # 20 puntos (price_scale = 100)
    ) -> None:
        self.stop_loss_points = stop_loss_points
        self.take_profit_points = take_profit_points

    def evaluar_tick_long(
        self,
        entry_ask: int,
        tick_bid: int,
        tick_ask: int,
    ) -> tuple[Literal["OPEN", "TAKE_PROFIT", "STOP_LOSS", "AMBIGUOUS_STOP_FIRST"], int]:
        """Para posición LONG: Entrada al Ask; Stop y Target se validan al Bid."""
        stop_price = entry_ask - self.stop_loss_points
        target_price = entry_ask + self.take_profit_points

        hit_stop = tick_bid <= stop_price
        hit_target = tick_bid >= target_price or tick_ask >= target_price

        # Invariante CA-14: Ambigüedad en tick atómico resuelve STOP_FIRST
        if hit_stop and hit_target:
            return "AMBIGUOUS_STOP_FIRST", stop_price
        if hit_stop:
            return "STOP_LOSS", stop_price
        if tick_bid >= target_price:
            return "TAKE_PROFIT", target_price
        return "OPEN", tick_bid

    def evaluar_tick_short(
        self,
        entry_bid: int,
        tick_bid: int,
        tick_ask: int,
    ) -> tuple[Literal["OPEN", "TAKE_PROFIT", "STOP_LOSS", "AMBIGUOUS_STOP_FIRST"], int]:
        """Para posición SHORT: Entrada al Bid; Stop y Target se validan al Ask."""
        stop_price = entry_bid + self.stop_loss_points
        target_price = entry_bid - self.take_profit_points

        hit_stop = tick_ask >= stop_price
        hit_target = tick_ask <= target_price or tick_bid <= target_price

        # Invariante CA-14: Ambigüedad en tick atómico resuelve STOP_FIRST
        if hit_stop and hit_target:
            return "AMBIGUOUS_STOP_FIRST", stop_price
        if hit_stop:
            return "STOP_LOSS", stop_price
        if tick_ask <= target_price:
            return "TAKE_PROFIT", target_price
        return "OPEN", tick_ask
