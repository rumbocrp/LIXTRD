"""Interruptor de emergencia (Kill Switch) fail-closed y recuperación auditada (SPEC-001 §8, CA-18)."""

from datetime import datetime
from typing import Literal

from sistema_luces.domain.error import ErrorDominio
from sistema_luces.domain.result import Resultado, exito, fallo
from sistema_luces.domain.vocabulary import Actor


class InterruptorEmergencia:
    """Controla el estado del Kill Switch y su desbloqueo verificado."""

    def __init__(self) -> None:
        self._activo: bool = False
        self._motivo: str | None = None
        self._activado_en_utc: datetime | None = None

    @property
    def activo(self) -> bool:
        return self._activo

    @property
    def motivo(self) -> str | None:
        return self._motivo

    @property
    def activado_en_utc(self) -> datetime | None:
        return self._activado_en_utc

    def activar(self, motivo: str, timestamp_utc: datetime) -> None:
        self._activo = True
        self._motivo = motivo
        self._activado_en_utc = timestamp_utc

    def recuperar(self, actor: Actor | str, resolucion: str) -> Resultado[bool]:
        """Recupera el kill switch requiriendo actor explícito y resolución no vacía."""
        if not actor or not isinstance(actor, str) or not actor.strip():
            return fallo(
                ErrorDominio(
                    codigo="VALIDATION_ERROR",
                    mensaje_seguro="Recuperación del kill switch exige un actor válido",
                    reintentable=False,
                    correlation_id="",
                    detalles={"actor": str(actor)},
                )
            )
        if not resolucion or not isinstance(resolucion, str) or not resolucion.strip():
            return fallo(
                ErrorDominio(
                    codigo="VALIDATION_ERROR",
                    mensaje_seguro="Recuperación del kill switch exige una justificación/resolución",
                    reintentable=False,
                    correlation_id="",
                    detalles={"resolucion": str(resolucion)},
                )
            )
        self._activo = False
        self._motivo = None
        self._activado_en_utc = None
        return exito(True)
