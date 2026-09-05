"""Esquema canónico y validadores para ProyeccionLecturaV1 (SPEC-001 §5.2.1, RF-L015, RNF-L012, RB-L001).

Define el contrato unificado de lectura para el frontend y clientes externos, integrando:
1. Ticker y microestructura: bid, ask, spread, mid_price, micro_price.
2. Balancines y macro: beta_kalman, z_score, desbalance_ofi, balancines list.
3. Motor de riesgo: drawdown_diario_pct, limite_por_trade_pct, slots_concurrentes, pnl_paper_acumulado.
4. Linaje del corte y salud: data_age_ms, secuencia, hash_snapshot, salud_feed.
5. 7 estados canónicos de interfaz y vocabulario cerrado en español (LARGO, MONITORIZAR, CORTO).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import re
from typing import Any, Literal

from sistema_luces.domain.error import ErrorDominio
from sistema_luces.domain.result import Resultado, exito, fallo
from sistema_luces.domain.vocabulary import (
    DIRECCIONES_CANONICAS_PERMITIDAS,
    ENTORNOS_PERMITIDOS,
    ESTADOS_UI_PERMITIDOS,
    LUCES_PERMITIDAS,
    DireccionCanonica,
    Environment,
    EstadoUI,
    Light,
    parse_direccion_canonica,
    parse_environment,
    parse_estado_ui,
    Instrument,
    parse_instrument,
    parse_light,
)

ReasonCode = str

_UUID_REGEX = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE)
_HASH_REGEX = re.compile(r"^[0-9a-f]{64}$", re.IGNORECASE)

VALID_HEALTH_STATES: frozenset[str] = frozenset(
    {"NO_DATA", "INITIALIZING", "HEALTHY", "STALE", "GAPPED", "RECONNECTING", "STOPPED", "ERROR"}
)


def _format_iso_utc(dt: datetime | str | None) -> str | None:
    if dt is None:
        return None
    if isinstance(dt, str):
        return dt
    if isinstance(dt, datetime):
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        utc_dt = dt.astimezone(timezone.utc)
        if utc_dt.microsecond == 0:
            return utc_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        return utc_dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    return str(dt)


def _parse_iso_utc(val: datetime | str | None) -> datetime | None:
    if val is None:
        return None
    if isinstance(val, datetime):
        if val.tzinfo is None:
            return val.replace(tzinfo=timezone.utc)
        return val.astimezone(timezone.utc)
    if isinstance(val, str):
        clean_str = val.strip()
        if clean_str.endswith("Z") or clean_str.endswith("z"):
            clean_str = clean_str[:-1] + "+00:00"
        parsed = datetime.fromisoformat(clean_str)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    return None


def _is_valid_uuid(val: str) -> bool:
    return isinstance(val, str) and bool(_UUID_REGEX.match(val))


def _is_valid_hash(val: str) -> bool:
    return isinstance(val, str) and bool(_HASH_REGEX.match(val))


def _is_utc_datetime(dt: object) -> bool:
    return isinstance(dt, datetime) and dt.tzinfo is not None and dt.utcoffset() == timezone.utc.utcoffset(dt)


@dataclass(frozen=True)
class BalancinItemV1:
    """Información cuantitativa de un par balancín macro o momentum."""

    key: str
    name: str
    category: str
    symbol_y: str
    symbol_x: str
    price_y: float | None = None
    price_x: float | None = None
    beta_kalman: float | None = None
    z_score: float | None = None
    ofi: float | None = None
    micro_price: float | None = None
    mid_price: float | None = None
    light: Light = "YELLOW"
    direction: DireccionCanonica = "MONITORIZAR"
    composite_score: float | None = None
    confidence_pct: float | None = None
    threshold_green: float | None = None
    threshold_red: float | None = None
    source_name: str | None = None
    data_age_ms: int | None = None
    action: str = "MONITORIZAR"

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "name": self.name,
            "category": self.category,
            "symbol_y": self.symbol_y,
            "symbol_x": self.symbol_x,
            "price_y": self.price_y,
            "price_x": self.price_x,
            "beta_kalman": self.beta_kalman,
            "z_score": self.z_score,
            "ofi": self.ofi,
            "micro_price": self.micro_price,
            "mid_price": self.mid_price,
            "light": self.light,
            "direction": self.direction,
            "composite_score": self.composite_score,
            "confidence_pct": self.confidence_pct,
            "threshold_green": self.threshold_green,
            "threshold_red": self.threshold_red,
            "source_name": self.source_name,
            "data_age_ms": self.data_age_ms,
            "action": self.action,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BalancinItemV1":
        return cls(
            key=str(data.get("key", "")),
            name=str(data.get("name", "")),
            category=str(data.get("category", "")),
            symbol_y=str(data.get("symbol_y", "")),
            symbol_x=str(data.get("symbol_x", "")),
            price_y=data.get("price_y"),
            price_x=data.get("price_x"),
            beta_kalman=data.get("beta_kalman"),
            z_score=data.get("z_score"),
            ofi=data.get("ofi"),
            micro_price=data.get("micro_price"),
            mid_price=data.get("mid_price"),
            light=data.get("light", "YELLOW"),
            direction=data.get("direction", "MONITORIZAR"),
            composite_score=data.get("composite_score"),
            confidence_pct=data.get("confidence_pct"),
            threshold_green=data.get("threshold_green"),
            threshold_red=data.get("threshold_red"),
            source_name=data.get("source_name"),
            data_age_ms=data.get("data_age_ms"),
            action=str(data.get("action", "MONITORIZAR")),
        )


@dataclass(frozen=True)
class ProyeccionLecturaV1:
    """Proyección de lectura inmutable V1 para consumo UI y API externa (SPEC-001 §5.2.1, RF-L015)."""

    schema_version: int
    generated_at_utc: datetime
    environment: Environment
    instrument: Instrument
    market_cutoff_utc: datetime | None
    data_age_ms: int | None
    health_state: str
    light: Light
    direction: DireccionCanonica
    reason_codes: tuple[ReasonCode, ...]
    model_id: str | None
    model_version: str | None
    model_hash: str | None
    policy_version: str
    transitions: tuple[dict[str, Any] | Any, ...]
    simulations: tuple[dict[str, Any] | Any, ...]
    metrics: tuple[dict[str, Any] | Any, ...]
    incidents: tuple[dict[str, Any], ...]
    kill_switch_active: bool
    ui_state: EstadoUI
    as_of_event_id: str | None
    next_cursor: str | None = None
    session: str | None = None

    # Telemetría Cuantitativa Densa (Milestone 2 & 3)
    # Ticker:
    bid: float | None = None
    ask: float | None = None
    spread: float | None = None
    mid_price: float | None = None
    micro_price: float | None = None
    # Balancines y Macro:
    beta_kalman: float | None = None
    z_score: float | None = None
    desbalance_ofi: float | None = None
    balancines: tuple[dict[str, Any] | BalancinItemV1, ...] = ()
    # Motor de Riesgo:
    drawdown_diario_pct: float | None = None
    limite_por_trade_pct: float | None = None
    slots_concurrentes_usados: int | None = None
    slots_concurrentes_max: int | None = None
    pnl_paper_acumulado: float | None = None
    # Linaje del corte y salud adicional:
    secuencia: int | None = None
    hash_snapshot: str | None = None
    salud_feed: str | None = None
    diagnostico_semaforo: dict[str, Any] | None = None
    market_data: dict[str, Any] | None = None
    market_assets: tuple[dict[str, Any], ...] = ()

    def to_dict(self) -> dict[str, Any]:
        def _serialize_item(item: Any) -> Any:
            if hasattr(item, "to_dict") and callable(item.to_dict):
                return item.to_dict()
            if hasattr(item, "payload") and item.payload is not None:
                return _serialize_item(item.payload)
            if isinstance(item, dict):
                return {k: _serialize_item(v) for k, v in item.items()}
            if isinstance(item, (list, tuple)):
                return [_serialize_item(x) for x in item]
            if isinstance(item, datetime):
                return _format_iso_utc(item)
            return item

        result: dict[str, Any] = {
            "schema_version": self.schema_version,
            "generated_at_utc": _format_iso_utc(self.generated_at_utc),
            "environment": self.environment,
            "instrument": self.instrument,
            "market_cutoff_utc": _format_iso_utc(self.market_cutoff_utc),
            "data_age_ms": self.data_age_ms,
            "health_state": self.health_state,
            "light": self.light,
            "direction": self.direction,
            "reason_codes": list(self.reason_codes),
            "model_id": self.model_id,
            "model_version": self.model_version,
            "model_hash": self.model_hash,
            "policy_version": self.policy_version,
            "transitions": [_serialize_item(t) for t in self.transitions],
            "simulations": [_serialize_item(s) for s in self.simulations],
            "metrics": [_serialize_item(m) for m in self.metrics],
            "incidents": [_serialize_item(i) for i in self.incidents],
            "kill_switch_active": self.kill_switch_active,
            "ui_state": self.ui_state,
            "as_of_event_id": self.as_of_event_id,
            "next_cursor": self.next_cursor,
            "session": self.session,
            # Telemetría densa
            "bid": self.bid,
            "ask": self.ask,
            "spread": self.spread,
            "mid_price": self.mid_price,
            "micro_price": self.micro_price,
            "beta_kalman": self.beta_kalman,
            "z_score": self.z_score,
            "desbalance_ofi": self.desbalance_ofi,
            "balancines": [_serialize_item(b) for b in self.balancines],
            "drawdown_diario_pct": self.drawdown_diario_pct,
            "limite_por_trade_pct": self.limite_por_trade_pct,
            "slots_concurrentes_usados": self.slots_concurrentes_usados,
            "slots_concurrentes_max": self.slots_concurrentes_max,
            "pnl_paper_acumulado": self.pnl_paper_acumulado,
            "secuencia": self.secuencia,
            "hash_snapshot": self.hash_snapshot,
            "salud_feed": self.salud_feed or self.health_state,
            "diagnostico_semaforo": _serialize_item(self.diagnostico_semaforo),
            "market_data": _serialize_item(self.market_data or {}),
            "market_assets": [_serialize_item(asset) for asset in self.market_assets],
        }
        return result

    def to_canonical_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"), allow_nan=False, ensure_ascii=False)

    def to_canonical_bytes(self) -> bytes:
        return self.to_canonical_json().encode("utf-8")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProyeccionLecturaV1":
        gen_at = _parse_iso_utc(data.get("generated_at_utc"))
        if gen_at is None:
            raise ValueError("generated_at_utc es requerido y no puede ser nulo")
        cutoff = _parse_iso_utc(data.get("market_cutoff_utc"))
        return cls(
            schema_version=int(data.get("schema_version", 1)),
            generated_at_utc=gen_at,
            environment=data["environment"],
            instrument=data.get("instrument", "US500"),
            market_cutoff_utc=cutoff,
            data_age_ms=data.get("data_age_ms"),
            health_state=str(data.get("health_state", "NO_DATA")),
            light=data["light"],
            direction=data["direction"],
            reason_codes=tuple(data.get("reason_codes", ())),
            model_id=data.get("model_id"),
            model_version=data.get("model_version"),
            model_hash=data.get("model_hash"),
            policy_version=str(data.get("policy_version", "policy-v1")),
            transitions=tuple(data.get("transitions", ())),
            simulations=tuple(data.get("simulations", ())),
            metrics=tuple(data.get("metrics", ())),
            incidents=tuple(data.get("incidents", ())),
            kill_switch_active=bool(data.get("kill_switch_active", False)),
            ui_state=data.get("ui_state", "vacio"),
            as_of_event_id=data.get("as_of_event_id"),
            next_cursor=data.get("next_cursor"),
            session=data.get("session"),
            bid=data.get("bid"),
            ask=data.get("ask"),
            spread=data.get("spread"),
            mid_price=data.get("mid_price"),
            micro_price=data.get("micro_price"),
            beta_kalman=data.get("beta_kalman"),
            z_score=data.get("z_score"),
            desbalance_ofi=data.get("desbalance_ofi"),
            balancines=tuple(data.get("balancines", ())),
            drawdown_diario_pct=data.get("drawdown_diario_pct"),
            limite_por_trade_pct=data.get("limite_por_trade_pct"),
            slots_concurrentes_usados=data.get("slots_concurrentes_usados"),
            slots_concurrentes_max=data.get("slots_concurrentes_max"),
            pnl_paper_acumulado=data.get("pnl_paper_acumulado"),
            secuencia=data.get("secuencia"),
            hash_snapshot=data.get("hash_snapshot"),
            salud_feed=data.get("salud_feed"),
            diagnostico_semaforo=data.get("diagnostico_semaforo"),
            market_data=data.get("market_data") or {},
            market_assets=tuple(data.get("market_assets", ())),
        )

    @classmethod
    def from_json(cls, json_data: str | bytes) -> "ProyeccionLecturaV1":
        if isinstance(json_data, bytes):
            json_data = json_data.decode("utf-8")
        return cls.from_dict(json.loads(json_data))


def validar_proyeccion_lectura_v1(
    proyeccion: ProyeccionLecturaV1, correlation_id: str = ""
) -> Resultado[ProyeccionLecturaV1]:
    """Valida exhaustivamente una ProyeccionLecturaV1 contra todas las invariantes de dominio."""
    if proyeccion.schema_version != 1:
        return fallo(
            ErrorDominio(
                codigo="SCHEMA_UNSUPPORTED",
                mensaje_seguro=f"Version de esquema no admitida: {proyeccion.schema_version}",
                reintentable=False,
                correlation_id=correlation_id,
                detalles={"schema_version": proyeccion.schema_version},
            )
        )

    # La lectura admite observación US500/GOLD; el motor operativo continúa sólo US500.
    inst_res = parse_instrument(proyeccion.instrument, correlation_id)
    if not inst_res.exito:
        return fallo(inst_res.error)

    # Entorno
    env_res = parse_environment(proyeccion.environment, correlation_id)
    if not env_res.exito:
        return fallo(env_res.error)

    # Health state
    if proyeccion.health_state not in VALID_HEALTH_STATES:
        return fallo(
            ErrorDominio(
                codigo="VALIDATION_ERROR",
                mensaje_seguro=f"Estado de salud invalido: {proyeccion.health_state}",
                reintentable=False,
                correlation_id=correlation_id,
                detalles={"health_state": proyeccion.health_state},
            )
        )

    # Luz
    light_res = parse_light(proyeccion.light, correlation_id)
    if not light_res.exito:
        return fallo(light_res.error)

    # Dirección canónica
    dir_res = parse_direccion_canonica(proyeccion.direction, correlation_id)
    if not dir_res.exito:
        return fallo(dir_res.error)

    # Invariantes de correspondencia Luz <-> Dirección canónica (RB-L001, CA-12)
    if proyeccion.light == "YELLOW" and proyeccion.direction != "MONITORIZAR":
        return fallo(
            ErrorDominio(
                codigo="VALIDATION_ERROR",
                mensaje_seguro="Luz YELLOW exige direccion MONITORIZAR",
                reintentable=False,
                correlation_id=correlation_id,
                detalles={"light": proyeccion.light, "direction": proyeccion.direction},
            )
        )
    if proyeccion.light == "GREEN" and proyeccion.direction != "LARGO":
        return fallo(
            ErrorDominio(
                codigo="VALIDATION_ERROR",
                mensaje_seguro="Luz GREEN exige direccion LARGO",
                reintentable=False,
                correlation_id=correlation_id,
                detalles={"light": proyeccion.light, "direction": proyeccion.direction},
            )
        )
    if proyeccion.light == "RED" and proyeccion.direction != "CORTO":
        return fallo(
            ErrorDominio(
                codigo="VALIDATION_ERROR",
                mensaje_seguro="Luz RED exige direccion CORTO",
                reintentable=False,
                correlation_id=correlation_id,
                detalles={"light": proyeccion.light, "direction": proyeccion.direction},
            )
        )

    # Invariantes de Amarillo Seguro (RF-L008, RB-L003, RB-L012)
    if proyeccion.environment == "NO_DATA" and proyeccion.light != "YELLOW":
        return fallo(
            ErrorDominio(
                codigo="VALIDATION_ERROR",
                mensaje_seguro="Entorno NO_DATA exige luz YELLOW (MONITORIZAR)",
                reintentable=False,
                correlation_id=correlation_id,
                detalles={"environment": proyeccion.environment, "light": proyeccion.light},
            )
        )
    if proyeccion.as_of_event_id is None and proyeccion.light != "YELLOW":
        return fallo(
            ErrorDominio(
                codigo="VALIDATION_ERROR",
                mensaje_seguro="Ausencia de evento de mercado exige luz YELLOW",
                reintentable=False,
                correlation_id=correlation_id,
                detalles={"as_of_event_id": proyeccion.as_of_event_id, "light": proyeccion.light},
            )
        )
    if (
        proyeccion.health_state in {"NO_DATA", "INITIALIZING", "STALE", "GAPPED", "ERROR", "STOPPED"}
        and proyeccion.light != "YELLOW"
    ):
        return fallo(
            ErrorDominio(
                codigo="VALIDATION_ERROR",
                mensaje_seguro=f"Estado de salud {proyeccion.health_state} exige luz YELLOW",
                reintentable=False,
                correlation_id=correlation_id,
                detalles={"health_state": proyeccion.health_state, "light": proyeccion.light},
            )
        )
    if (
        proyeccion.model_id is None or proyeccion.model_version is None or proyeccion.model_hash is None
    ) and proyeccion.light != "YELLOW":
        return fallo(
            ErrorDominio(
                codigo="VALIDATION_ERROR",
                mensaje_seguro="Ausencia de modelo campeon verificado exige luz YELLOW",
                reintentable=False,
                correlation_id=correlation_id,
                detalles={
                    "model_id": proyeccion.model_id,
                    "model_version": proyeccion.model_version,
                    "model_hash": proyeccion.model_hash,
                    "light": proyeccion.light,
                },
            )
        )
    if proyeccion.kill_switch_active and proyeccion.light != "YELLOW":
        return fallo(
            ErrorDominio(
                codigo="VALIDATION_ERROR",
                mensaje_seguro="Kill switch activo exige luz YELLOW",
                reintentable=False,
                correlation_id=correlation_id,
                detalles={"kill_switch_active": True, "light": proyeccion.light},
            )
        )

    # Invariantes de Tiempos y Causalidad (RNF-L013, OPT-7)
    if not _is_utc_datetime(proyeccion.generated_at_utc):
        return fallo(
            ErrorDominio(
                codigo="VALIDATION_ERROR",
                mensaje_seguro="generated_at_utc debe ser un datetime con zona horaria UTC",
                reintentable=False,
                correlation_id=correlation_id,
                detalles={},
            )
        )
    if proyeccion.market_cutoff_utc is not None:
        if not _is_utc_datetime(proyeccion.market_cutoff_utc):
            return fallo(
                ErrorDominio(
                    codigo="VALIDATION_ERROR",
                    mensaje_seguro="market_cutoff_utc debe ser un datetime con zona horaria UTC",
                    reintentable=False,
                    correlation_id=correlation_id,
                    detalles={},
                )
            )
        if proyeccion.generated_at_utc < proyeccion.market_cutoff_utc:
            return fallo(
                ErrorDominio(
                    codigo="VALIDATION_ERROR",
                    mensaje_seguro="generated_at_utc no puede ser anterior a market_cutoff_utc",
                    reintentable=False,
                    correlation_id=correlation_id,
                    detalles={
                        "generated_at_utc": str(proyeccion.generated_at_utc),
                        "market_cutoff_utc": str(proyeccion.market_cutoff_utc),
                    },
                )
            )

    # Invariantes de Hashes y UUIDs
    if proyeccion.model_hash is not None and not _is_valid_hash(proyeccion.model_hash):
        return fallo(
            ErrorDominio(
                codigo="VALIDATION_ERROR",
                mensaje_seguro="model_hash debe ser SHA-256 de 64 hex caracteres",
                reintentable=False,
                correlation_id=correlation_id,
                detalles={"model_hash": proyeccion.model_hash},
            )
        )
    if proyeccion.as_of_event_id is not None and not _is_valid_uuid(proyeccion.as_of_event_id):
        return fallo(
            ErrorDominio(
                codigo="VALIDATION_ERROR",
                mensaje_seguro="as_of_event_id debe ser un UUID valido",
                reintentable=False,
                correlation_id=correlation_id,
                detalles={"as_of_event_id": proyeccion.as_of_event_id},
            )
        )

    # data_age_ms
    if proyeccion.data_age_ms is not None:
        if not isinstance(proyeccion.data_age_ms, int) or proyeccion.data_age_ms < 0:
            return fallo(
                ErrorDominio(
                    codigo="VALIDATION_ERROR",
                    mensaje_seguro="data_age_ms debe ser un entero no negativo",
                    reintentable=False,
                    correlation_id=correlation_id,
                    detalles={"data_age_ms": str(proyeccion.data_age_ms)},
                )
            )
        if proyeccion.data_age_ms > 5000 and proyeccion.light != "YELLOW":
            return fallo(
                ErrorDominio(
                    codigo="VALIDATION_ERROR",
                    mensaje_seguro="data_age_ms > 5000ms (datos obsoletos) exige luz YELLOW",
                    reintentable=False,
                    correlation_id=correlation_id,
                    detalles={"data_age_ms": proyeccion.data_age_ms, "light": proyeccion.light},
                )
            )

    # ui_state
    ui_res = parse_estado_ui(proyeccion.ui_state, correlation_id)
    if not ui_res.exito:
        return fallo(ui_res.error)

    # policy_version
    if not isinstance(proyeccion.policy_version, str) or not proyeccion.policy_version.strip():
        return fallo(
            ErrorDominio(
                codigo="VALIDATION_ERROR",
                mensaje_seguro="policy_version debe ser una cadena no vacia",
                reintentable=False,
                correlation_id=correlation_id,
                detalles={},
            )
        )

    return exito(proyeccion)


__all__ = [
    "BalancinItemV1",
    "ProyeccionLecturaV1",
    "VALID_HEALTH_STATES",
    "validar_proyeccion_lectura_v1",
]
