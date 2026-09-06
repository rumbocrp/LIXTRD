# Plan de Implementación - FASE 1: Frontend Multi-Activo

**Versión:** 1.0  
**Fecha de creación:** 2026-08-30  
**Duración estimada:** 2-3 semanas  
**Dependencias:** R0 (completada), R1 (en progreso)  
**Estado objetivo:** `G-R2-H` con observación multi-activo funcional

---

## 1. Objetivo de la Fase 1

Transformar el frontend standalone actual (monolítico, centrado en US500) en una interfaz **multi-activo navegable** que permita:

1. Visualizar 4 activos independientes: **XAUUSD**, **TSLA**, **AAPL** (ALPE), **US500** (SP500)
2. Cada activo con su propio panel de diagnóstico, sistema de luces y registro independiente
3. Navegación clara entre activos sin mezclar datos ni señales
4. Preparar la arquitectura para futura integración de **MT5** como fuente de ejecución simulada

**NO incluye en esta fase:**
- Integración real con MT5 (Fase 5)
- Modelos ML específicos por activo (Fase 4)
- Persistencia separada por activo (Fase 3)
- Señales cruzadas o correlaciones activas

---

## 2. Estado Actual del Proyecto

### 2.1 Activos Existentes

| Activo | Símbolo Yahoo | Tipo | Estado Pipeline | Sistema de Luces |
|--------|---------------|------|-----------------|------------------|
| **US500** | `^GSPC` | Índice | ✅ Completo | ✅ Funcional |
| **TSLA** | `TSLA` | Equity | ⚠️ Solo cotización | ❌ No implementado |
| **AAPL** | `AAPL` | Equity | ⚠️ Solo cotización | ❌ No implementado |
| **XAUUSD** | `GC=F` | Futuro Oro | ❌ No existe (solo GC=F como cotización) | ❌ No implementado |
| **MT5** | N/A | Broker | ❌ Cero integración | ❌ No implementado |

### 2.2 Hallazgos Críticos del Análisis

1. **GC=F ≠ XAUUSD spot**: El símbolo `GC=F` de Yahoo es un **futuro continuo de oro COMEX**, no el spot XAUUSD. Requiere tratamiento especial en UI y validación.

2. **Monitor multi-activo actual** (`yahoo_multi_asset.py`):
   - Observa 4 símbolos: `^GSPC`, `TSLA`, `AAPL`, `GC=F`
   - Emite eventos `CROSS_ASSET_SNAPSHOT` con array `assets[]`
   - **NO genera señales individuales**, solo cotizaciones
   - Todos los activos están hardcodeados bajo `instrument="US500"` (incorrecto para TSLA/AAPL/XAUUSD)

3. **UI actual** (`views.py`):
   - Renderiza un solo panel centrado en US500
   - Tabla multi-activo muestra solo balancines (relaciones), no paneles independientes
   - No hay navegación entre activos
   - No hay registro histórico por activo

4. **MT5**: 
   - No existe ningún adaptador, script o mención a MetaTrader 5
   - Se requiere bridge desde cero (MQL5 EA + Python subscriber)

---

## 3. Arquitectura Objetivo Fase 1

### 3.1 Diagrama de Flujo Multi-Activo

