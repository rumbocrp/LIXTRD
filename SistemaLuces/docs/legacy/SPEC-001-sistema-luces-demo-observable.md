# [SUPERSEDIDA] SPEC-001: Sistema de Luces demo observable

Estado: APROBADO — REAUDITORÍA PASS  
Diseñador: agent-architect  
Fecha: 2026-08-29  
Entrada única de dominio: `docs/research/2026-08-29-sistema-luces-demo-independiente.md`  
Retroalimentación de auditoría: `docs/specs/REVIEW-SPEC-001.md`  
Decisión asociada: `ADR-001-producto-independiente-demo-sin-ordenes.md`

## 1 · Propósito y alcance

### 1.1 Propósito

Definir la V1 canónica de un producto local e independiente llamado **Sistema de Luces**.
El producto observa US500, conserva una historia reproducible de mercado y decisiones,
emite señales auditables con luz `GREEN|YELLOW|RED`, simula operativas internamente y
concilia operaciones realizadas manualmente en una cuenta demo. Funciona sólo en
`REPLAY`, `SHADOW` o `BROKER_DEMO_OBSERVED`.

La V1 debe poder responder, sin depender del Trading Journal:

1. qué información se conocía al crear cada caso;
2. qué modelo, calibración, política y perfil de riesgo produjeron cada señal;
3. por qué una luz apareció, cambió o fue forzada a amarillo;
4. qué habría hecho el simulador y qué ocurrió en una operación demo importada;
5. si los eventos, estados, señales, simulaciones y métricas se pueden reproducir desde
   datos y artefactos versionados.

### 1.2 Alcance incluido

- Un solo instrumento canónico: `US500`.
- Colores canónicos: `GREEN`, `YELLOW`, `RED`.
- Ventanas de características de 30 s y 60 s, cerradas por reloj de dominio; evaluación
  en cada cierre de 30 s usando sólo eventos hasta `market_event_cutoff`.
- Horizonte de operativa/etiqueta de 5 min.
- Ingestión de bid/ask; depth es una extensión opcional, inactiva hasta superar su gate.
- Modos `REPLAY`, `SHADOW`, `BROKER_DEMO_OBSERVED`.
- Archivo append-only en SQLite, proyecciones reconstruibles y exportación de auditoría.
- Simulación interna sin llamadas de escritura a un broker.
- Importación read-only de operaciones manuales de una cuenta demo y conciliación con
  señales/simulaciones.
- Modelos versionados, calibración fuera de fold, campeón/retador, abstención y rollback.
- Importación opcional, copiada e idempotente del formato
  `trading-journal/exportacion-completa-v1`.
- UI local delgada, sólo en loopback, que siempre muestra el entorno además del color.

### 1.3 Fuera de alcance

- Enviar, modificar, cancelar o cerrar órdenes, incluso en demo.
- Representar o aceptar `LIVE`; no existe como miembro del tipo `Environment`.
- Credenciales live, scopes de trading, SDKs de órdenes o endpoints de escritura del
  broker.
- Abrir `tj.db`, importar paquetes del Trading Journal o compartir proceso, migraciones,
  runtime o base de datos con él.
- XAUUSD, DXY, acciones, color azul, datos Yahoo 4 h o parámetros heredados de esos datos.
- Prometer rentabilidad, forzar 5–10 señales al día o usar esa meta como cuota.
- Ejecución monetaria mientras valor por punto, contrato, lote mínimo y costos de US500
  no estén validados.
- Depth/OFI como variable productiva antes de cinco sesiones completas y un veredicto
  explícito de calidad.
- Explicaciones generativas como fuente de verdad; los números, hashes y `reason_codes`
  versionados son el contrato auditable.
- Servicio público, multiusuario, nube o acceso fuera de loopback.

## 2 · Decisiones canónicas D-A–D-H

| ID | Cierre V1 | Consecuencia verificable |
|---|---|---|
| `D-A` | Crear un repositorio independiente `SistemaLuces`. `trading_bot` queda como prototipo de referencia y sólo se copia código probado. | Ningún import de runtime hacia `trading_bot`; historia, base, proceso y releases propios. |
| `D-B` | `US500`, `GREEN|YELLOW|RED`, ventanas 30/60 s y sesión/día de riesgo de Nueva York, con timestamps persistidos en UTC. | Configuración rechaza otro instrumento, color o ventana en V1. |
| `D-C` | Sólo `REPLAY|SHADOW|BROKER_DEMO_OBSERVED`; cuentas y fuentes conectadas deben probar `demo=true`. | `LIVE` falla en parseo antes de persistir o iniciar una sesión. |
| `D-D` | Simulador interno más importación read-only de operaciones manuales demo. | No existe puerto, comando, clase, scope ni endpoint de órdenes. |
| `D-E` | Python 3.11 fijado, SQLite `luces.db`, motor/ML en Python y UI local delgada server-rendered. | No hay frontend Next ni dependencia runtime del Journal. |
| `D-F` | Bid/ask ejecutable; stop 5 puntos, objetivo 20 puntos, horizonte 5 min; empate conservador `STOP_FIRST`; costos y latencia observados/versionados. | Sin contrato económico completo no se abre simulación ni se calcula P&L/tamaño monetario. |
| `D-G` | Una posición, sin solape, stale a 5 s, blackout de noticias high-impact, USD 50/operación, USD 250/día/drawdown, 3 pérdidas, 10 aperturas/día, máximo de referencia 5 lotes y kill switch fail-closed. | Todo límite tiene versión, evento y prueba de borde; valores monetarios desconocidos nunca se vuelven cero. |
| `D-H` | cTrader/Open API de cuenta demo en modo read-only; depth queda en cuarentena hasta cinco sesiones válidas. | El producto continúa sólo con bid/ask si depth no supera el gate. |

Los números de D-F/D-G son perfiles provisionales versionados, no constantes ocultas. La
justificación y las alternativas rechazadas están en el ADR asociado.

## 3 · Principios de diseño

- `DM-1 · Interfaz estrecha`: el paquete raíz sólo exporta cuatro casos de uso; los puertos
  son internos y cada uno tiene un consumidor declarado.
- `DM-2 · Hechos inmutables`: cada hecho y transición se añade; nunca se reescribe un
  evento anterior.
- `DM-3 · Fail-closed`: dato stale/gapped, reloj regresivo, disco/hash/modelo inválido,
  contrato económico incompleto o riesgo excedido fuerzan amarillo e impiden nuevas
  simulaciones.
- `DM-4 · Causalidad`: una salida sólo puede leer eventos con orden lógico menor o igual a
  su `market_event_cutoff`.
- `DM-5 · Reproducibilidad`: esquemas, código, dataset, features, modelo, calibración,
  política, costos y riesgo se identifican por versión y hash.
- `DM-6 · Ausencia fiel`: un dato desconocido es `None`; cero es un valor observado.
- `DM-7 · Dinero exacto`: precios, dinero y cantidades son enteros más una escala explícita.
- `DM-8 · Independencia`: la integración entre productos es copia validada, nunca acceso a
  base, paquete o proceso ajeno.
- `DM-9 · Capacidad mínima`: el binario no contiene capacidad de escribir órdenes; una
  bandera de UI no se considera una barrera.
- `DM-10 · Observabilidad primero`: toda decisión relevante produce un evento y una
  transición correlacionables antes de actualizar su proyección.
- `DM-11 · Depth degradable`: el núcleo funciona con bid/ask; depth no puede bloquear V1.
- `DM-12 · Una sola autoridad temporal`: UTC para hechos; `America/New_York` sólo para
  sesión, calendario y reinicio de límites diarios, con DST resuelto por `zoneinfo`.

## 4 · Modelo de dominio

### 4.1 Vocabulario cerrado

```text
Instrument             = US500
Environment            = REPLAY | SHADOW | BROKER_DEMO_OBSERVED
Source                 = replay | ctrader_demo | broker_demo_import |
                         journal_import | simulator | system | operator
Light                   = GREEN | YELLOW | RED
Direction               = LONG | SHORT | MONITOR
Actor                   = system | operator | import
DecisionWindow          = S30 | S60
ReconciliationStatus    = PENDING | MATCHED | PARTIAL | UNMATCHED | INVALID
```

`LIVE` no es un estado dormido ni una opción deshabilitada: es un valor inválido. Todo
adaptador de entrada debe devolver `ENVIRONMENT_NOT_ALLOWED` si recibe esa cadena.

### 4.2 Entidades y agregados

| Concepto | Identidad | Responsabilidad | Fuente de verdad |
|---|---|---|---|
| Evento | `event_id` | Hecho inmutable con causalidad y tres relojes. | `event_log` |
| Stream de mercado | `source + instrument` | Orden, huecos, salud y corte causal. | eventos de mercado/calidad |
| Caso | `case_id` | Snapshot inmutable de variables elegibles. | `CASE_CREATED` + blob por hash |
| Señal | `signal_id` | Evaluación versionada y vigente de un caso. | eventos de señal |
| Luz | `instrument + decision_window` | Estado visible e histéresis de una política. | `LIGHT_TRANSITION` |
| Simulación | `simulation_id` | Propuesta y ciclo paper sin broker write. | eventos `SIM_*` |
| Etiqueta | `label_id/case_id` | Resultado madurado sin mirar el futuro al crear caso. | `LABEL_MATURED` |
| Modelo | `model_id + version + hash` | Artefacto inmutable candidato/campeón. | eventos de modelo + almacén de artefactos |
| Perfil de riesgo | `risk_profile_version` | Límites y unidad económica aplicables. | `RISK_PROFILE_ACTIVATED` |
| Importación | `import_id` | Copia, hash, adapter y resultado idempotente. | manifiesto + eventos de importación |
| Snapshot métrico | `metric_snapshot_id` | Agregado reproducible sobre un rango y cohorte. | `metric_snapshots` |

### 4.3 Invariantes

1. Todos los agregados pertenecen a `US500` y a un `Environment` permitido.
2. Un `event_id`, `signal_id`, `simulation_id`, `case_id` o `import_id` no cambia de
   contenido una vez persistido.
3. `received_at_utc >= occurred_at_utc` no se presupone: latencias o relojes defectuosos se
   registran; un retroceso de reloj produce `CLOCK_ROLLBACK` y fail-closed.
4. `persisted_at_utc` lo asigna el archivo de eventos dentro de la transacción de append.
5. Una señal referencia exactamente un caso y un corte de mercado persistidos.
6. Una simulación referencia exactamente una señal; una operación demo sin señal se
   conserva como `UNMATCHED`, nunca se inventa la relación.
7. `GREEN` y `RED` no transicionan directamente entre sí.
8. Una señal vencida no se reutiliza; una nueva decisión crea otro `signal_id`.
9. No se abre simulación si existe otra `OPEN_SIMULATED` para US500.
10. Sin escala/unidad/valor por punto/costos completos, cantidades monetarias y P&L son
    `None`, y la propuesta termina rechazada con `ECONOMIC_CONTRACT_INCOMPLETE`.
11. Todas las proyecciones se pueden borrar y reconstruir desde eventos y artefactos; no
    son autoridad.
12. Un evento con esquema desconocido se puede archivar en cuarentena, pero no aplicar a
    estado ni a decisiones.

## 5 · Contratos Python estrechos

### 5.1 Resultado discriminado común

Todas las operaciones que pueden fallar devuelven la unión discriminada siguiente. No se
usan excepciones como contrato de dominio; las excepciones inesperadas se traducen en el
borde del adaptador y se auditan.

