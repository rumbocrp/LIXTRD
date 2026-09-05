"""Prueba externa opt-in del monitor Yahoo multi-activo."""

import os
import unittest

from sistema_luces.sources.yahoo_multi_asset import AdaptadorYahooMultiActivo, SIMBOLOS_YAHOO_MONITOR


@unittest.skipUnless(os.getenv("RUN_YAHOO_INTEGRATION") == "1", "requiere acceso externo explícito")
class YahooMultiAssetRealIntegrationTests(unittest.TestCase):
    def test_yahoo_entrega_los_cuatro_simbolos_con_precio_y_timestamp(self) -> None:
        result = AdaptadorYahooMultiActivo().obtener_evento_snapshot(timeout_seconds=15)

        self.assertTrue(result.exito, getattr(result, "error", None))
        self.assertEqual([], result.datos.payload["partial_failures"])
        assets = result.datos.payload["assets"]
        self.assertEqual(list(SIMBOLOS_YAHOO_MONITOR), [asset["provider_symbol"] for asset in assets])
        for asset in assets:
            self.assertGreater(asset["last_price_scaled"], 0)
            self.assertTrue(asset["source_timestamp_utc"].endswith("Z"))
            self.assertEqual("PROVIDER_DELAY_UNDISCLOSED", asset["quote_status"])
        gold = next(asset for asset in assets if asset["provider_symbol"] == "GC=F")
        self.assertEqual("FUTURE", gold["instrument_type"])
        self.assertEqual("CONTINUOUS_FUTURES_NOT_SPOT", gold["quote_scope"])


if __name__ == "__main__":
    unittest.main()
