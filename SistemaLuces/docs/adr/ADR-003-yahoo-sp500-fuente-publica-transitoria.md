# ADR-003 — Yahoo `^GSPC` como fuente pública transitoria

**Estado:** aceptada por instrucción del dueño  
**Fecha:** 2026-08-30  
**Ámbito:** observación `SHADOW`; no modifica ADR-002 ni aprueba `G-R3`

## Contexto

El monitor necesita mostrar números reales del S&P 500, actualizar con la menor latencia
práctica y permanecer activo en terminal mientras se prepara la conexión posterior a order
flow o brokers. La integración cTrader demo sigue bloqueada por OAuth/cuenta/sesiones y no
debe fingirse con fixtures ni con otro proveedor.

Yahoo Finance entrega datos públicos para `^GSPC`, pero su disponibilidad no equivale a un
precio ejecutable de broker. Yahoo explica que la disponibilidad en tiempo real depende del
mercado y del horario; también publica una tabla de proveedores/demoras. `yfinance` declara
que es una herramienta open source no afiliada a Yahoo, orientada a investigación/uso
personal.

## Decisión

1. Incorporar `yahoo_finance` como fuente permitida sólo en entorno `SHADOW`.
2. Fijar una allowlist inmutable: `^GSPC` se normaliza como `US500`; cualquier otro símbolo
   se rechaza antes de proyectarse.
3. Usar `yfinance.AsyncWebSocket` como camino de menor latencia cuando Yahoo publica y
   `Ticker.history(period="1d", interval="1m")` como snapshot inicial/fallback.
4. Persistir precios y porcentajes como enteros escalados en el evento
   `INDEX_MARKET_SNAPSHOT`; convertirlos para presentación sólo en la Proyección.
5. Publicar proveedor, símbolo, timestamp de fuente, recepción, transporte, granularidad,
   estado de mercado, edad y latencia de consulta.
6. Rotular la demora como `PROVIDER_DELAY_UNDISCLOSED`: la aplicación no eleva la
   disponibilidad del transporte a una garantía de tiempo real.
7. No sintetizar bid/ask, spread, microprecio, OFI, depth, order flow, relaciones
   AAPL/TSLA, probabilidad del modelo ni Operativas simuladas.
8. Mantener la luz amarilla sin modelo campeón, costos y precio ejecutable.
9. Ejecutar el proceso 24/7 con reintentos; mercado cerrado conserva el último valor real y
   muestra su antigüedad en lugar de generar cambios.

## Interfaz reemplazable

Yahoo termina en el mismo evento/proyección consumido por el servidor HTTP. Un adaptador de
broker u order flow posterior puede aportar `QUOTE_TICK`, depth u otros eventos detrás del
puerto de fuente. La UI no importa `yfinance` ni conoce cómo se obtuvieron los datos.

## Alternativas descartadas

### Consultar AAPL/TSLA junto con el índice

Descartada por la instrucción de observar sólo S&P 500 y por `RF-L028`: un quote de US500 no
crea relaciones multi-activo.

### Copiar el último precio como bid y ask

Descartada porque inventaría precios ejecutables, spread cero y microestructura inexistente.

### Polling REST cada segundo como única ruta

Descartada por latencia, carga y riesgo de rate limiting. El WebSocket es primario; REST
restaura contexto y cubre periodos sin mensajes.

### Declarar «tiempo real 24/7»

Descartada: el proceso sí permanece activo 24/7, pero `^GSPC` no cambia fuera de la sesión y
la API no entrega una garantía contractual de demora.

## Consecuencias

- `yfinance` queda como dependencia exclusiva del adaptador/runtime, con importación
  perezosa para no acoplar dominio ni replay.
- El panel muestra números públicos reales y su calidad, pero `G-R3` continúa
  `BLOCKED_EXTERNAL`.
- Fallos repetidos conservan el último hecho, degradan salud y fuerzan amarillo.
- La operación debe respetar los términos del proveedor y el uso previsto de la librería.

## Verificación

- tests contractuales rechazan símbolos distintos de `^GSPC` y bid/ask ausentes;
- prueba opt-in consulta Yahoo y verifica precio/timestamp/procedencia;
- prueba HTTP confirma que la Proyección llega al panel sin crear una señal;
- `make verify` conserva el baseline offline;
- el runtime responde sólo en `127.0.0.1` y permanece hasta `Ctrl+C`.

## Referencias primarias

- [Yahoo Help — disponibilidad de datos en tiempo real](https://help.yahoo.com/kb/SLN29023.html)
- [Yahoo Help — proveedores y demoras](https://sg.help.yahoo.com/kb/SLN2310.html)
- [Yahoo Finance — `^GSPC`](https://finance.yahoo.com/quote/%5EGSPC/)
- [yfinance — repositorio y condiciones de uso](https://github.com/ranaroussi/yfinance)
- [yfinance — referencia WebSocket](https://github.com/ranaroussi/yfinance/blob/main/doc/source/reference/yfinance.websocket.rst)