```python
from dataclasses import dataclass
from typing import AsyncIterator, Generic, Literal, Protocol, TypeAlias, TypeVar

T = TypeVar("T")

@dataclass(frozen=True)
class ErrorDominio:
    codigo: Literal[
        "VALIDATION_ERROR",
        "SCHEMA_UNSUPPORTED",
        "ENVIRONMENT_NOT_ALLOWED",
        "INSTRUMENT_NOT_ALLOWED",
        "SOURCE_NOT_DEMO",
        "CAPABILITY_DENIED",
        "DUPLICATE_EVENT",
        "OUT_OF_ORDER",
        "STALE_FEED",
        "GAPPED_FEED",
        "CLOCK_ROLLBACK",
        "STORAGE_UNAVAILABLE",
        "INTEGRITY_ERROR",
        "MODEL_UNAVAILABLE",
        "ECONOMIC_CONTRACT_INCOMPLETE",
        "RISK_LIMIT_HIT",
        "SIGNAL_EXPIRED",
        "IMPORT_INVALID",
        "RECONCILIATION_FAILED",
        "NOT_FOUND",
        "INTERNAL_ERROR",
    ]
    mensaje_seguro: str
    reintentable: bool
    correlation_id: str
    detalles: dict[str, str | int | bool | None]

@dataclass(frozen=True)
class Exito(Generic[T]):
    exito: Literal[True]
    datos: T

@dataclass(frozen=True)
class Fallo:
    exito: Literal[False]
    error: ErrorDominio

Resultado: TypeAlias = Exito[T] | Fallo
```

`mensaje_seguro` y `detalles` nunca contienen tokens, secretos, rutas absolutas ni payloads
completos del broker.

### 5.2 API pública del paquete

El `__init__.py` raíz exporta exclusivamente:

```python
def ejecutar_replay(solicitud: SolicitudReplay) -> Resultado[ResumenEjecucion]: ...
def ejecutar_shadow(solicitud: SolicitudShadow) -> Resultado[ResumenEjecucion]: ...
def importar_demo_observada(
    solicitud: SolicitudImportacionDemo,
) -> Resultado[ResumenImportacion]: ...
def consultar_vista(solicitud: SolicitudConsulta) -> Resultado[VistaLectura]: ...
```

No se exportan adaptadores, repositorios, modelos concretos ni un cliente de broker. La UI
sólo consume `consultar_vista`; CLI/servicio de aplicación consumen los otros tres casos.

#### 5.2.1 DTOs públicos V1 cerrados

Cada nombre de la API pública tiene un schema `additionalProperties=false`. Los tipos son
datos inmutables; las restricciones indicadas se validan en el borde antes de abrir una
fuente o anexar un evento.

```python
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

Environment = Literal["REPLAY", "SHADOW", "BROKER_DEMO_OBSERVED"]
ReasonCode = str

@dataclass(frozen=True)
class SolicitudReplay:
    correlation_id: str
    environment: Literal["REPLAY"]
    dataset_manifest_hash: str
    range_start_utc: datetime
    range_end_utc: datetime
    clock_seed: int

@dataclass(frozen=True)
class SolicitudShadow:
    correlation_id: str
    environment: Literal["SHADOW"]
    source_profile_version: str
    capabilities_manifest_hash: str
    expected_demo_account_hash: str

@dataclass(frozen=True)
class SolicitudImportacionDemo:
    correlation_id: str
    environment: Literal["BROKER_DEMO_OBSERVED"]
    staged_copy: str
    expected_sha256: str
    adapter_version: str
    expected_demo_account_hash: str

@dataclass(frozen=True)
class SolicitudConsulta:
    correlation_id: str
    environment: Environment
    view: Literal[
        "FEED", "LIGHTS", "SIGNALS", "SIMULATIONS",
        "METRICS", "SECURITY", "TRACE", "IMPORTS",
    ]
    as_of_event_id: str | None
    cursor: str | None
    limit: int

@dataclass(frozen=True)
class ResumenEjecucion:
    run_id: str
    environment: Literal["REPLAY", "SHADOW"]
    final_event_cutoff: str | None
    accepted_event_count: int
    rejected_event_count: int
    emitted_signal_count: int
    opened_simulation_count: int
    reason_codes: tuple[ReasonCode, ...]

@dataclass(frozen=True)
class ResumenImportacion:
    import_id: str
    environment: Literal["BROKER_DEMO_OBSERVED"]
    final_event_cutoff: str | None
    accepted_count: int
    rejected_count: int
    matched_count: int
    unmatched_count: int
    reason_codes: tuple[ReasonCode, ...]

@dataclass(frozen=True)
class DocumentoVistaV1:
    schema_id: Literal[
        "sistema-luces/event-envelope-v1",
        "sistema-luces/state-transition-v1",
        "sistema-luces/signal-v1",
        "sistema-luces/simulation-v1",
        "sistema-luces/metric-snapshot-v1",
    ]
    document_hash: str
    canonical_json_utf8: bytes

@dataclass(frozen=True)
class VistaLectura:
    instrument: Literal["US500"]
    environment: Environment
    health_state: str
    data_age_ms: int | None
    light: Literal["GREEN", "YELLOW", "RED"]
    reason_codes: tuple[ReasonCode, ...]
    model_id: str | None
    model_version: str | None
    model_hash: str | None
    policy_version: str
    kill_switch_active: bool
    as_of_event_id: str | None
    next_cursor: str | None
    documents: tuple[DocumentoVistaV1, ...]
```

Contratos adicionales de los DTOs:

- `correlation_id` es UUID; todos los hashes son SHA-256 hex de 64 caracteres.
- `range_start_utc < range_end_utc`; ambos son UTC. `clock_seed` es entero
  `0..2^63-1`.
- `staged_copy` es un identificador/basename interno de staging, nunca ruta absoluta, `..`
  ni URI. Tamaño máximo aceptado: 50 MiB.
- `limit` está cerrado a `1..200`; un cursor opaco no puede cambiar `environment`, `view` o
  `as_of_event_id`.
- Conteos son enteros `>=0`; `matched_count + unmatched_count <= accepted_count`.
- `canonical_json_utf8` ya fue validado contra el `schema_id` discriminante y su hash debe
  coincidir con `document_hash`.
- Campos extra, `LIVE`, otro instrumento, fechas naive, hash inválido, conteo negativo o
  combinación incoherente devuelven `VALIDATION_ERROR`, salvo `LIVE`, que devuelve
  `ENVIRONMENT_NOT_ALLOWED`.
- WP-01 es propietario exclusivo de estos DTOs y sus schemas
  `sistema-luces/api-requests-v1`, `sistema-luces/api-results-v1` y
  `sistema-luces/view-document-v1`. Ningún adaptador puede añadir campos; un cambio exige
  schema V2.

### 5.3 Puertos internos

Las firmas siguientes son contratos, no lógica. Cada método devuelve `Resultado` y cada
evento producido se persiste antes de ser visible en una proyección.

```python
class SesionFuente(Protocol):
    def eventos(self) -> AsyncIterator[Resultado[EventoMercadoV1]]: ...
    async def cerrar(self) -> Resultado[ResumenFuente]: ...

class FuenteMercado(Protocol):
    async def abrir(self, solicitud: SolicitudFuente) -> Resultado[SesionFuente]: ...

class ArchivoEventos(Protocol):
    def anexar(self, evento: EventoV1) -> Resultado[ReciboEvento]: ...
    def anexar_lote(self, lote: LoteEventosV1) -> Resultado[ReciboLote]: ...
    def leer(self, consulta: ConsultaEventos) -> Resultado[PaginaEventos]: ...
    def verificar_integridad(self, rango: RangoEventos) -> Resultado[InformeIntegridad]: ...

class ConstructorCaso(Protocol):
    def construir(self, solicitud: SolicitudCaso) -> Resultado[CasoV1]: ...

class Etiquetador(Protocol):
    def madurar(self, solicitud: SolicitudEtiqueta) -> Resultado[EtiquetaV1]: ...

class Evaluador(Protocol):
    def evaluar(self, solicitud: SolicitudEvaluacion) -> Resultado[EvaluacionV1]: ...

class PoliticaLuces(Protocol):
    def decidir(self, solicitud: SolicitudLuz) -> Resultado[DecisionLuzV1]: ...

class SimuladorOperativa(Protocol):
    def proponer(self, solicitud: SolicitudSimulacion) -> Resultado[SimulacionV1]: ...
    def avanzar(self, solicitud: AvanceSimulacion) -> Resultado[SimulacionV1]: ...

class ImportadorDemo(Protocol):
    def importar(self, solicitud: SolicitudImportacionDemo) -> Resultado[ResumenImportacion]: ...

class RegistroAuditoria(Protocol):
    def registrar(self, entrada: EntradaAuditoriaV1) -> Resultado[ReciboAuditoria]: ...
```

#### 5.3.1 Catálogo de tipos internos y propiedad

Cada tipo referenciado por los puertos enlaza exactamente un schema de §6 o tiene un dueño
único que lo define como dataclass cerrada dentro de su WP. Los tipos internos no se
exportan desde el paquete raíz.

| Tipo | Contrato/schema exacto | Propietario |
|---|---|---|
| `SesionFuente` | protocolo §5.3; no serializable | WP-03; adapter WP-10 lo implementa sin ampliar métodos |
| `SolicitudFuente` | `source-request-v1`: correlation, environment, source profile, instrument, rango/corte | WP-01 |
| `EventoMercadoV1` | `event-envelope-v1` discriminado a `QUOTE_TICK|DEPTH_DELTA|SESSION_STATUS|HEARTBEAT` | WP-01 |
| `ResumenFuente` | `source-summary-v1`: session id, corte, recibidos/rechazados y reasons | WP-03 |
| `EventoV1` | `event-envelope-v1` | WP-01 |
| `ReciboEvento` | `event-receipt-v1`: event id, row id, persisted at, payload/chain hash, idempotent | WP-02 |
| `LoteEventosV1` | `event-batch-v1`: batch id/hash raíz y tuple de `EventoV1` | WP-01 |
| `ReciboLote` | `batch-receipt-v1`: batch id, first/last row id, accepted/rejected y reasons | WP-02 |
| `ConsultaEventos` | `event-query-v1`: range, tipos, corte, cursor y limit `1..1000` | WP-02 |
| `PaginaEventos` | `event-page-v1`: eventos, corte y cursor siguiente | WP-02 |
| `RangoEventos` | `event-range-v1`: ids/row ids inicial-final inclusivos | WP-02 |
| `InformeIntegridad` | `integrity-report-v1`: rango, conteo, root hash, violations y status | WP-02 |
| `SolicitudCaso` | `case-request-v1`: ventana, cutoff, health y feature version | WP-05 |
| `CasoV1` | payload `CASE_CREATED` de §6.3 | WP-05 |
| `SolicitudEtiqueta` | `label-request-v1`: case id, cutoff de maduración, economía y horizonte | WP-06 |
| `EtiquetaV1` | payload `LABEL_MATURED` de §6.3 + estados de §6.4 | WP-06 |
| `SolicitudEvaluacion` | `evaluation-request-v1`: case/model/calibration/cost hashes y cutoff | WP-07 |
| `EvaluacionV1` | payload `EVALUATION` de §6.3 | WP-07 |
| `SolicitudLuz` | `light-request-v1`: evaluation, feed health, policy/risk versions y cutoff | WP-08 |
| `DecisionLuzV1` | `signal-v1` + `state-transition-v1` producidos atómicamente | WP-08 |
| `SolicitudSimulacion` | `simulation-request-v1`: signal id, profiles y cutoff | WP-09 |
| `SimulacionV1` | `simulation-v1` | WP-01 schema; WP-09 ciclo |
| `AvanceSimulacion` | `simulation-advance-v1`: simulation id, market cutoff y actor | WP-09 |
| `EntradaAuditoriaV1` | `audit-entry-v1`: actor, operation, result, correlation y safe details | WP-02 |
| `ReciboAuditoria` | `audit-receipt-v1`: audit id, row id, persisted at y hash | WP-02 |

`SolicitudImportacionDemo` y `ResumenImportacion` son los DTOs públicos de §5.2.1 y no se
redefinen en WP-11. Si un WP necesita un tipo no listado, primero añade propietario y
schema en una nueva versión de esta tabla; no puede inventarlo dentro de un adaptador.

