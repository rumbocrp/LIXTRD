"""Contrato Yahoo para SP500, TSLA, AAPL y oro en un único monitor."""

from datetime import datetime, timezone
from dataclasses import replace
import json
from pathlib import Path
import sys
import threading
import unittest
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sistema_luces.domain.api import SolicitudConsulta
from sistema_luces.domain.event import compute_payload_hash
from sistema_luces.observability.projections import ProyectorVistas
from sistema_luces.sources.yahoo_multi_asset import AdaptadorYahooMultiActivo, SIMBOLOS_YAHOO_MONITOR
from sistema_luces.sources.yahoo_sp500 import AdaptadorYahooSP500
from sistema_luces.ui.server import ServidorLoopback
from sistema_luces.ui.views import render_dashboard_html


NOW = datetime(2026, 8, 30, 16, 0, tzinfo=timezone.utc)
SOURCE_TIME = datetime(2026, 8, 28, 20, 37, tzinfo=timezone.utc)
QUOTES = {
    "^GSPC": (7711.76, 7730.99, "INDEX", "SNP"),
    "TSLA": (352.14, 349.60, "EQUITY", "NMS"),
    "AAPL": (232.55, 230.10, "EQUITY", "NMS"),
    "GC=F": (4529.90, 4664.00, "FUTURE", "CMX"),
}


class _Iloc:
    def __init__(self, values: list[object]) -> None:
        self._values = values

    def __getitem__(self, position: int) -> object:
        return self._values[position]


class _Series:
    def __init__(self, values: list[object]) -> None:
        self.iloc = _Iloc(values)


class _IndexItem:
    def to_pydatetime(self) -> datetime:
        return SOURCE_TIME


class _Frame:
    def __init__(self, price: float) -> None:
        self.index = [_IndexItem()]
        self.columns = ["Open", "Close"]
        self._values = {"Open": [price - 1.0], "Close": [price]}

    def __getitem__(self, key: str) -> _Series:
        return _Series(self._values[key])


class _Ticker:
    def __init__(self, symbol: str) -> None:
        self.symbol = symbol
        self.price, self.previous, self.kind, self.exchange = QUOTES[symbol]

    def history(self, **_: object) -> _Frame:
        return _Frame(self.price)

    def get_history_metadata(self) -> dict[str, object]:
        return {
            "symbol": self.symbol,
            "currency": "USD",
            "instrumentType": self.kind,
            "exchangeName": self.exchange,
            "exchangeTimezoneName": "America/New_York",
            "regularMarketPrice": self.price,
            "previousClose": self.previous,
            "regularMarketDayHigh": self.price + 4.0,
            "regularMarketDayLow": self.price - 5.0,
            "regularMarketVolume": 123_456,
            "regularMarketChangePercent": ((self.price / self.previous) - 1.0) * 100.0,
            "regularMarketTime": SOURCE_TIME,
            "dataGranularity": "1m",
            "currentTradingPeriod": {
                "regular": {
                    "start": datetime(2026, 8, 28, 13, 30, tzinfo=timezone.utc),
                    "end": datetime(2026, 8, 28, 21, 0, tzinfo=timezone.utc),
                }
            },
        }


def _request() -> SolicitudConsulta:
    return SolicitudConsulta(
        correlation_id="a671182a-a438-4f75-95c5-c39fa74c962a",
        environment="SHADOW",
        view="FEED",
        as_of_event_id=None,
        cursor=None,
        limit=100,
    )