```text
┌─────────────────────────────────────────────────────────────┐
│                    Yahoo Finance Multi-Activo                │
│  ^GSPC ──┐                                                  │
│  TSLA  ──┼──> AdaptadorYahooMultiActivo ──> Eventos        │
│  AAPL  ──┤                                                  │
│  GC=F  ──┘                                                  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│              Composition Root (sources/yahoo_sp500.py)       │
│   - Suscribe eventos CROSS_ASSET_SNAPSHOT                   │
│   - Extrae assets[] por símbolo                             │
│   - Publica en Proyección con market_assets[]               │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                  Proyección de Lectura V1                    │
│   - Mantiene último estado por símbolo                      │
│   - Expone /v1/view con market_assets[] completo            │
│   - Endpoint nuevo: /v1/assets/{symbol}/view                │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Frontend Navegable                        │
│   ┌─────────────────────────────────────────────────────┐   │
│   │  [Selector de Activo]                               │   │
│   │  ○ US500  ○ XAUUSD  ○ TSLA  ○ AAPL  ○ MT5 (sim)    │   │
│   └─────────────────────────────────────────────────────┘   │
│                              │                                │
│         ┌────────────────────┼────────────────────┐          │
│         ▼                    ▼                    ▼          │
│   ┌──────────┐        ┌──────────┐        ┌──────────┐      │
│   │ Panel    │        │ Panel    │        │ Panel    │      │
│   │ US500    │        │ XAUUSD   │        │ TSLA     │      │
│   │ (verde)  │        │(amarillo)│        │  (rojo)  │      │
│   └──────────┘        └──────────┘        └──────────┘      │
│         │                    │                    │          │
│         └────────────────────┴────────────────────┘          │
│                              │                                │
│                              ▼                                │
│   ┌─────────────────────────────────────────────────────┐   │
│   │          Sistema de Luces Independiente             │   │
│   │  - Cada activo tiene su propia luz (VERDE/AMARILLO/ROJO) │
│   │  - Umbrales y políticas configurables por activo   │   │
│   │  - Diagnóstico de transición específico            │   │
│   └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 Endpoints HTTP Requeridos

**Actuales (conservar):**
- `GET /v1/status` → Estado global del sistema
- `GET /v1/view` → Proyección completa con todos los activos
- `GET /v1/transitions?after=` → Transiciones append-only
- `GET /assets/dashboard-v1.js` → Actualizador incremental

**Nuevos (Fase 1):**
- `GET /v1/assets` → Lista de activos disponibles con estado resumido
- `GET /v1/assets/{symbol}/view` → Vista específica de un activo
  - Ej: `/v1/assets/XAUUSD/view`, `/v1/assets/TSLA/view`
- `GET /v1/assets/{symbol}/transitions?after=` → Historial de transiciones por activo
- `GET /v1/assets/{symbol}/light` → Estado actual de luz + diagnóstico

### 3.3 Estructura de Datos por Activo

Cada activo debe tener en la Proyección:

```json
{
  "symbol": "XAUUSD",
  "display_name": "Oro Spot (XAU/USD)",
  "instrument_type": "SPOT",  // SPOT, EQUITY, INDEX, FUTURE
  "provider_symbol": "GC=F",  // Símbolo Yahoo equivalente
  "market_state": "OPEN|CLOSED",
  "quote_status": "PROVIDER_DELAY_UNDISCLOSED",
  "last_price": 2654.30,
  "bid": null,  // Yahoo no proporciona bid/ask
  "ask": null,
  "spread": null,
  "timestamp_utc": "2026-08-30T14:32:00Z",
  "age_ms": 2340,
  "light": "YELLOW",  // VERDE|AMARILLO|ROJO
  "light_reason": "SIN_MODELO_CAMPEON",
  "threshold_green": null,
  "threshold_red": null,
  "probability_long": null,
  "probability_short": null,
  "utility_long": null,
  "utility_short": null,
  "diagnostico": {
    "estado": "MONITORIZAR",
    "umbral_actual": null,
    "distancia_umbral": null
  },
  "registro": {
    "total_transiciones": 0,
    "ultima_senal": null,
    "operativas_simuladas": []
  }
}
```

---

## 4. Componentes Frontend a Implementar

### 4.1 Navegación Multi-Activo

**Archivo:** `src/sistema_luces/ui/views.py` (extender)

**Componente:** Selector de Activo (tabs horizontales o rail vertical)

```html
<nav class="asset-selector" role="tablist" aria-label="Selección de activo">
  <button role="tab" aria-selected="true" data-asset="US500">
    🇺🇸 US500 <span class="light-indicator green"></span>
  </button>
  <button role="tab" aria-selected="false" data-asset="XAUUSD">
    🥇 XAUUSD <span class="light-indicator yellow"></span>
  </button>
  <button role="tab" aria-selected="false" data-asset="TSLA">
    🚗 TSLA <span class="light-indicator red"></span>
  </button>
  <button role="tab" aria-selected="false" data-asset="AAPL">
    🍎 AAPL <span class="light-indicator yellow"></span>
  </button>
  <button role="tab" aria-selected="false" data-asset="MT5_SIM" disabled title="Próximamente">
    📊 MT5 Sim <span class="badge">PRÓXIMAMENTE</span>
  </button>
</nav>
```

**Requisitos:**
- Solo un activo visible a la vez
- Indicador de luz visible en cada tab (punto de color)
- Teclado: flechas izquierda/derecha cambian de activo
- URL hash: `#asset=XAUUSD` para deep linking
- Estado persistente en localStorage

### 4.2 Panel por Activo

