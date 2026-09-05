# WP-13 · Evidencia RED→GREEN (Adaptador Aislado Journal V1)

> **HISTÓRICO:** baseline del primer intento; no acredita una Puerta R0–R7.

## Costuras preacordadas antes de escribir pruebas

La SPEC-001 (§9.4, §12.8) y ADR-001 fijan estas costuras públicas para WP-13:

1. **Aislamiento Arquitectural (`journal_v1.py`, SPEC-001 §9.4, CA-20, CA-28):**
   - El adaptador opera únicamente sobre copias de exportación estáticas (`trading-journal/exportacion-completa-v1`).
   - **Invariante CA-20:** El núcleo del sistema reporta `CA-20=NOT_INCLUDED` en ausencia de la extensión sin bloquear ni degradar replay, shadow, señal o simulación.
   - **Invariante CA-28:** Cero importaciones o referencias en tiempo de ejecución a bases de datos externas (`tj.db`), paquetes del bot o del Journal.

---

## Ciclos verticales

### Ciclo 1 · Estado de aislamiento y lectura de exportación estructurada
- **RED:** `PYTHONPATH=src python3.11 -B -m unittest tests/imports/test_journal_v1.py` -> `ModuleNotFoundError: No module named 'sistema_luces.imports.journal_v1'`.
- **GREEN:** Implementación de `AdaptadorExportacionJournalV1` en `src/sistema_luces/imports/journal_v1.py`.
- **Resultado GREEN:** `Ran 2 tests`, `OK`.

---

## Gate WP-13 & Milestone M5
- Comando: `PYTHONPATH=src python3.11 -B -m unittest tests/imports/test_journal_v1.py -v`
- Pruebas pasando: 2 / 2 (100%).
- Verificación de repositorio (`make verify`): 299 / 299 pruebas pasando, `uv lock --check`, `compileall` y `tabnanny` limpios.
