"""Batería de pruebas de sabotaje adversarial y verificación empírica de datos (Milestone M1 / Fase R1).

Objetivos de Sabotaje:
1. Sabotage Case 1: Probar ProyectorVistas.consultar() sin eventos o con estado degradado ->
   verificar que bajo ninguna circunstancia genera model_id ficticio o métricas inventadas,
   forzando light="YELLOW" y NO_DATA.
2. Sabotage Case 2: Probar render_dashboard_html() con datos ausentes (None/null) ->
   verificar que renderiza N/A con null_reason y jamás muestra 3.42, 74.5%, Pepperstone o claims de superioridad.
3. Sabotage Case 3: Verificar los 7 estados canónicos de UI con payloads límite/malformados ->
   verificar robustez, escape XSS y ausencia de crashes.
4. Sabotage Case 4: Intentar acceder a base de datos externa (tj.db) ->
   verificar rechazo por política de seguridad.
"""

from datetime import datetime, timezone
import hashlib
import html
from pathlib import Path
import tempfile
from typing import Any
import unittest
import uuid

from tests.architecture.policy_check import _scan_python, _scan_text, scan_repository
from tests.conftest import REPO_ROOT

from sistema_luces.domain.api import (
    SolicitudConsulta,
    VistaLectura,
    validar_solicitud_consulta,
)
from sistema_luces.domain.event import SobreEventoV1, canonical_json_bytes
from sistema_luces.domain.vocabulary import (
    ESTADOS_UI_PERMITIDOS,
    LUCES_PERMITIDAS,
    obtener_color_luz,
    obtener_texto_direccion,
    obtener_texto_luz,
    parse_environment,
    parse_estado_ui,
)
from sistema_luces.imports.journal_v1 import AdaptadorExportacionJournalV1
from sistema_luces.observability.projections import ProyectorVistas
from sistema_luces.ui.server import ServidorLoopback
from sistema_luces.ui.views import (
    deducir_estado_ui,
    format_metric_value,
    render_dashboard_html,
)


def _crear_evento_prueba(
    event_type: str = "QUOTE_TICK",
    environment: str = "REPLAY",
    payload: dict[str, Any] | None = None,
) -> SobreEventoV1:
    p = payload or {"bid": 500000, "ask": 500040, "instrument": "US500"}
    c_bytes = canonical_json_bytes(p)
    p_hash = hashlib.sha256(c_bytes).hexdigest()
    now = datetime.now(timezone.utc)

    return SobreEventoV1(
        event_id=f"ev-sabotage-{uuid.uuid4()}",
        event_type=event_type,
        schema_version=1,
        occurred_at_utc=now,
        received_at_utc=now,
        persisted_at_utc=None,
        source="simulator",
        environment=environment,  # type: ignore[arg-type]
        source_account_id_hash=None,
        instrument="US500",
        symbol_id="US500",
        source_sequence=1,
        correlation_id=str(uuid.uuid4()),
        causation_id=None,
        payload_hash=p_hash,
        previous_hash=None,
        payload=p,
    )