| Puerto | Único consumidor previsto |
|---|---|
| `FuenteMercado` | orquestador de `ejecutar_replay` o `ejecutar_shadow` |
| `ArchivoEventos` | orquestador transaccional y constructor de proyecciones |
| `ConstructorCaso` | pipeline de cierre 30/60 s |
| `Etiquetador` | job de maduración causal |
| `Evaluador` | pipeline de señal sobre un caso persistido |
| `PoliticaLuces` | pipeline de señal después de evaluación y salud |
| `SimuladorOperativa` | pipeline paper, nunca adaptador de broker |
| `ImportadorDemo` | caso público `importar_demo_observada` |
| `RegistroAuditoria` | bordes de aplicación y operaciones administrativas |

No se introduce un puerto `Broker`, `OrderGateway`, `ExecutionClient` ni equivalente.

## 6 · Esquemas versionados

### 6.1 Convenciones

- Identificadores de esquema: `sistema-luces/<nombre>-v1`.
- JSON canónico UTF-8, claves ordenadas, sin NaN/Infinity y con números de dominio como
  enteros; su SHA-256 produce `payload_hash`.
- Fechas: RFC 3339 UTC con sufijo `Z` y precisión de microsegundos.
- IDs: UUID textual; un importador puede mapear una identidad externa mediante una clave
  idempotente separada.
- Campos desconocidos: rechazados dentro de una versión. Campos nuevos requieren `v2` o
  una nueva variante de evento con adaptación explícita.
- `None` JSON se expresa como `null`; nunca se sustituye por `0`, `""` o `[]`.
- Escalas: cada entero económico incluye o referencia `instrument_profile_version`,
  `price_scale`, `money_scale`, `quantity_scale` y moneda cuando aplique.

### 6.2 Sobre de evento `sistema-luces/event-envelope-v1`

| Campo | Tipo | Nulable | Regla |
|---|---:|:---:|---|
| `event_id` | string UUID | no | único global |
| `event_type` | enum cerrado | no | una familia de 6.3 |
| `schema_version` | literal `1` | no | versión del payload |
| `occurred_at_utc` | datetime | no | reloj fuente/dominio |
| `received_at_utc` | datetime | no | reloj local de recepción |
| `persisted_at_utc` | datetime | no | asignado al append |
| `source` | `Source` | no | nunca `live` |
| `environment` | `Environment` | no | no puede representar LIVE |
| `source_account_id_hash` | string | sí | SHA-256 seudónimo; sólo demo |
| `instrument` | literal `US500` | no | único piloto V1 |
| `symbol_id` | string | sí | identidad del proveedor |
| `source_sequence` | integer >= 0 | sí | se conserva ausencia |
| `correlation_id` | string UUID | no | operación lógica |
| `causation_id` | string UUID | sí | evento causal anterior |
| `payload_hash` | string SHA-256 | no | JSON canónico del payload |
| `previous_hash` | string SHA-256 | sí | cadena por stream/lote |
| `payload` | objeto versionado | no | validado antes de aplicar |

### 6.3 Familias y payloads de eventos V1

| Familia | `event_type` V1 | Payload obligatorio |
|---|---|---|
| Mercado | `QUOTE_TICK` | `bid`, `ask`, `price_scale`, tamaños nulables, instante fuente, secuencia nulable; `ask >= bid` |
| Mercado | `DEPTH_DELTA` | lado, nivel/precio/tamaño observado, acción y secuencia; marcado `quarantined=true` hasta D-H gate; nunca se aproxima profundidad ausente |
| Mercado | `SESSION_STATUS` | `OPEN|CLOSED|UNKNOWN`, sesión NY y fuente |
| Mercado | `HEARTBEAT` | último sequence/tick conocido y edad de fuente |
| Calidad | `GAP_DETECTED` | secuencia inicial/final, cantidad, decisión `FORCE_YELLOW_STOP_SIM`, resolución nulable |
| Calidad | `DUPLICATE` | identidad/clave duplicada y evento retenido |
| Calidad | `OUT_OF_ORDER` | secuencia esperada/recibida y acción de cuarentena |
| Calidad | `STALE` | `data_age_ms`, umbral y acción segura |
| Calidad | `RECONNECTED` | intento, duración, último corte seguro |
| Calidad | `CLOCK_ROLLBACK` | reloj previo/nuevo, delta y acción segura |
| Calidad | `DISK_ERROR` | código seguro, operación y estado de persistencia; sin ruta absoluta |
| Caso/señal | `CASE_CREATED` | `case_id`, ventanas, `feature_snapshot_hash`, feature/version, corte, elegibilidad |
| Caso/señal | `SIGNAL_EMITTED` | documento `signal-v1` completo |
| Caso/señal | `SIGNAL_EXPIRED` | `signal_id`, vencimiento y razón |
| Caso/señal | `SIGNAL_INVALIDATED` | `signal_id`, problema de datos/modelo/política |
| Caso/señal | `LABEL_MATURED` | `label_id`, `case_id`, estado, primer toque, empate, costos y horizonte |
| Luz | `LIGHT_TRANSITION` | documento `state-transition-v1`, umbrales, confirmaciones, razones, hashes y `safety_forced` |
| Simulación | `SIM_PROPOSED` | documento `simulation-v1` en `PROPOSED` |
| Simulación | `SIM_OPENED` | estado abierto, fill simulado y corte causal |
| Simulación | `SIM_FILL` | lado, precio/costo observado o simulado y fuente |
| Simulación | `SIM_CLOSED` | resultado completo y causa de cierre |
| Simulación | `SIM_REJECTED` | límite/guardia y valores observado/permitido |
| Simulación | `SIM_CANCELLED` | actor y causa antes de apertura |
| Riesgo | `RISK_PROFILE_ACTIVATED` | versión, límites, escalas, vigencia y aprobador |
| Riesgo | `RISK_LIMIT_HIT` | límite, observado, ventana, simulaciones causales y acción |
| Riesgo | `KILL_SWITCH` | disparador, alcance, actor, estado y condiciones de recuperación |
| Modelo | `TRAINING_ATTEMPT` | hashes de dataset/código/features, splits, purga/embargo, semilla, costos y resultado |
| Modelo | `EVALUATION` | cohorte, ventanas, métricas, intervalos y muestra efectiva |
| Modelo | `PROMOTION` | campeón/retador, artefactos, aprobador, gate y motivo |
| Modelo | `ROLLBACK` | versión retirada/restaurada, incidente y aprobador |
| Modelo | `DRIFT` | detector/version, referencia, observado, severidad y acción |
| Importación | `IMPORT_ACCEPTED` | `import_id`, formato, adapter version, SHA-256, filas y origen copiado |
| Importación | `IMPORT_REJECTED` | `import_id`, formato/hash/esquema y códigos seguros |
| Conciliación | `RECONCILIATION_UPDATED` | ids externos hasheados, simulación/señal nulables, estado y diferencias |

### 6.4 Estado `sistema-luces/state-transition-v1`

```text
transition_id, aggregate_type, aggregate_id,
previous_state: str | None, next_state: str,
actor: system | operator | import,
occurred_at_utc, causation_id, correlation_id,
policy_version, reason_codes[], safety_forced
```

Transiciones permitidas:

```text
feed:
  None -> INITIALIZING
  INITIALIZING -> HEALTHY | STALE | GAPPED | STOPPED
  HEALTHY -> STALE | GAPPED | RECONNECTING | STOPPED
  STALE -> HEALTHY | GAPPED | RECONNECTING | STOPPED
  GAPPED -> RECONNECTING | STOPPED
  RECONNECTING -> HEALTHY | STALE | GAPPED | STOPPED

signal:
  None -> CANDIDATE
  CANDIDATE -> EMITTED | INVALIDATED
  EMITTED -> ACTIVE | EXPIRED | INVALIDATED
  ACTIVE -> EXPIRED | INVALIDATED
  EXPIRED -> MATURE | INVALID
  INVALIDATED -> INVALID

light:
  None -> YELLOW
  YELLOW -> YELLOW | GREEN | RED
  GREEN -> GREEN | YELLOW
  RED -> RED | YELLOW

simulation:
  None -> PROPOSED
  PROPOSED -> OPEN_SIMULATED | REJECTED | CANCELLED
  OPEN_SIMULATED -> CLOSED_SIMULATED

label:
  None -> PENDING
  PENDING -> MATURE | INVALID
```

Una transición fuera de esta tabla devuelve `VALIDATION_ERROR`, genera auditoría y no
modifica la proyección. `GREEN -> RED` y `RED -> GREEN` requieren dos eventos y un estado
intermedio `YELLOW`, incluso si se procesan dentro del mismo ciclo.

### 6.5 Señal `sistema-luces/signal-v1`

| Grupo | Campos |
|---|---|
| Identidad/tiempo | `signal_id`, `case_id`, `created_at_utc`, `valid_until_utc`, `environment` |
| Mercado | `instrument=US500`, `decision_window=S30|S60`, `market_event_cutoff`, `reference_bid`, `reference_ask`, `price_scale`, `data_age_ms` |
| Decisión | `direction=LONG|SHORT|MONITOR`, `light`, `reason_codes[]`, `health_state`, `safety_forced` |
| Estrategia/features | `strategy_id`, `strategy_version`, `feature_set_version`, `feature_snapshot_hash` |
| Modelo | `model_id`, `model_version`, `model_hash`, `calibration_version`, `policy_version` |
| Scores | `raw_score_long`, `raw_score_short`, `calibrated_probability_long`, `calibrated_probability_short` |
| Economía | `expected_value_long_net`, `expected_value_short_net`, `cost_profile_version`; los valores pueden ser `None` |
| Trazabilidad | `correlation_id`, `causation_id`, `code_hash`, `schema_version=1` |

Los scores/probabilidades se almacenan como enteros escalados `0..1_000_000`. La señal
vence 30 s después de emitirse salvo que su política versionada declare una vigencia menor;
la simulación, una vez abierta, conserva su horizonte independiente de 5 min. Una señal
amarilla siempre usa `direction=MONITOR` y no puede proponer simulación.

### 6.6 Simulación `sistema-luces/simulation-v1`

| Grupo | Campos |
|---|---|
| Identidad | `simulation_id`, `signal_id`, `environment`, `demo_account_hash` nulable |
| Estado/tiempo | `status`, `proposed_at_utc`, `opened_at_utc`, `closed_at_utc`, `horizon_end` |
| Plan | `direction`, `planned_entry`, `stop`, `target`, `risk_profile_version`, `instrument_profile_version` |
| Cantidad | `requested_quantity_simulated`, `effective_quantity_simulated`, `quantity_scale` |
| Fills | `fill_entry`, `fill_exit`, `fill_source=simulator|broker_demo_import`, `source_execution_ids[]` hasheados |
| Costos | `spread_cost`, `slippage_cost`, `commission_cost`, `carry_cost`, `money_scale`, `currency` |
| Resultado | `exit_reason=stop|target|time|manual_demo|risk_limit|invalid_data`, `gross_pnl`, `net_pnl`, `realized_r`, `mfe`, `mae` |
| Conciliación | `reconciliation_status`, `reconciliation_reason_codes[]` |
| Trazabilidad | `market_event_cutoff`, `cost_profile_version`, `correlation_id`, `causation_id`, `schema_version=1` |

`environment=BROKER_DEMO_OBSERVED` sólo aparece en registros importados/conciliados. El
simulador no muta una operación de broker ni produce un identificador de orden. Campos de
costos o resultados desconocidos quedan `None` y excluyen métricas netas.

### 6.7 Métrica `sistema-luces/metric-snapshot-v1`

Todo snapshot contiene:

