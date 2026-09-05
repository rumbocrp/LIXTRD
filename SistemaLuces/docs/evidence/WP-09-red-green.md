# WP-09 · Evidencia RED→GREEN (Motor de Riesgo, Kill Switch y Simulador Paper)

> **HISTÓRICO:** baseline del primer intento; no acredita una Puerta R0–R7.

## Costuras preacordadas antes de escribir pruebas

La SPEC-001 (§5.3, §6.6, §7.1, §8, §12.3) y ADR-001 fijan estas costuras públicas para WP-09:

1. **Calendario de Noticias y Ventanas de Blackout (`blackout.py`, SPEC-001 §8, CA-17):**
   - Eventos económicos con impacto `HIGH` y moneda `USD` o `ALL`.
   - Ventana de bloqueo estricta `[evento_utc - 15 min, evento_utc + 15 min]` inclusive.

2. **Interruptor de Emergencia / Kill Switch (`kill_switch.py`, SPEC-001 §8, CA-18):**
   - Comportamiento fail-closed ante fallas técnicas, pérdida máxima o brecha de riesgo.
   - Procedimiento de recuperación auditado que exige `actor` identificado y `resolucion` fundamentada.

3. **Motor de Riesgo y Guardias Tripwire (`engine.py`, SPEC-001 §8, CA-15, CA-16, CA-17, DM-12):**
   - **Invariante CA-16 (Posición Única):** Máximo 1 posición abierta en US500. Propuestas concurrentes son rechazadas con `RISK_LIMIT_HIT` (`OVERLAPPING_POSITION`).
   - **Invariante CA-17 (Matriz de Riesgo):**
     - Riesgo máximo por operación $\le \$50.00$ (5000 cents).
     - Pérdida diaria máxima acumulada $\le \$250.00$ (25000 cents); al alcanzarse activa el Kill Switch.
     - Pausa operativa tras 3 pérdidas consecutivas netas.
     - Límite de 10 aperturas por día de sesión NY.
   - **Invariante DM-12:** Reseteo de contadores a la medianoche de `America/New_York` usando `zoneinfo`.
   - **Invariante CA-15:** Contrato económico incompleto (falta stop, target o cantidad) es rechazado con `ECONOMIC_CONTRACT_INCOMPLETE`.

4. **Evaluador de Triple Barrera y Ciclo Paper (`lifecycle.py`, `paper.py`, SPEC-001 §5.3, §6.6, §7.1, CA-11, CA-12, CA-13, CA-14):**
   - **Precios ejecutables:** LONG entra al Ask y valida Stop/Target al Bid; SHORT entra al Bid y valida Stop/Target al Ask.
   - **Invariante CA-14:** Ambigüedad en tick atómico resuelve `STOP_FIRST` con etiqueta `AMBIGUOUS_STOP_FIRST`.
   - **Invariante CA-11:** Señal con antigüedad $> 30\text{ s}$ es rechazada con `SIGNAL_EXPIRED`.
   - **Invariante CA-12:** Señal en `YELLOW` o `MONITOR` rechaza simulación y nunca emite `SIM_OPENED`.
   - **Cálculo de P&L:** P&L bruto, P&L neto descontando spread/comisiones/slippage, R realizada, MFE y MAE.

---

## Ciclos verticales

### Ciclo 1 · Ventana de blackout de noticias y eventos macro
- **RED:** `PYTHONPATH=src python3.11 -B -m unittest tests/risk/test_blackout.py` -> `ModuleNotFoundError: No module named 'sistema_luces.risk'`.
- **GREEN:** Implementación de `CalendarioNoticias` y `EventoNoticia` en `src/sistema_luces/risk/blackout.py`.
- **Resultado GREEN:** `Ran 2 tests`, `OK`.

### Ciclo 2 · Kill switch fail-closed y procedimiento de recuperación verificado
- **RED:** `PYTHONPATH=src python3.11 -B -m unittest tests/risk/test_kill_switch.py` -> `ModuleNotFoundError: No module named 'sistema_luces.risk.kill_switch'`.
- **GREEN:** Implementación de `InterruptorEmergencia` en `src/sistema_luces/risk/kill_switch.py`.
- **Resultado GREEN:** `Ran 4 tests`, `OK`.

### Ciclo 3 · Motor de riesgo, tripwires, posición única y reseteo NY
- **RED:** `PYTHONPATH=src python3.11 -B -m unittest tests/risk/test_risk_engine.py` -> `ModuleNotFoundError: No module named 'sistema_luces.risk.engine'`.
- **GREEN:** Implementación de `MotorRiesgo` en `src/sistema_luces/risk/engine.py` con matriz completa de tripwires, reseteo a medianoche NY y activación de kill switch.
- **Resultado GREEN:** `Ran 6 tests`, `OK`.

### Ciclo 4 · Evaluador de triple barrera y resolución STOP_FIRST
- **RED:** `PYTHONPATH=src python3.11 -B -m unittest tests/simulation/test_lifecycle.py` -> `ModuleNotFoundError: No module named 'sistema_luces.simulation'`.
- **GREEN:** Implementación de `EvaluadorTripleBarrera` en `src/sistema_luces/simulation/lifecycle.py`.
- **Resultado GREEN:** `Ran 6 tests`, `OK`.

### Ciclo 5 · Simulador paper, expiración de señal y liquidación de P&L
- **RED:** `PYTHONPATH=src python3.11 -B -m unittest tests/simulation/test_paper_simulator.py` -> `ModuleNotFoundError: No module named 'sistema_luces.simulation.paper'`.
- **GREEN:** Implementación de `SimuladorPapel` en `src/sistema_luces/simulation/paper.py` integrando validación de señales, evaluación de riesgo, tracking de ticks y cierre contable de órdenes paper.
- **Resultado GREEN:** `Ran 4 tests`, `OK`.

---

## Gate WP-09 & Milestone M4
- Comando: `PYTHONPATH=src python3.11 -B -m unittest discover -s tests/risk -v && PYTHONPATH=src python3.11 -B -m unittest discover -s tests/simulation -v`
- Pruebas pasando: 22 / 22 (100%).
- Verificación de repositorio (`make verify`): 287 / 287 pruebas pasando, `uv lock --check`, `compileall` y `tabnanny` limpios.