**Estructura común para cada activo:**

```html
<section class="asset-panel" id="panel-XAUUSD" role="tabpanel">
  
  <!-- Encabezado -->
  <header class="asset-header">
    <h2>XAUUSD · Oro Spot</h2>
    <div class="light-badge yellow">AMARILLO · MONITORIZAR</div>
    <div class="market-state closed">MERCADO CERRADO</div>
  </header>

  <!-- Cotización -->
  <div class="quote-section">
    <div class="metric">
      <span class="label">Último Precio</span>
      <span class="value tabular">2654.30</span>
    </div>
    <div class="metric">
      <span class="label">Variación</span>
      <span class="value tabular positive">+1.2%</span>
    </div>
    <div class="metric">
      <span class="label">Edad</span>
      <span class="value tabular">2.3s</span>
    </div>
  </div>

  <!-- Sistema de Luces -->
  <div class="light-system">
    <div class="light-indicator large yellow"></div>
    <div class="light-reason">
      <strong>Razón:</strong> Sin modelo campeón evaluado para este activo
    </div>
    
    <!-- Barra de diagnóstico -->
    <div class="diagnostic-bar" role="progressbar" aria-valuenow="0" aria-valuemin="0" aria-valuemax="100">
      <div class="threshold-zone red" style="width: 30%"></div>
      <div class="threshold-zone yellow" style="width: 40%"></div>
      <div class="threshold-zone green" style="width: 30%"></div>
      <div class="current-marker" style="left: 0%"></div>
      <div class="threshold-labels">
        <span>Rojo &lt;30%</span>
        <span>Verde &gt;70%</span>
      </div>
    </div>
  </div>

  <!-- Registro de Operativas -->
  <div class="registry-section">
    <h3>Registro de Operativas Simuladas</h3>
    <table class="operations-table">
      <thead>
        <tr>
          <th>Fecha</th>
          <th>Dirección</th>
          <th>Precio</th>
          <th>Luz</th>
          <th>Resultado</th>
        </tr>
      </thead>
      <tbody>
        <tr class="empty-row">
          <td colspan="5">Sin operativas registradas</td>
        </tr>
      </tbody>
    </table>
  </div>

  <!-- Linaje -->
  <footer class="provenance">
    <div>Fuente: Yahoo Finance (GC=F)</div>
    <div>Última actualización: 2026-08-30 14:32:00 UTC</div>
    <div>Hash: <code>a3f5...</code></div>
  </footer>
</section>
```

### 4.3 JavaScript Dashboard (dashboard-v1.js)

**Modificaciones requeridas:**

1. **Estado multi-activo:**
```javascript
const state = {
  currentAsset: 'US500',
  assets: {
    US500: { light: 'GREEN', price: 5634.20, age_ms: 1200 },
    XAUUSD: { light: 'YELLOW', price: 2654.30, age_ms: 2340 },
    TSLA: { light: 'RED', price: 245.67, age_ms: 890 },
    AAPL: { light: 'YELLOW', price: 227.80, age_ms: 1100 }
  }
};
```

2. **Funciones nuevas:**
```javascript
// Cambiar de activo
function switchAsset(symbol) {
  state.currentAsset = symbol;
  localStorage.setItem('sl_current_asset', symbol);
  updateActiveTab(symbol);
  renderAssetPanel(symbol);
  updateURLHash(symbol);
}

// Renderizar panel específico
function renderAssetPanel(symbol) {
  const data = state.assets[symbol];
  if (!data) return renderNoData(symbol);
  
  updateLightIndicator(symbol, data.light);
  updateQuoteSection(symbol, data);
  updateDiagnosticBar(symbol, data.diagnostico);
  updateRegistryTable(symbol, data.registro);
}

// Polling específico por activo
async function fetchAssetView(symbol) {
  const response = await fetch(`/v1/assets/${symbol}/view`);
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return response.json();
}
```

3. **Actualización incremental:**
- Mantener polling global cada 2s para `/v1/view` (todos los activos)
- Actualizar solo el panel activo inmediatamente
- Actualizar indicadores de luz en tabs siempre
- Reducir frecuencia a 10s cuando pestaña oculta

---

## 5. Backend: Extensiones Requeridas

### 5.1 Módulos Python a Modificar

**Archivo:** `src/sistema_luces/sources/yahoo_multi_asset.py`

**Cambios:**
1. Corregir `instrument` por símbolo (actualmente todos "US500")
2. Agregar metadata específica por activo

