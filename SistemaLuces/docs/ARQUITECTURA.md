# Arquitectura — motor separado, módulo visual trasladable

**Versión:** 2.3.0
**Estado:** objetivo de realineación  
**Decisiones:** ADR-002, ADR-003 y ADR-004

## 1. Principio rector

SistemaLuces tiene un solo núcleo de verdad y dos hosts de presentación posibles:

1. durante el piloto, una aplicación standalone compatible visualmente con Trading Journal;
2. en el futuro, una ruta `/luces` dentro del shell de Trading Journal.

Ambos consumen la misma Proyección de lectura. Ninguno conoce reglas financieras, SQL ni el
SDK del broker.

## 2. Diagrama de procesos

```text
          cTrader demo read-only      Yahoo multi-activo SHADOW     archivo de replay
                    │             ^GSPC/TSLA/AAPL/GC=F WS+REST              │
                    └──────────────────────┬──────────────────────────┘
                               ▼
                    Adaptadores de fuente
                               │
                               ▼
                   Normalización + archivo
                               │
                               ▼
          caso causal → modelos → política → simulación
                               │
                               ▼
                      Proyección de lectura V1
                               │
                     HTTP loopback read-only
                               │
              ┌────────────────┴────────────────┐
              ▼                                 ▼
     Panel standalone piloto          Trading Journal futuro
       Next/React/Tailwind                 ruta /luces
        puerto separado                mismo shell y origen
```

El navegador nunca habla directamente con cTrader ni con SQLite. En el piloto habla con el
panel; el servidor del panel consulta el motor. En la integración futura, el servidor del
Journal cumple el mismo papel de BFF.

## 3. Límites de proceso y datos

| Límite | SistemaLuces piloto | Trading Journal |
|---|---|---|
| proceso UI | propio, loopback | existente, intacto |
| proceso motor | Python, loopback | se consume como sidecar futuro |
| base | `luces.db` y artefactos propios | `tj.db`, nunca abierta por Luces |
| migraciones | propias | propias |
| diseño | snapshot versionado del contrato visual | fuente original |
| integración | Proyección de lectura V1 | futuro consumidor |
| datos personales | no se importan por defecto | permanecen en Journal |

La independencia es de ciclo de vida y datos. La compatibilidad es de vocabulario,
presentación y contrato.

## 4. Módulos profundos del motor

| Módulo | Oculta | Interfaz estable |
|---|---|---|
| `dominio` | vocabulario, IDs, escalas, errores y estados | tipos puros |
| `fuentes` | replay, Yahoo público transitorio y cTrader demo | `suscribir(config) -> eventos` |
| `archivo` | SQLite, idempotencia, hashes y backup | `anexar`, `reproducir`, `verificar` |
| `salud` | huecos, stale, secuencia y reloj | `evaluar(evento) -> estado` |
| `casos` | cierres S30/S60 y features causales | `actualizar(evento) -> caso?` |
| `etiquetas` | stop/objetivo/horizonte/costos | `madurar(caso, eventos) -> etiqueta` |
| `laboratorio` | datasets, purga, walk-forward y artefactos | `evaluar(candidato) -> informe` |
| `modelos` | baseline, logística, boosting y calibración | `predecir(caso) -> probabilidades` |
| `registro` | campeón, candidato, promoción y rollback | `resolver(version) -> modelo` |
| `politica` | utilidad, histéresis, vigencia y amarillo seguro | `decidir(...) -> decision` |
| `riesgo` | perfiles y límites de simulación | `evaluar(propuesta) -> resultado` |
| `simulacion` | estado paper, fills teóricos y conciliación | `avanzar(evento) -> transiciones` |
| `proyeccion` | modelos de lectura y métricas con linaje | `consultar(corte) -> vista` |

El dominio no importa framework web, SQLite ni cTrader. Los adaptadores reciben interfaces y
traducen en los bordes.

## 5. Un solo composition root

`ejecutar_replay` y `ejecutar_shadow` construyen el mismo grafo:

```text
Fuente → Salud → Archivo → Casos → Modelo → Política → Riesgo/Simulación → Proyección
```

