"""Calendario de noticias y detección de ventanas de blackout (SPEC-001 §8, CA-17)."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal


@dataclass(frozen=True)
class EventoNoticia:
    event_id: str
    nombre: str
    impacto: Literal["HIGH", "MEDIUM", "LOW"]
    moneda: str
    timestamp_utc: datetime


class CalendarioNoticias:
    """Gestiona eventos de calendario económico y determina ventanas de bloqueo."""

    def __init__(self, blackout_minutes: int = 15) -> None:
        self.blackout_minutes = blackout_minutes
        self._eventos: list[EventoNoticia] = []

    def registrar_evento(self, evento: EventoNoticia) -> None:
        self._eventos.append(evento)

    def esta_en_blackout(self, timestamp_utc: datetime) -> bool:
        """Determina si un instante cae dentro de [evento - blackout, evento + blackout] inclusive."""
        delta = timedelta(minutes=self.blackout_minutes)
        for ev in self._eventos:
            if ev.impacto == "HIGH" and ev.moneda in {"USD", "ALL"}:
                inicio = ev.timestamp_utc - delta
                fin = ev.timestamp_utc + delta
                if inicio <= timestamp_utc <= fin:
                    return True
        return False

    def intervalos_blackout(self) -> list[tuple[datetime, datetime]]:
        delta = timedelta(minutes=self.blackout_minutes)
        return [
            (ev.timestamp_utc - delta, ev.timestamp_utc + delta)
            for ev in self._eventos
            if ev.impacto == "HIGH"
        ]
