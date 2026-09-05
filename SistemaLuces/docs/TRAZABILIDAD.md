# Trazabilidad de producto y verificación

**Versión:** 2.4.0
**Corte:** 2026-08-30  
**Estado:** canónico; refleja cobertura demostrada, no intención

## Convenciones

| Estado | Significado |
|---|---|
| `BASELINE` | existe una prueba local útil, pero aún no satisface la Puerta nueva |
| `PLANIFICADO` | requisito especificado; falta implementación/evidencia |
| `BLOCKED_EXTERNAL` | requiere cuenta, sesión o decisión externa real |
| `PASS_TECNICO` | evidencia reproducible disponible; falta aprobación de Puerta si aplica |
| `PASS` | Puerta aprobada con toda su evidencia |

## Catálogo de verificaciones

| ID | Verificación | Tipo | Fase |
|---|---|---|---|
| `T-DOC-001` | autoridad, archivos, links y términos prohibidos | automática | R0 |
| `T-JRN-001` | HEAD/estado del Trading Journal antes y después, sólo lectura | auditoría | R0/R7 |
| `T-SEC-001` | LIVE y capacidades de órdenes ausentes del runtime completo | estática/adversarial | R1 |
| `T-PROV-001` | procedencia preservada y sintético nunca rotulado demo | contrato/UI | R1 |
| `T-PROJ-001` | producer/consumer contract de Proyección V1 | contrato | R2 |
| `T-PIPE-001` | replay y shadow atraviesan el mismo composition root | integración | R2 |
| `T-REP-001` | corpus dorado reproducible, restart y restore | end-to-end | R2 |
| `T-DEMO-001` | handshake, cuenta demo y capabilities read-only | externa | R3 |
| `T-ECON-001` | símbolo, escalas, valor por punto y costos US500 | externa/contrato | R3 |
| `T-SESS-001` | cinco sesiones raw+normalizadas con manifiesto/hash | externa | R3 |
| `T-SIM-001` | ciclo de Operativa simulada y conciliación | integración | R3/R6 |
| `T-ML-001` | dataset causal, baselines, calibración y walk-forward | evaluación | R4 |
| `T-UI-001` | siete estados, linaje, temas, accesibilidad y reflujo | UI | R5 |
| `T-OPS-001` | cinco sesiones shadow, incidentes y reproducibilidad | operación | R6 |
| `T-HOST-001` | host fixture `/luces`, BFF read-only y ausencia de `tj.db` | integración | R7 |
| `T-DIAG-001` | barra de transición deriva del mismo `SIGNAL_EMITTED`, con umbrales y distancia | contrato/UI | R2/R5 |
| `T-XASSET-001` | US500 no inventa AAPL/TSLA; snapshot explícito conserva fuente, edad y umbrales | contrato/UI | R2/R3/R5 |
| `T-YAHOO-001` | Yahoo limita la ingesta a `^GSPC`, `TSLA`, `AAPL`, `GC=F`; WebSocket/REST conservan precio, timestamp, estado y ausencias hasta HTTP/UI | contrato/integración externa opt-in | R2/R5 |
| `T-ASSET-DIAG-001` | cada activo fusiona y presenta su propio diagnóstico; los demás permanecen N/A y no heredan la señal | contrato/UI | R2/R5 |
| `T-UI-INC-001` | HTML estable, recurso same-origin, CSP, actualización parcial, timeout, backoff y ausencia de recarga/HTML remoto | contrato/UI/HTTP | R5 |
| `T-SPEC-EVO-001` | cada defecto verificado conserva causa, invariante, regresión, estado y mejora futura | documental | R0/R5 |

## Objetivos

| Objetivo | Requisitos | Verificaciones | Puertas |
|---|---|---|---|
| `OBJ-L01` | RF-L001…L012, L029…L032, L035…L036; RNF-L001…L005, L014 | T-SEC-001, T-PROV-001, T-PIPE-001, T-REP-001, T-YAHOO-001, T-ASSET-DIAG-001 | G-R1, G-R2 |
| `OBJ-L02` | RF-L013…L020; RNF-L007, L013 | T-DEMO-001, T-ECON-001, T-SIM-001, T-OPS-001 | G-R3, G-R6 |
| `OBJ-L03` | RF-L005…L011, L019; RNF-L004, L007…L009, L012 | T-PROJ-001, T-REP-001, T-ML-001 | G-R2, G-R4 |
| `OBJ-L04` | RF-L016…L022, L027…L028, L033…L036; RNF-L005…L007, L013, L015 | T-PROV-001, T-PROJ-001, T-UI-001, T-DIAG-001, T-XASSET-001, T-ASSET-DIAG-001, T-UI-INC-001, T-SPEC-EVO-001 | G-R1, G-R5 |
| `OBJ-L05` | RF-L015, L021…L023; RNF-L003, L006, L012 | T-JRN-001, T-PROJ-001, T-HOST-001 | G-R0, G-R7 |

