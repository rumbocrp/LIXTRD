"""Servidor HTTP de sólo lectura en loopback 127.0.0.1 (SPEC-001 §10.6, CA-24)."""

from __future__ import annotations

import http.server
import json
from pathlib import Path
import sys
from typing import Any, Dict
import logging

from sistema_luces.domain.api import SolicitudConsulta
from sistema_luces.observability.projections import ProyectorVistas
from sistema_luces.ui.views import deducir_estado_ui, render_dashboard_html

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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

    def _parsear_query_params(self) -> dict:
        """Extrae parámetros de query string para soporte multi-activo."""
        params = {}
        if "?" in self.path:
            query_string = self.path.split("?", 1)[1]
            for param in query_string.split("&"):
                if "=" in param:
                    key, value = param.split("=", 1)
                    params[key] = value
        return params

    def _get_default_solicitud(self, instrumento: str = "US500") -> SolicitudConsulta:
        params = self._parsear_query_params()
        instrumento_param = params.get("instrument", instrumento)
        
        # Validar instrumento solicitado
        from sistema_luces.config.multi_asset_config import INSTRUMENTOS_PERMITIDOS
        if instrumento_param not in INSTRUMENTOS_PERMITIDOS:
            instrumento_param = "US500"  # Fallback seguro
        
        return SolicitudConsulta(
            correlation_id="00000000-0000-0000-0000-000000000001",
            environment="REPLAY",
            view="FEED",
            as_of_event_id=None,
            cursor=None,
            limit=50,
        )

    def _handle_dashboard_html(self) -> None:
        params = self._parsear_query_params()
        instrumento_solicitado = params.get("instrument", "US500")
        
        # Validar y seleccionar proyector
        from sistema_luces.config.multi_asset_config import INSTRUMENTOS_PERMITIDOS
        if instrumento_solicitado not in INSTRUMENTOS_PERMITIDOS:
            instrumento_solicitado = "US500"
        
        proyector_activo = getattr(self, "proyectores_multi", {}).get(instrumento_solicitado, self.proyector)
        
        solicitud = self._get_default_solicitud(instrumento_solicitado)
        res_vista = proyector_activo.consultar(solicitud)
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
        params = self._parsear_query_params()
        instrumento_solicitado = params.get("instrument", "US500")
        
        # Validar y seleccionar proyector
        from sistema_luces.config.multi_asset_config import INSTRUMENTOS_PERMITIDOS
        if instrumento_solicitado not in INSTRUMENTOS_PERMITIDOS:
            instrumento_solicitado = "US500"
        
        proyector_activo = getattr(self, "proyectores_multi", {}).get(instrumento_solicitado, self.proyector)
        
        solicitud = self._get_default_solicitud(instrumento_solicitado)
        res_vista = proyector_activo.consultar(solicitud)
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
        params = self._parsear_query_params()
        instrumento_solicitado = params.get("instrument", "US500")
        
        # Validar y seleccionar proyector
        from sistema_luces.config.multi_asset_config import INSTRUMENTOS_PERMITIDOS
        if instrumento_solicitado not in INSTRUMENTOS_PERMITIDOS:
            instrumento_solicitado = "US500"
        
        proyector_activo = getattr(self, "proyectores_multi", {}).get(instrumento_solicitado, self.proyector)
        
        solicitud = self._get_default_solicitud(instrumento_solicitado)
        res_vista = proyector_activo.consultar(solicitud)
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
    """Envoltorio del servidor HTTP vinculado exclusivamente a 127.0.0.1.
    
    FASE 1: Soporte multi-activo - mantiene proyectores independientes por instrumento.
    Cada instrumento (US500, XAUUSD, TSLA, AAPL) tiene su propio proyector y estado.
    FASE 6: Integración con actualizador de datos en vivo para polling continuo.
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8080,
        proyectores: Dict[str, ProyectorVistas] | None = None,
        habilitar_polling: bool = True,
        intervalo_polling: float = 5.0,
    ) -> None:
        if host != "127.0.0.1":
            raise ValueError(f"El servidor sólo puede escuchar en loopback (127.0.0.1), no en {host}")
        self.host = host
        self.port = port
        
        # FASE 1: Inicializar proyectores por instrumento si no se proporcionan
        if proyectores is None:
            from sistema_luces.config.multi_asset_config import INSTRUMENTOS_PERMITIDOS
            self.proyectores = {
                inst: ProyectorVistas(inst) for inst in INSTRUMENTOS_PERMITIDOS
            }
        else:
            self.proyectores = proyectores
        
        # Usar el proyector de US500 como default para compatibilidad backward
        default_proyector = self.proyectores.get("US500") or next(iter(self.proyectores.values()))
        
        # Una subclase local evita que dos servidores compartan accidentalmente el mismo proyector.
        handler_class = type(
            "ManejadorServidorLoopbackAislado",
            (ManejadorServidorLoopback,),
            {"proyector": default_proyector, "proyectores_multi": self.proyectores},
        )
        # ThreadingHTTPServer impide que una conexión especulativa/inactiva del navegador
        # bloquee todas las peticiones posteriores. El proyector protege sus snapshots
        # compartidos mediante RLock.
        self.httpd = ServidorHTTPConcurrente((host, port), handler_class)
        
        # FASE 6: Inicializar servicio de polling si está habilitado
        self._actualizador = None
        if habilitar_polling:
            try:
                from sistema_luces.sources.actualizador_multi_activo import crear_servicio_actualizacion
                self._actualizador = crear_servicio_actualizacion(
                    proyectores=self.proyectores,
                    intervalo=intervalo_polling,
                )
                logger.info(f"Polling multi-activo configurado (intervalo={intervalo_polling}s)")
            except ImportError as e:
                logger.warning(f"No se pudo importar el actualizador: {e}. Polling deshabilitado.")
    
    def iniciar_polling(self) -> None:
        """Inicia el servicio de polling de datos en vivo."""
        if self._actualizador:
            self._actualizador.iniciar()
        else:
            logger.warning("El actualizador no está disponible")
    
    def detener_polling(self) -> None:
        """Detiene el servicio de polling."""
        if self._actualizador:
            self._actualizador.detener()

    def serve_forever(self) -> None:
        # Iniciar polling antes de servir
        self.iniciar_polling()
        try:
            self.httpd.serve_forever()
        finally:
            self.detener_polling()

    def shutdown(self) -> None:
        self.detener_polling()
        self.httpd.shutdown()
        self.httpd.server_close()
