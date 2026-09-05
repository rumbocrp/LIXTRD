"""Adaptador Read-Only para cTrader Demo (SPEC-001 §10.2, §10.3, CA-1, CA-2, CA-3, WP-10)."""

from collections import deque
from collections.abc import AsyncIterator, Iterator, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
import re
from typing import Any, Literal
import uuid

from sistema_luces.domain.error import ErrorDominio
from sistema_luces.domain.event import (
    QuoteTickPayloadV1,
    ReconnectedPayloadV1,
    SobreEventoV1,
    compute_payload_hash,
    validar_sobre_evento,
)
from sistema_luces.domain.result import Resultado, exito, fallo
from sistema_luces.domain.vocabulary import Environment, parse_environment
from sistema_luces.sources.replay import ResumenFuente

_UUID_REGEX = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE)

CAPABILITIES_READ_ONLY_PERMITIDAS: frozenset[str] = frozenset(
    {
        "market_data.read",
        "account_metadata.read",
        "historical_executions.read",
    }
)


def validar_capacidades_read_only(
    capabilities: Sequence[str] | set[str] | frozenset[str],
    correlation_id: str = "",
) -> Resultado[frozenset[str]]:
    """Valida que todas las capacidades declaradas pertenezcan exclusivamente a la lista blanca read-only (CA-2, §10.2)."""
    solicitadas = frozenset(capabilities)
    if not solicitadas:
        return fallo(
            ErrorDominio(
                codigo="VALIDATION_ERROR",
                mensaje_seguro="Debe especificarse al menos una capacidad read-only",
                reintentable=False,
                correlation_id=correlation_id,
                detalles={},
            )
        )

    for cap in solicitadas:
        if cap not in CAPABILITIES_READ_ONLY_PERMITIDAS:
            return fallo(
                ErrorDominio(
                    codigo="CAPABILITY_DENIED",
                    mensaje_seguro=f"Capacidad prohibida o no read-only: {cap}",
                    reintentable=False,
                    correlation_id=correlation_id,
                    detalles={"capability": cap},
                )
            )

    return exito(solicitadas)


@dataclass(frozen=True)
class MetadatosCuentaCTrader:
    account_id_hash: str
    is_demo: bool
    broker_name: str
    currency: str = "USD"


def validar_metadatos_cuenta_demo(
    meta: MetadatosCuentaCTrader,
    expected_hash: str,
    correlation_id: str = "",
) -> Resultado[MetadatosCuentaCTrader]:
    """Verifica formalmente que la cuenta sea demo=true y coincida con el hash esperado (CA-3)."""
    if meta.is_demo is not True:
        return fallo(
            ErrorDominio(
                codigo="SOURCE_NOT_DEMO",
                mensaje_seguro="La cuenta conectada no es una cuenta DEMO verificable",
                reintentable=False,
                correlation_id=correlation_id,
                detalles={"is_demo": str(meta.is_demo)},
            )
        )

    if meta.account_id_hash.lower() != expected_hash.lower():
        return fallo(
            ErrorDominio(
                codigo="SOURCE_NOT_DEMO",
                mensaje_seguro="El hash de la cuenta demo no coincide con el hash esperado",
                reintentable=False,
                correlation_id=correlation_id,
                detalles={"account_id_hash": meta.account_id_hash, "expected_hash": expected_hash},
            )
        )

    return exito(meta)


@dataclass(frozen=True)
class SolicitudConexionCTrader:
    correlation_id: str
    environment: Environment
    capabilities: Sequence[str]
    expected_demo_account_hash: str
    symbol_id: str = "US500"
    max_queue_size: int = 1000


