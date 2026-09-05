"""Feedback loop de proyección y UI para snapshots reales de Yahoo ^GSPC."""

from datetime import datetime, timezone
import http.client
import json
import threading
import unittest
import uuid

from sistema_luces.domain.api import SolicitudConsulta
from sistema_luces.domain.event import SobreEventoV1, compute_payload_hash
from sistema_luces.observability.projections import ProyectorVistas
from sistema_luces.ui.views import render_dashboard_html
from sistema_luces.ui.server import ServidorLoopback


def _evento_yahoo() -> SobreEventoV1:
    payload = {
        "provider": "Yahoo Finance",
        "provider_symbol": "^GSPC",
        "instrument_type": "INDEX",
        "currency": "USD",
        "exchange": "SNP",
        "exchange_timezone": "America/New_York",
        "last_price_scaled": 771_176,
        "previous_close_scaled": 773_099,
        "day_open_scaled": 773_517,
        "day_high_scaled": 777_148,
        "day_low_scaled": 770_091,
        "price_scale": 100,
        "change_pct_scaled": -24_900,
        "percent_scale": 100_000,
        "day_volume": 4_297_560_000,
        "source_timestamp_utc": "2026-08-28T20:37:00Z",
        "received_at_utc": "2026-08-30T16:00:00Z",
        "fetch_latency_ms": 1585,
        "market_state": "CLOSED",
        "transport": "REST_1M",
        "data_granularity": "1m",
        "quote_status": "PROVIDER_DELAY_UNDISCLOSED",
    }
    occurred = datetime(2026, 8, 28, 20, 37, tzinfo=timezone.utc)
    received = datetime(2026, 8, 30, 16, 0, tzinfo=timezone.utc)
    return SobreEventoV1(
        event_id=str(uuid.uuid4()),
        event_type="INDEX_MARKET_SNAPSHOT",
        schema_version=1,
        occurred_at_utc=occurred,
        received_at_utc=received,
        persisted_at_utc=None,
        source="yahoo_finance",  # type: ignore[arg-type]
        environment="SHADOW",
        source_account_id_hash=None,
        instrument="US500",
        symbol_id="^GSPC",
        source_sequence=None,
        correlation_id=str(uuid.uuid4()),
        causation_id=None,
        payload_hash=compute_payload_hash(payload),
        previous_hash=None,
        payload=payload,
    )


class YahooMarketMonitorTests(unittest.TestCase):
    def test_snapshot_publico_llega_a_api_y_html_sin_crear_senal(self) -> None:
        projector = ProyectorVistas()
        self.assertTrue(projector.actualizar_desde_evento(_evento_yahoo()).exito)
        result = projector.consultar(
            SolicitudConsulta(
                correlation_id=str(uuid.uuid4()),
                environment="SHADOW",
                view="FEED",
                as_of_event_id=None,
                cursor=None,
                limit=10,
            )
        )

        self.assertTrue(result.exito, getattr(result, "error", None))
        view = result.datos
        self.assertEqual("SHADOW", view.environment)
        self.assertEqual("YELLOW", view.light)
        self.assertIsNone(view.bid)
        self.assertIsNone(view.ask)
        self.assertIsNone(view.diagnostico_semaforo)
        self.assertEqual(7711.76, view.market_data["last_price"])
        self.assertEqual("^GSPC", view.market_data["provider_symbol"])
        self.assertEqual("CLOSED", view.market_data["market_state"])

        html = render_dashboard_html(view)
        self.assertIn("Yahoo Finance", html)
        self.assertIn("^GSPC", html)
        self.assertIn("7,711.76", html)
        self.assertIn("MERCADO CERRADO", html)
        self.assertIn("PROVIDER_DELAY_UNDISCLOSED", html)
        self.assertIn("Diagnóstico de transición:</strong> N/A", html)
        self.assertIn('id="diagnostic-panel"', html)
        self.assertIn('id="diagnostic-empty" class="diagnostic-empty"', html)
        self.assertIn('data-bind="market-last"', html)
        self.assertNotIn("SP500 vs. AAPL", html)
        self.assertNotIn("SP500 vs. TSLA", html)

    def test_endpoint_http_publica_procedencia_y_timestamp_yahoo(self) -> None:
        projector = ProyectorVistas()
        projector.actualizar_desde_evento(_evento_yahoo())
        server = ServidorLoopback(host="127.0.0.1", port=0, proyector=projector)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            conn = http.client.HTTPConnection("127.0.0.1", server.httpd.server_address[1])
            conn.request("GET", "/v1/view")
            response = conn.getresponse()
            body = json.loads(response.read().decode("utf-8"))
            conn.close()
            self.assertEqual(200, response.status)
            self.assertEqual("Yahoo Finance", body["market_data"]["provider"])
            self.assertEqual("^GSPC", body["market_data"]["provider_symbol"])
            self.assertEqual("2026-08-28T20:37:00Z", body["market_data"]["source_timestamp_utc"])
            self.assertEqual(7711.76, body["market_data"]["last_price"])
            self.assertIsNone(body["bid"])
            self.assertIsNone(body["ask"])
        finally:
            server.shutdown()

    def test_proyeccion_continua_acota_snapshots_sin_perder_el_actual(self) -> None:
        projector = ProyectorVistas()
        events = [_evento_yahoo() for _ in range(1005)]
        result = projector.reconstruir(events)

        self.assertTrue(result.exito)
        self.assertEqual(1000, result.datos["FEED"])
        view = projector.consultar(
            SolicitudConsulta(
                correlation_id=str(uuid.uuid4()),
                environment="SHADOW",
                view="FEED",
                as_of_event_id=None,
                cursor=None,
                limit=1,
            )
        ).datos
        self.assertEqual(7711.76, view.market_data["last_price"])


if __name__ == "__main__":
    unittest.main()
