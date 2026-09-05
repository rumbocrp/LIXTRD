# Autoridad del producto — Sistema de Luces

**Estado:** vigente  
**Fecha de consolidación:** 2026-08-30  
**Autoridad:** decisiones explícitas del dueño en la conversación de trabajo

Este archivo reemplaza el mandato interno en inglés que ordenaba ejecutar WP-02…WP-15. Aquel
texto fue generado durante la construcción y no era la solicitud original del dueño.

## Decisiones del dueño

| ID | Decisión vigente | Consecuencia |
|---|---|---|
| `DO-01` | Trading Journal ya está construido y no se modifica en este trabajo. | Toda inspección del Journal es de solo lectura. |
| `DO-02` | SistemaLuces es un proyecto independiente durante el piloto. | Repositorio, proceso y datos propios. |
| `DO-03` | Producto, documentación y experiencia se diseñan tomando Trading Journal como plataforma de referencia. | Se adopta su vocabulario, sistema visual, arquitectura modular, criterios de accesibilidad y calidad. |
| `DO-04` | En el futuro, el Sistema de Luces debe poder vivir dentro del Trading Journal. | La interfaz se diseña como módulo trasladable; el motor se integra por contrato, no por acceso a `tj.db`. |
| `DO-05` | Antes de continuar el producto se reemplazan y auditan SPEC, SRS, arquitectura y plan. | La documentación nueva es la autoridad; la anterior queda como legado. |
| `DO-06` | El piloto monitorea operativas simuladas para cuentas demo. | No existe ruta de órdenes; los datos demo y las simulaciones deben estar claramente identificados. |
| `DO-07` | El plan debe mejorar el producto, adaptarlo al diseño y mitigar las divergencias detectadas. | Cada fase termina en una Puerta con evidencia, no con una declaración narrativa. |
| `DO-08` | Durante la prueba actual, el monitor toma al S&P 500 como mercado principal, con números obtenidos de Yahoo Finance, actualización de baja latencia práctica y proceso activo 24/7. | Yahoo se incorpora como fuente pública transitoria `SHADOW` para `^GSPC`; se muestran timestamp, estado de mercado, demora y latencia sin inventar movimiento, bid/ask ni señales. |
| `DO-09` | La fuente provisional debe poder reemplazarse o complementarse después con order flow y brokers. | La ingesta Yahoo implementa el mismo límite de adaptador de fuente y no introduce reglas financieras en la UI. |
| `DO-10` | La pantalla debe conservar S&P 500, TSLA y AAPL y añadir el oro reportado por Yahoo Finance. | Un único proceso `SHADOW` publica las cuatro cotizaciones verificadas; `GC=F` se rotula como futuro continuo de oro, no como spot XAU/USD, y ninguna cotización por sí sola certifica una señal. |

## Interpretación arquitectónica reversible

Durante el piloto, «integración futura dentro del Trading Journal» significa:

1. una interfaz del mismo stack y sistema visual que pueda trasladarse a una ruta `/luces`;
2. un motor Python separado, servido sólo en loopback y consumido mediante un contrato
   versionado de lectura;
3. bases independientes y ninguna lectura directa de `tj.db`;
4. una decisión futura separada si se quisiera fusionar procesos, bases o lenguajes.

Esta interpretación reduce el trabajo de integración futura sin acoplar hoy los dos
productos. Puede cambiarse por una decisión posterior del dueño registrada en un ADR.

Yahoo Finance no se interpreta como la Fuente demo de `DO-06`: prueba el monitor y su seam
de datos, pero no demuestra una cuenta demo, precios ejecutables, order flow ni la Puerta
`G-R3`. El proceso puede operar 24/7; el índice sólo cambia cuando el proveedor publica un
nuevo valor y la interfaz conserva el último corte con su antigüedad cuando el mercado cierra.

`DO-10` amplía únicamente la observación pública: el motor de decisiones, simulación,
economía y Puertas de cuenta demo de V1 continúan limitados a US500. SP500, TSLA, AAPL y
`GC=F` aparecen como cotizaciones independientes con procedencia y edad propias; no se
fabrican relaciones, scores, señales ni umbrales a partir de sus precios.

## Jerarquía de autoridad

1. Decisiones nuevas y explícitas del dueño.
2. Este archivo y `docs/adr/ADR-002-piloto-separado-integracion-futura-journal.md`.
3. `docs/specs/SPEC-002-integracion-futura-trading-journal.md` y `docs/SRS.md`.
4. Arquitectura, sistema visual, trazabilidad y plan vigentes.
5. Código y pruebas, como evidencia del estado actual, no como fuente de requisitos.
6. `docs/legacy/` y `docs/evidence/WP-*`, sólo como historia del primer intento.