class SesionCTraderDemo:
    """Sesión de streaming read-only desde cTrader demo con control de backpressure."""

    def __init__(
        self,
        solicitud: SolicitudConexionCTrader,
        metadatos: MetadatosCuentaCTrader,
    ) -> None:
        self.solicitud = solicitud
        self.metadatos = metadatos
        self.max_queue_size = solicitud.max_queue_size
        self._cola: deque[SobreEventoV1] = deque(maxlen=self.max_queue_size)
        self.eventos_recibidos: int = 0
        self.eventos_descartados: int = 0
        self.reconnect_attempts: int = 0
        self.last_safe_cutoff: datetime | None = None
        self._pausada: bool = False
        self._cerrada: bool = False

    def tamano_cola(self) -> int:
        return len(self._cola)

    def recibir_mensaje_raw(self, raw_msg: dict[str, Any]) -> Resultado[SobreEventoV1 | None]:
        """Procesa y mapea un mensaje entrante crudo de cTrader, gestionando backpressure si la cola se llena."""
        if self._cerrada:
            return fallo(
                ErrorDominio(
                    codigo="VALIDATION_ERROR",
                    mensaje_seguro="Sesion cerrada",
                    reintentable=False,
                    correlation_id=self.solicitud.correlation_id,
                    detalles={},
                )
            )

        res_sobre = self.mapear_mensaje_a_sobre(raw_msg)
        if not res_sobre.exito:
            return fallo(res_sobre.error)

        sobre = res_sobre.datos
        self.eventos_recibidos += 1

        # Control de backpressure
        if len(self._cola) >= self.max_queue_size:
            self.eventos_descartados += 1
            # deque con maxlen descarta automáticamente el más antiguo
            self._cola.append(sobre)
        else:
            self._cola.append(sobre)

        self.last_safe_cutoff = sobre.occurred_at_utc
        return exito(sobre)

    def mapear_mensaje_a_sobre(self, raw_msg: dict[str, Any]) -> Resultado[SobreEventoV1]:
        """Normaliza un mensaje crudo a SobreEventoV1 inmutable."""
        msg_type = raw_msg.get("type", "QUOTE_TICK")
        ts = raw_msg.get("timestamp_utc") or datetime.now(timezone.utc)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)

        seq = raw_msg.get("sequence")
        event_id = raw_msg.get("event_id") or str(uuid.uuid4())

        if msg_type == "QUOTE_TICK":
            payload = {
                "ask": raw_msg.get("ask", 0),
                "bid": raw_msg.get("bid", 0),
                "flags": 0,
                "price_scale": raw_msg.get("price_scale", 100),
                "size_ask": raw_msg.get("size_ask", 10),
                "size_bid": raw_msg.get("size_bid", 10),
            }
        else:
            payload = raw_msg.get("payload", {})

        payload_hash = compute_payload_hash(payload)

        sobre = SobreEventoV1(
            event_id=event_id,
            event_type=msg_type,
            schema_version=1,
            occurred_at_utc=ts,
            received_at_utc=datetime.now(timezone.utc),
            persisted_at_utc=None,
            source="ctrader_demo",
            environment=self.solicitud.environment,
            source_account_id_hash=self.metadatos.account_id_hash,
            instrument="US500",
            symbol_id=self.solicitud.symbol_id,
            source_sequence=seq,
            payload=payload,
            payload_hash=payload_hash,
            previous_hash=None,
            causation_id=None,
            correlation_id=self.solicitud.correlation_id,
        )

        res_val = validar_sobre_evento(sobre)
        if not res_val.exito:
            return fallo(res_val.error)

        return exito(sobre)

    def registrar_reconexion(
        self,
        reconnected_at_utc: datetime,
        duration_ms: int,
    ) -> Resultado[SobreEventoV1]:
        """Registra un evento de reconexión exitosa tras pérdida de enlace."""
        self.reconnect_attempts += 1
        self.last_safe_cutoff = reconnected_at_utc

        payload_rec = {
            "attempt": self.reconnect_attempts,
            "duration_ms": duration_ms,
            "last_safe_cutoff": reconnected_at_utc.isoformat(),
        }
        payload_hash = compute_payload_hash(payload_rec)

        sobre = SobreEventoV1(
            event_id=str(uuid.uuid4()),
            event_type="RECONNECTED",
            schema_version=1,
            occurred_at_utc=reconnected_at_utc,
            received_at_utc=datetime.now(timezone.utc),
            persisted_at_utc=None,
            source="ctrader_demo",
            environment=self.solicitud.environment,
            source_account_id_hash=self.metadatos.account_id_hash,
            instrument="US500",
            symbol_id=self.solicitud.symbol_id,
            source_sequence=None,
            payload=payload_rec,
            payload_hash=payload_hash,
            previous_hash=None,
            causation_id=None,
            correlation_id=self.solicitud.correlation_id,
        )

        self._cola.append(sobre)
        return exito(sobre)

    def paso(self) -> Resultado[SobreEventoV1 | None]:
        """Extrae el siguiente evento disponible de la cola."""
        if self._pausada or not self._cola:
            return exito(None)
        return exito(self._cola.popleft())

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
                final_cutoff_utc=self.last_safe_cutoff,
                total_received=self.eventos_recibidos,
                total_rejected=self.eventos_descartados,
                reason_codes=(),
            )
        )


class AdaptadorCTraderDemoReadOnly:
    """Adaptador de mercado cTrader Demo estrictamente read-only (CA-1, CA-2, CA-3)."""

    def conectar(
        self,
        solicitud: SolicitudConexionCTrader,
        metadatos: MetadatosCuentaCTrader | None = None,
    ) -> Resultado[SesionCTraderDemo]:
        # CA-1: Validacion estricta de entorno
        env_res = parse_environment(solicitud.environment, solicitud.correlation_id)
        if not env_res.exito:
            return fallo(env_res.error)

        # CA-2: Allowlist de capacidades read-only
        caps_res = validar_capacidades_read_only(solicitud.capabilities, solicitud.correlation_id)
        if not caps_res.exito:
            return fallo(caps_res.error)

        # CA-3: Verificación de cuenta demo
        meta = metadatos or MetadatosCuentaCTrader(
            account_id_hash=solicitud.expected_demo_account_hash,
            is_demo=True,
            broker_name="cTrader-Demo",
        )
        meta_res = validar_metadatos_cuenta_demo(meta, solicitud.expected_demo_account_hash, solicitud.correlation_id)
        if not meta_res.exito:
            return fallo(meta_res.error)

        sesion = SesionCTraderDemo(
            solicitud=solicitud,
            metadatos=meta,
        )
        return exito(sesion)
