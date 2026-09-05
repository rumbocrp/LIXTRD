# Lanzamiento con Antigravity Teamwork

## Estado

El contenido técnico está preparado para la entrevista de alcance de Teamwork, pero la ejecución
autónoma todavía necesita dos confirmaciones humanas:

1. aceptar `G-R0` además de su `PASS_TECNICO`;
2. decidir cómo crear el baseline Git, porque el repositorio no tiene un commit inicial y conserva
   archivos sin seguimiento.

Antigravity debe detectar ambos puntos durante su Fase 1. No debe inventar identidad Git ni crear el
commit sin autorización.

## Cómo iniciar

1. Abre `/Users/nuevo/Documents/PROYECTOS/SistemaLuces` como workspace en Antigravity.
2. Inicia una conversación nueva.
3. Ejecuta `/teamwork-preview` y pega el bloque delimitado en
   [ANTIGRAVITY-TEAMWORK-SYSTEM-PROMPT.md](ANTIGRAVITY-TEAMWORK-SYSTEM-PROMPT.md).
4. Revisa el prompt artifact que Antigravity crea en su Fase 1.
5. Aprueba la ejecución sólo si conserva:
   - R1 como primer milestone;
   - Trading Journal en solo lectura;
   - ownership exclusivo por Builder;
   - QA/Auditor independientes;
   - `BLOCKED_EXTERNAL` para evidencia demo ausente;
   - gates R1–R7 y aprobación humana separada.

## Señales para rechazar el prompt artifact

- propone reconstruir el proyecto en `~/teamwork_projects` o copiarlo fuera del repo;
- trata `.agents/`, `docs/legacy/` o los WP históricos como autoridad;
- declara listo el producto por el conteo de pruebas existente;
- intenta ejecutar todos los milestones a la vez;
- promete conectar cTrader sin credenciales ni handshake real;
- modifica Trading Journal, abre `tj.db` o comparte su base;
- usa la UI/`quant` sintética como fuente de producto.

El prompt está pensado para el camino General de Teamwork y su flujo de dos fases: primero se revisa
el alcance; después de la aprobación, Sentinel entrega la ejecución al Project Orchestrator.