class TestSabotageCase1ProyectorVistas(unittest.TestCase):
    """Sabotage Case 1: ProyectorVistas.consultar() sin eventos o con estado degradado."""

    def test_proyector_vacio_nunca_inventa_model_id_o_metricas(self) -> None:
        """Verifica que un proyector sin eventos fuerza YELLOW, NO_DATA y model_id=None."""
        proyector = ProyectorVistas()

        vistas_a_probar = [
            "FEED",
            "LIGHTS",
            "SIGNALS",
            "SIMULATIONS",
            "METRICS",
            "SECURITY",
            "TRACE",
            "IMPORTS",
        ]

        for vista_nombre in vistas_a_probar:
            solicitud = SolicitudConsulta(
                correlation_id=str(uuid.uuid4()),
                environment="REPLAY",
                view=vista_nombre,  # type: ignore[arg-type]
                as_of_event_id=None,
                cursor=None,
                limit=10,
            )
            res = proyector.consultar(solicitud)
            self.assertTrue(res.exito, f"Falló consulta para vista {vista_nombre}: {res.error if not res.exito else ''}")
            vista = res.datos

            # Invariantes estrictos de ausencia de datos
            self.assertEqual("NO_DATA", vista.environment, "Ambiente debe ser NO_DATA si no hay eventos")
            self.assertEqual("NO_DATA", vista.health_state, "Estado de salud debe ser NO_DATA")
            self.assertEqual("YELLOW", vista.light, "Luz debe ser estrictamente YELLOW")
            self.assertIsNone(vista.model_id, "model_id jamás debe ser inventado ni tener defaults ficticios")
            self.assertIsNone(vista.model_version, "model_version debe ser None")
            self.assertIsNone(vista.model_hash, "model_hash debe ser None")
            self.assertIsNone(vista.as_of_event_id, "as_of_event_id debe ser None")
            self.assertEqual(("NO_DATA_YELLOW",), vista.reason_codes)
            self.assertEqual((), vista.documents, "No debe haber documentos generados")
            self.assertEqual("vacio", vista.ui_state, "ui_state debe ser vacio")

    def test_proyector_con_feed_degradado_fuerza_yellow_y_obsoleto(self) -> None:
        """Verifica que eventos de degradación fuercen luz YELLOW, estado STALE/GAPPED y ui_state obsoleto."""
        eventos_degradados = [
            ("STALE", "STALE"),
            ("GAPPED", "GAPPED"),
            ("OUT_OF_ORDER", "GAPPED"),
            ("CLOCK_ROLLBACK", "GAPPED"),
        ]

        for ev_type, expected_health in eventos_degradados:
            proyector = ProyectorVistas()
            ev = _crear_evento_prueba(
                event_type=ev_type,
                environment="REPLAY",
                payload={"anomaly": ev_type, "timestamp_utc": "2026-08-30T10:00:00Z"},
            )
            proyector.actualizar_desde_evento(ev)

            sol = SolicitudConsulta(
                correlation_id=str(uuid.uuid4()),
                environment="REPLAY",
                view="FEED",
                as_of_event_id=None,
                cursor=None,
                limit=10,
            )
            res = proyector.consultar(sol)
            self.assertTrue(res.exito, f"Falló consultar con evento {ev_type}")
            vista = res.datos

            self.assertEqual("YELLOW", vista.light, f"Luz debe forzarse a YELLOW tras {ev_type}")
            self.assertEqual(expected_health, vista.health_state)
            self.assertEqual("obsoleto", vista.ui_state, "Estado UI debe ser obsoleto ante feed degradado")
            self.assertIsNone(vista.model_id, "No debe haber model_id si no hubo evento de modelo")

    def test_proyector_reconstruir_lista_vacia_limpia_estado(self) -> None:
        """Verifica que proyector.reconstruir([]) deja el proyector en estado vacío seguro."""
        proyector = ProyectorVistas()
        ev1 = _crear_evento_prueba("QUOTE_TICK")
        proyector.actualizar_desde_evento(ev1)

        # Reconstruir con lista vacía
        res_rec = proyector.reconstruir([])
        self.assertTrue(res_rec.exito)

        sol = SolicitudConsulta(
            correlation_id=str(uuid.uuid4()),
            environment="REPLAY",
            view="FEED",
            as_of_event_id=None,
            cursor=None,
            limit=10,
        )
        res_vista = proyector.consultar(sol)
        self.assertTrue(res_vista.exito)
        vista = res_vista.datos
        self.assertEqual("NO_DATA", vista.health_state)
        self.assertEqual("YELLOW", vista.light)
        self.assertIsNone(vista.model_id)

    def test_solicitud_consulta_uuid_invalido_falla_seguro(self) -> None:
        """Verifica que correlation_id no UUID sea rechazado con VALIDATION_ERROR."""
        sol_invalida = SolicitudConsulta(
            correlation_id="no-es-uuid",
            environment="REPLAY",
            view="FEED",
            as_of_event_id=None,
            cursor=None,
            limit=10,
        )
        res = validar_solicitud_consulta(sol_invalida)
        self.assertFalse(res.exito)
        self.assertEqual("VALIDATION_ERROR", res.error.codigo)


