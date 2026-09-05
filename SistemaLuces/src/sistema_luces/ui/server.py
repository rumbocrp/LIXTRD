"""Servidor HTTP de sólo lectura en loopback 127.0.0.1 (SPEC-001 §10.6, CA-24)."""

from __future__ import annotations

import http.server
import json
from pathlib import Path
import sys
from typing import Any

from sistema_luces.domain.api import SolicitudConsulta
from sistema_luces.observability.projections import ProyectorVistas
from sistema_luces.ui.views import deducir_estado_ui, render_dashboard_html

_ALLOWED_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
_CSP_HEADER = "default-src 'self'; script-src 'self'; connect-src 'self'; style-src 'self' 'unsafe-inline'; frame-ancestors 'none'; object-src 'none'; base-uri 'none';"
_DASHBOARD_SCRIPT_PATH = Path(__file__).with_name("dashboard-v1.js")


class ServidorHTTPConcurrente(http.server.ThreadingHTTPServer):
    """Listener loopback resistente a preconexiones y cierres anticipados del navegador."""

    daemon_threads = True
    allow_reuse_address = True
    request_queue_size = 32

    def handle_error(self, request: object, client_address: object) -> None:
        error = sys.exception()
        if isinstance(error, (BrokenPipeError, ConnectionResetError, TimeoutError)):
            return
        super().handle_error(request, client_address)  # type: ignore[arg-type]


