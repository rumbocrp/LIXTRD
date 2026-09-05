# WP-07 · Evidencia RED→GREEN (Registro de Modelos, Calibración OOF y Compuerta de Evaluación)

> **HISTÓRICO:** baseline del primer intento; no acredita una Puerta R0–R7.

## Costuras preacordadas antes de escribir pruebas

La SPEC-001 (§6.8, §12.7) y ADR-001 fijan estas costuras públicas para WP-07:

1. **Registro Inmutable de Modelos (`registry.py`, SPEC-001 §6.8, PROJECT.md § Interface Contracts):**
   - Almacenamiento inmutable de artefactos de modelo indexados por `model_id` y su hash SHA-256 canónico `model_hash`.
   - Idempotencia exacta al re-registrar un modelo idéntico; rechazo con `INTEGRITY_ERROR` si se intenta mutar un ID con distinto hash.
   - Consulta y obtención de modelos por ID o por hash; falla con `MODEL_UNAVAILABLE` si el modelo no existe.
   - Asociación de calibrador OOF y cálculo de predicciones calibradas enteras `0..1_000_000` (`predecir_calibrado`).

2. **Modelos Predictivos Base y Regresión Logística (`baseline.py`, SPEC-001 §6.8):**
   - **`ModeloBaseV1`:** Modelo de referencia con probabilidades a priori empíricas y ajuste opcional por desbalance de órdenes / momentum.
   - **`ModeloRegresionLogisticaV1`:** Regresión logística multivariada con soporte direccional LONG y SHORT, estandarización de features, pesos y sesgo entrenados deterministamente con regularización L2.
   - **Cálculo de hash determinista (`calcular_hash_modelo`):** SHA-256 sobre la representación JSON canónica de parámetros, pesos y nombres de variables.

3. **Calibración Out-of-Fold y Platt Scaling (`calibration.py`, CA-26):**
   - **Platt Scaling:** Ajuste de parámetros logísticos sobre predicciones Out-of-Fold para transformar scores brutos en probabilidades bien calibradas `0..1_000_000`.
   - **Invariante CA-26:** Calibración in-fold estrictamente prohibida (`is_out_of_fold == True`); el intento de calibrar in-fold es rechazado con `VALIDATION_ERROR`.

4. **Métricas de Evaluación Predictiva y Económica (`metrics.py`, DM-5, CA-26):**
   - **Brier Score:** `(1/N) * sum((p_i - y_i)^2)` escalado como entero `0..1_000_000`.
   - **Expected Calibration Error (ECE):** Error de calibración en bins uniformes escalado `0..1_000_000` (umbral policy $\le 100\_000$, i.e. $\le 0.10$).
   - **Log Loss:** Pérdida logarítmica / cross-entropy acotada por epsilon.
   - **Intervalo de Wilson 95%:** Intervalo analítico exacto para proporciones binomiales ($z = 1.959964$).
   - **Utilidad Neta:** Evaluación de puntos y P&L neto descontando spread, slippage y comisiones en escenarios Base, Adverso y Estrés.

5. **Evaluador de Compuerta de Modelos (`gate.py`, CA-26, SPEC-001 §12.7):**
   - Evaluación contra `model-gate-policy-v1` (`ModelGatePolicyV1`):
     - Tamaño de muestra efectivo $\ge 500$ (`effective_sample_size_min`).
     - Mejora de Brier score $\ge 0$ contra referencia baseline (`brier_improvement_min_scaled`).
     - ECE $\le 100\_000$ (`ece_max_scaled`).
     - Utilidad neta base CI inferior estrictamente $> 0$ (`net_utility_base_ci_lower_exclusive`).
     - Utilidad neta adversa $\ge 0$ (`net_utility_adverse_min`).
     - Ratio de folds positivos en walk-forward $\ge 600\_000$ (60%).
     - Cero tolerancia a fuga de datos (`leakage_violations_max = 0`).
     - Calibración out-of-fold obligatoria y splits con purga/embargo obligatorios.
     - Detección de drift severo bloquea promoción.
     - Hashes de cohortes y costos alineados con la política.
   - Salida: `DecisionCompuertaModelo` (`PROMOTION` / `REJECTED`).

