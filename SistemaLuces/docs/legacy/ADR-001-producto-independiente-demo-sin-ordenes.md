# [SUPERSEDIDA] ADR-001: Producto independiente demo sin órdenes

Estado: ACEPTADO  
Fecha: 2026-08-29  
Decisor: agent-architect  
Entrada única de dominio: `docs/research/2026-08-29-sistema-luces-demo-independiente.md`  
Especificación: `docs/specs/SPEC-001-sistema-luces-demo-observable.md`

## 1 · Contexto

El prototipo `trading_bot` demuestra piezas útiles para velas OHLC de 4 h, triple barrera,
métricas, referencias, auditoría y tablero local, pero su gate F0 está rojo: 212 de 213
pruebas pasan, no hay VCS ni entorno de producto fijado y no existe ruta real de ticks,
modelo, sombra u operativa demo. También conserva decisiones incompatibles con el objetivo
actual: XAUUSD/DXY, color azul, Yahoo 4 h y fases distintas.

El Trading Journal ya es otro producto, con repo, stack, proceso y base propios. Su formato
de exportación versionado puede ser una frontera útil, pero compartir `tj.db`, runtime,
migraciones o código convertiría ambos ciclos de vida en uno solo.

La palabra “demo” es ambigua: puede significar replay, cálculo shadow, observación de una
cuenta demo o envío automático de órdenes demo. La V1 necesita evidencia operativa sin
crear una ruta que pueda saltar accidentalmente a live. Una bandera visual no elimina esa
capacidad; debe estar físicamente ausente.

La decisión debe cerrar D-A–D-H antes de construir y establecer una única interpretación
canónica.

## 2 · Decisión

Construir **Sistema de Luces** como un producto local y repositorio nuevo, independiente de
`trading_bot` y del Trading Journal. Su V1 observa exclusivamente US500 y sólo admite
`REPLAY`, `SHADOW` y `BROKER_DEMO_OBSERVED`. No contiene capacidad de enviar, modificar,
cancelar o cerrar órdenes, ni siquiera en demo; `LIVE` no forma parte del modelo de dominio
y se rechaza antes de persistir o conectar.

La arquitectura usa Python 3.11 fijado, SQLite `luces.db`, motor/ML en Python y una UI local
delgada de sólo lectura. El Journal sólo puede integrarse mediante una copia validada,
hasheada, versionada e idempotente de su exportación. La fuente conectada canónica es
cTrader/Open API de una cuenta demo con capacidades read-only.

## 3 · Cierre D-A–D-H

### D-A · Repositorio final

**Decisión:** crear un repo nuevo `SistemaLuces`. `trading_bot` es únicamente una cantera de
ideas y código probado que puede copiarse por piezas, con pruebas rojas previas y commits
aislados. No habrá imports de runtime entre ambos.

**Justificación:** la recomendación de convertir `trading_bot` estaba condicionada a una
aceptación explícita de su refactor. Esa aceptación no forma parte de la entrada. Además,
el prototipo no tiene VCS, su suite está roja y su dominio 4 h/XAUUSD no es la V1 US500.
Elegir repo nuevo evita heredar configuración, evidencia y nombres contradictorios.

**Excepción aparente:** la SPEC y este ADR se guardan en `trading_bot/docs` como artefactos
puente solicitados para Fase 02. Su ubicación documental no convierte ese árbol en el repo
final. WP-00 debe copiar ambos documentos al nuevo repo conservando hash y procedencia.

### D-B · Alcance canónico

**Decisión:** US500; luces `GREEN|YELLOW|RED`; features en ventanas cerradas de 30 s y 60 s;
evaluación al cierre de cada bloque de 30 s; UTC para hechos y `America/New_York` para
sesión, DST y límites diarios.

**Justificación:** es el plan específico más reciente y mantiene separadas ingestión por
evento y publicación por ventana. Verde y rojo representan sesgos long/short; amarillo es
abstención o seguridad.

**Excepciones:** ninguna respecto de la recomendación del informe. Los umbrales del modelo
no se fijan en el ADR: pertenecen a una política versionada, validada fuera de muestra.

### D-C · Entorno

**Decisión:** los únicos valores válidos son `REPLAY`, `SHADOW` y
`BROKER_DEMO_OBSERVED`. Una fuente conectada debe probar `demo=true`; no se aceptan secretos
ni metadata live.

**Justificación:** un enum y constraints sin `LIVE`, sumados a un allowlist de capacidades
read-only, convierten el rechazo en propiedad estructural, no en preferencia de operador.

**Excepciones:** ninguna. Observar datos de una cuenta live, aunque fuera “sólo lectura”, se
rechaza en V1 porque comparte una ruta de autenticación con el entorno prohibido.

### D-D · Semántica de demo

