# WP-02 · Evidencia RED→GREEN (Storage SQLite e Integridad)

> **HISTÓRICO:** baseline del primer intento; no acredita una Puerta R0–R7.

## Costuras preacordadas antes de escribir pruebas

La SPEC-001 aprobada fija estas costuras públicas para WP-02:

1. **Almacén inmutable y append-only:** Base de datos SQLite `luces.db` con WAL mode, Foreign Keys activas (`PRAGMA foreign_keys = ON`), `busy_timeout = 5000ms`, y triggers inmutables que prohíben estrictamente operaciones `UPDATE` o `DELETE` sobre hechos en `event_log` y `audit_log`.
2. **Encadenamiento criptográfico de hashes (CA-4, CA-21):** Cada sobre de evento almacena su `payload_hash` (SHA-256 sobre JSON canónico ordenado UTF-8) y el `previous_hash` del evento precedente en el log.
3. **Idempotencia y rechazo de conflicto (OPT-6, CA-5):**
   - El primer evento aceptado para una clave/ID gana irrevocablemente.
   - Un duplicado idéntico devuelve el `ReciboEvento` original con `idempotent=True` sin reinserción.
   - Un evento con el mismo `event_id` pero contenido o hash diferente devuelve `INTEGRITY_ERROR` sin mutar el almacén.
4. **Append atómico por lotes (`LoteEventosV1`):** Inserción transaccional de lotes; si cualquier evento falla, toda la transacción revierte limpiamente.
5. **Consulta y paginación determinista (`ConsultaEventos`):** Paginación por cursor numérico (`row_id`), filtrado por rango temporal UTC (`range_start_utc`, `range_end_utc`) y tipos de evento (`event_types`), con límite 1..1000.
6. **Verificación de integridad e informe (`InformeIntegridad`):** Recorrido y comprobación de hashes de payload y continuidad de la cadena, generando un `root_hash` acumulativo SHA-256.
7. **Backup, verificación y restore en caliente (CA-21):** Uso de la API `sqlite3.Connection.backup()`, comprobación con `PRAGMA integrity_check` y verificación de conteos e integridad antes y después del restore.

## Ciclos verticales

### Ciclo 1 · Configuración SQLite, WAL y triggers inmutables

- **RED:** `python3.11 -B -m unittest tests.storage.test_sqlite_connection -v` -> `ModuleNotFoundError: No module named 'sistema_luces.storage.sqlite'`.
- **GREEN:** Se implementó `src/sistema_luces/storage/sqlite.py` con `inicializar_db`, `conectar_db`, esquema DDL completo y triggers `trg_prevent_update_event_log`, `trg_prevent_delete_event_log`, `trg_prevent_update_audit_log`, `trg_prevent_delete_audit_log`.
- **Resultado GREEN:** `Ran 2 tests`, `OK`.

### Ciclo 2 · Append atómico y validación de sobre (CA-4, CA-1)

- **RED:** `python3.11 -B -m unittest tests.storage.test_event_store_append -v` -> `ModuleNotFoundError: No module named 'sistema_luces.storage.event_store'`.
- **GREEN:** Se implementó `ArchivoEventos.anexar()` en `src/sistema_luces/storage/event_store.py` con validación de sobre, rechazo de `LIVE` con `ENVIRONMENT_NOT_ALLOWED`, asignación de tres relojes UTC y retorno de `ReciboEvento`.
- **Resultado GREEN:** `Ran 2 tests`, `OK`.

### Ciclo 3 · Idempotencia exacta y detección de conflictos (OPT-6, CA-5)

- **RED:** `python3.11 -B -m unittest tests.storage.test_idempotency_and_conflict -v` -> Falla por ausencia de lógica de consulta previa.
- **GREEN:** Se implementó la verificación de duplicados idénticos (`idempotent=True`) y detección de colisiones de ID con payload divergente (`INTEGRITY_ERROR`).
- **Resultado GREEN:** `Ran 2 tests`, `OK`.

### Ciclo 4 · Encadenamiento de hashes, lote atómico e informe de integridad (CA-4, CA-21)

- **RED:** `python3.11 -B -m unittest tests.storage.test_hash_chain_and_integrity -v` -> Falla por ausencia de `anexar_lote` y `verificar_integridad`.
- **GREEN:** Se implementó encadenamiento secuencial en `_anexar_en_transaccion`, `anexar_lote` con control de rollback atómico y `verificar_integridad` con cálculo de `root_hash`.
- **Resultado GREEN:** `Ran 2 tests`, `OK`.

### Ciclo 5 · Consulta paginada y filtrado temporal

- **RED:** `python3.11 -B -m unittest tests.storage.test_event_query_and_pagination -v` -> Falla por ausencia de `leer()`.
- **GREEN:** Se implementó `ArchivoEventos.leer()` con filtros dinámicos, cursor sobre `row_id` y empaquetado en `PaginaEventos`.
- **Resultado GREEN:** `Ran 2 tests`, `OK`.

### Ciclo 6 · Backup, verificación y restauración (CA-21)

- **RED:** `python3.11 -B -m unittest tests.storage.test_backup_restore -v` -> `ModuleNotFoundError: No module named 'sistema_luces.storage.backup'`.
- **GREEN:** Se implementó `src/sistema_luces/storage/backup.py` con `copiar_base_segura`, `verificar_backup_integro` y `restaurar_backup`.
- **Resultado GREEN:** `Ran 1 test`, `OK`.

### Ciclo 7 · Registro de auditoría y rollback ante conflicto en lote

- **RED:** `python3.11 -B -m unittest tests.storage.test_audit_and_edge_cases -v` -> Falla por ausencia de `RegistroAuditoria`.
- **GREEN:** Se implementó `RegistroAuditoria` y se perfeccionó el aislamiento transaccional con flag `auto_commit`.
- **Resultado GREEN:** `Ran 2 tests`, `OK`.

## Gate WP-02

- Comando: `make verify`
- Exit code: `0`
- Pruebas totales pasando: 102 (incluye arquitectura, dominio, acceptance tier 1 y storage).
- Cero violaciones de seguridad y cero capacidades de orden.
