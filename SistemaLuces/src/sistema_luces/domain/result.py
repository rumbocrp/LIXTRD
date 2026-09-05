"""Resultado discriminado comun (SPEC-001 §5.1)."""

from dataclasses import dataclass
from typing import Generic, Literal, TypeAlias, TypeVar

from sistema_luces.domain.error import ErrorDominio

T = TypeVar("T")


@dataclass(frozen=True)
class Exito(Generic[T]):
    exito: Literal[True]
    datos: T


@dataclass(frozen=True)
class Fallo:
    exito: Literal[False]
    error: ErrorDominio


Resultado: TypeAlias = Exito[T] | Fallo


def exito(datos: T) -> Exito[T]:
    """Crea una instancia inmutable de Exito."""
    return Exito(exito=True, datos=datos)


def fallo(error: ErrorDominio) -> Fallo:
    """Crea una instancia inmutable de Fallo."""
    return Fallo(exito=False, error=error)
