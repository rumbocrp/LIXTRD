# WP-04 · Evidencia RED→GREEN (Calidad de Feed y Compuerta Depth)

> **HISTÓRICO:** baseline del primer intento; no acredita una Puerta R0–R7.

## Costuras preacordadas antes de escribir pruebas

La SPEC-001 aprobada fija estas costuras públicas para WP-04:

1. **Monitor de Calidad de Feed (`MonitorCalidadFeed`, CA-7):**
   - Inspección estricta de cada evento entrante contra condiciones de anomalía.
   - **Gaps de secuencia:** Si `source_sequence > last_sequence + 1`, emite sobre `GAP_DETECTED` con conteo de eventos perdidos, acción `FORCE_YELLOW_STOP_SIM` y pasa el estado de feed a `GAPPED`.
   - **Duplicados:** Detección por colisión de `event_id` o número de secuencia repetido, emitiendo sobre `DUPLICATE` con acción `IGNORE`.
   - **Fuera de orden (`OUT_OF_ORDER`):** Si `source_sequence < last_sequence`, emite alerta con acción `QUARANTINE`.
   - **Staleness / Envejecimiento de datos:** Cálculo de `ahora_utc - occurred_at_utc`. A 5000 ms es `HEALTHY`; a 5001 ms emite sobre `STALE` con acción `FORCE_YELLOW` y pasa el estado de feed a `STALE`.
   - **Clock rollback:** Si `occurred_at_utc < last_occurred_at`, emite alerta `CLOCK_ROLLBACK` con acción `FAIL_CLOSED`.
2. **Máquina de Estados de Feed (`GestorEstadoFeed`, CA-8):**
   - Estados: `INITIALIZING`, `HEALTHY`, `STALE`, `GAPPED`, `RECONNECTING`, `STOPPED`.
   - Transiciones gobernadas por la matriz de dominio §6.4. Toda transición genera un `TransicionEstadoV1` inmutable.
3. **Compuerta de Depth y Cuarentena (`EvaluadorCompuertaDepth`, CA-25, §12.7):**
   - Evaluación de sesiones de libro L2/Depth contra la política `DepthGatePolicyV1`.
   - Si no hay política o carece de aprobador explícito -> `status="QUARANTINED"` con `DEPTH_POLICY_MISSING`.
   - Si se tienen menos de 5 sesiones completas válidas -> `status="QUARANTINED"` con `DEPTH_SESSIONS_INSUFFICIENT`.
   - Si cualquier sesión viola los umbrales de la política (cobertura < 95%, continuidad < 99.99%, gaps > 0, OOO > 0, rollbacks > 0, ratio stale > 1%) -> `status="REJECTED"`.
   - Si 5 sesiones cumplen todos los criterios exactos -> `status="ACCEPTED"`.
   - En cualquier escenario de fallo o cuarentena de depth, los quote ticks (bid/ask) continúan operando sin interrupción.

## Ciclos verticales

### Ciclo 1 · Monitor de calidad y flujo saludable

- **RED:** `python3.11 -B -m unittest tests.feed.test_feed_quality -v` -> `ModuleNotFoundError: No module named 'sistema_luces.feed.quality'`.
- **GREEN:** Se implementó `MonitorCalidadFeed` en `src/sistema_luces/feed/quality.py` con seguimiento de secuencias y estado inicial.
- **Resultado GREEN:** `Ran 1 test`, `OK`.

### Ciclo 2 · Detección de gaps y transición a GAPPED

- **RED:** `python3.11 -B -m unittest tests.feed.test_feed_quality.FeedQualityTests.test_gap_en_secuencia_genera_alerta_y_pasa_a_gapped -v` -> Falla por ausencia de cálculo de gap.
- **GREEN:** Se integró la lógica de detección de salto de secuencia, cálculo de `missing_count` y emisión del sobre `GAP_DETECTED` con `FORCE_YELLOW_STOP_SIM`.
- **Resultado GREEN:** `Ran 2 tests`, `OK`.

### Ciclo 3 · Límite de Stale exacto en 5000 vs 5001 ms (CA-7)

- **RED:** `python3.11 -B -m unittest tests.feed.test_feed_quality.FeedQualityTests.test_feed_stale_exacto_en_5000_y_5001_ms -v` -> Falla por comparación laxa de milisegundos.
- **GREEN:** Se ajustó la comparación estricta de envejecimiento de datos: `age_ms > threshold_ms`.
- **Resultado GREEN:** `Ran 3 tests`, `OK`.

### Ciclo 4 · Eventos fuera de orden y clock rollback

- **RED:** `python3.11 -B -m unittest tests.feed.test_feed_quality.FeedQualityTests.test_evento_fuera_de_orden_genera_alerta_y_cuarentena -v` -> Falla por ausencia de ramas para OOO y rollback.
- **GREEN:** Se implementó la emisión de sobres `OUT_OF_ORDER` y `CLOCK_ROLLBACK` con sus payloads tipados.
- **Resultado GREEN:** `Ran 4 tests`, `OK`.

### Ciclo 5 · Gestor de estado de Feed y validación de transiciones

- **RED:** `python3.11 -B -m unittest tests.feed.test_feed_state -v` -> `ModuleNotFoundError: No module named 'sistema_luces.feed.state'`.
- **GREEN:** Se implementó `GestorEstadoFeed` en `src/sistema_luces/feed/state.py` conectado a `es_transicion_valida`.
- **Resultado GREEN:** `Ran 2 tests`, `OK`.

### Ciclo 6 · Compuerta de Depth, suficiencia de sesiones y política de rechazo

- **RED:** `python3.11 -B -m unittest tests.feed.test_depth_gate -v` -> `ModuleNotFoundError: No module named 'sistema_luces.feed.depth_gate'`.
- **GREEN:** Se implementó `EvaluadorCompuertaDepth` en `src/sistema_luces/feed/depth_gate.py` con verificación completa de matriz §12.7.
- **Resultado GREEN:** `Ran 4 tests`, `OK`.

## Gate WP-04

- Comando: `make verify`
- Exit code: `0`
- Pruebas totales pasando: 157 (100% de la suite completa del repositorio).
- Calidad de feed, detección de anomalías y política de compuerta depth plenamente operativas y verificadas.
