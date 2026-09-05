"""Gestión y alineación de ventanas temporales S30 y S60 (SPEC-001 §6.5, §7.3, WP-05)."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Literal

from sistema_luces.domain.vocabulary import DecisionWindow


@dataclass(frozen=True)
class VentanaTemporal:
    decision_window: DecisionWindow
    start_utc: datetime
    end_utc: datetime


def obtener_limites_ventana(t_utc: datetime, window: DecisionWindow) -> tuple[datetime, datetime]:
    """Calcula los límites [start_utc, end_utc) o ventana correspondiente a un instante t_utc."""
    if t_utc.tzinfo is None:
        raise ValueError("t_utc debe tener zona horaria UTC")

    # Truncar microsegundos para alineación de reloj
    base_second = t_utc.replace(microsecond=0)
    second = base_second.second

    if window == "S30":
        if second < 30:
            start_sec = 0
            end_sec = 30
            start = base_second.replace(second=start_sec)
            end = base_second.replace(second=end_sec)
        else:
            start_sec = 30
            start = base_second.replace(second=start_sec)
            end = (base_second - timedelta(seconds=second)) + timedelta(minutes=1)
        return start, end

    elif window == "S60":
        start = base_second.replace(second=0)
        end = start + timedelta(minutes=1)
        return start, end

    else:
        raise ValueError(f"Ventana de decision no admitida: {window}")


def es_cierre_de_ventana(t_utc: datetime, window: DecisionWindow) -> bool:
    """Verifica si t_utc corresponde a un límite de cierre exacto (:00 o :30 para S30; :00 para S60)."""
    if t_utc.tzinfo is None:
        raise ValueError("t_utc debe tener zona horaria UTC")

    if t_utc.microsecond != 0:
        return False

    sec = t_utc.second
    if window == "S30":
        return sec in (0, 30)
    elif window == "S60":
        return sec == 0
    return False


def siguiente_cierre_de_ventana(t_utc: datetime, window: DecisionWindow) -> datetime:
    """Calcula el próximo instante de cierre de ventana posterior a t_utc."""
    if t_utc.tzinfo is None:
        raise ValueError("t_utc debe tener zona horaria UTC")

    base = t_utc.replace(microsecond=0)
    if t_utc.microsecond > 0:
        base += timedelta(seconds=1)

    sec = base.second
    if window == "S30":
        if sec == 0 or sec == 30:
            return base
        elif sec < 30:
            return base.replace(second=30)
        else:
            return (base - timedelta(seconds=sec)) + timedelta(minutes=1)
    elif window == "S60":
        if sec == 0:
            return base
        return (base - timedelta(seconds=sec)) + timedelta(minutes=1)
    else:
        raise ValueError(f"Ventana de decision no admitida: {window}")


def alinear_ventana(t_cierre_utc: datetime, window: DecisionWindow) -> VentanaTemporal:
    """Dado un instante de cierre exacto, construye la VentanaTemporal inmutable."""
    if window == "S30":
        start = t_cierre_utc - timedelta(seconds=30)
    elif window == "S60":
        start = t_cierre_utc - timedelta(seconds=60)
    else:
        raise ValueError(f"Ventana no admitida: {window}")
    return VentanaTemporal(decision_window=window, start_utc=start, end_utc=t_cierre_utc)
