# WP-06 · Evidencia RED→GREEN (Etiquetas Triple-Barrier, Dataset y Splits)

> **HISTÓRICO:** baseline del primer intento; no acredita una Puerta R0–R7.

## Costuras preacordadas antes de escribir pruebas

La SPEC-001 y ADR-001 fijan estas costuras públicas para WP-06:

1. **Etiquetado de Triple Barrera con Precios Ejecutables (`labels.py`, §7.1, §7.2, CA-13, CA-14):**
   - **LONG:** Entra al `ask` de referencia. Barrera de stop en `ask - 500` (5 pts), target en `ask + 2000` (20 pts). Salida y evaluación ejecutada contra `bid`.
   - **SHORT:** Entra al `bid` de referencia. Barrera de stop en `bid + 500` (5 pts), target en `bid - 2000` (20 pts). Salida y evaluación ejecutada contra `ask`.
   - **Empate / Ambigüedad en tick atómico (`STOP_FIRST`, CA-14):** Si un tick atómico abarca stop y target sin secuencia interna resoluble, el resultado es `STOP_LOSS` y se anexa la razón `AMBIGUOUS_STOP_FIRST`.
   - **Expiración de horizonte:** A los 5 minutos (300 s), si no se tocó barrera, cierra con `HORIZON_EXPIRATION` al último precio ejecutable observado.
   - **Datos insuficientes:** Si faltan referencias o ticks, status `INVALID` con `INSUFFICIENT_OR_UNKNOWN_DATA`.
2. **Purga y Embargo en Particiones Walk-Forward (`splits.py`, §6.8, CA-26):**
   - **Purga:** Muestras de entrenamiento cuyo horizonte de 5 minutos invade el inicio del conjunto de prueba son eliminadas del fold de entrenamiento.
   - **Embargo:** Bloqueo de muestras tras el conjunto de prueba para evitar autocorrelación serial.
   - **Verificación de Cero Fuga (`verificar_cero_fuga`):** Auditoría formal que garantiza `leakage_violations_max = 0`.
3. **Constructor de Dataset Causal (`dataset.py`, WP-06):**
   - Fusión determinista de `CasoV1` con `EtiquetaV1` (LONG y SHORT).
   - Generación de vectores de features y etiquetas binarias con hash de manifiesto inmutable.

## Ciclos verticales

### Ciclo 1 · Etiquetado de triple barrera y precios ejecutables (Tabla 7.2)
- **RED:** `python3.11 -B -m unittest tests/learning/test_labels.py` -> `ModuleNotFoundError: No module named 'sistema_luces.learning'`.
- **GREEN:** Implementación de `EtiquetaV1`, `SolicitudEtiqueta`, `validar_etiqueta` y `Etiquetador` en `src/sistema_luces/learning/labels.py`.
- **Resultado GREEN:** `Ran 5 tests`, `OK`.

### Ciclo 2 · Purga, embargo y particiones walk-forward
- **RED:** `python3.11 -B -m unittest tests/learning/test_splits.py` -> `ModuleNotFoundError: No module named 'sistema_luces.learning.splits'`.
- **GREEN:** Implementación de `GeneradorParticionesWalkForward`, `ParticionFoldV1`, `SolicitudParticionWalkForward` y `verificar_cero_fuga` en `src/sistema_luces/learning/splits.py`.
- **Resultado GREEN:** `Ran 2 tests`, `OK`.

### Ciclo 3 · Constructor de dataset causal y matrices de aprendizaje
- **RED:** `python3.11 -B -m unittest tests/learning/test_dataset.py` -> `ModuleNotFoundError: No module named 'sistema_luces.learning.dataset'`.
- **GREEN:** Implementación de `ConstructorDatasetCausal`, `DatasetCausalV1` y `MuestraAprendizajeV1` en `src/sistema_luces/learning/dataset.py`.
- **Resultado GREEN:** `Ran 1 test`, `OK`.

## Gate WP-06
- Comando: `python3.11 -B -m unittest discover -s tests/learning -v`
- Pruebas pasando: 8 / 8 (100%).
- Convenciones ejecutables LONG/SHORT (CA-13), empate stop-first (CA-14) y particiones sin fuga con purga/embargo (CA-26) verificadas.
