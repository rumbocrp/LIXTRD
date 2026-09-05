"""Caso de uso importar_demo_observada (SPEC-001 §5.2, CA-19)."""

from sistema_luces.domain.api import ResumenImportacion, SolicitudImportacionDemo
from sistema_luces.domain.result import Resultado
from sistema_luces.imports.demo import ImportadorDemo
from sistema_luces.imports.reconciliation import ReconciliadorDemo
from sistema_luces.imports.staging import ValidadorStaging


class EjecutorImportacionDemo:
    """Orquesta la importación validada de copias staged y su reconciliación."""

    def __init__(
        self,
        validador_staging: ValidadorStaging | None = None,
        importador: ImportadorDemo | None = None,
        reconciliador: ReconciliadorDemo | None = None,
    ) -> None:
        self.validador_staging = validador_staging or ValidadorStaging()
        self.importador = importador or ImportadorDemo(validador_staging=self.validador_staging)
        self.reconciliador = reconciliador or ReconciliadorDemo()

    def ejecutar(self, solicitud: SolicitudImportacionDemo) -> Resultado[ResumenImportacion]:
        return self.importador.importar(solicitud)


def importar_demo_observada(solicitud: SolicitudImportacionDemo) -> Resultado[ResumenImportacion]:
    """Punto de entrada de caso de uso para importar ejecuciones de broker demo."""
    ejecutor = EjecutorImportacionDemo()
    return ejecutor.ejecutar(solicitud)
