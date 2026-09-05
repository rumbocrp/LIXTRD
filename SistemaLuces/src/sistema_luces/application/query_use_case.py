"""Caso de uso consultar_vista (SPEC-001 §5.2)."""

from sistema_luces.domain.api import SolicitudConsulta, VistaLectura
from sistema_luces.domain.result import Resultado
from sistema_luces.observability.projections import ProyectorVistas


class ConsultorVistas:
    """Orquesta la consulta de proyecciones y vistas inmutables."""

    def __init__(self, proyector: ProyectorVistas | None = None) -> None:
        self.proyector = proyector or ProyectorVistas()

    def consultar(self, solicitud: SolicitudConsulta) -> Resultado[VistaLectura]:
        return self.proyector.consultar(solicitud)


def consultar_vista(solicitud: SolicitudConsulta) -> Resultado[VistaLectura]:
    """Punto de entrada de caso de uso para consultar vistas del sistema."""
    consultor = ConsultorVistas()
    return consultor.consultar(solicitud)
