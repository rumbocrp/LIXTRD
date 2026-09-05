"""Motor de Microestructura, Order Flow Imbalance (OFI) y Micro-Price (confidencial_trade)."""

from typing import Tuple


class OrderFlowEngine:
    """Calcula el Order Flow Imbalance (OFI) y el Micro-Price a partir del libro L2."""

    def __init__(self) -> None:
        self.prev_bid_p = 0.0
        self.prev_bid_v = 0.0
        self.prev_ask_p = 0.0
        self.prev_ask_v = 0.0

    def compute(
        self, bid_p: float, bid_v: float, ask_p: float, ask_v: float
    ) -> Tuple[float, float, float]:
        """Calcula (OFI, Mid-Price, Micro-Price)."""
        if self.prev_bid_p == 0.0:
            self.prev_bid_p, self.prev_bid_v = bid_p, bid_v
            self.prev_ask_p, self.prev_ask_v = ask_p, ask_v
            mid_init = (bid_p + ask_p) / 2.0
            return 0.0, mid_init, mid_init

        # Cálculo de flujo en Bid
        if bid_p > self.prev_bid_p:
            i_bid = bid_v
        elif bid_p == self.prev_bid_p:
            i_bid = bid_v - self.prev_bid_v
        else:
            i_bid = 0.0

        # Cálculo de flujo en Ask
        if ask_p < self.prev_ask_p:
            i_ask = ask_v
        elif ask_p == self.prev_ask_p:
            i_ask = ask_v - self.prev_ask_v
        else:
            i_ask = 0.0

        ofi = i_bid - i_ask
        mid_price = (bid_p + ask_p) / 2.0
        # Micro-Price ponderado por volumen opuesto (Stoikov)
        micro_price = (bid_p * ask_v + ask_p * bid_v) / max(1e-4, bid_v + ask_v)

        self.prev_bid_p, self.prev_bid_v = bid_p, bid_v
        self.prev_ask_p, self.prev_ask_v = ask_p, ask_v

        return ofi, mid_price, micro_price
