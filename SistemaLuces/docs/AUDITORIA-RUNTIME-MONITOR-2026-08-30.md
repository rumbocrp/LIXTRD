# Auditoría runtime del monitor — 2026-08-30

**Alcance:** dashboard standalone, proyección, servidor loopback, replay demostrativo y
relaciones SP500–AAPL/SP500–TSLA.  
**Fuera de alcance:** modificar Trading Journal, ejecutar órdenes o certificar una fuente
demo externa.  
**Veredicto:** monitor REPLAY reparado; integración demo observada continúa
`BLOCKED_EXTERNAL`.

## Evidencia de diagnóstico

La regresión mínima está en `tests/ui/test_diagnostic_monitor.py`. Antes de la reparación sus
cuatro casos fallaban: no existía barra diagnóstica, OFI daba cero, un quote de US500 creaba
cuatro relaciones inventadas y un snapshot explícito era ignorado. Después de la reparación
los cuatro pasan.

La prueba HTTP `tests/ui/test_server.py` valida bind exclusivo a loopback, CSP, endpoints de
lectura y rechazo de métodos mutantes. Las suites de proyección, contrato V1 y composition
root cubren compatibilidad y determinismo local.

## Hallazgos y tratamiento

| ID | Severidad | Hallazgo | Tratamiento / estado |
|---|---:|---|---|
| `MON-001` | crítica | `iniciar_servidor_luces.py` creaba siempre un proyector vacío. | Acepta `--db-path`/`SISTEMA_LUCES_DB_PATH` y reconstruye todo el event log; sin fuente declara `NO_DATA`. Corregido. |
| `MON-002` | alta | La demo iniciaba un hilo daemon y el proceso terminaba inmediatamente; además describía hechos en memoria como persistidos. | El replay permanece activo hasta `Ctrl+C` y su salida distingue proyección de persistencia. Corregido. |
| `MON-003` | alta | La pantalla no se actualizaba mientras cambiaba la proyección. | Sustituido el refresco completo por consulta JSON y actualización parcial de nodos cada 2 s; mantiene N/A y procedencia. Corregido técnicamente. |
| `MON-004` | crítica | Un quote exclusivo de US500 generaba precios, beta, z-score, OFI y scores hardcodeados para AAPL/TSLA/GOLD. | Eliminados del proyector y composition root. Las relaciones requieren `CROSS_ASSET_SNAPSHOT` explícito. Corregido. |
| `MON-005` | alta | El proyector leía `bid_size`/`ask_size`, mientras el adapter cTrader emitía `size_bid`/`size_ask`. | Se aceptan ambas formas; sin tamaños reales micro-price y OFI quedan N/A. Corregido. |
| `MON-006` | alta | El evento que cambiaba la luz no alimentaba un diagnóstico visible. | `SIGNAL_EMITTED` proyecta probabilidad larga/corta, umbrales, fuente y distancia en pp. Corregido. |
| `MON-007` | media | `/v1/view` y `/v1/status` omitían la telemetría nueva. | Ambos publican diagnóstico; `/v1/view` añade cotización, OFI, relaciones y linaje. Corregido. |
| `MON-008` | media | El handler compartía un proyector como estado de clase global. | Cada `ServidorLoopback` construye un handler aislado e inyecta su proyector. Corregido. |
| `MON-009` | alta | El estado UI podía seguir en éxito aunque la edad excediera 5 s. | La edad/stale preceden al estado proyectado y fuerzan presentación amarilla obsoleta. Corregido. |
| `MON-010` | crítica | El adaptador `ctrader_demo.py` sólo transforma mensajes inyectados; no implementa OAuth ni una conexión de mercado. | No se maquilla con fixtures. G-R3 permanece `BLOCKED_EXTERNAL` hasta contar con credenciales, capabilities read-only y sesiones reales. Pendiente externo. |
| `MON-011` | alta | El `HTTPServer` monohilo podía quedar ocupado por una conexión loopback abierta sin petición; el proceso y Yahoo seguían vivos, pero el panel no respondía. | Sustituido por `ThreadingHTTPServer`, timeout de conexión, cierre explícito y prueba adversarial con socket inactivo. Corregido. |
| `MON-012` | media | El mecanismo provisional de `meta refresh` reemplazaba el documento completo, reiniciaba el contexto de lectura y no podía preservar la vista ante un fallo HTTP. | Eliminado `meta refresh`; recurso JS same-origin con CSP, timeout, exclusión de solicitudes, backoff y actualización agrupada. SPEC-003 registra la regresión y el trabajo pendiente de harness DOM. Corregido técnicamente. |

## Contrato del diagnóstico

La barra principal usa la probabilidad larga como posición sobre `0…100 %`:

- `p_long >= threshold_green`: verde alcanzado; se muestra el exceso en puntos porcentuales;
- `p_long <= threshold_red`: rojo alcanzado; se muestra el exceso en puntos porcentuales;
- entre ambos: amarillo; se muestran ambas distancias.

Cada relación multi-activo conserva su score compuesto y sus umbrales propios. La barra
secundaria expresa `abs(score) / abs(umbral objetivo)`; la confianza se muestra por separado
y nunca se llama progreso. Color, texto, número y `role="progressbar"` comunican el estado.

## Procedencia de SP500–AAPL/SP500–TSLA

Los documentos de `confidencial_trade` aportan la hipótesis de relación y una fórmula de
score como material conceptual. No prueban precios actuales, precisión ni una fuente activa.
Por ello:

1. un `QUOTE_TICK` de US500 no crea AAPL ni TSLA;
2. sólo `CROSS_ASSET_SNAPSHOT` puede crear esas filas;
3. el snapshot exige `source_name` y muestra `data_age_ms`;
4. el script de demostración usa `fixture-replay-cross-asset-v1`, identificado como REPLAY;
5. datos demo observados sólo podrán rotularse así después de G-R3.

## Riesgo de autocertificación de agentes

El handoff de Antigravity reportó una victoria basada en el número de tests. Esa conclusión
no era suficiente: los tests aceptaban valores hardcodeados y el proceso que escribía la
implementación también emitía el veredicto. Una suite verde demuestra únicamente las
aserciones incluidas. Desde este corte, los criterios críticos tienen pruebas negativas de
procedencia: ausencia de snapshot implica ausencia de AAPL/TSLA, y falta de tamaños implica
OFI/micro-price N/A.

## Cómo verificar

```bash
python3.11 -B -m unittest tests.ui.test_diagnostic_monitor -v
python3.11 -B -m unittest tests.ui.test_views tests.ui.test_server -v
python3.11 -B -m unittest tests.observability.test_projections -v
python3.11 -B -m unittest tests.application.test_composition_root -v
python3.11 -B scripts/verificar_documentacion.py
```

`make verify` sigue siendo una verificación técnica del repositorio; no sustituye las cinco
sesiones, economía del contrato ni aprobación humana exigidas por G-R3/G-R6.
