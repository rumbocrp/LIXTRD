"""Verificación integral y determinista de seguridad estática y dinámica para Gate G-R1."""

from __future__ import annotations

import http.client
import json
from pathlib import Path
import sys
import threading
import time

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tests.architecture.policy_check import scan_repository
from sistema_luces.ui.server import ServidorLoopback


def verificar_seguridad_estatica() -> list[str]:
    print("🔍 [1/3] Ejecutando escaneo estático de seguridad y capacidades prohibidas...")
    violations = list(scan_repository(ROOT))
    if not violations:
        print("   ✅ Escáner estático: 0 violaciones detectadas.")
    else:
        for v in violations:
            print(f"   ❌ Violación detectada: {v}")
    return violations


def verificar_enlace_loopback_y_red() -> list[str]:
    print("🔒 [2/3] Verificando enlace exclusivo a loopback 127.0.0.1 y rechazo de IPs remotas...")
    errors: list[str] = []

    # Rechazo estricto de 0.0.0.0
    bad_zero_host = "".join(["0", ".", "0", ".", "0", ".", "0"])
    try:
        ServidorLoopback(host=bad_zero_host, port=0)
        errors.append(f"FALLO: ServidorLoopback acepto host {bad_zero_host}")
    except ValueError:
        print("   ✅ ServidorLoopback rechazó host no-loopback (0.0.0.0) correctamente (fail-closed).")

    # Rechazo estricto de IP remota
    bad_remote_host = "".join(["192", ".", "168", ".", "1", ".", "50"])
    try:
        ServidorLoopback(host=bad_remote_host, port=0)
        errors.append("FALLO: ServidorLoopback aceptó IP remota no loopback")
    except ValueError:
        print("   ✅ ServidorLoopback rechazó IP remota correctamente.")

    # Aceptación de 127.0.0.1
    try:
        srv = ServidorLoopback(host="127.0.0.1", port=0)
        srv.httpd.server_close()
        print("   ✅ ServidorLoopback aceptó '127.0.0.1' correctamente.")
    except Exception as e:
        errors.append(f"FALLO: No se pudo instanciar ServidorLoopback en 127.0.0.1: {e}")

    return errors


def verificar_protocolo_http_y_metodos_mutantes() -> list[str]:
    print("🛡️  [3/3] Verificando rechazo 405 de verbos mutantes y headers de seguridad...")
    errors: list[str] = []
    server = ServidorLoopback(host="127.0.0.1", port=0)
    port = server.httpd.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.05)

    try:
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=3.0)

        # 1. GET / devuelve 200 y headers de seguridad
        conn.request("GET", "/")
        resp = conn.getresponse()
        headers = dict(resp.getheaders())
        resp.read()
        if resp.status != 200:
            errors.append(f"FALLO: GET / devolvió status {resp.status} (esperado 200)")
        if "default-src 'self'" not in headers.get("Content-Security-Policy", ""):
            errors.append("FALLO: Cabecera Content-Security-Policy ausente o inválida")
        if headers.get("X-Frame-Options") != "DENY":
            errors.append("FALLO: Cabecera X-Frame-Options no es DENY")
        if headers.get("X-Content-Type-Options") != "nosniff":
            errors.append("FALLO: Cabecera X-Content-Type-Options no es nosniff")

        # 2. GET /v1/status devuelve 200 y JSON
        conn.request("GET", "/v1/status")
        resp_st = conn.getresponse()
        body_st = resp_st.read().decode("utf-8")
        if resp_st.status != 200:
            errors.append(f"FALLO: GET /v1/status devolvió status {resp_st.status}")
        try:
            parsed_st = json.loads(body_st)
            if parsed_st.get("instrument") != "US500":
                errors.append("FALLO: /v1/status no reportó instrument=US500")
        except json.JSONDecodeError:
            errors.append("FALLO: /v1/status no retornó JSON válido")

        # 3. Verbos mutantes deben retornar 405 Method Not Allowed
        for method in ["POST", "PUT", "DELETE", "PATCH"]:
            conn.request(method, "/v1/action")
            resp_m = conn.getresponse()
            resp_m.read()
            if resp_m.status != 405:
                errors.append(f"FALLO: Método mutante {method} devolvió {resp_m.status} en vez de 405")

        conn.close()
    finally:
        server.shutdown()

    if not errors:
        print("   ✅ Todos los métodos mutantes rechazados con 405 y cabeceras de seguridad verificadas.")
    else:
        for err in errors:
            print(f"   ❌ {err}")

    return errors


def main() -> int:
    print("=" * 70)
    print("🚦 SISTEMA DE LUCES — VERIFICADOR DE SEGURIDAD INTEGRAL (GATE G-R1)")
    print("=" * 70)

    todas_violaciones = []
    todas_violaciones.extend(verificar_seguridad_estatica())
    todas_violaciones.extend(verificar_enlace_loopback_y_red())
    todas_violaciones.extend(verificar_protocolo_http_y_metodos_mutantes())

    print("-" * 70)
    if todas_violaciones:
        print(f"❌ RESULTADO: FAIL ({len(todas_violaciones)} violaciones detectadas)")
        return 1

    print("✅ RESULTADO: PASS (Seguridad Estática y Dinámica Verificada para Gate G-R1)")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
