import http.client
import socket
import threading
import time
import unittest

from tests.conftest import REPO_ROOT, SRC_ROOT

from sistema_luces.ui.server import ServidorLoopback


class TestServidorLoopback(unittest.TestCase):
    """Verifica enlace exclusivo a 127.0.0.1, rechazo con 405 en verbos mutantes y headers CSP."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.server = ServidorLoopback(host="127.0.0.1", port=0)
        cls.port = cls.server.httpd.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        time.sleep(0.05)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()

    def test_enlace_estricto_a_loopback(self) -> None:
        self.assertEqual("127.0.0.1", self.server.host)

    def test_get_retorna_200_y_headers_csp(self) -> None:
        conn = http.client.HTTPConnection("127.0.0.1", self.port)
        conn.request("GET", "/")
        resp = conn.getresponse()
        self.assertEqual(200, resp.status)
        headers = dict(resp.getheaders())
        self.assertIn("Content-Security-Policy", headers)
        csp = headers["Content-Security-Policy"]
        self.assertIn("default-src 'self'", csp)
        self.assertIn("script-src 'self'", csp)
        self.assertIn("connect-src 'self'", csp)
        self.assertNotIn("script-src 'none'", csp)
        self.assertEqual("DENY", headers.get("X-Frame-Options"))
        self.assertEqual("nosniff", headers.get("X-Content-Type-Options"))
        self.assertEqual("no-store", headers.get("Cache-Control"))
        self.assertEqual("close", headers.get("Connection"))
        body = resp.read().decode("utf-8")
        self.assertIn("Sistema de Luces", body)
        conn.close()

    def test_recurso_incremental_es_externo_seguro_y_no_recarga(self) -> None:
        conn = http.client.HTTPConnection("127.0.0.1", self.port)
        conn.request("GET", "/assets/dashboard-v1.js")
        resp = conn.getresponse()
        script = resp.read().decode("utf-8")
        headers = dict(resp.getheaders())
        conn.close()

        self.assertEqual(200, resp.status)
        self.assertEqual("application/javascript; charset=utf-8", headers.get("Content-Type"))
        self.assertIn('fetch("/v1/status"', script)
        self.assertIn("AbortController", script)
        self.assertIn("requestAnimationFrame", script)
        self.assertIn("visibilitychange", script)
        self.assertIn("requestRunning", script)
        self.assertIn("MAX_RETRY_MS", script)
        self.assertIn("setTimeout", script)
        self.assertNotIn("location.reload", script)
        self.assertNotIn("innerHTML", script)

    def test_metodos_mutantes_retornan_405_method_not_allowed_ca24(self) -> None:
        conn = http.client.HTTPConnection("127.0.0.1", self.port)
        for method in ["POST", "PUT", "DELETE", "PATCH"]:
            conn.request(method, "/api/action")
            resp = conn.getresponse()
            self.assertEqual(405, resp.status, f"Método {method} debió retornar 405")
            resp.read()
        conn.close()

    def test_servidor_endpoints_v1_status_y_view(self) -> None:
        import json
        conn = http.client.HTTPConnection("127.0.0.1", self.port)
        
        # Test /v1/status
        conn.request("GET", "/v1/status")
        resp = conn.getresponse()
        self.assertEqual(200, resp.status)
        data = json.loads(resp.read().decode("utf-8"))
        self.assertEqual("US500", data.get("instrument"))
        self.assertEqual("NO_DATA", data.get("health_state"))
        self.assertEqual("YELLOW", data.get("light"))
        self.assertEqual("vacio", data.get("ui_state"))
        self.assertIn("market_data", data)

        # Test /v1/view
        conn.request("GET", "/v1/view")
        resp_v = conn.getresponse()
        self.assertEqual(200, resp_v.status)
        data_v = json.loads(resp_v.read().decode("utf-8"))
        self.assertEqual("US500", data_v.get("instrument"))
        self.assertIsNone(data_v.get("model_id"))
        conn.close()

    def test_servidor_no_tiene_acoplamiento_con_quant(self) -> None:
        from sistema_luces.ui.server import ManejadorServidorLoopback
        self.assertFalse(hasattr(ManejadorServidorLoopback, "motor_quant"))

    def test_conexion_inactiva_no_bloquea_otras_peticiones(self) -> None:
        """Una conexión especulativa del navegador no puede congelar todo el panel."""
        server = ServidorLoopback(host="127.0.0.1", port=0)
        port = server.httpd.server_address[1]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        idle_socket = socket.create_connection(("127.0.0.1", port), timeout=1)
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=1)
        try:
            conn.request("GET", "/v1/status")
            response = conn.getresponse()
            response.read()
            self.assertEqual(200, response.status)
        finally:
            conn.close()
            idle_socket.close()
            server.shutdown()


if __name__ == "__main__":
    unittest.main()
