# Índice y autoridad documental

## Canónico

| Documento | Responsabilidad |
|---|---|
| [Autoridad del dueño](../ORIGINAL_REQUEST.md) | decisiones del dueño y jerarquía de autoridad |
| [SPEC-002](specs/SPEC-002-integracion-futura-trading-journal.md) | alcance de producto y contrato observable |
| [SPEC-003](specs/SPEC-003-registro-evolutivo-y-actualizacion-incremental-ui.md) | registro de defectos verificados y contrato de actualización incremental |
| [SRS](SRS.md) | requisitos funcionales/no funcionales y criterios de aceptación |
| [Arquitectura](ARQUITECTURA.md) | módulos, procesos, datos y seam de integración futura |
| [Sistema visual](SISTEMA-VISUAL.md) | experiencia y contrato visual compatible con Trading Journal |
| [Trazabilidad](TRAZABILIDAD.md) | objetivo → requisito → prueba → Puerta |
| [Plan](PLAN-REALINEACION.md) | orden de trabajo R0–R7 y mitigaciones |
| [Decisiones abiertas](DECISIONES-ABIERTAS.md) | decisiones que necesitan evidencia o dueño |
| [ADR-002](adr/ADR-002-piloto-separado-integracion-futura-journal.md) | decisión arquitectónica vigente |
| [ADR-003](adr/ADR-003-yahoo-sp500-fuente-publica-transitoria.md) | fuente pública Yahoo `^GSPC`, límites y reemplazo futuro |
| [ADR-004](adr/ADR-004-yahoo-cotizaciones-multi-activo.md) | SP500, TSLA, AAPL y `GC=F` con procedencia por símbolo en un único monitor |
| [Auditoría](AUDITORIA-REALINEACION.md) | divergencias actuales y destino de cada módulo |
| [Auditoría runtime 2026-08-30](AUDITORIA-RUNTIME-MONITOR-2026-08-30.md) | fallos del monitor, reparaciones y bloqueo externo vigente |
| [Auditoría Yahoo S&P 500](AUDITORIA-FUENTE-YAHOO-SP500-2026-08-30.md) | evidencia real, latencia, límites y veredicto de integración |
| [Auditoría Yahoo multi-activo](AUDITORIA-FUENTE-YAHOO-MULTI-ACTIVO-2026-08-30.md) | evidencia real de SP500, TSLA, AAPL y oro, con límites del diagnóstico |
| [Estrategia de pruebas](../TEST_INFRA.md) | niveles de evidencia y política de veredicto |
| [Estado de pruebas](../TEST_READY.md) | readiness vigente, sin heredar certificaciones antiguas |
| [Antigravity Teamwork](teamwork/README.md) | prompt de entrada, readiness y reglas de orquestación |

## Evidencia, no autoridad

- [Índice de evidencia](evidence/README.md): separa resultados vigentes e históricos.
- [Gate vigente](evidence/v1-gate.md): cierre técnico de R0; no aprueba el producto.
- [Legado](legacy/README.md): SPEC, ADR y declaraciones del primer intento.
- [Registros de agentes](../.agents/README.md): rastros de ejecución; no sustituyen
  decisiones del dueño ni Puertas.

## Reglas de cambio

1. Una decisión del dueño actualiza primero `ORIGINAL_REQUEST.md`.
2. Un cambio de producto actualiza SPEC, SRS y trazabilidad.
3. Un cambio de arquitectura requiere ADR antes de implementación.
4. Una fase sólo se declara `PASS` con la evidencia indicada por su Puerta.
5. Un documento histórico nunca vuelve a canónico por ser citado desde código o tests.
