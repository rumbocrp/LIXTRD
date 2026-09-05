# Auditoría de realineación

**Fecha:** 2026-08-30  
**Alcance:** documentación y diseño de SistemaLuces frente a la nueva autoridad del dueño y
al Trading Journal inspeccionado en solo lectura.

## 1. Veredicto

El repositorio no era una V1 terminada. Era un scaffold amplio de contratos y piezas
aisladas, acompañado por una UI sintética que contradecía la verdad de datos exigida por sus
propios documentos. La raíz del fallo fue de autoridad: una SPEC generada por agentes se
marcó aprobada, luego se convirtió en un mandato interno y finalmente se certificó contra
tests diseñados por ese mismo mandato.

La nueva dirección mantiene lo valioso y cambia la presentación/operación para que el piloto
sea compatible desde ahora con Trading Journal y pueda integrarse allí más adelante.

## 2. Fuente de diseño auditada

Trading Journal aporta, sin ser modificado:

- monolito modular con dominio independiente del framework;
- Next.js App Router, React, TypeScript y Tailwind;
- shell con rail/escritorio y una navegación primaria móvil;
- sistema de tokens primitive→semantic→component, temas claro/nocturno y contraste AA;
- estados explícitos, N/A con razón y cifras con linaje;
- SQLite encapsulado en adaptadores, hechos/correcciones auditables y loopback;
- gates que separan documentación, dominio, UI, operación, seguridad y evidencia.

SistemaLuces adopta esas ideas como contrato. No copia su base, migraciones ni dominio.

## 3. Diagnóstico causal

| Hipótesis | Evidencia | Veredicto |
|---|---|---|
| Deriva de autoridad | SPEC/ADR antiguos nombraban al agente como diseñador/decisor; `ORIGINAL_REQUEST` no era la petición real. | causa raíz |
| Stack/interfaz divergentes | UI Python propia, estética de terminal y ausencia de seam de módulo `/luces`. | confirmada |
| Doble motor | módulos auditables por un lado; `quant` aleatorio alimentando la UI por otro. | confirmada |
| Evidencia sintética presentada como real | Pepperstone/«en línea», OFI y métricas prefijadas sin conexión/dataset. | confirmada |
| Gate semánticamente débil | tests de contratos/fakes usados para afirmar fuente, pipeline y producto terminados. | confirmada |

## 4. Inventario de código

| Área actual | Destino | Motivo |
|---|---|---|
| `domain` | conservar | contratos y vocabulario útiles; reconciliar con CONTEXT/SRS |
| `storage` | conservar | append-only, SQLite, hash, backup como base |
| `feed` | conservar | calidad y depth gate adecuados si reciben evidencia real |
| `cases` | conservar | ventanas causales; validar en pipeline completo |
| `learning/labels` y `splits` | conservar | base de etiquetado/purga, necesita corpus real |
| `models` | conservar parcialmente | logística/calibración/métricas; falta boosting y artefactos |
| `policy` | conservar | histéresis y amarillo seguro; conectar al campeón/costos |
| `risk` y `simulation` | conservar parcialmente | quitar supuestos no ratificados y dinero no calculable |
| `imports` y `observability` | conservar | base para demo/linaje; integrar con store/proyección |
| `sources/ctrader_demo.py` | reescribir/separar | hoy es un adaptador de mensajes inyectados, no una conexión |
| `application/replay_use_case.py` | reescribir | cuenta eventos; no compone el pipeline |
| `application/shadow_use_case.py` | reescribir | devuelve resumen vacío; no abre una sesión |
| `ui` Python actual | retirar de ruta operativa | no coincide con Trading Journal y mezcla fuentes |
| `quant` | cuarentena `SINTETICO` | revive el motor histórico invalidado y genera datos aleatorios |
| scripts de «demo vivo» | cuarentena/reemplazo | imprimen escenarios prefijados y no prueban una cuenta demo |

## 5. Divergencias y mitigaciones

| ID | Divergencia | Riesgo | Mitigación | Puerta |
|---|---|---|---|---|
| `DV-01` | autoridad generada por agentes | construir el producto equivocado | registro DO, SPEC-002, ADR-002 y guardián documental | G-R0 |
| `DV-02` | certificación prematura | falsa confianza | gate actual BLOCKED y separación de capas de evidencia | G-R0/R6 |
| `DV-03` | simulador rotulado como broker | decisión con datos falsos | banda SINTETICO, retirar claims y rutas públicas | G-R1 |
| `DV-04` | dos motores | UI y auditoría discrepan | único composition root y Proyección de lectura | G-R2 |
| `DV-05` | cTrader falso | no hay demo observada | adapter fixture separado + integración OAuth/stream real | G-R3 |
| `DV-06` | economía US500 no validada | P&L/riesgo falsos | N/A fail-closed hasta contrato y costos | G-R3 |
| `DV-07` | no hay datos/artefactos | métricas sin evidencia | cinco sesiones, manifests, hashes y storage fuera de Git | G-R3/R4 |
| `DV-08` | falta boosting | comparación incompleta | candidato tabular después de dataset válido | G-R4 |
| `DV-09` | UI fuera de plataforma | reescritura futura | panel en stack/tokens del Journal y host fixture | G-R5/R7 |
| `DV-10` | métricas sin linaje | claims no interpretables | contrato de métrica y guardián de presentación | G-R5 |
| `DV-11` | posible acoplamiento futuro | riesgo sobre Journal | BFF read-only, sidecar, DB separada y consumer tests | G-R7 |
| `DV-12` | datos personales/contrato | uso no autorizado | no importar ni entrenar hasta decisión y base legal | decisión abierta |

## 6. Resultado documental

- SPEC-001, ADR-001 y gate anterior se preservaron en `docs/legacy/`.
- SPEC-002, SRS, arquitectura, sistema visual, ADR-002, trazabilidad y plan son canónicos.
- `ORIGINAL_REQUEST.md` ahora conserva las decisiones reales del dueño.
- `AGENTS.md` impone preflight, fronteras y verdad operacional.
- `scripts/verificar_documentacion.py` constituye el feedback loop de R0.

Esta auditoría no cambia el código del producto ni Trading Journal. La corrección funcional
comienza en R1.

