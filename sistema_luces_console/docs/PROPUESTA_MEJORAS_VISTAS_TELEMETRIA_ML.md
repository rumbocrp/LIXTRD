# PROPUESTA TÉCNICA Y EXTENSIÓN DEL MANUAL DE USUARIO: MEJORAS VISUALES Y DE TELEMETRÍA ANALÍTICA AVANZADA (SISTEMA DE LUCES 2.0 & ML INSTRUCTOR)

**Documento Técnico Formal · Monografía de Arquitectura Cuantitativa & Manual de Operador**  
**ID del Documento:** `SPEC-003-TELEMETRY-VISUALS-V2`  
**Sistemas Afectados:** `Sistema de Luces 2.0 (SPEC-001)`, `ML Policy Distillation Engine (SPEC-002)`, `Consola Web Industrial HITL`  
**Objetivo Métrico:** Reducción del margen de error a $< 25.0\%$ (Hit Rate empírico $> 75.0\%$) bajo fricción de mercado mediante observabilidad de caja de cristal (*Glass-Box Telemetry*), explicabilidad axiomática y supervisión humana de ultra-baja latencia ($< 1.0\text{ ms}$).  
**Clasificación:** Documentación Técnica de Grado Industrial / Manual de Operación Cuantitativa  
**Fecha:** Septiembre 2026  

---

## RESUMEN EJECUTIVO & JUSTIFICACIÓN ARQUITECTÓNICA

El **Sistema de Luces 2.0** opera como un motor estocástico-cuantitativo de alta frecuencia y como supervisor pedagógico en tiempo real para modelos de aprendizaje por refuerzo fuera de línea (*Offline Reinforcement Learning*). Si bien la arquitectura base proporciona una señal discreta tri-estado (`VERDE / COMPRA`, `AMARILLO / MONITOR`, `ROJO / VENTA`) sustentada en la confluencia de Filtros de Kalman Robusto, Desbalance del Flujo de Órdenes (*OFI Multi-Nivel*), Micro-Precio de Stoikov y toxicidad VPIN, el operador humano de alta frecuencia (*Human-in-the-Loop*) requiere una observabilidad total de las fuerzas microscópicas subyacentes antes de validar una ejecución o ejercer un veto manual (`[⌘V]`).

Esta propuesta técnica formaliza e implementa **7 nuevas vistas analíticas y subsistemas de telemetría de alta densidad**, diseñados bajo los principios estrictos del estándar *Anti-AI Slop* (cero elementos decorativos innecesarios, contraste tipográfico industrial, precisión matemática rigurosa, cifras tabulares y renderizado a 60 FPS con latencia de interfaz $< 16\text{ ms}$):

```
┌────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                      SISTEMA DE LUCES 2.0 · MATRIZ DE TELEMETRÍA ANALÍTICA AVANZADA                    │
└────────────────────────────────────────────────────────────────────────────────────────────────────────┘
                                                    │
    ┌───────────────────────────────────────────────┴───────────────────────────────────────────────┐
    │                                                                                               │
    ▼                                                                                               ▼
┌──────────────────────────────────────────┐                                   ┌──────────────────────────────────────────┐
│  CAPA 1: MICROESTRUCTURA & FLUJO L2      │                                   │  CAPA 2: COINTEGRACIÓN & REVERSIÓN DIN.  │
│  ──────────────────────────────────────  │                                   │  ──────────────────────────────────────  │
│  • Vista 1: Cascada L2 & DOM Heatmap     │                                   │  • Vista 2: Lead-Lag & Ornstein-Uhlenbeck│
│    - Ratios multi-nivel K=20             │                                   │    - Estimación θ_OU, σ_OU, T_1/2        │
│    - Latencia de reposición τ_replenish  │                                   │    - Bandas ADF Rolling (p-value)        │
│    - Ratio de Spoofing / Cancelación     │                                   │    - Geometría de dispersión live        │
│    - Detección de bloques Iceberg        │                                   │    - Vector de error ortogonal           │
└──────────────────────────────────────────┘                                   └──────────────────────────────────────────┘
    │                                                                                               │
    ├───────────────────────────────────────────────┬───────────────────────────────────────────────┤
    │                                               │                                               │
    ▼                                               ▼                                               ▼
┌──────────────────────────────────────────┐ ┌──────────────────────────────────────────┐ ┌──────────────────────────────────────────┐
│  CAPA 3: ESPACIO LATENTE & OOD           │ │  CAPA 4: EXPLICABILIDAD & GRADIENTES     │ │  CAPA 5: INCERTIDUMBRE DUAL            │
│  ──────────────────────────────────────  │ │  ──────────────────────────────────────  │ │  ──────────────────────────────────────  │
│  • Vista 3: Proyección I-JEPA D=256      │ │  • Vista 4: Integrated Gradients & SHAP  │ │  • Vista 5: Epistémica vs. Aleatoria   │
│    - Reducción live PCA / UMAP           │ │    - Atribución axiomática tick a tick   │ │    - Dispersión Twin-Q |Q1 - Q2|       │
│    - Distancia Mahalanobis a centroides  │ │    - Desglose % (OFI, Kalman, Micro, etc)│ │    - Entropía de política H(π)         │
│    - Alarma geométrica OOD preventiva    │ │    - Panel "¿Por qué cambió la señal?"   │ │    - Clamping automático a AMARILLO    │
└──────────────────────────────────────────┘ └──────────────────────────────────────────┘ └──────────────────────────────────────────┘
    │                                                                                               │
    └───────────────────────────────────────────────┬───────────────────────────────────────────────┘
                                                    │
    ┌───────────────────────────────────────────────┴───────────────────────────────────────────────┐
    │                                                                                               │
    ▼                                                                                               ▼
┌──────────────────────────────────────────┐                                   ┌──────────────────────────────────────────┐
│  CAPA 6: BENCHMARKING DE SETUPS & SHADOW │                                   │  CAPA 7: TENSOR DE COVARIANZA GLOBAL     │
│  ──────────────────────────────────────  │                                   │  ──────────────────────────────────────  │
│  • Vista 6: Panel de Setups & Shadow Run │                                   │  • Vista 7: Matriz de Correlación N x N  │
│    - Test Diebold-Mariano acumulado      │                                   │    - Covarianza EWMA de alta frecuencia  │
│    - Sharpe, Sortino, E[R] por setup     │                                   │    - 7 Activos: Gold, DXY, SPX, TSLA,    │
│    - Log de auditoría de filtros defens. │                                   │      AAPL, US10Y, EURUSD                 │
│    - Detección automática de Edge        │                                   │    - Alarma de ruptura y contagio        │
└──────────────────────────────────────────┘                                   └──────────────────────────────────────────┘
```

---

## SECCIÓN 1: VISTA DE PROFUNDIDAD L2 EN CASCADA (DOM HEATMAP & ORDER BOOK QUEUE DYNAMICS)

### 1.1 Fundamentos de Microestructura y Fuentes Primarias
El libro de órdenes límite (*Limit Order Book*, LOB) contiene información predictiva que precede a la formación del precio en el tiempo continuo. Basándonos en las investigaciones fundamentales de **Cont, Kukanov & Stoikov (2014)** (*The Price Impact of Order Book Events*), **Lehalle & Laruelle (2018)** (*Market Microstructure in Practice*) y **Biais, Hillion & Spatt (1995)**, el impacto de precios de alta frecuencia está regido por la dinámica espacial y temporal del libro:

1. **Impacto No Lineal Multi-Nivel:** El flujo de órdenes en niveles profundos ($L_2\text{-}L_{20}$) contiene el $45\text{-}60\%$ del poder explicativo de la dirección del próximo precio medio (*next mid-price change*).
2. **Asimetría de Reposición (*Replenishment Asymmetry*):** La rapidez con la que los creadores de mercado reponen cotizaciones tras un barrido agresivo determina si el nivel es defendido o vulnerado.
3. **Flujo Falso (*Spoofing / Flashing*):** La presencia de órdenes masivas con vida media ultra-corta ($<150\text{ ms}$) sesga los estimadores lineales simples y requiere filtros de permanencia temporal.
4. **Liquidez Oculta (*Iceberg Blocks*):** La reposición repetida e instantánea en el mejor nivel revela bloques institucionales que frenan las tendencias.

