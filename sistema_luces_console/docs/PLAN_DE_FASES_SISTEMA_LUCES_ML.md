# PLAN MAESTRO DE FASES: MOTOR CUANTITATIVO & SISTEMA DE APRENDIZAJE SUPERVISADO (SISTEMA DE LUCES 2.0)

**Documento:** Plan de Implementación por Fases, Puertas de Aceptación y Gobernanza  
**Estado:** Listo para Ejecución Secuencial (`ready-for-implementation`)  
**Referencias:** [SPEC-001 (Sistema de Luces)](file:///Users/nuevo/.gemini/antigravity-cli/brain/3a83a68b-bfa8-46c7-a13e-da954cdc89e6/spec_sistema_luces_cuantitativo_pro_max.md), [SPEC-002 (ML Instructor Engine)](file:///Users/nuevo/.gemini/antigravity-cli/brain/3a83a68b-bfa8-46c7-a13e-da954cdc89e6/spec_ml_instructor_trading_engine.md), [RESEARCH Report](file:///Users/nuevo/sistema_luces_console/docs/RESEARCH_OPTIMAL_PARAMETERS_HUMAN_SUPERVISION.md)  

---

## 1. Visión General del Plan de Fases

El objetivo de este plan es construir, validar y desplegar el **Sistema de Luces 2.0** y su **Motor de Machine Learning Supervisado** de forma modular, con contabilidad estricta de evidencia y **capacidad de adaptación y personalización según los trades y estrategias que el operador registre**.

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        MAPA DE RUTA DE IMPLEMENTACIÓN POR FASES                        │
├────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                        │
│  [FASE 0] ──► [FASE 1] ──► [FASE 2] ──► [FASE 3] ──► [FASE 4] ──► [FASE 5] ──► [FASE 6]│
│  Cimientos &  Motor        Decisión      Capa de      Preentreno   Destilación  Consola    │
│  Ingesta de   Cuantitativo Bayesiana     Adaptación   Latente      ML & IQL     Industrial │
│  Operativa    Calibrado    & Diales      Personal del JEPA/Barlow  con Veto     & Puerta   │
│  del Usuario  (Kalman/OFI) de Control    Operador     (D=256)      Instructor   Campeón    │
│                                                                                        │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Desglose Detallado de Fases

### Fase 0 · Cimientos de Dominio, Ingesta de Operativa del Operador y Contratos Inmutables
**Objetivo:** Establecer la infraestructura de datos inmutable, el esquema SQLite WAL y el módulo para importar y catalogar los trades históricos y en vivo del operador sin acoplamiento con bases de datos externas.

- **Entregables:**
  1. `sistema_luces.domain.operator_trade`: Modelo de datos para capturar operaciones del usuario (`entrada`, `stop`, `take_profit`, `salida`, `R_multiplo`, `setup_id`, `emocion_previa`, `costos_reales`).
  2. `sistema_luces.imports.trade_importer`: Parser idempotente de CSV/JSON para exportaciones de operativas con validación de hashes SHA-256.
  3. `sistema_luces.storage.schema_v2`: Tablas append-only `operativa_operador`, `estrategia_version`, `snapshot_mercado_t`.
- **Criterio de Aceptación (Puerta G0):**
  - Importación idempotente probada: importar el mismo archivo de trades dos veces produce exactamente los mismos registros sin duplicación.
  - Cero escrituras en bases de datos externas.

---

### Fase 1 · Motor Cuantitativo Calibrado de Alta Fidelidad
**Objetivo:** Implementar los algoritmos matemáticos con los parámetros óptimos derivados de la investigación para procesar ticks L2 con margen de error mínimo.

- **Entregables:**
  1. `DynamicKalmanFilter` robusto: Factor de descuento $\delta = 1.0 \times 10^{-4}$, varianza adaptativa de Mehra $R_0 = 1.0 \times 10^{-2}$ y rechazo de outliers Huber M-estimator ($c_{\text{Huber}} = 2.576$).
  2. `MultiLevelOrderFlowEngine`: Cálculo de $\text{OFI}_t$ sobre $K=5$ niveles del libro L2 con decaimiento espacial exponencial $\kappa = 0.65$.
  3. `StoikovMicroPriceEngine`: Estimador analítico de microprecio ponderado por colas opuestas y trigger de desbalance $\Delta_{\text{micro}} \ge \pm 250,000\text{ ppm}$.
  4. `VPINDetector`: Detección de flujo tóxico con 50 cubos de volumen y parada cautelar a $VPIN \ge 0.85$.
- **Criterio de Aceptación (Puerta G1):**
  - Pruebas de convergencia de Kalman con error estándar $<0.05$ en estimación de $\beta_t$.
  - Invarianza temporal: ninguna característica utiliza información posterior a $t$.

---

### Fase 2 · Motor de Decisión Bayesiana, Histéresis y Diales de Control Humano
**Objetivo:** Fusión de alfas en el clasificador probabilístico de 3 estados (`VERDE`, `AMARILLO`, `ROJO`) con confluencia bayesiana para alcanzar $>75\%$ de Hit Rate ($<25\%$ error) y diales interactivos de control.

- **Entregables:**
  1. `BayesianConfluenceGate`: Fusión de verosimilitudes (Odds a posteriori $\ge 5.54 \implies P(\text{Win}) > 84\%$).
  2. `DecisionStateMachine` asimétrica: Umbrales $T_{\text{in}} = 0.45$, $T_{\text{out}} = 0.15$ y seguro por defecto (`AMARILLO`).
  3. `HumanControlDials`: Módulo de ajuste en caliente de sensibilidad, umbral Z-score y parada manual inmediata (`⌘V` / Hard Veto en $<1\text{ ms}$).
- **Criterio de Aceptación (Puerta G2):**
  - Validación *walk-forward* histórica confirmando *Hit Rate* direccional $\ge 75.0\%$ neto de spread y slippage.
  - Cero transiciones directas `VERDE` $\leftrightarrow$ `ROJO` en un solo tick.

---

### Fase 3 · Capa de Adaptación Personal y Perfiles de Estrategia del Operador
**Objetivo:** Conectar las decisiones cuantitativas con el estilo y los setups específicos del operador para crear perfiles de estrategia personalizados.

- **Entregables:**
  1. `StrategyProfileRegistry`: Registro de setups aprobados por el usuario (e.g. *Breakout de Sesión Londres*, *Reversión Oro/DXY*, *Momentum TSLA/SP500*).
  2. `OperatorBehavioralProfiler`: Análisis de correlación entre las señales del Sistema de Luces y las entradas/salidas reales del operador (identificando en qué regímenes el operador aporta alfa positivo frente a la máquina).
  3. `PersonalizedFilterMatrix`: Matriz de filtrado que modula la emisión de la luz adaptándola al horizonte temporal y aversión al riesgo del operador.
- **Criterio de Aceptación (Puerta G3):**
  - Capacidad de reproducir el historial de trades del operador clasificando aciertos por setup y régimen de mercado.

---

### Fase 4 · Preentrenamiento Auto-Supervisado (JEPA / Barlow Twins)
**Objetivo:** Entrenar el codificador de series temporales para extraer representaciones latentes de 32 a 256 dimensiones invariantes al ruido de microestructura.

- **Entregables:**
  1. `MarketTimeSeriesJEPA`: Arquitectura Joint-Embedding con programa de decaimiento EMA en el codificador objetivo ($\alpha = 0.996 \to 0.9999$).
  2. `BarlowTwinsRegularizer`: Pérdida de reducción de redundancia con coeficiente $\lambda_{\text{Barlow}} = 5.0 \times 10^{-3}$.
  3. `LatentStateExtractor`: Servicio de inferencia ultra-rápido ($<1.5\text{ ms}$) que alimenta vectores latentes al motor de ML.
- **Criterio de Aceptación (Puerta G4):**
  - Cero colapso dimensional en el espacio latente ($D=256$) verificado por la matriz de covarianza cruzada.

---

### Fase 5 · Motor de Machine Learning Supervisado (AWBC + IQL con Veto del Instructor)
**Objetivo:** Construir la red de políticas del estudiante que replica y optimiza la ejecución de las estrategias del operador bajo la tutela del Sistema de Luces.

- **Entregables:**
  1. `ImplicitQLearningValueNet`: Estimador de función de valor con pérdida expectil $\tau_e = 0.75$ y factor de descuento $\gamma = 0.99$.
  2. `AdvantageWeightedPolicy`: Extracción de política con temperatura $\beta_T = 1.50$ y regularización de divergencia KL ($\lambda_{\text{KL}} = 0.10$) contra el Sistema de Luces.
  3. `InstructorVetoGuardrail`: Módulo de intercepción en tiempo real que anula cualquier acción del estudiante si la incertidumbre epistémica supera el $25\%$ o si contradice la región admisible del instructor.
- **Criterio de Aceptación (Puerta G5):**
  - Acuerdo con el Sistema de Luces $\ge 95\%$ en regímenes no ambiguos.
  - Intercepción y veto forzado a `AMARILLO` en $<1\text{ ms}$ ante anomalías inyectadas.

---

### Fase 6 · Consola Industrial Anti-AI Slop con Diales de Telemetría y Puerta Campeón/Retador
**Objetivo:** Integrar toda la telemetría en la interfaz de usuario de grado industrial con baliza óptica de hardware, cifras tabulares y protocolo de aprobación criptográfica.

- **Entregables:**
  1. `IndustrialConsoleUI`: Interfaz en vivo con tokens de obsidiana, cuadrícula de 4 puntos, bisel mecanizado, micro-clicks de audio y loop de teclado completo (`⌘K`, `1-3`, `Space`, `⌘M`, `⌘V`).
  2. `EvidenceTreasuryDashboard`: Monitor de presupuesto de riesgo (límite diario de 2.0% equity) y degradación de Brier Score.
  3. `ChampionChallengerGate`: Protocolo de sombra (10,000 ticks) con prueba de Diebold-Mariano y firma criptográfica Ed25519 obligatoria del operador para promover modelos a producción.
- **Criterio de Aceptación (Puerta G6):**
  - 100/100 puntos en la Rúbrica Anti-AI Slop (0 emojis, 0 halos neón, 0 blurs).
  - Presupuesto de latencia cumplido: $p95 < 100\text{ ms}$ de extremo a extremo (tick $\to$ UI).

---

## 3. Matriz de Parámetros Calibrados por Fase

| Fase | Parámetro Clave | Valor Exacto | Justificación |
|---|---|---|---|
| **Fase 1** | Descuento Kalman ($\delta$) | $1.0 \times 10^{-4}$ | Vida media de 6,931 ticks (17.3 min de régimen de mercado) |
| **Fase 1** | Decaimiento OFI ($\kappa$) | $0.65$ | Ponderación decreciente sobre los 5 niveles del libro L2 |
| **Fase 1** | Umbral VPIN Crítico | $0.85 \text{ (Yellow)} / 0.92 \text{ (Halt)}$ | Prevención de selección adversa y choques de liquidez |
| **Fase 2** | Histéresis ($T_{\text{in}} / T_{\text{out}}$) | $0.45 / 0.15$ | Convicción asimétrica para evitar parpadeo cerca del umbral |
| **Fase 4** | Dimensión Latente JEPA ($D$) | $256$ | Invarianza al ruido con presupuesto de inferencia $<1.5\text{ ms}$ |
| **Fase 5** | Expectil IQL ($\tau_e$) | $0.75$ | Optimización sobre el cuartil superior de trades rentables |
| **Fase 5** | Temperatura AWBC ($\beta_T$) | $1.50$ | Ponderación exponencial de ventaja sin colapso de política |
| **Fase 5** | Regularización KL ($\lambda_{\text{KL}}$) | $0.10$ | Anclaje de seguridad estricto a las reglas del instructor |
| **Fase 6** | Sombra de Validación | $10,000\text{ ticks}$ | Muestra mínima fuera de muestra antes de habilitar la promoción |

---

## 4. Gobernanza y Contabilidad de Evidencia

Cada fase se ejecuta bajo el principio de **preservación de evidencia**:
1. **Separación de Datos:** Los conjuntos de datos de prueba final permanecen sellados e inaccesibles durante el ajuste de hiperparámetros.
2. **Registro de Intentos:** La tesorería descuenta fichas de evidencia con cada barrido de parámetros. Si el presupuesto se agota, se bloquea el reentrenamiento para prevenir el sobreajuste (Bucle L3).
3. **Control Exclusivo del Operador:** Ningún componente automatizado puede alterar parámetros críticos o promover modelos retadores sin la intervención manual y aprobación del operador.