Sólo cambia la Fuente y el Reloj. La UI consulta esa Proyección; no ejecuta modelos ni genera
precios. Un `QUOTE_TICK` de US500 sólo puede poblar cotización/microestructura disponible.
AAPL, TSLA, beta, z-score o scores compuestos requieren un `CROSS_ASSET_SNAPSHOT` explícito
con fuente y edad. El módulo histórico `quant` queda fuera de este grafo.

El test principal usa el seam más alto: un corpus entra por FuenteReplay y se aserta la
Proyección final. Una implementación que sólo cuenta eventos no satisface el seam.

### 5.1 Fuente pública transitoria Yahoo

`AdaptadorYahooSP500` mantiene `^GSPC` → `US500` como mercado primario.
`AdaptadorYahooMultiActivo` agrega una allowlist cerrada `^GSPC`, `TSLA`, `AAPL`, `GC=F`:
REST consulta los símbolos faltantes en paralelo y `AsyncWebSocket` usa una sola suscripción
multi-símbolo. El agregado emite `CROSS_ASSET_SNAPSHOT` con una colección `assets` y
procedencia por fila; `GC=F` conserva `instrument_type=FUTURE` y scope no-spot.

La Proyección combina actualizaciones parciales por símbolo sin completar ausencias ni borrar
las demás filas. `market_assets` es independiente de `balancines`: precio observado no crea
beta, z-score o relación. Cada activo puede recibir después un `diagnostico_semaforo` propio;
si no existe una fórmula/entrada verificable, su barra queda N/A. Yahoo no se adapta
a `QUOTE_TICK`: si no entrega bid/ask, permanecen N/A. Por eso tampoco crea spread,
microprecio, OFI, depth ni decisiones. El adaptador futuro de order flow o broker implementa
el mismo límite de fuente y puede producir sus eventos más ricos sin cambiar la UI.

El proceso puede ejecutarse 24/7, pero `market_state=CLOSED` conserva el último valor real y
su edad. `quote_status=PROVIDER_DELAY_UNDISCLOSED` evita afirmar tiempo real cuando el
proveedor no incluye una garantía de demora en el payload.

## 6. Contrato HTTP local

Superficie V1 de lectura:

| Método | Ruta | Resultado |
|---|---|---|
| `GET` | `/v1/status` | versión, entorno, fuente, salud y cutoffs |
| `GET` | `/v1/view` | Proyección de lectura completa |
| `GET` | `/assets/dashboard-v1.js` | actualizador incremental same-origin |
| `GET` | `/v1/transitions?after=` | transiciones append-only |
| `GET` | `/v1/simulations?after=` | operativas simuladas y conciliación |
| `GET` | `/v1/metrics?range=` | métricas con linaje |

`/v1/status` y `/v1/view` exponen también `diagnostico_semaforo` y `market_assets[]`;
`/v1/view` incluye la telemetría, `market_data` y `balancines[]` con procedencia. El HTML se construye desde la misma
instancia de `ProyectorVistas` una vez; después, el recurso externo consulta `/v1/status` y
actualiza nodos concretos cada 2 s sin reemplazar el documento. Con la pestaña oculta reduce
la frecuencia, nunca solapa solicitudes, aplica timeout/backoff y conserva el último corte
verificado si la consulta falla. CSP limita script y conexión al mismo origen.

Cada servidor recibe su proyector por construcción para impedir estado global compartido. El listener usa un
`ThreadingHTTPServer` con workers daemon, timeout por conexión y `Connection: close`: una
conexión especulativa o inactiva del navegador no puede bloquear el panel completo.

El arranque standalone acepta un event log existente mediante `--db-path` o
`SISTEMA_LUCES_DB_PATH` y reconstruye la vista completa. Sin event log ni fuente conectada
abre honestamente en `NO_DATA`; el script demostrativo es un REPLAY y permanece activo hasta
`Ctrl+C`.

