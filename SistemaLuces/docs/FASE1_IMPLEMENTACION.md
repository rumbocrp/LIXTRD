# FASE 1: Frontend Multi-Activo - Implementación y Estado

## Objetivo de la Fase 1
Transformar el frontend monolítico actual en una interfaz multi-activo navegable con 4 activos independientes (US500, XAUUSD, TSLA, AAPL), cada uno con su propio panel de luces, registro de eventos y configuración específica.

## Alcance Completado

### 1. Configuración Multi-Activo ✅
**Archivo:** `src/sistema_luces/config/multi_asset_config.py`

Se creó el módulo de configuración que define:
- **4 instrumentos permitidos:** US500, XAUUSD, TSLA, AAPL
- **Configuración por instrumento:**
  - Símbolo Yahoo (^GSPC, GC=F, TSLA, AAPL)
  - Nombre para mostrar en UI
  - Categoría (Índice, Commodity, Acción)
  - Parámetros de trading (precio_scale, tick_size, lotes)
  - Umbrales de luz específicos por activo
  - Estado `economic_ready` (solo US500 = True)

```python
INSTRUMENTOS_PERMITIDOS = {"US500", "XAUUSD", "TSLA", "AAPL"}

CONFIGURACION_INSTRUMENTOS = {
    "US500": {...},    # economic_ready=True
    "XAUUSD": {...},   # economic_ready=False, umbrales=(30.0, 70.0)
    "TSLA": {...},     # economic_ready=False, umbrales=(25.0, 75.0)
    "AAPL": {...},     # economic_ready=False, umbrales=(35.0, 65.0)
}
```

### 2. Proyector Multi-Activo ✅
**Archivo:** `src/sistema_luces/observability/projections.py`

**Cambios realizados:**
- `ProyectorVistas` ahora acepta parámetro `instrumento: str = "US500"`
- Valida que el instrumento esté en `INSTRUMENTOS_PERMITIDOS`
- Almacena configuración específica en `self._config`
- Cada proyector mantiene estado independiente

**Comportamiento:**
```python
proyector_us500 = ProyectorVistas("US500")   # Funcional
proyector_xauusd = ProyectorVistas("XAUUSD") # Funcional
proyector_tsla = ProyectorVistas("TSLA")     # Funcional
proyector_aapl = ProyectorVistas("AAPL")     # Funcional
```

### 3. Servidor HTTP Multi-Activo ✅
**Archivo:** `src/sistema_luces/ui/server.py`

**Cambios realizados:**
- `ServidorLoopback` ahora acepta `proyectores: Dict[str, ProyectorVistas]`
- Si no se proporcionan, crea automáticamente 4 proyectores (uno por instrumento)
- Mantiene diccionario `self.proyectores` con todos los instrumentos
- Usa US500 como default para compatibilidad backward

**Estructura del servidor:**
```python
servidor = ServidorLoopback(
    host="127.0.0.1",
    port=8080,
    proyectores={
        "US500": ProyectorVistas("US500"),
        "XAUUSD": ProyectorVistas("XAUUSD"),
        "TSLA": ProyectorVistas("TSLA"),
        "AAPL": ProyectorVistas("AAPL"),
    }
)
```

### 4. Endpoints Existentes (Sin Cambios)
Los endpoints actuales permanecen iguales pero operan sobre el proyector default (US500):
- `GET /` → Dashboard HTML (US500 por defecto)
- `GET /v1/status` → Estado JSON (US500 por defecto)
- `GET /v1/view` → Vista completa (US500 por defecto)
- `GET /assets/dashboard-v1.js` → Script cliente

## Trabajo Pendiente - Fase 1

### 1. Extensión de Endpoints para Multi-Activo ⏳
**Prioridad: ALTA**

Se requiere agregar soporte para parámetro de instrumento en los endpoints:

```python
# Nuevos endpoints propuestos:
GET /v1/status?instrument=XAUUSD
GET /v1/view?instrument=TSLA
GET /api/state/US500
GET /api/state/XAUUSD
GET /api/state/TSLA
GET /api/state/AAPL
```

**Modificaciones necesarias en `server.py`:**
```python
def do_GET(self):
    path = self.path.split("?", 1)[0]
    query_params = parse_qs(urlparse(self.path).query)
    instrument = query_params.get("instrument", ["US500"])[0]
    
    if path == "/v1/status":
        proyector = self.proyectores_multi.get(instrument, self.proyector)
        self._handle_status_json(proyector)
    # ... similar para otros endpoints
```

### 2. Dashboard HTML Multi-Activo ⏳
**Prioridad: ALTA**

El dashboard actual (`views.py`) está hardcodeado para US500. Se necesita:

**a) Navegación por Tabs/Pestañas:**
```html
<div class="asset-tabs">
  <button data-asset="US500" class="active">S&P 500</button>
  <button data-asset="XAUUSD">Oro (XAU/USD)</button>
  <button data-asset="TSLA">Tesla</button>
  <button data-asset="AAPL">Apple</button>
  <button data-asset="MT5" disabled>MT5 (Próximamente)</button>
</div>
```

