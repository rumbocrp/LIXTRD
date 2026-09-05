"""Máquina de estados e histéresis para luces (SPEC-001 §6.4, CA-8)."""

from datetime import datetime

from sistema_luces.domain.error import ErrorDominio
from sistema_luces.domain.result import Resultado, exito, fallo
from sistema_luces.domain.state import es_transicion_valida
from sistema_luces.domain.vocabulary import Light


class HisteresisLuces:
    """Gestiona la transición de estados de la luz asegurando el paso intermedio por YELLOW."""

    def __init__(
        self,
        threshold_green: int = 650_000,
        threshold_red: int = 350_000,
        initial_light: Light = "YELLOW",
    ) -> None:
        self.threshold_green = threshold_green
        self.threshold_red = threshold_red
        self._luz_actual: Light = initial_light

    @property
    def luz_actual(self) -> Light:
        return self._luz_actual

    def transicionar(
        self,
        target_light: Light,
        feed_health: str,
        timestamp_utc: datetime,
        correlation_id: str,
    ) -> Resultado[Light]:
        """Evalúa y aplica una transición de luz respetando el grafo de estados de §6.4."""
        # Si el feed está degradado, se fuerza invariablemente a YELLOW
        if feed_health != "HEALTHY":
            self._luz_actual = "YELLOW"
            return exito("YELLOW")

        # Comprobar si es el mismo estado
        if target_light == self._luz_actual:
            return exito(self._luz_actual)

        # Validar transición según grafo formal de estados (CA-8)
        if not es_transicion_valida("light", self._luz_actual, target_light):
            return fallo(
                ErrorDominio(
                    codigo="VALIDATION_ERROR",
                    mensaje_seguro=(
                        f"Transición directa de luz no permitida: {self._luz_actual} -> {target_light}. "
                        f"Debe pasar por YELLOW intermedio."
                    ),
                    reintentable=False,
                    correlation_id=correlation_id,
                    detalles={
                        "aggregate_type": "light",
                        "previous_state": self._luz_actual,
                        "next_state": target_light,
                    },
                )
            )

        self._luz_actual = target_light
        return exito(self._luz_actual)
