# Sistema de Luces 2.0 (Consola de Telemetría Óptica Cuantitativa)

Motor cuantitativo multi-activo y consola de apoyo a decisiones de trading en tiempo real construido bajo el estándar **Anti-AI Slop** y la inteligencia de diseño **UI/UX Pro Max**.

## Características Principales
- **Filtro de Kalman 2D:** Estimación recursiva de spread y ratio de cobertura ($\beta_t$).
- **Microestructura L2:** Order Flow Imbalance ($\text{OFI}_t$) y Micro-Price analítico ($P_{\text{micro}}$).
- **Baliza Óptica de Hardware:** Bisel mecanizado `#0e0e11` con diodos activos puros y punto especular.
- **Disciplina Tipográfica:** Cifras tabulares monoespaciadas (`font-variant-numeric: tabular-nums`).
- **Persistencia Inmutable:** SQLite append-only en `luces.db`.
- **Keyboard-First Loop:** Paleta de comandos (`⌘K`), cambio de pares (`1-3`), pausa (`Space`), silenciado (`⌘M`).

## Ejecución
```bash
uv run python run_console.py
```