## Requisitos funcionales

| Requisito | Verificación primaria | Puerta | Estado actual |
|---|---|---|---|
| `RF-L001` | T-SEC-001 | G-R1 | BASELINE |
| `RF-L002` | T-PIPE-001 | G-R2 | BASELINE |
| `RF-L003` | T-PROV-001 | G-R1 | PLANIFICADO |
| `RF-L004` | T-SEC-001 | G-R1 | BASELINE |
| `RF-L005` | T-REP-001 | G-R2 | BASELINE |
| `RF-L006` | T-REP-001 | G-R2 | BASELINE |
| `RF-L007` | T-PROJ-001 | G-R2 | PLANIFICADO |
| `RF-L008` | T-PIPE-001 | G-R2 | BASELINE |
| `RF-L009` | T-PIPE-001 | G-R2 | BASELINE |
| `RF-L010` | T-REP-001 | G-R2 | PLANIFICADO |
| `RF-L011` | T-PIPE-001 | G-R2 | PLANIFICADO |
| `RF-L012` | T-SIM-001 | G-R2 | BASELINE |
| `RF-L013` | T-DEMO-001 | G-R3 | BLOCKED_EXTERNAL |
| `RF-L014` | T-SIM-001 | G-R3 | BASELINE |
| `RF-L015` | T-PROJ-001 | G-R2 | PLANIFICADO |
| `RF-L016` | T-UI-001 | G-R5 | PLANIFICADO |
| `RF-L017` | T-UI-001 | G-R5 | PLANIFICADO |
| `RF-L018` | T-SIM-001, T-UI-001 | G-R5 | PLANIFICADO |
| `RF-L019` | T-PROJ-001, T-UI-001 | G-R5 | PLANIFICADO |
| `RF-L020` | T-UI-001 | G-R5 | PLANIFICADO |
| `RF-L021` | T-UI-001 | G-R5 | PLANIFICADO |
| `RF-L022` | T-PROJ-001 | G-R5 | PLANIFICADO |
| `RF-L023` | T-HOST-001 | G-R7 | PLANIFICADO |
| `RF-L024` | T-SESS-001 | G-R3 | BLOCKED_EXTERNAL |
| `RF-L025` | T-ML-001 | G-R4 | PLANIFICADO |
| `RF-L026` | T-ML-001 | G-R4 | PLANIFICADO |
| `RF-L027` | T-DIAG-001 | G-R2/G-R5 | PASS_TECNICO |
| `RF-L028` | T-XASSET-001 | G-R2/G-R3/G-R5 | PASS_TECNICO en REPLAY; `BLOCKED_EXTERNAL` para datos demo observados |
| `RF-L029` | T-YAHOO-001 | G-R2/G-R5 | PASS_INTEGRATION |
| `RF-L030` | T-YAHOO-001 | G-R2/G-R5 | PASS_INTEGRATION; soak 24/7 pendiente |
| `RF-L031` | T-YAHOO-001 | G-R2/G-R5 | PASS_INTEGRATION |
| `RF-L032` | T-YAHOO-001, T-PIPE-001 | G-R2 | PASS_TECNICO; adaptador futuro pendiente |
| `RF-L033` | T-UI-INC-001 | G-R5 | PASS_TECNICO; harness DOM de recuperación pendiente |
| `RF-L034` | T-SPEC-EVO-001 | G-R0/G-R5 | PASS_TECNICO; proceso evolutivo iniciado en SPEC-003 |
| `RF-L035` | T-YAHOO-001 | G-R2/G-R5 | PASS_INTEGRATION; soak 24/7 pendiente |
| `RF-L036` | T-ASSET-DIAG-001 | G-R2/G-R5 | PASS_TECNICO; fórmulas/modelos por activo pendientes |

