"""Árbol causal de trazabilidad y linaje de eventos (SPEC-001 §6.2, CA-23)."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class NodoTraza:
    node_id: str
    node_type: str
    correlation_id: str
    causation_id: str | None
    timestamp_utc: datetime
    details: dict[str, Any]


class ArbolTrazabilidad:
    """Registra y navega el linaje causal de eventos, casos, señales y simulaciones."""

    def __init__(self) -> None:
        self._nodos: dict[str, NodoTraza] = {}

    def registrar_nodo(self, nodo: NodoTraza) -> None:
        self._nodos[nodo.node_id] = nodo

    def obtener_nodo(self, node_id: str) -> NodoTraza | None:
        return self._nodos.get(node_id)

    def obtener_linaje_ascendente(self, node_id: str) -> list[NodoTraza]:
        """Recorre hacia atrás desde el nodo consultado hasta el evento raíz."""
        linaje: list[NodoTraza] = []
        curr_id: str | None = node_id

        while curr_id and curr_id in self._nodos:
            nodo = self._nodos[curr_id]
            linaje.append(nodo)
            curr_id = nodo.causation_id

        return linaje
