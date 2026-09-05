# Auditoría de fuente Yahoo multi-activo — 2026-08-30

## Alcance

Evidencia técnica de `^GSPC`, `TSLA`, `AAPL` y `GC=F` en un único monitor `SHADOW`.
No certifica cuenta demo, bid/ask ejecutable, order flow, modelo, señal ni operativa.

## Contrato verificado

- allowlist exacta de cuatro símbolos; un quinto se rechaza;
- `^GSPC` permanece mercado principal `US500`;
- `GC=F` se identifica como `FUTURE` y `CONTINUOUS_FUTURES_NOT_SPOT`;
- REST consulta símbolos faltantes en paralelo y conserva fallos parciales;
- WebSocket acepta una lista de símbolos y cada mensaje produce un delta de una fila;
- precios/porcentajes atraviesan eventos como enteros escalados;
- `market_assets` fusiona por `provider_symbol` sin borrar los demás activos;
- ninguna cotización crea bid/ask, beta, z-score, probabilidad o señal;
- cada fila reserva un `diagnostico_semaforo` independiente y muestra N/A sin evidencia.

## Evidencia externa observada

La consulta realizada el 2026-08-30 devolvió los cuatro activos sin fallos parciales:

| Símbolo | Tipo reportado | Último valor observado | Timestamp Yahoo observado |
|---|---|---:|---|
| `^GSPC` | `INDEX` | 7,711.76 | `2026-08-28T20:37:00Z` |
| `TSLA` | `EQUITY` | 348.75 | `2026-08-28T20:00:00Z` |
| `AAPL` | `EQUITY` | 319.70 | `2026-08-28T20:00:01Z` |
| `GC=F` | `FUTURE` | 4,529.90 | `2026-08-28T20:59:57Z` |

Son una captura reproducible de esa ejecución, no constantes del producto. El endpoint debe
mostrar siempre el valor y timestamp que Yahoo entregue en el corte actual. La demora
permanece `PROVIDER_DELAY_UNDISCLOSED`.

## Cómo reproducir

```bash
RUN_YAHOO_INTEGRATION=1 PYTHONPATH=src \
  UV_CACHE_DIR=/private/tmp/sistemaluces-uv-cache \
  uv run python -B -m unittest -v tests.integration.test_yahoo_multi_asset_real
```

La suite offline contractual vive en `tests/sources/test_yahoo_multi_asset.py` y no requiere
red.

## Veredicto limitado

`PASS_INTEGRATION` para ingesta pública, Proyección, HTTP y presentación multi-activo.
`G-R3` continúa `BLOCKED_EXTERNAL`: no hay OAuth/cuenta demo ni cinco sesiones de broker.
