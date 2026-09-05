# WP-05 · Evidencia RED→GREEN (Casos y Snapshots 30/60 s)

> **HISTÓRICO:** baseline del primer intento; no acredita una Puerta R0–R7.

## Costuras preacordadas antes de escribir pruebas

La SPEC-001 y ADR-001 fijan estas costuras públicas para WP-05:

1. **Gestión de Ventanas Temporales S30 y S60 (`windows.py`):**
   - Límite de ventanas alineadas a fronteras canónicas en segundos exactos (:00, :30 para S30; :00 para S60).
   - Cálculo estricto de límites `[start_utc, end_utc)` y función de detección de cierre `es_cierre_de_ventana`.
2. **Cálculo de Features Causales y Hashing (`features.py`, CA-9, OPT-7):**
   - Extracción de variables a partir de ticks de cotización dentro de la ventana: `tick_count`, `spread_last`, `spread_mean`, `price_first_bid`, `price_last_bid`, `price_last_ask`, `price_return_points`, `price_high`, `price_low`, `volume_total`, `order_imbalance`, `data_age_ms`.
   - **Invariante de valores ausentes (ADR-001 §6):** Si un dato no es computable (e.g. 0 ticks o tamaños no provistos), se preserva como `None`, nunca se inventa un cero.
   - **Determinismo y Hashing (CA-9):** Generación de `feature_snapshot_hash` como SHA-256 sobre el JSON canónico del snapshot.
3. **Constructor de Casos V1 (`builder.py`, OPT-7, CA-9):**
   - Contrato `ConstructorCaso.construir(solicitud, buffer_eventos)`.
   - Exclusión estricta de eventos posteriores a `market_event_cutoff` (`occurred_at_utc > cutoff`).
   - Inelegibilidad automática (`eligible_for_signal = False`) ante feed degradado (`feed_health_state != "HEALTHY"`) o datos insuficientes.

## Ciclos verticales

### Ciclo 1 · Gestión y alineación de ventanas temporales S30/S60
- **RED:** `python3.11 -B -m unittest tests/cases/test_windows.py` -> `ModuleNotFoundError: No module named 'sistema_luces.cases.windows'`.
- **GREEN:** Implementación de `obtener_limites_ventana`, `es_cierre_de_ventana`, `siguiente_cierre_de_ventana` y `alinear_ventana` en `src/sistema_luces/cases/windows.py`.
- **Resultado GREEN:** `Ran 5 tests`, `OK`.

### Ciclo 2 · Extracción de features y hashing de snapshots
- **RED:** `python3.11 -B -m unittest tests/cases/test_features.py` -> `ModuleNotFoundError: No module named 'sistema_luces.cases.features'`.
- **GREEN:** Implementación de `calcular_snapshot_features` y `calcular_snapshot_hash` en `src/sistema_luces/cases/features.py` con preservación de `None`.
- **Resultado GREEN:** `Ran 3 tests`, `OK`.

### Ciclo 3 · Constructor de Caso V1, causalidad temporal y elegibilidad
- **RED:** `python3.11 -B -m unittest tests/cases/test_builder.py` -> `ModuleNotFoundError: No module named 'sistema_luces.cases.builder'`.
- **GREEN:** Implementación de `SolicitudCaso`, `validar_solicitud_caso`, `CasoV1`, `validar_caso`, y `ConstructorCaso` en `src/sistema_luces/cases/builder.py`.
- **Resultado GREEN:** `Ran 5 tests`, `OK`.

## Gate WP-05
- Comando: `python3.11 -B -m unittest discover -s tests/cases -v`
- Pruebas pasando: 13 / 13 (100%).
- Causalidad temporal (OPT-7), reproducibilidad de hash (CA-9) y elegibilidad ante feed degradado verificadas.
