"""Proyecciones de lectura reconstruibles desde el event log (SPEC-001 §9.1, CA-21, Milestone 2 & 3).

FASE 1: Soporte multi-activo para US500, XAUUSD, TSLA, AAPL con proyector por instrumento.
"""

from datetime import datetime, timezone
import hashlib
import threading
from typing import Any, Dict, Literal
import uuid

from sistema_luces.config.multi_asset_config import (
    CONFIGURACION_INSTRUMENTOS,
    INSTRUMENTOS_PERMITIDOS,
    obtener_config_instrumento,
)
from sistema_luces.domain.api import (
    BalancinItemV1,
    DocumentoVistaV1,
    SolicitudConsulta,
    VistaLectura,
    validar_documento_vista,
    validar_solicitud_consulta,
)
from sistema_luces.domain.error import ErrorDominio
from sistema_luces.domain.event import SobreEventoV1, canonical_json_bytes
from sistema_luces.domain.result import Resultado, exito, fallo
from sistema_luces.domain.vocabulary import Light


_RELACIONES_PERMITIDAS = frozenset({"SP500_TSLA", "SP500_AAPL", "GOLD_DXY", "US500_COMPOSITE"})
_SIMBOLOS_MERCADO_PERMITIDOS = ("^GSPC", "TSLA", "AAPL", "GC=F")
_MAX_DOCUMENTOS_POR_VISTA = 1000


def _porcentaje_escalado(valor: object) -> float | None:
    """Normaliza probabilidades 0..1 o enteros en millonésimas a porcentaje 0..100."""
    if not isinstance(valor, (int, float)) or isinstance(valor, bool):
        return None
    numero = float(valor)
    if numero < 0:
        return None
    if numero <= 1:
        numero *= 100.0
    elif numero > 100:
        numero /= 10_000.0
    return round(min(100.0, numero), 4)


def _diagnostico_desde_senal(payload: dict[str, Any], event_id: str) -> dict[str, Any] | None:
    prob_long = _porcentaje_escalado(
        payload.get("calibrated_probability_long", payload.get("prob_long"))
    )
    prob_short = _porcentaje_escalado(
        payload.get("calibrated_probability_short", payload.get("prob_short"))
    )
    threshold_green = _porcentaje_escalado(payload.get("threshold_green"))
    threshold_red = _porcentaje_escalado(payload.get("threshold_red"))
    if prob_long is None and prob_short is None:
        return None
    if prob_long is None and prob_short is not None:
        prob_long = round(100.0 - prob_short, 4)
    if prob_short is None and prob_long is not None:
        prob_short = round(100.0 - prob_long, 4)
    # La política V1 usa estos umbrales; se identifican explícitamente como fallback.
    threshold_source = "signal-payload"
    if threshold_green is None:
        threshold_green = 65.0
        threshold_source = "policy-v1-default"
    if threshold_red is None:
        threshold_red = 35.0
        threshold_source = "policy-v1-default"
    assert prob_long is not None and prob_short is not None
    return {
        "probability_long_pct": prob_long,
        "probability_short_pct": prob_short,
        "threshold_green_pct": threshold_green,
        "threshold_red_pct": threshold_red,
        "distance_to_green_pp": round(threshold_green - prob_long, 4),
        "distance_to_red_pp": round(prob_long - threshold_red, 4),
        "threshold_source": threshold_source,
        "source_event_id": event_id,
    }


def _diagnostico_activo_validado(value: object) -> dict[str, Any] | None:
    """Acepta un diagnóstico por activo sólo cuando trae probabilidades y umbrales completos."""
    if not isinstance(value, dict):
        return None
    keys = (
        "probability_long_pct",
        "probability_short_pct",
        "threshold_green_pct",
        "threshold_red_pct",
    )
    numbers = [value.get(key) for key in keys]
    if not all(isinstance(number, (int, float)) and not isinstance(number, bool) for number in numbers):
        return None
    if not all(0 <= float(number) <= 100 for number in numbers):
        return None
    if float(value["threshold_red_pct"]) > float(value["threshold_green_pct"]):
        return None
    return dict(value)


