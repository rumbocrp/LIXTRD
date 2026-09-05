"""Contrato de la fuente pública transitoria Yahoo Finance para el índice S&P 500."""

from datetime import datetime, timezone
import unittest

from sistema_luces.sources.yahoo_sp500 import AdaptadorYahooSP500


class _Iloc:
    def __init__(self, values: list[object]) -> None:
        self._values = values

    def __getitem__(self, position: int) -> object:
        return self._values[position]


class _Serie:
    def __init__(self, values: list[object]) -> None:
        self.iloc = _Iloc(values)


class _IndiceItem:
    def __init__(self, value: datetime) -> None:
        self._value = value

    def to_pydatetime(self) -> datetime:
        return self._value


class _FrameFalso:
    def __init__(self) -> None:
        self.index = [_IndiceItem(datetime(2026, 8, 28, 19, 59, tzinfo=timezone.utc))]
        self.columns = ["Open", "High", "Low", "Close", "Volume"]
        self._values = {
            "Open": [7735.169921875],
            "High": [7771.47998046875],
            "Low": [7700.91015625],
            "Close": [7709.89990234375],
            "Volume": [65_680_000],
        }

    def __getitem__(self, key: str) -> _Serie:
        return _Serie(self._values[key])


class _TickerFalso:
    def __init__(self, symbol: str) -> None:
        self.symbol = symbol
        self._history = _FrameFalso()

    def history(self, **_: object) -> _FrameFalso:
        return self._history

    def get_history_metadata(self) -> dict[str, object]:
        return {
            "symbol": self.symbol,
            "currency": "USD",
            "instrumentType": "INDEX",
            "exchangeName": "SNP",
            "exchangeTimezoneName": "America/New_York",
            "regularMarketPrice": 7711.759765625,
            "previousClose": 7730.99,
            "regularMarketDayHigh": 7771.48,
            "regularMarketDayLow": 7700.91,
            "regularMarketVolume": 4_297_560_000,
            "regularMarketChangePercent": -0.249,
            "regularMarketTime": datetime(2026, 8, 28, 20, 37, tzinfo=timezone.utc),
            "dataGranularity": "1m",
            "currentTradingPeriod": {
                "regular": {
                    "start": datetime(2026, 8, 28, 13, 30, tzinfo=timezone.utc),
                    "end": datetime(2026, 8, 28, 20, 0, tzinfo=timezone.utc),
                }
            },
        }


class YahooSP500SourceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.requested_symbols: list[str] = []

        def factory(symbol: str) -> _TickerFalso:
            self.requested_symbols.append(symbol)
            return _TickerFalso(symbol)

        self.adapter = AdaptadorYahooSP500(ticker_factory=factory)

    def test_rest_usa_exclusivamente_gspc_y_conserva_numeros_del_proveedor(self) -> None:
        now = datetime(2026, 8, 30, 16, 0, tzinfo=timezone.utc)
        result = self.adapter.obtener_evento_snapshot(now_utc=now)

        self.assertTrue(result.exito, getattr(result, "error", None))
        event = result.datos
        self.assertEqual(["^GSPC"], self.requested_symbols)
        self.assertEqual("INDEX_MARKET_SNAPSHOT", event.event_type)
        self.assertEqual("yahoo_finance", event.source)
        self.assertEqual("SHADOW", event.environment)
        self.assertEqual("US500", event.instrument)
        self.assertEqual("^GSPC", event.symbol_id)
        self.assertEqual(771_176, event.payload["last_price_scaled"])
        self.assertEqual(100, event.payload["price_scale"])
        self.assertEqual(4_297_560_000, event.payload["day_volume"])
        self.assertEqual("CLOSED", event.payload["market_state"])
        self.assertEqual("2026-08-28T20:37:00Z", event.payload["source_timestamp_utc"])
        self.assertNotIn("bid", event.payload)
        self.assertNotIn("ask", event.payload)

    def test_websocket_rechaza_cualquier_simbolo_que_no_sea_gspc(self) -> None:
        result = self.adapter.mapear_mensaje_websocket(
            {"id": "AAPL", "price": 230.1, "time": 1_787_948_220_000},
            received_at_utc=datetime(2026, 8, 30, 16, 0, tzinfo=timezone.utc),
        )

        self.assertFalse(result.exito)
        self.assertEqual("INSTRUMENT_NOT_ALLOWED", result.error.codigo)

    def test_websocket_no_inventa_bid_ask_ausentes(self) -> None:
        result = self.adapter.mapear_mensaje_websocket(
            {
                "id": "^GSPC",
                "price": 7711.76,
                "time": 1_787_948_220_000,
                "market_hours": 1,
                "change_percent": -0.249,
            },
            received_at_utc=datetime(2026, 8, 28, 20, 37, 1, tzinfo=timezone.utc),
        )

        self.assertTrue(result.exito, getattr(result, "error", None))
        payload = result.datos.payload
        self.assertEqual("WEBSOCKET", payload["transport"])
        self.assertEqual(771_176, payload["last_price_scaled"])
        self.assertNotIn("bid_scaled", payload)
        self.assertNotIn("ask_scaled", payload)

    def test_fallo_de_red_devuelve_error_tipado_reintentable_sin_terminar_proceso(self) -> None:
        def factory_fallida(_: str) -> _TickerFalso:
            raise OSError("dns no disponible")

        result = AdaptadorYahooSP500(ticker_factory=factory_fallida).obtener_evento_snapshot()

        self.assertFalse(result.exito)
        self.assertEqual("INTERNAL_ERROR", result.error.codigo)
        self.assertTrue(result.error.reintentable)
        self.assertEqual("YAHOO_SOURCE_UNAVAILABLE", result.error.detalles["reason_code"])


if __name__ == "__main__":
    unittest.main()
