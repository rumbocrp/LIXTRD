# Sistema visual — extensión «Índice de Mercado» para Luces

**Estado:** contrato objetivo  
**Referencia:** sistema visual de Trading Journal, inspeccionado en solo lectura  
**Regla:** compatibilidad por snapshot/versionado, no dependencia runtime

## 1. Dirección

SistemaLuces debe sentirse como otra sección del Trading Journal, no como una terminal de
neón ni como un producto genérico separado. La pantalla es sobria, densa y verificable:

- mismo shell conceptual: rail en escritorio, menú único en móvil, topbar y contenido;
- mismos tokens semánticos y de componente en temas claro/nocturno;
- cifras tabulares y unidades visibles;
- verde, amarillo y rojo como estados, nunca como decoración;
- violeta reservado para acción/foco de plataforma, no para competir con la luz;
- sin glow, glassmorphism, blur, gradientes decorativos ni animaciones continuas;
- movimiento limitado a opacity/transform y anulado por `prefers-reduced-motion`.

## 2. Fuente del diseño

Trading Journal conserva la fuente original de tokens. SistemaLuces genera un snapshot local:

```text
journal_visual_contract_version
source_commit_or_snapshot_hash
primitive[claro|nocturno]
semantic
component
spacing
radius
typography
motion
```

Los componentes consumen sólo capas `semantic` o `component`. La actualización del snapshot
es una tarea explícita con contraste y revisión visual; no se sincroniza automáticamente y
no escribe en el Journal.

## 3. Arquitectura de información

La ruta standalone y la futura `/luces` comparten cinco zonas:

1. **Resumen actual:** luz+palabra, dirección, vigencia y estado de procedencia.
2. **Fuente y salud:** cuenta demo seudónima, corte, edad, latencia, gaps e incidentes.
3. **Por qué:** razones, utilidad long/short, campeón, política, costo y riesgo.
4. **Actividad:** línea de tiempo de transiciones y tabla de Operativas simuladas.
5. **Evidencia:** métricas con periodo/muestra, calibración y estado de etiquetas.

La primera pantalla abre con lo que necesita atención: `NO_DATA`, fuente degradada, incidente,
simulación abierta o cambio de luz. No abre con KPIs de vanidad.

## 4. Composición de la pantalla principal

```text
┌ Topbar: Sistema de Luces · DEMO/REPLAY/SHADOW · fuente · edad ┐
├ Estado que necesita atención / NO_DATA                         ┤
├ Luz + palabra + vigencia       │ Salud de fuente/modelo        ┤
├ Razones y utilidad neta        │ Perfil/costos/política         ┤
├ Línea de tiempo de transiciones                               ┤
├ Operativas simuladas y conciliación                            ┤
└ Métricas con muestra, periodo, versión y N/A con motivo        ┘
```

En móvil se mantiene una sola navegación primaria. Tablas densas refluyen a pares
etiqueta/valor; ninguna tabla obliga a scroll horizontal para leer su fila esencial.

## 5. Semántica de luz

| Luz | Texto obligatorio | Uso |
|---|---|---|
| verde | `LARGO` | utilidad long válida y dominante |
| amarillo | `MONITORIZAR` | abstención, incertidumbre o seguridad |
| rojo | `CORTO` | utilidad short válida y dominante |

Siempre se acompaña de razón y vigencia. Icono, texto, estructura y `aria-label` mantienen el
significado en forced colors y para personas que no distinguen el tono.

### 5.1 Diagnóstico de transición

Debajo del semáforo se muestra una barra de umbrales, no un adorno de progreso:

- eje de `0 %` a `100 %` para la probabilidad calibrada larga;
- zona roja hasta `threshold_red`, amarilla entre umbrales y verde desde `threshold_green`;
- marcador numérico actual y probabilidades `LARGO`/`CORTO`;
- texto de distancia: umbral alcanzado o puntos porcentuales faltantes;
- fuente de los umbrales y evento que originó el diagnóstico.

La barra usa `role="progressbar"`, cifra y etiquetas textuales. El color nunca es el único
canal. No se confunde confianza del modelo con avance hacia un umbral.

Cada activo observado — SP500, TSLA, AAPL y oro — reserva una barra diagnóstica propia. La
barra sólo se activa con probabilidades y umbrales verificables de ese símbolo; de lo
contrario muestra N/A. Una relación SP500–AAPL/SP500–TSLA puede usar además una barra
secundaria de score hacia su umbral cuando exista evidencia explícita.
La fila debe conservar score exacto, objetivo, confianza, fuente y edad; si no existe un
`CROSS_ASSET_SNAPSHOT` explícito, la tabla permanece vacía.

## 6. Estados de interfaz

| Estado | Mensaje y salida |
|---|---|
| cargando | qué se está esperando; sin valores previos presentados como actuales |
| vacío / `NO_DATA` | «Todavía no hay evidencia» + acción/condición necesaria |
| parcial | qué existe y qué falta; valores faltantes en N/A |
| error | causa segura, impacto y recuperación posible |
| obsoleto | edad visible, última evidencia y luz forzada a amarillo |
| conflicto | versión/contrato incompatible; no se renderiza a medias |
| éxito | confirmación discreta; no sustituye el estado persistido |

`SINTETICO` lleva una banda persistente y no puede usar etiquetas «Pepperstone», «demo
observada» ni «en vivo».

## 7. Métricas honestas

Cada métrica presenta:

- nombre y unidad;
- valor o N/A con razón;
- rango temporal;
- muestra total, efectiva, madura y pendiente;
- entorno y fuente;
- modelo/política/costos;
- enlace o identificador de linaje.

Accuracy, Sharpe, drawdown y P&L no aparecen como defaults. Una pantalla sin datos muestra
vacío, no números de demostración.

## 8. Accesibilidad y calidad

- WCAG 2.2 AA en claro y nocturno;
- 44 px para objetivos táctiles salvo excepción declarada;
- 16 px mínimo en campos móviles;
- navegación completa por teclado, foco visible y enlaces de salto;
- una sola región de estado atómica anuncia transiciones de conexión, no cada tick;
- charts con resumen y tabla/fallback accesible;
- el documento se carga una vez y los elementos declarados se actualizan cada 2 s cuando la
  pestaña está visible y cada 10 s cuando está oculta; no se reemplazan página, foco ni scroll;
- reserva de espacio para diagnóstico y valores tabulares, evitando saltos de layout;
- para la fuente pública Yahoo, timestamp,
  latencia, granularidad y `MERCADO CERRADO` distinguen conexión de actualidad del precio;
- contraste automatizado sobre pares reales y guardián de tokens;
- pruebas en 320/360/390/414 px y escritorio.

## 9. Anti-patrones bloqueantes

- pantalla «cerebro cuantitativo» con estética de control tower;
- datos aleatorios rotulados como broker;
- métricas prefijadas o claims de superioridad;
- luz alimentada por un motor distinto al pipeline auditado;
- color como único canal;
- múltiples navegaciones primarias visibles;
- copiar hexadecimales o clases desde el Journal sin snapshot/versionado.
