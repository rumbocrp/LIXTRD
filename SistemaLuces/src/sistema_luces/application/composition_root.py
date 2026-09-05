"""Composition Root Unificado de SistemaLuces (SPEC-002 §5, ARQUITECTURA.md §2, RF-L010, RF-L011, RNF-L003).

Este módulo implementa el orquestador principal del pipeline unificado (PipelineCompositionRoot)
que enlaza los 8 puertos hexagonales y garantiza determinismo byte-a-byte en Replay y Shadow.
"""

from collections.abc import Sequence
import dataclasses
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import hashlib
from pathlib import Path
import tempfile
from typing import Any, Literal
import uuid

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
from sistema_luces.cases.builder import CasoV1, ConstructorCaso, SolicitudCaso
from sistema_luces.cases.windows import alinear_ventana, es_cierre_de_ventana, obtener_limites_ventana
from sistema_luces.domain.api import (
    ProyeccionLecturaV1,
    ResumenEjecucion,
    SolicitudConsulta,
    VistaLectura,
    validar_proyeccion_lectura_v1,
)
from sistema_luces.domain.error import ErrorDominio
from sistema_luces.domain.event import (
    QuoteTickPayloadV1,
    SobreEventoV1,
    canonical_json_dumps,
    compute_payload_hash,
)
from sistema_luces.domain.manifest import CostProfileV1
from sistema_luces.domain.result import Resultado, exito, fallo
from sistema_luces.domain.signal import SenalV1
from sistema_luces.domain.simulation import SimulacionV1
from sistema_luces.domain.state import TransicionEstadoV1
from sistema_luces.domain.vocabulary import (
    DIRECCIONES_CANONICAS_PERMITIDAS,
    MAPEO_LUZ_A_DIRECCION_CANONICA,
    DecisionWindow,
    DireccionCanonica,
    Environment,
    EstadoUI,
    Light,
    parse_environment,
    parse_instrument,
)
from sistema_luces.feed.quality import MonitorCalidadFeed
from sistema_luces.models.baseline import ModeloPredictivoV1
from sistema_luces.models.registry import RegistroModelos
from sistema_luces.observability.projections import ProyectorVistas
from sistema_luces.policy.lights import DecisionLuzV1, PoliticaLuces, SolicitudLuz
from sistema_luces.simulation.paper import SimuladorPapel
from sistema_luces.sources.clock import RelojDominio
from sistema_luces.sources.replay import FuenteReplay, SolicitudFuente
from sistema_luces.storage.event_store import ArchivoEventos


def generar_uuid_determinista(correlation_id: str, tipo_entidad: str, clave_unica: str) -> str:
    """Genera un UUIDv5 determinista para asegurar reproducibilidad byte-a-byte (RF-L010, CA-5)."""
    semilla = f"{correlation_id}:{tipo_entidad}:{clave_unica}"
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, semilla))


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
class ResumenPasoPipeline:
    """Resultado detallado de procesar un evento en el Composition Root."""

    event_id: str
    event_type: str
    health_state: str
    light: Light
    direction: DireccionCanonica
    alerts_generated: tuple[SobreEventoV1, ...] = ()
    case_generated: CasoV1 | None = None
    signal_emitted: SenalV1 | None = None
    transition_emitted: TransicionEstadoV1 | None = None
    simulation_opened: SimulacionV1 | None = None
    simulations_closed: tuple[SimulacionV1, ...] = ()


