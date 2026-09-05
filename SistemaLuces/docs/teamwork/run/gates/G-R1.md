# Reporte Formal de Evidencia — Gate G-R1

**Fecha de Ejecución:** 2026-08-30  
**Milestone:** M1 / Fase R1 — Seguridad Semántica, Cuarentena de Laboratorio Sintético y Verdad de Datos  
**Repositorio:** `SistemaLuces` (V1 US500)  
**Marco de Especificación:** SPEC-002, SRS V2.0, ADR-002, PLAN-REALINEACION  
**Veredicto del Gate:** **`PASS`**  

---

## 1. Resumen Ejecutivo y Dictamen del Gate

El Milestone M1 / Fase R1 de `SistemaLuces` ha concluido exitosamente su implementación, auditoría forense, revisiones independientes de arquitectura/UI y pruebas adversariales de sabotaje. 

Todos los agentes intervinientes han emitido dictámenes favorables e independientes:

| Rol / Agente | Función | Tipo de Evaluación | Veredicto |
|---|---|---|:---:|
| `worker_r1` | Implementación de Workstreams M1/R1 | Desarrollo y pruebas unitarias/aceptación | **DONE (348 tests OK)** |
| `reviewer_r1_1` | Revisor de Código y Arquitectura | Revisión de código, AST y aislamiento | **APPROVE** |
| `reviewer_r1_2` | Revisor de Dominio, UI y Contratos | Revisión de 7 estados UI, vocabulario y XSS | **APPROVE** |
| `challenger_r1_1` | Desafío Adversarial de Seguridad | Sabotaje de órdenes, binds y entornos | **APPROVE** |
| `challenger_r1_2` | Desafío Adversarial de Veracidad de Datos | Sabotaje de proyecciones, métricas y XSS | **APPROVE** |
| `auditor_r1_1` | Auditoría Forense de Integridad | Verificación anti-fraude, 0 atajos, 0 mocks | **CLEAN** |

**Dictamen Consolidado de la Puerta:** **`PASS`** (Cumplimiento incondicional de los 5 Criterios de Aceptación de Gate G-R1).

---

## 2. Matriz de Cumplimiento de Workstreams (WS-1.1 a WS-1.5)

| Workstream | Descripción y Requisitos | Componentes y Archivos Modificados | Evidencia Empírica de Verificación | Estado |
|---|---|---|---|:---:|
| **WS-1.1** | **Test Rojo de Procedencia y Estado Seguro (R1-A)**<br>• Requisitos: `RF-L003`, `RF-L004`, `RB-L012`<br>• Diferenciación estricta de 6 entornos permitidos.<br>• Rechazo cerrado de `LIVE`, `REAL`, `PROD`, `PRODUCTION`. | • `src/sistema_luces/domain/vocabulary.py`<br>• `schemas/*.json`<br>• `tests/acceptance/test_semantic_security.py`<br>• `tests/ui/test_semantic_provenance.py` | `parse_environment` devuelve determinísticamente `ENVIRONMENT_NOT_ALLOWED`. Inyección de entornos prohibidos rechazada en dominio, esquemas, DTOs, EventStore y vistas. | **COMPLETO** |
| **WS-1.2** | **Aislamiento del Motor Cuantitativo Histórico (R1-B)**<br>• Requisitos: `RF-L003`, `RNF-L003`, `RB-L012`<br>• Cuarentena de `quant` y generador aleatorio.<br>• Salidas de laboratorio forzadas a `SINTETICO`. | • `src/sistema_luces/ui/server.py`<br>• `scripts/iniciar_servidor_luces.py`<br>• `scripts/laboratorio_sintetico.py` | Servidor HTTP desvinculado de `sistema_luces.quant` (0 imports). `laboratorio_sintetico.py` confinado a CLI independiente con banner persistente `SINTETICO`. | **COMPLETO** |
| **WS-1.3** | **Eliminación de Defaults Ficticios y Propagación de NO_DATA (R1-C)**<br>• Requisitos: `RF-L008`, `RF-L016`, `RNF-L005`, `RB-L003`, `RB-L008`<br>• Purga de métricas hardcodeadas y modelos dummy.<br>• Estado inicial en `NO_DATA` con luz `AMARILLO` y `N/A`. | • `src/sistema_luces/observability/projections.py`<br>• `src/sistema_luces/ui/views.py`<br>• `src/sistema_luces/domain/api.py` | `ProyectorVistas` virgen retorna `health_state="NO_DATA"`, `light="YELLOW"`, `model_id=None`, `reason_codes=("NO_DATA_YELLOW",)`. Métricas renderizan `<span class="metric-na">N/A</span>`. | **COMPLETO** |
| **WS-1.4** | **Ampliación del Escáner de Seguridad Estática y Dinámica (R1-D)**<br>• Requisitos: `RNF-L001`, `RNF-L002`, `RNF-L011`<br>• 0 capacidades de órdenes en todo el repo.<br>• Bind exclusivo a `127.0.0.1`, 405 en mutantes, 0 fugas. | • `tests/architecture/policy_check.py`<br>• `tests/architecture/test_forbidden_capabilities.py`<br>• `scripts/verificar_seguridad_completa.py` | Escaneo AST cubre `src/`, `scripts/`, `config/`, `contracts/`, `schemas/`, `ui/`, `Makefile`, `pyproject.toml` (0 violaciones). Loopback fail-closed y 405 verificados dinámicamente. | **COMPLETO** |
| **WS-1.5** | **Normalización de Vocabulario Canónico y Estados (R1-E)**<br>• Requisitos: `RF-L017`, `RF-L020`, `RB-L001`<br>• Tríada en español: Verde=`LARGO`, Amarillo=`MONITORIZAR`, Rojo=`CORTO`.<br>• Matriz de 7 estados canónicos de UI. | • `src/sistema_luces/domain/vocabulary.py`<br>• `src/sistema_luces/ui/views.py` | UI y DTOs aplican vocabulario canónico. Implementación determinista de los 7 estados (`cargando`, `vacio`, `parcial`, `error`, `obsoleto`, `conflicto`, `exito`) con sanitización XSS. | **COMPLETO** |

