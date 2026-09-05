# CONTEXT — vocabulario del Sistema de Luces

Los términos compartidos conservan el significado del Trading Journal para que la futura
integración no requiera traducir el dominio. Los términos propios del motor se definen aquí.

## Compartidos con Trading Journal

**Cuenta de trading**  
Ámbito contable demo al que pertenece una Ejecución observada. No es una credencial ni un
cliente de broker.

**Instrumento canónico**  
Producto con identidad, escalas, contrato y moneda explícitos. El piloto admite `US500`.

**Ejecución**  
Hecho observado en una cuenta demo: cantidad, dirección, precio e Instante. Una Operativa
simulada no es una Ejecución hasta que exista un hecho del broker importado y verificado.

**Trade**  
Agrupación analítica de Ejecuciones que describe el recorrido de una posición. La simulación
mantiene su identidad propia y sólo se concilia con un Trade observado.

**Dinero**  
Importe exacto como entero con moneda y escala. Si el contrato económico está incompleto, es
`N/A`; nunca se infiere desde el precio.

**Cantidad**  
Unidades del instrumento con escala declarada. «Lotes» sólo aparece en el adaptador del
proveedor y se normaliza antes de entrar al dominio.

**Instante**  
Momento UTC con zona de origen y reloj de recepción. El día operativo usa
`America/New_York`.

**Sesión de trading**  
Periodo operativo configurado para observar y evaluar el sistema; no significa sesión HTTP
ni autenticación.

**Regla de riesgo**  
Límite versionado que evalúa una Operativa simulada. El motor puede rechazar una simulación,
pero nunca bloquear una acción externa del operador.

**Puerta**  
Veredicto verificable de una fase: `PASS`, `FAIL` o `BLOCKED`, con requisito, comando y
artefacto. Un conjunto de tests unitarios no sustituye una Puerta externa.

## Propios del Sistema de Luces

**Evento de mercado**  
Hecho inmutable recibido de replay, fuente pública o fuente demo read-only, con identidad, tres relojes,
secuencia, payload y hash.

**Corte de mercado**  
Último Evento de mercado que una decisión puede conocer. Todo dato posterior queda fuera del
caso por causalidad.

**Caso de mercado**  
Snapshot de variables construido a 30 o 60 segundos sobre un Corte de mercado. No se modifica
cuando llegan datos futuros.

**Decisión de luz**  
Resultado auditable para `LARGO`, `MONITORIZAR` o `CORTO`, con luz, utilidad, vigencia,
modelo, política, salud y razones.

**Transición de luz**  
Cambio append-only entre decisiones visibles. Verde y rojo pasan por amarillo salvo política
versionada y validada.

**Operativa simulada**  
Hipótesis interna de entrada, salida y riesgo creada desde una Decisión de luz. No abre ni
modifica una orden en el broker.

**Conciliación demo**  
Comparación read-only entre Operativas simuladas y Ejecuciones observadas. Conserva hechos no
emparejados en lugar de descartarlos.

**Fuente demo**  
Conexión read-only cuya metadata demuestra que la cuenta es demo y cuya procedencia es
auditable. Un fixture no es una Fuente demo.

**Fuente sintética**  
Generador de pruebas o laboratorio. Sus eventos llevan `SINTETICO` hasta la interfaz y jamás
se rotulan como Pepperstone, demo observada o tiempo real.

**Fuente pública transitoria**  
Proveedor sin cuenta demo ni precios ejecutables usado para probar observación `SHADOW`. En
V1 es Yahoo Finance y admite únicamente `^GSPC`, normalizado como `US500`. Declara timestamp
del proveedor, recepción, transporte, estado de mercado y demora no divulgada. No habilita
verde/rojo, bid/ask, order flow ni la Puerta de Fuente demo.

**Proceso 24/7**  
Servicio que permanece conectado y reintenta aunque la sesión del índice esté cerrada. No
significa que el precio cambie 24/7 ni que el proveedor certifique tiempo real.

**Salud de datos**  
Estado derivado de frescura, secuencia, huecos, duplicados, reloj y persistencia. La salud no
se inventa en la UI.

**Modelo campeón**  
Modelo vigente aprobado por una Puerta y por una persona autorizada. Ausencia de campeón
fuerza amarillo.

**Modelo candidato**  
Modelo evaluado contra referencias y campeón. Nunca asciende sólo por una métrica aislada.

**Proyección de lectura**  
Contrato estable que resume hechos para la interfaz. Es la única entrada de la UI y el seam
de integración futura con Trading Journal.

## Estados de procedencia

| Estado | Significado |
|---|---|
| `NO_DATA` | no existe evidencia suficiente para mostrar una decisión |
| `SINTETICO` | fixture o simulador de laboratorio |
| `REPLAY` | reproducción de eventos archivados |
| `SHADOW` | cálculo actual sin intervención ni órdenes |
| `DEMO_OBSERVADO` | hechos leídos de una cuenta demo validada |
| `REAL` | reservado para un alcance futuro; no es válido en esta versión |
