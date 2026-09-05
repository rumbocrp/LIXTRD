# WP-01 · Evidencia RED→GREEN

> **HISTÓRICO:** baseline del primer intento; no acredita una Puerta R0–R7.

## Costuras preacordadas antes de escribir pruebas

La SPEC-001 aprobada fija estas costuras públicas para WP-01:

1. **Resultado discriminado y errores:** `Resultado[T] = Exito[T] | Fallo`, portando `ErrorDominio` con exactamente 21 códigos cerrados, mensajes seguros sin secretos y ausencia de excepciones como contrato de dominio.
2. **Vocabulario y canonicalización:** `US500` como único instrumento, `REPLAY|SHADOW|BROKER_DEMO_OBSERVED` como únicos entornos (rechazo explícito de intentos no permitidos devolviendo `ENVIRONMENT_NOT_ALLOWED`), enteros escalados finitos (OPT-2) y rechazo de NaN/Infinity.
3. **DTOs de API pública:** `SolicitudReplay`, `SolicitudShadow`, `SolicitudImportacionDemo`, `SolicitudConsulta`, `ResumenEjecucion`, `ResumenImportacion`, `DocumentoVistaV1` y `VistaLectura` cerrados con validación estricta.
4. **Sobre de eventos y JSON canónico:** `SobreEventoV1` con 3 relojes, `payload_hash` SHA-256 sobre JSON canónico ordenado y determinista (OPT-7), y familias de payloads V1.
5. **Máquina de estados:** validación de transiciones para feed, signal, light, simulation y label; prohibición estricta de `GREEN <-> RED` directo (CA-8).
6. **Esquemas JSON versionados:** 14 esquemas en `schemas/` con `additionalProperties: false`.

## Ciclos verticales

### Ciclo 1 · Resultado discriminado y 21 códigos de error

- **RED:** `python3.11 -B -m unittest tests.domain.test_result_and_error -v` -> `ModuleNotFoundError: No module named 'sistema_luces.domain.error'`.
- **GREEN:** Se implementaron `src/sistema_luces/domain/error.py` y `src/sistema_luces/domain/result.py`.
- **Resultado GREEN:** `Ran 4 tests in 0.002s`, `OK`.

### Ciclo 2 · Vocabulario cerrado, detección de entornos no permitidos y OPT-2

- **RED:** `python3.11 -B -m unittest tests.domain.test_vocabulary -v` -> `ModuleNotFoundError: No module named 'sistema_luces.domain.vocabulary'`.
- **GREEN:** Se implementó `src/sistema_luces/domain/vocabulary.py` con validación estricta de enteros escalados, precios, cantidades, factores de escala y ratio/probabilidad en `0..1_000_000`.
- **Resultado GREEN:** `Ran 7 tests in 0.003s`, `OK`.

### Ciclo 3 · DTOs de API pública y protección de rutas

- **RED:** `python3.11 -B -m unittest tests.domain.test_api_dtos -v` -> `ModuleNotFoundError: No module named 'sistema_luces.domain.api'`.
- **GREEN:** Se implementó `src/sistema_luces/domain/api.py` con validadores de UUID, hashes SHA-256, límites de consulta 1..200 y protección contra path traversal en staged copies.
- **Resultado GREEN:** `Ran 6 tests in 0.004s`, `OK`.

### Ciclo 4 · Sobre de eventos, payloads y JSON canónico

- **RED:** `python3.11 -B -m unittest tests.domain.test_event_envelope_and_canonical_json -v` -> `ModuleNotFoundError: No module named 'sistema_luces.domain.event'`.
- **GREEN:** Se implementó `src/sistema_luces/domain/event.py` con serializador JSON canónico recursivo (orden de claves, formato ISO UTC con `Z`, rechazo de NaN/Infinity) y validación de `payload_hash`.
- **Resultado GREEN:** `Ran 5 tests in 0.003s`, `OK`.

### Ciclo 5 · Máquina de estados y prohibición GREEN↔RED

- **RED:** `python3.11 -B -m unittest tests.domain.test_state_machine -v` -> `ModuleNotFoundError: No module named 'sistema_luces.domain.state'`.
- **GREEN:** Se implementó `src/sistema_luces/domain/state.py` con grafos de transición cerrados por agregado (`feed`, `signal`, `light`, `simulation`, `label`).
- **Resultado GREEN:** `Ran 4 tests in 0.002s`, `OK`.

### Ciclo 6 · Señales, simulaciones, métricas y manifiestos

- **RED:** `python3.11 -B -m unittest tests.domain.test_signal_and_simulation tests.domain.test_metric_and_manifests -v` -> `ModuleNotFoundError`.
- **GREEN:** Se implementaron `src/sistema_luces/domain/{signal,simulation,metric,manifest}.py`.
- **Resultado GREEN:** `Ran 10 tests in 0.006s`, `OK`.

### Ciclo 7 · Esquemas JSON versionados V1

- **RED:** `python3.11 -B -m unittest tests.domain.test_schemas_roundtrip -v` -> `AssertionError: Faltan esquemas`.
- **GREEN:** Se crearon los 14 esquemas JSON en `schemas/*.json`.
- **Resultado GREEN:** `Ran 1 test`, `OK`.

## Gate WP-01

- Comando único: `make verify`.
- Exit code: `0`.
- Suite completa: `Ran 44 tests in 0.057s`, `OK`.
- Seguridad y arquitectura: sin violaciones en `scan_repository`.
- Compilación y tabnanny: `exit 0` limpio.