## Requisitos no funcionales

| Requisito | Verificación primaria | Puerta | Estado actual |
|---|---|---|---|
| `RNF-L001` | T-SEC-001 | G-R1 | BASELINE |
| `RNF-L002` | T-SEC-001 | G-R1 | BASELINE; ampliar superficie |
| `RNF-L003` | T-SEC-001, T-HOST-001 | G-R1/G-R7 | BASELINE |
| `RNF-L004` | T-PIPE-001, T-ECON-001 | G-R2/G-R3 | BASELINE |
| `RNF-L005` | T-PROV-001, T-UI-001 | G-R1/G-R5 | PLANIFICADO |
| `RNF-L006` | T-UI-001 | G-R5 | PLANIFICADO |
| `RNF-L007` | T-PROJ-001, T-UI-001 | G-R2/G-R5 | PLANIFICADO |
| `RNF-L008` | T-REP-001 | G-R2 | PLANIFICADO |
| `RNF-L009` | T-REP-001 | G-R2 | BASELINE; falta E2E |
| `RNF-L010` | T-REP-001 | G-R2 | PLANIFICADO |
| `RNF-L011` | T-SEC-001, T-SESS-001 | G-R1/G-R3 | PLANIFICADO |
| `RNF-L012` | T-PROJ-001, T-HOST-001 | G-R2/G-R7 | PLANIFICADO |
| `RNF-L013` | T-PROJ-001, T-UI-001 | G-R2/G-R5 | PLANIFICADO |
| `RNF-L014` | T-YAHOO-001 | G-R2/G-R5 | PASS_INTEGRATION; latencia del proveedor sin SLA |
| `RNF-L015` | T-UI-INC-001 | G-R5 | PASS_TECNICO; QA de navegador/multidispositivo pendiente |

## Reglas de negocio

| Reglas | Verificación | Puerta | Estado actual |
|---|---|---|---|
| `RB-L001`…`RB-L004` | T-PIPE-001, T-SIM-001 | G-R2 | BASELINE; falta integración |
| `RB-L005`…`RB-L007` | T-REP-001, T-SIM-001 | G-R2 | BASELINE; falta E2E |
| `RB-L008` | T-ECON-001, T-SIM-001 | G-R3 | BLOCKED_EXTERNAL |
| `RB-L009` | T-ML-001 | G-R4 | BASELINE |
| `RB-L010`…`RB-L011` | T-ML-001 | G-R4 | PLANIFICADO |
| `RB-L012` | T-PROV-001 | G-R1 | PLANIFICADO |
| `RB-L013`…`RB-L014` | T-YAHOO-001 | G-R2/G-R5 | PASS_INTEGRATION |
| `RB-L015` | T-ASSET-DIAG-001 | G-R2/G-R5 | PASS_TECNICO; no hay agregador operativo aprobado |

## Estado de Puertas

| Puerta | Estado | Evidencia vigente |
|---|---|---|
| `G-R0` | PASS_TECNICO; aprobación del dueño pendiente | `docs/evidence/v1-gate.md` |
| `G-R1` | BLOCKED_REBASELINE | sin evidencia nueva |
| `G-R2` | BLOCKED_REBASELINE | Yahoo atraviesa Proyección/HTTP, pero falta aprobar el composition root completo |
| `G-R3` | BLOCKED_EXTERNAL | sin conexión/sesiones demo reales |
| `G-R4` | BLOCKED_REBASELINE | sin dataset/artefactos evaluados |
| `G-R5` | BLOCKED_REBASELINE | UI actual en cuarentena |
| `G-R6` | BLOCKED_REBASELINE | depende de R2–R5 |
| `G-R7` | BLOCKED_REBASELINE | depende de R5–R6; Journal permanece intacto |

Actualizar un estado requiere enlazar evidencia reproducible; editar esta tabla sin ella no
cambia ninguna Puerta.

`T-YAHOO-001` y `T-ASSET-DIAG-001` están evidenciados en
[`AUDITORIA-FUENTE-YAHOO-MULTI-ACTIVO-2026-08-30.md`](./AUDITORIA-FUENTE-YAHOO-MULTI-ACTIVO-2026-08-30.md).
No satisface `T-DEMO-001`, `T-ECON-001` ni `T-SESS-001`.
