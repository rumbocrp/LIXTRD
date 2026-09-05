"""Caso de uso ejecutar_shadow y orquestador ShadowUseCase (SPEC-001 §5.2, RF-L011, RNF-L001, RNF-L002, RNF-L011).

Este módulo implementa el orquestador de ejecución en modo Shadow/Sintético (ShadowUseCase)
utilizando exactamente el mismo PipelineCompositionRoot unificado que Replay, sin ninguna
bifurcación lógica en el motor de decisión, conectando con fuentes read-only etiquetadas
explícitamente como SHADOW o SINTETICO.
"""

from collections import deque
from collections.abc import AsyncIterator, Iterator, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
import tempfile
from typing import Any, Literal
import uuid

from sistema_luces.application.composition_root import (
    PipelineCompositionRoot,
    ResumenPasoPipeline,
    crear_pipeline_shadow,
    generar_uuid_determinista,
)
from sistema_luces.application.ports import (
    AlmacenPuerto,
    EvaluadorSaludFeedPuerto,
    FuentePuerto,
    GeneradorCasosPuerto,
    MotorPoliticaLucesPuerto,
    MotorSimulacionPuerto,
    ProyectorVistasPuerto,
    RegistroModelosPuerto,
    SesionFuentePuerto,
)
from sistema_luces.domain.api import (
    ProyeccionLecturaV1,
    ResumenEjecucion,
    SolicitudConsulta,
    SolicitudShadow,
    VistaLectura,
    validar_proyeccion_lectura_v1,
    validar_resumen_ejecucion,
    validar_solicitud_shadow,
)
from sistema_luces.domain.error import ErrorDominio
from sistema_luces.domain.event import (
    QuoteTickPayloadV1,
    SobreEventoV1,
    compute_payload_hash,
    validar_sobre_evento,
)
from sistema_luces.domain.result import Resultado, exito, fallo
from sistema_luces.domain.state import TransicionEstadoV1
from sistema_luces.domain.vocabulary import (
    DIRECCIONES_CANONICAS_PERMITIDAS,
    MAPEO_LUZ_A_DIRECCION_CANONICA,
    DireccionCanonica,
    Environment,
    Light,
    parse_environment,
)
from sistema_luces.sources.clock import RelojDominio
from sistema_luces.sources.ctrader_demo import (
    AdaptadorCTraderDemoReadOnly,
    MetadatosCuentaCTrader,
    SesionCTraderDemo,
    SolicitudConexionCTrader,
)
from sistema_luces.sources.replay import ResumenFuente, SolicitudFuente