class PipelineCompositionRoot:
    """Orquestador central determinista e inmutable del pipeline de decisión de luces.

    Enlaza los 8 puertos hexagonales respetando el principio de cero bifurcación
    lógica entre los modos de ejecución Replay y Shadow (RF-L010, RF-L011).
    """

    def __init__(
        self,
        almacen: AlmacenPuerto,
        evaluador_salud: EvaluadorSaludFeedPuerto,
        generador_casos: GeneradorCasosPuerto,
        registro_modelos: RegistroModelosPuerto,
        politica_luces: MotorPoliticaLucesPuerto,
        motor_simulacion: MotorSimulacionPuerto,
        proyector_vistas: ProyectorVistasPuerto,
        fuente: FuentePuerto | None = None,
        reloj: RelojDominio | None = None,
        environment: Environment = "REPLAY",
        instrument: Literal["US500"] = "US500",
        model_id_campeon: str | None = None,
        policy_version: str = "policy-us500-v1",
        feature_set_version: str = "features-v1",
        price_scale: int = 100,
        cost_profile: CostProfileV1 | None = None,
    ) -> None:
        self.almacen = almacen
        self.evaluador_salud = evaluador_salud
        self.generador_casos = generador_casos
        self.registro_modelos = registro_modelos
        self.politica_luces = politica_luces
        self.motor_simulacion = motor_simulacion
        self.proyector_vistas = proyector_vistas
        self.fuente = fuente
        self.reloj = reloj
        self.environment: Environment = environment
        self.instrument: Literal["US500"] = instrument
        self.model_id_campeon = model_id_campeon
        self.policy_version = policy_version
        self.feature_set_version = feature_set_version
        self.price_scale = price_scale
        self.cost_profile = cost_profile or CostProfileV1(
            profile_version="cost-us500-v1",
            spread_points_base=40,
            spread_points_adverse=60,
            spread_points_stress=100,
            slippage_points_base=0,
            slippage_points_adverse=10,
            slippage_points_stress=30,
            commission_per_lot_usd_cents=0,
            carry_per_night_usd_cents=0,
            latency_ms_base=10,
            latency_ms_stress=50,
        )

        # Estado interno mutable del pipeline
        self._buffer_ticks: list[SobreEventoV1] = []
        self._last_event_id: str | None = None
        self._last_market_cutoff_utc: datetime | None = None
        self._last_health_state: str = "NO_DATA"
        self._current_light: Light = "YELLOW"
        self._last_quote_bid: int | None = None
        self._last_quote_ask: int | None = None
        self._last_evaluated_window_s30: datetime | None = None
        self._event_counter: int = 0
        self._signals_emitted: list[SenalV1] = []
        self._transitions: list[TransicionEstadoV1] = []
        self._simulations: list[SimulacionV1] = []
        self._incidents: list[dict[str, Any]] = []
        self._kill_switch_active: bool = False

    @property
    def current_light(self) -> Light:
        return self._current_light

    @property
    def health_state(self) -> str:
        return self._last_health_state

    @property
    def kill_switch_active(self) -> bool:
        return self._kill_switch_active

    def activar_kill_switch(self, razon: str, correlation_id: str = "") -> Resultado[SobreEventoV1]:
        """Activa el switch de desconexión de seguridad (kill switch), forzando amarillo y registrando evento."""
        self._kill_switch_active = True
        self._current_light = "YELLOW"
        cid = correlation_id or str(uuid.uuid4())
        now_utc = self.reloj.ahora_utc() if self.reloj else datetime.now(timezone.utc)
        ev_id = generar_uuid_determinista(cid, "KILL_SWITCH", now_utc.isoformat())

        payload = {
            "reason": razon,
            "action": "FORCE_YELLOW_HALT_SIMULATIONS",
            "activated_at_utc": now_utc.isoformat(),
        }
        ev = SobreEventoV1(
            event_id=ev_id,
            event_type="KILL_SWITCH",
            schema_version=1,
            occurred_at_utc=now_utc,
            received_at_utc=now_utc,
            persisted_at_utc=None,
            source="system",
            environment=self.environment,
            source_account_id_hash=None,
            instrument=self.instrument,
            symbol_id=self.instrument,
            source_sequence=None,
            correlation_id=cid,
            causation_id=None,
            payload_hash=compute_payload_hash(payload),
            previous_hash=None,
            payload=payload,
        )
        self.almacen.anexar(ev)
        self.proyector_vistas.actualizar_desde_evento(ev)
        self._incidents.append({"type": "KILL_SWITCH", "occurred_at_utc": now_utc.isoformat(), "payload": payload})
        return exito(ev)

    def forzar_amarillo(
        self,
        razon: str,
        causation_id: str | None = None,
        correlation_id: str = "",
    ) -> Resultado[TransicionEstadoV1]:
        """Fuerza la transición a luz amarilla por regla de seguridad o degradación."""
        prev_light = self._current_light
        self._current_light = "YELLOW"
        now_utc = self.reloj.ahora_utc() if self.reloj else datetime.now(timezone.utc)
        cid = correlation_id or str(uuid.uuid4())
        t_id = generar_uuid_determinista(cid, "FORCED_YELLOW", now_utc.isoformat())

        transicion = TransicionEstadoV1(
            transition_id=t_id,
            aggregate_type="light",
            aggregate_id=f"light-{self.instrument.lower()}",
            previous_state=prev_light,
            next_state="YELLOW",
            actor="system",
            occurred_at_utc=now_utc,
            causation_id=causation_id,
            correlation_id=cid,
            policy_version=self.policy_version,
            reason_codes=(razon,),
            safety_forced=True,
        )
        self._transitions.append(transicion)

        # Persistir en almacén y proyector
        p_trans = {
            "transition_id": transicion.transition_id,
            "aggregate_type": transicion.aggregate_type,
            "aggregate_id": transicion.aggregate_id,
            "previous_state": transicion.previous_state,
            "next_state": transicion.next_state,
            "actor": transicion.actor,
            "occurred_at_utc": _format_iso_utc(transicion.occurred_at_utc),
            "causation_id": transicion.causation_id,
            "correlation_id": transicion.correlation_id,
            "policy_version": transicion.policy_version,
            "reason_codes": list(transicion.reason_codes),
            "safety_forced": transicion.safety_forced,
        }
        ev_trans = SobreEventoV1(
            event_id=generar_uuid_determinista(cid, "LIGHT_TRANSITION", t_id),
            event_type="LIGHT_TRANSITION",
            schema_version=1,
            occurred_at_utc=now_utc,
            received_at_utc=now_utc,
            persisted_at_utc=None,
            source="system",
            environment=self.environment,
            source_account_id_hash=None,
            instrument=self.instrument,
            symbol_id=self.instrument,
            source_sequence=None,
            correlation_id=cid,
            causation_id=causation_id,
            payload_hash=compute_payload_hash(p_trans),
            previous_hash=None,
            payload=p_trans,
        )
        self.almacen.anexar(ev_trans)
        self.proyector_vistas.actualizar_desde_evento(ev_trans)
        return exito(transicion)

    def procesar_evento(self, evento: SobreEventoV1) -> Resultado[ResumenPasoPipeline]:
        """Procesa determinísticamente un evento entrante a través de los 8 puertos (RF-L010)."""
        # 1. Sincronización del Reloj
        if self.reloj is not None:
            try:
                self.reloj.avanzar_hasta(evento.occurred_at_utc)
            except ValueError:
                # El reloj de dominio rechaza rollback pero capturamos para que el evaluador de feed lo marque
                pass
            now_utc = self.reloj.ahora_utc()
        else:
            now_utc = evento.occurred_at_utc

        self._last_event_id = evento.event_id
        self._last_market_cutoff_utc = evento.occurred_at_utc
        self._event_counter += 1

        # 2. Evaluación de Salud del Feed (EvaluadorSaludFeedPuerto)
        reloj_eval = self.reloj or RelojDominio(tiempo_inicial_utc=evento.occurred_at_utc)
        health_state, alertas = self.evaluador_salud.evaluar_evento(evento, reloj_eval)
        self._last_health_state = health_state

        alertas_emitidas: list[SobreEventoV1] = []
        for alerta in alertas:
            self.almacen.anexar(alerta)
            self.proyector_vistas.actualizar_desde_evento(alerta)
            alertas_emitidas.append(alerta)
            self._incidents.append(
                {
                    "type": alerta.event_type,
                    "occurred_at_utc": _format_iso_utc(alerta.occurred_at_utc),
                    "payload": alerta.payload,
                }
            )

        # Regla de Amarillo Seguro ante degradación de salud o kill switch
        if health_state != "HEALTHY" or self._kill_switch_active:
            if hasattr(self.politica_luces, "histeresis"):
                self.politica_luces.histeresis.transicionar(
                    "YELLOW", health_state, evento.occurred_at_utc, evento.correlation_id
                )
            self._current_light = "YELLOW"

        # 3. Persistencia del Evento Entrante en el Almacén (AlmacenPuerto)
        recibo = self.almacen.anexar(evento)
        if not recibo.exito:
            return fallo(recibo.error)

        # 4. Actualización Reactiva de Proyecciones (ProyectorVistasPuerto)
        self.proyector_vistas.actualizar_desde_evento(evento)

        # 5. Avance de Simulaciones Paper Activas (MotorSimulacionPuerto)
        sims_cerradas: list[SimulacionV1] = []
        if evento.event_type == "QUOTE_TICK" and isinstance(evento.payload, dict):
            bid = int(evento.payload.get("bid", 0))
            ask = int(evento.payload.get("ask", 0))
            self._last_quote_bid = bid
            self._last_quote_ask = ask
            scale = int(evento.payload.get("price_scale", self.price_scale))
            bid_sz = evento.payload.get("bid_size")
            ask_sz = evento.payload.get("ask_size")
            tick = QuoteTickPayloadV1(
                bid=bid,
                ask=ask,
                price_scale=scale,
                bid_size=bid_sz,
                ask_size=ask_sz,
                source_timestamp_utc=evento.occurred_at_utc,
                source_sequence=evento.source_sequence,
            )

            activas = dict(
                getattr(
                    self.motor_simulacion,
                    "simulaciones_activas",
                    getattr(self.motor_simulacion, "_simulaciones_activas", {}),
                )
            )
            for sim_id in list(activas.keys()):
                res_tick = self.motor_simulacion.avanzar_tick(sim_id, tick, evento.occurred_at_utc)
                if res_tick.exito and res_tick.datos.status == "CLOSED_SIMULATED":
                    sim_cerrada = res_tick.datos
                    self._simulations.append(sim_cerrada)
                    sims_cerradas.append(sim_cerrada)

                    # Persistir evento SIM_CLOSED
                    sim_closed_id = generar_uuid_determinista(
                        evento.correlation_id, "SIM_CLOSED", f"{sim_id}:{_format_iso_utc(evento.occurred_at_utc)}"
                    )
                    payload_sim = {
                        "simulation_id": sim_cerrada.simulation_id,
                        "signal_id": sim_cerrada.signal_id,
                        "status": sim_cerrada.status,
                        "direction": sim_cerrada.direction,
                        "fill_entry": sim_cerrada.fill_entry,
                        "fill_exit": sim_cerrada.fill_exit,
                        "exit_reason": sim_cerrada.exit_reason,
                        "gross_pnl": sim_cerrada.gross_pnl,
                        "net_pnl": sim_cerrada.net_pnl,
                        "realized_r": sim_cerrada.realized_r,
                        "mfe": sim_cerrada.mfe,
                        "mae": sim_cerrada.mae,
                        "closed_at_utc": _format_iso_utc(sim_cerrada.closed_at_utc),
                    }
                    ev_sim_closed = SobreEventoV1(
                        event_id=sim_closed_id,
                        event_type="SIM_CLOSED",
                        schema_version=1,
                        occurred_at_utc=evento.occurred_at_utc,
                        received_at_utc=evento.occurred_at_utc,
                        persisted_at_utc=None,
                        source="system",
                        environment=evento.environment,
                        source_account_id_hash=None,
                        instrument=evento.instrument,
                        symbol_id=evento.symbol_id,
                        source_sequence=None,
                        correlation_id=evento.correlation_id,
                        causation_id=sim_id,
                        payload_hash=compute_payload_hash(payload_sim),
                        previous_hash=None,
                        payload=payload_sim,
                    )
                    self.almacen.anexar(ev_sim_closed)
                    self.proyector_vistas.actualizar_desde_evento(ev_sim_closed)

            # Acumular tick en el buffer causal para features
            self._buffer_ticks.append(evento)
            cutoff_buf = evento.occurred_at_utc - timedelta(seconds=120)
            self._buffer_ticks = [e for e in self._buffer_ticks if e.occurred_at_utc >= cutoff_buf]

        # 6. Cierre de Ventana Causal S30 y Generación de Caso (GeneradorCasosPuerto)
        caso_creado: CasoV1 | None = None
        senal_emitida: SenalV1 | None = None
        transicion_emitida: TransicionEstadoV1 | None = None
        sim_abierta: SimulacionV1 | None = None

        debe_cerrar_s30 = False
        if evento.event_type == "QUOTE_TICK":
            if es_cierre_de_ventana(evento.occurred_at_utc, "S30"):
                if self._last_evaluated_window_s30 != evento.occurred_at_utc:
                    debe_cerrar_s30 = True

        if debe_cerrar_s30:
            ventana_s30 = alinear_ventana(evento.occurred_at_utc, "S30")
            c_id = generar_uuid_determinista(
                evento.correlation_id, "CASE", f"S30:{_format_iso_utc(evento.occurred_at_utc)}"
            )

            sol_caso = SolicitudCaso(
                case_id=c_id,
                correlation_id=evento.correlation_id,
                decision_window="S30",
                window_start_utc=ventana_s30.start_utc,
                window_end_utc=ventana_s30.end_utc,
                market_event_cutoff=evento.occurred_at_utc,
                feed_health_state=health_state,
                feature_set_version=self.feature_set_version,
                environment=evento.environment,
                instrument=self.instrument,
                price_scale=self.price_scale,
                buffer_eventos=tuple(self._buffer_ticks),
            )
            res_caso = self.generador_casos.construir(sol_caso, buffer_eventos=self._buffer_ticks)
            if res_caso.exito:
                caso_creado = res_caso.datos
                self._last_evaluated_window_s30 = evento.occurred_at_utc

                # Persistir CASE_CREATED
                payload_caso = {
                    "case_id": caso_creado.case_id,
                    "decision_window": caso_creado.decision_window,
                    "window_start_utc": _format_iso_utc(caso_creado.window_start_utc),
                    "window_end_utc": _format_iso_utc(caso_creado.window_end_utc),
                    "market_event_cutoff": _format_iso_utc(caso_creado.market_event_cutoff),
                    "reference_bid": caso_creado.reference_bid,
                    "reference_ask": caso_creado.reference_ask,
                    "eligible_for_signal": caso_creado.eligible_for_signal,
                    "feature_snapshot_hash": caso_creado.feature_snapshot_hash,
                    "feed_health_state": caso_creado.feed_health_state,
                }
                ev_case = SobreEventoV1(
                    event_id=generar_uuid_determinista(evento.correlation_id, "CASE_CREATED", caso_creado.case_id),
                    event_type="CASE_CREATED",
                    schema_version=1,
                    occurred_at_utc=evento.occurred_at_utc,
                    received_at_utc=evento.occurred_at_utc,
                    persisted_at_utc=None,
                    source="system",
                    environment=evento.environment,
                    source_account_id_hash=None,
                    instrument=evento.instrument,
                    symbol_id=evento.symbol_id,
                    source_sequence=None,
                    correlation_id=evento.correlation_id,
                    causation_id=caso_creado.case_id,
                    payload_hash=compute_payload_hash(payload_caso),
                    previous_hash=None,
                    payload=payload_caso,
                )
                self.almacen.anexar(ev_case)
                self.proyector_vistas.actualizar_desde_evento(ev_case)

                # 7. Inferencia con Modelo Campeón (RegistroModelosPuerto)
                prob_long: int | None = None
                prob_short: int | None = None
                raw_long: int | None = None
                raw_short: int | None = None
                modelo_activo: ModeloPredictivoV1 | None = None

                if self.model_id_campeon:
                    res_m = self.registro_modelos.obtener(self.model_id_campeon)
                    if res_m.exito:
                        modelo_activo = res_m.datos
                        if caso_creado.eligible_for_signal and not self._kill_switch_active:
                            res_pred = self.registro_modelos.predecir_calibrado_par(
                                self.model_id_campeon, caso_creado
                            )
                            if res_pred.exito:
                                prob_long, prob_short = res_pred.datos
                                res_raw = modelo_activo.predecir_raw(caso_creado.feature_snapshot)
                                if res_raw.exito:
                                    raw_long, raw_short = res_raw.datos

                # 8. Evaluación de Política de Luces (MotorPoliticaLucesPuerto)
                sig_id = generar_uuid_determinista(
                    evento.correlation_id, "SIGNAL", f"{caso_creado.case_id}:{_format_iso_utc(evento.occurred_at_utc)}"
                )
                data_age_ms = int((now_utc - evento.occurred_at_utc).total_seconds() * 1000)

                sol_luz = SolicitudLuz(
                    case_id=caso_creado.case_id,
                    created_at_utc=evento.occurred_at_utc,
                    environment=evento.environment,
                    instrument=evento.instrument,
                    decision_window=caso_creado.decision_window,
                    market_event_cutoff=caso_creado.market_event_cutoff,
                    reference_bid=caso_creado.reference_bid or self._last_quote_bid or 0,
                    reference_ask=caso_creado.reference_ask or self._last_quote_ask or 0,
                    price_scale=self.price_scale,
                    data_age_ms=data_age_ms,
                    feed_health_state=health_state,
                    model_id=modelo_activo.model_id if modelo_activo else None,
                    model_version=modelo_activo.model_version if modelo_activo else None,
                    model_hash=modelo_activo.model_hash if modelo_activo else None,
                    calibration_version=getattr(modelo_activo, "calibration_version", "calib-v1")
                    if modelo_activo
                    else None,
                    feature_snapshot_hash=caso_creado.feature_snapshot_hash,
                    raw_score_long=raw_long,
                    raw_score_short=raw_short,
                    calibrated_probability_long=prob_long,
                    calibrated_probability_short=prob_short,
                    expected_value_long_net=None,
                    expected_value_short_net=None,
                    cost_profile_version=self.cost_profile.profile_version,
                    correlation_id=evento.correlation_id,
                    causation_id=caso_creado.case_id,
                    code_hash=hashlib.sha256(b"sistema_luces_v1").hexdigest(),
                    signal_id=sig_id,
                    policy_version=self.policy_version,
                )

                res_dec = self.politica_luces.decidir(sol_luz)
                if res_dec.exito:
                    decision = res_dec.datos
                    senal_emitida = decision.senal

                    # Normalizar determinísticamente el transition_id
                    t_det_id = generar_uuid_determinista(
                        evento.correlation_id, "LIGHT_TRANSITION", f"{senal_emitida.signal_id}:{_format_iso_utc(evento.occurred_at_utc)}"
                    )
                    transicion_emitida = dataclasses.replace(decision.transicion, transition_id=t_det_id)

                    self._signals_emitted.append(senal_emitida)
                    self._transitions.append(transicion_emitida)
                    self._current_light = senal_emitida.light

                    # Persistir SIGNAL_EMITTED
                    p_sig = {
                        "signal_id": senal_emitida.signal_id,
                        "case_id": senal_emitida.case_id,
                        "created_at_utc": _format_iso_utc(senal_emitida.created_at_utc),
                        "valid_until_utc": _format_iso_utc(senal_emitida.valid_until_utc),
                        "environment": senal_emitida.environment,
                        "instrument": senal_emitida.instrument,
                        "direction": senal_emitida.direction,
                        "light": senal_emitida.light,
                        "reason_codes": list(senal_emitida.reason_codes),
                        "health_state": senal_emitida.health_state,
                        "safety_forced": senal_emitida.safety_forced,
                        "model_id": senal_emitida.model_id,
                        "model_version": senal_emitida.model_version,
                        "model_hash": senal_emitida.model_hash,
                        "policy_version": senal_emitida.policy_version,
                        "calibrated_probability_long": senal_emitida.calibrated_probability_long,
                        "calibrated_probability_short": senal_emitida.calibrated_probability_short,
                        "threshold_green": getattr(self.politica_luces, "threshold_green", 650_000),
                        "threshold_red": getattr(self.politica_luces, "threshold_red", 350_000),
                    }
                    ev_sig = SobreEventoV1(
                        event_id=generar_uuid_determinista(
                            evento.correlation_id, "SIGNAL_EMITTED", senal_emitida.signal_id
                        ),
                        event_type="SIGNAL_EMITTED",
                        schema_version=1,
                        occurred_at_utc=evento.occurred_at_utc,
                        received_at_utc=evento.occurred_at_utc,
                        persisted_at_utc=None,
                        source="system",
                        environment=evento.environment,
                        source_account_id_hash=None,
                        instrument=evento.instrument,
                        symbol_id=evento.symbol_id,
                        source_sequence=None,
                        correlation_id=evento.correlation_id,
                        causation_id=senal_emitida.signal_id,
                        payload_hash=compute_payload_hash(p_sig),
                        previous_hash=None,
                        payload=p_sig,
                    )
                    self.almacen.anexar(ev_sig)
                    self.proyector_vistas.actualizar_desde_evento(ev_sig)

                    # Persistir LIGHT_TRANSITION
                    p_trans = {
                        "transition_id": transicion_emitida.transition_id,
                        "aggregate_type": transicion_emitida.aggregate_type,
                        "aggregate_id": transicion_emitida.aggregate_id,
                        "previous_state": transicion_emitida.previous_state,
                        "next_state": transicion_emitida.next_state,
                        "actor": transicion_emitida.actor,
                        "occurred_at_utc": _format_iso_utc(transicion_emitida.occurred_at_utc),
                        "causation_id": transicion_emitida.causation_id,
                        "correlation_id": transicion_emitida.correlation_id,
                        "policy_version": transicion_emitida.policy_version,
                        "reason_codes": list(transicion_emitida.reason_codes),
                        "safety_forced": transicion_emitida.safety_forced,
                    }
                    ev_trans = SobreEventoV1(
                        event_id=generar_uuid_determinista(
                            evento.correlation_id, "LIGHT_TRANSITION", transicion_emitida.transition_id
                        ),
                        event_type="LIGHT_TRANSITION",
                        schema_version=1,
                        occurred_at_utc=evento.occurred_at_utc,
                        received_at_utc=evento.occurred_at_utc,
                        persisted_at_utc=None,
                        source="system",
                        environment=evento.environment,
                        source_account_id_hash=None,
                        instrument=evento.instrument,
                        symbol_id=evento.symbol_id,
                        source_sequence=None,
                        correlation_id=evento.correlation_id,
                        causation_id=transicion_emitida.transition_id,
                        payload_hash=compute_payload_hash(p_trans),
                        previous_hash=None,
                        payload=p_trans,
                    )
                    self.almacen.anexar(ev_trans)
                    self.proyector_vistas.actualizar_desde_evento(ev_trans)

                    # 9. Disparo de Simulación Paper (MotorSimulacionPuerto)
                    if (
                        senal_emitida.light in {"GREEN", "RED"}
                        and senal_emitida.direction in {"LONG", "SHORT"}
                        and not senal_emitida.safety_forced
                        and not self._kill_switch_active
                    ):
                        ref_bid = caso_creado.reference_bid or self._last_quote_bid or 0
                        ref_ask = caso_creado.reference_ask or self._last_quote_ask or 0
                        res_sim = self.motor_simulacion.proponer_y_abrir(
                            senal=senal_emitida,
                            current_bid=ref_bid,
                            current_ask=ref_ask,
                            now_utc=evento.occurred_at_utc,
                        )
                        if res_sim.exito:
                            sim_abierta_raw = res_sim.datos
                            sim_det_id = generar_uuid_determinista(
                                evento.correlation_id, "SIMULATION", f"{senal_emitida.signal_id}:{_format_iso_utc(evento.occurred_at_utc)}"
                            )
                            sim_abierta = dataclasses.replace(sim_abierta_raw, simulation_id=sim_det_id)

                            # Re-indexar en motor_simulacion para determinismo estricto
                            if hasattr(self.motor_simulacion, "_simulaciones_activas"):
                                if sim_abierta_raw.simulation_id in self.motor_simulacion._simulaciones_activas:
                                    del self.motor_simulacion._simulaciones_activas[sim_abierta_raw.simulation_id]
                                self.motor_simulacion._simulaciones_activas[sim_det_id] = sim_abierta

                            self._simulations.append(sim_abierta)

                            p_sim_open = {
                                "simulation_id": sim_abierta.simulation_id,
                                "signal_id": sim_abierta.signal_id,
                                "status": sim_abierta.status,
                                "direction": sim_abierta.direction,
                                "planned_entry": sim_abierta.planned_entry,
                                "stop": sim_abierta.stop,
                                "target": sim_abierta.target,
                                "fill_entry": sim_abierta.fill_entry,
                                "opened_at_utc": _format_iso_utc(sim_abierta.opened_at_utc),
                                "horizon_end_utc": _format_iso_utc(sim_abierta.horizon_end_utc),
                            }
                            ev_sim_open = SobreEventoV1(
                                event_id=generar_uuid_determinista(
                                    evento.correlation_id, "SIM_OPENED", sim_abierta.simulation_id
                                ),
                                event_type="SIM_OPENED",
                                schema_version=1,
                                occurred_at_utc=evento.occurred_at_utc,
                                received_at_utc=evento.occurred_at_utc,
                                persisted_at_utc=None,
                                source="system",
                                environment=evento.environment,
                                source_account_id_hash=None,
                                instrument=evento.instrument,
                                symbol_id=evento.symbol_id,
                                source_sequence=None,
                                correlation_id=evento.correlation_id,
                                causation_id=sim_abierta.simulation_id,
                                payload_hash=compute_payload_hash(p_sim_open),
                                previous_hash=None,
                                payload=p_sim_open,
                            )
                            self.almacen.anexar(ev_sim_open)
                            self.proyector_vistas.actualizar_desde_evento(ev_sim_open)

        # Determinar dirección canónica para el paso
        dir_canonica: DireccionCanonica = MAPEO_LUZ_A_DIRECCION_CANONICA.get(self._current_light, "MONITORIZAR")

        return exito(
            ResumenPasoPipeline(
                event_id=evento.event_id,
                event_type=evento.event_type,
                health_state=self._last_health_state,
                light=self._current_light,
                direction=dir_canonica,
                alerts_generated=tuple(alertas_emitidas),
                case_generated=caso_creado,
                signal_emitted=senal_emitida,
                transition_emitted=transicion_emitida,
                simulation_opened=sim_abierta,
                simulations_closed=tuple(sims_cerradas),
            )
        )

    def procesar_flujo(self, sesion: SesionFuentePuerto) -> Resultado[ResumenEjecucion]:
        """Procesa secuencialmente un flujo o dataset completo desde una SesionFuentePuerto."""
        for res_ev in sesion.eventos_sync():
            if not res_ev.exito:
                return fallo(res_ev.error)
            res_paso = self.procesar_evento(res_ev.datos)
            if not res_paso.exito:
                return fallo(res_paso.error)

        # Cerrar sesión
        res_cierre = sesion.cerrar()
        cutoff_iso = _format_iso_utc(self._last_market_cutoff_utc)
        run_id = getattr(getattr(sesion, "solicitud", None), "correlation_id", str(uuid.uuid4()))

        resumen = ResumenEjecucion(
            run_id=run_id,
            environment=self.environment if self.environment in {"REPLAY", "SHADOW"} else "REPLAY",
            final_event_cutoff=cutoff_iso,
            accepted_event_count=self._event_counter,
            rejected_event_count=0,
            emitted_signal_count=len(self._signals_emitted),
            opened_simulation_count=len([s for s in self._simulations if s.status in {"OPEN_SIMULATED", "CLOSED_SIMULATED"}]),
            reason_codes=(),
        )
        return exito(resumen)

    def obtener_vista_lectura(self, view: str = "FEED", limit: int = 50) -> Resultado[VistaLectura]:
        """Obtiene una VistaLectura inmutable a través del proyector."""
        sol = SolicitudConsulta(
            correlation_id=str(uuid.uuid4()),
            environment=self.environment,
            view=view,  # type: ignore[arg-type]
            as_of_event_id=self._last_event_id,
            cursor=None,
            limit=limit,
        )
        return self.proyector_vistas.consultar(sol)

    def obtener_proyeccion_v1(self) -> Resultado[ProyeccionLecturaV1]:
        """Construye y valida la ProyeccionLecturaV1 canónica con metadatos completos (RF-L015, WS-2.1)."""
        now_utc = self.reloj.ahora_utc() if self.reloj else datetime.now(timezone.utc)
        has_data = bool(self._last_event_id)

        # Model resolution
        m_id: str | None = None
        m_ver: str | None = None
        m_hash: str | None = None
        if self.model_id_campeon:
            res_m = self.registro_modelos.obtener(self.model_id_campeon)
            if res_m.exito:
                m_id = res_m.datos.model_id
                m_ver = res_m.datos.model_version
                m_hash = res_m.datos.model_hash

        # Calcular data_age_ms
        age_ms: int | None = None
        if self._last_market_cutoff_utc is not None:
            age_ms = max(0, int((now_utc - self._last_market_cutoff_utc).total_seconds() * 1000))

        # Determinar luz y dirección con reglas de amarillo seguro (RF-L008, RB-L003, RB-L012)
        health = self._last_health_state if has_data else "NO_DATA"
        env = self.environment if has_data else "NO_DATA"

        es_seguro = (
            has_data
            and not self._kill_switch_active
            and health == "HEALTHY"
            and (age_ms is None or age_ms <= 5000)
            and m_id is not None
            and m_ver is not None
            and m_hash is not None
        )

        luz: Light = self._current_light if es_seguro else "YELLOW"
        direction: DireccionCanonica = MAPEO_LUZ_A_DIRECCION_CANONICA.get(luz, "MONITORIZAR")

        reasons: list[str] = []
        if not has_data:
            reasons.append("NO_DATA_YELLOW")
        if self._kill_switch_active:
            reasons.append("KILL_SWITCH_ACTIVE")
        if health != "HEALTHY":
            reasons.append(f"FEED_{health}")
        if age_ms is not None and age_ms > 5000:
            reasons.append("DATA_STALE_OVER_5000MS")
        if m_id is None or m_ver is None or m_hash is None:
            reasons.append("NO_CHAMPION_MODEL")

        ui_state: EstadoUI = "vacio"
        if has_data:
            if health == "HEALTHY":
                ui_state = "exito"
            elif health in {"STALE", "GAPPED"}:
                ui_state = "obsoleto"
            elif self._kill_switch_active:
                ui_state = "error"
            else:
                ui_state = "parcial"

        # Telemetría cuantitativa
        bid_val: float | None = None
        ask_val: float | None = None
        spread_val: float | None = None
        mid_val: float | None = None
        micro_val: float | None = None
        if self._last_quote_bid is not None and self._last_quote_ask is not None:
            bid_val = round(float(self._last_quote_bid) / float(self.price_scale), 2)
            ask_val = round(float(self._last_quote_ask) / float(self.price_scale), 2)
            spread_val = round(ask_val - bid_val, 2)
            mid_val = round((bid_val + ask_val) / 2.0, 2)
            # Micro-price y OFI requieren tamaños reales; no se infieren desde la luz.

        beta_k = None
        z_sc = None
        ofi_val = None
        balancines_list: list[dict[str, Any]] = []

        diagnostico_semaforo: dict[str, Any] | None = None
        if self._signals_emitted:
            ultima_senal = self._signals_emitted[-1]
            p_long_raw = ultima_senal.calibrated_probability_long
            p_short_raw = ultima_senal.calibrated_probability_short
            if p_long_raw is not None and p_short_raw is not None:
                p_long = round(float(p_long_raw) / 10_000.0, 4)
                p_short = round(float(p_short_raw) / 10_000.0, 4)
                t_green = round(float(getattr(self.politica_luces, "threshold_green", 650_000)) / 10_000.0, 4)
                t_red = round(float(getattr(self.politica_luces, "threshold_red", 350_000)) / 10_000.0, 4)
                diagnostico_semaforo = {
                    "probability_long_pct": p_long,
                    "probability_short_pct": p_short,
                    "threshold_green_pct": t_green,
                    "threshold_red_pct": t_red,
                    "distance_to_green_pp": round(t_green - p_long, 4),
                    "distance_to_red_pp": round(p_long - t_red, 4),
                    "threshold_source": "active-policy",
                    "source_event_id": self._last_event_id,
                }

        slots_usados = len([s for s in self._simulations if s.status == "OPEN_SIMULATED"])
        simulaciones_cerradas = [s for s in self._simulations if s.status == "CLOSED_SIMULATED"]
        pnl_acum = (
            round(sum(s.net_pnl for s in simulaciones_cerradas) / 100.0, 2)
            if simulaciones_cerradas
            else None
        )

        proyeccion = ProyeccionLecturaV1(
            schema_version=1,
            generated_at_utc=now_utc,
            environment=env,
            instrument=self.instrument,
            market_cutoff_utc=self._last_market_cutoff_utc,
            data_age_ms=age_ms,
            health_state=health,
            light=luz,
            direction=direction,
            reason_codes=tuple(reasons),
            model_id=m_id,
            model_version=m_ver,
            model_hash=m_hash,
            policy_version=self.policy_version,
            transitions=tuple(
                {
                    "transition_id": t.transition_id,
                    "previous_state": t.previous_state,
                    "next_state": t.next_state,
                    "occurred_at_utc": _format_iso_utc(t.occurred_at_utc),
                    "safety_forced": t.safety_forced,
                    "reason_codes": list(t.reason_codes),
                }
                for t in self._transitions[-20:]
            ),
            simulations=tuple(
                {
                    "simulation_id": s.simulation_id,
                    "status": s.status,
                    "direction": s.direction,
                    "gross_pnl": s.gross_pnl,
                    "net_pnl": s.net_pnl,
                    "realized_r": s.realized_r,
                }
                for s in self._simulations[-20:]
            ),
            metrics=(),
            incidents=tuple(self._incidents[-20:]),
            kill_switch_active=self._kill_switch_active,
            ui_state=ui_state,
            as_of_event_id=self._last_event_id,
            next_cursor=None,
            session=None,
            bid=bid_val,
            ask=ask_val,
            spread=spread_val,
            mid_price=mid_val,
            micro_price=micro_val,
            beta_kalman=beta_k,
            z_score=z_sc,
            desbalance_ofi=ofi_val,
            balancines=tuple(balancines_list),
            drawdown_diario_pct=None,
            limite_por_trade_pct=None,
            slots_concurrentes_usados=slots_usados if has_data else None,
            slots_concurrentes_max=None,
            pnl_paper_acumulado=pnl_acum,
            secuencia=self._event_counter if has_data else None,
            hash_snapshot=self._last_event_id if has_data else None,
            salud_feed=health,
            diagnostico_semaforo=diagnostico_semaforo,
        )

        return validar_proyeccion_lectura_v1(proyeccion, correlation_id=self._last_event_id or "")