class TestSabotageCase2RenderDashboardHtml(unittest.TestCase):
    """Sabotage Case 2: render_dashboard_html() con datos ausentes y strings prohibidos."""

    _FORBIDDEN_MOCKUP_PATTERNS = [
        "3.42",
        "74.5%",
        "-4.18%",
        "Pepperstone",
        "Margen de Error < 30% SUPERADO",
        "cTrader Live",
        "COMPRA FUERTE",
        "VENTA FUERTE",
        "logreg-v1",
        "AAPL",
        "TSLA",
        "Oro",
        "GOLD",
    ]

    def test_render_dashboard_con_vista_vacia_no_contiene_mockups(self) -> None:
        """Verifica que en estado vacío/ausente no aparezca NINGUNO de los valores hardcodeados históricos."""
        vista_vacia = VistaLectura(
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
            ui_state="vacio",
        )

        html_out = render_dashboard_html(vista_vacia, quant_state=None, ui_state=None)

        for pattern in self._FORBIDDEN_MOCKUP_PATTERNS:
            self.assertNotIn(
                pattern,
                html_out,
                f"SABOTAJE DETECTADO: El string prohibido '{pattern}' fue renderizado en el HTML.",
            )

        # Debe contener indicadores honestos
        self.assertIn("N/A", html_out)
        self.assertIn("NO_DATA_YELLOW", html_out)
        self.assertIn("Todavía no hay evidencia", html_out)
        self.assertIn("MONITORIZAR", html_out)
        self.assertIn("AMARILLO", html_out)

    def test_render_dashboard_con_quant_state_nulo_o_parcial(self) -> None:
        """Verifica renderizado honesto con diccionario quant explícitamente nulo."""
        vista = VistaLectura(
            instrument="US500",
            environment="REPLAY",
            health_state="HEALTHY",
            data_age_ms=100,
            light="GREEN",
            reason_codes=(),
            model_id=None,
            model_version=None,
            model_hash=None,
            policy_version="policy-v1",
            kill_switch_active=False,
            as_of_event_id="ev-123",
            next_cursor=None,
            documents=(),
            ui_state="parcial",
        )

        quant_nulo = {
            "us500_price": None,
            "bid": None,
            "ask": None,
            "hit_rate_pct": None,
            "error_rate_pct": None,
            "sharpe_ratio": None,
            "max_drawdown_pct": None,
        }

        html_out = render_dashboard_html(vista, quant_state=quant_nulo)

        for pattern in self._FORBIDDEN_MOCKUP_PATTERNS:
            self.assertNotIn(pattern, html_out)

        # Todas las métricas deben tener span metric-na con null_reason
        self.assertIn('class="metric-na" title="Precio no disponible">N/A</span>', html_out)
        self.assertIn('class="metric-na" title="Sin cálculo validado">N/A</span>', html_out)
        self.assertIn('class="metric-na" title="Requiere historial verificado">N/A</span>', html_out)

    def test_format_metric_value_helper(self) -> None:
        """Verifica que el formateador emita N/A con tooltip sanitizado ante None."""
        res_na = format_metric_value(None, "%", "Dato no disponible")
        self.assertEqual('<span class="metric-na" title="Dato no disponible">N/A</span>', res_na)

        res_val = format_metric_value(1234.567, "USD")
        self.assertEqual("1,234.57 USD", res_val)

        res_int = format_metric_value(500000, "cents")
        self.assertEqual("500,000 cents", res_int)