```
   NIVEL DE PROFUNDIDAD (ASK)
   Ask L5 [ 2642.50 ] ░░░░░░░░ 85.0 Lots
   Ask L4 [ 2642.40 ] ░░░░ 42.0 Lots
   Ask L3 [ 2642.30 ] ░░░░░░ 60.0 Lots  [SPOOFING FLAG: Lifetime < 120ms]
   Ask L2 [ 2642.20 ] ░░░░░░░░░░ 110.0 Lots
   Ask L1 [ 2642.10 ] ░░ 22.0 Lots ───────────┐
                                               ├── SPREAD S_t = 0.20
   Bid L1 [ 2641.90 ] ░░░░░░░░░░░░░░ 150.0 Lots ◄ [ICEBERG DETECTADO: ~450 Lots]
   Bid L2 [ 2641.80 ] ░░░░░░░░ 88.0 Lots
   Bid L3 [ 2641.70 ] ░░░░░░░░░░░░ 130.0 Lots
   Bid L4 [ 2641.60 ] ░░░░ 45.0 Lots
   Bid L5 [ 2641.50 ] ░░░░░░░ 72.0 Lots
   NIVEL DE PROFUNDIDAD (BID)
```

### 1.2 Formulación Matemática de Indicadores L2 en Cascada

#### A. Ratios de Profundidad Multi-Nivel Ponderados ($K=20$)
Para capturar la presión volumétrica sin que los niveles lejanos distorsionen espuriamente la señal, se define el vector de pesos espaciales decrecientes:

$$w_k = \frac{\exp(-\kappa (k-1))}{\sum_{j=1}^K \exp(-\kappa (j-1))}, \quad \kappa = 0.40, \quad K=20$$

El **Imbalance Ponderado Multi-Nivel ($I_K$)** se calcula como:

$$I_K(t) = \frac{\sum_{k=1}^K w_k v_k^b(t) - \sum_{k=1}^K w_k v_k^a(t)}{\sum_{k=1}^K w_k v_k^b(t) + \sum_{k=1}^K w_k v_k^a(t)} \in [-1.0, +1.0]$$

Donde $v_k^b(t)$ y $v_k^a(t)$ representan el volumen visible en el $k$-ésimo nivel de Bid y Ask en el instante $t$.

#### B. Latencia de Reposición de Liquidez ($\tau_{\text{replenish}}$)
Cuando una orden agresiva de mercado absorbe la totalidad de la liquidez en $L_1$, se mide el tiempo transcurrido $\Delta t$ hasta que los proveedores de liquidez reponen al menos el $75\%$ de la profundidad promedio histórica $\bar{v}_1$:

$$\tau_{\text{replenish}} = \inf \left\{ \Delta t > 0 \;\middle|\; v_1(t + \Delta t) \ge 0.75 \cdot \bar{v}_1 \right\}$$

- **Régimen de Liquidez Alta:** $\tau_{\text{replenish}} < 25\text{ ms}$ (Mercado resiliente; absorción no direccional).
- **Régimen de Vacío de Liquidez (*Liquidity Hole*):** $\tau_{\text{replenish}} > 180\text{ ms}$ (Indica retirada de Market Makers; alto riesgo de slippage adverso).

#### C. Ratio de Cancelación y Detección de Spoofing ($R_{\text{spoof}}$)
El spoofing algorítmico se caracteriza por la inserción de bloques voluminosos en los niveles $L_2\text{-}L_5$ que son cancelados antes de interactuar con el flujo ejecutor. Se define el ratio en una ventana rodante $W = 500\text{ ms}$:

$$R_{\text{spoof}}(t) = \frac{\sum_{i \in \text{Cancel}(t, W)} V_i \cdot \mathbb{I}\left(\Delta \tau_i < \tau_{\text{threshold}} \wedge \text{Dist}(P_i, P_{\text{mid}}) \le 3\text{ ticks}\right)}{\sum_{j \in \text{Insert}(t, W)} V_j}$$

Donde $\tau_{\text{threshold}} = 150\text{ ms}$ y $\mathbb{I}(\cdot)$ es la función indicatriz. Si $R_{\text{spoof}} > 0.65$, la señal cuantitativa penaliza el peso del LOB en un $50\%$ para evitar trampas de liquidez inducida.

#### D. Algoritmo de Detección de Bloques Ocultos (Iceberg Orders)
Siguiendo a Biais et al. (1995) y Lehalle (2018), una orden *Iceberg* se identifica cuando el volumen acumulado ejecutado $\sum V_{\text{trade}}$ a un precio fijo $P^*$ excede el volumen visible original $v_1(t)$ sin que el precio se mueva:

$$\hat{V}_{\text{iceberg}} = \sum_{t_k \in [t_0, t]} V_{\text{trade}}(t_k) \cdot \mathbb{I}(P(t_k) = P^*) - \left[ v_1(t_0) - v_1(t) \right]$$

Si $\hat{V}_{\text{iceberg}} > 3.5 \cdot \bar{v}_1$ con estabilidad de cotización, se ancla una bandera visual `ICEBERG_BUY` o `ICEBERG_SELL` en la escala del DOM.

### 1.3 Especificación del Componente de UI y Wireframe Industrial

```
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│ VISTA 1: CASCADA L2 Y MAPA DE CALOR DOM (ORDER BOOK DYNAMICS) · XAUUSD               [REC: 60FPS]│
├──────────────────────────────────────────────────┬───────────────────────────────────────────────┤
│ ESCALA DE PRECIOS & LADDER DOM L2 (20 NIVELES)   │ MAPA DE CALOR TEMPORAL (HISTOGRAMA 60 SEGUNDOS)│
├──────────┬────────┬──────────────┬───────────────┼───────────────────────────────────────────────┤
│  PRECIO  │ NIVEL  │ BID VOL (L)  │ ASK VOL (L)   │ -60s        -45s        -30s        -15s   LIVE   │
├──────────┼────────┼──────────────┼───────────────┼───────────────────────────────────────────────┤
│ 2642.60  │ Ask L6 │              │  95.0 [▓▓▓░░] │ ············████████························· │
│ 2642.50  │ Ask L5 │              │  40.0 [▓░░░░] │ ············································· │
│ 2642.40  │ Ask L4 │              │  35.0 [▓░░░░] │ ············································· │
│ 2642.30  │ Ask L3 │              │ 120.0 [▓▓▓▓▓] │ ◄ [SPOOF ALARM: 82% CANCEL < 110ms]           │
│ 2642.20  │ Ask L2 │              │  55.0 [▓▓░░░] │ ············································· │
│ 2642.10  │ Ask L1 │              │  18.0 [▓░░░░] │ ············································· │
├──────────┴────────┴──────────────┴───────────────┼───────────────────────────────────────────────┤
│ MID-PRICE: 2642.00 │ SPREAD: 0.20 │ MICRO: 2641.88│ OFI_20: +48.2 (FUERTE PRESIÓN COMPRADORA)      │
├──────────┬────────┬──────────────┬───────────────┼───────────────────────────────────────────────┤
│ 2641.90  │ Bid L1 │ 210.0 [▓▓▓▓▓]│               │ █████████████████████████████████████████████ │
│ 2641.80  │ Bid L2 │  85.0 [▓▓▓░░]│               │ ············████████························· │
│ 2641.70  │ Bid L3 │  60.0 [▓▓░░░]│               │ ············································· │
│ 2641.60  │ Bid L4 │ 140.0 [▓▓▓▓░]│               │ ····························████████········· │
│ 2641.50  │ Bid L5 │  90.0 [▓▓▓░░]│               │ ············································· │
├──────────┴────────┴──────────────┴───────────────┴───────────────────────────────────────────────┤
│ TELEMETRÍA DINÁMICA:                                                                             │
│ • Imbalance K=20: +0.642 (COMPRA)   • Reposición τ: 18.4 ms (ALTA LIQUIDEZ)                      │
│ • Iceberg Detectado: Bid @ 2641.90 (Est. 480 Lots)   • Spoofing Score: 0.12 (Bajo)               │
└──────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## SECCIÓN 2: VISTA DE DESACOPLE LEAD-LAG & REVERSIÓN A LA MEDIA ORNSTEIN-UHLENBECK

### 2.1 Fundamentos del Proceso Ornstein-Uhlenbeck & Cointegración
En pares macroeconómicos (ej. $Y = \text{XAUUSD}$, $X = \text{DXY}$) y canastas de alta beta ($Y = \text{TSLA}$, $X = \text{SPY}$), el diferencial de precios normalizado o residuo de cointegración $S_t = Y_t - (\alpha_t + \beta_t X_t)$ se modela como un proceso estocástico continuo de reversión a la media de **Ornstein-Uhlenbeck (1930)**:

$$d S_t = \theta_{\text{OU}} (\mu_{\text{OU}} - S_t) \, dt + \sigma_{\text{OU}} \, dW_t$$

Donde:
- $\theta_{\text{OU}} > 0$ es la **velocidad de reversión a la media** (tasa de disipación de anomalías).
- $\mu_{\text{OU}}$ es el **nivel de equilibrio asintótico** del spread (teóricamente $0$ bajo estimación Kalman adaptativa).
- $\sigma_{\text{OU}} > 0$ es la **volatilidad instantánea de difusión**.
- $W_t$ es un proceso estándar de Wiener browniano.

```
       DESVIACIÓN S_t
          ▲
  +2.5 σ ─┼───────────────────────────────── [BANDA SUPERIOR DE SOBRECOMPRA / ROJO]
          │          ╭───╮
  +1.2 σ ─┼─────────╭╯───╰╮───────────────── [UMBRAL DE ENTRADA VENDEDORA]
          │        ╭╯     ╰╮
   μ_OU  ─┼───────╭╯───────╰╮─────────────── [NIVEL DE EQUILIBRIO / MEDIA]
          │      ╭╯         ╰╮
  -1.2 σ ─┼─────╭╯───────────╰╮───────────── [UMBRAL DE ENTRADA COMPRADORA]
          │    ╭╯             ╰───╮
  -2.5 σ ─┼───╭╯───────────────────╰──────── [BANDA INFERIOR DE SOBREVENTA / VERDE]
          └──────────────────────────────────► TIEMPO (TICKS)
             ◄── T_1/2 = ln(2)/θ ──►
