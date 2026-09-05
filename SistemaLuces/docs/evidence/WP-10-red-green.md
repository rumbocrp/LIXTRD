# WP-10 · Evidencia RED→GREEN (Adaptador cTrader Demo Read-Only)

> **HISTÓRICO:** baseline del primer intento; no acredita una Puerta R0–R7.

## Costuras preacordadas antes de escribir pruebas

La SPEC-001 y ADR-001 fijan estas costuras públicas para WP-10:

1. **Lista Blanca de Capacidades Read-Only (`validar_capacidades_read_only`, §10.2, CA-2):**
   - Permitidas exclusivamente: `market_data.read`, `account_metadata.read`, `historical_executions.read`.
   - Cualquier solicitud con scopes de escritura, ejecución o gestión de órdenes (e.g. `orders.write`, `trade.execute`) es rechazada con `CAPABILITY_DENIED` y bloquea la apertura de conexión.
2. **Validación Estricta de Cuenta Demo (`validar_metadatos_cuenta_demo`, §10.3, CA-3):**
   - Requiere `is_demo = True` explícito y coincidencia del hash seudónimo `account_id_hash`.
   - Ausencia de demo o cuenta no demo devuelve `SOURCE_NOT_DEMO`.
3. **Manejo de Backpressure y Reconexión (`SesionCTraderDemo`, WP-10):**
   - Cola acotada por `max_queue_size` con descarte FIFO de eventos obsoletos ante sobrecarga.
   - Registro y emisión de sobres de evento `RECONNECTED` con actualización de `last_safe_cutoff`.
4. **Mapeo a Sobres de Dominio V1 (`mapear_mensaje_a_sobre`, CA-4):**
   - Conversión normalizada de mensajes crudos a `SobreEventoV1` con `source="ctrader_demo"`, `instrument="US500"` y hash canónico.

## Ciclos verticales

### Ciclo 1 · Lista blanca de capacidades y rechazo de scopes de escritura (CA-2)
- **RED:** `python3.11 -B -m unittest tests/sources/test_ctrader_demo.py` -> `ModuleNotFoundError: No module named 'sistema_luces.sources.ctrader_demo'`.
- **GREEN:** Implementación de `CAPABILITIES_READ_ONLY_PERMITIDAS` y `validar_capacidades_read_only` en `src/sistema_luces/sources/ctrader_demo.py`.
- **Resultado GREEN:** `Ran 1 test`, `OK`.

### Ciclo 2 · Verificación de cuenta demo y rechazo de live (CA-1, CA-3)
- **RED:** Falla por ausencia de `validar_metadatos_cuenta_demo` y chequeo de entorno.
- **GREEN:** Implementación de `MetadatosCuentaCTrader`, `validar_metadatos_cuenta_demo` y validación de `Environment` en `AdaptadorCTraderDemoReadOnly`.
- **Resultado GREEN:** `Ran 3 tests`, `OK`.

### Ciclo 3 · Backpressure, reconexión y mapeo de eventos
- **RED:** Falla por ausencia de `SesionCTraderDemo` y su lógica de cola.
- **GREEN:** Implementación de `SesionCTraderDemo` con gestión de cola acotada, `registrar_reconexion` y `mapear_mensaje_a_sobre`.
- **Resultado GREEN:** `Ran 6 tests`, `OK`.

## Gate WP-10
- Comando: `python3.11 -B -m unittest tests/sources/test_ctrader_demo.py -v`
- Pruebas pasando: 6 / 6 (100%).
- Cero capacidades de escritura (CA-2), validación demo obligatoria (CA-3) y fail-closed LIVE (CA-1) plenamente verificadas.