class TestSabotageCase3CanonicalUIStatesAndXSS(unittest.TestCase):
    """Sabotage Case 3: 7 estados canónicos de UI y resistencia a XSS/crashes."""

    def test_todos_los_7_estados_canonicos_renderizan_correctamente(self) -> None:
        """Verifica que cada uno de los 7 estados canónicos tenga su banner y comportamiento definido."""
        estados = ["cargando", "vacio", "parcial", "error", "obsoleto", "conflicto", "exito"]

        vista_base = VistaLectura(
            instrument="US500",
            environment="REPLAY",
            health_state="HEALTHY",
            data_age_ms=50,
            light="GREEN",
            reason_codes=(),
            model_id="m1",
            model_version="1.0",
            model_hash="h1",
            policy_version="policy-v1",
            kill_switch_active=False,
            as_of_event_id="ev-01",
            next_cursor=None,
            documents=(),
        )

        for estado in estados:
            html_out = render_dashboard_html(vista_base, ui_state=estado)  # type: ignore[arg-type]
            self.assertIn(f"ESTADO: {estado.upper()}", html_out)

            # Verificar banners distintivos
            if estado == "cargando":
                self.assertIn("Cargando telemetría", html_out)
                self.assertIn("AMARILLO", html_out)  # forzado a seguro
            elif estado == "vacio":
                self.assertIn("Todavía no hay evidencia", html_out)
                self.assertIn("AMARILLO", html_out)  # forzado a seguro
            elif estado == "obsoleto":
                self.assertIn("Datos obsoletos", html_out)
            elif estado == "error":
                self.assertIn("Condición de error", html_out)
                self.assertIn("AMARILLO", html_out)  # forzado a seguro
            elif estado == "conflicto":
                self.assertIn("Conflicto de versiones / Esquema", html_out)
                self.assertIn("AMARILLO", html_out)  # forzado a seguro
            elif estado == "parcial":
                self.assertIn("Telemetría parcial", html_out)
            elif estado == "exito":
                self.assertIn("Telemetría íntegra y verificada", html_out)

    def test_resiliencia_xss_en_todos_los_campos_inyectables(self) -> None:
        """Inyecta vectores de ataque XSS en todas las propiedades de VistaLectura y verifica escape estricto."""
        xss_payloads = [
            "<script>alert('XSS_ATTACK_01')</script>",
            "<img src=x onerror=alert('XSS_ATTACK_02')>",
            "<svg/onload=alert('XSS_ATTACK_03')>",
            "';alert('XSS_ATTACK_04');//",
            "<iframe src='javascript:alert(1)'>",
            "\" onmouseover=\"alert('XSS_ATTACK_05')\"",
        ]

        for payload in xss_payloads:
            vista_xss = VistaLectura(
                instrument=payload,
                environment=payload,  # type: ignore[arg-type]
                health_state=payload,
                data_age_ms=100,
                light="YELLOW",
                reason_codes=(payload, "<script>reason_xss()</script>"),
                model_id=payload,
                model_version=payload,
                model_hash=payload,
                policy_version=payload,
                kill_switch_active=False,
                as_of_event_id=payload,
                next_cursor=None,
                documents=(),
            )

            html_out = render_dashboard_html(vista_xss)

            # Invariante de seguridad: Ningún tag malicioso ejecutable sin escapar en HTML
            self.assertNotIn("<script>alert(", html_out)
            self.assertNotIn("<img src=x", html_out)
            self.assertNotIn("<svg/onload=", html_out)
            self.assertNotIn("<iframe", html_out)
            self.assertNotIn("<script>reason_xss()</script>", html_out)

            # Verificar que existe su versión escapada
            self.assertIn(html.escape(payload), html_out)

    def test_deducir_estado_ui_con_entradas_malformadas_o_limite(self) -> None:
        """Verifica robustez de deducir_estado_ui ante valores fuera de dominio o tipos inesperados."""
        vista = VistaLectura(
            instrument="US500",
            environment="REPLAY",
            health_state="UNKNOWN_STATE",
            data_age_ms=-999,
            light="YELLOW",
            reason_codes=(),
            model_id=None,
            model_version=None,
            model_hash=None,
            policy_version="policy-v1",
            kill_switch_active=False,
            as_of_event_id=None,
            next_cursor=None,
            documents=(),
        )

        # Sin as_of_event_id debe deducir vacio
        self.assertEqual("vacio", deducir_estado_ui(vista))

        # Con override inválido no debe romper y debe deducir
        self.assertEqual("vacio", deducir_estado_ui(vista, ui_state_override="INVALID_OVERRIDE"))  # type: ignore[arg-type]


class TestSabotageCase4SecurityPolicyAndDatabaseIsolation(unittest.TestCase):
    """Sabotage Case 4: Rechazo estricto de base externa (tj.db), capacidades prohibidas y entornos live."""

    def test_escaner_estatico_detecta_cualquier_referencia_a_tj_db(self) -> None:
        """Verifica que el escáner de arquitectura de security-policy-v1 detecte inmediatamente tj.db."""
        text_with_tj_db = 'import sqlite3\nconn = sqlite3.connect("tj.db")\n'
        violations = _scan_text(text_with_tj_db, "mock/test_file.py")
        self.assertTrue(any("FORBIDDEN_JOURNAL_DATABASE" in v for v in violations))

    def test_escaner_estatico_detecta_capacidades_de_ordenes(self) -> None:
        """Verifica detección estricta de capacidades de órdenes como place_order, submit_order, etc."""
        text_with_order = "def place_order(symbol, qty): pass"
        violations = _scan_text(text_with_order, "mock/orders.py")
        self.assertTrue(any("FORBIDDEN_ORDER_CAPABILITY" in v for v in violations))

    def test_repositorio_actual_pasa_escaner_estatico_con_cero_violaciones(self) -> None:
        """Verifica que el repositorio limpio tenga 0 violaciones de políticas."""
        violations = scan_repository(REPO_ROOT)
        self.assertEqual((), violations, f"Violaciones encontradas en repositorio: {violations}")

    def test_adaptador_journal_aislado_rechaza_archivos_no_json(self) -> None:
        """Verifica que AdaptadorExportacionJournalV1 no intente abrir bases SQLite y maneje binarios de forma segura."""
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_sqlite_db = Path(tmpdir) / "tj.db"
            fake_sqlite_db.write_bytes(b"SQLite format 3\x00\x10\x00\x01\x01\x00@  \x00\x00\x00")
            file_hash = hashlib.sha256(fake_sqlite_db.read_bytes()).hexdigest()

            adaptador = AdaptadorExportacionJournalV1()
            res = adaptador.cargar_desde_archivo(fake_sqlite_db, file_hash)

            # Debe fallar limpiamente como IMPORT_INVALID sin ejecutar conexiones SQLite
            self.assertFalse(res.exito)
            self.assertEqual("IMPORT_INVALID", res.error.codigo)

    def test_rechazo_invariable_de_entornos_live_real_prod(self) -> None:
        """Verifica que parse_environment rechace cualquier variante de LIVE/REAL/PROD."""
        prohibidos = ["LIVE", "live", "Live", "REAL", "real", "PROD", "prod", "PRODUCTION"]
        for p in prohibidos:
            res = parse_environment(p)
            self.assertFalse(res.exito)
            self.assertEqual("ENVIRONMENT_NOT_ALLOWED", res.error.codigo)


