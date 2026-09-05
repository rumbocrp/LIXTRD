# ADR-004 — Cotizaciones Yahoo multi-activo en un único monitor

**Estado:** aceptada por instrucción del dueño  
**Fecha:** 2026-08-30  
**Ámbito:** observación pública `SHADOW`; no amplía el motor operativo US500 ni aprueba G-R3

## Contexto

El monitor debe conservar S&P 500, TSLA y AAPL y añadir el oro reportado por Yahoo Finance.
Los símbolos públicos seleccionados son `^GSPC`, `TSLA`, `AAPL` y `GC=F`. Yahoo identifica
`GC=F` como `FUTURE`; por tanto se muestra como futuro continuo de oro y no como XAU/USD
spot, precio ejecutable de broker ni cuenta demo observada.

El contrato anterior permitía observar sólo `^GSPC` y prohibía inventar las demás cifras a
partir del índice. La ampliación debe aportar evidencia explícita por símbolo sin convertir
cuatro cotizaciones en relaciones cuantitativas, señales o una certificación del semáforo.

## Decisión

1. Mantener un único proceso y una única pantalla loopback en el puerto predeterminado
   `8080`.
2. Consultar una allowlist cerrada de cuatro símbolos: `^GSPC`, `TSLA`, `AAPL` y `GC=F`.
3. Conservar `US500` como instrumento operativo y publicar las cuatro observaciones en un
   `CROSS_ASSET_SNAPSHOT` explícito, detrás de la Proyección de lectura.
4. Cada fila declara símbolo, nombre, tipo, moneda, precio, cierre anterior, variación,
   timestamp de fuente, recepción, estado de mercado, transporte y demora no divulgada.
5. Rotular `GC=F` como «Oro · Futuro continuo Yahoo/COMEX» y nunca como spot XAU/USD.
6. Usar `yfinance.AsyncWebSocket` para mensajes de menor latencia y REST de un minuto para
   carga inicial y recuperación; la UI actualiza sólo nodos DOM mediante `/v1/status`.
7. Rechazar símbolos fuera de la allowlist y conservar el último valor verificable si falla
   una consulta. Un fallo parcial no borra las demás filas.
8. Reservar un diagnóstico independiente para cada fila — SP500, TSLA, AAPL y oro — con
   barra, probabilidad, umbrales, razón y evento fuente propios. Un activo no hereda el
   diagnóstico de otro.
9. No sintetizar bid/ask, spread, microprecio, OFI, beta, z-score, correlación, probabilidad,
   umbrales, señal u Operativas simuladas. Cada diagnóstico permanece N/A mientras no exista
   una fórmula/entrada verificable para ese activo.
10. El proceso permanece activo 24/7; cada instrumento sólo cambia cuando Yahoo publica y
    su antigüedad permanece visible fuera de sesión.

## Alternativas descartadas

### Un proceso separado sólo para oro

Descartado por corrección explícita del dueño: SP500, TSLA y AAPL deben permanecer visibles
en la misma pantalla junto con el oro.

### Presentar `GC=F` como XAU/USD spot

Descartado porque cambia el tipo de instrumento y podría inducir a interpretar un futuro
continuo como precio spot ejecutable.

### Convertir cotizaciones en balancines o scores

Descartado porque los precios por sí solos no justifican beta, z-score, confianza, umbrales
ni una decisión verde/roja. Las relaciones cuantitativas siguen requiriendo evidencia y
contrato propios.

## Consecuencias

- la frontera operativa V1 continúa siendo US500;
- la Proyección de lectura añade una colección `market_assets` independiente de
  `balancines`, con un campo opcional `diagnostico_semaforo` por activo;
- la UI diferencia cotización observada, relación cuantitativa y señal operativa;
- Yahoo continúa siendo fuente pública transitoria y reemplazable por order flow o brokers;
- una actualización WebSocket puede modificar una sola fila sin recargar la página ni
  borrar los últimos valores válidos de las demás.

## Verificación requerida

- contrato unitario REST/WebSocket de la allowlist de cuatro símbolos;
- rechazo de un quinto símbolo y ausencia de bid/ask inventados;
- `CROSS_ASSET_SNAPSHOT` con procedencia y timestamp por fila;
- Proyección que fusiona actualizaciones parciales por símbolo;
- HTTP/UI que muestra SP500, TSLA, AAPL y `GC=F` en la misma pantalla;
- cuatro espacios de diagnóstico independientes, N/A/amarillo sin evidencia real;
- integración externa opt-in contra Yahoo y gate offline completo;
- proceso activo en `127.0.0.1:8080` hasta `Ctrl+C`.