**Decisión:** “demo” significa simulación interna más ingestión read-only de operaciones
realizadas manualmente en una cuenta demo. `BROKER_DEMO_OBSERVED` describe observación y
conciliación, no ejecución iniciada por el sistema.

**Justificación:** conserva evidencia de fills, costos y conducta del operador sin crear un
gateway de órdenes. Las operaciones sin señal se conservan como `UNMATCHED`, evitando sesgo
por descartar decisiones manuales.

**Excepciones:** ninguna. Enviar órdenes a una cuenta demo no es una fase oculta de esta V1;
requeriría otro alcance, threat model, SPEC y ADR.

### D-E · Stack

**Decisión:** Python 3.11 fijado, SQLite y UI local delgada server-rendered sobre loopback.
El stack ML vive en Python y toda dependencia se fija en lockfile. No se crea un segundo
frontend Next ni se reutiliza runtime del Journal.

**Justificación:** el núcleo reutilizable y el trabajo de datos/ML están en Python; SQLite
ofrece una autoridad local transaccional y reconstruible. Una UI delgada reduce superficie
sin confundir coherencia visual con acoplamiento técnico.

**Excepción justificada:** no se impone FastAPI como parte irreversible del dominio. Puede
ser el adaptador HTTP local si WP-00 lo fija, pero la API de aplicación permanece
independiente del framework. Esto evita que una dependencia aún no instalada se convierta
en contrato público.

### D-F · Contrato económico

**Decisión:** precios ejecutables bid/ask; LONG entra ask y sale bid, SHORT entra bid y sale
ask; stop 5 puntos, objetivo 20 puntos, horizonte 5 min. Un toque atómico ambiguo se resuelve
`STOP_FIRST`. Costos, slippage, spread, comisión, carry y latencia deben provenir de perfiles
versionados con fuente. Sin valor por punto, contrato, lote mínimo o costos completos, no se
abre simulación ni se calcula tamaño/P&L monetario.

**Justificación:** la convención de lado evita valorar a mid; `STOP_FIRST` evita inflar
evidencia cuando el orden intratick es desconocido; fail-closed impide convertir datos
desconocidos en rentabilidad ficticia.

**Excepción justificada:** stop/objetivo/horizonte son parámetros provisionales del contrato
recomendado, no evidencia de rentabilidad. Cambiarlos exige versión nueva y reevaluación
walk-forward; no se sobreescriben resultados históricos.

### D-G · Límites faltantes

**Decisión:** perfil provisional V1 con:

- una sola posición US500;
- rechazo de simulaciones solapadas, aunque las señales se conservan;
- stale después de 5.000 ms en sesión abierta;
- USD 50 máximo por operación;
- USD 250 de pérdida o drawdown por día de Nueva York;
- pausa tras 3 pérdidas netas consecutivas;
- máximo 10 aperturas por día, que no es cuota mínima;
- máximo de referencia 5 lotes, subordinado al riesgo calculable;
- blackout 15 min antes/después de noticias high-impact de USD/índices EEUU;
- calendario ausente o stale, gap, reloj regresivo, disco/hash/modelo inválido, drift severo
  o fuente no demo activan amarillo/kill switch y bloquean aperturas.

**Justificación:** máximo uno elimina una política de cartera no diseñada; rechazar solape
evita doble exposición; los límites documentados 50/250/3 se preservan; stale, turnover,
blackout y recuperación cierran explícitamente los huecos antes del backtest. Todo límite se
persiste por versión y evento.

**Excepciones justificadas:** 5.000 ms, 10 aperturas y ±15 min son defaults conservadores
sin validación empírica en la entrada. Se eligen para que el sistema falle de forma segura,
no para optimizar rendimiento. Pueden cambiar sólo mediante `risk-profile-v2`, con nueva
evidencia y repetición de gates. Si el calendario no está disponible no se finge “sin
noticias”: se abstiene.

### D-H · Fuente y depth

**Decisión:** cTrader/Open API sobre cuenta demo y capacidades read-only para market data,
metadata de cuenta e histórico de ejecuciones observadas. El núcleo V1 usa bid/ask. Depth
se archiva en cuarentena y sólo entra a features después de cinco sesiones completas con
cobertura, secuencia, gaps y semántica aceptables.

**Justificación:** cTrader demo satisface la recomendación sin introducir una fuente live.
US500 es CFD OTC: depth del proveedor no representa un libro global y debe demostrar valor
y estabilidad. Si falla el gate, se descarta sin impedir V1.

**Excepción justificada:** la disponibilidad real de OAuth, scopes, `symbol_id` y calidad de
feed no fue validada por la investigación. Por ello la construcción usa fakes y no requiere
credenciales; conectar una sesión real exige revisión humana de capabilities y metadata.

## 4 · Barreras arquitectónicas obligatorias