6. **Detector de Drift de Distribución (`drift.py`, SPEC-001 §6.8):**
   - Monitoreo de features mediante Population Stability Index (PSI).
   - Clasificación: `HEALTHY` ($\text{PSI} < 0.10$), `WARNING` ($0.10 \le \text{PSI} < 0.25$), `SEVERE_DRIFT` ($\text{PSI} \ge 0.25$).

---

## Ciclos verticales

### Ciclo 1 · Registro inmutable de modelos y recuperación por hash
- **RED:** `python3.11 -B -m unittest tests/models/test_registry.py` -> `ModuleNotFoundError: No module named 'sistema_luces.models'`.
- **GREEN:** Implementación de `RegistroModelos` en `src/sistema_luces/models/registry.py` con almacenamiento inmutable por ID y SHA-256.
- **Resultado GREEN:** `Ran 6 tests`, `OK`.

### Ciclo 2 · Modelos predictivos base y regresión logística
- **RED:** `python3.11 -B -m unittest tests/models/test_baseline_and_logreg.py` -> `ModuleNotFoundError: No module named 'sistema_luces.models.baseline'`.
- **GREEN:** Implementación de `ModeloPredictivoV1`, `ModeloBaseV1` y `ModeloRegresionLogisticaV1` en `src/sistema_luces/models/baseline.py`.
- **Resultado GREEN:** `Ran 4 tests`, `OK`.

### Ciclo 3 · Calibración Out-of-Fold y Platt scaling
- **RED:** `python3.11 -B -m unittest tests/models/test_calibration.py` -> `ModuleNotFoundError: No module named 'sistema_luces.models.calibration'`.
- **GREEN:** Implementación de `CalibradorLogistico` en `src/sistema_luces/models/calibration.py` con optimización por descenso de gradiente de Platt scaling ($p = \sigma(-(Az+B))$, $A \leftarrow A + \text{lr}\cdot\frac{1}{n}\sum(p_i-t_i)z_i$, $B \leftarrow B + \text{lr}\cdot\frac{1}{n}\sum(p_i-t_i)$), manejo de límites $0 \le \text{raw\_score} \le 1\_000\_000$ en escala entera y prohibición estricta de calibración in-fold (CA-26).
- **Resultado GREEN:** `Ran 5 tests`, `OK`.

### Ciclo 4 · Métricas predictivas y calibración (Brier, ECE, Log Loss, Wilson 95% CI)
- **RED:** `python3.11 -B -m unittest tests/models/test_metrics.py` -> `ModuleNotFoundError: No module named 'sistema_luces.models.metrics'`.
- **GREEN:** Implementación de `calcular_brier_score`, `calcular_ece`, `calcular_log_loss`, `calcular_intervalo_wilson_95` y `calcular_utilidad_neta_con_ci` en `src/sistema_luces/models/metrics.py`.
- **Resultado GREEN:** `Ran 5 tests`, `OK`.

### Ciclo 5 · Matriz exhaustiva de compuerta CA-26 y promoción
- **RED:** `python3.11 -B -m unittest tests/models/test_gate.py` -> `ModuleNotFoundError: No module named 'sistema_luces.models.gate'`.
- **GREEN:** Implementación de `EvaluadorCompuertaModelo`, `EvaluacionModeloV1` y `DecisionCompuertaModelo` en `src/sistema_luces/models/gate.py`.
- **Resultado GREEN:** `Ran 12 tests`, `OK`.

### Ciclo 6 · Detector de drift de distribución (PSI) y alertas
- **RED:** `python3.11 -B -m unittest tests/models/test_drift.py` -> `ModuleNotFoundError: No module named 'sistema_luces.models.drift'`.
- **GREEN:** Implementación de `DetectorDrift` e `InformeDriftV1` en `src/sistema_luces/models/drift.py`.
- **Resultado GREEN:** `Ran 3 tests`, `OK`.

---

## Gate WP-07
- Comando: `PYTHONPATH=src python3.11 -B -m unittest discover -s tests/models -v`
- Pruebas pasando: 35 / 35 (100%).
- Cumplimiento de matriz CA-26 (§12.7), invariante de calibración out-of-fold obligatoria, ECE $\le 0.10$, Brier improvement $\ge 0$, net utility CI lower $> 0$, y detección de drift verificado al 100%.
- Gate de repositorio (`make verify`): 252 / 252 pruebas pasando, `uv lock --check`, `compileall` y `tabnanny` limpios.