class TestAdvancedAdversarialProbes(unittest.TestCase):
    """Pruebas adicionales de penetración, límites numéricos y esterilización de entrada."""

    def test_proyector_con_payloads_vacios_o_anomalos(self) -> None:
        """Verifica que el proyector tolere eventos con payloads vacíos o tipos inesperados sin romperse."""
        proyector = ProyectorVistas()
        ev_vacio = _crear_evento_prueba("SIGNAL_EMITTED", payload={})
        proyector.actualizar_desde_evento(ev_vacio)

        sol = SolicitudConsulta(
            correlation_id=str(uuid.uuid4()),
            environment="REPLAY",
            view="SIGNALS",
            as_of_event_id=None,
            cursor=None,
            limit=10,
        )
        res = proyector.consultar(sol)
        self.assertTrue(res.exito)
        vista = res.datos
        self.assertEqual("YELLOW", vista.light)
        self.assertIsNone(vista.model_id)

    def test_render_dashboard_con_valores_cero_legitimos(self) -> None:
        """Verifica que valores numéricos 0 (cero) se rendericen explícitamente y no se confundan con None."""
        vista = VistaLectura(
            instrument="US500",
            environment="DEMO_OBSERVADO",
            health_state="HEALTHY",
            data_age_ms=10,
            light="GREEN",
            reason_codes=(),
            model_id="model-zero-test",
            model_version="1.0",
            model_hash="abc",
            policy_version="policy-v1",
            kill_switch_active=False,
            as_of_event_id="ev-zero",
            next_cursor=None,
            documents=(),
            ui_state="exito",
        )

        quant_cero = {
            "us500_price": 5000.0,
            "bid": 4999.5,
            "ask": 5000.5,
            "hit_rate_pct": 0.0,
            "error_rate_pct": 0.0,
            "sharpe_ratio": 0.0,
            "max_drawdown_pct": 0.0,
        }

        html_out = render_dashboard_html(vista, quant_state=quant_cero)
        self.assertIn("0.00 %", html_out)
        self.assertIn("0.00", html_out)
        self.assertIn("5,000.00 USD", html_out)

    def test_escaner_detecta_imports_dinamicos_prohibidos(self) -> None:
        """Verifica que el escáner AST atrape importaciones dinámicas de repositorios ajenos."""
        snippet1 = 'mod = __import__("trading_bot.gateway")\n'
        v1 = _scan_python(snippet1, "test_dyn.py", {"sistema_luces", "tests"})
        self.assertTrue(any("FORBIDDEN_REPOSITORY_IMPORT" in v for v in v1))

        snippet2 = 'import importlib\nm = importlib.import_module("journal.db")\n'
        v2 = _scan_python(snippet2, "test_dyn2.py", {"sistema_luces", "tests"})
        self.assertTrue(any("FORBIDDEN_REPOSITORY_IMPORT" in v for v in v2))

    def test_escaner_detecta_bind_no_loopback_y_secretos(self) -> None:
        """Verifica que el escáner atrape enlaces remotos (0.0.0.0, IPs públicas) y asignación de tokens."""
        code_bind = 'HOST = "0.0.0.0"\n'
        v_bind = _scan_text(code_bind, "net.py")
        self.assertTrue(any("FORBIDDEN_NON_LOOPBACK" in v for v in v_bind))

        code_secret = 'api_key = "abcdef1234567890abcdef1234567890"\n'
        v_sec = _scan_text(code_secret, "sec.py")
        self.assertTrue(any("SECRET_LEAK_DETECTED" in v for v in v_sec))


if __name__ == "__main__":
    unittest.main()
