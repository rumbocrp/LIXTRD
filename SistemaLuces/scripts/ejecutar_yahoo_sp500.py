"""Monitor 24/7 de la fuente pública transitoria Yahoo Finance para ``^GSPC``.

El proceso permanece activo hasta Ctrl+C. WebSocket reduce la latencia cuando Yahoo publica
mensajes; REST de un minuto aporta el snapshot inicial y la recuperación periódica. Ninguna
de las dos rutas se presenta como bid/ask ejecutable ni como cuenta demo observada.
"""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
import signal
import sys
import threading
import time
from typing import Any
import uuid

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from sistema_luces.domain.event import SobreEventoV1, compute_payload_hash
from sistema_luces.observability.projections import ProyectorVistas
from sistema_luces.sources.yahoo_multi_asset import AdaptadorYahooMultiActivo, SIMBOLOS_YAHOO_MONITOR
from sistema_luces.sources.yahoo_sp500 import AdaptadorYahooSP500, SIMBOLO_YAHOO_SP500
from sistema_luces.ui.server import ServidorLoopback


def _iso_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _evento_fuente_degradada(reason_code: str) -> SobreEventoV1:
    now = datetime.now(timezone.utc)
    payload = {
        "reason_code": reason_code,
        "provider": "Yahoo Finance",
        "provider_symbol": SIMBOLO_YAHOO_SP500,
        "observed_at_utc": _iso_utc(now),
        "action": "KEEP_LAST_REAL_VALUE_AND_FORCE_YELLOW",
    }
    return SobreEventoV1(
        event_id=str(uuid.uuid4()),
        event_type="STALE",
        schema_version=1,
        occurred_at_utc=now,
        received_at_utc=now,
        persisted_at_utc=None,
        source="yahoo_finance",  # type: ignore[arg-type]
        environment="SHADOW",
        source_account_id_hash=None,
        instrument="US500",
        symbol_id=SIMBOLO_YAHOO_SP500,
        source_sequence=None,
        correlation_id=str(uuid.uuid4()),
        causation_id=None,
        payload_hash=compute_payload_hash(payload),
        previous_hash=None,
        payload=payload,
    )


@dataclass
class RegistroTerminal:
    """Reduce ruido: imprime cambios de precio/transporte y un heartbeat por minuto."""

    ultimas_firmas: dict[str, tuple[object, ...]] = field(default_factory=dict)
    ultimo_heartbeat_monotonic: float = 0.0

    def evento(self, event: SobreEventoV1) -> None:
        payload = event.payload
        assets = payload.get("assets")
        if isinstance(assets, list):
            for asset in assets:
                if isinstance(asset, dict):
                    self._cotizacion(asset)
            return
        self._cotizacion(payload)

    def _cotizacion(self, payload: dict[str, Any]) -> None:
        symbol = str(payload.get("provider_symbol") or "N/A")
        signature = (
            payload.get("last_price_scaled"),
            payload.get("source_timestamp_utc"),
            payload.get("transport"),
            payload.get("market_state"),
        )
        now_monotonic = time.monotonic()
        if signature == self.ultimas_firmas.get(symbol) and now_monotonic - self.ultimo_heartbeat_monotonic < 60:
            return
        self.ultimas_firmas[symbol] = signature
        self.ultimo_heartbeat_monotonic = now_monotonic
        scale = payload.get("price_scale", 100)
        raw_price = payload.get("last_price_scaled")
        price = raw_price / scale if isinstance(raw_price, int) and isinstance(scale, int) and scale else None
        price_text = f"{price:,.2f}" if price is not None else "N/A"
        print(
            f"[{_iso_utc(datetime.now(timezone.utc))}] "
            f"{symbol}={price_text} | mercado={payload.get('market_state', 'UNKNOWN')} | "
            f"transporte={payload.get('transport', 'N/A')} | "
            f"timestamp_yahoo={payload.get('source_timestamp_utc', 'N/A')} | "
            f"latencia={payload.get('fetch_latency_ms', payload.get('source_to_receive_ms', 'N/A'))}ms",
            flush=True,
        )

    def error(self, reason: str) -> None:
        print(
            f"[{_iso_utc(datetime.now(timezone.utc))}] FUENTE_DEGRADADA {reason}; "
            "se conserva el último valor real y la luz permanece AMARILLA.",
            flush=True,
        )


