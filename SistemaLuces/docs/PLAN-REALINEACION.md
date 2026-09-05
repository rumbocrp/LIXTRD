# Plan de realineación R0–R7

**Objetivo:** convertir el scaffold actual en un piloto honesto, demo-only y compatible con
la futura ruta `/luces` de Trading Journal.  
**Regla:** Trading Journal permanece de solo lectura durante todo este plan.

## Dependencias

```text
R0 → R1 → R2 → R3 → R4 → R6
                 └────→ R5 ───→ R7
                         R6 ───→ R7
```

R5 puede diseñarse sobre el contrato de R2 mientras R3 captura sesiones. R4 no empieza sin
datos/economía suficientes. R7 valida un host fixture, no modifica el Journal real.

## R0 · Autoridad, documentación y baseline

**Objetivo:** una sola idea de producto y un gate que no pueda autocertificarse.

Subsecciones acotadas:

- `R0-A` autoridad: decisiones DO/DC/DA, jerarquía y ADR-002;
- `R0-B` requisitos: SPEC-002, SRS y trazabilidad;
- `R0-C` diseño: arquitectura y sistema visual;
- `R0-D` auditoría: legado, gate actual y verificador documental;
- `R0-E` baseline: inventario, secretos/datos y commit autorizado.

**G-R0:** verificador documental verde; links válidos; documentación vieja bajo `legacy`;
Trading Journal sin cambios nuevos; estado de producto `BLOCKED_REBASELINE`.

## R1 · Seguridad semántica y cuarentena

**Objetivo:** impedir que el prototipo sintético se presente como producto.

Subsecciones:

- `R1-A` test rojo de procedencia: SINTETICO nunca se renderiza como Pepperstone/demo/live;
- `R1-B` sacar `quant` y scripts prefijados de la ruta pública;
- `R1-C` eliminar defaults de métricas/modelo/hash y usar `NO_DATA`;
- `R1-D` ampliar escaneo de seguridad a `scripts`, UI, dependencias y contratos;
- `R1-E` revisar copy, estados y errores.

**G-R1:** UI existente, si aún se sirve, abre en `NO_DATA` o `SINTETICO` inequívoco; no hay
claims sin linaje; ausencia de órdenes verificada en todo runtime.

## R2 · Un solo pipeline y Proyección de lectura

**Objetivo:** que replay, shadow y UI compartan comportamiento.

Subsecciones:

- `R2-A` contrato JSON/schema y consumer contract de Proyección V1;
- `R2-B` composition root con puertos de fuente, archivo, modelo y reloj;
- `R2-C` replay end-to-end determinista;
- `R2-D` shadow end-to-end con fuente fake explícita;
- `R2-E` proyecciones reconstruibles, restart y backup/restore;
- `R2-F` benchmark por tramo.
- `R2-G` adaptador público transitorio `^GSPC`: WebSocket + REST, procedencia, mercado
  cerrado y ausencias preservadas; no sustituye el composition root ni la Fuente demo.
- `R2-H` observación Yahoo multi-activo: `^GSPC`, `TSLA`, `AAPL`, `GC=F`, fusión parcial
  por símbolo y diagnóstico independiente opcional sin inferencias desde el precio.

**G-R2:** un corpus dorado produce la misma Proyección byte-a-byte en dos ejecuciones; replay
y shadow difieren sólo en Fuente/Reloj; UI no importa `quant`.

## R3 · Fuente demo, contrato económico y cinco sesiones

**Objetivo:** reemplazar fixtures por evidencia read-only real.

Subsecciones:

- `R3-A` OAuth/capabilities/metadata demo sin registrar secretos;
- `R3-B` adapter cTrader real con heartbeat, reconexión y backpressure;
- `R3-C` catálogo US500 y economía del contrato;
- `R3-D` captura raw+normalizada de cinco sesiones;
- `R3-E` calidad de bid/ask y veredicto depth;
- `R3-F` importación de Ejecuciones demo y conciliación.

**G-R3:** cinco manifests de sesión con hashes; cuenta demo y símbolo verificados; costos y
escalas aprobados o P&L en N/A; depth `ACEPTADO`/`DESCARTADO`; cero órdenes.

**Bloqueo externo legítimo:** si no hay OAuth o datos, R3 queda `BLOCKED_EXTERNAL`; no se
sustituye por Yahoo, random ni una etiqueta falsa de broker.

Yahoo puede mantener observable la UI y validar el seam de fuente durante ese bloqueo. Su
evidencia se clasifica `PASS_INTEGRATION` de `R2-G`; nunca se cuenta entre las cinco sesiones
demo ni habilita economía, depth, order flow, simulación o promoción de modelo.

## R4 · Modelos y utilidad neta

**Objetivo:** demostrar ventaja o aceptar `SIN_VENTAJA`.