class ProyectorVistas:
    """Mantiene y reconstruye proyecciones de lectura y telemetría a partir de hechos persistidos.
    
    FASE 1: Soporte multi-activo - cada instancia maneja UN instrumento específico.
    El servidor UI debe mantener un diccionario de proyectores por instrumento.
    """

    def __init__(self, instrumento: str = "US500") -> None:
        if instrumento not in INSTRUMENTOS_PERMITIDOS:
            raise ValueError(
                f"Instrumento '{instrumento}' no permitido. "
                f"Opciones válidas: {sorted(INSTRUMENTOS_PERMITIDOS)}"
            )
        
        self._instrument = instrumento
        self._config = obtener_config_instrumento(instrumento)
        self._lock = threading.RLock()
        self._documentos_por_vista: dict[str, list[dict[str, Any]]] = {
            "FEED": [],
            "LIGHTS": [],
            "SIGNALS": [],
            "SIMULATIONS": [],
            "METRICS": [],
            "SECURITY": [],
            "TRACE": [],
            "IMPORTS": [],
        }
        self._current_light: Light = "YELLOW"
        self._health_state: str = "NO_DATA"
        self._last_event_id: str | None = None
        self._last_environment: str | None = None
        self._last_cutoff_utc: datetime | None = None
        self._last_market_cutoff_utc: datetime | None = None
        self._last_market_received_at_utc: datetime | None = None
        self._last_data_age_ms: int | None = None
        self._current_model_id: str | None = None
        self._current_model_version: str | None = None
        self._current_model_hash: str | None = None
        self._current_policy_version: str = "policy-v1"
        self._kill_switch_active: bool = False

        # Telemetría cuantitativa densa
        self._last_bid: float | None = None
        self._last_ask: float | None = None
        self._last_spread: float | None = None
        self._last_mid_price: float | None = None
        self._last_micro_price: float | None = None
        self._last_beta_kalman: float | None = None
        self._last_z_score: float | None = None
        self._last_ofi: float | None = None
        self._balancines_data: list[dict[str, Any]] = []
        self._diagnostico_semaforo: dict[str, Any] | None = None
        self._secuencia: int | None = None
        self._hash_snapshot: str | None = None
        self._slots_usados: int | None = None
        self._slots_max: int | None = None
        self._pnl_paper_acumulado: float | None = None
        self._drawdown_diario_pct: float | None = None
        self._limite_por_trade_pct: float | None = None
        self._market_data: dict[str, Any] = {}
        self._market_assets_by_symbol: dict[str, dict[str, Any]] = {}
        self._source_reason_codes: tuple[str, ...] = ()

    def actualizar_desde_evento(self, evento: SobreEventoV1) -> Resultado[None]:
        """Aplica un evento bajo bloqueo para servir snapshots coherentes entre threads."""
        with self._lock:
            return self._actualizar_desde_evento_sin_bloqueo(evento)

    def _actualizar_desde_evento_sin_bloqueo(self, evento: SobreEventoV1) -> Resultado[None]:
        """Aplica un evento atómico a las proyecciones correspondientes."""
        if evento.instrument != self._instrument:
            return fallo(
                ErrorDominio(
                    codigo="INSTRUMENT_NOT_ALLOWED",
                    mensaje_seguro="El evento no pertenece al instrumento de este proyector",
                    reintentable=False,
                    correlation_id=evento.correlation_id,
                    detalles={
                        "instrumento_proyector": self._instrument,
                        "instrumento_evento": evento.instrument,
                    },
                )
            )
        self._last_event_id = evento.event_id
        self._last_environment = evento.environment
        self._last_cutoff_utc = evento.occurred_at_utc
        if evento.source_sequence is not None:
            self._secuencia = evento.source_sequence
        if evento.payload_hash:
            self._hash_snapshot = evento.payload_hash

        if evento.event_type == "QUOTE_TICK":
            self._health_state = "HEALTHY"
            payload = evento.payload if isinstance(evento.payload, dict) else {}
            self._documentos_por_vista["FEED"].append(payload)

            # Extraer precio del payload (puede venir como last_price_scaled o directamente como precio)
            last_price_scaled = payload.get("last_price_scaled")
            price_scale = payload.get("price_scale", 100) or 100
            
            if last_price_scaled is not None:
                # Convertir precio escalado a USD
                last_price_usd = float(last_price_scaled) / float(price_scale)
                self._last_mid_price = round(last_price_usd, 2)
                
                # Guardar en market_data para referencia
                self._market_data["last_price"] = last_price_usd
                self._market_data["provider"] = payload.get("provider", "unknown")
                self._market_data["provider_symbol"] = payload.get("provider_symbol", "")
            
            # Si hay bid/ask, usar lógica completa
            bid = payload.get("bid")
            ask = payload.get("ask")
            if bid is not None and ask is not None:
                b_usd = float(bid) / float(scale)
                a_usd = float(ask) / float(scale)
                self._last_bid = round(b_usd, 2)
                self._last_ask = round(a_usd, 2)
                self._last_spread = round(a_usd - b_usd, 2)
                mid = (b_usd + a_usd) / 2.0
                self._last_mid_price = round(mid, 2)

                bid_size = payload.get("size_bid", payload.get("bid_size"))
                ask_size = payload.get("size_ask", payload.get("ask_size"))
                if isinstance(bid_size, (int, float)) and isinstance(ask_size, (int, float)):
                    b_sz = float(bid_size)
                    a_sz = float(ask_size)
                    total_size = b_sz + a_sz
                    if total_size > 0:
                        micro = (b_usd * a_sz + a_usd * b_sz) / total_size
                        self._last_micro_price = round(micro, 2)
                        self._last_ofi = round(b_sz - a_sz, 1)
                    else:
                        self._last_micro_price = None
                        self._last_ofi = None
                else:
                    self._last_micro_price = None
                    self._last_ofi = None

        elif evento.event_type == "INDEX_MARKET_SNAPSHOT":
            payload = evento.payload if isinstance(evento.payload, dict) else {}
            self._health_state = "HEALTHY"
            self._current_light = "YELLOW"
            self._last_market_cutoff_utc = evento.occurred_at_utc
            self._last_market_received_at_utc = evento.received_at_utc
            self._documentos_por_vista["FEED"].append(payload)

            price_scale = payload.get("price_scale")
            percent_scale = payload.get("percent_scale")
            if not isinstance(price_scale, int) or price_scale <= 0:
                price_scale = 100
            if not isinstance(percent_scale, int) or percent_scale <= 0:
                percent_scale = 100_000
            market_data = dict(self._market_data)
            for key in (
                "provider",
                "provider_url",
                "provider_symbol",
                "display_name",
                "instrument_type",
                "quote_scope",
                "currency",
                "exchange",
                "exchange_timezone",
                "source_timestamp_utc",
                "received_at_utc",
                "market_state",
                "transport",
                "data_granularity",
                "quote_status",
                "fetch_latency_ms",
                "source_to_receive_ms",
                "day_volume",
            ):
                if key in payload and payload[key] is not None:
                    market_data[key] = payload[key]
            price_fields = {
                "last_price_scaled": "last_price",
                "previous_close_scaled": "previous_close",
                "day_open_scaled": "day_open",
                "day_high_scaled": "day_high",
                "day_low_scaled": "day_low",
                "change_scaled": "change",
                "bid_scaled": "bid",
                "ask_scaled": "ask",
            }
            for scaled_key, view_key in price_fields.items():
                value = payload.get(scaled_key)
                if isinstance(value, int) and not isinstance(value, bool):
                    market_data[view_key] = round(value / price_scale, 6)
            change_pct = payload.get("change_pct_scaled")
            if isinstance(change_pct, int) and not isinstance(change_pct, bool):
                market_data["change_pct"] = round(change_pct / percent_scale, 6)
            self._market_data = market_data
            if len(self._documentos_por_vista["FEED"]) > _MAX_DOCUMENTOS_POR_VISTA:
                del self._documentos_por_vista["FEED"][:-_MAX_DOCUMENTOS_POR_VISTA]

            # Una cotización pública no ofrece precios ejecutables ni certifica un modelo.
            self._last_bid = market_data.get("bid")
            self._last_ask = market_data.get("ask")
            self._last_spread = None
            self._last_mid_price = None
            self._last_micro_price = None
            self._last_ofi = None
            self._balancines_data = []
            self._diagnostico_semaforo = None
            reasons = [
                "PUBLIC_INDEX_PRICE_ONLY",
                "NO_EXECUTABLE_BID_ASK",
                "NO_CHAMPION_MODEL",
                "YAHOO_DELAY_UNDISCLOSED",
            ]
            if market_data.get("market_state") == "CLOSED":
                reasons.append("MARKET_CLOSED")
            self._source_reason_codes = tuple(reasons)

        elif evento.event_type == "CROSS_ASSET_SNAPSHOT":
            payload = evento.payload if isinstance(evento.payload, dict) else {}
            assets = payload.get("assets", [])
            if isinstance(assets, list):
                for raw_asset in assets:
                    if not isinstance(raw_asset, dict):
                        continue
                    symbol = str(raw_asset.get("provider_symbol", ""))
                    if symbol not in _SIMBOLOS_MERCADO_PERMITIDOS:
                        continue
                    price_scale = raw_asset.get("price_scale", 100)
                    percent_scale = raw_asset.get("percent_scale", 100_000)
                    if not isinstance(price_scale, int) or price_scale <= 0:
                        price_scale = 100
                    if not isinstance(percent_scale, int) or percent_scale <= 0:
                        percent_scale = 100_000
                    normalized = dict(self._market_assets_by_symbol.get(symbol, {}))
                    for key in (
                        "provider",
                        "provider_url",
                        "provider_symbol",
                        "display_name",
                        "instrument_type",
                        "quote_scope",
                        "currency",
                        "exchange",
                        "exchange_timezone",
                        "source_timestamp_utc",
                        "received_at_utc",
                        "market_state",
                        "transport",
                        "data_granularity",
                        "quote_status",
                        "fetch_latency_ms",
                        "source_to_receive_ms",
                        "day_volume",
                    ):
                        if key in raw_asset and raw_asset[key] is not None:
                            normalized[key] = raw_asset[key]
                    for scaled_key, view_key in {
                        "last_price_scaled": "last_price",
                        "previous_close_scaled": "previous_close",
                        "day_open_scaled": "day_open",
                        "day_high_scaled": "day_high",
                        "day_low_scaled": "day_low",
                        "change_scaled": "change",
                    }.items():
                        value = raw_asset.get(scaled_key)
                        if isinstance(value, int) and not isinstance(value, bool):
                            normalized[view_key] = round(value / price_scale, 6)
                    change_pct = raw_asset.get("change_pct_scaled")
                    if isinstance(change_pct, int) and not isinstance(change_pct, bool):
                        normalized["change_pct"] = round(change_pct / percent_scale, 6)
                    diagnostic = _diagnostico_activo_validado(raw_asset.get("diagnostico_semaforo"))
                    if diagnostic is not None:
                        normalized["diagnostico_semaforo"] = diagnostic
                    self._market_assets_by_symbol[symbol] = normalized
                if self._market_assets_by_symbol:
                    self._health_state = "HEALTHY"
                    self._current_light = "YELLOW"
                    reasons = list(self._source_reason_codes)
                    for reason in (
                        "PUBLIC_MULTI_ASSET_QUOTES_ONLY",
                        "NO_CHAMPION_MODEL",
                        "YAHOO_DELAY_UNDISCLOSED",
                    ):
                        if reason not in reasons:
                            reasons.append(reason)
                    partial_failures = payload.get("partial_failures")
                    if (
                        isinstance(partial_failures, list)
                        and partial_failures
                        and "YAHOO_PARTIAL_ASSET_FAILURE" not in reasons
                    ):
                        reasons.append("YAHOO_PARTIAL_ASSET_FAILURE")
                    self._source_reason_codes = tuple(reasons)
            relations = payload.get("relations", [])
            source_name = str(payload.get("source_name", "")) or None
            data_age_ms = payload.get("data_age_ms")
            parsed: list[dict[str, Any]] = []
            if isinstance(relations, list):
                for raw_relation in relations:
                    if not isinstance(raw_relation, dict):
                        continue
                    key = str(raw_relation.get("key", ""))
                    if key not in _RELACIONES_PERMITIDAS:
                        continue
                    enriched = dict(raw_relation)
                    enriched["source_name"] = enriched.get("source_name") or source_name
                    enriched["data_age_ms"] = enriched.get("data_age_ms", data_age_ms)
                    relation_source = enriched.get("source_name")
                    relation_age = enriched.get("data_age_ms")
                    if not isinstance(relation_source, str) or not relation_source.strip():
                        continue
                    if not isinstance(relation_age, (int, float)) or isinstance(relation_age, bool) or relation_age < 0:
                        continue
                    parsed.append(BalancinItemV1.from_dict(enriched).to_dict())
            self._balancines_data = parsed
            self._last_beta_kalman = payload.get("beta_kalman")
            self._last_z_score = payload.get("z_score")
            self._documentos_por_vista["METRICS"].append(payload)

        elif evento.event_type in {"STALE", "GAPPED", "OUT_OF_ORDER", "CLOCK_ROLLBACK"}:
            self._health_state = "STALE" if evento.event_type == "STALE" else "GAPPED"
            self._current_light = "YELLOW"
            self._documentos_por_vista["FEED"].append(evento.payload if isinstance(evento.payload, dict) else {})
        elif evento.event_type == "CASE_CREATED":
            payload = evento.payload if isinstance(evento.payload, dict) else {}
            if "feature_snapshot_hash" in payload:
                self._hash_snapshot = payload["feature_snapshot_hash"]
        elif evento.event_type == "SIGNAL_EMITTED":
            payload = evento.payload if isinstance(evento.payload, dict) else {}
            self._documentos_por_vista["SIGNALS"].append(payload)
            luz = str(payload.get("light", "YELLOW"))
            if luz in {"YELLOW", "GREEN", "RED"}:
                self._current_light = luz  # type: ignore[assignment]
            if "model_id" in payload:
                self._current_model_id = payload.get("model_id")
            if "model_version" in payload:
                self._current_model_version = payload.get("model_version")
            if "model_hash" in payload:
                self._current_model_hash = payload.get("model_hash")
            self._diagnostico_semaforo = _diagnostico_desde_senal(payload, evento.event_id)
        elif evento.event_type == "SIM_OPENED":
            payload = evento.payload if isinstance(evento.payload, dict) else {}
            self._documentos_por_vista["SIMULATIONS"].append(payload)
            self._slots_usados = (self._slots_usados or 0) + 1
            if isinstance(payload.get("slots_concurrentes_max"), int):
                self._slots_max = payload["slots_concurrentes_max"]
        elif evento.event_type == "SIM_CLOSED":
            payload = evento.payload if isinstance(evento.payload, dict) else {}
            self._documentos_por_vista["SIMULATIONS"].append(payload)
            self._slots_usados = max(0, (self._slots_usados or 0) - 1)
            net_pnl = payload.get("net_pnl", 0)
            if isinstance(net_pnl, (int, float)):
                self._pnl_paper_acumulado = round(
                    (self._pnl_paper_acumulado or 0.0) + float(net_pnl) / 100.0,
                    2,
                )
        elif evento.event_type == "SIM_PROPOSED":
            self._documentos_por_vista["SIMULATIONS"].append(evento.payload if isinstance(evento.payload, dict) else {})
        elif evento.event_type in {"IMPORT_ACCEPTED", "IMPORT_REJECTED", "RECONCILIATION_UPDATED"}:
            self._documentos_por_vista["IMPORTS"].append(evento.payload if isinstance(evento.payload, dict) else {})
        elif evento.event_type in {"KILL_SWITCH", "RISK_LIMIT_HIT"}:
            self._documentos_por_vista["SECURITY"].append(evento.payload if isinstance(evento.payload, dict) else {})
            if evento.event_type == "KILL_SWITCH":
                self._kill_switch_active = True
                self._current_light = "YELLOW"
        elif evento.event_type in {"MODEL_PROMOTED", "MODEL_REGISTERED"}:
            payload = evento.payload if isinstance(evento.payload, dict) else {}
            self._current_model_id = payload.get("model_id", self._current_model_id)
            self._current_model_version = payload.get("model_version", self._current_model_version)
            self._current_model_hash = payload.get("model_hash", self._current_model_hash)

        return exito(None)

    def reconstruir(self, eventos: list[SobreEventoV1]) -> Resultado[dict[str, int]]:
        """Reconstruye todas las vistas desde cero procesando la secuencia ordenada de eventos."""
        self.__init__()
        for ev in eventos:
            self.actualizar_desde_evento(ev)
        return exito({k: len(v) for k, v in self._documentos_por_vista.items()})

    def consultar(self, solicitud: SolicitudConsulta) -> Resultado[VistaLectura]:
        """Construye una vista coherente bajo el mismo bloqueo usado por la ingesta."""
        with self._lock:
            return self._consultar_sin_bloqueo(solicitud)

    def _consultar_sin_bloqueo(self, solicitud: SolicitudConsulta) -> Resultado[VistaLectura]:
        """Genera una VistaLectura inmutable con DocumentoVistaV1 y telemetría cuantitativa."""
        val_sol = validar_solicitud_consulta(solicitud)
        if not val_sol.exito:
            return fallo(val_sol.error)

        raw_docs = self._documentos_por_vista.get(solicitud.view, [])
        paginated_raw = raw_docs[: solicitud.limit]

        docs: list[DocumentoVistaV1] = []
        now_utc = datetime.now(timezone.utc)

        for payload in paginated_raw:
            c_bytes = canonical_json_bytes(payload)
            c_hash = hashlib.sha256(c_bytes).hexdigest()

            doc = DocumentoVistaV1(
                schema_id="sistema-luces/metric-snapshot-v1",
                document_hash=c_hash,
                canonical_json_utf8=c_bytes,
                view_id=str(uuid.uuid4()),
                view_name=solicitud.view,
                environment=(self._last_environment or solicitud.environment),
                as_of_event_id=self._last_event_id,
                generated_at_utc=now_utc,
                canonical_json_hash=c_hash,
                payload=payload,
            )
            docs.append(doc)

        has_data = bool(self._last_event_id)
        health = self._health_state if has_data else "NO_DATA"
        light: Light = self._current_light if has_data else "YELLOW"
        reasons_list: list[str] = []
        if not has_data:
            reasons_list.append("NO_DATA_YELLOW")
        elif health != "HEALTHY":
            reasons_list.append(f"FEED_{health}_YELLOW")
        if self._kill_switch_active:
            reasons_list.append("KILL_SWITCH_ACTIVE")
        reasons_list.extend(code for code in self._source_reason_codes if code not in reasons_list)
        reasons = tuple(reasons_list)
        env = self._last_environment if has_data and self._last_environment else "NO_DATA"

        age_ms: int | None = None
        effective_cutoff = self._last_market_cutoff_utc or self._last_cutoff_utc
        if effective_cutoff:
            age_ms = max(0, int((now_utc - effective_cutoff).total_seconds() * 1000))
        self._last_data_age_ms = age_ms

        ui_state: Any = "vacio"
        if has_data:
            if health == "HEALTHY":
                ui_state = "parcial" if self._market_data else "exito"
            elif health in {"STALE", "GAPPED"}:
                ui_state = "obsoleto"
            elif self._kill_switch_active:
                ui_state = "error"
            else:
                ui_state = "parcial"

        market_data = dict(self._market_data)
        if market_data:
            market_data["data_age_ms"] = age_ms
            if self._last_market_received_at_utc is not None:
                market_data["connection_age_ms"] = max(
                    0,
                    int((now_utc - self._last_market_received_at_utc).total_seconds() * 1000),
                )

        market_assets: list[dict[str, Any]] = []
        for symbol in _SIMBOLOS_MERCADO_PERMITIDOS:
            asset = self._market_assets_by_symbol.get(symbol)
            if asset is None:
                continue
            current = dict(asset)
            source_timestamp = current.get("source_timestamp_utc")
            if isinstance(source_timestamp, str):
                try:
                    parsed_source = datetime.fromisoformat(source_timestamp.replace("Z", "+00:00"))
                    current["data_age_ms"] = max(0, int((now_utc - parsed_source).total_seconds() * 1000))
                except ValueError:
                    current["data_age_ms"] = None
            received_timestamp = current.get("received_at_utc")
            if isinstance(received_timestamp, str):
                try:
                    parsed_received = datetime.fromisoformat(received_timestamp.replace("Z", "+00:00"))
                    current["connection_age_ms"] = max(0, int((now_utc - parsed_received).total_seconds() * 1000))
                except ValueError:
                    current["connection_age_ms"] = None
            market_assets.append(current)

        vista = VistaLectura(
            instrument=self._instrument,
            environment=env,
            health_state=health,
            data_age_ms=self._last_data_age_ms,
            light=light,
            reason_codes=reasons,
            model_id=self._current_model_id,
            model_version=self._current_model_version,
            model_hash=self._current_model_hash,
            policy_version=self._current_policy_version,
            kill_switch_active=self._kill_switch_active,
            as_of_event_id=self._last_event_id,
            next_cursor=None,
            documents=tuple(docs),
            ui_state=ui_state,
            # Telemetría densa
            bid=self._last_bid,
            ask=self._last_ask,
            spread=self._last_spread,
            mid_price=self._last_mid_price,
            micro_price=self._last_micro_price,
            beta_kalman=self._last_beta_kalman,
            z_score=self._last_z_score,
            desbalance_ofi=self._last_ofi,
            balancines=tuple(self._balancines_data),
            drawdown_diario_pct=self._drawdown_diario_pct,
            limite_por_trade_pct=self._limite_por_trade_pct,
            slots_concurrentes_usados=self._slots_usados,
            slots_concurrentes_max=self._slots_max,
            pnl_paper_acumulado=self._pnl_paper_acumulado,
            secuencia=self._secuencia,
            hash_snapshot=self._hash_snapshot,
            salud_feed=health,
            diagnostico_semaforo=self._diagnostico_semaforo,
            market_data=market_data,
            market_assets=tuple(market_assets),
        )

        return exito(vista)