class SesionShadowFake:
    """Sesión de fuente sintética / streaming para entorno SHADOW con reloj de dominio dinámico."""

    def __init__(
        self,
        solicitud: SolicitudFuente,
        dataset: Sequence[SobreEventoV1] | None = None,
        reloj: RelojDominio | None = None,
        tiempo_inicial_utc: datetime | None = None,
        max_queue_size: int = 5000,
    ) -> None:
        self.solicitud = solicitud
        if reloj is not None:
            self._reloj = reloj
        elif tiempo_inicial_utc is not None:
            self._reloj = RelojDominio(
                tiempo_inicial=tiempo_inicial_utc,
                clock_seed=solicitud.clock_seed,
            )
        elif solicitud.range_start_utc is not None:
            self._reloj = RelojDominio(
                tiempo_inicial=solicitud.range_start_utc,
                clock_seed=solicitud.clock_seed,
            )
        elif dataset and len(dataset) > 0:
            self._reloj = RelojDominio(
                tiempo_inicial=dataset[0].occurred_at_utc,
                clock_seed=solicitud.clock_seed,
            )
        else:
            self._reloj = RelojDominio(
                tiempo_inicial=datetime.now(timezone.utc),
                clock_seed=solicitud.clock_seed,
            )
        self.max_queue_size = max_queue_size
        self._cola: deque[SobreEventoV1] = deque(maxlen=self.max_queue_size)
        self._recibidos: int = 0
        self._descartados: int = 0
        self._pausada: bool = False
        self._cerrada: bool = False
        self._last_cutoff_utc: datetime | None = None

        if dataset:
            for ev in dataset:
                self._cola.append(ev)
                self._recibidos += 1
                self._last_cutoff_utc = ev.occurred_at_utc

    @property
    def reloj(self) -> RelojDominio:
        return self._reloj

    def esta_pausada(self) -> bool:
        return self._pausada

    def pausar(self) -> None:
        self._pausada = True

    def reanudar(self) -> None:
        self._pausada = False

    def inyectar_evento(self, evento: SobreEventoV1) -> Resultado[SobreEventoV1]:
        """Inyecta un evento validado en la cola de streaming."""
        if self._cerrada:
            return fallo(
                ErrorDominio(
                    codigo="VALIDATION_ERROR",
                    mensaje_seguro="La sesión de shadow streaming se encuentra cerrada",
                    reintentable=False,
                    correlation_id=self.solicitud.correlation_id,
                    detalles={},
                )
            )

        if len(self._cola) >= self.max_queue_size:
            self._descartados += 1

        self._cola.append(evento)
        self._recibidos += 1
        self._last_cutoff_utc = evento.occurred_at_utc
        return exito(evento)

    def inyectar_tick(
        self,
        bid: int,
        ask: int,
        occurred_at_utc: datetime | None = None,
        seq: int | None = None,
        price_scale: int = 100,
        bid_size: int = 10,
        ask_size: int = 10,
        correlation_id: str = "",
    ) -> Resultado[SobreEventoV1]:
        """Construye e inyecta un QuoteTickPayloadV1 en la cola de shadow streaming."""
        cid = correlation_id or self.solicitud.correlation_id or str(uuid.uuid4())
        ts = occurred_at_utc or self._reloj.ahora_utc()
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)

        payload = {
            "bid": bid,
            "ask": ask,
            "price_scale": price_scale,
            "bid_size": bid_size,
            "ask_size": ask_size,
            "source_timestamp_utc": ts.isoformat(),
            "source_sequence": seq,
        }
        eid = generar_uuid_determinista(cid, "SHADOW_TICK", f"{seq}:{ts.isoformat()}")

        evento = SobreEventoV1(
            event_id=eid,
            event_type="QUOTE_TICK",
            schema_version=1,
            occurred_at_utc=ts,
            received_at_utc=ts,
            persisted_at_utc=None,
            source="ctrader_demo",
            environment=self.solicitud.environment,  # type: ignore[arg-type]
            source_account_id_hash=None,
            instrument="US500",
            symbol_id="US500",
            source_sequence=seq,
            payload_hash=compute_payload_hash(payload),
            previous_hash=None,
            causation_id=None,
            correlation_id=cid,
            payload=payload,
        )

        res_val = validar_sobre_evento(evento)
        if not res_val.exito:
            return fallo(res_val.error)

        return self.inyectar_evento(evento)

    def paso(self) -> Resultado[SobreEventoV1 | None]:
        """Avanza un evento en la sesión sincronizando el reloj de streaming."""
        if self._pausada or not self._cola:
            return exito(None)

        ev = self._cola.popleft()
        try:
            self._reloj.avanzar_hasta(ev.occurred_at_utc)
        except ValueError:
            pass
        return exito(ev)

    def eventos_sync(self) -> Iterator[Resultado[SobreEventoV1]]:
        while self._cola:
            if self._pausada:
                break
            res = self.paso()
            if not res.exito:
                yield res
                break
            if res.datos is not None:
                yield exito(res.datos)

    async def eventos(self) -> AsyncIterator[Resultado[SobreEventoV1]]:
        for item in self.eventos_sync():
            yield item

    def cerrar(self) -> Resultado[ResumenFuente]:
        self._cerrada = True
        return exito(
            ResumenFuente(
                session_id=self.solicitud.correlation_id,
                final_cutoff_utc=self._last_cutoff_utc or self._reloj.ahora_utc(),
                total_received=self._recibidos,
                total_rejected=self._descartados,
                reason_codes=(),
            )
        )


