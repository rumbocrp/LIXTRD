# SRS — Sistema de Luces piloto e integración futura

**Versión:** 2.4.0
**Estado:** canónico; monitor Yahoo multi-activo y REPLAY técnicos disponibles, producto demo observado bloqueado por Puertas
**Fuente:** SPEC-002, SPEC-003 y decisiones `DO-01`…`DO-10`

## 1. Objetivos

| ID | Objetivo medible |
|---|---|
| `OBJ-L01` | Probar decisiones de luz sobre US500 sin capacidad de órdenes. |
| `OBJ-L02` | Monitorear Operativas simuladas y conciliarlas con hechos de cuentas demo. |
| `OBJ-L03` | Mantener toda decisión causal, reproducible y explicable. |
| `OBJ-L04` | Presentar información honesta con la experiencia de Trading Journal. |
| `OBJ-L05` | Preparar la futura ruta `/luces` sin modificar hoy Trading Journal. |

## 2. Actores

| Actor | Responsabilidad |
|---|---|
| Operador | observa, interpreta y decide fuera del sistema |
| Dueño | aprueba requisitos, perfiles y promoción de modelos |
| Motor | procesa hechos y publica decisiones; nunca ejecuta órdenes |
| Fuente demo | entrega datos y Ejecuciones read-only |
| Interfaz | presenta Proyecciones de lectura sin inventar datos |
| Auditor | reproduce decisiones, gates y artefactos |

## 3. Requisitos funcionales

| ID | Prioridad | Requisito | Criterio de aceptación |
|---|:-:|---|---|
| `RF-L001` | M | Admitir sólo `US500` en V1. | Otro instrumento falla antes de persistir. |
| `RF-L002` | M | Ingerir Eventos bid/ask con tres relojes, secuencia y procedencia. | Un evento incompleto queda rechazado/cuarentenado con razón. |
| `RF-L003` | M | Distinguir `SINTETICO`, `REPLAY`, `SHADOW` y `DEMO_OBSERVADO`. | El estado cruza dominio→persistencia→proyección→UI sin cambiar. |
| `RF-L004` | M | Rechazar `REAL`/`LIVE`. | Parseo, configuración y persistencia devuelven error tipado. |
| `RF-L005` | M | Archivar hechos append-only e idempotentes. | Duplicado idéntico no reaplica; conflicto conserva el primero y registra diagnóstico. |
| `RF-L006` | M | Construir Casos de mercado causales S30/S60. | Eventos posteriores al Corte no cambian el caso. |
| `RF-L007` | M | Emitir Decisión de luz versionada. | Contiene luz, dirección, vigencia, utilidades, razones, salud, modelo y política. |
| `RF-L008` | M | Forzar amarillo ante falta de evidencia o degradación. | `NO_DATA`, stale, gap, reloj, disco, modelo o política inválidos impiden verde/rojo. |
| `RF-L009` | M | Aplicar histéresis. | No existe transición verde↔rojo directa en la política V1. |
| `RF-L010` | M | Reproducir el pipeline completo. | Mismo corpus+versiones produce la misma Proyección de lectura y hashes. |
| `RF-L011` | M | Ejecutar shadow por el mismo composition root. | Fuente cambia; reglas, store, modelos, política y proyección son los mismos que replay. |
| `RF-L012` | M | Crear Operativas simuladas internas. | Amarillo nunca abre simulación; no existe llamada de broker. |
| `RF-L013` | M | Importar Ejecuciones demo read-only. | Copia staged, hash, idempotencia y cuenta demo verificada. |
| `RF-L014` | M | Conciliar simulación y demo observada. | Emparejadas, parciales y no emparejadas permanecen auditables. |
| `RF-L015` | M | Publicar Proyección de lectura V1. | Un contrato único alimenta UI standalone y host de integración. |
| `RF-L016` | M | Mostrar fuente, estado, corte y edad. | Siempre visibles junto a la luz; ausencia se muestra `NO_DATA`. |
| `RF-L017` | M | Mostrar razones y transiciones. | Color nunca es el único canal y cada transición tiene causa. |
| `RF-L018` | M | Mostrar Operativas simuladas con estado y linaje. | Cada fila enlaza decisión, perfil, entrada/salida, costos y resultado o N/A. |
| `RF-L019` | M | Mostrar métricas con contexto. | Periodo, muestra, maduras/pendientes, fuente, entorno, modelo y política visibles. |
| `RF-L020` | M | Proveer estados completos de interfaz. | Cargando, vacío, parcial, error, obsoleto, conflicto y éxito tienen salida clara. |
| `RF-L021` | M | Usar sistema visual compatible con Trading Journal. | Tokens semánticos versionados, dos temas, contraste y tipografía/cifras coherentes. |
| `RF-L022` | M | Mantener UI sin reglas financieras. | Cambiar una fórmula no requiere editar componentes React. |
| `RF-L023` | M | Probar integración futura en `/luces`. | Host fixture monta el módulo bajo layout compartido sin iframe ni segunda navegación. |
| `RF-L024` | S | Evaluar depth real. | Cinco sesiones producen `ACEPTADO` o `DESCARTADO`; ausencia no bloquea bid/ask. |
| `RF-L025` | S | Comparar baseline, logística y boosting. | Misma cohorte/costos; reporte de calibración, cobertura y utilidad neta. |
| `RF-L026` | S | Registrar campeón/candidato y rollback. | Promoción humana y degradación automática a amarillo auditables. |
| `RF-L027` | M | Mostrar diagnóstico de transición del semáforo. | La misma decisión que cambia la luz publica probabilidad larga/corta, umbrales y distancia en puntos porcentuales; si falta cualquier entrada se muestra N/A. |
| `RF-L028` | M | Mostrar relaciones SP500–AAPL y SP500–TSLA sólo con evidencia explícita. | Cada relación declara precios, score, objetivo, confianza, fuente y edad; un quote aislado de US500 no crea filas multi-activo. |
| `RF-L029` | M | Observar S&P 500, TSLA, AAPL y oro desde Yahoo Finance en la misma pantalla. | La allowlist contiene exactamente `^GSPC`, `TSLA`, `AAPL`, `GC=F`; un quinto símbolo falla antes de proyectarse y `GC=F` se identifica como futuro continuo, no spot. |
| `RF-L030` | M | Mantener el monitor público activo 24/7 sin falsear actualidad. | El proceso usa WebSocket + REST 1m, reintenta hasta `Ctrl+C` y, fuera de sesión, conserva el último valor con `MERCADO CERRADO`, timestamp y edad. |
| `RF-L031` | M | Publicar procedencia y calidad de la cotización pública. | Precio/OHLC/volumen/variación visibles incluyen proveedor, símbolo, timestamp de fuente, recepción, transporte, granularidad, estado de mercado, latencia de consulta y demora no divulgada. |
| `RF-L032` | M | Mantener la fuente sustituible por order flow y brokers. | Yahoo implementa el puerto de fuente y no introduce fórmulas financieras ni dependencias del proveedor en la UI. |
| `RF-L033` | M | Actualizar el dashboard sin reemplazar la página. | El HTML carga una vez; un cliente same-origin consulta `/v1/status` y actualiza únicamente elementos declarados cada pocos segundos, sin `meta refresh`, recarga ni solicitudes solapadas. |
| `RF-L034` | M | Mantener una SPEC evolutiva de errores verificados. | Cada defecto confirmado registra evidencia, causa, invariante, regresión, estado, riesgo residual y siguiente mejora con ID inmutable. |
| `RF-L035` | M | Mantener cotizaciones independientes por activo. | `market_assets` conserva precio, procedencia, timestamp, edad y estado por símbolo; una actualización parcial fusiona una fila y no borra las demás. |
| `RF-L036` | M | Permitir diagnóstico independiente para cada activo. | Cada fila posee una barra/estado propios desde `diagnostico_semaforo`; ausencia o contrato incompleto muestra N/A y nunca hereda la barra de otro símbolo. |

