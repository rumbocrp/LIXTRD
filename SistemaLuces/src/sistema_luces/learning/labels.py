"""Etiquetado de Triple Barrera con Precios Ejecutables (SPEC-001 §6.3, §7.1, §7.2, CA-13, CA-14, WP-06)."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import re
from typing import Any, Literal
import uuid

from sistema_luces.cases.builder import CasoV1
from sistema_luces.domain.error import ErrorDominio
from sistema_luces.domain.event import QuoteTickPayloadV1, SobreEventoV1
from sistema_luces.domain.result import Resultado, exito, fallo
from sistema_luces.domain.vocabulary import Direction, parse_direction, validate_price_scaled

_UUID_REGEX = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE)


@dataclass(frozen=True)
class SolicitudEtiqueta:
    case: CasoV1
    direction: Direction
    horizon_seconds: int = 300
    stop_loss_points: int = 500  # 5.00 puntos escalados x100
    take_profit_points: int = 2000  # 20.00 puntos escalados x100
    ticks_horizonte: tuple[QuoteTickPayloadV1 | SobreEventoV1, ...] = ()
    correlation_id: str = ""


@dataclass(frozen=True)
class EtiquetaV1:
    label_id: str
    case_id: str
    direction: Direction
    status: Literal["MATURE", "INVALID", "PENDING"]
    outcome: Literal["TAKE_PROFIT", "STOP_LOSS", "HORIZON_EXPIRATION", "INVALID"]
    entry_price: int
    exit_price: int
    stop_barrier_price: int
    target_barrier_price: int
    price_scale: int
    first_touch_at_utc: datetime | None
    horizon_end_utc: datetime
    realized_points: int
    is_ambiguous_tie: bool
    reason_codes: tuple[str, ...]
    correlation_id: str
    causation_id: str | None
    created_at_utc: datetime


def validar_etiqueta(eti: EtiquetaV1) -> Resultado[EtiquetaV1]:
    if not isinstance(eti.label_id, str) or not _UUID_REGEX.match(eti.label_id):
        return fallo(
            ErrorDominio(
                codigo="VALIDATION_ERROR",
                mensaje_seguro="label_id debe ser un UUID valido",
                reintentable=False,
                correlation_id=eti.correlation_id,
                detalles={"label_id": str(eti.label_id)},
            )
        )
    if not isinstance(eti.case_id, str) or not _UUID_REGEX.match(eti.case_id):
        return fallo(
            ErrorDominio(
                codigo="VALIDATION_ERROR",
                mensaje_seguro="case_id debe ser un UUID valido",
                reintentable=False,
                correlation_id=eti.correlation_id,
                detalles={"case_id": str(eti.case_id)},
            )
        )
    dir_res = parse_direction(eti.direction, eti.correlation_id)
    if not dir_res.exito:
        return fallo(dir_res.error)

    return exito(eti)


def _extraer_tick_info(tick: QuoteTickPayloadV1 | SobreEventoV1 | dict[str, Any]) -> tuple[int, int, datetime, int | None]:
    """Normaliza un tick a (bid, ask, timestamp_utc, sequence)."""
    if isinstance(tick, QuoteTickPayloadV1):
        return tick.bid, tick.ask, tick.source_timestamp_utc, tick.source_sequence
    elif isinstance(tick, SobreEventoV1):
        p = tick.payload
        bid = p.get("bid", 0)
        ask = p.get("ask", 0)
        seq = tick.source_sequence
        return bid, ask, tick.occurred_at_utc, seq
    elif isinstance(tick, dict):
        bid = tick.get("bid", 0)
        ask = tick.get("ask", 0)
        ts = tick.get("source_timestamp_utc") or tick.get("occurred_at_utc") or datetime.now(timezone.utc)
        seq = tick.get("source_sequence")
        return bid, ask, ts, seq
    else:
        raise TypeError(f"Tipo de tick no soportado: {type(tick)}")


class Etiquetador:
    """Implementa el contrato de triple barrera con precios ejecutables (CA-13, CA-14)."""

    def __init__(
        self,
        stop_loss_points: int = 500,
        take_profit_points: int = 2000,
        horizon_seconds: int = 300,
    ) -> None:
        self.stop_loss_points = stop_loss_points
        self.take_profit_points = take_profit_points
        self.horizon_seconds = horizon_seconds

    def madurar(
        self,
        caso_o_solicitud: CasoV1 | SolicitudEtiqueta,
        ticks_horizonte: list[QuoteTickPayloadV1] | list[SobreEventoV1] | tuple[Any, ...] | None = None,
        direction: Direction = "LONG",
        label_id: str | None = None,
    ) -> Resultado[EtiquetaV1]:
        if isinstance(caso_o_solicitud, SolicitudEtiqueta):
            caso = caso_o_solicitud.case
            dir_act = caso_o_solicitud.direction
            stop_pts = caso_o_solicitud.stop_loss_points
            tp_pts = caso_o_solicitud.take_profit_points
            horizon_sec = caso_o_solicitud.horizon_seconds
            ticks = ticks_horizonte if ticks_horizonte is not None else caso_o_solicitud.ticks_horizonte
            corr_id = caso_o_solicitud.correlation_id or caso.correlation_id
        else:
            caso = caso_o_solicitud
            dir_act = direction
            stop_pts = self.stop_loss_points
            tp_pts = self.take_profit_points
            horizon_sec = self.horizon_seconds
            ticks = ticks_horizonte or ()
            corr_id = caso.correlation_id

        actual_label_id = label_id or str(uuid.uuid4())
        horizon_end_utc = caso.window_end_utc + timedelta(seconds=horizon_sec)

        # Si faltan precios de referencia de entrada o no hay ticks
        if (
            (dir_act == "LONG" and caso.reference_ask is None)
            or (dir_act == "SHORT" and caso.reference_bid is None)
            or not ticks
        ):
            entry_p = caso.reference_ask if dir_act == "LONG" else (caso.reference_bid or 0)
            eti_invalida = EtiquetaV1(
                label_id=actual_label_id,
                case_id=caso.case_id,
                direction=dir_act,
                status="INVALID",
                outcome="INVALID",
                entry_price=entry_p or 0,
                exit_price=entry_p or 0,
                stop_barrier_price=0,
                target_barrier_price=0,
                price_scale=caso.price_scale,
                first_touch_at_utc=None,
                horizon_end_utc=horizon_end_utc,
                realized_points=0,
                is_ambiguous_tie=False,
                reason_codes=("INSUFFICIENT_OR_UNKNOWN_DATA",),
                correlation_id=corr_id,
                causation_id=caso.case_id,
                created_at_utc=caso.window_end_utc,
            )
            return exito(eti_invalida)

        # LONG: Entra al ask, evalua barreras contra bid ejecutable
        if dir_act == "LONG":
            assert caso.reference_ask is not None
            entry_price = caso.reference_ask
            stop_barrier = entry_price - stop_pts
            target_barrier = entry_price + tp_pts

            hit_outcome: Literal["TAKE_PROFIT", "STOP_LOSS", "HORIZON_EXPIRATION"] | None = None
            exit_price: int = entry_price
            first_touch_time: datetime | None = None
            is_ambiguous: bool = False
            reasons: list[str] = []

            last_bid: int = entry_price
            last_time: datetime = caso.window_end_utc

            for tick in ticks:
                bid, ask, ts, seq = _extraer_tick_info(tick)
                if ts > horizon_end_utc:
                    break

                last_bid = bid
                last_time = ts

                hit_stop = bid <= stop_barrier
                hit_target = bid >= target_barrier or ask >= target_barrier

                # Empate ambiguo en tick atómico -> STOP_FIRST (§7.1, CA-14, Tabla 7.2)
                if hit_stop and hit_target:
                    hit_outcome = "STOP_LOSS"
                    exit_price = stop_barrier
                    first_touch_time = ts
                    is_ambiguous = True
                    reasons.append("AMBIGUOUS_STOP_FIRST")
                    break

                if hit_stop:
                    hit_outcome = "STOP_LOSS"
                    exit_price = stop_barrier
                    first_touch_time = ts
                    break

                if bid >= target_barrier:
                    hit_outcome = "TAKE_PROFIT"
                    exit_price = target_barrier
                    first_touch_time = ts
                    break

            if hit_outcome is None:
                # Expiración de horizonte
                hit_outcome = "HORIZON_EXPIRATION"
                exit_price = last_bid
                first_touch_time = last_time
                reasons.append("HORIZON_TIMEOUT")

            realized_pts = exit_price - entry_price

        # SHORT: Entra al bid, evalua barreras contra ask ejecutable
        elif dir_act == "SHORT":
            assert caso.reference_bid is not None
            entry_price = caso.reference_bid
            stop_barrier = entry_price + stop_pts
            target_barrier = entry_price - tp_pts

            hit_outcome = None
            exit_price = entry_price
            first_touch_time = None
            is_ambiguous = False
            reasons = []

            last_ask: int = entry_price
            last_time = caso.window_end_utc

            for tick in ticks:
                bid, ask, ts, seq = _extraer_tick_info(tick)
                if ts > horizon_end_utc:
                    break

                last_ask = ask
                last_time = ts

                hit_stop = ask >= stop_barrier
                hit_target = ask <= target_barrier or bid <= target_barrier

                # Empate ambiguo en tick atómico -> STOP_FIRST (§7.1, CA-14)
                if hit_stop and hit_target:
                    hit_outcome = "STOP_LOSS"
                    exit_price = stop_barrier
                    first_touch_time = ts
                    is_ambiguous = True
                    reasons.append("AMBIGUOUS_STOP_FIRST")
                    break

                if hit_stop:
                    hit_outcome = "STOP_LOSS"
                    exit_price = stop_barrier
                    first_touch_time = ts
                    break

                if ask <= target_barrier:
                    hit_outcome = "TAKE_PROFIT"
                    exit_price = target_barrier
                    first_touch_time = ts
                    break

            if hit_outcome is None:
                hit_outcome = "HORIZON_EXPIRATION"
                exit_price = last_ask
                first_touch_time = last_time
                reasons.append("HORIZON_TIMEOUT")

            realized_pts = entry_price - exit_price

        else:
            return fallo(
                ErrorDominio(
                    codigo="VALIDATION_ERROR",
                    mensaje_seguro=f"Direccion invalida para etiquetado: {dir_act}",
                    reintentable=False,
                    correlation_id=corr_id,
                    detalles={"direction": str(dir_act)},
                )
            )

        eti = EtiquetaV1(
            label_id=actual_label_id,
            case_id=caso.case_id,
            direction=dir_act,
            status="MATURE",
            outcome=hit_outcome,
            entry_price=entry_price,
            exit_price=exit_price,
            stop_barrier_price=stop_barrier,
            target_barrier_price=target_barrier,
            price_scale=caso.price_scale,
            first_touch_at_utc=first_touch_time,
            horizon_end_utc=horizon_end_utc,
            realized_points=realized_pts,
            is_ambiguous_tie=is_ambiguous,
            reason_codes=tuple(reasons),
            correlation_id=corr_id,
            causation_id=caso.case_id,
            created_at_utc=first_touch_time or horizon_end_utc,
        )

        res_val = validar_etiqueta(eti)
        if not res_val.exito:
            return fallo(res_val.error)

        return exito(eti)
