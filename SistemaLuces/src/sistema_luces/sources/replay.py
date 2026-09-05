"""Fuente de datos de Replay y stepping temporal determinista (SPEC-001 §5.3, §12.6, CA-9, CA-23)."""

from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal

from sistema_luces.domain.error import ErrorDominio
from sistema_luces.domain.event import SobreEventoV1
from sistema_luces.domain.result import Resultado, exito, fallo
from sistema_luces.domain.vocabulary import Environment, parse_environment
from sistema_luces.sources.clock import RelojDominio


@dataclass(frozen=True)
class SolicitudFuente:
    correlation_id: str
    environment: Literal["REPLAY", "SHADOW"]
    source_profile_version: str
    instrument: Literal["US500"]
    range_start_utc: datetime
    range_end_utc: datetime
    clock_seed: int = 20260829
    event_cutoff_utc: datetime | None = None


@dataclass(frozen=True)
class ResumenFuente:
    session_id: str
    final_cutoff_utc: datetime | None
    total_received: int
    total_rejected: int
    reason_codes: tuple[str, ...] = ()


class SesionReplay:
    """Sesion de reproduccion de eventos secuencial sin sesgo de anticipacion."""

    def __init__(
        self,
        solicitud: SolicitudFuente,
        dataset: list[SobreEventoV1],
        reloj: RelojDominio,
    ) -> None:
        self.solicitud = solicitud
        self._reloj = reloj
        self._pausada = False
        self._indice = 0
        self._recibidos = 0
        self._rechazados = 0

        # Filtrar por ventana temporal y cutoff (OPT-7, CA-9)
        filtrados: list[SobreEventoV1] = []
        for ev in dataset:
            if ev.occurred_at_utc < solicitud.range_start_utc:
                continue
            if ev.occurred_at_utc > solicitud.range_end_utc:
                continue
            if solicitud.event_cutoff_utc and ev.occurred_at_utc > solicitud.event_cutoff_utc:
                continue
            filtrados.append(ev)

        # Ordenar temporalmente por occurred_at_utc y source_sequence
        filtrados.sort(key=lambda e: (e.occurred_at_utc, e.source_sequence or 0))
        self._eventos = filtrados

    @property
    def reloj(self) -> RelojDominio:
        return self._reloj

    def pausar(self) -> None:
        self._pausada = True

    def reanudar(self) -> None:
        self._pausada = False

    def esta_pausada(self) -> bool:
        return self._pausada

    def paso(self) -> Resultado[SobreEventoV1 | None]:
        """Avanza un paso en la emision de eventos y sincroniza el reloj de dominio."""
        if self._pausada:
            return exito(None)
        if self._indice >= len(self._eventos):
            return exito(None)

        evento = self._eventos[self._indice]
        self._indice += 1
        self._recibidos += 1

        # Avanzar el reloj de dominio
        self._reloj.avanzar_hasta(evento.occurred_at_utc)
        return exito(evento)

    def eventos_sync(self) -> Iterator[Resultado[SobreEventoV1]]:
        """Generador sincronico de eventos hasta el final del dataset."""
        while self._indice < len(self._eventos):
            if self._pausada:
                break
            res = self.paso()
            if not res.exito:
                yield res
                break
            if res.datos is not None:
                yield exito(res.datos)

    async def eventos(self) -> AsyncIterator[Resultado[SobreEventoV1]]:
        """Generador asincronico de eventos para protocolo SesionFuente (§5.3)."""
        for item in self.eventos_sync():
            yield item

    def cerrar(self) -> Resultado[ResumenFuente]:
        """Cierra la sesion y emite el resumen final."""
        return exito(
            ResumenFuente(
                session_id=self.solicitud.correlation_id,
                final_cutoff_utc=self._reloj.ahora_utc(),
                total_received=self._recibidos,
                total_rejected=self._rechazados,
                reason_codes=(),
            )
        )


class FuenteReplay:
    """Fuente de mercado determinista para entorno REPLAY."""

    def abrir(
        self,
        solicitud: SolicitudFuente,
        dataset: list[SobreEventoV1] | None = None,
    ) -> Resultado[SesionReplay]:
        """Abre una nueva sesion de replay validando entorno y configurando el reloj."""
        env_res = parse_environment(solicitud.environment, solicitud.correlation_id)
        if not env_res.exito:
            return fallo(env_res.error)

        reloj = RelojDominio(
            tiempo_inicial_utc=solicitud.range_start_utc,
            clock_seed=solicitud.clock_seed,
        )
        sesion = SesionReplay(
            solicitud=solicitud,
            dataset=dataset or [],
            reloj=reloj,
        )
        return exito(sesion)