```text
metric_snapshot_id, metric_name, metric_plane,
range_start_utc, range_end_utc, ny_session_date,
source, environment, instrument=US500,
strategy_version, model_version, policy_version,
raw_count, effective_sample_size,
value_int | value_ratio_scaled | histogram_int | null,
unit, scale, dimensions{}, input_event_cutoff,
dataset_hash, code_hash, computed_at_utc, schema_version=1
```

Catálogo mínimo por plano:

| Plano | Métricas V1 obligatorias |
|---|---|
| Feed | recibidos, persistidos, gaps, duplicados, fuera de orden, cobertura, edad p50/p95/p99, recepción→persistencia p50/p95/p99, recepción→luz p50/p95/p99, reconexiones |
| Señales | casos elegibles, cobertura green/red, proporción yellow por razón, señales por sesión/dirección, expiradas, invalidadas, transiciones/min, tiempo por luz |
| Predictivo | etiquetas pendientes/maduras/inválidas, precisión condicionada, Brier, log loss, error/curva de calibración, utilidad neta, muestra efectiva e intervalos |
| Robustez | siempre-yellow, regla predeclarada y logística; walk-forward; costos base/adverso/estrés; fuga, drift y estabilidad por régimen |
| Demo | abiertas/cerradas/rechazadas, win rate, P&L bruto/neto, R media/mediana, MFE/MAE, drawdown, pérdida diaria, exposición, turnover, duración y causas de cierre |
| Ejecución | señal→fill, slippage, spread, comisión/carry, conciliación simulador↔demo y fills faltantes/duplicados |
| Seguridad | límites, tiempo amarillo forzado, intentos live rechazados, kill switches, incidentes y tiempo a recuperación |
| Trazabilidad | señales reproducibles byte-a-byte e importaciones idempotentes/reconciliadas |

Una métrica no computable tiene valor `null`, `reason_code=INSUFFICIENT_OR_UNKNOWN_DATA` y
mantiene sus conteos; no se publica como cero.

### 6.8 Manifiestos complementarios

- `sistema-luces/instrument-profile-v1`: `US500`, proveedor, `symbol_id`, escala de precio,
  tamaño de punto/contrato, lote mínimo/paso/máximo, moneda, valor por punto y evidencia de
  validación. Hasta estar completo, `economic_ready=false`.
- `sistema-luces/cost-profile-v1`: spread, slippage, comisión, carry y latencia con fuente,
  distribución/escala, rango de observación y escenarios `BASE|ADVERSE|STRESS`.
- `sistema-luces/risk-profile-v1`: USD 50 por operación, USD 250 pérdida/drawdown por día
  NY, 3 pérdidas consecutivas, 10 aperturas/día, 1 posición, 5 lotes de referencia,
  blackout y reglas de kill switch.
- `sistema-luces/import-manifest-v1`: `import_id`, formato, schema/adapter version, hora,
  SHA-256 del archivo copiado, tamaño, filas aceptadas/rechazadas y hash de origen seguro.
- `sistema-luces/depth-gate-policy-v1`: `required_complete_sessions=5`,
  `minimum_event_coverage_scaled=950_000`, `minimum_sequence_continuity_scaled=999_900`,
  `maximum_unresolved_gaps=0`, `maximum_out_of_order=0`,
  `maximum_clock_rollbacks=0`, `maximum_stale_time_ratio_scaled=10_000`, validación de
  tamaños no negativos/semántica del proveedor, hash del corpus, aprobador e instante. Una
  sesión sólo cuenta si contiene `OPEN -> CLOSED`, no tiene tramo desconocido y sus métricas
  están persistidas. Falta de política, aprobación o cualquiera de los umbrales mantiene
  depth en cuarentena.
- `sistema-luces/model-gate-policy-v1`: `leakage_violations_max=0`,
  `effective_sample_size_min=500`, `brier_improvement_min_scaled=0`,
  `ece_max_scaled=100_000`, `net_utility_base_ci_lower_exclusive=0`,
  `net_utility_adverse_min=0`, `profitable_walk_forward_ratio_min_scaled=600_000`,
  `purge_required=true`, `embargo_required=true`, `out_of_fold_calibration_required=true`,
  `severe_drift_allowed=false`, hashes de cohortes/costos, aprobador e instante. El Brier se
  compara contra la mejor referencia predeclarada; la ausencia de política/aprobación o un
  solo incumplimiento impide `PROMOTION`.

## 7 · Contrato económico y de decisión

### 7.1 Precios ejecutables

- LONG simulado entra al `ask` y sale/valida stop/target al `bid`.
- SHORT simulado entra al `bid` y sale/valida stop/target al `ask`.
- Stop: 5 puntos desde el fill de entrada.
- Objetivo: 20 puntos desde el fill de entrada.
- Horizonte: 5 min desde `opened_at_utc`.
- Si un único evento atómico hace observables stop y objetivo sin orden interno resoluble,
  gana stop (`STOP_FIRST`) y se registra `AMBIGUOUS_STOP_FIRST`.
- Si hay secuencias distintas, gana el primer toque por `source_sequence`; sin secuencia,
  por `occurred_at_utc` y luego por orden de persistencia, dejando la limitación auditada.
- La latencia se toma del perfil observado. Si no existe, no se supone instantánea: la
  simulación queda rechazada por contrato económico incompleto.

### 7.2 Ejemplos manuales de contrato

Supóngase únicamente para comprobar aritmética un perfil validado con `price_scale=100`
(1 punto = 100 unidades enteras). Estos ejemplos no validan el contrato real de US500.

| Caso | Entrada ejecutable | Stop | Objetivo | Primer precio ejecutable | Resultado esperado |
|---|---:|---:|---:|---:|---|
| LONG | ask `500100` | bid `499600` | bid `502100` | bid `502100` antes del stop | `target` |
| SHORT | bid `500000` | ask `500500` | ask `498000` | ask `500500` antes del objetivo | `stop` |
| Empate | `500100` | `499600` | `502100` | tick atómico ambiguo que abarca ambos | `stop`, `AMBIGUOUS_STOP_FIRST` |
| Sin perfil | ask `500100` | desconocido | desconocido | cualquiera | `SIM_REJECTED`, todos los montos desconocidos `None` |

### 7.3 Decisión, abstención e histéresis

- Se construyen snapshots `S30` y `S60` sólo al cerrar la ventana.
- Toda luz parte en `YELLOW`; falta de salud, modelo, calibración, costos o vigencia mantiene
  `YELLOW` con razones explícitas.
- Umbrales, confirmaciones e histéresis viven en `policy_version`; no se codifican en la
  interfaz ni se cambian sin evento de activación.
- `GREEN` representa sesgo LONG elegible, `RED` sesgo SHORT elegible y `YELLOW` abstención.
- La política puede emitir `GREEN/RED` sólo si feed, modelo, datos, calendario, costos y
  riesgo están saludables. Cumplir una cuota diaria nunca es una condición.

## 8 · Riesgo, noticias y kill switch

Perfil V1 provisional `risk-us500-demo-v1`:

| Guardia | Límite/acción |
|---|---|
| Posiciones simultáneas | máximo 1 para US500 |
| Solape | toda señal adicional se persiste; su simulación se rechaza con `OVERLAPPING_POSITION` |
| Stale | quote age > 5.000 ms durante sesión abierta fuerza amarillo y bloquea aperturas |
| Riesgo por operación | máximo USD 50; requiere contrato económico validado |
| Pérdida/drawdown diaria | máximo USD 250 por día NY; activa kill switch hasta siguiente sesión y revisión |
| Racha | pausa después de 3 cierres netos perdedores consecutivos |
| Turnover | máximo 10 aperturas por día NY; no es cuota mínima |
| Cantidad | máximo de referencia 5 lotes, además del tope USD 50; sin metadatos no se calcula |
| Noticias | bloqueo 15 min antes y después de eventos high-impact de USD/índices EEUU en un calendario versionado |
| Calendario ausente/stale | amarillo y sin nuevas simulaciones en SHADOW/DEMO; replay exige snapshot de calendario, aunque esté vacío con atestación |
| Kill switch técnico | gap, reloj regresivo, disco/hash inválido, modelo ilegible, drift severo o fuente no demo |
| Recuperación | nuevo evento explícito con actor, causa resuelta, verificación de integridad y versión de política |

Los límites nuevos de stale, solape, noticias y turnover son defaults conservadores para
cerrar D-G; deben evaluarse, pero no relajarse silenciosamente. Un cambio crea
`risk-profile-v2` y exige repetición de gates.

## 9 · Persistencia y reproducibilidad

### 9.1 Autoridad y tablas

`luces.db` es propiedad exclusiva del nuevo producto. SQLite opera con foreign keys,
transacciones explícitas y WAL; un solo escritor serializa append y múltiples lectores
consumen proyecciones.

| Tabla | Mutabilidad | Contenido |
|---|---|---|
| `event_log` | append-only | sobre + payload canónico + cadena hash |
| `schema_registry` | append-only | schema id/version/hash y estado activo |
| `artifact_manifest` | append-only | datasets/features/modelos/calibradores/políticas por hash |
| `import_manifest` | append-only | copias Journal/demo y resultado idempotente |
| `audit_log` | append-only | actor, operación, resultado, correlation id y código seguro |
| `signals_view` | reconstruible | última representación por señal |
| `lights_view` | reconstruible | luz actual por ventana |
| `simulations_view` | reconstruible | ciclo y conciliación actual |
| `feed_health_view` | reconstruible | salud actual y corte seguro |
| `metric_snapshots` | append-only derivado | métricas con corte/hash; se pueden recomputar |
| `projection_checkpoint` | reconstruible | último `event_log.rowid` aplicado por proyección |

No hay `UPDATE/DELETE` sobre hechos. Corregir un error significa anexar un evento
compensatorio. Las vistas se actualizan después de que el evento causal se confirme.

### 9.2 Idempotencia, integridad y orden

- Unicidad de `event_id` y de `(source, source_sequence)` cuando hay secuencia.
- Sin secuencia, el adaptador declara una clave idempotente estable; `payload_hash` por sí
  solo no elimina ticks legítimamente iguales.
- Cada lote tiene hash raíz y cada evento puede encadenar `previous_hash` dentro del stream.
- `DUPLICATE` se audita sin volver a aplicar; `OUT_OF_ORDER` y `GAP_DETECTED` se conservan
  pero fuerzan cuarentena/amarillo hasta resolución.
- Una importación ya aceptada con igual `(format, schema_version, sha256)` devuelve éxito
  idempotente con el mismo `import_id`; mismo id con otro hash devuelve error de integridad.

### 9.3 Backup, restore y reconstrucción

- Backup consistente mediante API de backup de SQLite, seguido de SHA-256 y manifiesto.
- Gate de restore en base temporal: `integrity_check`, conteos, cadena hash y rebuild de
  todas las proyecciones antes de sustituir una copia operativa.
- Retención de eventos, artefactos y manifiestos; no se purgan hechos necesarios para
  reproducibilidad.
- La exportación de auditoría es NDJSON canónico y no se convierte en fuente primaria.

### 9.4 Frontera con Trading Journal

- Sólo se acepta una copia del formato `trading-journal/exportacion-completa-v1`.
- El importador valida formato, versión, manifiesto y hash antes de leer filas.
- El adapter versionado traduce a eventos propios; nombres de tablas externos no entran al
  dominio.
- El acceso a `tj.db`, sus migraciones o sus paquetes es un fallo de arquitectura.
- La importación es opcional: caída/cambio del Journal no impide replay, shadow, señal ni
  simulación.

## 10 · Seguridad estructural

1. `Environment` sólo tiene tres literales; los parsers, DB constraints y schemas JSON
   rechazan `LIVE`.
2. El manifest de capacidades permitido es `market_data.read`, `account_metadata.read` y
   `historical_executions.read`; cualquier scope adicional devuelve `CAPABILITY_DENIED`.
3. El arranque conectado exige metadata verificable `demo=true`; si falta, es falsa o no
   coincide con el hash configurado, no abre la fuente.
