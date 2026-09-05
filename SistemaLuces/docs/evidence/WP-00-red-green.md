# WP-00 · Evidencia RED→GREEN

> **HISTÓRICO:** baseline del primer intento; no acredita una Puerta R0–R7.

## Costuras preacordadas antes de escribir pruebas

La SPEC-001 aprobada y reauditable fija estas costuras públicas para WP-00:

1. **API raíz:** `sistema_luces` expone exactamente cuatro casos de uso:
   `ejecutar_replay`, `ejecutar_shadow`, `importar_demo_observada` y
   `consultar_vista`.
2. **Distribución, source y configuración:** se inspeccionan como superficies separadas y
   no pueden contener `LIVE`, capacidades o símbolos de órdenes, imports de
   `trading_bot`/Trading Journal, rutas `tj.db` ni dependencias fuera de allowlist.
3. **Manifest de capabilities:** el conjunto permitido es exacto y read-only:
   `market_data.read`, `account_metadata.read` y
   `historical_executions.read`.

Estas costuras son preacordadas por SPEC-001 §§3 DM-1/DM-9, 5.2, 10, 12.3 y 13 WP-00;
no se solicitó una interfaz nueva.

## Procedencia documental

- SPEC origen: `/Users/nuevo/Documents/PROYECTOS/trading_bot/docs/specs/SPEC-001-sistema-luces-demo-observable.md`
- SHA-256 SPEC origen: `fa9677613dd1d0167abd6e918d9c9a8f59447aca4aacaa4f8aedcebefb4afbe6`
- ADR origen: `/Users/nuevo/Documents/PROYECTOS/trading_bot/docs/adr/ADR-001-producto-independiente-demo-sin-ordenes.md`
- SHA-256 ADR origen: `76aa55cc1eeb083809ef374b80500801ccb0962b385b941829b8d5e40bdd6c23`

## Ciclos verticales

### Ciclo 1 · API raíz exacta

- **RED:** `python3.11 -B -m unittest tests.architecture.test_forbidden_capabilities.RootApiTests.test_root_api_exports_exactly_four_use_cases -v`
- **Resultado RED:** exit `1`; la aserción informó que faltaban los cuatro casos de uso
  públicos en el paquete raíz.
- **GREEN:** se creó `src/sistema_luces/__init__.py` con sólo los cuatro stubs y
  `__all__` exacto.
- **Resultado GREEN:** el mismo comando terminó con exit `0`; `Ran 1 test`, `OK`.

### Ciclo 3 · Runtime y lockfile reproducibles

- **RED:** `python3.11 -B -m unittest tests.architecture.test_forbidden_capabilities.ReproducibilityTests.test_python_runtime_and_lock_are_fixed_without_dependencies -v`
- **Resultado RED:** exit `1`; `FileNotFoundError` para `pyproject.toml` aún ausente.
- **GREEN:** se fijó Python `3.11.16` (`requires-python ==3.11.*`), SQLite `3.53.1`,
  timezone `UTC`, locale `C`, hash seed `0` y clock seed `20260829`; `uv lock --offline
  --python 3.11.16` resolvió exactamente un paquete local y ninguna dependencia externa.
- **Resultado GREEN:** el test focal terminó con exit `0`; `Ran 1 test`, `OK`.

### Ciclo 4 · Checker rojo-capable de capacidades prohibidas

- **RED:** `python3.11 -B -m unittest tests.architecture.test_forbidden_capabilities.ArchitectureGuardTests.test_forbidden_mutations_turn_architecture_check_red -v`
- **Resultado RED:** exit `1`; `ModuleNotFoundError` porque el comprobador de política aún
  no existía.
- **GREEN:** se creó `tests/architecture/policy_check.py`. El test ejecuta probes aislados
  para `LIVE`, `OrderGateway`, `place_order`, scope `account.write`, `tj.db`, imports
  `trading_bot`/Trading Journal, import dinámico, dependencia directa, dependencia
  transitiva y símbolo de órdenes oculto en wheel.
- **Resultado GREEN:** el test de mutaciones terminó con exit `0`; `Ran 1 test`, `OK`.
  El check focal del repositorio real también terminó con exit `0`; `Ran 1 test`, `OK`.

### Ciclo 5 · Un único comando local

- **RED:** `python3.11 -B -m unittest tests.architecture.test_forbidden_capabilities.ReproducibilityTests.test_single_local_verification_command_is_documented -v`
- **Resultado RED:** exit `1`; `FileNotFoundError` para `README.md` aún ausente.
- **GREEN:** se añadieron `README.md`, `.gitignore` y `Makefile`; `make verify` comprueba el
  lock offline, ejecuta toda la suite, compila y pasa `tabnanny`, sólo con stdlib/uv local.
- **Resultado GREEN:** el test focal terminó con exit `0`; `Ran 1 test`, `OK`.

## Integridad de las copias aprobadas

- `cmp` origen/destino de SPEC: exit `0`.
- `cmp` origen/destino de ADR: exit `0`.
- SHA-256 SPEC destino: `fa9677613dd1d0167abd6e918d9c9a8f59447aca4aacaa4f8aedcebefb4afbe6`.
- SHA-256 ADR destino: `76aa55cc1eeb083809ef374b80500801ccb0962b385b941829b8d5e40bdd6c23`.

## Gate WP-00

- Comando único: `make verify`.
- Exit code: `0`.
- Lock offline: Python `3.11.16`, un paquete local resuelto, cero dependencias externas.
- Suite: `Ran 6 tests in 0.035s`, `OK`.
- Arquitectura: el repositorio real pasó y todos los probes prohibidos volvieron rojo.
- Compilación: `python3.11 -B -m compileall -q src tests`, sin salida y exit `0`.
- Lint stdlib: `python3.11 -B -m tabnanny src tests`, sin salida y exit `0`.

## Git

- `git init -b main`: exit `0`.
- Commit inicial: **bloqueado deliberadamente**. `git config --show-origin
  --get-regexp '^user\.(name|email)$'` no devolvió ninguna identidad configurada. Aunque
  Git puede sintetizar `nuevo <nuevo@MacBook-Air-de-nuevo.local>` desde el host, usarla
  violaría la instrucción de no inventar identidad.
- Consecuencia del gate: no se exige working tree limpio porque el commit no puede crearse
  bajo la condición autorizada; el árbol contiene únicamente los archivos iniciales sin
  seguimiento.

### Ciclo 2 · Allowlist read-only

- **RED:** `python3.11 -B -m unittest tests.architecture.test_forbidden_capabilities.SecurityPolicyTests.test_security_policy_has_exact_read_only_allowlists -v`
- **Resultado RED:** exit `1`; `FileNotFoundError` para el manifiesto todavía ausente.
- **GREEN:** se creó `config/security-policy-v1.json` con cuatro exports permitidos,
  tres capabilities read-only y allowlists vacías para dependencias, imports, CLI y HTTP.
- **Resultado GREEN:** el mismo comando terminó con exit `0`; `Ran 1 test`, `OK`.
