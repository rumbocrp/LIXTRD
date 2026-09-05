# WP-11 · Evidencia RED→GREEN (Importación Staged Demo y Reconciliación)

> **HISTÓRICO:** baseline del primer intento; no acredita una Puerta R0–R7.

## Costuras preacordadas antes de escribir pruebas

La SPEC-001 (§5.2.1, §6.6, §12.4) y ADR-001 fijan estas costuras públicas para WP-11:

1. **Validador de Copia Staged (`staging.py`, SPEC-001 §5.2.1, CA-19):**
   - Rutas relativas seguras contra path traversal (rechazo de `..`, rutas absolutas y separadores inválidos).
   - Límite estricto de tamaño $\le 50\text{ MiB}$ (52,428,800 bytes).
   - Verificación de integridad por SHA-256 (`expected_sha256 == computed_sha256`).

2. **Importador de Operaciones Demo (`demo.py`, SPEC-001 §5.2.1, CA-3, CA-19):**
   - Parsing de registros de trading demo observados (`EjecucionDemoObservada`).
   - Verificación de cuenta demo `expected_demo_account_hash` (CA-3).
   - Emisión de `ResumenImportacion` conforme a DTOs de dominio.

3. **Motor de Reconciliación (`reconciliation.py`, SPEC-001 §6.6, CA-19):**
   - Cruce temporal y direccional entre simulaciones paper (`SimulacionV1`) y ejecuciones broker importadas.
   - Simulaciones coincidentes pasan a `reconciliation_status="MATCHED"` con registro de `source_execution_ids` y cálculo de slippage.
   - **Invariante CA-19:** Operaciones huérfanas o no coincidentes se marcan explícitamente como `reconciliation_status="UNMATCHED"` con `reason_code="NO_DEMO_MATCH_FOUND"`.

---

## Ciclos verticales

### Ciclo 1 · Validador de copias staged y verificación SHA-256
- **RED:** `PYTHONPATH=src python3.11 -B -m unittest tests/imports/test_demo_import.py` -> `ModuleNotFoundError: No module named 'sistema_luces.imports'`.
- **GREEN:** Implementación de `ValidadorStaging` en `src/sistema_luces/imports/staging.py` con comprobación de límites, prevención de traversal y SHA-256.
- **Resultado GREEN:** `Ran 3 tests`, `OK`.

### Ciclo 2 · Reconciliación de ejecuciones y marcado UNMATCHED
- **RED:** `PYTHONPATH=src python3.11 -B -m unittest tests/imports/test_reconciliation.py` -> `ModuleNotFoundError: No module named 'sistema_luces.imports.demo'`.
- **GREEN:** Implementación de `ReconciliadorDemo` e `InformeReconciliacion` en `src/sistema_luces/imports/reconciliation.py` y `demo.py`.
- **Resultado GREEN:** `Ran 2 tests`, `OK`.

---

## Gate WP-11
- Comando: `PYTHONPATH=src python3.11 -B -m unittest tests.imports.test_demo_import tests.imports.test_reconciliation -v`
- Pruebas pasando: 5 / 5 (100%).
- Verificación de repositorio (`make verify`): 299 / 299 pruebas pasando, `uv lock --check`, `compileall` y `tabnanny` limpios.
