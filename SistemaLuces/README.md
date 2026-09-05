# Sistema de Luces

Piloto independiente para observar US500, emitir decisiones de luz explicables y monitorear
operativas simuladas asociadas a cuentas demo. Se diseña desde ahora como un módulo futuro
del Trading Journal, aunque este repositorio no modifica ni depende de su base de datos.

## Estado honesto

**MONITOR PÚBLICO MULTI-ACTIVO Y REPLAY DISPONIBLES / PRODUCTO DEMO OBSERVADO BLOQUEADO.** El
dashboard observa S&P 500, TSLA, AAPL y el futuro continuo de oro `GC=F` desde Yahoo Finance
en `SHADOW`, reconstruye eventos y reserva un diagnóstico independiente para cada activo. Yahoo publica precios y metadatos,
pero no certifica aquí bid/ask ejecutables ni demora cero; el monitor muestra la antigüedad y
el estado de mercado en lugar de fabricar cambios. Todavía no hay conexión OAuth/cTrader real
ni cinco sesiones selladas; por eso `G-R3` sigue `BLOCKED_EXTERNAL`.

## Fuentes de verdad

1. [Autoridad del producto](./ORIGINAL_REQUEST.md)
2. [SPEC-002](./docs/specs/SPEC-002-integracion-futura-trading-journal.md)
3. [SPEC-003: defectos y actualización incremental](./docs/specs/SPEC-003-registro-evolutivo-y-actualizacion-incremental-ui.md)
4. [SRS](./docs/SRS.md)
5. [Arquitectura](./docs/ARQUITECTURA.md)
6. [Sistema visual](./docs/SISTEMA-VISUAL.md)
7. [Plan de realineación](./docs/PLAN-REALINEACION.md)
8. [Trazabilidad](./docs/TRAZABILIDAD.md)

El [índice documental](./docs/README.md) explica qué es canónico, qué es evidencia y qué quedó
supersedido.

## Antigravity Teamwork

El paquete de lanzamiento está en
[docs/teamwork/README.md](./docs/teamwork/README.md). Incluye el prompt para
`/teamwork-preview`, el readiness pendiente y las reglas de roles, ownership, handoffs y
auditoría independiente.

## Fronteras

- Trading Journal: referencia de diseño y futuro host; solo lectura durante este proyecto.
- SistemaLuces: motor, contratos, simulación, datos y proceso propios.
- Cuenta demo: fuente read-only y contexto de conciliación; nunca destino de órdenes.
- UI: mismo lenguaje visual del Journal; toda cifra declara fuente, corte, muestra y estado.

## Verificación documental

```bash
python3.11 -B scripts/verificar_documentacion.py
```

La verificación funcional histórica (`make verify`) no equivale a una Puerta de producto.
Los gates nuevos separan contratos, integración, fuente demo, economía, modelos, UI y shadow.

## Ejecutar el monitor standalone

```bash
# Fuente pública transitoria: Yahoo ^GSPC, TSLA, AAPL y GC=F, proceso 24/7
UV_CACHE_DIR=.cache/uv uv run python -B scripts/ejecutar_yahoo_sp500.py

# Replay demostrativo con diagnóstico y fixture multi-activo identificado
python3.11 -B scripts/ejecutar_demo_vivo.py

# Reconstruir un event log SQLite existente
python3.11 -B scripts/iniciar_servidor_luces.py --db-path /ruta/al/luces.db
```

Todos sirven únicamente en `http://127.0.0.1:8080/`. El monitor Yahoo usa una suscripción
WebSocket multi-símbolo como ruta de menor latencia y REST paralelo como arranque/respaldo; permanece activo hasta
`Ctrl+C`. Fuera de sesión conserva el último valor real y muestra `MERCADO CERRADO`. Sin
event log, el servidor genérico abre en `NO_DATA` y explica cómo aportar una fuente.

El dashboard carga el documento una vez y actualiza las cuatro filas, estado, latencias y diagnósticos
mediante `/v1/status` cada 2 s sin recargar la página. Esa cadencia es de presentación: el
timestamp y el transporte de Yahoo siguen indicando cuándo cambió realmente la fuente.

La prueba externa se ejecuta explícitamente —no forma parte del gate offline— con:

```bash
RUN_YAHOO_INTEGRATION=1 PYTHONPATH=src UV_CACHE_DIR=/private/tmp/sistemaluces-uv-cache \
  uv run python -B -m unittest -v tests.integration.test_yahoo_multi_asset_real
```