def _crear_temp_db_path() -> str:
    """Crea una ruta a un archivo temporal SQLite para almacén determinista."""
    tf = tempfile.NamedTemporaryFile(prefix="luces_pipeline_", suffix=".db", delete=False)
    tf.close()
    return tf.name


def crear_pipeline_replay(
    db_path: str | Path | None = None,
    model_id_campeon: str | None = None,
    clock_seed: int = 20260829,
    policy_version: str = "policy-us500-v1",
) -> PipelineCompositionRoot:
    """Factoría determinista para entorno REPLAY con reloj sintético."""
    effective_path = db_path if db_path is not None else _crear_temp_db_path()
    almacen = ArchivoEventos(effective_path)
    evaluador_salud = MonitorCalidadFeed()
    generador_casos = ConstructorCaso()
    registro_modelos = RegistroModelos()
    politica_luces = PoliticaLuces(policy_version=policy_version)
    motor_simulacion = SimuladorPapel()
    proyector_vistas = ProyectorVistas()
    fuente = FuenteReplay()
    reloj = RelojDominio(clock_seed=clock_seed)

    return PipelineCompositionRoot(
        almacen=almacen,
        evaluador_salud=evaluador_salud,
        generador_casos=generador_casos,
        registro_modelos=registro_modelos,
        politica_luces=politica_luces,
        motor_simulacion=motor_simulacion,
        proyector_vistas=proyector_vistas,
        fuente=fuente,
        reloj=reloj,
        environment="REPLAY",
        model_id_campeon=model_id_campeon,
        policy_version=policy_version,
    )


