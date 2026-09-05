"""Regresiones del monitor: datos visibles, procedencia y diagnóstico de transición."""

from datetime import datetime, timedelta, timezone
import http.client
import json
from pathlib import Path
import tempfile
import threading
import unittest

from tests.conftest import REPO_ROOT, SRC_ROOT

from sistema_luces.domain.api import SolicitudConsulta
from sistema_luces.domain.event import SobreEventoV1, compute_payload_hash
from sistema_luces.observability.projections import ProyectorVistas
from sistema_luces.ui.views import render_dashboard_html
from sistema_luces.ui.server import ServidorLoopback
from sistema_luces.storage.event_store import ArchivoEventos
from scripts.iniciar_servidor_luces import cargar_proyector_desde_db


class TestMonitorDiagnostico(unittest.TestCase):
    def setUp(self) -> None:
        self.t0 = datetime.now(timezone.utc).replace(microsecond=0)
        self.proyector = ProyectorVistas()

    def _evento(
        self,
        numero: int,
        event_type: str,
        payload: dict[str, object],
        *,
        source_sequence: int | None = None,
    ) -> SobreEventoV1:
        raw = f"{numero:032x}"
        event_id = f"{raw[:8]}-{raw[8:12]}-{raw[12:16]}-{raw[16:20]}-{raw[20:]}"
        return SobreEventoV1(
            event_id=event_id,
            event_type=event_type,
            schema_version=1,
            occurred_at_utc=self.t0 + timedelta(milliseconds=numero),
            received_at_utc=self.t0 + timedelta(milliseconds=numero + 1),
            persisted_at_utc=None,
            source="replay",
            environment="REPLAY",
            source_account_id_hash=None,
            instrument="US500",
            symbol_id="US500",
            source_sequence=source_sequence,
            correlation_id=event_id,
            causation_id=None,
            payload_hash=compute_payload_hash(payload),
            previous_hash=None,
            payload=payload,
        )

    def _vista(self):
        resultado = self.proyector.consultar(
            SolicitudConsulta(
                correlation_id="00000000-0000-0000-0000-000000000099",
                environment="REPLAY",
                view="FEED",
                as_of_event_id=None,
                cursor=None,
                limit=50,
            )
        )
        self.assertTrue(resultado.exito)
        return resultado.datos

    def test_senal_alimenta_barra_de_diagnostico(self) -> None:
        """El mismo SIGNAL_EMITTED que cambia la luz debe alimentar el diagnóstico visible."""
        self.proyector.actualizar_desde_evento(
            self._evento(
                1,
                "QUOTE_TICK",
                {
                    "bid": 500000,
                    "ask": 500040,
                    "price_scale": 100,
                    "size_bid": 25,
                    "size_ask": 30,
                },
                source_sequence=1,
            )
        )
        self.proyector.actualizar_desde_evento(
            self._evento(
                2,
                "SIGNAL_EMITTED",
                {
                    "light": "GREEN",
                    "direction": "LONG",
                    "calibrated_probability_long": 720000,
                    "calibrated_probability_short": 280000,
                    "threshold_green": 650000,
                    "threshold_red": 350000,
                    "model_id": "logreg-us500",
                    "model_version": "1.0.0",
                    "model_hash": "a" * 64,
                },
            )
        )

        html = render_dashboard_html(self._vista())

        self.assertIn("Diagnóstico de transición", html)
        self.assertIn('role="progressbar"', html)
        self.assertIn("72.0%", html)
        self.assertIn("Umbral verde: 65.0%", html)
        self.assertIn("Umbral rojo: 35.0%", html)
        self.assertIn("VERDE alcanzado por +7.0 pp", html)

    def test_quote_us500_no_inventa_relaciones_aapl_tsla(self) -> None:
        """Un quote exclusivo de US500 no es evidencia de precios o scores de AAPL/TSLA."""
        self.proyector.actualizar_desde_evento(
            self._evento(
                3,
                "QUOTE_TICK",
                {
                    "bid": 500000,
                    "ask": 500040,
                    "price_scale": 100,
                    "size_bid": 40,
                    "size_ask": 10,
                },
                source_sequence=2,
            )
        )

        vista = self._vista()

        self.assertEqual((), vista.balancines)
        self.assertIsNone(vista.beta_kalman)
        self.assertIsNone(vista.z_score)
        self.assertIsNone(vista.drawdown_diario_pct)
        self.assertIsNone(vista.limite_por_trade_pct)
        self.assertIsNone(vista.pnl_paper_acumulado)

    def test_snapshot_multi_activo_real_alimenta_barras_por_relacion(self) -> None:
        """AAPL/TSLA sólo aparecen después de recibir un snapshot explícito con procedencia."""
        self.proyector.actualizar_desde_evento(
            self._evento(
                4,
                "QUOTE_TICK",
                {"bid": 500000, "ask": 500040, "price_scale": 100},
                source_sequence=3,
            )
        )
        self.proyector.actualizar_desde_evento(
            self._evento(
                5,
                "CROSS_ASSET_SNAPSHOT",
                {
                    "source_name": "captura-demo-read-only",
                    "data_age_ms": 80,
                    "relations": [
                        {
                            "key": "SP500_TSLA",
                            "name": "S&P 500 vs. TSLA",
                            "category": "High-Beta Momentum",
                            "symbol_y": "TSLA",
                            "symbol_x": "US500",
                            "price_y": 234.56,
                            "price_x": 5000.20,
                            "composite_score": 0.21,
                            "threshold_green": 0.35,
                            "threshold_red": -0.35,
                            "confidence_pct": 60.2,
                            "light": "YELLOW",
                            "direction": "MONITORIZAR",
                        },
                        {
                            "key": "SP500_AAPL",
                            "name": "S&P 500 vs. AAPL",
                            "category": "Ancla Sistémica",
                            "symbol_y": "AAPL",
                            "symbol_x": "US500",
                            "price_y": 198.75,
                            "price_x": 5000.20,
                            "composite_score": -0.14,
                            "threshold_green": 0.35,
                            "threshold_red": -0.35,
                            "confidence_pct": 56.8,
                            "light": "YELLOW",
                            "direction": "MONITORIZAR",
                        },
                    ],
                },
                source_sequence=4,
            )
        )

        vista = self._vista()
        html = render_dashboard_html(vista)

        self.assertEqual(2, len(vista.balancines))
        self.assertIn("234.56", html)
        self.assertIn("198.75", html)
        self.assertIn("60.0% hacia verde", html)
        self.assertIn("40.0% hacia rojo", html)
        self.assertIn("captura-demo-read-only", html)

    def test_snapshot_multi_activo_sin_procedencia_no_se_publica(self) -> None:
        """Una relación sin fuente y edad no debe atravesar la frontera de presentación."""
        self.proyector.actualizar_desde_evento(
            self._evento(
                11,
                "CROSS_ASSET_SNAPSHOT",
                {
                    "relations": [
                        {
                            "key": "SP500_TSLA",
                            "name": "S&P 500 vs. TSLA",
                            "symbol_y": "TSLA",
                            "symbol_x": "US500",
                            "price_y": 234.56,
                            "price_x": 5000.20,
                        }
                    ]
                },
            )
        )

        self.assertEqual((), self._vista().balancines)

    def test_ofi_usa_las_claves_reales_del_payload(self) -> None:
        """size_bid/size_ask del contrato QUOTE_TICK deben llegar a la proyección."""
        self.proyector.actualizar_desde_evento(
            self._evento(
                6,
                "QUOTE_TICK",
                {
                    "bid": 500000,
                    "ask": 500040,
                    "price_scale": 100,
                    "size_bid": 40,
                    "size_ask": 10,
                },
                source_sequence=5,
            )
        )

        self.assertEqual(30.0, self._vista().desbalance_ofi)

    def test_api_expone_el_mismo_diagnostico_y_proyector_inyectado(self) -> None:
        """El servidor debe publicar el proyector recibido, no un singleton vacío."""
        self.proyector.actualizar_desde_evento(
            self._evento(
                7,
                "QUOTE_TICK",
                {"bid": 500000, "ask": 500040, "price_scale": 100, "size_bid": 20, "size_ask": 10},
                source_sequence=6,
            )
        )
        self.proyector.actualizar_desde_evento(
            self._evento(
                8,
                "SIGNAL_EMITTED",
                {
                    "light": "GREEN",
                    "calibrated_probability_long": 720000,
                    "calibrated_probability_short": 280000,
                    "threshold_green": 650000,
                    "threshold_red": 350000,
                },
            )
        )
        server = ServidorLoopback(host="127.0.0.1", port=0, proyector=self.proyector)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            port = server.httpd.server_address[1]
            conn = http.client.HTTPConnection("127.0.0.1", port, timeout=2)
            conn.request("GET", "/v1/view")
            response = conn.getresponse()
            body = json.loads(response.read().decode("utf-8"))
            conn.close()
            self.assertEqual(200, response.status)
            self.assertEqual(5000.20, body["mid_price"])
            self.assertEqual(72.0, body["diagnostico_semaforo"]["probability_long_pct"])
        finally:
            server.shutdown()

    def test_arranque_reconstruye_event_log_en_vez_de_mostrar_vacio(self) -> None:
        """El comando standalone debe recuperar los eventos persistidos antes de servir."""
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "luces.db"
            store = ArchivoEventos(db_path)
            quote = self._evento(
                9,
                "QUOTE_TICK",
                {"bid": 500000, "ask": 500040, "price_scale": 100, "size_bid": 15, "size_ask": 5},
                source_sequence=7,
            )
            signal = self._evento(
                10,
                "SIGNAL_EMITTED",
                {
                    "light": "GREEN",
                    "calibrated_probability_long": 700000,
                    "calibrated_probability_short": 300000,
                    "threshold_green": 650000,
                    "threshold_red": 350000,
                },
            )
            self.assertTrue(store.anexar(quote).exito)
            self.assertTrue(store.anexar(signal).exito)

            restored, count = cargar_proyector_desde_db(db_path)
            result = restored.consultar(
                SolicitudConsulta(
                    correlation_id="00000000-0000-0000-0000-000000000100",
                    environment="REPLAY",
                    view="FEED",
                    as_of_event_id=None,
                    cursor=None,
                    limit=50,
                )
            )
            self.assertEqual(2, count)
            self.assertTrue(result.exito)
            self.assertEqual("HEALTHY", result.datos.health_state)
            self.assertEqual(70.0, result.datos.diagnostico_semaforo["probability_long_pct"])


if __name__ == "__main__":
    unittest.main()