class FuenteShadowFake:
    """Adaptador de fuente fake explícita para pruebas e integración en entorno SHADOW (RF-L011).

    Garantiza etiquetado estricto como SHADOW o SINTETICO y rechaza cualquier entorno no autorizado.
    """

    def __init__(self, default_clock_seed: int = 20260830) -> None:
        self.default_clock_seed = default_clock_seed

    def abrir(
        self,
        solicitud: SolicitudFuente,
        dataset: Sequence[SobreEventoV1] | None = None,
        reloj: RelojDominio | None = None,
        tiempo_inicial_utc: datetime | None = None,
    ) -> Resultado[SesionShadowFake]:
        """Abre una nueva sesión de shadow streaming validando procedencia y entorno."""
        # Validar entorno: solo se permite SHADOW o SINTETICO
        if solicitud.environment not in {"SHADOW", "SINTETICO"}:
            return fallo(
                ErrorDominio(
                    codigo="ENVIRONMENT_NOT_ALLOWED",
                    mensaje_seguro=f"FuenteShadowFake rechaza el entorno '{solicitud.environment}'. Solo se permite SHADOW o SINTETICO.",
                    reintentable=False,
                    correlation_id=solicitud.correlation_id,
                    detalles={"environment": str(solicitud.environment)},
                )
            )

        env_res = parse_environment(solicitud.environment, solicitud.correlation_id)
        if not env_res.exito:
            return fallo(env_res.error)

        sesion = SesionShadowFake(
            solicitud=solicitud,
            dataset=dataset,
            reloj=reloj,
            tiempo_inicial_utc=tiempo_inicial_utc,
        )
        return exito(sesion)


@dataclass(frozen=True)
class ResumenEjecucionShadow:
    """Resumen enriquecido de ejecución en modo Shadow."""

    run_id: str
    environment: Literal["SHADOW", "SINTETICO"]
    final_event_cutoff: str | None
    accepted_event_count: int
    rejected_event_count: int
    emitted_signal_count: int
    opened_simulation_count: int
    closed_simulation_count: int
    alerts_count: int
    current_light: Light
    current_direction: DireccionCanonica
    current_health_state: str
    proyeccion: ProyeccionLecturaV1 | None = None
    reason_codes: tuple[str, ...] = ()

    def to_resumen_ejecucion(self) -> ResumenEjecucion:
        """Convierte a ResumenEjecucion estándar de la API de dominio."""
        return ResumenEjecucion(
            run_id=self.run_id,
            environment="SHADOW",
            final_event_cutoff=self.final_event_cutoff,
            accepted_event_count=self.accepted_event_count,
            rejected_event_count=self.rejected_event_count,
            emitted_signal_count=self.emitted_signal_count,
            opened_simulation_count=self.opened_simulation_count,
            reason_codes=(),
        )


