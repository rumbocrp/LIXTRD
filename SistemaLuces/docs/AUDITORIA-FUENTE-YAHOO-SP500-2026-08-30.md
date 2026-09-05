# Auditoría — fuente Yahoo S&P 500

**Fecha:** 2026-08-30  
**Veredicto:** `PASS_INTEGRATION` para observación pública `SHADOW`  
**Puerta demo:** `G-R3 = BLOCKED_EXTERNAL`

## Alcance verificado

- símbolo solicitado: exclusivamente `^GSPC`;
- instrumento canónico: `US500`;
- fuente/entorno: `yahoo_finance` / `SHADOW`;
- transporte: WebSocket primario y REST `1m` de respaldo;
- superficie: precio, cierre anterior, apertura, máximo, mínimo, variación, volumen,
  timestamps, estado de mercado, granularidad y latencia;
- salida: Proyección V1, HTTP loopback y dashboard;
- seguridad: ninguna capacidad de orden y ningún acceso a Trading Journal.

## Evidencia externa observada

El comando opt-in:

```bash
RUN_YAHOO_INTEGRATION=1 PYTHONPATH=src .venv/bin/python -m unittest -v tests.integration.test_yahoo_sp500_real
```

obtuvo una respuesta válida de Yahoo con `^GSPC`, precio positivo, timestamp de proveedor y
estado de sesión. En el corte de auditoría, el snapshot entregó un último precio de
`7,711.76 USD`, timestamp `2026-08-28T20:37:00Z` y mercado cerrado. El valor se registra como
hecho observado en ese corte, no como constante ni expectativa futura.

La conexión `AsyncWebSocket` se estableció correctamente; al estar el mercado cerrado no
recibió mensajes durante la ventana de ocho segundos. Ese silencio es esperado y no se
rellenó con datos sintéticos.

## Evidencia automatizada

| Verificación | Resultado |
|---|---|
| REST solicita sólo `^GSPC` | PASS_CONTRACT |
| mensaje WebSocket AAPL rechazado | PASS_CONTRACT |
| bid/ask ausentes permanecen ausentes | PASS_CONTRACT |
| precios/porcentajes ingresan escalados | PASS_CONTRACT |
| Proyección conserva Yahoo, timestamp y estado | PASS_INTEGRATION |
| HTTP `/v1/view` publica `market_data` | PASS_INTEGRATION |
| UI muestra último precio, demora y mercado cerrado | PASS_INTEGRATION |
| filas SP500–AAPL/TSLA no aparecen | PASS_CONTRACT |
| consulta real opt-in | PASS_INTEGRATION |

## Latencia y semántica 24/7

La consulta REST observada respondió aproximadamente en 1.6 s durante la auditoría. No es un
SLA. Cuando abre la sesión, el WebSocket evita esperar el siguiente poll; REST se mantiene
como recuperación cada 15 s. Fuera de sesión se consulta cada 60 s para conservar salud sin
golpear innecesariamente al proveedor. Ambos intervalos son configurables.

«24/7» describe la vida del proceso y sus reintentos. La pantalla separa:

- `source_timestamp_utc`: edad del precio;
- `received_at_utc`: último dato recibido;
- `fetch_latency_ms`: duración de la consulta REST de Yahoo (no es latencia de mercado);
- `source_to_receive_ms`: diferencia fuente→recepción para mensajes WebSocket;
- `connection_age_ms`: tiempo desde la recepción local;
- `market_state`: `REGULAR` o `CLOSED`;
- `quote_status`: `PROVIDER_DELAY_UNDISCLOSED`.

## Limitaciones que permanecen

1. Yahoo/`yfinance` no son una conexión de broker ni fuente contractual de ejecución.
2. No existen bid/ask, economía del contrato, depth u order flow validados.
3. No existe modelo campeón; el diagnóstico de transición permanece N/A y la luz amarilla.
4. No se han capturado cinco sesiones demo ni conciliado Ejecuciones.
5. La continuidad depende de red, términos y disponibilidad del proveedor.

Por estas limitaciones, este PASS no promueve `G-R3`, `G-R4` ni `G-R6`.
