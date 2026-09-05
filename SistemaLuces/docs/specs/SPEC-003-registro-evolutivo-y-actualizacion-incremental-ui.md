# SPEC-003 — Registro evolutivo de defectos y actualización incremental de UI

**Versión:** 1.1.0
**Estado:** canónico; primera iteración implementada con evidencia técnica
**Corte:** 2026-08-30
**Alcance:** dashboard standalone de SistemaLuces; Trading Journal permanece intacto

## 1. Propósito

Esta SPEC convierte cada error verificado en una mejora trazable del producto. Un hallazgo no
se considera resuelto sólo porque desaparezca visualmente: debe conservar evidencia,
causa, invariante, prueba de regresión, estado y trabajo futuro.

La primera iteración reemplaza el refresco completo del documento por actualización parcial
de elementos. El navegador carga el HTML una vez y después consulta un snapshot JSON
liviano. La frecuencia del DOM no se presenta como frecuencia del mercado ni como garantía
del proveedor.

## 2. Flujo obligatorio para nuevos defectos

Cada defecto confirmado añade o actualiza una fila en el registro de la sección 3 y documenta:

1. identificador inmutable `ERR-AAAAMMDD-NNN` y severidad;
2. síntoma reproducible y evidencia observada;
3. causa raíz o, si no se conoce, hipótesis marcada explícitamente;
4. invariante que debe mantenerse después de la corrección;
5. pruebas de regresión y evidencia runtime proporcional al riesgo;
6. estado `VERIFICADO`, `EN_REPARACION`, `CORREGIDO_TECNICO`, `BLOCKED_EXTERNAL` o
   `REABIERTO`;
7. riesgo residual y siguiente mejora.

Un conteo global de pruebas no sustituye esta evidencia. Una reparación puede obtener
`CORREGIDO_TECNICO` sin aprobar las Puertas de producto R0–R7.

## 3. Registro de defectos verificados

| ID | Severidad | Síntoma y causa verificada | Invariante / regresión | Estado |
|---|---:|---|---|---|
| `ERR-20260830-001` | alta | Un fallo de resolución Yahoo intentaba construir un error con `SOURCE_UNAVAILABLE`, código fuera del catálogo, y rompía la ruta de degradación. | El adaptador devuelve `INTERNAL_ERROR` con detalle `YAHOO_SOURCE_UNAVAILABLE`, reintenta y conserva el último hecho verificable. `tests/sources/test_yahoo_sp500.py`. | `CORREGIDO_TECNICO` |
| `ERR-20260830-002` | alta | El servidor monohilo quedaba retenido por una conexión especulativa/inactiva y los cierres anticipados producían `BrokenPipeError`; el panel parecía caído aunque el proceso siguiera activo. | Listener concurrente, timeout por conexión, cierre explícito y aislamiento de desconexiones esperables. `tests/ui/test_server.py::test_conexion_inactiva_no_bloquea_otras_peticiones`. | `CORREGIDO_TECNICO` |
| `ERR-20260830-003` | media | El refresco mediante `meta refresh` sustituía el documento completo, interrumpía foco/lectura, repetía recursos y podía dejar una página de error en vez de conservar el último corte. La causa era usar navegación como mecanismo de sincronización. | No existe `meta refresh`; un recurso same-origin consulta `/v1/status`, modifica sólo nodos declarados, no usa `location.reload` ni `innerHTML`, preserva datos ante fallo y aplica backoff. `tests/ui/test_views.py` y `tests/ui/test_server.py`. | `CORREGIDO_TECNICO` |
| `ERR-20260830-004` | alta | Una primera interpretación del requerimiento de oro lo aislaba y retiraba SP500/TSLA/AAPL de esa vista. La corrección del dueño exige que los cuatro permanezcan juntos y que cada uno pueda tener diagnóstico propio. | Un único `market_assets` contiene exactamente `^GSPC`, `TSLA`, `AAPL`, `GC=F`; actualizaciones parciales no borran filas y cada una reserva `diagnostico_semaforo` independiente. `tests/sources/test_yahoo_multi_asset.py`. | `CORREGIDO_TECNICO` |

## 4. Contrato de actualización incremental V1

### 4.1 Carga y transporte

- El HTML se solicita una vez durante la navegación inicial.
- `/assets/dashboard-v1.js` es externo, same-origin, empaquetado con la aplicación y servido
  con `Cache-Control: no-store`.
- CSP permite únicamente scripts y conexiones del mismo origen; no permite script inline ni
  evaluación dinámica.
- El cliente consulta `GET /v1/status` cada `2 000 ms` con la pestaña visible y cada
  `10 000 ms` con la pestaña oculta.
- Una solicitud tiene timeout de `4 000 ms`. No puede existir más de una solicitud en curso.
- Un fallo activa backoff exponencial hasta `30 000 ms`. Al recuperar visibilidad se solicita
  un corte inmediato, sin crear un segundo bucle.

### 4.2 Escrituras en el DOM

- Las escrituras se agrupan en `requestAnimationFrame`.
- Sólo cambian los nodos con contrato `data-bind`, `data-asset-field`, las clases de las
  lámparas y los atributos accesibles de las barras.