class MonitorYahooSP500:
    """Orquesta REST, WebSocket y proyección detrás de la interfaz de fuente."""

    def __init__(
        self,
        proyector: ProyectorVistas,
        *,
        rest_open_seconds: float,
        rest_closed_seconds: float,
        timeout_seconds: float,
    ) -> None:
        self.proyector = proyector
        self.adapter = AdaptadorYahooSP500()
        self.multi_adapter = AdaptadorYahooMultiActivo()
        self.rest_open_seconds = max(1.0, rest_open_seconds)
        self.rest_closed_seconds = max(self.rest_open_seconds, rest_closed_seconds)
        self.timeout_seconds = max(1.0, timeout_seconds)
        self.log = RegistroTerminal()
        self.market_state = "UNKNOWN"
        self.consecutive_failures = 0

    async def refrescar_rest(self) -> bool:
        result = await asyncio.to_thread(
            self.adapter.obtener_evento_snapshot,
            timeout_seconds=self.timeout_seconds,
        )
        if not result.exito:
            self.consecutive_failures += 1
            reason = str(result.error.detalles.get("reason_code") or result.error.codigo)
            self.log.error(reason)
            if self.consecutive_failures >= 3:
                self.proyector.actualizar_desde_evento(_evento_fuente_degradada(reason))
            return False
        self.consecutive_failures = 0
        event = result.datos
        self.market_state = str(event.payload.get("market_state") or "UNKNOWN")
        projection = self.proyector.actualizar_desde_evento(event)
        if not projection.exito:
            self.log.error(projection.error.codigo)
            return False
        self.log.evento(event)
        multi_result = await asyncio.to_thread(
            self.multi_adapter.obtener_evento_snapshot,
            timeout_seconds=self.timeout_seconds,
            primary_event=event,
        )
        if not multi_result.exito:
            self.log.error(str(multi_result.error.detalles.get("reason_code") or multi_result.error.codigo))
            return True
        multi_projection = self.proyector.actualizar_desde_evento(multi_result.datos)
        if not multi_projection.exito:
            self.log.error(multi_projection.error.codigo)
            return True
        self.log.evento(multi_result.datos)
        return True

    async def loop_rest(self, stop: asyncio.Event) -> None:
        while not stop.is_set():
            interval = self.rest_open_seconds if self.market_state == "REGULAR" else self.rest_closed_seconds
            try:
                await asyncio.wait_for(stop.wait(), timeout=interval)
            except TimeoutError:
                await self.refrescar_rest()

    async def loop_websocket(self, stop: asyncio.Event) -> None:
        import yfinance as yf

        while not stop.is_set():
            websocket: Any | None = None
            listen_task: asyncio.Task[None] | None = None
            try:
                websocket = yf.AsyncWebSocket(verbose=False)
                await websocket.subscribe(list(SIMBOLOS_YAHOO_MONITOR))

                async def handler(message: dict[str, object]) -> None:
                    if message.get("id") == SIMBOLO_YAHOO_SP500:
                        primary = self.adapter.mapear_mensaje_websocket(message)
                        if primary.exito:
                            event = primary.datos
                            self.market_state = str(event.payload.get("market_state") or self.market_state)
                            projected = self.proyector.actualizar_desde_evento(event)
                            if projected.exito:
                                self.log.evento(event)
                    multi = self.multi_adapter.mapear_mensaje_websocket(message)
                    if not multi.exito:
                        if multi.error.codigo != "INSTRUMENT_NOT_ALLOWED":
                            self.log.error(multi.error.codigo)
                        return
                    projected_multi = self.proyector.actualizar_desde_evento(multi.datos)
                    if projected_multi.exito:
                        self.log.evento(multi.datos)

                listen_task = asyncio.create_task(websocket.listen(handler))
                stop_task = asyncio.create_task(stop.wait())
                done, pending = await asyncio.wait(
                    {listen_task, stop_task},
                    return_when=asyncio.FIRST_COMPLETED,
                )
                for task in pending:
                    task.cancel()
                if stop_task in done:
                    break
                self.log.error("YAHOO_WEBSOCKET_DISCONNECTED")
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.log.error(f"YAHOO_WEBSOCKET_{type(exc).__name__.upper()}")
            finally:
                if listen_task is not None and not listen_task.done():
                    listen_task.cancel()
                if websocket is not None:
                    try:
                        await websocket.close()
                    except Exception:
                        pass
            if not stop.is_set():
                try:
                    await asyncio.wait_for(stop.wait(), timeout=3.0)
                except TimeoutError:
                    pass


async def _main_async(args: argparse.Namespace) -> None:
    proyector = ProyectorVistas()
    monitor = MonitorYahooSP500(
        proyector,
        rest_open_seconds=args.rest_open_seconds,
        rest_closed_seconds=args.rest_closed_seconds,
        timeout_seconds=args.timeout_seconds,
    )

    print("SISTEMA DE LUCES — OBSERVACIÓN PÚBLICA MULTI-ACTIVO", flush=True)
    print("Fuente: Yahoo Finance ^GSPC · TSLA · AAPL · GC=F | entorno: SHADOW | cero órdenes", flush=True)
    print("La demora del proveedor no está declarada por la API; no se etiqueta como tiempo real.", flush=True)
    print("WebSocket primario + REST 1m de respaldo; el proceso continúa 24/7 hasta Ctrl+C.", flush=True)
    await monitor.refrescar_rest()

    server = ServidorLoopback(host="127.0.0.1", port=args.port, proyector=proyector)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True, name="http-loopback")
    server_thread.start()
    print(f"Panel: http://127.0.0.1:{args.port}/", flush=True)

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop.set)
        except (NotImplementedError, RuntimeError):
            pass

    tasks = [asyncio.create_task(monitor.loop_rest(stop), name="yahoo-rest")]
    if not args.no_websocket:
        tasks.append(asyncio.create_task(monitor.loop_websocket(stop), name="yahoo-websocket"))
    try:
        await stop.wait()
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await asyncio.to_thread(server.shutdown)
        print("Monitor Yahoo multi-activo detenido limpiamente.", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Monitor Yahoo Finance 24/7 para SP500, TSLA, AAPL y oro")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--rest-open-seconds", type=float, default=15.0)
    parser.add_argument("--rest-closed-seconds", type=float, default=60.0)
    parser.add_argument("--timeout-seconds", type=float, default=10.0)
    parser.add_argument("--no-websocket", action="store_true", help="Sólo para diagnóstico del fallback REST")
    args = parser.parse_args()
    asyncio.run(_main_async(args))


if __name__ == "__main__":
    main()