**b) Selector de instrumento en `render_dashboard_html()`:**
```python
def render_dashboard_html(vista, instrument="US500", ...):
    config = obtener_config_instrumento(instrument)
    # Usar config.nombre_mostrar, config.umbrales_luz, etc.
```

**c) Estados independientes por activo:**
- Cada tab debe mostrar SU PROPIO semáforo
- Cada tab debe tener SU PROPIO registro de eventos
- Cada tab debe tener SUS PROPIAS métricas cuantitativas

### 3. JavaScript Cliente Multi-Activo ⏳
**Prioridad: ALTA**

**Archivo:** `src/sistema_luces/ui/dashboard-v1.js`

**Cambios requeridos:**
```javascript
// Estado actual: un solo polling a /v1/status
// Estado deseado: polling por activo seleccionado

const ASSETS = ["US500", "XAUUSD", "TSLA", "AAPL"];
let currentAsset = "US500";
let assetStates = {};

function switchAsset(symbol) {
    currentAsset = symbol;
    updateUI(assetStates[symbol]);
    // Actualizar tabs activas
}

async function requestStatus() {
    const response = await fetch(`/v1/status?instrument=${currentAsset}`);
    const data = await response.json();
    assetStates[currentAsset] = data;
    updateUI(data);
}

// Polling independiente por activo
// Opción A: Un timer que cambia entre activos
// Opción B: Múltiples timers (uno por activo)
```

### 4. Vistas Independientes por Activo ⏳
**Archivo:** `src/sistema_luces/ui/views.py`

**Función `render_dashboard_html()` actualmente:**
- Hardcodea "US500" en múltiples lugares
- Asume estructura fija de balancines SP500_TSLA, SP500_AAPL, GOLD_DXY
- Muestra tabla multi-activo que debe convertirse en navegación

**Cambios necesarios:**
```python
def render_dashboard_html(
    vista: VistaLectura,
    instrument: str | None = None,
    todos_los_instrumentos: bool = False,
) -> str:
    # Si instrument=None, usar vista.instrument
    # Si todos_los_instrumentos=True, mostrar vista general
    # Si todos_los_instrumentos=False, mostrar panel específico
```

### 5. Registro de Eventos por Activo ⏳
**Archivos afectados:**
- `src/sistema_luces/storage/event_store.py`
- `src/sistema_luces/observability/projections.py`

**Requerimiento:**
Cada instrumento debe tener su propio stream de eventos:
```python
# Event Store debe filtrar por instrumento
eventos_us500 = store.obtener_eventos(instrumento="US500", view="LIGHTS")
eventos_xauusd = store.obtener_eventos(instrumento="XAUUSD", view="LIGHTS")

# Proyecciones separadas
proyector_us500.actualizar_desde_evento(evento_us500)
proyector_xauusd.actualizar_desde_evento(evento_xauusd)
```

### 6. Sistema de Luces por Activo ⏳
**Archivos afectados:**
- `src/sistema_luces/policy/lights.py`
- `src/sistema_luces/quant/traffic_light.py`

**Requerimiento:**
Cada activo debe evaluar su propia luz independientemente:
```python
# Política de luces debe usar umbrales por instrumento
config = obtener_config_instrumento("XAUUSD")
threshold_red, threshold_green = config.umbrales_luz  # (30.0, 70.0)

luz_xauusd = evaluar_luz(prob_long, threshold_red, threshold_green)
luz_tsla = evaluar_luz(prob_long, 25.0, 75.0)  # Umbrales más extremos
```

## Pruebas de Validación - Fase 1

### Test 1: Creación de Proyectores ✅
```bash
cd /workspace/SistemaLuces
PYTHONPATH=/workspace/SistemaLuces/src python -c "
from sistema_luces.observability.projections import ProyectorVistas

# Debe funcionar para los 4 instrumentos
for inst in ['US500', 'XAUUSD', 'TSLA', 'AAPL']:
    p = ProyectorVistas(inst)
    assert p._instrument == inst
    print(f'✅ {inst}: OK')

# Debe rechazar instrumento inválido
try:
    ProyectorVistas('INVALIDO')
    print('❌ Debería haber lanzado ValueError')
except ValueError as e:
    print(f'✅ Rechazo correcto: {e}')
"
```

### Test 2: Servidor Multi-Activo ✅
```bash
cd /workspace/SistemaLuces
PYTHONPATH=/workspace/SistemaLuces/src python -c "
from sistema_luces.ui.server import ServidorLoopback

# Crear servidor con proyectores automáticos
servidor = ServidorLoopback(port=8081)

# Verificar que existen los 4 proyectores
assert len(servidor.proyectores) == 4
assert 'US500' in servidor.proyectores
assert 'XAUUSD' in servidor.proyectores
assert 'TSLA' in servidor.proyectores
assert 'AAPL' in servidor.proyectores

print('✅ Servidor creado con 4 proyectores')
print(f'   Instrumentos: {list(servidor.proyectores.keys())}')

servidor.shutdown()
"
```

