# Estado de preparación para pruebas

**Corte:** 2026-08-30  
**Estado:** `NOT_TEST_READY`  
**Puerta documental:** pendiente de ejecutar `G-R0`  
**Estado de producto:** `BLOCKED_REBASELINE`

## Veredicto

El repositorio todavía no está preparado para una validación de producto ni para operativas
demo observadas. Existen pruebas unitarias y contractuales útiles del primer intento, pero no
demuestran un pipeline integrado, una conexión real read-only, cinco sesiones selladas, un
modelo evaluado ni la interfaz compatible con Trading Journal.

Una prueba histórica que sólo usa fixtures puede conservar valor técnico; no se reutiliza para
declarar que un requisito externo o end-to-end está cumplido.

## Evidencia disponible

- dominio, persistencia, feed, casos, etiquetas, política, riesgo y simulación tienen pruebas;
- los artefactos `docs/evidence/WP-*` describen ciclos del primer intento;
- una auditoría local encontró 310 pruebas, con una incidencia de infraestructura al intentar
  abrir un socket loopback dentro del sandbox;
- `make verify` no completó en la auditoría porque `uv` intentó usar una caché sin permiso.
- la integración pública Yahoo `^GSPC` pasa contrato, HTTP/UI y prueba externa opt-in; sirve
  para observar el monitor, pero no demuestra una cuenta demo ni cambia `NOT_TEST_READY`.

Estos hechos no constituyen un PASS de las Puertas nuevas.

## Condiciones para cambiar a `TEST_READY`

1. `G-R0` y `G-R1` en PASS con evidencia reproducible.
2. Pipeline único de replay y shadow implementado y cubierto por `G-R2`.
3. Harness ejecutable sin depender de rutas, cachés o puertos no autorizados.
4. Fixtures con procedencia explícita; lo sintético nunca se rotula como demo observada.
5. Matriz de [trazabilidad](./docs/TRAZABILIDAD.md) actualizada con resultados reales.
6. Revisión independiente de la Puerta que corresponda; ningún agente se autocertifica.

## Comandos permitidos ahora

```bash
python3.11 -B scripts/verificar_documentacion.py
python3.11 -B -m unittest discover -s tests -t . -v
RUN_YAHOO_INTEGRATION=1 PYTHONPATH=src .venv/bin/python -m unittest -v tests.integration.test_yahoo_sp500_real
```

El segundo comando sólo caracteriza el baseline de código. Un resultado verde no cambia por sí
solo el estado de producto.

La declaración antigua fue preservada en
[`docs/legacy/TEST_READY-agentes.md`](./docs/legacy/TEST_READY-agentes.md).