1. El tipo `Environment`, schemas y DB constraints carecen de `LIVE`.
2. No existe interfaz `Broker`, `OrderGateway`, DTO de orden ni método place/modify/cancel/
   close; tampoco endpoint/CLI de ese tipo.
3. El manifest de capacidades contiene sólo lecturas. Cualquier scope adicional impide el
   arranque.
4. La cuenta conectada debe declarar `demo=true` y coincidir con un hash seudónimo esperado.
5. El producto no depende del Trading Journal ni de `trading_bot`; la única integración es
   una copia importada mediante adapter versionado.
6. `luces.db` es la única base del producto; abrir `tj.db` es un fallo de arquitectura.
7. Fallos de feed, reloj, persistencia, integridad, modelo, costos o riesgo producen
   amarillo y bloquean simulaciones antes de actualizar proyecciones visibles.
8. La distribución final se inspecciona para encontrar imports, símbolos, scopes,
   endpoints y dependencias prohibidos.

## 5 · Consecuencias

### Positivas

- El salto accidental de demo a live requiere introducir nueva capacidad y romper gates;
  no basta cambiar una bandera.
- Replay, shadow y demo observada comparten contratos y trazabilidad sin compartir efectos.
- Journal y Luces pueden actualizarse, detenerse, respaldarse y restaurarse por separado.
- El prototipo aporta piezas útiles sin dictar instrumento, frecuencia ni arquitectura.
- Bid/ask es suficiente para avanzar; depth puede fallar sin tumbar el producto.
- Los límites y unknowns quedan auditables y re-evaluables por versión.

### Negativas y costos aceptados

- Crear repo nuevo exige reconstruir packaging, VCS, CI local y contratos antes de copiar
  código.
- La ausencia deliberada de órdenes impide medir ejecución automática; sólo se observan
  simulador y operaciones manuales demo.
- El fail-closed puede producir muchas luces amarillas al inicio.
- SQLite con un escritor limita escala, aceptable para un producto local US500 V1.
- La importación copiada añade staging y adapters, a cambio de independencia.
- Los defaults D-G necesitarán evidencia y probablemente versiones posteriores.

## 6 · Alternativas rechazadas

### Convertir `trading_bot` in-place

Rechazada por falta de aceptación explícita, VCS y gate verde, y por riesgo de heredar
configuración 4 h/XAUUSD. Puede revisarse sólo con una nueva decisión que explique cómo
preservar historia y eliminar contradicciones.

### Alojar Luces dentro del Trading Journal

Rechazada porque compartir proceso, base o runtime acopla fallos, releases y migraciones.
La similitud visual no justifica dependencia técnica.

### Next.js compartido o segundo frontend Next en V1

Rechazada por superficie y duplicación sin necesidad funcional. La UI es un lector local
del motor Python; la coherencia se logra con tokens/especificación copiados y versionados.

### Envío automático de órdenes demo con una bandera que bloquee live

Rechazada: crea la capacidad peligrosa y reutiliza potencialmente autenticación/scopes. Un
control de UI o config no es una frontera de seguridad suficiente.

### Cuenta Standard Live read-only

Rechazada aunque sólo leyera datos: el objetivo actual es demo y esa cuenta reintroduce
metadata/secretos live en el sistema.

### Base compartida o lectura directa de `tj.db`

Rechazada: rompe independencia, idempotencia de frontera y propiedad de migraciones.

### Yahoo/OHLC 4 h como fuente operativa US500

Rechazada: prueba mecánica, no evidencia de tick, costos, latencia u order flow.

### Depth obligatorio

Rechazada porque depth del CFD OTC no equivale a libro global y aún no tiene evidencia de
cinco sesiones. Bid/ask es el fallback canónico.

### Sustituir valores desconocidos por cero

Rechazada porque fabrica costos, tamaños y P&L. La ausencia se conserva como `None` y puede
bloquear la operativa.

## 7 · Validación y reversión

La decisión se considera aplicada cuando WP-00 demuestra repo independiente y los criterios
`CA-1`, `CA-2`, `CA-3`, `CA-20` y `CA-28` de la SPEC pasan. Conectar una cuenta demo real
requiere además inspección humana de scopes, metadata y segregación de secretos.

Revisar este ADR si ocurre cualquiera de estos hechos:

- se propone enviar cualquier orden, incluso demo;
- se propone aceptar una cuenta o dato live;
- se valida que cTrader demo no ofrece el contrato read-only necesario;
- se necesita más de un instrumento, posición o proceso remoto;
- SQLite deja de satisfacer integridad/latencia local;
- se quiere convertir `trading_bot` in-place o alojar el producto en el Journal.

Esas revisiones requieren un ADR sucesor. No se “revierte” habilitando flags ocultas: se
mantiene esta V1 sin la capacidad prohibida hasta aprobar una arquitectura nueva.
