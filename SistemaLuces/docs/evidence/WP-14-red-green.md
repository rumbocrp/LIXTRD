# WP-14 · Evidencia RED→GREEN (Casos de Uso Raíz y Loopback UI 127.0.0.1)

> **HISTÓRICO:** baseline del primer intento; no acredita una Puerta R0–R7.

## Costuras preacordadas antes de escribir pruebas

La SPEC-001 (§5.2, §10.6, §11.1, §12.6) y ADR-001 fijan estas costuras públicas para WP-14:

1. **Superficie Pública Raíz (`sistema_luces/__init__.py`, SPEC-001 §5.2, CA-2, CA-28):**
   - Exporta exactamente los cuatro casos de uso canónicos:
     - `ejecutar_replay(solicitud: SolicitudReplay) -> Resultado[ResumenEjecucion]`
     - `ejecutar_shadow(solicitud: SolicitudShadow) -> Resultado[ResumenEjecucion]`
     - `importar_demo_observada(solicitud: SolicitudImportacionDemo) -> Resultado[ResumenImportacion]`
     - `consultar_vista(solicitud: SolicitudConsulta) -> Resultado[VistaLectura]`
   - Cero símbolos de emisión de órdenes externas, modificación o cancelación.

2. **Casos de Uso de Aplicación (`application/`):**
   - `EjecutorReplay`: ejecución determinista sobre corpus de eventos en `REPLAY`.
   - `EjecutorShadow`: monitoreo en tiempo real acotado a capacidades de lectura.
   - `EjecutorImportacionDemo`: importación staged y reconciliación contra simulaciones.
   - `ConsultorVistas`: generación de vistas inmutables con hashes SHA-256.

3. **Interfaz de Usuario Local Loopback (`ui/server.py`, `ui/views.py`, SPEC-001 §10.6, §11.1, CA-24):**
   - Enlace estricto exclusivo a `127.0.0.1`.
   - **Invariante CA-24:** Verbos HTTP mutantes (`POST`, `PUT`, `DELETE`, `PATCH`) son rechazados con `405 Method Not Allowed`.
   - Cabeceras de seguridad estrictas: `Content-Security-Policy`, `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`.
   - **Resiliencia XSS (BUG-1):** Escape HTML determinista de todos los campos dinámicos y badges de estado.

---

## Ciclos verticales

### Ciclo 1 · Casos de uso de aplicación
- **RED:** `PYTHONPATH=src python3.11 -B -m unittest discover -s tests/application -v` -> `ModuleNotFoundError: No module named 'sistema_luces.application'`.
- **GREEN:** Implementación de `EjecutorReplay`, `EjecutorShadow`, `EjecutorImportacionDemo` y `ConsultorVistas` en `src/sistema_luces/application/`.
- **Resultado GREEN:** `Ran 4 tests`, `OK`.

### Ciclo 2 · Servidor loopback 127.0.0.1, rechazo 405 y renderizado XSS-safe
- **RED:** `PYTHONPATH=src python3.11 -B -m unittest discover -s tests/ui -v` -> `ModuleNotFoundError: No module named 'sistema_luces.ui'`.
- **GREEN:** Implementación de `ServidorLoopback`, `ManejadorServidorLoopback` y `render_dashboard_html` en `src/sistema_luces/ui/`.
- **Resultado GREEN:** `Ran 5 tests`, `OK`.

### Ciclo 3 · Exposición limpia en raíz `sistema_luces`
- **RED / GREEN:** Actualización de `src/sistema_luces/__init__.py` exportando exactamente las 4 funciones públicas.
- **Resultado GREEN:** `RootApiTests.test_root_api_exports_exactly_four_use_cases` pasa al 100%.

---

## Gate WP-14 & Milestone M6
- Comando: `PYTHONPATH=src python3.11 -B -m unittest discover -s tests/application -v && PYTHONPATH=src python3.11 -B -m unittest discover -s tests/ui -v`
- Pruebas pasando: 9 / 9 (100%).
- Verificación de repositorio (`make verify`): 308 / 308 pruebas pasando, `uv lock --check`, `compileall` y `tabnanny` limpios.