class ManejadorServidorLoopback(http.server.BaseHTTPRequestHandler):
    """Manejador HTTP que sólo admite métodos de lectura y aplica cabeceras de seguridad estrictas."""

    proyector: ProyectorVistas = ProyectorVistas()

    def setup(self) -> None:
        """Evita que una conexión loopback inactiva retenga un worker indefinidamente."""
        super().setup()
        self.connection.settimeout(5.0)

    def do_GET(self) -> None:
        path = self.path.split("?", 1)[0]
        if path == "/assets/dashboard-v1.js":
            self._handle_dashboard_script()
        elif path in {"/v1/status", "/v1/status/", "/api/state", "/api/state/"}:
            self._handle_status_json()
        elif path in {"/v1/view", "/v1/view/", "/api/tick", "/api/tick/"}:
            self._handle_view_json()
        else:
            self._handle_dashboard_html()

    def _get_default_solicitud(self) -> SolicitudConsulta:
        return SolicitudConsulta(
            correlation_id="00000000-0000-0000-0000-000000000001",
            environment="REPLAY",
            view="FEED",
            as_of_event_id=None,
            cursor=None,
            limit=50,
        )

    def _handle_dashboard_html(self) -> None:
        solicitud = self._get_default_solicitud()
        res_vista = self.proyector.consultar(solicitud)
        if res_vista.exito:
            html_content = render_dashboard_html(res_vista.datos).encode("utf-8")
            self.send_response(200)
            self._send_security_headers("text/html; charset=utf-8", len(html_content))
            self.wfile.writelines([html_content])
        else:
            self.send_error(500, "Error interno al consultar vista")

    def _handle_dashboard_script(self) -> None:
        try:
            script = _DASHBOARD_SCRIPT_PATH.read_bytes()
        except OSError:
            self.send_error(500, "No se pudo cargar el actualizador del panel")
            return
        self.send_response(200)
        self._send_security_headers("application/javascript; charset=utf-8", len(script))
        self.wfile.writelines([script])

    def _handle_status_json(self) -> None:
        solicitud = self._get_default_solicitud()
        res_vista = self.proyector.consultar(solicitud)
        if res_vista.exito:
            vista = res_vista.datos
            ui_state = deducir_estado_ui(vista)
            light = vista.light if vista.light in {"GREEN", "YELLOW", "RED"} else "YELLOW"
            if ui_state in {"vacio", "cargando", "error", "conflicto", "obsoleto"}:
                light = "YELLOW"
            status_data = {
                "instrument": vista.instrument,
                "environment": vista.environment,
                "health_state": vista.health_state,
                "ui_state": ui_state,
                "light": light,
                "model_id": vista.model_id,
                "model_version": vista.model_version,
                "policy_version": vista.policy_version,
                "kill_switch_active": vista.kill_switch_active,
                "as_of_event_id": vista.as_of_event_id,
                "documents_count": len(vista.documents),
                "reason_codes": list(vista.reason_codes),
                "data_age_ms": vista.data_age_ms,
                "bid": vista.bid,
                "ask": vista.ask,
                "spread": vista.spread,
                "mid_price": vista.mid_price,
                "micro_price": vista.micro_price,
                "desbalance_ofi": vista.desbalance_ofi,
                "beta_kalman": vista.beta_kalman,
                "z_score": vista.z_score,
                "secuencia": vista.secuencia,
                "hash_snapshot": vista.hash_snapshot,
                "diagnostico_semaforo": vista.diagnostico_semaforo,
                "market_data": vista.market_data,
                "market_assets": list(vista.market_assets),
            }
            data = json.dumps(status_data).encode("utf-8")
            self.send_response(200)
            self._send_security_headers("application/json; charset=utf-8", len(data))
            self.wfile.writelines([data])
        else:
            self.send_error(500, "Error interno al consultar estado")

    def _handle_view_json(self) -> None:
        solicitud = self._get_default_solicitud()
        res_vista = self.proyector.consultar(solicitud)
        if res_vista.exito:
            vista = res_vista.datos
            view_data = {
                "instrument": vista.instrument,
                "environment": vista.environment,
                "health_state": vista.health_state,
                "data_age_ms": vista.data_age_ms,
                "light": vista.light,
                "model_id": vista.model_id,
                "model_version": vista.model_version,
                "policy_version": vista.policy_version,
                "kill_switch_active": vista.kill_switch_active,
                "as_of_event_id": vista.as_of_event_id,
                "documents": [
                    {
                        "schema_id": doc.schema_id,
                        "document_hash": doc.document_hash,
                        "payload": doc.payload,
                    }
                    for doc in vista.documents
                ],
                "reason_codes": list(vista.reason_codes),
                "ui_state": vista.ui_state,
                "bid": vista.bid,
                "ask": vista.ask,
                "spread": vista.spread,
                "mid_price": vista.mid_price,
                "micro_price": vista.micro_price,
                "beta_kalman": vista.beta_kalman,
                "z_score": vista.z_score,
                "desbalance_ofi": vista.desbalance_ofi,
                "balancines": [
                    item.to_dict() if hasattr(item, "to_dict") else item
                    for item in vista.balancines
                ],
                "diagnostico_semaforo": vista.diagnostico_semaforo,
                "secuencia": vista.secuencia,
                "hash_snapshot": vista.hash_snapshot,
                "salud_feed": vista.salud_feed,
                "market_data": vista.market_data,
                "market_assets": list(vista.market_assets),
            }
            data = json.dumps(view_data).encode("utf-8")
            self.send_response(200)
            self._send_security_headers("application/json; charset=utf-8", len(data))
            self.wfile.writelines([data])
        else:
            self.send_error(500, "Error interno al consultar vista")

    def do_HEAD(self) -> None:
        self.send_response(200)
        self._send_security_headers("text/html; charset=utf-8", 0)

    def do_OPTIONS(self) -> None:
        self.send_response(200)
        self.send_header("Allow", "GET, HEAD, OPTIONS")
        self._send_security_headers("text/plain", 0)

    def do_POST(self) -> None:
        self._reject_mutating_method()

    def do_PUT(self) -> None:
        self._reject_mutating_method()

    def do_DELETE(self) -> None:
        self._reject_mutating_method()

    def do_PATCH(self) -> None:
        self._reject_mutating_method()

    def _reject_mutating_method(self) -> None:
        """CA-24: Rechaza cualquier método mutante con 405 Method Not Allowed."""
        self.send_response(405)
        self.send_header("Allow", "GET, HEAD, OPTIONS")
        self._send_security_headers("text/plain", 0)

    def _send_security_headers(self, content_type: str, content_length: int) -> None:
        self.send_header("Content-Type", content_type)
        if content_length > 0:
            self.send_header("Content-Length", str(content_length))
        self.send_header("Content-Security-Policy", _CSP_HEADER)
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "close")
        self.end_headers()
        self.close_connection = True

    def log_message(self, format: str, *args: Any) -> None:
        # Desactivar logs por stdout para no contaminar salida de tests
        pass


class ServidorLoopback:
    """Envoltorio del servidor HTTP vinculado exclusivamente a 127.0.0.1."""

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8080,
        proyector: ProyectorVistas | None = None,
    ) -> None:
        if host != "127.0.0.1":
            raise ValueError(f"El servidor sólo puede escuchar en loopback (127.0.0.1), no en {host}")
        self.host = host
        self.port = port
        # Una subclase local evita que dos servidores compartan accidentalmente el mismo proyector.
        handler_class = type(
            "ManejadorServidorLoopbackAislado",
            (ManejadorServidorLoopback,),
            {"proyector": proyector or ProyectorVistas()},
        )
        # ThreadingHTTPServer impide que una conexión especulativa/inactiva del navegador
        # bloquee todas las peticiones posteriores. El proyector protege sus snapshots
        # compartidos mediante RLock.
        self.httpd = ServidorHTTPConcurrente((host, port), handler_class)

    def serve_forever(self) -> None:
        self.httpd.serve_forever()

    def shutdown(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()