```python
_CONFIGURACIONES = {
    SIMBOLO_YAHOO_SP500: ConfiguracionYahooPublica(
        symbol=SIMBOLO_YAHOO_SP500,
        instrument="US500",  # ✅ Correcto
        display_name="S&P 500",
        instrument_type="INDEX",
        ...
    ),
    "TSLA": ConfiguracionYahooPublica(
        symbol="TSLA",
        instrument="TSLA",  # ❌ Era "US500"
        display_name="Tesla Inc",
        instrument_type="EQUITY",
        ...
    ),
    "AAPL": ConfiguracionYahooPublica(
        symbol="AAPL",
        instrument="AAPL",  # ❌ Era "US500"
        display_name="Apple Inc",
        instrument_type="EQUITY",
        ...
    ),
    "GC=F": ConfiguracionYahooPublica(
        symbol="GC=F",
        instrument="XAUUSD",  # ❌ Era "US500"
        display_name="Oro Spot (XAU/USD) · Futuro COMEX",
        instrument_type="FUTURE",
        quote_scope="CONTINUOUS_FUTURES_NOT_SPOT",  # ⚠️ Advertencia UI
        ...
    ),
}
```

**Archivo:** `src/sistema_luces/presentation/views.py`

**Agregar proyector multi-activo:**

```python
class ProyectorMultiActivoV1:
    """Proyecta vistas individuales por activo desde ProyeccionLecturaV1."""
    
    def __init__(self, proyeccion_global: ProyeccionLecturaV1):
        self._proyeccion = proyeccion_global
    
    def obtener_vista_activo(self, symbol: str) -> VistaActivoIndividual:
        """Extrae y transforma datos para un activo específico."""
        vista_global = self._proyeccion.consultar()
        
        # Buscar asset en market_assets[]
        asset_data = None
        for asset in vista_global.market_assets:
            if asset.get('provider_symbol') == self._mapear_a_yahoo(symbol):
                asset_data = asset
                break
        
        if not asset_data:
            return VistaActivoIndividual.sin_datos(symbol)
        
        # Construir vista individual
        return VistaActivoIndividual(
            symbol=symbol,
            display_name=self._nombre_mostrar(symbol),
            instrument_type=asset_data.get('instrument_type'),
            last_price=asset_data.get('last_price'),
            market_state=asset_data.get('market_state'),
            quote_status=asset_data.get('quote_status'),
            timestamp_utc=asset_data.get('source_timestamp_utc'),
            age_ms=vista_global.data_age_ms,
            light=self._calcular_luz_local(symbol, asset_data),
            light_reason=self._razon_luz(symbol),
            diagnostico=self._construir_diagnostico(symbol, asset_data),
            registro=self._cargar_registro(symbol),
        )
```

**Archivo:** `src/sistema_luces/ui/server.py`

**Agregar endpoints:**

```python
def manejar_request_assets(self, path: str, query: dict) -> tuple[int, dict, dict]:
    """Router para /v1/assets/*"""
    
    if path == '/v1/assets':
        # Lista resumen de todos los activos
        return self._listar_activos()
    
    match = re.match(r'^/v1/assets/([^/]+)/view$', path)
    if match:
        symbol = match.group(1).upper()
        return self._vista_activo_individual(symbol)
    
    match = re.match(r'^/v1/assets/([^/]+)/transitions$', path)
    if match:
        symbol = match.group(1).upper()
        after = query.get('after', [None])[0]
        return self._transiciones_por_activo(symbol, after)
    
    return 404, {'error': 'Not Found'}, {}
```

### 5.2 Registro por Activo

**Nuevo archivo:** `src/sistema_luces/storage/registro_activo.py`