Subsecciones:

- `R4-A` dataset causal, etiquetas maduras y manifiesto;
- `R4-B` referencias siempre-amarillo/tasa-base/regla simple;
- `R4-C` logística regularizada + calibración OOF;
- `R4-D` boosting tabular retador;
- `R4-E` walk-forward purgado, costos base/adverso/estrés;
- `R4-F` registry, promoción humana, rollback y drift.

**G-R4:** mismo dataset/costos para todos; Brier, log loss, calibración, cobertura y utilidad
neta; artefactos hasheados; >90 % abre incidente; sin ventaja deja amarillo.

## R5 · Interfaz compatible con Trading Journal

**Objetivo:** panel standalone trasladable y visualmente coherente.

Subsecciones:

- `R5-A` snapshot versionado de tokens semantic/component;
- `R5-B` shell Next/React/Tailwind compatible y diccionario español;
- `R5-C` adaptador server-side/BFF para Proyección V1;
- `R5-D` pantalla principal, transiciones, simulaciones y métricas con linaje;
- `R5-E` siete estados, temas, teclado, reflujo y reduced motion;
- `R5-F` consumer tests y visual QA.
- `R5-G` SPEC evolutiva de defectos y sincronización incremental: HTML estable, polling JSON,
  backoff, estado accesible y posterior evaluación de push/SSE o WebSocket de proyección.
- `R5-H` tabla multi-activo estable con cuatro barras diagnósticas independientes y N/A
  explícito cuando falta fórmula/modelo por símbolo.

**G-R5:** contrato/temas/contraste/axe/multidispositivo verdes; ningún cálculo financiero en
React; motor ausente produce `NO_DATA`, no valores de muestra.

## R6 · Shadow demo y decisión de continuidad

**Objetivo:** operar cinco sesiones sin intervenir el broker.

Subsecciones:

- `R6-A` runbook y freeze de configuración;
- `R6-B` cinco sesiones shadow continuas;
- `R6-C` maduración de etiquetas y Operativas simuladas;
- `R6-D` conciliación con Ejecuciones demo observadas;
- `R6-E` incidentes, latencia, drift, costos y cobertura;
- `R6-F` informe y veredicto humano.

**G-R6:** todas las decisiones reproducibles; métricas maduras con linaje; incidentes
resueltos/aceptados; veredicto `CONTINUAR`, `AJUSTAR` o `DESCARTAR` firmado por el dueño.

## R7 · Preparación de integración futura

**Objetivo:** probar la incorporación sin tocar el Trading Journal real.

Subsecciones:

- `R7-A` host fixture con route group/layout y ruta `/luces`;
- `R7-B` BFF read-only y same-origin;
- `R7-C` navegación/textos/tokens como lista de cambios futura;
- `R7-D` operación del sidecar y estado cuando está ausente;
- `R7-E` plan de migración/rollback y consumer contract;
- `R7-F` estimación y decisión go/no-go.

**G-R7:** módulo montado en host fixture sin iframe, sin SQL ni `tj.db`; contrato compatible;
lista exacta de cambios futuros al Journal; cero cambios aplicados al Journal.

## Matriz de mitigación de riesgo

| Riesgo | Prevención | Detección | Recuperación |
|---|---|---|---|
| autoridad incorrecta | DO/ADR/AGENTS | verificador documental | reabrir R0 |
| datos ficticios | procedencia tipada | test UI/contrato | NO_DATA/amarillo |
| doble pipeline | composition root | test end-to-end | retirar adapter paralelo |
| fuga temporal | corte causal/purga | sabotaje futuro | invalidar artefacto |
| overfitting | baseline + walk-forward | múltiples ventanas/costos | SIN_VENTAJA |
| cTrader no disponible | gate externo | handshake real | BLOCKED_EXTERNAL |
| economía incompleta | N/A fail-closed | contract checks | no calcular dinero |
| OFI inválido | depth apagado | cinco sesiones | DESCARTADO |
| drift visual | snapshot tokens | guardián/contraste | regenerar snapshot |
| rotura futura del Journal | host fixture/BFF | consumer tests | no integrar/rollback |
| exposición/red | loopback/same-origin | bind/CSP tests | apagar servicio |
| privacidad | hashes/retención | escaneo artefactos | cuarentena y borrado autorizado |

## Disciplina de ejecución

- Un implementador por ownership de archivos; investigación y QA pueden ser paralelos.
- Cada subsección tiene un test rojo o artefacto de entrada antes de implementar.
- Un auditor independiente revisa la Puerta contra evidencia, no contra el relato del agente.
- Dos fallos idénticos después de reparación dejan la fase `BLOCKED`; no se rebaja el gate.
- Nunca se adelanta código de una fase bloqueada por decisión o evidencia externa.