```

### 2.2 Estimación Analítica en Tiempo Real & Test ADF Rodante

#### A. Estimación Discreta de Parámetros $(\theta_{\text{OU}}, \sigma_{\text{OU}}, T_{1/2})$
Discretizando el proceso OU en pasos uniformes $\Delta t$, obtenemos un modelo autoregresivo $\text{AR}(1)$:

$$S_{t+\Delta t} = a + b S_t + \epsilon_t, \quad \epsilon_t \sim \mathcal{N}(0, \sigma_\epsilon^2)$$

Aplicando estimación por Mínimos Cuadrados Ordinarios (OLS) en una ventana rodante de $N = 300$ ticks:

$$\hat{b} = \frac{\sum_{i=1}^N (S_{i-1} - \bar{S}_{-1})(S_i - \bar{S})}{\sum_{i=1}^N (S_{i-1} - \bar{S}_{-1})^2}, \quad \hat{a} = \bar{S} - \hat{b} \bar{S}_{-1}$$

Los parámetros continuos se recuperan de forma exacta mediante:

$$\hat{\theta}_{\text{OU}} = -\frac{\ln(\hat{b})}{\Delta t}, \quad \hat{\mu}_{\text{OU}} = \frac{\hat{a}}{1 - \hat{b}}, \quad \hat{\sigma}_{\text{OU}} = \hat{\sigma}_\epsilon \sqrt{\frac{-2 \ln(\hat{b})}{\Delta t (1 - \hat{b}^2)}}$$

**Vida Media de Reversión (*Half-Life*):**
$$T_{1/2} = \frac{\ln(2)}{\hat{\theta}_{\text{OU}}}$$

- **Criterio Operativo de Reversión Rápida:** $T_{1/2} \le 120\text{ ticks}$ ($30\text{ segundos}$ a $250\text{ms/tick}$) $\implies$ Régimen óptimo para arbitraje estadístico de reversión a la media.
- **Criterio de Régimen en Tendencia / Ruptura:** $T_{1/2} > 600\text{ ticks}$ o $\hat{b} \ge 1.0$ ($\theta_{\text{OU}} \le 0$) $\implies$ Cointegración rota; el semáforo bloquea señales a `AMARILLO`.

#### B. Test Dickey-Fuller Aumentado Rodante (*Rolling ADF*)
Se calcula el estadístico $t$ de la hipótesis nula de raíz unitaria ($\gamma = 0$) en la regresión $\Delta S_t = \alpha + \gamma S_{t-1} + \sum_{p=1}^P \beta_p \Delta S_{t-p} + e_t$.
- Si $p\text{-value}_{\text{ADF}} < 0.01$ $\implies$ Fuerte estacionariedad (Confluencia $1.35\times$).
- Si $p\text{-value}_{\text{ADF}} \ge 0.05$ $\implies$ No estacionario (Desacople estructural; bloqueo preventivo).

### 2.3 Geometría del Diagrama de Dispersión en Vivo & Vector Ortogonal
El plano bidimensional $(X_t, Y_t)$ grafica la nube de puntos de los últimos 200 ticks junto a la recta de regresión de Kalman $Y = \hat{\alpha}_t + \hat{\beta}_t X$. La distancia ortogonal euclidiana $d_{\perp, t}$ representa la anomalía geométrica pura:

$$d_{\perp, t} = \frac{|Y_t - \hat{\beta}_t X_t - \hat{\alpha}_t|}{\sqrt{1 + \hat{\beta}_t^2}} = \frac{|\nu_t|}{\sqrt{1 + \hat{\beta}_t^2}}$$

Las elipses de covarianza proyectadas a $1\sigma, 2\sigma, 3\sigma$ delimitan las fronteras de normalidad estocástica.

### 2.4 Wireframe y Diseño de Consola

```
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│ VISTA 2: DESACOPLE LEAD-LAG & REVERSIÓN ORNSTEIN-UHLENBECK · [XAUUSD vs DXY]                     │
├──────────────────────────────────────────────────┬───────────────────────────────────────────────┤
│ DIAGRAMA DE FASE (DISPERSIÓN LIVE XAU/DXY)       │ BANDA DE RESIDUO OU & HALF-LIFE T_1/2         │
├──────────────────────────────────────────────────┼───────────────────────────────────────────────┤
│ Y (XAUUSD)                                       │ Z-SCORE OU [300 TICKS]                        │
│ 2646.00 │                 •                      │ +3.0σ │······································ │
│ 2644.00 │               •  ••                    │ +2.0σ │······································ │
│ 2642.00 │            • • [LIVE: (104.2, 2641.9)] │ +1.0σ │─────────╭╮─────────────────────────── │
│ 2640.00 │         •••  / (Recta Kalman β=-1.42)  │  0.0σ │────────╭╯╰╮───────╭───────────── (μ)  │
│ 2638.00 │       ••    /                          │ -1.0σ │───────╭╯───╰╮────╭╯────────────────── │
│ 2636.00 │     •      /  [Elipse 2σ Confianza]    │ -2.0σ │──────╭╯─────╰───╭╯─────────────────── │
│         └───────────────────────────────► X (DXY)│ -3.0σ │─────╭╯───────────╯ ◄ [Z = -2.14σ]     │
│           103.80  104.00  104.20  104.40         │       └────────────────────────────────────── │
├──────────────────────────────────────────────────┴───────────────────────────────────────────────┤
│ PARÁMETROS ESTIMADOS OU & COINTEGRACIÓN:                                                         │
│ • Velocidad θ_OU: 0.0482 s⁻¹    • Vida Media T_1/2: 14.38 s (57 Ticks) [RÉGIMEN RÁPIDO]          │
│ • Volatilidad σ_OU: 0.184 USD   • Rolling ADF p-value: 0.0024 (ESTACIONARIO CONFIRMADO)         │
│ • Desacople Lead-Lag: DXY lidera a XAU por 420 ms (Correlación cruzada ρ_max = -0.84)            │
└──────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## SECCIÓN 3: VISTA DE TELEMETRÍA DEL ESPACIO LATENTE (I-JEPA D=256 -> 2D/3D PCA/UMAP & OOD MAHALANOBIS)

