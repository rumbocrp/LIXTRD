"""Cotizaciones Yahoo allowlist para SP500, TSLA, AAPL y futuro continuo de oro."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Any
import uuid

from sistema_luces.domain.error import ErrorDominio
from sistema_luces.domain.event import SobreEventoV1, compute_payload_hash, validar_sobre_evento
from sistema_luces.domain.result import Resultado, exito, fallo
from sistema_luces.sources.yahoo_sp500 import (
    AdaptadorYahooPublico,
    ConfiguracionYahooPublica,
    PROVIDER_NAME,
    SIMBOLO_YAHOO_SP500,
)


SIMBOLOS_YAHOO_MONITOR = (SIMBOLO_YAHOO_SP500, "TSLA", "AAPL", "GC=F")

_CONFIGURACIONES = {
    SIMBOLO_YAHOO_SP500: ConfiguracionYahooPublica(
        symbol=SIMBOLO_YAHOO_SP500,
        instrument="US500",
        display_name="S&P 500",
        provider_url="https://finance.yahoo.com/quote/%5EGSPC/",
        event_type="CROSS_ASSET_SNAPSHOT",
        instrument_type="INDEX",
        exchange="SNP",
        exchange_timezone="America/New_York",
        quote_scope="PUBLIC_INDEX_NOT_EXECUTABLE",
    ),
    "TSLA": ConfiguracionYahooPublica(
        symbol="TSLA",
        instrument="US500",
        display_name="Tesla",
        provider_url="https://finance.yahoo.com/quote/TSLA/",
        event_type="CROSS_ASSET_SNAPSHOT",
        instrument_type="EQUITY",
        exchange="NMS",
        exchange_timezone="America/New_York",
        quote_scope="PUBLIC_EQUITY_NOT_EXECUTABLE",
    ),
    "AAPL": ConfiguracionYahooPublica(
        symbol="AAPL",
        instrument="US500",
        display_name="Apple",
        provider_url="https://finance.yahoo.com/quote/AAPL/",
        event_type="CROSS_ASSET_SNAPSHOT",
        instrument_type="EQUITY",
        exchange="NMS",
        exchange_timezone="America/New_York",
        quote_scope="PUBLIC_EQUITY_NOT_EXECUTABLE",
    ),
    "GC=F": ConfiguracionYahooPublica(
        symbol="GC=F",
        instrument="US500",
        display_name="Oro · Futuro continuo Yahoo/COMEX",
        provider_url="https://finance.yahoo.com/quote/GC%3DF/",
        event_type="CROSS_ASSET_SNAPSHOT",
        instrument_type="FUTURE",
        exchange="CMX",
        exchange_timezone="America/New_York",
        quote_scope="CONTINUOUS_FUTURES_NOT_SPOT",
    ),
}


class AdaptadorYahooMultiActivo:
    """Agrega cuatro cotizaciones explícitas sin inferir relaciones ni señales."""

    def __init__(self, ticker_factory: Callable[[str], Any] | None = None) -> None:
        self._readers = {
            symbol: AdaptadorYahooPublico(
                config,
                ticker_factory=ticker_factory,
                include_history=False,
            )
            for symbol, config in _CONFIGURACIONES.items()
        }

    def obtener_evento_snapshot(
        self,
        *,
        now_utc: datetime | None = None,
        timeout_seconds: float = 10.0,
        primary_event: SobreEventoV1 | None = None,
    ) -> Resultado[SobreEventoV1]:
        """Consulta en paralelo los símbolos faltantes y publica un solo snapshot."""
        received = now_utc or datetime.now(timezone.utc)
        if received.tzinfo is None:
            received = received.replace(tzinfo=timezone.utc)
        received = received.astimezone(timezone.utc)

        payloads: dict[str, dict[str, Any]] = {}
        failures: list[dict[str, str]] = []
        if primary_event is not None:
            if primary_event.symbol_id != SIMBOLO_YAHOO_SP500:
                return fallo(
                    ErrorDominio(
                        codigo="INSTRUMENT_NOT_ALLOWED",
                        mensaje_seguro="El snapshot primario debe corresponder a ^GSPC",
                        reintentable=False,
                        correlation_id=primary_event.correlation_id,
                        detalles={"simbolo_recibido": str(primary_event.symbol_id)},
                    )
                )
            payloads[SIMBOLO_YAHOO_SP500] = dict(primary_event.payload)

        missing = [symbol for symbol in SIMBOLOS_YAHOO_MONITOR if symbol not in payloads]
        with ThreadPoolExecutor(max_workers=len(missing) or 1) as pool:
            pending = {
                pool.submit(
                    self._readers[symbol].obtener_evento_snapshot,
                    now_utc=received,
                    timeout_seconds=timeout_seconds,
                ): symbol
                for symbol in missing
            }
            for future in as_completed(pending):
                symbol = pending[future]
                try:
                    result = future.result()
                except Exception as exc:
                    failures.append({"provider_symbol": symbol, "reason_code": type(exc).__name__})
                    continue
                if result.exito:
                    payloads[symbol] = dict(result.datos.payload)
                else:
                    failures.append(
                        {
                            "provider_symbol": symbol,
                            "reason_code": str(result.error.detalles.get("reason_code") or result.error.codigo),
                        }
                    )

        if not payloads:
            return fallo(
                ErrorDominio(
                    codigo="INTERNAL_ERROR",
                    mensaje_seguro="Yahoo Finance no entregó ninguna cotización permitida",
                    reintentable=True,
                    correlation_id="",
                    detalles={"reason_code": "YAHOO_MULTI_ASSET_UNAVAILABLE"},
                )
            )
        ordered = [payloads[symbol] for symbol in SIMBOLOS_YAHOO_MONITOR if symbol in payloads]
        source_times = [
            self._parse_utc(asset.get("source_timestamp_utc"))
            for asset in ordered
        ]
        occurred = max((value for value in source_times if value is not None), default=received)
        return self._crear_evento(
            assets=ordered,
            occurred_at=occurred,
            received_at=received,
            source_sequence=None,
            failures=failures,
        )

    def mapear_mensaje_websocket(
        self,
        message: Mapping[str, object],
        *,
        received_at_utc: datetime | None = None,
    ) -> Resultado[SobreEventoV1]:
        """Convierte una actualización de cualquiera de los cuatro símbolos en un delta."""
        symbol = str(message.get("id", ""))
        reader = self._readers.get(symbol)
        if reader is None:
            return fallo(
                ErrorDominio(
                    codigo="INSTRUMENT_NOT_ALLOWED",
                    mensaje_seguro="El stream Yahoo recibió un símbolo fuera de la allowlist",
                    reintentable=False,
                    correlation_id="",
                    detalles={"simbolo_recibido": symbol},
                )
            )
        mapped = reader.mapear_mensaje_websocket(message, received_at_utc=received_at_utc)
        if not mapped.exito:
            return fallo(mapped.error)
        event = mapped.datos
        return self._crear_evento(
            assets=[dict(event.payload)],
            occurred_at=event.occurred_at_utc,
            received_at=event.received_at_utc,
            source_sequence=event.source_sequence,
            failures=[],
        )

    @staticmethod
    def _parse_utc(value: object) -> datetime | None:
        if not isinstance(value, str):
            return None
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)

    @staticmethod
    def _crear_evento(
        *,
        assets: list[dict[str, Any]],
        occurred_at: datetime,
        received_at: datetime,
        source_sequence: int | None,
        failures: list[dict[str, str]],
    ) -> Resultado[SobreEventoV1]:
        payload: dict[str, Any] = {
            "source_name": PROVIDER_NAME,
            "provider": PROVIDER_NAME,
            "provider_symbols": list(SIMBOLOS_YAHOO_MONITOR),
            "assets": assets,
            "relations": [],
            "partial_failures": failures,
            "quote_status": "PROVIDER_DELAY_UNDISCLOSED",
        }
        event = SobreEventoV1(
            event_id=str(uuid.uuid4()),
            event_type="CROSS_ASSET_SNAPSHOT",
            schema_version=1,
            occurred_at_utc=occurred_at,
            received_at_utc=received_at,
            persisted_at_utc=None,
            source="yahoo_finance",  # type: ignore[arg-type]
            environment="SHADOW",
            source_account_id_hash=None,
            instrument="US500",
            symbol_id=SIMBOLO_YAHOO_SP500,
            source_sequence=source_sequence,
            correlation_id=str(uuid.uuid4()),
            causation_id=None,
            payload_hash=compute_payload_hash(payload),
            previous_hash=None,
            payload=payload,
        )
        validation = validar_sobre_evento(event)
        if not validation.exito:
            return fallo(validation.error)
        return exito(event)


__all__ = ["AdaptadorYahooMultiActivo", "SIMBOLOS_YAHOO_MONITOR"]
