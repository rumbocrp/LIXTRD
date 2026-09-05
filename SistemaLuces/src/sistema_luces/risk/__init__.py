"""Módulo de gestión de riesgos, kill switch y tripwires (SPEC-001 §8, CA-16, CA-17, CA-18)."""

from sistema_luces.risk.blackout import CalendarioNoticias, EventoNoticia
from sistema_luces.risk.engine import MotorRiesgo
from sistema_luces.risk.kill_switch import InterruptorEmergencia

__all__ = [
    "CalendarioNoticias",
    "EventoNoticia",
    "InterruptorEmergencia",
    "MotorRiesgo",
]