```python
class RegistroPorActivo:
    """Mantiene historial de señales y operativas por activo."""
    
    def __init__(self, db_path: str):
        self._conn = sqlite3.connect(db_path)
        self._inicializar_tablas()
    
    def _inicializar_tablas(self):
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS registro_operativas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                fecha_utc TEXT NOT NULL,
                direccion TEXT CHECK(direccion IN ('LARGO', 'CORTO', 'NINGUNA')),
                precio_entrada REAL,
                luz_origen TEXT CHECK(luz_origen IN ('VERDE', 'AMARILLO', 'ROJO')),
                resultado TEXT,  -- 'GANANCIA', 'PERDIDA', 'PENDIENTE'
                pnl_puntos REAL,
                notas TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_registro_symbol 
            ON registro_operativas(symbol, fecha_utc)
        """)
    
    def registrar_operativa(self, symbol: str, direccion: str, **kwargs):
        """Registra una operativa simulada."""
        self._conn.execute("""
            INSERT INTO registro_operativas 
            (symbol, fecha_utc, direccion, precio_entrada, luz_origen, resultado, pnl_puntos, notas)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            symbol,
            datetime.now(timezone.utc).isoformat(),
            direccion,
            kwargs.get('precio'),
            kwargs.get('luz'),
            kwargs.get('resultado', 'PENDIENTE'),
            kwargs.get('pnl'),
            kwargs.get('notas')
        ))
        self._conn.commit()
    
    def obtener_historial(self, symbol: str, limite: int = 50) -> list[dict]:
        """Obtiene últimas operativas de un activo."""
        cursor = self._conn.execute("""
            SELECT * FROM registro_operativas
            WHERE symbol = ?
            ORDER BY fecha_utc DESC
            LIMIT ?
        """, (symbol, limite))
        return [dict(zip([d[0] for d in cursor.description], row)) for row in cursor.fetchall()]
```

---

## 6. Sistema de Luces por Activo

### 6.1 Configuración de Umbrales

**Archivo:** `config/umbrales_por_activo.json`

```json
{
  "US500": {
    "threshold_green": 0.70,
    "threshold_red": 0.30,
    "histéresis_minima": 0.15,
    "vigencia_maxima_minutos": 30,
    "politica_version": "policy-v1-us500"
  },
  "XAUUSD": {
    "threshold_green": 0.75,
    "threshold_red": 0.25,
    "histéresis_minima": 0.20,
    "vigencia_maxima_minutos": 45,
    "politica_version": "policy-v1-xauusd",
    "notas": "Mayor volatilidad, umbrales más estrictos"
  },
  "TSLA": {
    "threshold_green": 0.80,
    "threshold_red": 0.20,
    "histéresis_minima": 0.25,
    "vigencia_maxima_minutos": 20,
    "politica_version": "policy-v1-tsla",
    "notas": "Equity de alta volatilidad"
  },
  "AAPL": {
    "threshold_green": 0.70,
    "threshold_red": 0.30,
    "histéresis_minima": 0.15,
    "vigencia_maxima_minutos": 30,
    "politica_version": "policy-v1-aapl"
  }
}
```

### 6.2 Lógica de Decisión por Activo

**Archivo:** `src/sistema_luces/policy/decision_multi_activo.py`

```python
class PolicyMultiActivo:
    """Aplica política de luces independiente por activo."""
    
    def __init__(self, config_path: str):
        with open(config_path) as f:
            self._config = json.load(f)
    
    def decidir_luz(self, symbol: str, probabilidades: dict) -> DecisionLuz:
        """Determina luz para un activo específico."""
        config = self._config.get(symbol, self._config['DEFAULT'])
        
        p_long = probabilidades.get('long', 0.5)
        p_short = probabilidades.get('short', 0.5)
        
        threshold_green = config['threshold_green']
        threshold_red = config['threshold_red']
        histeresis = config['histéresis_minima']
        
        # Lógica con histéresis
        if p_long >= threshold_green:
            return DecisionLuz(
                luz='VERDE',
                razon=f'Probabilidad LONG {p_long:.1%} >= umbral {threshold_green:.1%}',
                vigencia_minutos=config['vigencia_maxima_minutos'],
                utilidad_long=probabilidades.get('utility_long'),
                utilidad_short=probabilidades.get('utility_short')
            )
        
        if p_short <= threshold_red:
            return DecisionLuz(
                luz='ROJO',
                razon=f'Probabilidad SHORT {p_short:.1%} <= umbral {threshold_red:.1%}',
                vigencia_minutos=config['vigencia_maxima_minutos'],
                utilidad_long=probabilidades.get('utility_long'),
                utilidad_short=probabilidades.get('utility_short')
            )
        
        # Zona amarilla (abstención)
        return DecisionLuz(
            luz='AMARILLO',
            razon='Probabilidades en zona neutral o sin modelo',
            vigencia_minutos=5,
            utilidad_long=None,
            utilidad_short=None
        )
```

---

## 7. Criterios de Aceptación Fase 1

### 7.1 Funcionales