- Está prohibido reemplazar `body`, `dashboard-current-region` o el documento completo.
- Está prohibido insertar HTML proveniente del endpoint; texto, razones y metadatos se
  escriben con `textContent`/nodos creados localmente.
- El layout reserva la estructura de la barra diagnóstica aun cuando esté en N/A para evitar
  saltos inesperados.

### 4.3 Honestidad y fallos

- Una respuesta válida actualiza precio, OHLC, variación, volumen, timestamps, transporte,
  latencias, salud, luz, razones y diagnóstico disponibles.
- Un fallo HTTP, timeout o JSON inválido conserva el último dato verificado y cambia sólo el
  estado de conexión a reintento.
- La hora `Corte DOM` identifica cuándo el navegador aplicó la respuesta; no es timestamp de
  mercado.
- Yahoo puede actualizar por WebSocket o por REST 1m. Consultar el endpoint cada 2 segundos
  no convierte un snapshot de Yahoo en un tick nuevo ni elimina su demora no divulgada.
- El proceso 24/7 no implica precio 24/7: `MERCADO CERRADO`, timestamp y edad permanecen
  visibles.

### 4.4 Barra diagnóstica

- `diagnostico_semaforo` es la única fuente de probabilidad y umbrales.
- La estructura exige `probability_long_pct`, `probability_short_pct`,
  `threshold_green_pct` y `threshold_red_pct`, todos finitos y dentro de `0…100`; el umbral
  rojo no puede superar al verde.
- Sin un `SIGNAL_EMITTED` verificable, la barra muestra N/A. Un precio de Yahoo nunca se
  transforma en probabilidad, score, distancia a verde o distancia a rojo.
- Con datos válidos se actualizan marcador, `aria-valuenow`, texto largo/corto, umbrales,
  distancia, fuente y evento.
- Error, conflicto u obsolescencia fuerzan la salida visual a amarillo aunque la barra
  conserve la señal base para diagnóstico.
- Cada elemento de `market_assets` puede contener otro `diagnostico_semaforo` con el mismo
  contrato. Su barra pertenece sólo a ese símbolo; ausencia muestra N/A y no copia la señal
  central ni la de otra fila.

### 4.5 Accesibilidad

- Una sola región `role="status"` y atómica anuncia cambios de conexión, no cada cifra.
- Las actualizaciones no mueven foco, no reinician el scroll y no sustituyen nodos de
  navegación.
- La barra comunica número, texto y umbrales además del color.
- El sondeo no introduce animación continua ni altera la política de reduced motion.

## 5. Criterios de aceptación

| ID | Criterio | Evidencia mínima |
|---|---|---|
| `CA-INC-01` | El HTML no contiene refresco automático de documento. | Test de render. |
| `CA-INC-02` | El recurso JS es externo, same-origin y cubierto por CSP. | Test HTTP de recurso y cabeceras. |
| `CA-INC-03` | El cliente usa timeout, exclusión de solicitudes, intervalos visible/oculto y backoff. | Inspección contractual automatizada + prueba runtime. |
| `CA-INC-04` | No hay recarga de página ni inserción de HTML remoto. | Test negativo sobre el recurso. |
| `CA-INC-05` | Mercado y barra cambian mediante bindings estables. | Test HTML/endpoint y verificación manual de navegador. |
| `CA-INC-06` | Un fallo conserva el último dato y anuncia reintento una sola vez por transición. | Prueba de cliente pendiente de harness DOM. |
| `CA-INC-07` | Sin señal real, diagnóstico permanece N/A. | `tests/ui/test_yahoo_market_monitor.py`. |
| `CA-INC-08` | SP500, TSLA, AAPL y oro permanecen en una sola tabla y cada fila tiene barra independiente. | `tests/sources/test_yahoo_multi_asset.py`. |

`CA-INC-06` queda como deuda de automatización: la conducta está implementada, pero el gate
completo requiere un harness de navegador/DOM que simule timeout y recuperación. No bloquea
el uso técnico del monitor; sí impide declarar R5 aprobado.

## 6. Plan de mejora derivado

1. **R5-G1 — completado técnicamente:** polling JSON incremental y barra estable.
2. **R5-G2 — siguiente:** pruebas de navegador para fallo, recuperación, foco, scroll y
   pestaña oculta; medir solicitudes solapadas y layout shift.
3. **R5-G3 — posterior:** evaluar Server-Sent Events o WebSocket de proyección para enviar
   cambios, conservando `/v1/status` como recuperación y health check.
4. **R5-G4 — integración futura:** trasladar el contrato de bindings a componentes de
   `/luces` y al BFF same-origin del Trading Journal, sin tocar el Journal en este piloto.
5. **R5-G5 — observabilidad:** registrar latencia fuente→proyección→HTTP→DOM por tramos, sin
   mezclarla con la demora del proveedor.

## 7. Historial de cambios

| Versión | Fecha | Cambio |
|---|---|---|
| `1.0.0` | 2026-08-30 | Crea el flujo evolutivo, registra tres defectos y fija el contrato de actualización incremental V1. |
| `1.1.0` | 2026-08-30 | Corrige el alcance multi-activo, añade fusión por símbolo y diagnóstico independiente por fila. |
