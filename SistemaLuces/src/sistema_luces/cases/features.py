"""Cálculo de snapshots de features causales y hashing determinista (SPEC-001 §6.3, §6.5, OPT-7, WP-05)."""

from datetime import datetime
from typing import Any

from sistema_luces.domain.event import SobreEventoV1, compute_payload_hash


def calcular_snapshot_hash(snapshot: dict[str, Any]) -> str:
    """Calcula el hash SHA-256 canónico del diccionario de features (excluyendo la clave de hash si estuviera presente)."""
    snapshot_clean = {k: v for k, v in snapshot.items() if k != "feature_snapshot_hash"}
    return compute_payload_hash(snapshot_clean)


def calcular_snapshot_features(
    events: list[SobreEventoV1] | tuple[SobreEventoV1, ...],
    window_start_utc: datetime,
    window_end_utc: datetime,
    market_event_cutoff: datetime,
) -> dict[str, Any]:
    """Extrae features causales estrictamente respetando los límites de ventana y corte temporal (OPT-7).

    Preserva valores faltantes como None sin inventar ceros (ADR-001 §6).
    """
    if market_event_cutoff < window_end_utc:
        cutoff = market_event_cutoff
    else:
        cutoff = window_end_utc

    # Filtrar únicamente ticks de mercado dentro de la ventana y <= cutoff causal
    quote_ticks: list[SobreEventoV1] = []
    for ev in events:
        if ev.event_type == "QUOTE_TICK":
            if window_start_utc <= ev.occurred_at_utc <= cutoff:
                quote_ticks.append(ev)

    # Orden determinista: occurred_at_utc, secuencia, event_id
    quote_ticks.sort(
        key=lambda x: (
            x.occurred_at_utc,
            x.source_sequence if x.source_sequence is not None else 0,
            x.event_id,
        )
    )

    if not quote_ticks:
        snapshot: dict[str, Any] = {
            "tick_count": 0,
            "spread_last": None,
            "spread_mean": None,
            "price_first_bid": None,
            "price_first_ask": None,
            "price_last_bid": None,
            "price_last_ask": None,
            "price_return_points": None,
            "price_high": None,
            "price_low": None,
            "volume_total": None,
            "order_imbalance": None,
            "data_age_ms": None,
        }
        snapshot["feature_snapshot_hash"] = calcular_snapshot_hash(snapshot)
        return snapshot

    # Extraer arrays de datos
    bids: list[int] = []
    asks: list[int] = []
    spreads: list[int] = []
    bid_sizes: list[int] = []
    ask_sizes: list[int] = []

    for tick in quote_ticks:
        p = tick.payload
        bid = p.get("bid")
        ask = p.get("ask")
        if bid is not None and ask is not None:
            bids.append(bid)
            asks.append(ask)
            spreads.append(ask - bid)

        b_size = p.get("size_bid") if p.get("size_bid") is not None else p.get("bid_size")
        a_size = p.get("size_ask") if p.get("size_ask") is not None else p.get("ask_size")
        if b_size is not None:
            bid_sizes.append(b_size)
        if a_size is not None:
            ask_sizes.append(a_size)

    first_bid = bids[0]
    first_ask = asks[0]
    last_bid = bids[-1]
    last_ask = asks[-1]

    spread_last = last_ask - last_bid
    spread_mean = int(sum(spreads) / len(spreads)) if spreads else None
    price_return = last_bid - first_bid
    price_high = max(asks) if asks else None
    price_low = min(bids) if bids else None

    # Cálculo de volumen e imbalance si están presentes
    if bid_sizes or ask_sizes:
        total_b = sum(bid_sizes)
        total_a = sum(ask_sizes)
        total_vol = total_b + total_a
        if total_vol > 0:
            volume_total: int | None = total_vol
            # Imbalance escalado a -1_000_000 .. 1_000_000
            order_imbalance: int | None = int(((total_b - total_a) / total_vol) * 1_000_000)
        else:
            volume_total = None
            order_imbalance = None
    else:
        volume_total = None
        order_imbalance = None

    last_tick_time = quote_ticks[-1].occurred_at_utc
    data_age_ms = max(0, int((cutoff - last_tick_time).total_seconds() * 1000))

    snapshot = {
        "tick_count": len(quote_ticks),
        "spread_last": spread_last,
        "spread_mean": spread_mean,
        "price_first_bid": first_bid,
        "price_first_ask": first_ask,
        "price_last_bid": last_bid,
        "price_last_ask": last_ask,
        "price_return_points": price_return,
        "price_high": price_high,
        "price_low": price_low,
        "volume_total": volume_total,
        "order_imbalance": order_imbalance,
        "data_age_ms": data_age_ms,
    }

    snapshot["feature_snapshot_hash"] = calcular_snapshot_hash(snapshot)
    return snapshot
