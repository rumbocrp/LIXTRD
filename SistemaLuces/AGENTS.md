# Reglas para trabajar en SistemaLuces

## Preflight obligatorio

1. Lee `ORIGINAL_REQUEST.md` y `docs/README.md`.
2. Para producto o requisitos, lee `docs/specs/SPEC-002-integracion-futura-trading-journal.md`
   y `docs/SRS.md`.
3. Para código o estructura, lee `docs/ARQUITECTURA.md` y el ADR aplicable.
4. Para interfaz, lee `docs/SISTEMA-VISUAL.md`.
5. Para una fase, trabaja sólo el bloque correspondiente de `docs/PLAN-REALINEACION.md`.

El preflight termina cuando la tarea puede vincularse a requisitos y a una Puerta vigentes.

Para Antigravity Teamwork o ejecución multiagente de R1–R7, lee además
`docs/teamwork/README.md` y usa `docs/teamwork/ANTIGRAVITY-TEAMWORK-SYSTEM-PROMPT.md` como prompt
de entrada. Sus artefactos de ejecución viven bajo `docs/teamwork/run/` y nunca sustituyen la
SPEC, el SRS o la trazabilidad.

## Autoridad y fronteras

- Trading Journal es referencia de solo lectura. Este repositorio no lo modifica, no abre
  `tj.db` y no importa sus paquetes en runtime.
- La integración futura usa un contrato versionado de lectura. El motor y su base permanecen
  separados hasta que un ADR posterior diga lo contrario.
- Las decisiones del dueño prevalecen. Una decisión técnica nueva se rotula `PROPUESTA` hasta
  que su Puerta o ADR tenga aprobador y evidencia.

## Verdad operacional

- Usa `REAL`, `DEMO_OBSERVADO`, `SHADOW`, `REPLAY`, `SINTETICO` y `NO_DATA` con significado
  explícito. Un fixture conserva siempre `SINTETICO`.
- Toda métrica visible declara fuente, periodo, muestra, versión y estado de maduración.
- Un dato ausente es `None`/`null` y produce `N/A` o amarillo; nunca un valor plausible.
- Profundidad, OFI y microprecio sólo existen después de la Puerta `G-R3`.
- La UI operativa consume la misma proyección que replay y shadow. No se crean motores
  paralelos para alimentar una pantalla.

## Diseño y lenguaje

- La interfaz replica el contrato visual del Trading Journal mediante un snapshot versionado
  de tokens semánticos; no copia colores sueltos ni importa su runtime.
- Color y texto viajan juntos. Verde = `LARGO`, amarillo = `MONITORIZAR`, rojo = `CORTO`.
- Conserva los siete estados del Journal: cargando, vacío, parcial, error, obsoleto,
  conflicto y éxito; `NO_DATA` es el estado inicial del producto.
- El vocabulario de `CONTEXT.md` es canónico. Código de dominio, pruebas y documentación se
  escriben en español salvo nombres de APIs externas.

## Desarrollo y evidencia

- Construye primero un test rojo en el seam más alto disponible y termina con la Puerta de
  la fase, no sólo con tests unitarios.
- Distingue `PASS_CONTRACT`, `PASS_INTEGRATION`, `BLOCKED_EXTERNAL` y `FAIL`. Ninguno implica
  `PASS_PRODUCT` por sí solo.
- Archivos de mercado, bases, modelos, credenciales, cuentas y respaldos permanecen fuera de
  Git. La evidencia en Git contiene manifiestos y hashes, no secretos ni datos privados.
- Antes de cerrar, ejecuta `python3.11 -B scripts/verificar_documentacion.py`, las pruebas de
  la fase y el feedback loop end-to-end definido por su Puerta.

Trabajo terminado significa: requisito trazado, comportamiento verificado en su seam real,
evidencia archivada, documentación actualizada y ninguna frontera violada.
