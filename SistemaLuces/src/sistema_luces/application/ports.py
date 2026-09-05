"""Definición de Puertos Hexagonales del Sistema (SPEC-002 §5, ARQUITECTURA.md §2, RF-L010, RF-L011, RNF-L003).

Este módulo define formalmente los 8 contratos de puertos de la arquitectura hexagonal
mediante protocolos verificables en tiempo de ejecución (@runtime_checkable Protocol).
"""

from collections.abc import Iterator, Mapping, Sequence
from datetime import datetime
from typing import Any, Protocol, runtime_checkable

from sistema_luces.cases.builder import CasoV1, SolicitudCaso
from sistema_luces.domain.api import ProyeccionLecturaV1, SolicitudConsulta, VistaLectura
from sistema_luces.domain.event import QuoteTickPayloadV1, SobreEventoV1
from sistema_luces.domain.result import Resultado
from sistema_luces.domain.signal import SenalV1
from sistema_luces.domain.simulation import SimulacionV1
from sistema_luces.domain.state import TransicionEstadoV1
from sistema_luces.domain.vocabulary import Light
from sistema_luces.models.baseline import ModeloPredictivoV1
from sistema_luces.policy.lights import DecisionLuzV1, SolicitudLuz
from sistema_luces.sources.clock import RelojDominio
from sistema_luces.sources.replay import ResumenFuente, SolicitudFuente
from sistema_luces.storage.event_store import (
    ConsultaEventos,
    InformeIntegridad,
    LoteEventosV1,
    PaginaEventos,
    RangoEventos,
    ReciboEvento,
    ReciboLote,
)


@runtime_checkable
class SesionFuentePuerto(Protocol):
    """Puerto de sesión de ingesta de eventos."""

    @property
    def reloj(self) -> RelojDominio:
        """Reloj de dominio sincronizado con la sesión."""
        ...

    def paso(self) -> Resultado[SobreEventoV1 | None]:
        """Avanza un paso en la emisión de eventos."""
        ...

    def eventos_sync(self) -> Iterator[Resultado[SobreEventoV1]]:
        """Generador sincrónico de eventos hasta agotar el dataset o flujo."""
        ...

    def esta_pausada(self) -> bool:
        """Indica si la sesión se encuentra pausada."""
        ...

    def pausar(self) -> None:
        """Pausa la emisión de eventos."""
        ...

    def reanudar(self) -> None:
        """Reanuda la emisión de eventos."""
        ...

    def cerrar(self) -> Resultado[ResumenFuente]:
        """Cierra la sesión y emite el resumen final."""
        ...


@runtime_checkable
class FuentePuerto(Protocol):
    """Puerto 1: Ingesta de datos de mercado (Replay / Shadow / Demo)."""

    def abrir(
        self,
        solicitud: SolicitudFuente,
        dataset: Sequence[SobreEventoV1] | None = None,
    ) -> Resultado[SesionFuentePuerto]:
        """Abre una nueva sesión de datos validando entorno e inicializando reloj."""
        ...


@runtime_checkable
class AlmacenPuerto(Protocol):
    """Puerto 2: Almacén append-only inmutable de eventos con encadenamiento de hashes."""

    def anexar(self, evento: SobreEventoV1) -> Resultado[ReciboEvento]:
        """Anexa un sobre de evento validando integridad criptográfica e idempotencia."""
        ...

    def anexar_lote(self, lote: LoteEventosV1) -> Resultado[ReciboLote]:
        """Anexa un lote de eventos atómicamente en una sola transacción."""
        ...

    def leer(self, consulta: ConsultaEventos) -> Resultado[PaginaEventos]:
        """Consulta eventos persistidos con paginación y filtros temporales."""
        ...

    def verificar_integridad(self, rango: RangoEventos) -> Resultado[InformeIntegridad]:
        """Verifica la cadena de hashes SHA-256 e integridad del payload."""
        ...

    def reconstruir_proyecciones(self) -> Resultado[dict[str, int]]:
        """Reconstruye el conteo y resumen base desde el log inmutable."""
        ...