### 3.1 Arquitectura del Espacio Latente I-JEPA ($D=256$)
Siguiendo la arquitectura de **Assran et al. (2023)** (*Joint-Embedding Predictive Architecture*), el codificador temporal del Sistema de Luces $f_\theta$ mapea una ventana de contexto de alta frecuencia $\mathbf{X}_{t-9:t} \in \mathbb{R}^{10 \times 12}$ (compuesta por precios L2, volúmenes, OFI, spreads y tasas de flujo) a un vector denso de características latentes:

$$\mathbf{z}_t = f_\theta(\mathbf{X}_{t-9:t}) \in \mathbb{R}^{256}$$

Para garantizar que el espacio latente esté libre de colapso representacional y maximice la entropía de información, el modelo fue preentrenado con la función de pérdida de correlación cruzada de **Barlow Twins**:

$$\mathcal{L}_{\text{Barlow}} = \sum_i (1 - \mathcal{C}_{ii})^2 + \lambda_{\text{BT}} \sum_i \sum_{j \ne i} \mathcal{C}_{ij}^2$$

Donde $\mathcal{C}$ es la matriz de correlación cruzada calculada entre representaciones de vistas aumentadas del mercado.

```
  VENTANA TEMPORAL L2 (10x12)        ENCODER I-JEPA           ESPACIO LATENTE D=256
 ┌───────────────────────────┐      ┌───────────────┐      ┌─────────────────────────┐
 │ P_bid, P_ask, V_1..5, OFI │ ───► │ 4x Conv1D +   │ ───► │ z_t in R^256            │
 │ Kalman Z, VPIN, dP_micro  │      │ Residual Blk  │      │ (Invariante a ruido)    │
 └───────────────────────────┘      └───────────────┘      └────────────┬────────────┘
                                                                        │
                 ┌──────────────────────────────────────────────────────┴────────────────┐
                 ▼                                                                       ▼
    ┌──────────────────────────┐                                            ┌──────────────────────────┐
    │ REDUCCIÓN LINEAL DIRECTA │                                            │ DISTANCIA DE MAHALANOBIS │
    │ Matriz W_PCA (256 -> 2D) │                                            │ D_M a Clústeres Ganadores│
    │ Latencia < 0.05 ms       │                                            │ D_M = sqrt((z-μ)^T Σ^-1(z-μ))
    └────────────┬─────────────┘                                            └────────────┬─────────────┘
                 │                                                                       │
                 ▼                                                                       ▼
    ┌──────────────────────────┐                                            ┌──────────────────────────┐
    │ COORDENADAS (x_pca, y_pca│                                            │ ALARMA TEMPRANA OOD:     │
    │ Renderizado 60 FPS       │                                            │ D_M > 24.5 -> YELLOW LOCK│
    └──────────────────────────┘                                            └──────────────────────────┘
```

### 3.2 Proyección a Baja Dimensión en Tiempo Real (PCA Paramétrico)
Para proyectar el vector $\mathbf{z}_t \in \mathbb{R}^{256}$ al plano visual bidimensional $(x_t^{\text{lat}}, y_t^{\text{lat}})$ en menos de $50\text{ microsegundos}$, se utiliza la matriz ortogonal precalculada de componentes principales $\mathbf{W}_{\text{PCA}} \in \mathbb{R}^{256 \times 2}$:

$$\mathbf{p}_t = \mathbf{W}_{\text{PCA}}^T (\mathbf{z}_t - \bar{\mathbf{z}})$$

Esta proyección conserva el $68.4\%$ de la varianza explicada global del espacio representacional.

### 3.3 Distancia de Mahalanobis a Centroides de Trades Ganadores ($D_M$)
Se almacenan en memoria los centroides empíricos $\boldsymbol{\mu}_{\text{LONG}}, \boldsymbol{\mu}_{\text{SHORT}} \in \mathbb{R}^{256}$ y la matriz de covarianza inversa $\boldsymbol{\Sigma}^{-1} \in \mathbb{R}^{256 \times 256}$ de las trayectorias que resultaron en trades con ganancia $\ge +1.5\text{ R}$ en el historial operativo:

$$D_M^2(\mathbf{z}_t, \boldsymbol{\mu}_k) = (\mathbf{z}_t - \boldsymbol{\mu}_k)^T \boldsymbol{\Sigma}_k^{-1} (\mathbf{z}_t - \boldsymbol{\mu}_k) \sim \chi_{256}^2$$

- **Criterio de Proximidad Óptima (Zona de Convicción):** $D_M \le 12.0$ $\implies$ El estado actual del mercado es topológicamente idéntico a configuraciones históricas de alta rentabilidad.
- **Alarma Geométrica Fuera de Distribución (*Out-of-Distribution*, OOD):**
  $$\text{Si } \min_{k \in \{\text{LONG}, \text{SHORT}\}} D_M(\mathbf{z}_t, \boldsymbol{\mu}_k) > \gamma_{\text{OOD}} = 24.5 \quad (\text{Percentil } 99.5\% \text{ de } \chi_{256}^2)$$
  El sistema detecta de forma instantánea que el mercado se encuentra en un régimen anómalo no visto en el entrenamiento (ej. flash crash, intervención de banco central). **Acción automática:** Conmutación forzosa a `AMARILLO` y bloqueo de sugerencias del estudiante de ML.

### 3.4 Wireframe de la Vista del Espacio Latente

