# Estrategia de pruebas y evidencia

**Versión:** 2.0.0  
**Estado:** canónico para la realineación R0–R7

## Principio

Las pruebas responden preguntas diferentes y no son intercambiables. Una prueba unitaria
demuestra comportamiento local; una Puerta de producto exige además integración, procedencia y,
cuando aplique, evidencia externa de una cuenta demo.

## Capas

| Capa | Pregunta | Ejecutor | Resultado admisible |
|---|---|---|---|
| Documentación | ¿Hay una sola autoridad coherente y links válidos? | `scripts/verificar_documentacion.py` | PASS/FAIL reproducible |
| Arquitectura | ¿Se respetan loopback, demo-only, cero órdenes y límites de imports? | escaneo + tests | PASS/FAIL |
| Dominio | ¿Las reglas puras y estados son correctos? | unit/property tests | PASS/FAIL |
| Contrato | ¿La Proyección V1 conserva esquema, procedencia y `NO_DATA`? | producer/consumer tests | PASS/FAIL |
| Integración | ¿Replay, shadow, store y UI usan el mismo composition root? | tests con adapters reales/fakes tipados | PASS/FAIL |
| Externa pública | ¿Yahoo devuelve exclusivamente `^GSPC` con precio, timestamp y procedencia? | prueba opt-in sin secretos | PASS_INTEGRATION/FAIL |
| Externa demo | ¿La cuenta, símbolo, economía y sesiones provienen de cTrader demo read-only? | harness supervisado | PASS/BLOCKED_EXTERNAL/FAIL |
| Modelo | ¿Hay utilidad neta fuera de muestra y calibración suficiente? | evaluación sellada | APTO/SIN_VENTAJA/FAIL |
| Experiencia | ¿La interfaz es honesta, accesible y trasladable al Journal? | axe, visual, responsive, contract | PASS/FAIL |
| Operación | ¿Cinco sesiones shadow son reproducibles y conciliables? | runbook + manifests | CONTINUAR/AJUSTAR/DESCARTAR |

## Reglas del harness

- UTC, relojes inyectables y semillas explícitas cuando exista aleatoriedad.
- Temporales aislados dentro del workspace; ninguna dependencia en el home del usuario.
- Puertos efímeros o servidor in-process; si el sandbox prohíbe sockets, se registra como
  incidencia de infraestructura y se prueba el handler sin red.
- Datos financieros exactos y ausencia preservada como `null`/N/A con razón.
- Fixtures marcados `SINTETICO` o `REPLAY`; ningún nombre de broker en datos inventados.
- Evidencia externa con manifiesto, hash, corte, versión, comando y exit code.
- La prueba Yahoo se omite en el gate offline y se activa con `RUN_YAHOO_INTEGRATION=1`; su
  PASS no se interpreta como handshake de cuenta demo ni certificación de tiempo real.
- Secretos, identificadores de cuenta y rutas personales se redactan antes de persistir.

## Relación con las Puertas

| Puerta | Evidencia principal |
|---|---|
| `G-R0` | verificador documental y comprobación read-only del Journal |
| `G-R1` | pruebas adversariales de procedencia, copy y cero capacidades de órdenes |
| `G-R2` | corpus dorado y consumer contract de Proyección V1 |
| `G-R3` | handshake demo, economía US500 y cinco manifests de sesión |
| `G-R4` | dataset/manifiesto, walk-forward, costos y artefactos de modelo |
| `G-R5` | contrato UI, estados, accesibilidad, temas y matriz multidispositivo |
| `G-R6` | sesiones shadow, simulaciones, conciliación e incidentes |
| `G-R7` | host fixture `/luces`, BFF read-only y ensayo de rollback |

## Política de veredicto

- No se suman conteos de pruebas de distintas ejecuciones para formar un PASS.
- `SKIP` y `BLOCKED_EXTERNAL` se reportan, nunca se convierten en verde.
- Un test que sólo afirma que existe un stub no satisface una integración.
- Las métricas de rendimiento requieren dataset, muestra, corte, costos y método.
- La revisión de Puerta la realiza una persona o agente distinto al implementador.

La matriz antigua se conserva sólo como historia en
[`docs/legacy/TEST_INFRA-agentes.md`](./docs/legacy/TEST_INFRA-agentes.md).
