"""Módulo de simulación paper y evaluación de ciclo de vida (SPEC-001 §5.3, §6.6, CA-12, CA-15)."""

from sistema_luces.simulation.lifecycle import EvaluadorTripleBarrera
from sistema_luces.simulation.paper import SimuladorPapel

__all__ = [
    "EvaluadorTripleBarrera",
    "SimuladorPapel",
]