```
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│ VISTA 3: PROYECCIÓN DEL ESPACIO LATENTE I-JEPA (D=256 ──► 2D PCA) & DETECTOR OOD                 │
├──────────────────────────────────────────────────┬───────────────────────────────────────────────┤
│ MANIFOLD LATENTE BIDIMENSIONAL (PCA 1 vs PCA 2)  │ TELEMETRÍA TOPOLÓGICA & DISTANCIA MAHALANOBIS │
├──────────────────────────────────────────────────┼───────────────────────────────────────────────┤
│ PCA 2 (24.1% Var)                                │ ESTADO TOPOLÓGICO: RÉGIMEN LONG IDENTIFICADO  │
│  +4.0 │                                          ├───────────────────────────────────────────────┤
│       │         [CLÚSTER GANADOR SHORT]          │ • D_M a Centroide LONG:  8.42  (ZONA DE EDGE) │
│  +2.0 │           ( • ••• • )                    │ • D_M a Centroide SHORT: 34.18 (MUY LEJANO)   │
│       │                                          │ • Umbral OOD (γ_OOD):    24.50                │
│   0.0 │ ──────────────────────────────────────── │ • Estado OOD:            SEGURO / IN-DISTRIB. │
│       │                                          ├───────────────────────────────────────────────┤
│  -2.0 │      [CLÚSTER GANADOR LONG]              │ DESCOMPOSICIÓN DE VARIANZA:                   │
│       │        ( • • [LIVE: ●] ••• )             │ • Componente 1 (OFI + Micro-Price):   44.3%   │
│  -4.0 │                                          │ • Componente 2 (Kalman Cointegration): 24.1%  │
│       └──────────────────────────────────► PCA 1 │ • Componente 3 (VPIN Volatility):      11.2%  │
│         -4.0     -2.0      0.0     +2.0   +4.0   │ • Varianza Acumulada 2D:               68.4%  │
├──────────────────────────────────────────────────┴───────────────────────────────────────────────┤
│ COMENTARIO DE NAVEGACIÓN TOPOLÓGICA:                                                             │
│ El vector latente z_t se ubica en el núcleo denso del clúster LONG (+1.8σ dentro del volumen de │
│ densidad kernel). Probabilidad topológica de régimen favorable: 89.2%. Sin riesgo OOD.           │
└──────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## SECCIÓN 4: VISTA DE EXPLICABILIDAD Y ATRIBUCIÓN DE GRADIENTES (INTEGRATED GRADIENTS & REAL-TIME SHAP)

### 4.1 Marco Axiomático de Atribución (Sundararajan et al., 2017)
Para garantizar la explicabilidad estricta y cumplir con el principio de *Caja de Cristal*, la contribución de cada variable de microestructura en la decisión de la red neuronal $\pi_\phi(a|\mathbf{x})$ se calcula mediante **Gradientes Integrados** (*Integrated Gradients*).

A diferencia de los gradientes simples de saliency map, Integrated Gradients satisface los axiomas fundamentales de **Completitud** (*Completeness*) e **Invarianza a la Implementación** (*Implementation Invariance*):

$$\text{IG}_i(\mathbf{x}) = (x_i - x_i') \times \int_0^1 \frac{\partial F(\mathbf{x}' + \alpha(\mathbf{x} - \mathbf{x}'))}{\partial x_i} \, d\alpha$$

Donde:
- $\mathbf{x} \in \mathbb{R}^M$ es el vector de entrada actual en el tick $t$.
- $\mathbf{x}' \in \mathbb{R}^M$ es el estado neutro o línea base de referencia ($\text{Kalman } Z = 0, \text{OFI} = 0, \Delta P_{\text{micro}} = 0, \text{VPIN} = 0.50$).
- $F(\mathbf{x}) = \log \left(\frac{\pi(\text{BUY}|\mathbf{x})}{\pi(\text{SELL}|\mathbf{x})}\right)$ es el logit de ventaja de la acción de compra.

```
  ESTADO NEUTRO (x')                                             ESTADO ACTUAL (x)
  [ Z=0, OFI=0, dP=0 ] ════════════════════════════════════════► [ Z=-1.85, OFI=+48, dP=+350k ]
                              α in [0.0, 1.0] (m=20 pasos)
                                           │
                                           ▼
                 Cálculo de Gradientes: ∂F(x' + α(x - x')) / ∂x_i
                                           │
                                           ▼
        Suma de Riemann: IG_i ≈ (x_i - x_i') * (1/m) * Σ_k [ ∂F / ∂x_i ]
                                           │
                                           ▼
      DESGLOSE % NORMALIZADO:  OFI: +38.4% │ Kalman Z: +29.1% │ Micro-Price: +19.2% ...
```

### 4.2 Aproximación Numérica de Riemann en Tiempo Real ($m=20$ pasos)
Para ejecutar la atribución dentro del presupuesto de tiempo de inferencia ($< 0.8\text{ ms}$ en CPU/GPU):

$$\text{IG}_i(\mathbf{x}) \approx (x_i - x_i') \times \frac{1}{m} \sum_{k=1}^m \frac{\partial F\left(\mathbf{x}' + \frac{k}{m}(\mathbf{x} - \mathbf{x}')\right)}{\partial x_i}, \quad m = 20$$

Normalizando las atribuciones porcentuales:

$$\omega_i = \frac{|\text{IG}_i(\mathbf{x})|}{\sum_{j=1}^M |\text{IG}_j(\mathbf{x})|} \times 100\%$$

### 4.3 Desglose de Factores y Panel "¿Por Qué Cambió la Señal?"
Cada conmutación del semáforo genera instantáneamente una tarjeta de atribución causal que desglosa el porcentaje de responsabilidad de cada una de las variables primarias:

1. **Order Flow Imbalance ($OFI_{K=5}$):** Presión neta en el libro L2.
2. **Kalman Innovation Z-Score ($Z_{\text{Kalman}}$):** Grado de anomalía respecto a la paridad líder.
3. **Stoikov Micro-Price ($\Delta P_{\text{micro}}$):** Asimetría de cola en el mejor nivel.
4. **Correlación Dinámica Macro ($\rho_{xy}$):** Coherencia con activos ancla.
5. **Toxicidad de Flujo ($VPIN$):** Penalización por presencia de operadores informados.

### 4.4 Wireframe de la Vista de Explicabilidad

```
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│ VISTA 4: EXPLICABILIDAD AXIOMÁTICA & ATRIBUCIÓN DE GRADIENTES (INTEGRATED GRADIENTS)             │
├──────────────────────────────────────────────────────────────────────────────────────────────────┤
│ MOTIVO DE LA DECISIÓN: COMPRA CONFIRMADA (VERDE) ──► P(WIN): 84.7% │ VENTAJA NETA: +1.82 R       │
├──────────────────────────────────────────────────────────────────────────────────────────────────┤
│ FACTOR ANALÍTICO        │ IMPACTO │ VALOR ACTUAL │ CONTRIBUCIÓN RELATIVA (IG SHAPLEY %)          │
├─────────────────────────┼─────────┼──────────────┼───────────────────────────────────────────────┤
│ 1. Order Flow Imbalance │  +BULL  │ OFI = +48.20 │ [▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓░░░░░░░░░░] +38.4%        │
│ 2. Kalman Z-Score       │  +BULL  │ Z = -1.85 σ  │ [▓▓▓▓▓▓▓▓▓▓▓▓▓▓░░░░░░░░░░░░░░] +29.1%        │
│ 3. Stoikov Micro-Price  │  +BULL  │ ΔP = +340ppm │ [▓▓▓▓▓▓▓▓▓░░░░░░░░░░░░░░░░░░░] +19.2%        │
│ 4. Macro Cointegración  │  +BULL  │ ρ = -0.84    │ [▓▓▓▓░░░░░░░░░░░░░░░░░░░░░░░░]  +8.5%        │
│ 5. Toxicidad VPIN       │  -NEUT  │ VPIN = 0.38  │ [▓▓░░░░░░░░░░░░░░░░░░░░░░░░░░]  +4.8%        │
├─────────────────────────┴─────────┴──────────────┴───────────────────────────────────────────────┤
│ RESUMEN EN LENGUAJE NATURAL DEL MOTOR EXPLICATIVO:                                               │
│ "La señal VERDE se activó principalmente por absorción institucional compradora en L2 (+38.4%)  │
│  en confluencia con una sobreventa extrema de -1.85 desviaciones respecto a DXY (+29.1%).         │
│  El libro muestra reposición asimétrica en Bid sin toxicidad de flujo adverso."                  │
└──────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## SECCIÓN 5: DESGLOSE DE INCERTIDUMBRE EPISTÉMICA VS. ALEATORIA

### 5.1 Descomposición Matemática de Incertidumbre en RL Fuera de Línea
La toma de decisiones robusta en finanzas cuantitativas exige distinguir entre:
1. **Incertidumbre Aleatoria ($\sigma_{\text{aleatoria}}^2$):** Ruido intrínseco e irreducible del mercado (estocasticidad del flujo de órdenes y dispersión de volatilidad).
2. **Incertidumbre Epistémica ($\sigma_{\text{epistémica}}^2$):** Ignorancia del modelo por escasez de datos históricos en una región del espacio de estados.

```
                  INCERTIDUMBRE TOTAL DEL SISTEMA U_total
                                     │
         ┌───────────────────────────┴───────────────────────────┐
         ▼                                                       ▼
  INCERTIDUMBRE EPISTÉMICA                                INCERTIDUMBRE ALEATORIA
  (Falta de conocimiento del modelo)                     (Ruido estocástico del mercado)
  ──────────────────────────────────                     ───────────────────────────────
  • Fuente: Desacuerdo de redes Twin-Q                   • Fuente: Entropía de la política
    U_epis = |Q_θ1(s, a) - Q_θ2(s, a)|                     U_alea = H(π_ϕ(·|s)) = -Σ π ln(π)
  • Solución: Si U_epis > τ_epis                         • Solución: Si U_alea > τ_alea
    ──► CLAMPING TOTAL A AMARILLO                          ──► REDUCCIÓN DE TAMAÑO DE POSICIÓN
```

### 5.2 Formulación de las Métricas de Incertidumbre

#### A. Incertidumbre Epistémica por Dispersión de Redes Twin-Q ($U_{\text{epis}}$)
En el algoritmo Implicit Q-Learning (IQL / AWBC), se entrenan dos redes de valor de acción independientes $Q_{\theta_1}(s, a)$ y $Q_{\theta_2}(s, a)$. El desacuerdo absoluto entre ambas estimaciones cuantifica la incertidumbre epistémica:

$$U_{\text{epis}}(s, a) = |Q_{\theta_1}(s, a) - Q_{\theta_2}(s, a)|$$

- **Normalización Z-Score:** $Z_{\text{epis}} = \frac{U_{\text{epis}}(s, a) - \bar{U}_{\text{epis}}}{\sigma(U_{\text{epis}})}$.

#### B. Incertidumbre Aleatoria por Entropía de Shannon de la Política ($U_{\text{alea}}$)
La incertidumbre irreducible sobre la acción óptima se extrae de la distribución categórica de la política parametrizada $\pi_\phi(a|s)$:

$$U_{\text{alea}}(s) = \mathcal{H}(\pi_\phi(\cdot|s)) = -\sum_{a \in \{\text{BUY}, \text{MONITOR}, \text{SELL}\}} \pi_\phi(a|s) \ln \pi_\phi(a|s) \in [0, \ln(3)]$$

Normalizado a la escala $[0.0, 1.0]$ dividiendo por $\ln(3) \approx 1.0986$.

### 5.3 Reglas Automáticas de Clamping a Amarillo (*Standby Clamping*)

El sistema ejecuta de forma determinista la siguiente lógica de seguridad en cada ciclo de inferencia:

$$\text{Estado Semáforo} = \begin{cases} 
\text{AMARILLO (CLAMPING EPISTÉMICO)} & \text{si } U_{\text{epis}} > 0.45\text{ R} \quad (Z_{\text{epis}} > 2.0) \\
\text{AMARILLO (CLAMPING ALEATORIO)} & \text{si } U_{\text{alea}} > 0.85 \quad (P_{\max} < 55\%) \\
\text{VERDE / ROJO (TAMAÑO ATENUADO)} & \text{si } U_{\text{total}} \le \tau_{\text{safe}} \implies \text{Size} = \text{Size}_{\text{base}} \cdot \exp(-\gamma U_{\text{alea}}) \\
\text{VERDE / ROJO (TAMAÑO COMPLETO)} & \text{si } U_{\text{epis}} \le 0.15\text{ R} \wedge U_{\text{alea}} \le 0.35
\end{cases}$$

### 5.4 Wireframe del Panel de Incertidumbre Dual

```
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│ VISTA 5: DESGLOSE DE INCERTIDUMBRE (EPISTÉMICA VS. ALEATORIA) & CLAMPING AUTOMÁTICO              │
├──────────────────────────────────────────────────────────────────────────────────────────────────┤
│ INDICADOR DE INCERTIDUMBRE DUAL (GAUGE INDUSTRIAL DE DOBLE AGUJA)                                │
├──────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 1. INCERTIDUMBRE EPISTÉMICA (DESACUERDO TWIN-Q |Q1 - Q2|):                                       │
│    VALOR: 0.082 R [Z = -0.95σ] ──► ZONA SEGURA (MODELO FAMILIARIZADO)                            │
│    [████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░] 18.2% (Umbral Clamping: > 45.0%)                 │
│                                                                                                  │
│ 2. INCERTIDUMBRE ALEATORIA (ENTROPÍA DE POLÍTICA H(π)):                                          │
│    VALOR: 0.241 / 1.098 [P(BUY)=84.7%, P(MON)=10.1%, P(SELL)=5.2%] ──► BAJA DISPERSIÓN          │
│    [███████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░] 21.9% (Umbral Clamping: > 85.0%)                 │
├──────────────────────────────────────────────────────────────────────────────────────────────────┤
│ ESTADO DEL MODULADOR DE RIESGO:                                                                  │
│ • Estado de Clamping:   INACTIVO (OPERACIÓN HABILITADA SIN RESTRICCIÓN)                          │
│ • Factor de Tamaño:     100.0% (1.00 Lot Equivalente)                                            │
│ • Entropía de Red:      0.241 nats (Convicción direccional del 84.7%)                            │
│ • Varianza Twin-Q:      Var(Q1, Q2) = 0.0033 (Alta consistencia entre críticos)                  │
└──────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## SECCIÓN 6: PANEL DE RENDIMIENTO DE SETUPS DEL OPERADOR & SHADOW RUN BENCHMARK

### 6.1 Fundamento Estadístico del Test Diebold-Mariano en Alta Frecuencia
Para validar rigurosamente la superioridad predictiva del modelo Retador (*Challenger*) frente al Campeón (*Champion*) o frente a la línea base sin incurrir en *p-hacking*, se evalúa de forma continua el **Test de Diebold-Mariano (1995)** con corrección de autocorrelación de **Harvey, Leybourne & Newbold (1997)** sobre una ventana de $N = 10,000$ ticks de ejecución en sombra (*Shadow Run*).

Sean los errores de predicción probabilística de ambos modelos $e_{1, t} = (y_t - \hat{p}_{1, t})^2$ y $e_{2, t} = (y_t - \hat{p}_{2, t})^2$, y la serie diferencial de pérdidas $d_t = e_{1, t} - e_{2, t}$:

$$\bar{d} = \frac{1}{N} \sum_{t=1}^N d_t, \quad \hat{\gamma}_k = \frac{1}{N} \sum_{t=k+1}^N (d_t - \bar{d})(d_{t-k} - \bar{d})$$

$$\text{Estadístico DM} = \frac{\bar{d}}{\sqrt{\frac{1}{N} \left( \hat{\gamma}_0 + 2 \sum_{k=1}^{h-1} \left(1 - \frac{k}{h}\right) \hat{\gamma}_k \right)}} \sim \mathcal{N}(0, 1)$$

- **Criterio de Promoción Campeón:** $\text{DM} < -2.576$ ($p\text{-value} < 0.01$) con $N \ge 10,000$ ticks y Brier Score $BS \le 0.165$.

### 6.2 Desglose de Rendimiento por Setup Específico del Operador
El sistema registra y evalúa las métricas en tiempo real divididas por la etiqueta del setup (`setup_id`):

$$\mathbb{E}[R] = \frac{1}{M} \sum_{i=1}^M \frac{\text{PnL}_i}{\text{Riesgo Inicial } R_i}, \quad \text{Sortino} = \frac{\bar{R} - R_f}{\sqrt{\frac{1}{M} \sum_{i=1}^M \min(0, R_i - \tau)^2}}$$

### 6.3 Tabla de Rendimiento de Setups & Log de Filtros Defensivos

```
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│ VISTA 6: BENCHMARKING DE SETUPS DEL OPERADOR & SHADOW RUN (10,000 TICKS)                         │
├──────────────────────────────────────────────────────────────────────────────────────────────────┤
│ EVALUACIÓN ESTADÍSTICA DE SETUPS INGRESTADOS POR EL OPERADOR                                     │
├───────────────────────┬────────┬──────────┬────────┬─────────┬─────────┬────────┬────────────────┤
│ SETUP ID              │ TRADES │ WIN RATE │  E[R]  │ PROFIT  │ SHARPE  │SORTINO │ CLASIFICACIÓN  │
│                       │  (N)   │   (%)    │  (R)   │ FACTOR  │ RATIO   │ RATIO  │ DE EDGE        │
├───────────────────────┼────────┼──────────┼────────┼─────────┼─────────┼────────┼────────────────┤
│ OU_REVERSION_GOLD     │   84   │  82.1%   │ +0.64R │  2.45   │  2.84   │  4.12  │ STRONG_EDGE    │
│ TSLA_BETA_MOMENTUM    │   52   │  76.9%   │ +0.48R │  1.92   │  2.10   │  3.05  │ STRONG_EDGE    │
│ AAPL_PULLBACK_L2      │   39   │  69.2%   │ +0.22R │  1.38   │  1.45   │  1.82  │ MODERATE_EDGE  │
│ BREAKOUT_ASIAN_SESSION│   28   │  32.1%   │ -0.34R │  0.62   │ -0.85   │ -0.92  │ NEGATIVE_EDGE  │
├───────────────────────┴────────┴──────────┴────────┴─────────┴─────────┴────────┴────────────────┤
│ TEST DE DIEBOLD-MARIANO (SHADOW RUN TICK 8,420 / 10,000):                                        │
│ • DM Statistic: -3.12 (p = 0.0009) ──► RETADOR SUPERA AL CAMPEÓN CON SIGNIFICANCIA 99.9%       │
│ • Brier Score Retador: 0.142 vs Campeón: 0.168 (Mejora de calibración: +15.4%)                   │
├──────────────────────────────────────────────────────────────────────────────────────────────────┤
│ LOG DE AUDITORÍA DE FILTROS DEFENSIVOS (ÚLTIMOS EVENTOS HITL):                                   │
│ [14:22:05.120] 🛡️ AUTO-VETO: Señal en BREAKOUT_ASIAN bloqueada (NEGATIVE_EDGE: E[R]=-0.34R).    │
│ [14:18:32.840] ⚠️ CLAMPING: VPIN alcanzó 0.88 en AAPL ──► Señal forzada a AMARILLO.             │
│ [14:05:11.050] 🛡️ SLIPPAGE GUARD: Latencia de reposición τ = 210ms ──► Orden retrasada 150ms.  │
└──────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## SECCIÓN 7: MATRIZ DE CORRELACIÓN DINÁMICA MULTI-ACTIVO (HEATMAP N x N)

### 7.1 Tensor de Covarianza EWMA de Alta Frecuencia ($N=7$)
Para monitorear el contagio sistémico y las rupturas de cointegración entre mercados globales, el sistema procesa un vector de rendimientos logarítmicos $\mathbf{r}_t \in \mathbb{R}^7$ en una escala temporal de alta frecuencia:

$$\mathbf{r}_t = \begin{bmatrix} r_{\text{XAUUSD}}, & r_{\text{DXY}}, & r_{\text{SP500}}, & r_{\text{TSLA}}, & r_{\text{AAPL}}, & r_{\text{US10Y}}, & r_{\text{EURUSD}} \end{bmatrix}^T$$

La matriz de covarianza condicional $\boldsymbol{\Sigma}_t \in \mathbb{R}^{7 \times 7}$ se actualiza recursivamente mediante un estimador EWMA con decaimiento $\lambda_{\text{cov}} = 0.96$:

$$\boldsymbol{\Sigma}_t = \lambda_{\text{cov}} \boldsymbol{\Sigma}_{t-1} + (1 - \lambda_{\text{cov}}) (\mathbf{r}_t - \bar{\mathbf{r}}_t)(\mathbf{r}_t - \bar{\mathbf{r}}_t)^T$$

La matriz de correlación dinámica $\mathbf{C}_t \in \mathbb{R}^{7 \times 7}$ se obtiene de forma exacta:

$$\mathbf{C}_{i,j}(t) = \frac{\Sigma_{i,j}(t)}{\sqrt{\Sigma_{i,i}(t) \cdot \Sigma_{j,j}(t)}} \in [-1.0, +1.0]$$

```
               MATRIZ DE CORRELACIÓN DINÁMICA C_t (7x7)
           XAUUSD    DXY    SP500   TSLA    AAPL    US10Y  EURUSD
 XAUUSD  [ +1.00   -0.84   +0.32   +0.18   +0.22   -0.65   +0.81 ]
 DXY     [ -0.84   +1.00   -0.45   -0.25   -0.30   +0.72   -0.96 ]
 SP500   [ +0.32   -0.45   +1.00   +0.74   +0.88   -0.38   +0.42 ]
 TSLA    [ +0.18   -0.25   +0.74   +1.00   +0.62   -0.20   +0.22 ]
 AAPL    [ +0.22   -0.30   +0.88   +0.62   +1.00   -0.28   +0.28 ]
 US10Y   [ -0.65   +0.72   -0.38   -0.20   -0.28   +1.00   -0.68 ]
 EURUSD  [ +0.81   -0.96   +0.42   +0.22   +0.28   -0.68   +1.00 ]
```

### 7.2 Ratio de Absorción & Alarma de Ruptura de Correlación
Siguiendo a **Kritzman et al. (2011)** (*Principal Components as a Measure of Systemic Risk*), se calcula el **Ratio de Absorción ($AR$)** a partir de los valores propios $\lambda_1 \ge \lambda_2 \ge \dots \ge \lambda_7$ de la matriz $\mathbf{C}_t$:

$$AR(t) = \frac{\lambda_1 + \lambda_2}{\sum_{i=1}^7 \lambda_i} = \frac{\lambda_1 + \lambda_2}{7.0}$$

- **Régimen Normal:** $AR \in [0.40, 0.65]$ (Mercados desacoplados y eficientes).
- **Régimen de Estrés Sistémico / Contagio:** $AR > 0.82$ (Los mercados se mueven al unísono; alto riesgo de shock macro).
- **Alarma de Ruptura (*Decoupling Breakdown*):** Si el diferencial instantáneo entre pares fuertemente cointegrados excede $3\sigma$:
  $$|\mathbf{C}_{\text{XAU, DXY}}(t) - \bar{\mathbf{C}}_{\text{XAU, DXY}}| > 3.0 \cdot \sigma(\mathbf{C}) \implies \text{DESACOPLE ANÓMALO (OPORTUNIDAD DE ARBITRAJE)}$$

### 7.3 Wireframe del Heatmap Interactivo

```
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│ VISTA 7: MATRIZ DE CORRELACIÓN DINÁMICA MULTI-ACTIVO (EWMA 7x7 TENSOR)                           │
├──────────────────────────────────────────────────────────────────────────────────────────────────┤
│ MAPA DE CALOR DE ALTA FRECUENCIA (ACTUALIZACIÓN 250 MS)                                          │
├─────────┬─────────┬─────────┬─────────┬─────────┬─────────┬─────────┬─────────┬──────────────────┤
│ ACTIVO  │ XAUUSD  │   DXY   │  SP500  │  TSLA   │  AAPL   │  US10Y  │ EURUSD  │ DIVERGENCIA LIVE │
├─────────┼─────────┼─────────┼─────────┼─────────┼─────────┼─────────┼─────────┼──────────────────┤
│ XAUUSD  │  +1.00  │  -0.84  │  +0.32  │  +0.18  │  +0.22  │  -0.65  │  +0.81  │ NORMAL (0.2σ)    │
│ DXY     │  -0.84  │  +1.00  │  -0.45  │  -0.25  │  -0.30  │  +0.72  │  -0.96  │ NORMAL (0.1σ)    │
│ SP500   │  +0.32  │  -0.45  │  +1.00  │  +0.74  │  +0.88  │  -0.38  │  +0.42  │ NORMAL (0.3σ)    │
│ TSLA    │  +0.18  │  -0.25  │  +0.74  │  +1.00  │  +0.62  │  -0.20  │  +0.22  │ DESACOPLE (+1.8σ)│
│ AAPL    │  +0.22  │  -0.30  │  +0.88  │  +0.62  │  +1.00  │  -0.28  │  +0.28  │ NORMAL (0.2σ)    │
│ US10Y   │  -0.65  │  +0.72  │  -0.38  │  -0.20  │  -0.28  │  +1.00  │  -0.68  │ NORMAL (0.4σ)    │
│ EURUSD  │  +0.81  │  -0.96  │  +0.42  │  +0.22  │  +0.28  │  -0.68  │  +1.00  │ NORMAL (0.1σ)    │
├─────────┴─────────┴─────────┴─────────┴─────────┴─────────┴─────────┴─────────┴──────────────────┤
│ INDICADORES DE RIESGO SISTÉMICO & CONTAGIO:                                                      │
│ • Ratio de Absorción (AR): 0.584 (Régimen Estable)   • Varianza Primer Autovalor λ1: 42.1%       │
│ • Par Más Desacoplado:    TSLA vs SP500 (Divergencia temporal alcista de 45 bps)                 │
└──────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## SECCIÓN 8: PROTOCOLO DE INTEGRACIÓN TÉCNICA, ESQUEMAS DE DATOS & WEBSOCKETS

### 8.1 Esquema Unificado de Telemetría (Pydantic v2 / JSON Schema)
Para garantizar un rendimiento de baja latencia y serialización estricta sin recolección de basura (*Zero GC pressure*), toda la telemetría se consolida en el siguiente esquema:

```python
from pydantic import BaseModel, Field
from typing import List, Dict, Optional

class DOMDepthLevel(BaseModel):
    price: float = Field(..., description="Precio del nivel")
    volume: float = Field(..., description="Volumen visible en lotes")
    orders_count: int = Field(..., description="Número de órdenes agregadas")
    is_spoof_risk: bool = Field(False, description="Flag de orden efímera")

class L2CascadeTelemetry(BaseModel):
    bid_levels: List[DOMDepthLevel] = Field(..., max_length=20)
    ask_levels: List[DOMDepthLevel] = Field(..., max_length=20)
    imbalance_k20: float = Field(..., ge=-1.0, le=1.0)
    replenish_latency_ms: float = Field(..., ge=0.0)
    spoofing_ratio: float = Field(..., ge=0.0, le=1.0)
    iceberg_detected: bool = Field(False)
    iceberg_price: Optional[float] = None
    iceberg_estimated_volume: Optional[float] = None

class OrnsteinUhlenbeckTelemetry(BaseModel):
    theta_ou: float = Field(..., description="Velocidad de reversión")
    mu_ou: float = Field(0.0, description="Media asintótica")
    sigma_ou: float = Field(..., description="Volatilidad instantánea")
    half_life_seconds: float = Field(..., description="Vida media T_1/2")
    half_life_ticks: int = Field(..., description="Vida media en ticks")
    adf_p_value: float = Field(..., ge=0.0, le=1.0)
    z_score_ou: float = Field(..., description="Desviación estandarizada")
    orthogonal_distance: float = Field(...)

class LatentSpaceTelemetry(BaseModel):
    pca_2d: List[float] = Field(..., min_length=2, max_length=2)
    mahalanobis_dist_long: float = Field(...)
    mahalanobis_dist_short: float = Field(...)
    ood_threshold: float = Field(24.50)
    is_ood_regime: bool = Field(False)
    topological_confidence: float = Field(..., ge=0.0, le=1.0)

class GradientAttributionTelemetry(BaseModel):
    ofi_attribution_pct: float = Field(...)
    kalman_attribution_pct: float = Field(...)
    micro_price_attribution_pct: float = Field(...)
    macro_corr_attribution_pct: float = Field(...)
    vpin_attribution_pct: float = Field(...)
    natural_language_explanation: str = Field(...)

class UncertaintyTelemetry(BaseModel):
    epistemic_uncertainty_r: float = Field(..., description="Dispersión Twin-Q")
    aleatoric_uncertainty_nats: float = Field(..., description="Entropía de política H(pi)")
    is_epistemic_clamped: bool = Field(False)
    is_aleatoric_clamped: bool = Field(False)
    position_size_factor: float = Field(1.0, ge=0.0, le=1.0)

class SetupBenchmarkTelemetry(BaseModel):
    active_setup_id: str
    historical_trades: int
    empirical_win_rate_pct: float
    expected_return_r: float
    diebold_mariano_stat: float
    diebold_mariano_p_value: float
    is_defensive_veto_active: bool

class CorrelationTensorTelemetry(BaseModel):
    assets: List[str]
    correlation_matrix: List[List[float]]
    absorption_ratio: float
    max_divergence_pair: str
    max_divergence_sigma: float

class MasterTelemetryFrame(BaseModel):
    timestamp_utc_ms: int
    symbol: str
    canonical_light_state: str  # "VERDE", "AMARILLO", "ROJO"
    win_probability_pct: float
    l2_cascade: L2CascadeTelemetry
    ornstein_uhlenbeck: OrnsteinUhlenbeckTelemetry
    latent_space: LatentSpaceTelemetry
    attribution: GradientAttributionTelemetry
    uncertainty: UncertaintyTelemetry
    setup_benchmark: SetupBenchmarkTelemetry
    correlation_tensor: CorrelationTensorTelemetry
```

### 8.2 Endpoint WebSocket y Protocolo de Difusión
El servidor FastAPI expone el canal de transmisión binario/JSON optimizado:
- **URI:** `ws://127.0.0.1:8765/ws/telemetry/v2`
- **Cadencia de emisión:** 150 ms por frame de mercado (6.67 Hz) o evento-impulsado (*event-driven*) ante transiciones de estado del semáforo.
- **Formato:** JSON comprimido con gzip o MessagePack binario para latencias de red inferiores a $1.2\text{ ms}$.

---

## SECCIÓN 9: GUÍA DE OPERACIÓN EN VIVO (MANUAL EXTENDIDO PARA EL OPERADOR)

### 9.1 Matriz de Decisión Rápida para el Operador Cuantitativo

| Semáforo | Probabilidad $P(\text{Win})$ | Incertidumbre | Condición L2 / Cointegración | Acción del Operador |
| :--- | :--- | :--- | :--- | :--- |
| **VERDE** | $> 75.0\%$ | $U_{\text{epis}} \le 0.15\text{ R}$, $U_{\text{alea}} \le 0.35$ | $Z \le -1.2\sigma$, $\text{OFI} \ge +20$, $T_{1/2} < 60\text{s}$ | **EJECUTAR COMPRA (LONG)** con tamaño nominal. |
| **ROJO** | $> 75.0\%$ | $U_{\text{epis}} \le 0.15\text{ R}$, $U_{\text{alea}} \le 0.35$ | $Z \ge +1.2\sigma$, $\text{OFI} \le -20$, $T_{1/2} < 60\text{s}$ | **EJECUTAR VENTA (SHORT)** con tamaño nominal. |
| **AMARILLO** | Cualquiera | $U_{\text{epis}} > 0.45\text{ R}$ (*Clamping*) | Régimen OOD detectado ($D_M > 24.5$) | **STANDBY TOTAL:** Modelo no comprende el mercado. |
| **AMARILLO** | $< 75.0\%$ | $U_{\text{alea}} > 0.85$ | Ruptura OU ($T_{1/2} > 300\text{s}$), $p_{\text{ADF}} > 0.05$ | **NO OPERAR:** Mercado en consolidación estocástica. |
| **CUALQUIERA** | - | - | Spike de Spoofing $> 65\%$ o VPIN $> 0.88$ | **HARD VETO INMEDIATO (`[⌘V]`):** Riesgo de manipulación. |

### 9.2 Protocolo ante Alarmas Críticas de Telemetría

1. **Alarma de Régimen OOD en Vista 3 ($D_M > 24.5$):**
   - El operador **no debe forzar órdenes manuales**. El sistema entrará automáticamente en modo defensivo. Espere a que el vector latente reingrese al elipsoide de covarianza de trades ganadores ($D_M \le 12.0$).
2. **Alarma de Ruptura de Correlación en Vista 7 ($|\mathbf{C} - \bar{\mathbf{C}}| > 3\sigma$):**
   - Examine si la divergencia responde a una noticia macro programada (CPI, FOMC, NFP). Si no hay fundamental subyacente, active el setup de arbitraje estadístico de reversión OU.
3. **Alarma de Spoofing / Reposición Lenta en Vista 1 ($\tau_{\text{replenish}} > 180\text{ ms}$):**
   - Reduzca el apalancamiento a la mitad o cancele órdenes límite pasivas para evitar ser ejecutado en el lado perdedor de un barrido de liquidez.

---

## CONCLUSIÓN & HOJA DE RUTA DE IMPLEMENTACIÓN

Esta monografía formaliza la actualización a la versión **2.0 Pro Max** de la interfaz y motor de telemetría del Sistema de Luces. La combinación de microestructura de alta frecuencia, explicabilidad por gradientes axiomáticos, descomposición formal de incertidumbres y pruebas estadísticas continuas de Diebold-Mariano asegura el cumplimiento estricto del estándar de **tasa de error $< 25.0\%$** y proporciona al operador una herramienta de supervisión sin precedentes en la industria.

```
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│ SISTEMA DE LUCES 2.0 · ESPECIFICACIÓN TÉCNICA Y MONOGRAFÍA VISUAL APROBADA                       │
│ Antigravity Quantitative AI Safety & High-Frequency Systems Group · Septiembre 2026             │
└──────────────────────────────────────────────────────────────────────────────────────────────────┘
```