4. Secretos demo se cargan fuera de eventos/DB/logs y nunca se comparten con credenciales
   live. REPLAY no necesita secretos.
5. No se incluye SDK/módulo de trading, DTO de orden, endpoint HTTP mutante, comando CLI de
   orden ni permiso broker de escritura.
6. La UI escucha sólo en `127.0.0.1`, es read-only, presenta entorno permanente, CSP y
   `Cache-Control: no-store`; no recibe secretos.
7. Imports son archivos copiados a un staging propio, con límite de tamaño, hash, parseo
   estricto, nombre interno seguro y cuarentena. Rutas absolutas no se persisten.
8. La base del Journal y cualquier ruta que termine en `tj.db` están denegadas por pruebas
   de arquitectura y revisión de configuración.
9. Errores de disco/integridad detienen el pipeline antes de publicar una señal nueva; no
   existe modo degradado que decida sin persistencia.
10. Una prueba de distribución inspecciona dependencias, símbolos, rutas y contrato OpenAPI
    para demostrar la ausencia de capacidad de órdenes.

## 11 · Migración y reutilización del prototipo

### 11.1 Estrategia

La construcción comienza en un repositorio nuevo `SistemaLuces`. No se mueve el árbol
actual ni se importa desde él. Cada pieza candidata se copia en un commit aislado después
de tener una prueba roja contra esta SPEC; se conserva sólo si pasa el contrato V1.

Precondiciones de extracción:

- repositorio nuevo con VCS, entorno fijado y suite verde;
- BUG-1 se cierra estabilizando exclusivamente la costura de prueba: una ficha hostil en
  memoria y un estado/bloque determinista, sin red ni disco, demuestran a la vez que el
  texto crudo `<script>alert(1)</script>` no aparece y que
  `&lt;script&gt;alert(1)&lt;/script&gt;` sí aparece. Para cerrar BUG-1 no se modifican el
  escapado de producción, `_e`, `_bloque_html`, `estado_real` ni CSP. Si se conserva un
  recorrido end-to-end, usa una vela archivada determinista y una fuente `sin_red`
  inyectada;
- inventario explícito del commit/origen y hash de cada archivo copiado;
- ninguna cifra/documentación de velas 4 h se presenta como evidencia US500 tick.

### 11.2 Matriz de reutilización

| Pieza del prototipo | Decisión | Restricción V1 |
|---|---|---|
| enteros, UTC, sello/hash | copiar tras pruebas | adaptar a schemas V1 y tres relojes |
| triple barrera | adaptar | tick bid/ask, 5/20 puntos, 5 min, empate stop-first; no OHLC 4 h |
| métricas (precisión/Brier/calibración/salud) | adaptar | añadir cohortes, muestra efectiva, costos, intervalos y métricas F-10 |
| contrato de estrategia | copiar concepto | versión/hash y consumidor único; sin exportaciones muertas |
| referencias siempre-verde/moneda/tasa-base | no copiar literalmente | reemplazar por siempre-yellow, regla predeclarada y logística |
| predicciones/intentos/auditoría append-only | adaptar | SQLite/event envelope/correlation/hash |
| tablero local/CSP/no-cache | copiar patrón tras arreglar gate | sin banco sintético rotulado como operativo; entorno siempre visible |
| Yahoo/velas 4 h | no reutilizar como fuente V1 | sólo fixtures históricos claramente no operativos si hicieran falta |
| configuración XAUUSD/DXY/azul/4h | descartar | está fuera del dominio canónico |

El baseline 212/213 no se hereda como aprobación; el nuevo producto inicia en rojo y gana
sus propios gates.

### 11.3 Disposición de OPT-1..OPT-8

| OPT | Disposición V1 y prueba propietaria |
|---|---|
| `OPT-1` | **Adoptada por WP-00:** bootstrap limpio, Python fijado, lockfile, repo Git limpio y un único comando de suite reproducible. |
| `OPT-2` | **Adoptada por WP-01:** toda entrada numérica se recibe como entero escalado o `Decimal` finito y se canonicaliza a entero antes de persistir. Precio, cantidad, escala y horizontes presentes son `>0`; costos son `>=0`; ratios/probabilidades son `0..1_000_000`; `bid <= ask`; stop/target respetan dirección. NaN, Infinity, overflow, escala no positiva o valor fuera de rango devuelven `VALIDATION_ERROR` antes del append. Los perfiles de instrumento, costo, riesgo, depth y modelo usan los mismos validadores. |
| `OPT-3` | **Adoptada por WP-02:** un escritor, transacción atómica y pruebas con barrera concurrente cubren idempotencia, claves distintas, conflicto y rollback. |
| `OPT-4` | **Eliminada por diseño:** la UI no expone `/parar` ni ningún verbo mutante. `POST|PUT|PATCH|DELETE` sobre cualquier ruta devuelven 405 y no cambian proceso, estado, DB ni proyecciones. |
| `OPT-5` | **Eliminada por diseño:** BANCO y su vista no se copian. WP-14 prueba `limit <=200`, respuesta canónica <=1 MiB y consultas acotadas; una copia importada no supera 50 MiB. En el perfil de referencia fijado por WP-00, fixture de 10.000 filas responde p95 <=250 ms y <=32 MiB incrementales; import de 50 MiB es streaming, <=10 s y <=64 MiB incrementales. |
| `OPT-6` | **Adoptada por WP-02:** gana irrevocablemente el primer evento aceptado para una clave idempotente. Duplicado idéntico devuelve el recibo original y no reaplica; mismo id/clave con contenido distinto conserva el primero, devuelve `INTEGRITY_ERROR`, anexa diagnóstico correlacionado y no cambia proyección. |
| `OPT-7` | **Adoptada por WP-01/05/07:** scores finitos escalados y `case_window_end <= market_event_cutoff_time <= signal.created_at_utc < valid_until_utc`. Toda feature usa evento `<= cutoff`; violaciones se rechazan/auditan y ninguna métrica publica NaN/Infinity. |
| `OPT-8` | **Adoptada por WP-00/15:** SPEC/ADR se copian al repo nuevo con SHA-256 y procedencia; el gate registra commit, comando exacto, exit code y salida real, sin heredar el conteo histórico 212/213 como evidencia V1. |

`OPT-2`, `OPT-6` y `OPT-7` son invariantes de dominio/storage, no recomendaciones de
estilo: una violación impide persistir o aplicar el documento. `OPT-4/5` se demuestran por
ausencia en wheel/rutas y por los tests de límites; no se marcan simplemente “no aplica”.

## 12 · Criterios de aceptación verificables

- [ ] `CA-1`: Dado cualquier parser/config/schema/constraint, cuando recibe `LIVE`, devuelve
  `exito=false` con `ENVIRONMENT_NOT_ALLOWED` y no persiste ni inicia sesión.
- [ ] `CA-2`: Dado el artefacto construido, una inspección de imports, símbolos, CLI,
  endpoints, scopes y dependencias demuestra que no existe capacidad de enviar, modificar,
  cancelar o cerrar órdenes.
- [ ] `CA-3`: Dada metadata de cuenta sin `demo=true`, `ejecutar_shadow` devuelve
  `SOURCE_NOT_DEMO` antes de abrir el stream.
- [ ] `CA-4`: Dado un evento V1 válido, append y lectura conservan byte-a-byte el JSON
  canónico, tres relojes, `None`, secuencia, causalidad y hashes.
- [ ] `CA-5`: Dado el mismo evento/import dos veces, el segundo procesamiento es idempotente;
  mismo id con contenido distinto produce `INTEGRITY_ERROR`.
- [ ] `CA-6`: Dado schema desconocido, el evento queda en cuarentena y no cambia estados,
  señales, simulaciones ni métricas productivas.
- [ ] `CA-7`: Dado gap, stale > 5.000 ms, out-of-order no resuelto o clock rollback, se añade
  evento de calidad, la luz pasa/se mantiene amarilla y no abre simulación.
- [ ] `CA-8`: Dada una transición no incluida en 6.4, devuelve `VALIDATION_ERROR`; en
  particular jamás existe `GREEN -> RED` directo.
- [ ] `CA-9`: Dado un corte de mercado, el caso S30/S60 no contiene eventos posteriores y
  su snapshot se reproduce al mismo hash.
- [ ] `CA-10`: Dada una señal, todos los ids/versiones/hashes/corte, scores, probabilidades,
  expected values, reasons, salud y vigencia del schema 6.5 están presentes o `None` donde
  el contrato lo permite.
- [ ] `CA-11`: Dada una señal vencida, proponer simulación devuelve `SIGNAL_EXPIRED` y crea
  una nueva señal para una decisión posterior, nunca la reutiliza.
- [ ] `CA-12`: Dada luz amarilla o `direction=MONITOR`, no se crea `SIM_OPENED`.
- [ ] `CA-13`: Dados ticks bid/ask secuenciados, LONG usa ask al entrar/bid al salir y SHORT
  bid al entrar/ask al salir; los cuatro ejemplos de 7.2 pasan.
- [ ] `CA-14`: Dado toque ambiguo de stop/target en un evento atómico, el resultado es stop
  y contiene `AMBIGUOUS_STOP_FIRST`.
- [ ] `CA-15`: Dado contrato económico incompleto, la simulación termina `REJECTED`, no
  calcula cantidad/P&L y conserva campos desconocidos como `None`.
- [ ] `CA-16`: Dada una posición abierta, toda propuesta solapada se persiste y rechaza con
  `OVERLAPPING_POSITION`; nunca hay más de una abierta.
- [ ] `CA-17`: Los bordes de riesgo se evalúan exactamente con la matriz de §12.4; máximo
  permitido y primer valor bloqueado no quedan a elección del implementador.
- [ ] `CA-18`: Dado kill switch, ninguna nueva simulación abre hasta evento de recuperación
  con actor, resolución e integridad verificada.
- [ ] `CA-19`: Dada una operación manual demo importada, se conserva aunque no tenga señal;
  queda `UNMATCHED` y nunca se fabrica una relación o costo.
- [ ] `CA-20`: Dada una copia Journal V1 válida, se valida hash/esquema y se importa
  idempotentemente; cualquier intento de abrir `tj.db` falla una prueba de arquitectura.
- [ ] `CA-21`: Dado restore de backup, integrity check, cadena hash, conteos y todas las
  proyecciones reconstruidas coinciden antes de declarar éxito.
- [ ] `CA-22`: Cada plano métrico de 6.7 usa el catálogo, fórmula, escala, redondeo, cohorte y
  fixture esperado de §12.5; dato no computable es `null` con razón, no cero.
- [ ] `CA-23`: Dado el corpus dorado, señal objetivo y semilla fijos de §12.6, replay desde
  corte + artefactos produce el mismo documento `signal-v1` byte-a-byte o un informe de no
  reproducibilidad auditable.
- [ ] `CA-24`: La UI sólo escucha en loopback, es read-only y muestra siempre instrumento,
  entorno, salud, edad, luz, razones, modelo/política y estado de kill switch.
- [ ] `CA-25`: La matriz §12.7 aplica `depth-gate-policy-v1`; falta de política/aprobación o
  cualquier umbral fallido mantiene depth en cuarentena sin afectar bid/ask.
- [ ] `CA-26`: La matriz §12.7 aplica `model-gate-policy-v1`; ausencia de política/aprobación
  o fallo de fuga, muestra efectiva, costo, robustez o calibración impide promoción.
- [ ] `CA-27`: La meta 5–10 señales/día aparece sólo como métrica de cobertura; ninguna
  política, test o código fuerza emisiones para alcanzarla.
- [ ] `CA-28`: Una búsqueda en runtime y dependencias no encuentra imports de `trading_bot`
  ni del Trading Journal; ambos productos pueden detenerse independientemente.

### 12.1 Reglas comunes de los oráculos

- WP-00 fija reloj, locale, timezone de proceso, versión Python/SQLite, semilla y comando de
  suite. Tests de dominio usan reloj/fuente/UUID inyectados; no usan red, disco externo ni
  azar del sistema.