---

## 3. Criterios de Aceptación de Gate G-R1 y Cadenas de Evidencia

### Criterio 1: Procedencia y Aislamiento Semántico (RF-L003, RB-L012)
- **Especificación:** La UI y las Proyecciones deben iniciar en `NO_DATA` o `SINTETICO` inequívoco. Cero nombres de brokers («Pepperstone») ni afirmaciones de «en vivo» sin evidencia. Los tests deben fallar si se emiten payloads sintéticos con etiquetas reales.
- **Cadena de Evidencia:**
  1. *Aislamiento de Entornos:* `vocabulary.py` delimita los entornos a `{"NO_DATA", "SINTETICO", "REPLAY", "SHADOW", "DEMO_OBSERVADO", "BROKER_DEMO_OBSERVED"}`. La función `parse_environment()` intercepta variantes de `LIVE`, `REAL`, `PROD`, `PRODUCTION`, retornando `ENVIRONMENT_NOT_ALLOWED`.
  2. *Etiquetado Obligatorio:* Todo cálculo emitido desde `scripts/laboratorio_sintetico.py` lleva `environment="SINTETICO"`. La UI inyecta el banner visual destacado `LABORATORIO SINTÉTICO` en la cabecera.
  3. *Eliminación de Claims Engañosos:* Se eliminaron del código fuente todas las referencias a `Pepperstone`, `cTrader Live`, `COMPRA FUERTE`, `VENTA FUERTE` y claims de precisión infundados.
  4. *Verificación de Rechazo:* `tests/acceptance/test_semantic_security.py` y `tests/ui/test_semantic_provenance.py` comprueban que cualquier intento de persistir o renderizar datos sin procedencia válida es rechazado inmediatamente.

### Criterio 2: Honestidad de Métricas y Datos Ausentes (RNF-L005, RB-L003, RB-L008)
- **Especificación:** Cero métricas ficticias hardcodeadas. Datos ausentes producen `None`/`null` y se muestran como `N/A` o estado amarillo `MONITORIZAR`. P&L y riesgo permanecen en `N/A` hasta la validación del contrato económico en R3.
- **Cadena de Evidencia:**
  1. *Purga de Defaults:* Eliminadas las constantes estáticas de Sharpe, Hit Rate, Drawdown y modelos dummy `logreg-v1`.
  2. *Comportamiento Inicial Determinado:* `ProyectorVistas` virgen retorna `health_state="NO_DATA"`, `light="YELLOW"`, `model_id=None`, `model_version=None`, `model_hash=None`, `reason_codes=("NO_DATA_YELLOW",)` y `documents=()`.
  3. *Formateo Visual Honesto:* `views.py:format_metric_value()` ante `val is None` produce `<span class="metric-na" title="...">N/A</span>` con descripciones explícitas del motivo de nulidad.
  4. *Modo Seguro en Fallas:* Ante estados `vacio`, `cargando`, `error` o `conflicto`, el semáforo conmuta invariablemente a `AMARILLO · MONITORIZAR`.

