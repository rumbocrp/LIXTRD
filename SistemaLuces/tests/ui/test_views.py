"""Pruebas para el motor de vistas HTML y presentación cuantitativa densa (Milestone 3, SISTEMA-VISUAL.md)."""

from datetime import datetime, timezone
import unittest

from tests.conftest import REPO_ROOT, SRC_ROOT

from sistema_luces.domain.api import BalancinItemV1, DocumentoVistaV1, ProyeccionLecturaV1, VistaLectura
from sistema_luces.presentation.views import (
    deducir_estado_ui,
    format_metric_value,
    render_dashboard_html,
)


class TestRenderDashboardHtml(unittest.TestCase):
    """Verifica renderizado accesible, badges semánticos, diseño plano y telemetría densa."""

    def test_renderizado_correcto_dashboard(self) -> None:
        vista = VistaLectura(
            instrument="US500",
            environment="REPLAY",
            health_state="HEALTHY",
            data_age_ms=150,
            light="GREEN",
            reason_codes=("MODEL_EDGE_LONG",),
            model_id="logreg-v1",
            model_version="1.0.0",
            model_hash="a" * 64,
            policy_version="policy-v1",
            kill_switch_active=False,
            as_of_event_id="ev-01",
            next_cursor=None,
            documents=(),
        )

        html = render_dashboard_html(vista)
        self.assertIn("US500", html)
        self.assertIn("REPLAY", html)
        self.assertIn("GREEN", html)
        self.assertIn("HEALTHY", html)
        self.assertIn("MODEL_EDGE_LONG", html)

    def test_actualizacion_incremental_no_reemplaza_el_documento(self) -> None:
        """La carga inicial queda estable y delega cambios puntuales al recurso externo."""
        vista = VistaLectura(
            instrument="US500",
            environment="REPLAY",
            health_state="HEALTHY",
            data_age_ms=150,
            light="YELLOW",
            reason_codes=(),
            model_id=None,
            model_version=None,
            model_hash=None,
            policy_version="policy-v1",
            kill_switch_active=False,
            as_of_event_id="ev-incremental",
            next_cursor=None,
            documents=(),
        )

        rendered = render_dashboard_html(vista)

        self.assertNotIn('http-equiv="refresh"', rendered)
        self.assertIn('<script defer src="/assets/dashboard-v1.js"></script>', rendered)
        self.assertIn('data-bind="market-last"', rendered)
        self.assertIn('id="diagnostic-progress"', rendered)
        self.assertIn('id="update-status" role="status" aria-atomic="true"', rendered)

    def test_resiliencia_a_inyeccion_xss_en_campos_dinamicos(self) -> None:
        # Inyección maliciosa en reason_codes y health_state
        malicious_input = "<script>alert('XSS')</script>"
        vista = VistaLectura(
            instrument="US500",
            environment="REPLAY",
            health_state=malicious_input,
            data_age_ms=100,
            light="YELLOW",
            reason_codes=(malicious_input,),
            model_id=malicious_input,
            model_version="1.0.0",
            model_hash="b" * 64,
            policy_version="policy-v1",
            kill_switch_active=False,
            as_of_event_id="ev-99",
            next_cursor=None,
            documents=(),
        )

        html = render_dashboard_html(vista)
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;alert(&#x27;XSS&#x27;)&lt;/script&gt;", html)

    def test_format_metric_value_helper(self) -> None:
        self.assertIn('title="Sin datos">N/A</span>', format_metric_value(None))
        self.assertIn('title="Custom">N/A</span>', format_metric_value(None, null_reason="Custom"))
        self.assertEqual("74.50 %", format_metric_value(74.5, "%"))
        self.assertEqual("5,000 USD", format_metric_value(5000, "USD"))

    def test_topbar_monitoreo_cuantitativo_denso(self) -> None:
        """Verifica la barra superior con todas las dimensiones cuantitativas requeridas."""
        vista = VistaLectura(
            instrument="US500",
            environment="SHADOW",
            health_state="HEALTHY",
            data_age_ms=45,
            light="GREEN",
            reason_codes=("MODEL_BULLISH_SIGNAL",),
            model_id="logreg-v1",
            model_version="1.0.0",
            model_hash="a" * 64,
            policy_version="policy-v1",
            kill_switch_active=False,
            as_of_event_id="00000000-0000-0000-0000-000000000001",
            next_cursor=None,
            documents=(),
            bid=5000.00,
            ask=5000.40,
            spread=0.40,
            mid_price=5000.20,
            micro_price=5000.28,
            beta_kalman=1.042,
            z_score=-1.25,
            desbalance_ofi=35.2,
            drawdown_diario_pct=0.0,
            limite_por_trade_pct=50.0,
            slots_concurrentes_usados=0,
            slots_concurrentes_max=1,
            pnl_paper_acumulado=196.00,
            secuencia=1402,
            hash_snapshot="f3a8b9c1d2e3f4a5",
        )

        html = render_dashboard_html(vista)
        self.assertIn("quant-topbar", html)
        self.assertIn("5,000.00 USD / 5,000.40 USD", html)
        self.assertIn("Spread: 0.40 pts", html)
        self.assertIn('data-bind="top-micro">5,000.28 USD', html)
        self.assertIn('data-bind="top-mid">5,000.20 USD', html)
        self.assertIn('data-bind="top-ofi">35.20', html)
        self.assertIn('data-bind="top-beta">1.04', html)
        self.assertIn('data-bind="top-z">-1.25 σ', html)
        self.assertIn("Slots: 0 / 1", html)
        self.assertIn("Paper: +$196.00 USD", html)
        self.assertIn('data-bind="top-age">45 ms', html)
        self.assertIn('data-bind="top-sequence">#1402', html)
        self.assertIn('data-bind="top-hash">f3a8b9c1...', html)

    def test_panel_telemetria_multi_activo_balancines(self) -> None:
        """Verifica la renderización de la tabla de los 3 balancines macro/momentum/ancla."""
        balancines = (
            BalancinItemV1(
                key="GOLD_DXY",
                name="ORO vs. DÓLAR (DXY)",
                category="Macro Inverso",
                symbol_y="XAU/USD",
                symbol_x="DXY",
                price_y=2050.0,
                price_x=104.0,
                beta_kalman=-18.5,
                z_score=-0.45,
                ofi=12.0,
                micro_price=2050.15,
                mid_price=2050.0,
                light="YELLOW",
                direction="MONITORIZAR",
            ),
            BalancinItemV1(
                key="SP500_TSLA",
                name="S&P 500 vs. TSLA",
                category="High-Beta Momentum",
                symbol_y="TSLA",
                symbol_x="US500",
                price_y=220.0,
                price_x=5000.0,
                beta_kalman=0.045,
                z_score=1.80,
                ofi=-24.5,
                micro_price=219.90,
                mid_price=220.0,
                light="RED",
                direction="CORTO",
            ),
            BalancinItemV1(
                key="SP500_AAPL",
                name="S&P 500 vs. AAPL",
                category="Ancla Sistémica",
                symbol_y="AAPL",
                symbol_x="US500",
                price_y=185.0,
                price_x=5000.0,
                beta_kalman=0.037,
                z_score=-1.65,
                ofi=41.0,
                micro_price=185.12,
                mid_price=185.0,
                light="GREEN",
                direction="LARGO",
            ),
        )

        vista = VistaLectura(
            instrument="US500",
            environment="REPLAY",
            health_state="HEALTHY",
            data_age_ms=100,
            light="GREEN",
            reason_codes=(),
            model_id="logreg-v1",
            model_version="1.0.0",
            model_hash="a" * 64,
            policy_version="policy-v1",
            kill_switch_active=False,
            as_of_event_id="00000000-0000-0000-0000-000000000002",
            next_cursor=None,
            documents=(),
            balancines=balancines,
        )

        html = render_dashboard_html(vista)
        self.assertIn("ORO vs. DÓLAR (DXY)", html)
        self.assertIn("Macro Inverso", html)
        self.assertIn("S&amp;P 500 vs. TSLA", html)
        self.assertIn("High-Beta Momentum", html)
        self.assertIn("S&amp;P 500 vs. AAPL", html)
        self.assertIn("Ancla Sistémica", html)
        self.assertIn("2,050.00 / 104.00", html)
        self.assertIn("-18.50", html)
        self.assertIn("-0.45 σ", html)

    def test_sistema_visual_ausencia_de_box_shadow_glow_y_gradientes(self) -> None:
        """SISTEMA-VISUAL.md §1: Garantiza que no existen resplandores glow box-shadow ni degradados de fantasía."""
        vista = VistaLectura(
            instrument="US500",
            environment="REPLAY",
            health_state="HEALTHY",
            data_age_ms=100,
            light="GREEN",
            reason_codes=(),
            model_id="logreg-v1",
            model_version="1.0.0",
            model_hash="a" * 64,
            policy_version="policy-v1",
            kill_switch_active=False,
            as_of_event_id="ev-01",
            next_cursor=None,
            documents=(),
        )
        html = render_dashboard_html(vista)

        # Verificar ausencia total de box-shadow con glow difuso
        self.assertNotIn("box-shadow: 0 0", html)
        self.assertNotIn("box-shadow:0 0", html)
        self.assertNotIn("box-shadow:", html)
        self.assertNotIn("backdrop-filter", html)
        self.assertNotIn("linear-gradient", html)

        # Tipografía tabular monospace activa
        self.assertIn("font-variant-numeric: tabular-nums", html)

    def test_render_directo_desde_proyeccion_lectura_v1(self) -> None:
        """Verifica que render_dashboard_html acepte directamente una ProyeccionLecturaV1."""
        now = datetime(2026, 8, 30, 12, 0, 0, tzinfo=timezone.utc)
        proy = ProyeccionLecturaV1(
            schema_version=1,
            generated_at_utc=now,
            environment="REPLAY",
            instrument="US500",
            market_cutoff_utc=now,
            data_age_ms=120,
            health_state="HEALTHY",
            light="GREEN",
            direction="LARGO",
            reason_codes=("MODEL_BULLISH_SIGNAL",),
            model_id="logreg-champion-v1",
            model_version="1.0.0",
            model_hash="c" * 64,
            policy_version="policy-v1",
            transitions=(),
            simulations=(),
            metrics=(),
            incidents=(),
            kill_switch_active=False,
            ui_state="exito",
            as_of_event_id="00000000-0000-0000-0000-000000000003",
            bid=5000.10,
            ask=5000.50,
            spread=0.40,
            mid_price=5000.30,
            micro_price=5000.38,
            beta_kalman=1.042,
            z_score=-1.25,
            desbalance_ofi=35.2,
            pnl_paper_acumulado=250.00,
        )

        html = render_dashboard_html(proy)
        self.assertIn("US500", html)
        self.assertIn("VERDE · LARGO", html)
        self.assertIn("5,000.10 USD / 5,000.50 USD", html)
        self.assertIn("logreg-champion-v1", html)


if __name__ == "__main__":
    unittest.main()
