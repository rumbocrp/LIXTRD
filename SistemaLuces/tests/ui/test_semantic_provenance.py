"""Pruebas de interfaz para procedencia semántica, 7 estados canónicos y ausencia de datos ficticios."""

import unittest

from tests.conftest import REPO_ROOT, SRC_ROOT

from sistema_luces.domain.api import VistaLectura
from sistema_luces.ui.views import format_metric_value, render_dashboard_html


class SemanticProvenanceUITests(unittest.TestCase):
    """Verifica que la UI nunca presente datos sintéticos o vacíos como reales ni invente métricas."""

    def test_ui_never_renders_broker_name_for_synthetic_or_replay(self) -> None:
        """RB-L012, RNF-L005: Jamás debe aparecer el nombre de un broker o claim de cuenta real."""
        for env in ["SINTETICO", "REPLAY", "NO_DATA"]:
            vista = VistaLectura(
                instrument="US500",
                environment=env,  # type: ignore[arg-type]
                health_state="NO_DATA" if env == "NO_DATA" else "HEALTHY",
                data_age_ms=100,
                light="YELLOW",
                reason_codes=(),
                model_id=None,
                model_version=None,
                model_hash=None,
                policy_version="policy-v1",
                kill_switch_active=False,
                as_of_event_id="ev-01" if env != "NO_DATA" else None,
                next_cursor=None,
                documents=(),
            )
            html_out = render_dashboard_html(vista)

            # Verificación de ausencia de nombres de brokers falsos
            self.assertNotIn("Pepperstone", html_out)
            self.assertNotIn("cTrader Live", html_out)
            self.assertNotIn("Margen de Error < 30% SUPERADO", html_out)
            self.assertNotIn("COMPRA FUERTE", html_out)
            self.assertNotIn("VENTA FUERTE", html_out)

    def test_ui_renders_explicit_synthetic_badge_when_synthetic(self) -> None:
        """RF-L003: Datos en SINTETICO deben mostrar badge visible de laboratorio."""
        vista = VistaLectura(
            instrument="US500",
            environment="SINTETICO",
            health_state="HEALTHY",
            data_age_ms=50,
            light="GREEN",
            reason_codes=(),
            model_id=None,
            model_version=None,
            model_hash=None,
            policy_version="policy-v1",
            kill_switch_active=False,
            as_of_event_id="ev-synth-01",
            next_cursor=None,
            documents=(),
        )
        html_out = render_dashboard_html(vista)
        self.assertIn("LABORATORIO SINTÉTICO", html_out)
        self.assertIn("SINTETICO", html_out)

    def test_ui_empty_state_renders_na_without_phantom_metrics(self) -> None:
        """RF-L008, RF-L016: En estado vacio/NO_DATA, las métricas son N/A y la luz es AMARILLO/MONITORIZAR."""
        vista = VistaLectura(
            instrument="US500",
            environment="NO_DATA",
            health_state="NO_DATA",
            data_age_ms=None,
            light="YELLOW",
            reason_codes=("NO_DATA_YELLOW",),
            model_id=None,
            model_version=None,
            model_hash=None,
            policy_version="policy-v1",
            kill_switch_active=False,
            as_of_event_id=None,
            next_cursor=None,
            documents=(),
        )
        html_out = render_dashboard_html(vista)

        # Semáforo forzado en estado seguro
        self.assertIn("AMARILLO", html_out)
        self.assertIn("MONITORIZAR", html_out)
        self.assertIn("NO_DATA_YELLOW", html_out)
        self.assertIn("ESTADO: VACIO", html_out)
        self.assertIn("Todavía no hay evidencia", html_out)

        # Métricas deben ser N/A
        self.assertIn("N/A", html_out)
        self.assertNotIn("74.5%", html_out)
        self.assertNotIn("3.42", html_out)
        self.assertNotIn("-4.18%", html_out)

    def test_ui_renders_canonical_spanish_vocabulary(self) -> None:
        """RB-L001: Verde=LARGO, Amarillo=MONITORIZAR, Rojo=CORTO."""
        luces = [
            ("GREEN", "VERDE · LARGO"),
            ("YELLOW", "AMARILLO · MONITORIZAR"),
            ("RED", "ROJO · CORTO"),
        ]
        for light_code, expected_label in luces:
            vista = VistaLectura(
                instrument="US500",
                environment="REPLAY",
                health_state="HEALTHY",
                data_age_ms=100,
                light=light_code,  # type: ignore[arg-type]
                reason_codes=(),
                model_id="model-test",
                model_version="1.0.0",
                model_hash="abc",
                policy_version="policy-v1",
                kill_switch_active=False,
                as_of_event_id="ev-10",
                next_cursor=None,
                documents=(),
            )
            html_out = render_dashboard_html(vista, ui_state="exito")
            self.assertIn(expected_label, html_out)

    def test_ui_renders_all_7_canonical_states(self) -> None:
        """RF-L020: Renderizado correcto de los 7 estados canónicos."""
        estados = ["cargando", "vacio", "parcial", "error", "obsoleto", "conflicto", "exito"]

        for estado in estados:
            vista = VistaLectura(
                instrument="US500",
                environment="REPLAY",
                health_state="HEALTHY",
                data_age_ms=100,
                light="YELLOW",
                reason_codes=(),
                model_id=None,
                model_version=None,
                model_hash=None,
                policy_version="policy-v1",
                kill_switch_active=False,
                as_of_event_id="ev-01",
                next_cursor=None,
                documents=(),
            )
            html_out = render_dashboard_html(vista, ui_state=estado)  # type: ignore[arg-type]
            self.assertIn(f"ESTADO: {estado.upper()}", html_out)
            self.assertIn("<!DOCTYPE html>", html_out)


if __name__ == "__main__":
    unittest.main()
