# WP-08 · Evidencia RED→GREEN (Política de Luces, Histéresis y Señales)

> **HISTÓRICO:** baseline del primer intento; no acredita una Puerta R0–R7.

## Costuras preacordadas antes de escribir pruebas

La SPEC-001 (§6.4, §6.5, §7.3, §12.2) y ADR-001 fijan estas costuras públicas para WP-08:

1. **Máquina de Estados de Luces e Histéresis (`hysteresis.py`, SPEC-001 §6.4, CA-8):**
   - Estados admisibles: `YELLOW`, `GREEN`, `RED` (con `YELLOW` como estado inicial inmutable).
   - Transiciones permitidas: `YELLOW -> {YELLOW, GREEN, RED}`, `GREEN -> {GREEN, YELLOW}`, `RED -> {RED, YELLOW}`.
   - **Invariante CA-8:** El salto directo `GREEN <-> RED` está estrictamente prohibido y devuelve `VALIDATION_ERROR`. Toda inversión de sesgo debe transitar por un estado intermedio `YELLOW`.
   - Degradación de feed fuerza retorno inmediato a `YELLOW`.

2. **Política de Decisión y Generación de Señales (`lights.py`, SPEC-001 §6.5, CA-10, CA-11, CA-12, CA-27):**
   - **Solicitud de Decisión (`SolicitudLuz`):** Contiene caso maduro, salud del feed, probabilidades calibradas `0..1_000_000`, modelo, versión de features y cortes temporales.
   - **Invariante CA-11 (Vencimiento de Señal):** Toda señal emitida tiene `valid_until_utc = created_at_utc + timedelta(seconds=30)`.
   - **Invariante CA-12 (Abstención Amarilla):** Si la luz es `YELLOW`, la dirección de la señal es obligatoriamente `MONITOR` y `safety_forced` se marca si proviene de degradación de datos.
   - **Invariante CA-27 (No-Cuota Diaria):** El target diario de 5 a 10 señales es estrictamente una métrica observacional; la política nunca fuerza emisiones para cumplir una cuota.
   - **Salida Atómica (`DecisionLuzV1`):** Retorna `SenalV1` y `TransicionEstadoV1` validados contra sus esquemas de dominio.

---

## Ciclos verticales

### Ciclo 1 · Máquina de estados de luces y protección contra saltos directos
- **RED:** `PYTHONPATH=src python3.11 -B -m unittest tests/policy/test_hysteresis.py` -> `ModuleNotFoundError: No module named 'sistema_luces.policy'`.
- **GREEN:** Implementación de `HisteresisLuces` en `src/sistema_luces/policy/hysteresis.py` con validación de grafo de estados de §6.4 y forzado a YELLOW en degradación de feed.
- **Resultado GREEN:** `Ran 7 tests`, `OK`.

### Ciclo 2 · Política de luces, expiración en 30s, abstención amarilla y no-cuota
- **RED:** `PYTHONPATH=src python3.11 -B -m unittest tests/policy/test_lights_policy.py` -> `ModuleNotFoundError: No module named 'sistema_luces.policy.lights'`.
- **GREEN:** Implementación de `PoliticaLuces`, `SolicitudLuz` y `DecisionLuzV1` en `src/sistema_luces/policy/lights.py` asegurando `valid_until_utc = created_at_utc + 30s`, `direction=MONITOR` en `YELLOW`, degradación `FEED_DEGRADED_YELLOW` y emisión determinista sin cuotas.
- **Resultado GREEN:** `Ran 6 tests`, `OK`.

---

## Gate WP-08
- Comando: `PYTHONPATH=src python3.11 -B -m unittest discover -s tests/policy -v`
- Pruebas pasando: 13 / 13 (100%).
- Verificación de repositorio (`make verify`): 265 / 265 pruebas pasando, `uv lock --check`, `compileall` y `tabnanny` limpios.
