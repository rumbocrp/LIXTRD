# WP-03 · Evidencia RED→GREEN (Replay y Reloj de Dominio)

> **HISTÓRICO:** baseline del primer intento; no acredita una Puerta R0–R7.

## Costuras preacordadas antes de escribir pruebas

La SPEC-001 aprobada fija estas costuras públicas para WP-03:

1. **Reloj de Dominio Determinista (`RelojDominio`):** Control de tiempo inyectable y reproducible mediante semilla (`clock_seed=20260829`), avance estrictamente monótono (`avanzar_hasta`) y detección fail-closed de retroceso (`ValueError` ante rollback).
2. **Control de Sesión NY con Horario de Verano/Invierno (DST):** Conversión automática a zona `America/New_York` con `zoneinfo`, identificación de apertura (09:30), cierre (16:00), horario regular y discriminación de fines de semana.
3. **Fuente y Sesión de Replay (`FuenteReplay`, `SesionReplay`):** Implementación de los puertos de §5.3 (`SesionFuente`), entrega progresiva de eventos paso a paso (`paso()`), y generadores síncronos/asíncronos (`eventos_sync`, `eventos`).
4. **Ausencia de Sesgo de Anticipación (OPT-7, CA-9):** Filtrado exacto de eventos según `range_start_utc`, `range_end_utc` y `event_cutoff_utc`. Eventos posteriores al corte son estrictamente invisibles para el engine.
5. **Pausa y Reanudación:** Capacidad de congelar y reanudar la emisión sin perder posición temporal ni causalidad.
6. **Determinismo Byte-a-Byte (CA-23):** Dos ejecuciones sobre el mismo dataset y semilla producen exactamente el mismo flujo ordenado de eventos y mismo hash acumulativo SHA-256.

## Ciclos verticales

### Ciclo 1 · Reloj de dominio, avance monótono y control de rollback

- **RED:** `python3.11 -B -m unittest tests.sources.test_clock -v` -> `ModuleNotFoundError: No module named 'sistema_luces.sources.clock'`.
- **GREEN:** Se implementó `RelojDominio` en `src/sistema_luces/sources/clock.py` con `ahora_utc()`, `avanzar_hasta()` y validación contra reloj regresivo.
- **Resultado GREEN:** `Ran 2 tests`, `OK`.

### Ciclo 2 · Zona horaria America/New_York y horario de sesión con DST

- **RED:** `python3.11 -B -m unittest tests.sources.test_clock.DomainClockTests.test_hora_ny_aplica_zona_horaria_con_dst -v` -> Falla por ausencia de métodos de sesión NY.
- **GREEN:** Se implementaron `hora_ny()`, `fecha_sesion_ny()`, `en_sesion_ny()`, `es_fin_de_semana_ny()` soportando transiciones EDT (UTC-4) y EST (UTC-5).
- **Resultado GREEN:** `Ran 4 tests`, `OK`.

### Ciclo 3 · Apertura de fuente de replay y entrega ordenada de eventos

- **RED:** `python3.11 -B -m unittest tests.sources.test_replay -v` -> `ModuleNotFoundError: No module named 'sistema_luces.sources.replay'`.
- **GREEN:** Se implementó `FuenteReplay` y `SesionReplay` en `src/sistema_luces/sources/replay.py` con ordenamiento por `(occurred_at_utc, source_sequence)` y emisión progresiva.
- **Resultado GREEN:** `Ran 1 test`, `OK`.

### Ciclo 4 · Corte temporal estricto (Zero Look-Ahead Bias)

- **RED:** `python3.11 -B -m unittest tests.sources.test_replay.ReplayEngineTests.test_cutoff_temporal_evita_look_ahead_bias -v` -> Falla por falta de filtrado estricto por `event_cutoff_utc`.
- **GREEN:** Se integró el filtro de corte `occurred_at_utc <= event_cutoff_utc` en el constructor de `SesionReplay`.
- **Resultado GREEN:** `Ran 2 tests`, `OK`.

### Ciclo 5 · Pausa y reanudación interactiva

- **RED:** `python3.11 -B -m unittest tests.sources.test_replay.ReplayEngineTests.test_pausa_y_reanudacion_de_sesion -v` -> Falla por ausencia de `pausar()` / `reanudar()`.
- **GREEN:** Se añadieron las primitivas de control de flujo en `SesionReplay`.
- **Resultado GREEN:** `Ran 3 tests`, `OK`.

### Ciclo 6 · Determinismo estricto e igualdad hash byte-a-byte (CA-23)

- **RED:** `python3.11 -B -m unittest tests.sources.test_replay_determinism -v` -> Falla por discrepancia en orden o serialización.
- **GREEN:** Se verificó que dos corridas idénticas sobre 20 eventos producen hashes SHA-256 canónicos exactamente iguales.
- **Resultado GREEN:** `Ran 1 test`, `OK`.

## Gate WP-03

- Comando: `python3.11 -B -m unittest discover -s tests -t . -v`
- Exit code: `0`
- Pruebas totales pasando: 110.
- Replay determinista verificado y sincronización con el reloj de dominio garantizada.