- Cada CA afirma `Resultado.exito`, datos o `ErrorDominio.codigo`, secuencia exacta de
  eventos/transiciones, corte final, hashes y contadores de spies de efectos prohibidos.
- Un esperado “sin cambio” compara root hash, row count y proyecciones antes/después.
- Los fixtures `FX-*` son JSON canónico versionado, se añaden rojos por el WP propietario y
  quedan inmutables por SHA-256 después del gate WP-01. Cambiarlos exige versión nueva, no
  actualizar snapshots para hacer verde una regresión.
- Toda matriz incluye el borde exacto, el primer valor inválido y un caso con campo extra.
  Un CA no pasa sólo porque “no lanzó excepción”.

### 12.2 Matriz determinista de CA-1: LIVE irrepresentable

Todos los casos usan spies `append_calls=0` y `source_open_calls=0`; ambos deben seguir en
cero. El resultado esperado es `exito=false`, código `ENVIRONMENT_NOT_ALLOWED`, y DB/root
hash sin cambio.

| Borde | Entrada fija | Oráculo adicional |
|---|---|---|
| parser `Environment` | cadena exacta `LIVE` | no construye enum/DTO |
| config loader | documento válido salvo `environment=LIVE` | no resuelve secretos ni source profile |
| JSON schema | `event-envelope-v1` con `LIVE` | rechazo antes de canonical/hash/append |
| constraint SQLite | insert de fixture transaccional con `LIVE` | constraint falla y transacción completa revierte |
| `SolicitudReplay` | payload válido salvo `LIVE` | no abre replay |
| `SolicitudShadow` | payload válido salvo `LIVE` | no consulta metadata ni abre cTrader |
| `SolicitudImportacionDemo` | payload válido salvo `LIVE` | no abre staged copy |
| `SolicitudConsulta` | payload válido salvo `LIVE` | no ejecuta query ni devuelve vista |

Además se parametrizan `live`, `Live`, ` LIVE ` y un valor desconocido. Ninguno se
normaliza a un entorno válido; `LIVE` tras trim/case fold conserva
`ENVIRONMENT_NOT_ALLOWED`, los demás desconocidos devuelven `VALIDATION_ERROR`.

### 12.3 Oráculo estructural de CA-2 y CA-28

WP-00 crea `security-policy-v1` con allowlists exactos y WP-15 lo ejecuta contra la
distribución instalada. Un scan léxico aislado no basta.

| Superficie inspeccionada | PASS exacto | FAIL inyectado obligatorio |
|---|---|---|
| wheel instalado | sólo archivos declarados y cuatro exports raíz; tests/docs no están en wheel | módulo o símbolo `place_order`, `modify_order`, `cancel_order`, `close_position` o gateway equivalente |
| AST/import graph de `src` | imports stdlib + distribuciones fijadas en allowlist | import directo/dinámico de SDK de trading, `trading_bot` o paquete Journal |
| metadatos y lockfile | cierre transitivo idéntico a allowlist revisada | dependencia transitiva no declarada o con capacidad broker write |
| exports raíz | exactamente `ejecutar_replay`, `ejecutar_shadow`, `importar_demo_observada`, `consultar_vista` | cliente/adaptador/repositorio exportado |
| tabla de rutas | sólo `GET|HEAD|OPTIONS`; toda mutación 405 | ruta place/modify/cancel/close o método mutante que cambia estado |
| registro CLI | sólo serve/query/replay/shadow/import-demo/integrity/backup/restore | comando o alias de orden/posición broker |
| manifest capabilities | conjunto exacto `{market_data.read, account_metadata.read, historical_executions.read}` | scope adicional, comodín o write |
| configuración/bytes wheel | ninguna ruta `tj.db`, repo ajeno o credencial live | literal/config que abre `tj.db` o resuelve runtime ajeno |
| independencia de proceso | replay/shadow/query arrancan con Journal ausente; extensión Journal desinstalada | import obligatorio, healthcheck o parent process Journal |

Para evitar falsos negativos, los tests de mutación añaden una dependencia transitiva fake
con `place_order`, una ruta no exportada `POST /orders`, un comando oculto y un import
dinámico; cada uno debe volver rojo CA-2. Para CA-28 inyectan respectivamente import
`trading_bot`, paquete Journal y ruta `tj.db`. Tests, fixtures y docs se excluyen sólo del
scan léxico de producción; no se excluye ningún archivo empacado ni metadata transitiva.

### 12.4 Matriz determinista de CA-17

Todos los casos presuponen contrato económico completo salvo la fila que lo niega. “Abrir”
significa evento `SIM_OPENED`; “bloquear” significa `SIM_REJECTED` o `KILL_SWITCH` según la
tabla, con `reason_code`, perfil y valores observado/permitido.

| Guardia | Permitido | Primer bloqueado/disparador |
|---|---|---|
| riesgo por operación | `0 < riesgo_usd <= 50` abre si las demás guardas pasan | `>50` rechaza; `None` rechaza por contrato incompleto |
| pérdida diaria | acumulada `<250` | acumulada `>=250` activa kill switch |
| drawdown diario | `<250` | `>=250` activa kill switch |
| racha perdedora | cierres 1 y 2 | el tercer cierre neto perdedor pausa antes de otra apertura |
| aperturas por día NY | aperturas 1..10 | propuesta 11 se rechaza |
| cantidad | `0 < lotes <=5` si economía completa y riesgo <=50 | `>5`, `<=0` o `None` rechaza |
| posición simultánea | 0 abiertas permite propuesta | 1 abierta rechaza toda propuesta solapada |
| blackout `[inicio, fin]` | instante `<inicio` o `>fin` | `inicio <= instante <= fin`, incluidos ambos extremos |
| stale | edad `<=5_000 ms` | `>5_000 ms` fuerza amarillo y rechaza |

El reinicio diario ocurre exactamente a medianoche `America/New_York` resuelta por
`zoneinfo`; el fixture cubre día normal y cambio DST. Un kill switch no se limpia por el
reinicio si su causa técnica continúa.

### 12.5 Oráculo y catálogo de CA-22

Reglas universales: ratios usan escala `1_000_000` y redondeo half-even; dinero, tiempo,
precio y R usan la escala declarada sin float; percentil p usa nearest-rank
`x[ceil(p*n)]` sobre valores ordenados; denominador cero devuelve `null` con
`INSUFFICIENT_OR_UNKNOWN_DATA`. La cohorte es siempre la intersección exacta de rango UTC,
sesión NY, fuente, entorno, US500 y versiones declaradas. `raw_count` cuenta candidatos
antes de excluir unknowns; `effective_sample_size` cuenta observaciones realmente usadas.

| Métricas de §6.7 | Fórmula/escala determinista | Fixture esperado |
|---|---|---|
| todos los conteos de feed/señal/label/demo/seguridad/import | `count(distinct event_id o aggregate_id)` según identidad del catálogo | `FX-METRIC-COUNT-v1`: 4 identidades, una repetida => `raw=5`, valor `4` |
| cobertura temporal/feed | unión de intervalos saludables / duración de sesión abierta | `FX-METRIC-RATIO-v1`: 3 de 4 unidades => `750_000` |
| cobertura green/red, yellow por razón, win rate, causas, reconciliación, trazabilidad | numerador del estado / cohorte elegible; una identidad sólo una vez por corte | `FX-METRIC-RATIO-v1`: `3/4 => 750_000` |
| edad y latencias p50/p95/p99, slippage/spread/comisión/carry, duración | nearest-rank sobre valores conocidos, conservando unidad | `FX-METRIC-LATENCY-v1`: `[10,20,30,40] => p50=20,p95=40,p99=40` |
| transiciones/minuto | transiciones no self / minutos abiertos; ratio escalado | `FX-METRIC-RATIO-v1`: 3 en 4 min => `750_000` |
| tiempo por luz/exposición | suma de intersecciones `[transition_i, transition_i+1)` con rango | `FX-METRIC-LIGHT-v1`: Y=30s,G=20s,R=10s |
| precisión condicionada | aciertos entre señales direccionales maduras / direccionales maduras | `FX-METRIC-PRED-v1`: 2 aciertos/4 => `500_000` |
| Brier | media de `(p_scaled-y_scaled)^2`, reescalada half-even | `FX-METRIC-CAL-v1`: p=.5, y=[1,0] => `250_000` |
| log loss | media Decimal de `-[y ln(p)+(1-y)ln(1-p)]`; p se limita sólo para esta fórmula a `[1,999_999]` y registra clip | `FX-METRIC-CAL-v1`: p=.5, y=[1,0] => `693_147` |
| error/curva de calibración | 10 bins fijos `[0,.1),...,[.9,1]`; ECE = suma `n_bin/n * abs(mean_p-rate)` | `FX-METRIC-CAL-v1`: único bin p=.5 con rate=.5 => ECE `0` |
| intervalos de proporción | Wilson bilateral 95 %, `z=1.959963984540054`, Decimal y half-even | `FX-METRIC-WILSON-v1`: 2/4 => `[150_039,849_961]` |
| utilidad/P&L bruto-neto | suma de valores conocidos; utilidad media = suma / muestra efectiva | `FX-METRIC-PNL-v1`: `[-100,300,-50] => suma=150, media=50` |
| R media/mediana, MFE/MAE | media half-even; mediana promedio de los dos centros si n par | `FX-METRIC-PNL-v1`: mediana de `[-100,-50,300] => -50` |
| drawdown/pérdida diaria | máximo `peak_equity_to_date - equity`; pérdida diaria `max(0,-net_sum)` | `FX-METRIC-PNL-v1`: curva `[0,-100,200,150] => drawdown=100` |
| turnover | número de `SIM_OPENED` y cantidad efectiva total, ambos publicados por separado | `FX-METRIC-COUNT-v1`: 4 aperturas => count `4` |
| muestra efectiva | filas después de madurez, purga, embargo, unknowns y dedupe causal | cada fixture declara `raw=5`, una excluida => efectivo `4` |
| robustez/referencias | aplica las mismas fórmulas predictivas/económicas por baseline, fold y escenario de costo; nunca agrega escenarios distintos | `FX-METRIC-ROBUST-v1`: cinco folds, tres positivos => ratio `600_000` |
| drift/fuga/estabilidad | valor del detector versionado; violaciones de fuga son conteo, drift/estabilidad ratio escalado | `FX-METRIC-ROBUST-v1`: 0 fugas, 1 drift severo => `0` y `1` |

WP-12 mantiene `metric-definition-v1` con una entrada por cada nombre de 6.7: nombre,
identidad contada, fórmula de esta tabla, unidad, escala, redondeo, dimensiones permitidas,
fixture y resultado exacto. El test de completitud compara conjuntos: falta o sobra una
métrica vuelve rojo CA-22. No se permite que un implementador elija otra fórmula bajo el
mismo nombre.

### 12.6 Corpus fijo de CA-23

El corpus se denomina `FX-REPLAY-GOLDEN-V1`, usa `clock_seed=20260829`, rango UTC cerrado,
secuencias contiguas y manifiestos inmutables de dataset, feature, modelo, calibración,
costos, riesgo y política. WP-01 materializa el JSON canónico mínimo; WP-05 añade el caso
objetivo y WP-07 la evaluación fake determinista. Antes de implementar replay, el test rojo
fija en bytes un único `signal_id` objetivo, su `market_event_cutoff` y SHA-256 esperado.

El test ejecuta dos veces desde DB vacía y una vez desde restore al corte; las tres salidas,
orden de eventos y root hash deben ser idénticos. No se selecciona señal al azar ni se
regenera el esperado. Una mutación de tick posterior al cutoff no cambia el hash; una
mutación anterior produce hash distinto y un informe `NON_REPRODUCIBLE_INPUT_HASH`.

### 12.7 Matrices de CA-25 y CA-26