`scripts/ejecutar_yahoo_sp500.py` inicia ambos adaptadores, la Proyección y el HTTP loopback
en un proceso persistente. WebSocket y REST escriben bajo un bloqueo de proyección para que cada
respuesta HTTP observe un snapshot coherente. Tres fallos REST consecutivos degradan salud,
conservan el último precio recibido y fuerzan amarillo.

No se exponen mutaciones de órdenes, conexión de cuentas ni secretos. El arranque de replay
o shadow es una operación local/CLI con configuración validada y auditada, no un botón web.

La interfaz valida `schema_version`. Una versión mayor desconocida produce estado de
conflicto, no render parcial silencioso.

## 7. Interfaz piloto y futura integración

### Piloto

- Next.js App Router, React, TypeScript y Tailwind compatibles con las versiones del Journal.
- route group `(app)` y layout equivalente para que las páginas sean trasladables.
- tokens semánticos generados desde un snapshot firmado del sistema visual del Journal.
- servidor en loopback y otro puerto que no colisione con el Journal.
- lecturas actuales con `cache: 'no-store'`; ningún KPI se cachea como si siguiera vigente.

### Integración futura

- mover componentes/páginas a la route group existente del Journal y publicar `/luces`;
- registrar navegación y textos dentro del diccionario del Journal;
- mantener el motor como servicio local;
- añadir un Route Handler/BFF read-only en el Journal para same-origin;
- conservar `tj.db` y `luces.db` separados;
- verificar consumer contract, CSP, loopback y estado cuando el motor está ausente.

La documentación oficial de Next.js confirma que las route groups organizan módulos sin
afectar la URL y permiten compartir layouts; los Server Components pueden leer datos
dinámicos con `cache: 'no-store'`. La implementación debe consultar la documentación incluida
con la versión fijada antes de escribir código.

## 8. Persistencia

`luces.db` conserva hechos append-only y proyecciones reconstruibles. Datos voluminosos y
artefactos viven fuera de Git:

```text
datos/raw/            eventos tal como llegaron
datos/normalizados/   eventos canónicos
datos/luces.db        hechos y auditoría
artefactos/modelos/   modelo, calibrador y manifiesto
importaciones/        copias staged de ejecuciones demo
respaldos/            backups verificados
```

Todo artefacto tiene SHA-256, versión de esquema, procedencia y periodo. Ninguna ruta absoluta
ni identificador de cuenta sin hash entra en logs versionados.

## 9. Modelos y política

El modelo estima probabilidades/resultados; la política decide la luz. La política incluye
costos, utilidad neta, salud, vigencia, cobertura e histéresis.

```text
modelo(caso) -> p_long, p_short
economia(probabilidades, costos) -> u_long, u_short
politica(utilidades, salud, riesgo, vigencia) -> DecisionLuz
```

Referencias: siempre amarillo, tasa base y regla simple predeclarada. Candidatos: logística
regularizada y boosting tabular. Si ninguno demuestra ventaja neta, el resultado válido es
`SIN_VENTAJA` y la pantalla permanece amarilla.

## 10. Seguridad

- allowlist exacta de capacidades read-only;
- tipo de entorno sin `LIVE`/`REAL`;
- rechazo de metadata que no demuestre cuenta demo;
- ausencia estructural de SDK/métodos/endpoints de órdenes;
- bind explícito a `127.0.0.1`;
- CSP y BFF same-origin para la UI;
- secretos sólo en entorno/almacén local, nunca en eventos o evidencia;
- degradación a amarillo por disco, fuente, reloj, modelo, contrato o esquema inválido.

## 11. Estructura objetivo

```text
SistemaLuces/
├── AGENTS.md
├── CONTEXT.md
├── docs/
├── contracts/                 esquemas de Proyección de lectura
├── src/sistema_luces/         motor Python
├── panel/                     Next/React/Tailwind standalone
├── scripts/                   operación y verificadores
├── tests/
├── datos/                     fuera de Git
├── artefactos/                fuera de Git
├── importaciones/             fuera de Git
└── respaldos/                 fuera de Git
```

La migración a esta estructura ocurre por fases; este documento no autoriza un movimiento
masivo del árbol antes de `G-R1`.
