"""Caso de uso Replay End-to-End Determinista (SPEC-001 §5.2, SPEC-002 §5, RF-L005, RF-L006, RF-L007, RF-L010, CA-5, CA-21, CA-23).

Orquesta la ejecución determinista de replay histórico sobre el corpus de eventos de mercado
a través de PipelineCompositionRoot, garantizando reproducibilidad estricta byte-a-byte.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time
from typing import Any, Literal
import uuid

from sistema_luces.application.composition_root import (
    PipelineCompositionRoot,
    ResumenPasoPipeline,
    crear_pipeline_replay,
    generar_uuid_determinista,
)
from sistema_luces.application.ports import SesionFuentePuerto
from sistema_luces.domain.api import (
    ProyeccionLecturaV1,
    ResumenEjecucion,
    SolicitudReplay,
    validar_resumen_ejecucion,
    validar_solicitud_replay,
)
from sistema_luces.domain.error import ErrorDominio
from sistema_luces.domain.event import SobreEventoV1
from sistema_luces.domain.manifest import CostProfileV1
from sistema_luces.domain.result import Resultado, exito, fallo
from sistema_luces.domain.vocabulary import Environment
from sistema_luces.sources.replay import FuenteReplay, ResumenFuente, SolicitudFuente
from sistema_luces.storage.event_store import ConsultaEventos, RangoEventos


def _format_iso_utc(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    utc_dt = dt.astimezone(timezone.utc)
    if utc_dt.microsecond > 0:
        return utc_dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    return utc_dt.strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass(frozen=True)
class ConfiguracionReplay:
    """Configuración inmutable para la ejecución de Replay determinista."""

    correlation_id: str = ""
    environment: Literal["REPLAY"] = "REPLAY"
    dataset_manifest_hash: str = "0" * 64
    range_start_utc: datetime = field(
        default_factory=lambda: datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    )
    range_end_utc: datetime = field(
        default_factory=lambda: datetime(2026, 12, 31, 23, 59, 59, tzinfo=timezone.utc)
    )
    clock_seed: int = 20260829
    db_path: str | Path | None = None
    model_id_campeon: str | None = None
    policy_version: str = "policy-us500-v1"
    feature_set_version: str = "features-v1"
    price_scale: int = 100
    cost_profile: CostProfileV1 | None = None
    dataset: Sequence[SobreEventoV1] | None = None
    event_cutoff_utc: datetime | None = None


@dataclass(frozen=True)
class ResultadoEjecucionReplay:
    """Resultado estructurado de la ejecución de Replay determinista (RF-L010, CA-5)."""

    session_id: str
    environment: Literal["REPLAY"]
    events_processed: int
    ticks_ingested: int
    cases_generated: int
    signals_emitted: int
    transitions_recorded: int
    simulations_opened: int
    simulations_closed: int
    final_projection: ProyeccionLecturaV1
    final_hash: str
    duration_ms: float

    @property
    def run_id(self) -> str:
        """Alias para compatibilidad con ResumenEjecucion."""
        return self.session_id

    @property
    def accepted_event_count(self) -> int:
        """Alias para compatibilidad con ResumenEjecucion."""
        return self.events_processed

    @property
    def rejected_event_count(self) -> int:
        """Alias para compatibilidad con ResumenEjecucion."""
        return 0

    @property
    def emitted_signal_count(self) -> int:
        """Alias para compatibilidad con ResumenEjecucion."""
        return self.signals_emitted

    @property
    def opened_simulation_count(self) -> int:
        """Alias para compatibilidad con ResumenEjecucion."""
        return self.simulations_opened

    @property
    def final_event_cutoff(self) -> str | None:
        """Alias para compatibilidad con ResumenEjecucion."""
        return _format_iso_utc(self.final_projection.market_cutoff_utc)

    @property
    def reason_codes(self) -> tuple[str, ...]:
        """Alias para compatibilidad con ResumenEjecucion."""
        return self.final_projection.reason_codes

    @property
    def resumen(self) -> ResumenEjecucion:
        """Emite el DTO canónico ResumenEjecucion."""
        return ResumenEjecucion(
            run_id=self.session_id,
            environment="REPLAY",
            final_event_cutoff=self.final_event_cutoff,
            accepted_event_count=self.events_processed,
            rejected_event_count=0,
            emitted_signal_count=self.signals_emitted,
            opened_simulation_count=self.simulations_opened,
            reason_codes=self.reason_codes,
        )

    def to_dict(self, include_timing: bool = True) -> dict[str, Any]:
        """Serializa el resultado a diccionario canónico."""
        data: dict[str, Any] = {
            "session_id": self.session_id,
            "environment": self.environment,
            "events_processed": self.events_processed,
            "ticks_ingested": self.ticks_ingested,
            "cases_generated": self.cases_generated,
            "signals_emitted": self.signals_emitted,
            "transitions_recorded": self.transitions_recorded,
            "simulations_opened": self.simulations_opened,
            "simulations_closed": self.simulations_closed,
            "final_projection": self.final_projection.to_dict(),
            "final_hash": self.final_hash,
        }
        if include_timing:
            data["duration_ms"] = self.duration_ms
        return data

    def to_canonical_json(self) -> str:
        """Serializa a JSON canónico ordenado y determinista (sin ruido de reloj CPU)."""
        return json.dumps(
            self.to_dict(include_timing=False),
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
            ensure_ascii=False,
        )

    def to_canonical_bytes(self) -> bytes:
        """Serializa a bytes UTF-8 del JSON canónico."""
        return self.to_canonical_json().encode("utf-8")


class ReplayUseCase:
    """Orquesta la ejecución determinista de replay histórico sobre el corpus de eventos.

    Utiliza PipelineCompositionRoot para garantizar determinismo estricto byte-a-byte,
    evaluación causal de casos S30/S60, e integridad en el hash chain de SQLite WAL.
    """

    def __init__(
        self,
        pipeline: PipelineCompositionRoot | None = None,
        db_path: str | Path | None = None,
        model_id_campeon: str | None = None,
        clock_seed: int = 20260829,
        policy_version: str = "policy-us500-v1",
        price_scale: int = 100,
        cost_profile: CostProfileV1 | None = None,
    ) -> None:
        if pipeline is not None:
            self._pipeline = pipeline
        else:
            self._pipeline = crear_pipeline_replay(
                db_path=db_path,
                model_id_campeon=model_id_campeon,
                clock_seed=clock_seed,
                policy_version=policy_version,
            )
            if cost_profile is not None:
                self._pipeline.cost_profile = cost_profile
            self._pipeline.price_scale = price_scale

        self._eventos_cargados: list[SobreEventoV1] = []

    @property
    def pipeline(self) -> PipelineCompositionRoot:
        """Acceso al orquestador PipelineCompositionRoot subyacente."""
        return self._pipeline

    def cargar_eventos_replay(self, eventos: Sequence[SobreEventoV1]) -> None:
        """Carga en memoria un corpus de eventos para replay."""
        self._eventos_cargados = list(eventos)

    def cargar_eventos(self, eventos: Sequence[SobreEventoV1]) -> None:
        """Alias para cargar_eventos_replay."""
        self.cargar_eventos_replay(eventos)

    def ejecutar(
        self,
        solicitud: SolicitudReplay | ConfiguracionReplay | None = None,
        dataset: Sequence[SobreEventoV1] | None = None,
    ) -> Resultado[ResultadoEjecucionReplay]:
        """Ejecuta el pipeline de replay secuencial y determinísticamente."""
        t_start = time.perf_counter()

        # 1. Normalizar y validar solicitud
        cid: str
        range_start: datetime
        range_end: datetime
        clk_seed: int
        cutoff_utc: datetime | None = None

        if isinstance(solicitud, SolicitudReplay):
            val_sol = validar_solicitud_replay(solicitud)
            if not val_sol.exito:
                return fallo(val_sol.error)
            cid = solicitud.correlation_id
            range_start = solicitud.range_start_utc
            range_end = solicitud.range_end_utc
            clk_seed = solicitud.clock_seed
        elif isinstance(solicitud, ConfiguracionReplay):
            cid = solicitud.correlation_id or generar_uuid_determinista(
                "replay-session", "CONFIG", f"{solicitud.range_start_utc.isoformat()}:{solicitud.clock_seed}"
            )
            range_start = solicitud.range_start_utc
            range_end = solicitud.range_end_utc
            clk_seed = solicitud.clock_seed
            cutoff_utc = solicitud.event_cutoff_utc
        else:
            cid = generar_uuid_determinista("replay-session", "DEFAULT", "seed:20260829")
            range_start = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
            range_end = datetime(2026, 12, 31, 23, 59, 59, tzinfo=timezone.utc)
            clk_seed = 20260829

        # 2. Determinar dataset a reproducir
        dataset_efectivo: list[SobreEventoV1]
        if dataset is not None:
            dataset_efectivo = list(dataset)
        elif self._eventos_cargados:
            dataset_efectivo = list(self._eventos_cargados)
        elif isinstance(solicitud, ConfiguracionReplay) and solicitud.dataset is not None:
            dataset_efectivo = list(solicitud.dataset)
        else:
            dataset_efectivo = []

        # 3. Configurar fuente y abrir sesión
        sol_fuente = SolicitudFuente(
            correlation_id=cid,
            environment="REPLAY",
            source_profile_version="replay-v1",
            instrument=self._pipeline.instrument,
            range_start_utc=range_start,
            range_end_utc=range_end,
            clock_seed=clk_seed,
            event_cutoff_utc=cutoff_utc,
        )

        fuente = self._pipeline.fuente or FuenteReplay()
        res_sesion = fuente.abrir(sol_fuente, dataset=dataset_efectivo)
        if not res_sesion.exito:
            return fallo(res_sesion.error)
        sesion: SesionFuentePuerto = res_sesion.datos

        # 4. Procesar eventos secuencialmente a través del Composition Root
        events_processed = 0
        ticks_ingested = 0
        cases_generated = 0
        signals_emitted = 0
        transitions_recorded = 0
        simulations_opened = 0
        simulations_closed = 0
        last_event_hash = ""

        for res_ev in sesion.eventos_sync():
            if not res_ev.exito:
                return fallo(res_ev.error)
            evento = res_ev.datos
            events_processed += 1
            if evento.event_type == "QUOTE_TICK":
                ticks_ingested += 1

            res_paso = self._pipeline.procesar_evento(evento)
            if not res_paso.exito:
                return fallo(res_paso.error)
            paso: ResumenPasoPipeline = res_paso.datos

            if paso.case_generated is not None:
                cases_generated += 1
            if paso.signal_emitted is not None:
                signals_emitted += 1
            if paso.transition_emitted is not None:
                transitions_recorded += 1
            if paso.simulation_opened is not None:
                simulations_opened += 1
            simulations_closed += len(paso.simulations_closed)

        # Cerrar sesión de fuente
        sesion.cerrar()

        # 5. Obtener Proyección de Lectura V1 final
        res_proy = self._pipeline.obtener_proyeccion_v1()
        if not res_proy.exito:
            return fallo(res_proy.error)
        final_projection = res_proy.datos

        # 6. Obtener final_hash (hash del último evento en el almacén o root_hash)
        res_integ = self._pipeline.almacen.verificar_integridad(RangoEventos())
        if res_integ.exito and res_integ.datos.event_count > 0:
            final_hash = res_integ.datos.root_hash
        else:
            final_hash = hashlib.sha256(b"").hexdigest()

        duration_ms = max(0.0, (time.perf_counter() - t_start) * 1000.0)

        resultado = ResultadoEjecucionReplay(
            session_id=cid,
            environment="REPLAY",
            events_processed=events_processed,
            ticks_ingested=ticks_ingested,
            cases_generated=cases_generated,
            signals_emitted=signals_emitted,
            transitions_recorded=transitions_recorded,
            simulations_opened=simulations_opened,
            simulations_closed=simulations_closed,
            final_projection=final_projection,
            final_hash=final_hash,
            duration_ms=duration_ms,
        )

        return exito(resultado)


# Alias para compatibilidad con código existente
EjecutorReplay = ReplayUseCase


def ejecutar_replay(
    solicitud: SolicitudReplay,
    dataset: Sequence[SobreEventoV1] | None = None,
    pipeline: PipelineCompositionRoot | None = None,
) -> Resultado[ResultadoEjecucionReplay]:
    """Punto de entrada funcional del caso de uso ejecutar_replay."""
    ejecutor = ReplayUseCase(pipeline=pipeline)
    return ejecutor.ejecutar(solicitud, dataset=dataset)


__all__ = [
    "ConfiguracionReplay",
    "ResultadoEjecucionReplay",
    "ReplayUseCase",
    "EjecutorReplay",
    "ejecutar_replay",
]