| CA | Fixture fijo | Resultado exacto |
|---|---|---|
| 25 | política ausente o sin aprobador | depth `quarantined=true`, razón `DEPTH_POLICY_MISSING`, bid/ask sigue saludable |
| 25 | 4 sesiones perfectas | cuarentena por `DEPTH_SESSIONS_INSUFFICIENT` |
| 25 | 5 sesiones y cada valor exactamente en el umbral §6.8, con aprobación | `DEPTH_GATE_ACCEPTED`; una activación versionada permite features futuras |
| 25 | un valor una unidad bajo el mínimo o una unidad sobre el máximo | `DEPTH_GATE_REJECTED`; no cambia pipeline bid/ask |
| 26 | política ausente, incompleta o sin aprobador | no `PROMOTION`; `MODEL_POLICY_MISSING` |
| 26 | candidato exactamente en todos los umbrales inclusivos y CI base estrictamente >0 | promoción sólo si hashes/cohortes coinciden y no hay drift severo |
| 26 | fuga=1, muestra=499, ECE=100001, ratio folds=599999, CI base=0 o utilidad adversa <0 | cada mutación por separado rechaza con reason específico |
| 26 | calibración in-fold o falta purga/embargo | rechazo aunque todas las métricas numéricas pasen |

### 12.8 Oráculos para los CA restantes

| CA | Fixture/oráculo determinista |
|---|---|
| 3 | `FX-ACCOUNT-NOT-DEMO-v1`: `demo=false`, ausente y hash distinto; todos devuelven `SOURCE_NOT_DEMO`, stream sin abrir. |
| 4–6 | `FX-EVENT-V1` y variantes duplicate/conflict/schema-v2; compara bytes, recibo, row count, hash y proyección exactos. |
| 7–8 | secuencias enumeradas en §6.4 y edad `5000/5001`; cada transición/evento/rechazo tiene lista esperada fija. |
| 9–10 | `FX-REPLAY-GOLDEN-V1`; campo posterior al cutoff excluido y documento signal comparado completo, no por subconjunto. |
| 11–12 | fake clock en `valid_until-1µs`, `valid_until` y `+1µs`; yellow/MONITOR nunca produce `SIM_OPENED`. |
| 13–15 | las cuatro filas exactas §7.2, más unknown por cada campo económico; compara fill/lado/exit/reasons y todos los `None`. |
| 16 | DB con 0 y 1 simulación abierta; compara count y `OVERLAPPING_POSITION`. |
| 18 | cada causa de kill switch se activa por separado; recovery incompleto falla y recovery completo añade transición exacta. |
| 19 | import fijo con ids externos 1 matched/1 unmatched/1 duplicate; esperado `accepted=2`, `unmatched=1`, costos desconocidos `None`. |
| 20 | sólo si se incluye extensión Journal: copia V1 fija, repetida y corrupta; ausencia de extensión es `NOT_INCLUDED`, no bloqueo del core. |
| 21 | backup fijo + byte corrupto; restore válido reproduce conteos/hashes/vistas, corrupto no sustituye base operativa. |
| 24 | tabla de bind/headers/métodos/vista exacta; no-loopback falla, métodos mutantes 405 y mutación de escapador a identidad vuelve rojo BUG-1. |
| 27 | misma entrada con contador diario 0, 5, 10 y 11 señales produce idéntica decisión; sólo cambia métrica de cobertura. |

Los CA-1..28 tienen así al menos un fixture positivo, uno de borde y uno negativo. CA-20 es
el único condicional porque WP-13 es extensión opcional/post-V1; su estado se registra como
`PASS_INCLUDED` o `NOT_INCLUDED`, nunca como PASS simulado.

## 13 · Descomposición de construcción

### 13.1 Ownership y handoffs obligatorios

Un archivo tiene un solo propietario activo. Un agente no modifica archivos ajenos para
“desbloquearse”: entrega una solicitud al propietario. Cada handoff registra WP productor,
gate/commit, rutas y hashes entregados, contratos consumidos, tests verdes y pendientes; el
WP receptor confirma el mismo hash antes de editar.

| Ruta/frontera | Propietario | Handoff permitido |
|---|---|---|
| `pyproject.toml`, lockfile, config raíz, `tests/conftest.py` | WP-00 durante toda V1 | otros WPs solicitan dependencia/fixture; sólo el propietario edita y vuelve a ejecutar gate WP-00 |
| `src/sistema_luces/__init__.py` | WP-00 crea stub con cuatro nombres; WP-14 recibe ownership exclusivo | transferencia después de gate WP-00; WP-14 verifica hash y es el único editor posterior |
| `src/sistema_luces/domain/**`, `schemas/**`, fixtures dorados comunes | WP-01 | permanece congelado; un cambio incompatible vuelve a WP-01 y crea V2 |
| `migrations/**`, `storage/**`, recibos/auditoría internos | WP-02 | consumidores sólo usan `ArchivoEventos` |
| cada subpaquete productivo WP-03..WP-12 | WP indicado en “Archivos previstos” | sus `__init__.py` y tests locales pertenecen al mismo WP |
| `src/sistema_luces/imports/__init__.py` y `staging.py` | WP-11 | WP-13 sólo consume; no edita ni reexporta desde ese `__init__.py` |
| `src/sistema_luces/imports/journal_v1.py` | WP-13 opcional | no se registra en core; inclusión se hace como extensión inyectada sin editar raíz/imports init |
| `application/**` y composition root | líder application de WP-14 | recibe stub raíz de WP-00; único editor del root init |
| `ui/**` | agente UI de WP-14 | entrega API de lectura y evidencia BUG-1 al líder application; no edita composition root |
| `tests/acceptance/contracts/**` | agente contratos WP-15 | sólo salida de tests al coordinador |
| `tests/security/**` | agente seguridad WP-15 | sólo salida de tests al coordinador |
| `tests/acceptance/integration/**` | agente integración WP-15 | sólo salida de tests al coordinador |
| `docs/evidence/v1-gate.md` | un coordinador WP-15 | se escribe una sola vez después de reunir los tres resultados; ningún agente paralelo lo edita |

En ningún momento hay más de tres agentes constructores activos. El coordinador cuenta como
uno si también edita o ejecuta un WP; si sólo recibe resultados no abre una cuarta rama.

### WP-00 · Repositorio y guardas estructurales

- **Objetivo:** crear `SistemaLuces` con Python 3.11 fijado, VCS, layout, comandos de test y
  checks que prohíban LIVE, órdenes, acceso a `tj.db` e imports de repos ajenos.
- **Archivos previstos:** `pyproject.toml`, lockfile, `src/sistema_luces/__init__.py`,
  `tests/architecture/test_forbidden_capabilities.py`, `tests/conftest.py`.
- **Dependencias:** ninguna.
- **Pruebas red primero:** import raíz contiene sólo cuatro casos; fixtures prohibidos
  `LIVE`, `OrderGateway`, scope write y `tj.db` fallan antes del scaffold.
- **Gate:** suite reproducible verde en repo Git limpio; `CA-1`, esqueleto de `CA-2/28`.
- **Riesgos de colisión:** altos sobre config raíz. Mantiene ownership de config/lockfile y
  transfiere exclusivamente `src/sistema_luces/__init__.py` a WP-14 tras su gate.
- **Paralelizable:** no; bloquea a todos los demás.

### WP-01 · Resultados, vocabulario y schemas V1

- **Objetivo:** materializar tipos puros, `Resultado`, enums permitidos y validadores de los
  schemas 6.2–6.8, sin IO.
- **Archivos previstos:** `src/sistema_luces/domain/{result,error,vocabulary,api,event,state,signal,simulation,metric,manifest}.py`, `schemas/*.json`, `tests/domain/*`.
- **Dependencias:** WP-00.
- **Pruebas red primero:** matrices §12.2 y OPT-2/7: LIVE, otro instrumento, campos extra,
  NaN/Infinity/rangos/escalas, ausencia convertida a cero, orden temporal,
  canonicalización y transiciones.
- **Gate:** `CA-1`, `CA-6`, `CA-8`, validación round-trip de fixtures dorados.
- **Riesgos de colisión:** muy altos; congela contratos compartidos. Cambios posteriores
  requieren coordinación y nueva versión.
- **Paralelizable:** no dentro del WP; tras su gate habilita hasta tres ramas.

### WP-02 · Archivo SQLite e integridad

- **Objetivo:** implementar `ArchivoEventos`, migraciones propias, append atómico,
  idempotencia, hashes, backup/restore y checkpoints.
- **Archivos previstos:** `src/sistema_luces/storage/{sqlite,event_store,backup}.py`,
  `migrations/*.sql`, `tests/storage/*`.
- **Dependencias:** WP-01.
- **Pruebas red primero:** barrera concurrente y OPT-6: primer aceptado gana, duplicado
  idéntico, conflicto conserva primero, claves distintas, lote truncado, rollback, disco no
  disponible, restore y rebuild vacío.
- **Gate:** `CA-4`, `CA-5`, `CA-21`; cero UPDATE/DELETE de hechos.
- **Riesgos de colisión:** migraciones y `event.py`; dueño exclusivo de `storage/`.
- **Paralelizable:** con WP-03 y WP-04.

### WP-03 · Replay y reloj de dominio

- **Objetivo:** fuente replay determinista con pausas, reconexiones, DST NY y cortes
  controlados, sin base concreta.
- **Archivos previstos:** `src/sistema_luces/sources/{clock,replay}.py`,
  `tests/sources/test_replay_*.py`, fixtures V1.
- **Dependencias:** WP-01.
- **Pruebas red primero:** misma semilla/archivo produce mismo orden; pause/resume, gap,
  rollback y cambio DST no miran futuro.
- **Gate:** determinismo byte-a-byte y parte replay de `CA-9/23`.
- **Riesgos de colisión:** fixtures de eventos; usa su propia carpeta y no toca schemas.
- **Paralelizable:** con WP-02 y WP-04.

### WP-04 · Salud del feed y cuarentena de depth

- **Objetivo:** detectar gap/duplicate/out-of-order/stale/reconnect, proyectar estado de
  feed y recolectar evidencia de depth sin usarla en señales.
- **Archivos previstos:** `src/sistema_luces/feed/{quality,state,depth_gate}.py`,
  `tests/feed/*`.
- **Dependencias:** WP-01.
- **Pruebas red primero:** secuencias sintéticas de cada fallo, borde 5.000 ms y matriz
  depth §12.7, incluida política ausente, umbral exacto/±1 y degradación a bid/ask.
- **Gate:** `CA-7`, `CA-25` con repositorio fake.
- **Riesgos de colisión:** enum/eventos calidad; cambios se proponen a WP-01, no se editan.
- **Paralelizable:** con WP-02 y WP-03.

### WP-05 · Casos y snapshots 30/60 s

- **Objetivo:** construir casos inmutables y features causales sobre puertos fake.
- **Archivos previstos:** `src/sistema_luces/cases/{windows,builder,features}.py`,
  `tests/cases/*`.
- **Dependencias:** WP-01, WP-03, WP-04.
- **Pruebas red primero:** límites exactos de ventana, tick posterior excluido, `None`
  preservado, hash estable y feed no saludable inelegible.
- **Gate:** `CA-9` y fixtures dorados S30/S60.
- **Riesgos de colisión:** feature schema; `cases/` es propiedad exclusiva.
- **Paralelizable:** con WP-06 y WP-10 una vez cumplidas sus dependencias.

### WP-06 · Etiquetas, dataset y evaluación walk-forward

- **Objetivo:** adaptar triple barrera a ticks ejecutables, madurar etiquetas, construir
  datasets causales y evaluar referencias/modelos sin promoción implícita.
- **Archivos previstos:** `src/sistema_luces/learning/{labels,dataset,splits,metrics}.py`,
  `tests/learning/*`.