### Criterio 3: Seguridad Estricta y Cero Órdenes (RNF-L001, RNF-L002, RNF-L011)
- **Especificación:** Escaneo AST integral con 0 violaciones y 0 capacidades de órdenes. Servidor HTTP enlazado exclusivamente a `127.0.0.1`, rechazando verbos mutantes (`POST`, `PUT`, `DELETE`, `PATCH`) con `405 Method Not Allowed`.
- **Cadena de Evidencia:**
  1. *Escáner AST Integral:* `tests/architecture/policy_check.py` analiza 34 símbolos prohibidos de trading/ordenes a lo largo de `src/`, `scripts/`, `config/`, `contracts/`, `schemas/`, `ui/`, `Makefile` y `pyproject.toml`, reportando 0 violaciones.
  2. *Enlace Estricto a Loopback:* `ServidorLoopback` en `src/sistema_luces/ui/server.py` evalúa `if host != "127.0.0.1": raise ValueError(...)`, garantizando fallo cerrado ante `0.0.0.0` o IPs remotas.
  3. *Rechazo de Métodos Mutantes:* `ManejadorServidorLoopback` intercepta peticiones `POST`, `PUT`, `DELETE`, `PATCH`, respondiendo con HTTP `405 Method Not Allowed` y cabecera `Allow: GET, HEAD, OPTIONS`.
  4. *Cabeceras de Seguridad:* Emisión obligatoria de `Content-Security-Policy`, `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff` y `Referrer-Policy: no-referrer`.
  5. *Segregación de Base Externa:* Cero lecturas/escrituras a `tj.db`; `luces.db` es la única base SQLite propia.
  6. *Cero Fugas de Secretos y Rutas:* Cero claves privadas, tokens hardcodeados o rutas absolutas de desarrollo (`/Users/`, `/home/`) en el código runtime.

### Criterio 4: Prueba Adversarial y Sabotaje de Invariantes
- **Especificación:** Comprobación empírica independiente mediante inyección de fallos y sabotaje de invariantes, validando que el sistema opera en modo fail-closed.
- **Cadena de Evidencia:**
  1. *Sabotaje de Órdenes:* Inyección temporal de `def send_order()` y `class OrderGateway` fue detectada inmediatamente por `verificar_seguridad_completa.py` (código de salida 1, violación `FORBIDDEN_ORDER_CAPABILITY`).
  2. *Sabotaje de Binding de Red:* Intentos de instanciar `ServidorLoopback(host="0.0.0.0")` o inyectar `SERVER_HOST = "0.0.0.0"` provocaron `ValueError` en runtime y fallo estático en el escáner (`FORBIDDEN_NON_LOOPBACK`).
  3. *Sabotaje de Entornos Prohibidos:* Peticiones con `LIVE`, `REAL`, `PROD`, `PRODUCTION` fueron interceptadas uniformemente en dominio, esquemas, DTOs y almacenamiento con `ENVIRONMENT_NOT_ALLOWED`.
  4. *Sabotaje de Verbos HTTP:* Envío de solicitudes `POST`, `PUT`, `DELETE` a `/`, `/v1/status`, `/v1/view`, `/v1/orders` resultó en HTTP `405 Method Not Allowed`.
  5. *Sabotaje de Inyección XSS:* Inyección de vectores `<script>`, `<img>`, `<svg>` en campos de la vista fue neutralizada al 100% mediante `html.escape` bajo CSP estricto.
  6. *Sabotaje de Base de Datos Externa:* Intentos de referenciar `tj.db` fueron detectados como `FORBIDDEN_JOURNAL_DATABASE`.