class YahooMultiAssetTests(unittest.TestCase):
    def setUp(self) -> None:
        self.requested: list[str] = []

        def factory(symbol: str) -> _Ticker:
            self.requested.append(symbol)
            return _Ticker(symbol)

        self.factory = factory
        self.adapter = AdaptadorYahooMultiActivo(ticker_factory=factory)

    def test_rest_publica_allowlist_completa_con_numeros_y_procedencia(self) -> None:
        result = self.adapter.obtener_evento_snapshot(now_utc=NOW)

        self.assertTrue(result.exito, getattr(result, "error", None))
        event = result.datos
        self.assertCountEqual(SIMBOLOS_YAHOO_MONITOR, self.requested)
        self.assertEqual("CROSS_ASSET_SNAPSHOT", event.event_type)
        self.assertEqual("US500", event.instrument)
        assets = event.payload["assets"]
        self.assertEqual(list(SIMBOLOS_YAHOO_MONITOR), [item["provider_symbol"] for item in assets])
        by_symbol = {item["provider_symbol"]: item for item in assets}
        self.assertEqual(771_176, by_symbol["^GSPC"]["last_price_scaled"])
        self.assertEqual(35_214, by_symbol["TSLA"]["last_price_scaled"])
        self.assertEqual(23_255, by_symbol["AAPL"]["last_price_scaled"])
        self.assertEqual(452_990, by_symbol["GC=F"]["last_price_scaled"])
        self.assertEqual("FUTURE", by_symbol["GC=F"]["instrument_type"])
        self.assertEqual("CONTINUOUS_FUTURES_NOT_SPOT", by_symbol["GC=F"]["quote_scope"])
        for asset in assets:
            self.assertNotIn("bid_scaled", asset)
            self.assertNotIn("ask_scaled", asset)

    def test_rest_reutiliza_snapshot_sp500_y_solo_consulta_los_otros_tres(self) -> None:
        primary = AdaptadorYahooSP500(ticker_factory=self.factory).obtener_evento_snapshot(now_utc=NOW)
        self.assertTrue(primary.exito)
        self.requested.clear()

        result = self.adapter.obtener_evento_snapshot(now_utc=NOW, primary_event=primary.datos)

        self.assertTrue(result.exito, getattr(result, "error", None))
        self.assertCountEqual(["TSLA", "AAPL", "GC=F"], self.requested)
        self.assertEqual(4, len(result.datos.payload["assets"]))

    def test_websocket_acepta_cuatro_simbolos_y_rechaza_cualquier_otro(self) -> None:
        for symbol, (price, _, kind, _) in QUOTES.items():
            result = self.adapter.mapear_mensaje_websocket(
                {"id": symbol, "price": price, "time": 1_787_948_220_000, "market_hours": 1, "quote_type": kind},
                received_at_utc=NOW,
            )
            self.assertTrue(result.exito, getattr(result, "error", None))
            self.assertEqual(symbol, result.datos.payload["assets"][0]["provider_symbol"])
            self.assertNotIn("bid_scaled", result.datos.payload["assets"][0])

        rejected = self.adapter.mapear_mensaje_websocket(
            {"id": "MSFT", "price": 500.0, "time": 1_787_948_220_000},
            received_at_utc=NOW,
        )
        self.assertFalse(rejected.exito)
        self.assertEqual("INSTRUMENT_NOT_ALLOWED", rejected.error.codigo)

    def test_proyeccion_fusiona_cuatro_filas_y_actualizacion_parcial(self) -> None:
        projector = ProyectorVistas()
        initial = self.adapter.obtener_evento_snapshot(now_utc=NOW)
        self.assertTrue(projector.actualizar_desde_evento(initial.datos).exito)
        update = self.adapter.mapear_mensaje_websocket(
            {"id": "TSLA", "price": 355.25, "time": 1_787_948_221_000, "market_hours": 1},
            received_at_utc=NOW,
        )
        self.assertTrue(projector.actualizar_desde_evento(update.datos).exito)
        view = projector.consultar(_request()).datos

        self.assertEqual(4, len(view.market_assets))
        by_symbol = {item["provider_symbol"]: item for item in view.market_assets}
        self.assertEqual(355.25, by_symbol["TSLA"]["last_price"])
        self.assertEqual(232.55, by_symbol["AAPL"]["last_price"])
        self.assertEqual(4529.90, by_symbol["GC=F"]["last_price"])
        self.assertEqual((), view.balancines)
        self.assertIsNone(view.diagnostico_semaforo)
        rendered = render_dashboard_html(view)
        for text in ("S&amp;P 500", "Tesla", "Apple", "Oro", "GC=F"):
            self.assertIn(text, rendered)

    def test_http_status_expone_las_cuatro_cotizaciones(self) -> None:
        projector = ProyectorVistas()
        projector.actualizar_desde_evento(self.adapter.obtener_evento_snapshot(now_utc=NOW).datos)
        server = ServidorLoopback(host="127.0.0.1", port=0, proyector=projector)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            port = server.httpd.server_address[1]
            with urlopen(f"http://127.0.0.1:{port}/v1/status", timeout=3) as response:
                body = json.loads(response.read().decode("utf-8"))
            self.assertEqual(["^GSPC", "TSLA", "AAPL", "GC=F"], [
                item["provider_symbol"] for item in body["market_assets"]
            ])
        finally:
            server.shutdown()
            thread.join(timeout=3)

    def test_cada_activo_tiene_diagnostico_independiente_sin_herencia(self) -> None:
        result = self.adapter.obtener_evento_snapshot(now_utc=NOW)
        payload = dict(result.datos.payload)
        assets = [dict(asset) for asset in payload["assets"]]
        assets[1]["diagnostico_semaforo"] = {
            "probability_long_pct": 67.0,
            "probability_short_pct": 33.0,
            "threshold_green_pct": 65.0,
            "threshold_red_pct": 35.0,
            "threshold_source": "modelo-tsla-v1",
            "source_event_id": "signal-tsla-1",
        }
        payload["assets"] = assets
        event = replace(result.datos, payload=payload, payload_hash=compute_payload_hash(payload))
        projector = ProyectorVistas()
        self.assertTrue(projector.actualizar_desde_evento(event).exito)
        view = projector.consultar(_request()).datos
        by_symbol = {item["provider_symbol"]: item for item in view.market_assets}

        self.assertEqual(67.0, by_symbol["TSLA"]["diagnostico_semaforo"]["probability_long_pct"])
        self.assertNotIn("diagnostico_semaforo", by_symbol["AAPL"])
        rendered = render_dashboard_html(view)
        self.assertEqual(4, rendered.count("data-asset-diagnostic role="))
        self.assertIn("67.0% · R≤35.0 · V≥65.0", rendered)


if __name__ == "__main__":
    unittest.main()