def crear_pipeline_shadow(
    db_path: str | Path | None = None,
    model_id_campeon: str | None = None,
    policy_version: str = "policy-us500-v1",
    reloj: RelojDominio | None = None,
    tiempo_inicial_utc: datetime | None = None,
    clock_seed: int = 20260830,
) -> PipelineCompositionRoot:
    """Factoría determinista para entorno SHADOW compartiendo idéntico Composition Root."""
    effective_path = db_path if db_path is not None else _crear_temp_db_path()
    almacen = ArchivoEventos(effective_path)
    evaluador_salud = MonitorCalidadFeed()
    generador_casos = ConstructorCaso()
    registro_modelos = RegistroModelos()
    politica_luces = PoliticaLuces(policy_version=policy_version)
    motor_simulacion = SimuladorPapel()
    proyector_vistas = ProyectorVistas()

    if reloj is not None:
        reloj_final = reloj
    elif tiempo_inicial_utc is not None:
        reloj_final = RelojDominio(tiempo_inicial=tiempo_inicial_utc, clock_seed=clock_seed)
    else:
        reloj_final = RelojDominio(tiempo_inicial=datetime.now(timezone.utc), clock_seed=clock_seed)

    return PipelineCompositionRoot(
        almacen=almacen,
        evaluador_salud=evaluador_salud,
        generador_casos=generador_casos,
        registro_modelos=registro_modelos,
        politica_luces=politica_luces,
        motor_simulacion=motor_simulacion,
        proyector_vistas=proyector_vistas,
        fuente=None,
        reloj=reloj_final,
        environment="SHADOW",
        model_id_campeon=model_id_campeon,
        policy_version=policy_version,
    )


__all__ = [
    "ResumenPasoPipeline",
    "PipelineCompositionRoot",
    "generar_uuid_determinista",
    "crear_pipeline_replay",
    "crear_pipeline_shadow",
]