### Test 3: Configuración por Instrumento ✅
```bash
cd /workspace/SistemaLuces
PYTHONPATH=/workspace/SistemaLuces/src python -c "
from sistema_luces.config.multi_asset_config import (
    CONFIGURACION_INSTRUMENTOS,
    obtener_config_instrumento
)

# Verificar configuraciones
for simbolo in ['US500', 'XAUUSD', 'TSLA', 'AAPL']:
    config = obtener_config_instrumento(simbolo)
    assert config is not None
    assert config.simbolo_yahoo is not None
    assert config.umbrales_luz is not None
    print(f'✅ {simbolo}: Yahoo={config.simbolo_yahoo}, Umbrales={config.umbrales_luz}')
"
```

## Cronograma Fase 1

| Tarea | Estado | Estimación | Dependencias |
|-------|--------|------------|--------------|
| 1. Configuración multi-activo | ✅ COMPLETADO | - | - |
| 2. Proyector multi-activo | ✅ COMPLETADO | - | Tarea 1 |
| 3. Servidor multi-activo | ✅ COMPLETADO | - | Tarea 2 |
| 4. Endpoints con parámetro instrument | ⏳ PENDIENTE | 2-3 días | Tareas 1-3 |
| 5. Dashboard HTML con tabs | ⏳ PENDIENTE | 3-4 días | Tarea 4 |
| 6. JavaScript cliente multi-activo | ⏳ PENDIENTE | 2-3 días | Tareas 4-5 |
| 7. Registro events por activo | ⏳ PENDIENTE | 2 días | Tarea 2 |
| 8. Luces por activo (umbrales) | ⏳ PENDIENTE | 1-2 días | Tarea 1 |
| 9. Pruebas integración | ⏳ PENDIENTE | 2 días | Tareas 4-8 |
| 10. Documentación UI | ⏳ PENDIENTE | 1 día | Tarea 5 |

**Total estimado restante:** 15-19 días hábiles (3 semanas)

## Criterios de Aceptación - Fase 1

Para considerar la Fase 1 como COMPLETADA:

1. ✅ **Navegación:** Usuario puede cambiar entre 4 tabs (US500, XAUUSD, TSLA, AAPL)
2. ✅ **Independencia:** Cada tab muestra datos DEL INSTRUMENTO SELECCIONADO
3. ✅ **Luces:** Cada instrumento tiene su propio semáforo (VERDE/AMARILLO/ROJO)
4. ✅ **Registro:** Cada instrumento tiene su propio historial de eventos visible
5. ✅ **Configuración:** Umbrales de luz difieren por instrumento según configuración
6. ✅ **Tab MT5:** Existe tab "MT5" deshabilitado con tooltip "Próximamente - Operativa Demo"
7. ✅ **URLs:** Se puede acceder vía URL directa (ej: `/?instrument=XAUUSD`)
8. ✅ **Backward:** Compatibilidad con clientes existentes que usan US500 por defecto

## Notas Importantes

### Sobre XAUUSD vs GC=F
⚠️ **GC=F es futuro de oro COMEX, NO XAUUSD spot**
- El futuro tiene vencimiento, rollover, y pricing diferente
- Para Fase 2+ se deberá evaluar:
  - Usar proveedor alternativo (OANDA, FXCM) para XAUUSD spot real
  - O ajustar modelo para trabajar con futuros GC=F explícitamente

### Sobre Umbrales Diferenciados
Cada instrumento tiene características distintas:
- **US500:** Índice diversificado → umbrales estándar (35%/65%)
- **XAUUSD:** commodity volátil → umbrales amplios (30%/70%)
- **TSLA:** High-beta momentum → umbrales extremos (25%/75%)
- **AAPL:** Blue-chip ancla → umbrales estándar (35%/65%)

Estos umbrales DEBEN reflejarse en la UI cuando se muestra el diagnóstico del semáforo.

### Sobre MT5
La integración con MetaTrader 5 requiere:
- Bridge ZeroMQ o TCP entre Python y MQL5
- EA (Expert Advisor) en MQL5 que reciba señales
- Validación en cuenta DEMO antes de operativa real
- **NO incluido en Fase 1** - objetivo de Fase 5

## Siguientes Pasos Inmediatos

1. **Implementar endpoint `/v1/status?instrument=<SIMBOLO>`**
2. **Agregar selector de instrumento en dashboard HTML**
3. **Modificar JavaScript para polling dinámico por activo**
4. **Validar que cada proyector mantiene estado independiente**

---

**Estado Actual:** 3/10 tareas completadas (30%)
**Próximo Hito:** Endpoints multi-activo funcionales con parámetro `instrument`