- **Dependencias:** WP-01, WP-03.
- **Pruebas red primero:** LONG/SHORT bid/ask, no mirar entrada/futuro, empate stop-first,
  pendiente/inválida, purga/embargo y calibración fuera de fold.
- **Gate:** `CA-13`, `CA-14`, `CA-26` para etiquetado/dataset.
- **Riesgos de colisión:** aritmética económica compartida; consume profiles, no los edita.
- **Paralelizable:** con WP-05 y WP-10.

### WP-07 · Registro de modelos y evaluador

- **Objetivo:** artefactos por hash, referencias, evaluador, campeón/retador,
  promoción/rollback y drift fail-closed.
- **Archivos previstos:** `src/sistema_luces/models/{registry,baselines,evaluator,promotion,drift}.py`, `tests/models/*`.
- **Dependencias:** WP-05, WP-06.
- **Pruebas red primero:** matriz modelo §12.7: política/aprobación ausente, cada umbral
  exacto/±1, artefacto/hash ilegible, calibrador in-fold, baselines, drift y rollback.
- **Gate:** `CA-10`, `CA-22`, `CA-26` en puertos fake.
- **Riesgos de colisión:** manifest de artefacto; este WP no cambia tipos V1.
- **Paralelizable:** con WP-11 y WP-12.

### WP-08 · Política de luces e histéresis

- **Objetivo:** aplicar salud, vigencia, evaluación y política versionada para producir
  señal/transición; abstención y amarillo seguro.
- **Archivos previstos:** `src/sistema_luces/lights/{policy,state_machine,reasons}.py`,
  `tests/lights/*`.
- **Dependencias:** WP-04, WP-05, WP-07.
- **Pruebas red primero:** estado inicial, confirms/histéresis, G↔R pasando por Y, stale,
  señal vencida, reasons y cuota diaria ignorada.
- **Gate:** `CA-8`, `CA-10`, `CA-11`, `CA-27`.
- **Riesgos de colisión:** reason codes/policy fixtures; dueño exclusivo de `lights/`.
- **Paralelizable:** con trabajo remanente de WP-11/12.

### WP-09 · Riesgo y simulador paper

- **Objetivo:** contrato económico, perfiles versionados, límites D-G y ciclo simulado sin
  ningún adaptador broker.
- **Archivos previstos:** `src/sistema_luces/simulation/{economics,risk,simulator,kill_switch}.py`, `tests/simulation/*`.
- **Dependencias:** WP-06, WP-08.
- **Pruebas red primero:** tabla 7.2, unknowns, amarillo, expiración, solape y cada borde
  USD/racha/turnover/blackout/kill switch.
- **Gate:** `CA-12`–`CA-18` y reejecución de ausencia de órdenes `CA-2`.
- **Riesgos de colisión:** perfiles económicos; archivos exclusivos y schemas congelados.
- **Paralelizable:** con WP-10/11 si ya están habilitados.

### WP-10 · Fuente cTrader demo read-only

- **Objetivo:** adaptar market data/account metadata de cTrader demo con capabilities
  allowlist y backpressure, sin importar APIs de trading.
- **Archivos previstos:** `src/sistema_luces/sources/ctrader_readonly/{client,mapper,capabilities}.py`, `tests/sources/ctrader_readonly/*`.
- **Dependencias:** WP-01, WP-04.
- **Pruebas red primero:** metadata live/ausente, scope write, reconnect, heartbeat,
  backpressure, sequence y payload corrupto usando fake server.
- **Gate:** `CA-2`, `CA-3`, compatibilidad `CA-7/25`; ninguna prueba requiere credencial.
- **Riesgos de colisión:** dependencias/config de red; agente no toca `pyproject` sin dueño
  WP-00 y revisión.
- **Paralelizable:** con WP-05 y WP-06.

### WP-11 · Importación demo y conciliación

- **Objetivo:** importar fills/operaciones manuales demo desde copia read-only, normalizar
  ids hasheados y conciliar sin inventar relaciones/costos.
- **Archivos previstos:** `src/sistema_luces/imports/{__init__,demo,staging,reconciliation}.py`,
  `tests/imports/test_demo_*.py`.
- **Dependencias:** WP-01, WP-02.
- **Pruebas red primero:** copia duplicada, hash cambiado, fill sin señal, parcial,
  duplicado, campo desconocido y cuenta no demo.
- **Gate:** `CA-5`, `CA-19`; sólo produce eventos propios.
- **Riesgos de colisión:** WP-11 posee `imports/__init__.py` y `staging.py` durante toda V1;
  WP-13 sólo consume ambos y no los edita.
- **Paralelizable:** con WP-07 y WP-12.

### WP-12 · Proyecciones, métricas y trazabilidad

- **Objetivo:** reconstruir vistas y snapshots de todos los planos F-10 con valores
  nulables, cohortes, cortes y evidencia de reproducibilidad.
- **Archivos previstos:** `src/sistema_luces/observability/{projections,metrics,trace}.py`,
  `tests/observability/*`.
- **Dependencias:** WP-01, WP-02.
- **Pruebas red primero:** completitud `metric-definition-v1`, fixtures/fórmulas §12.5,
  rebuild, checkpoint interrumpido y corpus fijo reproducible/no reproducible §12.6.
- **Gate:** `CA-21`, `CA-22`, `CA-23` sobre fixtures.
- **Riesgos de colisión:** consultas SQL/projection checkpoint; dueño exclusivo de
  `observability/`.
- **Paralelizable:** con WP-07 y WP-11.

### WP-13 · Extensión opcional/post-V1 de importación Journal

- **Objetivo:** si la distribución decide incluir esta extensión, aceptar sólo copia
  `trading-journal/exportacion-completa-v1`, validar y traducir mediante adapter versionado
  sin acceso a `tj.db`. Su ausencia es el default core V1.
- **Archivos previstos:** `src/sistema_luces/imports/journal_v1.py`,
  `tests/imports/test_journal_v1.py`, fixtures sanitizados mínimos.
- **Dependencias:** WP-02, WP-11.
- **Pruebas red primero:** schema/hash/formato inválido, idempotencia, ruta `tj.db`, tabla
  desconocida y Journal ausente.
- **Gate:** `CA-20=PASS_INCLUDED` y `CA-28` sólo para la distribución que la incluya; el
  core registra `CA-20=NOT_INCLUDED` y no carga, registra ni descubre el adapter.
- **Riesgos de colisión:** posee sólo `journal_v1.py` y su test/fixtures; no edita
  `imports/__init__.py`, raíz, composition core ni staging.
- **Paralelizable:** con WP-07/12 una vez WP-11 esté listo.

### WP-14 · Orquestación y UI local

- **Objetivo:** ensamblar los cuatro casos públicos y una UI read-only loopback que muestre
  entorno, salud, razones, versiones y kill switch.
- **Archivos previstos:** `src/sistema_luces/__init__.py`,
  `src/sistema_luces/application/{replay,shadow,import_demo,query}.py`,
  `src/sistema_luces/ui/{server,views,assets}.py`, `tests/application/*`, `tests/ui/*`.
- **Dependencias:** WP-02, WP-03, WP-04, WP-05, WP-07, WP-08, WP-09, WP-10, WP-11, WP-12.
- **Pruebas red primero:** flujos end-to-end con fakes, binding no-loopback, verbos
  mutantes, CSP/no-store, entorno ausente de pantalla y fixture hostil determinista de
  §11.1; una mutación que convierta el escapador en identidad debe volver roja la prueba.
- **Gate:** `CA-3`, `CA-24`, API raíz exacta y BUG-1 estabilizado sin modificar escapado,
  `_e`, `_bloque_html`, `estado_real` ni CSP.
- **Riesgos de colisión:** el líder application recibe ownership exclusivo del root init y
  composition root; el agente UI posee sólo `ui/**` y entrega su evidencia por handoff.
- **Paralelizable:** UI y application pueden ser dos agentes sólo si tienen archivos
  disjuntos; cuentan dentro del máximo 3.

### WP-15 · Gates integrales y evidencia de distribución

- **Objetivo:** ejecutar todos los CA, replay dorado, cinco sesiones sintéticas del gate de
  depth, backup/restore, inspección de wheel/dependencias y matriz de seguridad.
- **Archivos previstos:** `tests/acceptance/contracts/*`, `tests/security/*`,
  `tests/acceptance/integration/*`, `docs/evidence/v1-gate.md`.
- **Dependencias:** core WP-00–WP-12 y WP-14; WP-13 sólo si se incluye extensión Journal.
- **Pruebas red primero:** escenario integral inicialmente rojo que referencia `CA-1..28`.
- **Gate:** core `CA-1..19` y `CA-21..28` verdes; `CA-20=PASS_INCLUDED` si se empaca WP-13 o
  `CA-20=NOT_INCLUDED` si se omite. Suite completa verde, wheel inspeccionado y evidencia
  terminal; nunca autoriza LIVE ni órdenes.
- **Riesgos de colisión:** tres agentes poseen rutas de test disjuntas y no corrigen
  producción. Un único coordinador escribe `v1-gate.md` tras recibir sus handoffs; fallos
  vuelven al WP propietario.
- **Paralelizable:** hasta tres agentes pueden dividir contratos, seguridad e integración,
  sin editar producción.

## 14 · Grafo y oleadas de construcción

Grafo simple (`A -> B` significa que B depende de A):

```text
WP-00 -> WP-01
WP-01 -> WP-02, WP-03, WP-04
WP-03 + WP-04 -> WP-05
WP-01 + WP-03 -> WP-06
WP-01 + WP-04 -> WP-10
WP-05 + WP-06 -> WP-07
WP-01 + WP-02 -> WP-11, WP-12
WP-04 + WP-05 + WP-07 -> WP-08
WP-11 -> WP-13
WP-06 + WP-08 -> WP-09
WP-02 + WP-03 + WP-04 + WP-05 + WP-07 + WP-08 + WP-09 + WP-10 + WP-11 + WP-12 -> WP-14
WP-00..WP-12 + WP-14 -> WP-15(core)
WP-13 -> WP-15(extension CA-20 only)
```

Orden recomendado, con máximo tres agentes constructores simultáneos:

| Oleada | WPs | Agentes máx. | Motivo |
|---|---|---:|---|
| 0 | WP-00 | 1 | congela repo y guardas |
| 1 | WP-01 | 1 | congela contratos compartidos |
| 2 | WP-02, WP-03, WP-04 | 3 | storage, replay y calidad con ownership separado |
| 3 | WP-05, WP-06, WP-10 | 3 | casos, learning y fuente read-only |
| 4 | WP-07, WP-11, WP-12 | 3 | modelos, imports demo y observabilidad |
| 5 | WP-08; WP-13 opcional | 1–2 | política core; Journal puede omitirse o construirse como extensión |
| 6 | WP-09 | 1 | riesgo depende de política/etiquetado |
| 7 | WP-14 | 2 como máximo | application y UI con contrato ya estable |
| 8 | WP-15 | 3 como máximo | QA integral por ejes, sin cambios de producción |

Un WP no comienza por calendario: comienza cuando sus gates de dependencia están verdes.
Ningún agente modifica archivos de otro WP; un cambio de schema vuelve a WP-01 y crea una
versión explícita si rompe compatibilidad. Omitir WP-13 no cambia dependencias, gates ni
funciones públicas de WP-14.

## 15 · Gate para autorizar construcción

Fase 03 **no** puede iniciar WP-00 hasta que una reauditoría independiente marque PASS para
RV-1..RV-5 sobre esta revisión. D-A–D-H permanecen cerradas; este estado no declara sano el
prototipo ni autoriza adaptar su repo in-place. Después del PASS, la promoción a shadow requiere primero
WP-00–WP-09, WP-12, WP-14 y sus CA verdes. La conexión real a cTrader demo requiere además
revisión humana de scopes y metadata `demo=true`. Ningún gate de esta V1 puede autorizar
órdenes o entorno live; hacerlo exige otro producto, otra SPEC y otro ADR.
