# Decisiones abiertas

Una decisión abierta no se resuelve por conveniencia del implementador. El trabajo que no
dependa de ella puede continuar; su Puerta permanece `BLOCKED`.

| ID | Decisión | Estado | Cuándo bloquea |
|---|---|---|---|
| `DA-L01` | Cuenta demo, aplicación cTrader y OAuth read-only disponibles | pendiente externo | R3 |
| `DA-L02` | `symbolId`, dígitos, punto, contrato, cantidad mínima/paso y moneda US500 | pendiente evidencia | R3 |
| `DA-L03` | Comisión, spread observado, slippage y carry | pendiente evidencia | R3/R4 |
| `DA-L04` | Límites añadidos: una posición, 10 aperturas/día, stale 5 s y noticias ±15 min | pendiente dueño + datos | R3/R6 |
| `DA-L05` | Depth aceptado/descartado tras cinco sesiones | pendiente evidencia | sólo RF-L024 |
| `DA-L06` | Versión exacta del snapshot visual y política de actualización | pendiente al iniciar R5 | R5 |
| `DA-L07` | Puertos standalone definitivos para panel y motor | pendiente operación | R5 |
| `DA-L08` | Retención y borrado de eventos demo/artefactos | pendiente dueño | R3 |
| `DA-L09` | Uso futuro de datos personales o del Journal para entrenamiento | no autorizado | fuera de V1 |
| `DA-L10` | Fecha y release del Journal que recibirá `/luces` | futura | R7 no la necesita; integración real sí |
| `DA-L11` | Condiciones de uso/retención y proveedor contractual definitivo de datos de mercado | pendiente antes de producto | no bloquea prueba local Yahoo; bloquea producción |

## Cerradas por el dueño

| ID | Decisión |
|---|---|
| `DC-L01` | Trading Journal no se modifica durante el piloto. |
| `DC-L02` | SistemaLuces permanece separado por ahora. |
| `DC-L03` | Se diseña bajo la idea/plataforma del Trading Journal. |
| `DC-L04` | Se prepara para integración futura dentro del Journal. |
| `DC-L05` | V1 usa cuentas demo y Operativas simuladas, sin órdenes. |
| `DC-L06` | La documentación anterior se audita y reemplaza antes de continuar. |
| `DC-L07` | La prueba transitoria observa sólo `^GSPC` desde Yahoo Finance y permanece anexable a order flow/brokers. |
