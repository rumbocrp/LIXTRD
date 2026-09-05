# WP-15 · Evidencia RED→GREEN (Cierre E2E, Endurecimiento Tier 5 y Gate V1)

> **HISTÓRICO:** baseline del primer intento; no acredita una Puerta R0–R7.

## Costuras preacordadas antes de escribir pruebas

La SPEC-001 (§12.7) y ADR-001 fijan estas costuras públicas para WP-15:

1. **Matriz Completa de Criterios de Aceptación (CA-1 a CA-28):**
   - 100% de criterios de aceptación verificados mediante pruebas unitarias, de integración, de límites (Tier 2), de interacción (Tier 3), de escenarios reales (Tier 4) y adversariales (Tier 5).
   - Invariantes de seguridad: cero capacidad de órdenes, bloqueo estricto de LIVE (`ENVIRONMENT_NOT_ALLOWED`), scopes de lectura únicamente (`market_data.read`, `historical_executions.read`, `account_metadata.read`), hash de cuenta demo obligatorio (CA-3).
   - Invariantes matemáticas: Platt scaling con gradiente descendente monótono, Brier score, Wilson 95% CI, triple barrera atómica `STOP_FIRST`.
   - Invariantes de observabilidad: 8 planos métricos, `null` con reason code en muestras insuficientes, proyecciones reconstruibles desde el event log.
   - Invariantes de aislamiento: `CA-20=NOT_INCLUDED` sin dependencias externas a `trading_bot` o `trading_journal`.

2. **Endurecimiento Adversarial Tier 5 (`tests/acceptance/test_tier5_adversarial.py`):**
   - Intentos de evasión LIVE mediante caracteres Unicode, saltos nulos y padding.
   - Ataques de manipulación de payloads con hashes adulterados.
   - Ataques de oscilación rápida de sesgo (Green -> Red -> Green) neutralizados por histeresis intermedia obligatoria.
   - Intentos de bypass del Kill Switch sin actor o resolución.
   - Gaps extremos de mercado y saltos de volatilidad resueltos deterministamente.

---

## Ciclos verticales

### Ciclo 1 · Pruebas adversariales Tier 5
- **RED:** Definición de escenarios de ataque en `tests/acceptance/test_tier5_adversarial.py`.
- **GREEN:** Verificación de guardias activas en `parse_environment`, `validar_sobre_evento`, `PoliticaLuces`, `InterruptorEmergencia` y `EvaluadorTripleBarrera`.
- **Resultado GREEN:** `Ran 5 tests`, `OK`.

### Ciclo 2 · Verificación integral y escaneo de políticas
- **Comando:** `make verify` (incluye `uv lock --check`, `unittest discover -s tests`, `compileall` y `tabnanny`).
- **Resultado:** 313 / 313 pruebas pasando al 100%, 0 violaciones de arquitectura o seguridad.

---

## Gate WP-15 & Cierre V1
- Total de pruebas en suite: 313 pruebas automáticas.
- Resultado: **PASS** (100% verde, cero advertencias, cero hardcodings, cero violaciones de política de seguridad).
