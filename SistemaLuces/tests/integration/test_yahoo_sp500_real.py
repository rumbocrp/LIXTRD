"""Verificación opt-in contra Yahoo; no forma parte del gate offline determinista."""

import os
import unittest

from sistema_luces.sources.yahoo_sp500 import AdaptadorYahooSP500


@unittest.skipUnless(os.environ.get("RUN_YAHOO_INTEGRATION") == "1", "requiere red Yahoo explícita")
class YahooSP500RealIntegrationTests(unittest.TestCase):
    def test_gspc_real_tiene_precio_timestamp_y_procedencia_sin_bid_ask_inventados(self) -> None:
        result = AdaptadorYahooSP500().obtener_evento_snapshot(timeout_seconds=15)
        self.assertTrue(result.exito, getattr(result, "error", None))
        event = result.datos
        payload = event.payload
        self.assertEqual("^GSPC", payload["provider_symbol"])
        self.assertEqual("Yahoo Finance", payload["provider"])
        self.assertGreater(payload["last_price_scaled"], 0)
        self.assertRegex(payload["source_timestamp_utc"], r"^\d{4}-\d{2}-\d{2}T")
        self.assertIn(payload["market_state"], {"REGULAR", "CLOSED"})
        self.assertNotIn("bid", payload)
        self.assertNotIn("ask", payload)
        self.assertNotIn("SP500_AAPL", str(payload))
        self.assertNotIn("SP500_TSLA", str(payload))


if __name__ == "__main__":
    unittest.main()
