"""Adaptador parametrizado Yahoo y configuración cerrada para observar ``^GSPC``.

Yahoo no es un feed ejecutable ni sustituye la Puerta de cuenta demo. Este adaptador sólo
normaliza datos públicos de índice en entorno ``SHADOW`` y conserva la procedencia y el
timestamp entregados por el proveedor. La ausencia de bid/ask permanece ausente.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import math
from time import perf_counter
from typing import Any
import uuid

from sistema_luces.domain.error import ErrorDominio
from sistema_luces.domain.event import SobreEventoV1, compute_payload_hash, validar_sobre_evento
from sistema_luces.domain.result import Resultado, exito, fallo
from sistema_luces.domain.vocabulary import Instrument


SIMBOLO_YAHOO_SP500 = "^GSPC"
INSTRUMENTO_CANONICO = "US500"
PRICE_SCALE = 100
PERCENT_SCALE = 100_000
PROVIDER_NAME = "Yahoo Finance"
PROVIDER_URL = "https://finance.yahoo.com/quote/%5EGSPC/"


@dataclass(frozen=True)
class ConfiguracionYahooPublica:
    symbol: str
    instrument: Instrument
    display_name: str
    provider_url: str
    event_type: str
    instrument_type: str
    exchange: str
    exchange_timezone: str
    quote_scope: str


CONFIGURACION_YAHOO_SP500 = ConfiguracionYahooPublica(
    symbol=SIMBOLO_YAHOO_SP500,
    instrument="US500",
    display_name="S&P 500 · Índice público Yahoo",
    provider_url=PROVIDER_URL,
    event_type="INDEX_MARKET_SNAPSHOT",
    instrument_type="INDEX",
    exchange="SNP",
    exchange_timezone="America/New_York",
    quote_scope="PUBLIC_INDEX_NOT_EXECUTABLE",
)


def _crear_ticker_yahoo(symbol: str) -> Any:
    # Importación perezosa: replay y dominio pueden ejecutarse sin cargar dependencias de red.
    import yfinance as yf

    return yf.Ticker(symbol)


def _iso_utc(value: datetime) -> str:
    utc = value.astimezone(timezone.utc)
    if utc.microsecond:
        return utc.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    return utc.strftime("%Y-%m-%dT%H:%M:%SZ")


def _datetime_utc(value: object) -> datetime | None:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        raw = float(value)
        if not math.isfinite(raw):
            return None
        if abs(raw) >= 1_000_000_000_000:
            raw /= 1000.0
        return datetime.fromtimestamp(raw, tz=timezone.utc)
    if isinstance(value, str) and value.strip():
        try:
            parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    return None


def _numero_finito(value: object) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    if not number.is_finite():
        return None
    return number


def _escalar(value: object, scale: int) -> int | None:
    number = _numero_finito(value)
    if number is None:
        return None
    return int((number * scale).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _entero_no_negativo(value: object) -> int | None:
    number = _numero_finito(value)
    if number is None or number < 0:
        return None
    return int(number.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _valor_frame(frame: Any, column: str, position: int) -> object | None:
    try:
        if frame is None or len(frame.index) == 0 or column not in frame.columns:
            return None
        return frame[column].iloc[position]
    except (AttributeError, IndexError, KeyError, TypeError):
        return None


class AdaptadorYahooPublico:
    """Obtiene snapshots REST/WebSocket para una configuración allowlist inmutable."""

    def __init__(
        self,
        config: ConfiguracionYahooPublica,
        ticker_factory: Callable[[str], Any] | None = None,
        *,
        include_history: bool = True,
    ) -> None:
        self.config = config
        self._ticker_factory = ticker_factory or _crear_ticker_yahoo
        self._include_history = include_history

    def obtener_evento_snapshot(
        self,
        *,
        now_utc: datetime | None = None,
        timeout_seconds: float = 10.0,
    ) -> Resultado[SobreEventoV1]:
        """Consulta un snapshot de un minuto y lo normaliza a un evento ``SHADOW``."""
        started = perf_counter()
        try:
            ticker = self._ticker_factory(self.config.symbol)
            metadata = ticker.get_history_metadata()
            history = None
            if self._include_history:
                history = ticker.history(
                    period="1d",
                    interval="1m",
                    prepost=False,
                    actions=False,
                    auto_adjust=False,
                    repair=False,
                    timeout=timeout_seconds,
                )
        except Exception as exc:
            return fallo(
                ErrorDominio(
                    # El catálogo SPEC-001 no expone un código SOURCE_UNAVAILABLE.
                    # Se conserva el contrato cerrado y se aporta una razón específica
                    # para que el runtime degrade y reintente sin terminar el proceso.
                    codigo="INTERNAL_ERROR",
                    mensaje_seguro=f"Yahoo Finance no respondió al snapshot de {self.config.symbol}",
                    reintentable=True,
                    correlation_id="",
                    detalles={
                        "reason_code": "YAHOO_SOURCE_UNAVAILABLE",
                        "tipo_error": type(exc).__name__,
                    },
                )
            )

        received_at = now_utc or datetime.now(timezone.utc)
        if received_at.tzinfo is None:
            received_at = received_at.replace(tzinfo=timezone.utc)
        received_at = received_at.astimezone(timezone.utc)
        fetch_latency_ms = max(0, round((perf_counter() - started) * 1000))

        if not isinstance(metadata, Mapping) or metadata.get("symbol") != self.config.symbol:
            return fallo(
                ErrorDominio(
                    codigo="INSTRUMENT_NOT_ALLOWED",
                    mensaje_seguro=(
                        "La respuesta de Yahoo no corresponde al símbolo permitido "
                        f"{self.config.symbol}"
                    ),
                    reintentable=False,
                    correlation_id="",
                    detalles={"simbolo_recibido": str(getattr(metadata, "get", lambda _k: None)("symbol"))},
                )
            )

        source_timestamp = _datetime_utc(metadata.get("regularMarketTime"))
        if source_timestamp is None:
            try:
                source_timestamp = _datetime_utc(history.index[-1].to_pydatetime())
            except (AttributeError, IndexError, TypeError):
                source_timestamp = None

        last_price = metadata.get("regularMarketPrice")
        if _numero_finito(last_price) is None:
            last_price = _valor_frame(history, "Close", -1)
        if source_timestamp is None or _numero_finito(last_price) is None:
            return fallo(
                ErrorDominio(
                    codigo="SOURCE_DATA_INVALID",
                    mensaje_seguro=(
                        "Yahoo no entregó precio y timestamp válidos para "
                        f"{self.config.symbol}"
                    ),
                    reintentable=True,
                    correlation_id="",
                    detalles={},
                )
            )

        regular_period = metadata.get("currentTradingPeriod", {})
        if isinstance(regular_period, Mapping):
            regular_period = regular_period.get("regular", {})
        market_state = "CLOSED"
        if isinstance(regular_period, Mapping):
            session_start = _datetime_utc(regular_period.get("start"))
            session_end = _datetime_utc(regular_period.get("end"))
            if session_start is not None and session_end is not None and session_start <= received_at < session_end:
                market_state = "REGULAR"

        payload: dict[str, Any] = {
            "provider": PROVIDER_NAME,
            "provider_url": self.config.provider_url,
            "provider_symbol": self.config.symbol,
            "display_name": self.config.display_name,
            "instrument_type": str(metadata.get("instrumentType") or self.config.instrument_type),
            "quote_scope": self.config.quote_scope,
            "currency": str(metadata.get("currency") or "USD"),
            "exchange": str(metadata.get("exchangeName") or self.config.exchange),
            "exchange_timezone": str(
                metadata.get("exchangeTimezoneName") or self.config.exchange_timezone
            ),
            "price_scale": PRICE_SCALE,
            "percent_scale": PERCENT_SCALE,
            "source_timestamp_utc": _iso_utc(source_timestamp),
            "received_at_utc": _iso_utc(received_at),
            "fetch_latency_ms": fetch_latency_ms,
            "market_state": market_state,
            "transport": "REST_1M",
            "data_granularity": str(metadata.get("dataGranularity") or "1m"),
            "quote_status": "PROVIDER_DELAY_UNDISCLOSED",
        }
        self._agregar_escalado(payload, "last_price_scaled", last_price, PRICE_SCALE)
        self._agregar_escalado(payload, "previous_close_scaled", metadata.get("previousClose"), PRICE_SCALE)
        day_open = metadata.get("regularMarketOpen")
        if _numero_finito(day_open) is None:
            day_open = _valor_frame(history, "Open", 0)
        self._agregar_escalado(payload, "day_open_scaled", day_open, PRICE_SCALE)
        self._agregar_escalado(payload, "day_high_scaled", metadata.get("regularMarketDayHigh"), PRICE_SCALE)
        self._agregar_escalado(payload, "day_low_scaled", metadata.get("regularMarketDayLow"), PRICE_SCALE)
        self._agregar_escalado(
            payload,
            "change_pct_scaled",
            metadata.get("regularMarketChangePercent"),
            PERCENT_SCALE,
        )
        previous_close = _numero_finito(metadata.get("previousClose"))
        last_decimal = _numero_finito(last_price)
        if previous_close is not None and last_decimal is not None:
            self._agregar_escalado(payload, "change_scaled", last_decimal - previous_close, PRICE_SCALE)
        volume = _entero_no_negativo(metadata.get("regularMarketVolume"))
        if volume is not None:
            payload["day_volume"] = volume

        return self._crear_evento(payload, source_timestamp, received_at, source_sequence=None)

    def mapear_mensaje_websocket(
        self,
        message: Mapping[str, object],
        *,
        received_at_utc: datetime | None = None,
    ) -> Resultado[SobreEventoV1]:
        """Mapea un mensaje de ``yfinance.AsyncWebSocket`` preservando campos ausentes."""
        symbol = message.get("id")
        if symbol != self.config.symbol:
            return fallo(
                ErrorDominio(
                    codigo="INSTRUMENT_NOT_ALLOWED",
                    mensaje_seguro=f"El stream Yahoo sólo admite {self.config.symbol}",
                    reintentable=False,
                    correlation_id="",
                    detalles={"simbolo_recibido": str(symbol)},
                )
            )
        source_timestamp = _datetime_utc(message.get("time"))
        last_price = message.get("price")
        if source_timestamp is None or _numero_finito(last_price) is None:
            return fallo(
                ErrorDominio(
                    codigo="SOURCE_DATA_INVALID",
                    mensaje_seguro="Mensaje Yahoo sin precio o timestamp válido",
                    reintentable=True,
                    correlation_id="",
                    detalles={},
                )
            )
        received = received_at_utc or datetime.now(timezone.utc)
        if received.tzinfo is None:
            received = received.replace(tzinfo=timezone.utc)
        received = received.astimezone(timezone.utc)
        market_hours = message.get("market_hours")
        payload: dict[str, Any] = {
            "provider": PROVIDER_NAME,
            "provider_url": self.config.provider_url,
            "provider_symbol": self.config.symbol,
            "display_name": self.config.display_name,
            "instrument_type": self.config.instrument_type,
            "quote_scope": self.config.quote_scope,
            "currency": str(message.get("currency") or "USD"),
            "exchange": str(message.get("exchange") or self.config.exchange),
            "exchange_timezone": self.config.exchange_timezone,
            "price_scale": PRICE_SCALE,
            "percent_scale": PERCENT_SCALE,
            "source_timestamp_utc": _iso_utc(source_timestamp),
            "received_at_utc": _iso_utc(received),
            "source_to_receive_ms": max(0, int((received - source_timestamp).total_seconds() * 1000)),
            "market_state": "REGULAR" if market_hours == 1 else "CLOSED",
            "transport": "WEBSOCKET",
            "data_granularity": "stream",
            "quote_status": "PROVIDER_DELAY_UNDISCLOSED",
        }
        fields = {
            "last_price_scaled": (last_price, PRICE_SCALE),
            "previous_close_scaled": (message.get("previous_close"), PRICE_SCALE),
            "day_open_scaled": (message.get("open_price"), PRICE_SCALE),
            "day_high_scaled": (message.get("day_high"), PRICE_SCALE),
            "day_low_scaled": (message.get("day_low"), PRICE_SCALE),
            "change_scaled": (message.get("change"), PRICE_SCALE),
            "change_pct_scaled": (message.get("change_percent"), PERCENT_SCALE),
            "bid_scaled": (message.get("bid"), PRICE_SCALE),
            "ask_scaled": (message.get("ask"), PRICE_SCALE),
        }
        for key, (value, scale) in fields.items():
            # Yahoo representa a veces campos inexistentes como cero. Bid/ask cero no son ejecutables.
            if key in {"bid_scaled", "ask_scaled"} and _numero_finito(value) == Decimal("0"):
                continue
            self._agregar_escalado(payload, key, value, scale)
        volume = _entero_no_negativo(message.get("day_volume"))
        if volume is not None:
            payload["day_volume"] = volume
        sequence = int(source_timestamp.timestamp() * 1000)
        return self._crear_evento(payload, source_timestamp, received, source_sequence=sequence)

    @staticmethod
    def _agregar_escalado(payload: dict[str, Any], key: str, value: object, scale: int) -> None:
        scaled = _escalar(value, scale)
        if scaled is not None:
            payload[key] = scaled

    def _crear_evento(
        self,
        payload: dict[str, Any],
        source_timestamp: datetime,
        received_at: datetime,
        *,
        source_sequence: int | None,
    ) -> Resultado[SobreEventoV1]:
        correlation_id = str(uuid.uuid4())
        event = SobreEventoV1(
            event_id=str(uuid.uuid4()),
            event_type=self.config.event_type,
            schema_version=1,
            occurred_at_utc=source_timestamp,
            received_at_utc=received_at,
            persisted_at_utc=None,
            source="yahoo_finance",  # type: ignore[arg-type]
            environment="SHADOW",
            source_account_id_hash=None,
            instrument=self.config.instrument,
            symbol_id=self.config.symbol,
            source_sequence=source_sequence,
            correlation_id=correlation_id,
            causation_id=None,
            payload_hash=compute_payload_hash(payload),
            previous_hash=None,
            payload=payload,
        )
        validation = validar_sobre_evento(event)
        if not validation.exito:
            return fallo(validation.error)
        return exito(event)


class AdaptadorYahooSP500(AdaptadorYahooPublico):
    """Allowlist Yahoo para observar exclusivamente ``^GSPC`` como ``US500``."""

    def __init__(self, ticker_factory: Callable[[str], Any] | None = None) -> None:
        super().__init__(CONFIGURACION_YAHOO_SP500, ticker_factory=ticker_factory, include_history=True)


__all__ = [
    "AdaptadorYahooSP500",
    "AdaptadorYahooPublico",
    "CONFIGURACION_YAHOO_SP500",
    "ConfiguracionYahooPublica",
    "INSTRUMENTO_CANONICO",
    "PERCENT_SCALE",
    "PRICE_SCALE",
    "PROVIDER_NAME",
    "PROVIDER_URL",
    "SIMBOLO_YAHOO_SP500",
]
