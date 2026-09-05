# Estado y mapa de trabajo

**Corte:** 2026-08-30  
**Estado global:** `BLOCKED_REBASELINE`  
**Producto:** piloto separado, preparado para integración futura en Trading Journal

## Lo que existe

| Área | Estado | Tratamiento |
|---|---|---|
| Dominio, eventos y vocabulario | base útil | conservar y reconciliar con el SRS |
| SQLite append-only y hashes | base útil | integrar en una ruta única |
| Salud de feed y gates | base útil | conservar; alimentar con datos reales |
| Casos, etiquetas y splits temporales | base útil | validar end-to-end |
| Logística, calibración y métricas | parcial | faltan dataset, artefactos y evaluación real |
| Boosting tabular | ausente | implementar después de cerrar datos/economía |
| Política, riesgo y simulación | parcial | conservar; eliminar valores no ratificados o no calculables |
| Adaptador cTrader | doble/fixture | reescribir como integración real read-only |
| Adaptador Yahoo `^GSPC` | integración pública transitoria | `PASS_INTEGRATION`; útil para monitor, no satisface G-R3 |
| Replay y shadow | stubs de composición | conectar el pipeline completo |
| UI Python standalone | monitor REPLAY técnico | conservar como piloto; aún no satisface G-R5 Journal-compatible |
| Módulo `quant` histórico | no apto para decisión | mantener en cuarentena; no alimenta el monitor |
| UI compatible con Trading Journal | ausente | construir en el stack del Journal durante la realineación |
| Datos demo, modelos y respaldos | ausentes | producir como evidencia fuera de Git |

## Líneas de trabajo

| Línea | Objetivo | Puerta de salida |
|---|---|---|
| `R0` Autoridad y verdad | documentación coherente y legado aislado | `G-R0` |
| `R1` Seguridad semántica | ninguna pantalla confunde sintético con real | `G-R1` |
| `R2` Composición | replay y shadow atraviesan una sola ruta | `G-R2` |
| `R3` Fuente demo y economía | cuenta/símbolo/costos validados y cinco sesiones | `G-R3` |
| `R4` Modelos | baseline, logística y boosting evaluados causalmente | `G-R4` |
| `R5` Interfaz Journal-compatible | UX, tokens, accesibilidad y contrato de lectura | `G-R5` |
| `R6` Shadow demo | operativas simuladas y conciliación observables | `G-R6` |
| `R7` Paquete de integración futura | módulo `/luces` trasladable sin tocar `tj.db` | `G-R7` |

Los detalles, dependencias y criterios de cada línea viven únicamente en
[`docs/PLAN-REALINEACION.md`](./docs/PLAN-REALINEACION.md).

## Condiciones de parada

- falta autorización o una decisión material está abierta;
- una fuente sintética aparece rotulada como broker/demo/real;
- una cifra de rendimiento carece de dataset, corte, muestra y método;
- OFI, microprecio o profundidad no provienen de un contrato real validado;
- aparece una capacidad de crear, modificar o cancelar órdenes;
- una fase intenta escribir en Trading Journal o abrir `tj.db`;
- una Puerta depende sólo de tests con fixtures cuando exige evidencia externa.

## Corte de diagnóstico runtime 2026-08-30

El monitor standalone ya reconstruye un event log, expone diagnóstico de transición y sólo
muestra SP500–AAPL/SP500–TSLA cuando recibe evidencia multi-activo explícita. Esto es
`PASS_TECNICO` de REPLAY, no evidencia de G-R3 ni autorización para rotular datos como demo
observados. Véase [`docs/AUDITORIA-RUNTIME-MONITOR-2026-08-30.md`](./docs/AUDITORIA-RUNTIME-MONITOR-2026-08-30.md).

## Corte Yahoo S&P 500 2026-08-30

La fuente `yahoo_finance` normaliza únicamente `^GSPC` como `US500`, usa WebSocket con REST
1m de respaldo y publica precio, OHLC, volumen, variación, timestamps, estado de mercado y
latencia. La ausencia de bid/ask y order flow se conserva como N/A, y sin modelo campeón la
luz permanece amarilla. Véase
[`docs/AUDITORIA-FUENTE-YAHOO-SP500-2026-08-30.md`](./docs/AUDITORIA-FUENTE-YAHOO-SP500-2026-08-30.md).