@runtime_checkable
class EvaluadorSaludFeedPuerto(Protocol):
    """Puerto 3: Monitor y evaluador de calidad y salud del feed de datos."""

    @property
    def feed_state(self) -> str:
        """Estado actual de salud del feed ('HEALTHY', 'STALE', 'GAPPED', etc.)."""
        ...

    def evaluar_evento(
        self,
        evento: SobreEventoV1,
        reloj: RelojDominio,
    ) -> tuple[str, list[SobreEventoV1]]:
        """Evalúa un evento entrante y retorna el estado de salud y alertas de anomalía."""
        ...


@runtime_checkable
class GeneradorCasosPuerto(Protocol):
    """Puerto 4: Constructor de snapshots causales de características (S30/S60)."""

    def construir(
        self,
        solicitud: SolicitudCaso,
        buffer_eventos: Sequence[SobreEventoV1] | None = None,
    ) -> Resultado[CasoV1]:
        """Construye un CasoV1 inmutable respetando causalidad estricta y OPT-7."""
        ...


@runtime_checkable
class RegistroModelosPuerto(Protocol):
    """Puerto 5: Registro inmutable de modelos y evaluador de inferencia/calibración."""

    def obtener(self, modelo_id_o_hash: str) -> Resultado[ModeloPredictivoV1]:
        """Obtiene un modelo por su ID o hash SHA-256."""
        ...

    def predecir_calibrado_par(
        self,
        modelo_id: str,
        caso: CasoV1,
    ) -> Resultado[tuple[int, int]]:
        """Calcula probabilidades calibradas LONG y SHORT en escala 0..1_000_000."""
        ...

    def predecir_calibrado(
        self,
        modelo_id: str,
        caso: CasoV1,
    ) -> Resultado[int]:
        """Calcula la probabilidad calibrada LONG en escala 0..1_000_000."""
        ...

    def listar(self) -> Resultado[list[str]]:
        """Lista todos los identificadores de modelos registrados."""
        ...


@runtime_checkable
class MotorPoliticaLucesPuerto(Protocol):
    """Puerto 6: Motor de política de decisión de luces con histéresis y amarillo seguro."""

    def decidir(self, solicitud: SolicitudLuz) -> Resultado[DecisionLuzV1]:
        """Evalúa un caso maduro y emite SenalV1 y TransicionEstadoV1."""
        ...


@runtime_checkable
class MotorSimulacionPuerto(Protocol):
    """Puerto 7: Motor de simulación en papel interna con triple barrera sin broker."""

    def proponer_y_abrir(
        self,
        senal: SenalV1,
        current_bid: int,
        current_ask: int,
        now_utc: datetime,
        quantity: int = 100,
    ) -> Resultado[SimulacionV1]:
        """Procesa una señal activa y abre una posición simulada."""
        ...

    def avanzar_tick(
        self,
        simulation_id: str,
        tick: QuoteTickPayloadV1,
        now_utc: datetime,
    ) -> Resultado[SimulacionV1]:
        """Avanza la simulación con un nuevo tick y ejecuta salidas si aplica."""
        ...


@runtime_checkable
class ProyectorVistasPuerto(Protocol):
    """Puerto 8: Proyector reactivo de vistas de lectura y documentos V1."""

    def actualizar_desde_evento(self, evento: SobreEventoV1) -> Resultado[None]:
        """Aplica un evento atómico a las proyecciones correspondientes."""
        ...

    def consultar(self, solicitud: SolicitudConsulta) -> Resultado[VistaLectura]:
        """Genera una VistaLectura inmutable a partir de documentos proyectados."""
        ...

    def reconstruir(self, eventos: list[SobreEventoV1]) -> Resultado[dict[str, int]]:
        """Reconstruye todas las vistas desde cero procesando la secuencia de eventos."""
        ...


__all__ = [
    "SesionFuentePuerto",
    "FuentePuerto",
    "AlmacenPuerto",
    "EvaluadorSaludFeedPuerto",
    "GeneradorCasosPuerto",
    "RegistroModelosPuerto",
    "MotorPoliticaLucesPuerto",
    "MotorSimulacionPuerto",
    "ProyectorVistasPuerto",
]
