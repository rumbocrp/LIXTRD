"""Maquina de estados de salud del Feed (SPEC-001 §6.4, CA-8)."""

from datetime import datetime, timezone
import uuid

from sistema_luces.domain.error import ErrorDominio
from sistema_luces.domain.result import Resultado, exito, fallo
from sistema_luces.domain.state import (
    EstadoFeed,
    TransicionEstadoV1,
    es_transicion_valida,
)


class GestorEstadoFeed:
    """Controlador transaccional de estados del feed de mercado."""

    def __init__(self, estado_inicial: EstadoFeed = "INITIALIZING") -> None:
        self._estado_actual: EstadoFeed = estado_inicial

    @property
    def estado_actual(self) -> EstadoFeed:
        return self._estado_actual

    def transicionar(
        self,
        nuevo_estado: EstadoFeed,
        reason_code: str | None = None,
    ) -> Resultado[TransicionEstadoV1]:
        """Ejecuta y registra una transicion de estado si esta permitida por la maquina de estados."""
        if not es_transicion_valida("feed", self._estado_actual, nuevo_estado):
            return fallo(
                ErrorDominio(
                    codigo="VALIDATION_ERROR",
                    mensaje_seguro=f"Transicion invalida de feed: {self._estado_actual} -> {nuevo_estado}",
                    reintentable=False,
                    correlation_id="",
                    detalles={"desde": self._estado_actual, "hacia": nuevo_estado},
                )
            )

        transicion = TransicionEstadoV1(
            transition_id=str(uuid.uuid4()),
            aggregate_type="feed",
            aggregate_id="feed-main",
            previous_state=self._estado_actual,
            next_state=nuevo_estado,
            actor="system",
            occurred_at_utc=datetime.now(timezone.utc),
            causation_id=None,
            correlation_id=str(uuid.uuid4()),
            policy_version="1.0.0",
            reason_codes=(reason_code,) if reason_code else (),
            safety_forced=False,
        )
        self._estado_actual = nuevo_estado
        return exito(transicion)
