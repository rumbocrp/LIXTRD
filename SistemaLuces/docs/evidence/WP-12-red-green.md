# WP-12 · Evidencia RED→GREEN (Métricas en 8 Planos y Proyecciones Reconstruibles)

> **HISTÓRICO:** baseline del primer intento; no acredita una Puerta R0–R7.

## Costuras preacordadas antes de escribir pruebas

La SPEC-001 (§6.7, §9.1, §12.5) y ADR-001 fijan estas costuras públicas para WP-12:

1. **Catálogo de Métricas en 8 Planos (`metrics.py`, SPEC-001 §6.7, CA-22):**
   - Planos obligatorios: `FEED`, `SIGNALS`, `PREDICTIVE`, `ROBUSTNESS`, `DEMO`, `EXECUTION`, `SECURITY`, `TRACEABILITY`.
   - **Invariante CA-22:** Métricas no computables devuelven valores `null` (`value_int=None, value_ratio_scaled=None`) con `reason_code="INSUFFICIENT_OR_UNKNOWN_DATA"` y preservan los conteos de muestra efectivos; no se publican erróneamente como cero.
   - Cumplimiento estricto del esquema `sistema-luces/metric-snapshot-v1`.

2. **Proyecciones Reconstruibles (`projections.py`, SPEC-001 §9.1, CA-21):**
   - Mantiene proyecciones de lectura `FEED`, `LIGHTS`, `SIGNALS`, `SIMULATIONS`, `METRICS`, `SECURITY`, `TRACE`, `IMPORTS`.
   - **Invariante CA-21:** La reconstrucción completa desde la secuencia de eventos persistidos produce un estado byte-a-byte idéntico y determinista.
   - Generación de `DocumentoVistaV1` y `VistaLectura` con bytes canónicos y SHA-256 verificado.

3. **Árbol Causal y Trazabilidad (`trace.py`, SPEC-001 §6.2, CA-23):**
   - Registro de nodos de traza y recorrido ascendente por `causation_id` hasta el evento raíz.

---

## Ciclos verticales

### Ciclo 1 · Catálogo de 8 planos y regla de nulls
- **RED:** `PYTHONPATH=src python3.11 -B -m unittest tests/observability/test_metrics_8_planes.py` -> `ModuleNotFoundError: No module named 'sistema_luces.observability'`.
- **GREEN:** Implementación de `CalculadorMetricas8Planos` en `src/sistema_luces/observability/metrics.py`.
- **Resultado GREEN:** `Ran 2 tests`, `OK`.

### Ciclo 2 · Proyecciones reconstruibles e integridad de vistas
- **RED:** `PYTHONPATH=src python3.11 -B -m unittest tests/observability/test_projections.py` -> `ModuleNotFoundError: No module named 'sistema_luces.observability.projections'`.
- **GREEN:** Implementación de `ProyectorVistas` en `src/sistema_luces/observability/projections.py`.
- **Resultado GREEN:** `Ran 2 tests`, `OK`.

### Ciclo 3 · Árbol de trazabilidad causal
- **RED:** `PYTHONPATH=src python3.11 -B -m unittest tests/observability/test_trace.py` -> `ModuleNotFoundError: No module named 'sistema_luces.observability.trace'`.
- **GREEN:** Implementación de `ArbolTrazabilidad` en `src/sistema_luces/observability/trace.py`.
- **Resultado GREEN:** `Ran 1 test`, `OK`.

---

## Gate WP-12
- Comando: `PYTHONPATH=src python3.11 -B -m unittest discover -s tests/observability -v`
- Pruebas pasando: 5 / 5 (100%).
- Verificación de repositorio (`make verify`): 299 / 299 pruebas pasando, `uv lock --check`, `compileall` y `tabnanny` limpios.