## 4. Requisitos no funcionales

| ID | Requisito | Evidencia mínima |
|---|---|---|
| `RNF-L001` | Sólo loopback; UI y motor nunca escuchan en `0.0.0.0`. | Test de bind y configuración. |
| `RNF-L002` | Cero capacidad de órdenes en binario, scripts, dependencias y contratos. | Escaneo estático + prueba adversarial. |
| `RNF-L003` | Dominio independiente de Next, SQLite y cTrader. | Prueba de arquitectura/imports. |
| `RNF-L004` | Dinero, precios y cantidades exactos con escala. | Propiedades; ningún valor financiero persistido como float ambiguo. |
| `RNF-L005` | Datos ausentes permanecen ausentes. | Fixtures `None/null` → N/A/amarillo, nunca cero/default. |
| `RNF-L006` | WCAG 2.2 AA en claro/nocturno, teclado y 320 px. | Axe, contraste, reflujo, foco y reduced motion. |
| `RNF-L007` | Cifras con fuente, muestra, corte y linaje. | Guardián de contrato de presentación. |
| `RNF-L008` | Recepción→decisión p95 <100 ms y p99 <250 ms local, medido por tramo. | Benchmark con corpus sellado; red se reporta aparte. |
| `RNF-L009` | Backup online, integrity check y restore ensayado. | Restore sobre copia limpia y hash de hechos. |
| `RNF-L010` | Portabilidad macOS/Windows. | Sin comandos Unix obligatorios; rutas y runbooks por plataforma. |
| `RNF-L011` | Secrets, cuentas y rutas absolutas fuera de logs/Git. | Escaneo y revisión de artefactos. |
| `RNF-L012` | Contrato de lectura compatible hacia atrás dentro de V1. | Consumer contract del panel y del host fixture. |
| `RNF-L013` | UI de datos actuales sin caché engañosa. | Proyección declara `generated_at`, `market_cutoff` y `data_age_ms`. |
| `RNF-L014` | Menor latencia práctica sin prometer una latencia que el proveedor no garantiza. | WebSocket multi-símbolo es primario, REST paralelo es fallback; latencia/edad/timestamp se muestran por activo. |
| `RNF-L015` | Actualización incremental estable, accesible y recuperable. | Intervalos visible/oculto, timeout, exclusión mutua, backoff, una región de estado y conservación del último dato verificado están cubiertos por SPEC-003. |