### Criterio 5: Archivo Formal de Evidencia y Trazabilidad
- **Especificación:** Trazabilidad documental completa y archivo de reportes de handoff de todos los agentes participantes en `.agents/` y `docs/teamwork/run/gates/G-R1.md`.
- **Cadena de Evidencia:**
  1. Estado del Gate registrado en `.agents/orchestrator_r1/GATE_STATUS.md`.
  2. Handoff de implementación archivado en `.agents/worker_r1/handoff.md`.
  3. Handoffs de revisión archivados en `.agents/reviewer_r1_1/handoff.md` y `.agents/reviewer_r1_2/handoff.md`.
  4. Handoffs de desafío adversarial archivados en `.agents/challenger_r1_1/handoff.md` y `.agents/challenger_r1_2/handoff.md`.
  5. Handoff de auditoría forense archivado en `.agents/auditor_r1_1/handoff.md`.
  6. Documento de certificación y evidencia formal consolidado en `docs/teamwork/run/gates/G-R1.md`.

---

## 4. Comandos de Verificación y Salidas Verbatim de Terminal

### 4.1 Verificador Documental y Autoridad Canónica
**Comando:**
```bash
python3.11 -B scripts/verificar_documentacion.py
```
**Salida de Terminal (Exit Code 0):**
```text
DOCUMENTACION: PASS (23 archivos canónicos verificados)
AUTORIDAD: PASS (sin claims históricos prohibidos)
LINKS: PASS
LEGADO: PASS (aislado y preservado)
```

### 4.2 Verificador Integral de Seguridad y Arquitectura (Gate G-R1)
**Comando:**
```bash
python3.11 -B scripts/verificar_seguridad_completa.py
```
**Salida de Terminal (Exit Code 0):**
```text
======================================================================
🚦 SISTEMA DE LUCES — VERIFICADOR DE SEGURIDAD INTEGRAL (GATE G-R1)
======================================================================
🔍 [1/3] Ejecutando escaneo estático de seguridad y capacidades prohibidas...
   ✅ Escáner estático: 0 violaciones detectadas.
🔒 [2/3] Verificando enlace exclusivo a loopback 127.0.0.1 y rechazo de IPs remotas...
   ✅ ServidorLoopback rechazó host no-loopback (0.0.0.0) correctamente (fail-closed).
   ✅ ServidorLoopback rechazó IP remota correctamente.
   ✅ ServidorLoopback aceptó '127.0.0.1' correctamente.
🛡️  [3/3] Verificando rechazo 405 de verbos mutantes y headers de seguridad...
   ✅ Todos los métodos mutantes rechazados con 405 y cabeceras de seguridad verificadas.
----------------------------------------------------------------------
✅ RESULTADO: PASS (Seguridad Estática y Dinámica Verificada para Gate G-R1)
======================================================================
```

### 4.3 Suite Completa de Pruebas Unitarias, UI, Aceptación y Arquitectura
**Comando:**
```bash
python3.11 -B -m unittest discover -s tests -t . -v
```
**Salida de Terminal (Exit Code 0):**
```text
Ran 348 tests in 1.878s

OK
```

### 4.4 Verificación Canónica del Repositorio (Make Target)
**Comando:**
```bash
make verify
```
**Salida de Terminal (Exit Code 0):**
```text
Ran 348 tests in 1.820s

OK
```

---

## 5. Condiciones de Invalidación y Próximos Pasos (Transición a R2)

### Condiciones de Invalidación del Gate:
1. Reintroducción de cualquier símbolo o método de colocación/modificación de órdenes en `src/` o `scripts/`.
2. Habilitación de enlaces del servidor HTTP fuera de `127.0.0.1`.
3. Cualquier respuesta con código de estado HTTP $\neq 405$ ante verbos `POST`, `PUT`, `DELETE` o `PATCH`.
4. Presentación en la UI de datos sintéticos o simulados sin el banner de laboratorio `SINTETICO`.
5. Omisión del estado `NO_DATA` o renderizado de valores numéricos ficticios ante ausencia de datos.
6. Cualquier intento de lectura o conexión a la base de datos externa `tj.db`.

### Conclusión y Transición a Fase R2:
Habiendo satisfecho plenamente todos los requerimientos de seguridad semántica, cuarentena del laboratorio sintético, veracidad de datos y pruebas adversariales de Gate G-R1, el repositorio queda formalmente certificado para iniciar la **Fase R2: Un solo pipeline y Proyección de lectura (Milestone M2)**, conforme al plan de realineación técnica.