- [ ] **FA1.1**: Usuario puede navegar entre 4 activos (US500, XAUUSD, TSLA, AAPL) mediante tabs
- [ ] **FA1.2**: Cada activo muestra panel independiente con cotización, luz y diagnóstico
- [ ] **FA1.3**: Sistema de luces funciona independientemente por activo (colores pueden diferir)
- [ ] **FA1.4**: URL hash refleja activo seleccionado (#asset=XAUUSD)
- [ ] **FA1.5**: Estado de activo seleccionado persiste en localStorage
- [ ] **FA1.6**: Teclado (flechas) permite cambiar de activo
- [ ] **FA1.7**: Endpoint `/v1/assets/{symbol}/view` retorna datos específicos del activo
- [ ] **FA1.8**: Registro de operativas muestra solo operativas del activo filtrado
- [ ] **FA1.9**: Indicadores de luz en tabs se actualizan en tiempo real para todos los activos
- [ ] **FA1.10**: MT5 aparece como tab deshabilitado con tooltip "Próximamente - Fase 5"

### 7.2 Técnicos

- [ ] **FT1.1**: `instrument` corregido en yahoo_multi_asset.py por símbolo
- [ ] **FT1.2**: ProyectorMultiActivoV1 implementado y testeado
- [ ] **FT1.3**: Endpoints nuevos documentados en OpenAPI/Swagger
- [ ] **FT1.4**: Tabla `registro_operativas` creada con índice por symbol
- [ ] **FT1.5**: Config JSON de umbrales por activo validado contra schema
- [ ] **FT1.6**: Tests unitarios para PolicyMultiActivo con casos por activo
- [ ] **FT1.7**: Dashboard JS refactorizado para estado multi-activo
- [ ] **FT1.8**: Polling optimizado: 2s visible, 10s oculto, sin solapamiento

### 7.3 UX/UI

- [ ] **FU1.1**: Diseño compatible con SISTEMA-VISUAL.md (sobrio, tabular, sin glow)
- [ ] **FU1.2**: WCAG 2.2 AA: foco visible, roles ARIA, contraste verificado
- [ ] **FU1.3**: Responsive: tabs colapsan a dropdown en móvil (<768px)
- [ ] **FU1.4**: Estados canónicos aplicados por activo (vacio, cargando, error, obsoleto)
- [ ] **FU1.5**: Tooltips explicativos para GC=F ≠ XAUUSD spot
- [ ] **FU1.6**: Loading skeleton durante cambio de activo
- [ ] **FU1.7**: Banner de advertencia si mercado cerrado por activo

### 7.4 Documentación

- [ ] **FD1.1**: README actualizado con descripción multi-activo
- [ ] **FD1.2**: ADR creado para decisión de arquitectura multi-activo
- [ ] **FD1.3**: Manual de usuario con navegación entre activos
- [ ] **FD1.4**: Changelog documenta cambios breaking (si los hay)

---

## 8. Riesgos y Mitigaciones

| Riesgo | Probabilidad | Impacto | Mitigación |
|--------|--------------|---------|------------|
| **R1**: GC=F confunde usuarios como XAUUSD spot | Alta | Medio | Banner explícito: "Futuro COMEX, no spot" + tooltip educativo |
| **R2**: Performance degradada con 4 polls simultáneos | Media | Bajo | Consolidar en single poll `/v1/view` con todos los activos |
| **R3**: Estado compartido causa bugs de sincronización | Media | Alto | Estado centralizado en store JS, nunca DOM directo |
| **R4**: Umbrales hardcodeados sin justificación | Baja | Medio | Config externo JSON + documentación de criterios |
| **R5**: Accesibilidad rota en tabs dinámicos | Media | Alto | Tests axe-core automatizados + revisión manual teclado |
| **R6**: Usuarios esperan señales reales en Fase 1 | Alta | Medio | Banners claros: "Sin modelo - Solo cotización" en amarillo |

---

## 9. Entregables Fase 1

### Código
- [ ] `src/sistema_luces/sources/yahoo_multi_asset.py` (corregido)
- [ ] `src/sistema_luces/presentation/views.py` (ProyectorMultiActivoV1)
- [ ] `src/sistema_luces/ui/server.py` (endpoints nuevos)
- [ ] `src/sistema_luces/ui/views.py` (HTML multi-activo)
- [ ] `src/sistema_luces/ui/dashboard-v1.js` (estado multi-activo)
- [ ] `src/sistema_luces/storage/registro_activo.py` (nuevo)
- [ ] `src/sistema_luces/policy/decision_multi_activo.py` (nuevo)
- [ ] `config/umbrales_por_activo.json` (nuevo)

### Tests
- [ ] `tests/unit/test_proyector_multi_activo.py`
- [ ] `tests/unit/test_policy_multi_activo.py`
- [ ] `tests/integration/test_endpoints_activos.py`
- [ ] `tests/e2e/test_navegacion_multi_activo.py`

### Documentación
- [ ] `docs/ADR-005-frontend-multi-activo.md`
- [ ] `docs/FASE1-MANUAL-USUARIO.md`
- [ ] `CHANGELOG.md` actualizado
- [ ] `README.md` actualizado

### Evidencia
- [ ] Screenshots de los 4 paneles activos
- [ ] Video demo navegación (teclado + ratón)
- [ ] Reporte axe-core verde
- [ ] Logs de polling sin solapamiento

---

## 10. Cronograma Detallado

### Semana 1: Backend Multi-Activo
| Día | Tarea | Entrega |
|-----|-------|---------|
| 1 | Corregir `yahoo_multi_asset.py` (instruments) | Commit + tests unit |
| 2 | Implementar `ProyectorMultiActivoV1` | Tests integración |
| 3 | Endpoints `/v1/assets/*` en server.py | Swagger actualizado |
| 4 | Registro SQLite por activo | Migration script |
| 5 | Policy multi-activo + config JSON | Tests policy |

### Semana 2: Frontend Navegable
| Día | Tarea | Entrega |
|-----|-------|---------|
| 1 | HTML estructura tabs + paneles | Mock static |
| 2 | JS estado multi-activo + switcher | Funcional local |
| 3 | Integración API endpoints | Datos reales |
| 4 | Accesibilidad (ARIA, teclado) | Reporte axe |
| 5 | Responsive + estados canónicos | QA móvil |

### Semana 3: Pulido y Validación
| Día | Tarea | Entrega |
|-----|-------|---------|
| 1 | Tests e2e navegación | CI verde |
| 2 | Documentación ADR + manual | Docs merge |
| 3 | Performance audit (Lighthouse) | Score >90 |
| 4 | Bug fixing + edge cases | Release candidate |
| 5 | Demo grabada + release notes | **FASE 1 COMPLETE** ✅ |

---

## 11. Dependencias con Otras Fases

```text
FASE 1 (Frontend Multi-Activo)
         │
         ├──→ FASE 2 (Backend Multi-Activo): Refinar políticas por activo
         │
         ├──→ FASE 3 (Datos y Persistencia): Schema multi-activo en DB
         │
         ├──→ FASE 4 (Motor ML/IA): Modelos específicos por activo
         │
         └──→ FASE 5 (Integración MT5): Bridge para ejecución simulada
```

**Lo que Fase 1 NO hace pero prepara:**
- Estructura HTML/CSS lista para MT5 tab
- Endpoints preparados para recibir señales de ML
- Registro listo para almacenar operativas MT5
- Config JSON extensible para umbrales ML-driven

---

## 12. Métricas de Éxito Fase 1

| Métrica | Objetivo | Medición |
|---------|----------|----------|
| **Tiempo cambio de activo** | <200ms | Chrome DevTools Performance |
| **LCP (Largest Contentful Paint)** | <2.5s | Lighthouse |
| **Accesibilidad** | 100/100 | axe-core + manual keyboard |
| **Cobertura tests** | >85% | pytest --cov |
| **Errores JS en consola** | 0 | Browser console + Sentry (si aplica) |
| **Satisfacción usuario** | >4/5 | Survey interna 5 personas |

---

## 13. Próximos Pasos Inmediatos

1. **Revisión de este plan** con stakeholder (¿faltan activos? ¿prioridad correcta?)
2. **Crear branch** `feature/fase1-multi-activo` desde `main`
3. **Setup ambiente** desarrollo frontend (Node.js, npm dependencies)
4. **Kickoff implementación** con tarea FA1.1 (corrección instruments)
5. **Daily check-ins** para bloqueos tempranos

---

**Aprobaciones Requeridas:**
- [ ] Product Owner: Alcance y priorización
- [ ] Tech Lead: Arquitectura y endpoints
- [ ] UX/UI: Diseño de tabs y paneles
- [ ] Seguridad: Revisión de endpoints públicos

---

*Documento vivo - Actualizar conforme avanza la implementación*