## 5. Reglas de negocio

| ID | Regla |
|---|---|
| `RB-L001` | Verde significa sesgo `LARGO`; rojo `CORTO`; amarillo `MONITORIZAR`. |
| `RB-L002` | La luz es resultado de utilidad neta + salud + política, no de un score fijo. |
| `RB-L003` | Sin Modelo campeón, datos frescos, costos y política válida, la luz es amarilla. |
| `RB-L004` | Una decisión vencida no puede abrir una Operativa simulada. |
| `RB-L005` | La etiqueta madura al stop, objetivo o fin de 5 minutos; antes está pendiente. |
| `RB-L006` | LONG usa precios ejecutables ask→bid y SHORT bid→ask. |
| `RB-L007` | Un toque ambiguo se resuelve conservadoramente y conserva la causa. |
| `RB-L008` | P&L monetario sólo existe con valor por punto, contrato, cantidad y costos validados. |
| `RB-L009` | 5–10 decisiones/día es observación de cobertura, no cuota. |
| `RB-L010` | El Modelo candidato nunca asciende por accuracy aislada ni por una sola ventana. |
| `RB-L011` | Un resultado >90 % fuera de muestra abre incidente de fuga antes de promoción. |
| `RB-L012` | Datos sintéticos nunca se presentan como broker, demo observada o tiempo real. |
| `RB-L013` | Las cotizaciones Yahoo de `^GSPC`, `TSLA`, `AAPL` y `GC=F` son observaciones públicas: no crean bid/ask, microprecio, OFI, order flow, Operativas simuladas ni verde/rojo por sí solas. |
| `RB-L014` | Proceso 24/7 no significa precio 24/7: mercado cerrado conserva el último hecho real y su antigüedad. |
| `RB-L015` | Cada activo conserva su propio diagnóstico; está prohibido copiar o agregar señales entre símbolos sin una regla versionada y evidencia explícita. |

## 6. Contrato mínimo de Proyección de lectura

```text
schema_version
generated_at_utc
environment = NO_DATA | SINTETICO | REPLAY | SHADOW | DEMO_OBSERVADO
instrument = US500
session
source { name, account_hash?, health, market_cutoff, data_age_ms }
decision { light, direction, valid_until, reason_codes, utilities, safety_forced }
model { champion_id?, version?, hash?, calibration?, status }
policy { version, risk_profile_version, cost_profile_version }
transitions[]
simulations[]
metrics[] { id, value?, unit, sample, mature, pending, range, source, null_reason? }
incidents[]
diagnostico_semaforo {
  probability_long_pct, probability_short_pct,
  threshold_green_pct, threshold_red_pct,
  distance_to_green_pp, distance_to_red_pp,
  threshold_source, source_event_id
}
balancines[] {
  key, symbols, prices?, composite_score?,
  threshold_green?, threshold_red?, confidence_pct?, source_name, data_age_ms
}
market_data {
  provider = Yahoo Finance, provider_symbol = ^GSPC,
  last_price?, previous_close?, day_open?, day_high?, day_low?,
  change?, change_pct?, day_volume?, currency?, exchange?,
  source_timestamp_utc, received_at_utc, market_state,
  transport, data_granularity, quote_status, fetch_latency_ms?, source_to_receive_ms?,
  data_age_ms, connection_age_ms
}
market_assets[] {
  provider_symbol = ^GSPC | TSLA | AAPL | GC=F,
  display_name, instrument_type, quote_scope, currency, exchange,
  last_price?, previous_close?, change?, change_pct?, day_volume?,
  source_timestamp_utc, received_at_utc, market_state, transport,
  quote_status, data_age_ms, connection_age_ms,
  diagnostico_semaforo? {
    probability_long_pct, probability_short_pct,
    threshold_green_pct, threshold_red_pct, threshold_source, source_event_id
  }
}
```

Un campo desconocido es `null` con `null_reason`. La UI no completa valores faltantes.

## 7. Puertas de aceptación

| Puerta | Declara PASS sólo si |
|---|---|
| `G-R0` | documentación canónica coherente, legado aislado y autoridad verificable |
| `G-R1` | ninguna ruta pública muestra claims/datos sintéticos como reales |
| `G-R2` | replay y shadow producen proyecciones por el mismo pipeline |
| `G-R3` | fuente demo read-only, economía US500 y cinco sesiones están evidenciadas |
| `G-R4` | modelos y artefactos superan evaluación causal o queda `SIN_VENTAJA` amarillo |
| `G-R5` | UI Journal-compatible cumple contrato, estados y accesibilidad |
| `G-R6` | cinco sesiones shadow con simulaciones/conciliación y veredicto humano |
| `G-R7` | host fixture demuestra traslado a `/luces` sin tocar `tj.db` |

## 8. Exclusiones

Se aplican las exclusiones de SPEC-002. Ninguna prueba o fase puede ampliar el alcance por
inferencia.