class ShadowUseCase:
    """Caso de Uso de Monitoreo y Decisión en Modo Shadow (SPEC-001 §5.2, RF-L011, RNF-L001, RNF-L002, RNF-L011).

    Orquesta la ejecución paso a paso o por flujo conectando fuentes read-only (FuenteShadowFake
    o AdaptadorCTraderDemoReadOnly) con el PipelineCompositionRoot unificado.
    """

    def __init__(
        self,
        pipeline: PipelineCompositionRoot | None = None,
        db_path: str | Path | None = None,
        model_id_campeon: str | None = None,
        policy_version: str = "policy-us500-v1",
        fuente: FuentePuerto | None = None,
        environment: Environment = "SHADOW",
        reloj: RelojDominio | None = None,
        tiempo_inicial_utc: datetime | None = None,
        clock_seed: int = 20260830,
    ) -> None:
        if environment not in {"SHADOW", "SINTETICO"}:
            raise ValueError(f"ShadowUseCase solo admite entorno SHADOW o SINTETICO, recibido: {environment}")

        self.environment: Literal["SHADOW", "SINTETICO"] = "SHADOW" if environment == "SHADOW" else "SINTETICO"
        self._pipeline = pipeline or crear_pipeline_shadow(
            db_path=db_path,
            model_id_campeon=model_id_campeon,
            policy_version=policy_version,
            reloj=reloj,
            tiempo_inicial_utc=tiempo_inicial_utc,
            clock_seed=clock_seed,
        )
        self._fuente = fuente or FuenteShadowFake(default_clock_seed=clock_seed)
        self._sesion_activa: SesionFuentePuerto | None = None
        self._eventos_rechazados: int = 0
        self._alertas_totales: int = 0
        self._simulaciones_cerradas_count: int = 0

    @property
    def pipeline(self) -> PipelineCompositionRoot:
        return self._pipeline

    @property
    def fuente(self) -> FuentePuerto:
        return self._fuente

    @property
    def sesion_activa(self) -> SesionFuentePuerto | None:
        return self._sesion_activa

    @property
    def current_light(self) -> Light:
        return self._pipeline.current_light

    @property
    def health_state(self) -> str:
        return self._pipeline.health_state

    @property
    def kill_switch_active(self) -> bool:
        return self._pipeline.kill_switch_active

    def inicializar_sesion(
        self,
        solicitud: SolicitudFuente | SolicitudShadow | None = None,
        dataset: Sequence[SobreEventoV1] | None = None,
        reloj: RelojDominio | None = None,
        tiempo_inicial_utc: datetime | None = None,
    ) -> Resultado[SesionFuentePuerto]:
        """Abre y asocia una sesión de streaming con el adaptador de fuente."""
        cid = getattr(solicitud, "correlation_id", str(uuid.uuid4()))
        env = getattr(solicitud, "environment", self.environment)
        if env not in {"SHADOW", "SINTETICO"}:
            return fallo(
                ErrorDominio(
                    codigo="ENVIRONMENT_NOT_ALLOWED",
                    mensaje_seguro=f"Entorno no permitido para ShadowUseCase: {env}",
                    reintentable=False,
                    correlation_id=cid,
                    detalles={"environment": str(env)},
                )
            )

        range_start = getattr(solicitud, "range_start_utc", None)
        if range_start is None:
            if tiempo_inicial_utc is not None:
                range_start = tiempo_inicial_utc
            elif self._pipeline.reloj is not None:
                range_start = self._pipeline.reloj.ahora_utc()
            elif dataset and len(dataset) > 0:
                range_start = dataset[0].occurred_at_utc
            else:
                range_start = datetime.now(timezone.utc)

        range_end = getattr(solicitud, "range_end_utc", None)
        if range_end is None:
            range_end = range_start

        sol_fuente = SolicitudFuente(
            correlation_id=cid,
            environment="SHADOW",
            source_profile_version=getattr(solicitud, "source_profile_version", "fake-shadow-v1"),
            instrument="US500",
            range_start_utc=range_start,
            range_end_utc=range_end,
            clock_seed=getattr(solicitud, "clock_seed", 20260830),
        )

        reloj_sesion = reloj or self._pipeline.reloj
        if isinstance(self._fuente, FuenteShadowFake):
            res_ses = self._fuente.abrir(
                solicitud=sol_fuente,
                dataset=dataset,
                reloj=reloj_sesion,
                tiempo_inicial_utc=tiempo_inicial_utc,
            )
        else:
            res_ses = self._fuente.abrir(solicitud=sol_fuente, dataset=dataset)

        if not res_ses.exito:
            return fallo(res_ses.error)

        self._sesion_activa = res_ses.datos
        return exito(self._sesion_activa)

    def procesar_evento(self, evento: SobreEventoV1) -> Resultado[ResumenPasoPipeline]:
        """Procesa un SobreEventoV1 a través del Composition Root."""
        res_paso = self._pipeline.procesar_evento(evento)
        if not res_paso.exito:
            self._eventos_rechazados += 1
            return fallo(res_paso.error)

        paso = res_paso.datos
        if paso.alerts_generated:
            self._alertas_totales += len(paso.alerts_generated)
        if paso.simulations_closed:
            self._simulaciones_cerradas_count += len(paso.simulations_closed)

        return exito(paso)

    def procesar_tick(
        self,
        bid: int,
        ask: int,
        occurred_at_utc: datetime | None = None,
        seq: int | None = None,
        price_scale: int = 100,
        bid_size: int = 10,
        ask_size: int = 10,
        correlation_id: str = "",
    ) -> Resultado[ResumenPasoPipeline]:
        """Construye y procesa un tick en tiempo real dentro del pipeline."""
        cid = correlation_id or str(uuid.uuid4())
        ts = occurred_at_utc or (self._pipeline.reloj.ahora_utc() if self._pipeline.reloj else datetime.now(timezone.utc))
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)

        payload = {
            "bid": bid,
            "ask": ask,
            "price_scale": price_scale,
            "bid_size": bid_size,
            "ask_size": ask_size,
            "source_timestamp_utc": ts.isoformat(),
            "source_sequence": seq,
        }
        eid = generar_uuid_determinista(cid, "SHADOW_TICK", f"{seq}:{ts.isoformat()}")

        evento = SobreEventoV1(
            event_id=eid,
            event_type="QUOTE_TICK",
            schema_version=1,
            occurred_at_utc=ts,
            received_at_utc=ts,
            persisted_at_utc=None,
            source="ctrader_demo",
            environment=self.environment,
            source_account_id_hash=None,
            instrument="US500",
            symbol_id="US500",
            source_sequence=seq,
            payload_hash=compute_payload_hash(payload),
            previous_hash=None,
            causation_id=None,
            correlation_id=cid,
            payload=payload,
        )

        val_ev = validar_sobre_evento(evento)
        if not val_ev.exito:
            self._eventos_rechazados += 1
            return fallo(val_ev.error)

        return self.procesar_evento(evento)

    def procesar_paso(self) -> Resultado[ResumenPasoPipeline | None]:
        """Avanza un paso consumiendo el siguiente evento disponible en la sesión activa."""
        if not self._sesion_activa:
            return fallo(
                ErrorDominio(
                    codigo="VALIDATION_ERROR",
                    mensaje_seguro="No hay una sesión activa configurada. Llame a inicializar_sesion primero.",
                    reintentable=False,
                    correlation_id="",
                    detalles={},
                )
            )

        res_ev = self._sesion_activa.paso()
        if not res_ev.exito:
            return fallo(res_ev.error)

        if res_ev.datos is None:
            return exito(None)

        return self.procesar_evento(res_ev.datos)

    def procesar_flujo(
        self,
        sesion: SesionFuentePuerto | None = None,
    ) -> Resultado[ResumenEjecucionShadow]:
        """Procesa secuencialmente un flujo o dataset de streaming hasta agotarlo."""
        sesion_objetivo = sesion or self._sesion_activa
        if not sesion_objetivo:
            return fallo(
                ErrorDominio(
                    codigo="VALIDATION_ERROR",
                    mensaje_seguro="No se proporcionó ni existe una sesión de fuente activa.",
                    reintentable=False,
                    correlation_id="",
                    detalles={},
                )
            )

        for res_ev in sesion_objetivo.eventos_sync():
            if not res_ev.exito:
                self._eventos_rechazados += 1
                return fallo(res_ev.error)
            res_paso = self.procesar_evento(res_ev.datos)
            if not res_paso.exito:
                return fallo(res_paso.error)

        # Cerrar sesión
        sesion_objetivo.cerrar()

        # Proyección final
        res_proy = self.obtener_proyeccion_v1()
        proyeccion = res_proy.datos if res_proy.exito else None

        run_id = getattr(getattr(sesion_objetivo, "solicitud", None), "correlation_id", str(uuid.uuid4()))
        final_cutoff = (
            self._pipeline._last_market_cutoff_utc.isoformat()
            if self._pipeline._last_market_cutoff_utc
            else None
        )

        dir_canonica: DireccionCanonica = MAPEO_LUZ_A_DIRECCION_CANONICA.get(
            self._pipeline.current_light, "MONITORIZAR"
        )

        resumen = ResumenEjecucionShadow(
            run_id=run_id,
            environment=self.environment,
            final_event_cutoff=final_cutoff,
            accepted_event_count=self._pipeline._event_counter,
            rejected_event_count=self._eventos_rechazados,
            emitted_signal_count=len(self._pipeline._signals_emitted),
            opened_simulation_count=len(
                [s for s in self._pipeline._simulations if s.status in {"OPEN_SIMULATED", "CLOSED_SIMULATED"}]
            ),
            closed_simulation_count=len(
                [s for s in self._pipeline._simulations if s.status == "CLOSED_SIMULATED"]
            ),
            alerts_count=self._alertas_totales,
            current_light=self._pipeline.current_light,
            current_direction=dir_canonica,
            current_health_state=self._pipeline.health_state,
            proyeccion=proyeccion,
            reason_codes=proyeccion.reason_codes if proyeccion else (),
        )
        return exito(resumen)

    def ejecutar(
        self,
        solicitud: SolicitudShadow,
        dataset: Sequence[SobreEventoV1] | None = None,
    ) -> Resultado[ResumenEjecucion]:
        """Punto de entrada canónico para SolicitudShadow exigido por SPEC-001 y API de dominio."""
        val_sol = validar_solicitud_shadow(solicitud)
        if not val_sol.exito:
            return fallo(val_sol.error)

        if dataset:
            res_ses = self.inicializar_sesion(solicitud=solicitud, dataset=dataset)
            if not res_ses.exito:
                return fallo(res_ses.error)
            res_flujo = self.procesar_flujo()
            if not res_flujo.exito:
                return fallo(res_flujo.error)
            resumen_shadow = res_flujo.datos
            resumen = resumen_shadow.to_resumen_ejecucion()
        else:
            final_cutoff = (
                self._pipeline._last_market_cutoff_utc.isoformat()
                if self._pipeline._last_market_cutoff_utc
                else datetime.now(timezone.utc).isoformat()
            )
            resumen = ResumenEjecucion(
                run_id=solicitud.correlation_id,
                environment="SHADOW",
                final_event_cutoff=final_cutoff,
                accepted_event_count=self._pipeline._event_counter,
                rejected_event_count=self._eventos_rechazados,
                emitted_signal_count=len(self._pipeline._signals_emitted),
                opened_simulation_count=len(
                    [s for s in self._pipeline._simulations if s.status in {"OPEN_SIMULATED", "CLOSED_SIMULATED"}]
                ),
                reason_codes=(),
            )

        val_resumen = validar_resumen_ejecucion(resumen)
        if not val_resumen.exito:
            return fallo(val_resumen.error)

        return exito(resumen)

    def obtener_proyeccion_v1(self) -> Resultado[ProyeccionLecturaV1]:
        """Obtiene y valida la Proyección de lectura V1 emitida por el Composition Root."""
        return self._pipeline.obtener_proyeccion_v1()

    def obtener_vista_lectura(self, view: str = "FEED", limit: int = 50) -> Resultado[VistaLectura]:
        """Consulta una vista reactiva inmutable."""
        return self._pipeline.obtener_vista_lectura(view=view, limit=limit)

    def activar_kill_switch(self, razon: str, correlation_id: str = "") -> Resultado[SobreEventoV1]:
        """Activa el switch de corte de emergencia en el pipeline."""
        return self._pipeline.activar_kill_switch(razon=razon, correlation_id=correlation_id)

    def forzar_amarillo(
        self,
        razon: str,
        causation_id: str | None = None,
        correlation_id: str = "",
    ) -> Resultado[TransicionEstadoV1]:
        """Fuerza la transición a luz amarilla por regla de seguridad."""
        return self._pipeline.forzar_amarillo(
            razon=razon,
            causation_id=causation_id,
            correlation_id=correlation_id,
        )


# Alias para compatibilidad con código existente
EjecutorShadow = ShadowUseCase


def ejecutar_shadow(
    solicitud: SolicitudShadow,
    dataset: Sequence[SobreEventoV1] | None = None,
    db_path: str | Path | None = None,
    model_id_campeon: str | None = None,
    reloj: RelojDominio | None = None,
    tiempo_inicial_utc: datetime | None = None,
    clock_seed: int = 20260830,
) -> Resultado[ResumenEjecucion]:
    """Función de nivel superior de caso de uso para ejecutar shadow trading (SPEC-001 §5.2)."""
    t_init = tiempo_inicial_utc
    if reloj is None and t_init is None:
        if getattr(solicitud, "range_start_utc", None):
            t_init = solicitud.range_start_utc
        elif dataset and len(dataset) > 0:
            t_init = dataset[0].occurred_at_utc

    caso_uso = ShadowUseCase(
        db_path=db_path,
        model_id_campeon=model_id_campeon,
        reloj=reloj,
        tiempo_inicial_utc=t_init,
        clock_seed=clock_seed,
    )
    return caso_uso.ejecutar(solicitud, dataset=dataset)


def crear_caso_uso_shadow(
    db_path: str | Path | None = None,
    model_id_campeon: str | None = None,
    policy_version: str = "policy-us500-v1",
    fuente: FuentePuerto | None = None,
    environment: Environment = "SHADOW",
    reloj: RelojDominio | None = None,
    tiempo_inicial_utc: datetime | None = None,
    clock_seed: int = 20260830,
) -> ShadowUseCase:
    """Factoría para instanciar ShadowUseCase con configuración estándar."""
    return ShadowUseCase(
        db_path=db_path,
        model_id_campeon=model_id_campeon,
        policy_version=policy_version,
        fuente=fuente,
        environment=environment,
        reloj=reloj,
        tiempo_inicial_utc=tiempo_inicial_utc,
        clock_seed=clock_seed,
    )


__all__ = [
    "SesionShadowFake",
    "FuenteShadowFake",
    "ResumenEjecucionShadow",
    "ShadowUseCase",
    "EjecutorShadow",
    "ejecutar_shadow",
    "crear_caso_uso_shadow",
]
