"""Generador de Plantillas HTML para el Sistema de Luces 2.0 (Fase 6).
Cumple al 100% con la especificación Anti-AI Slop y UI/UX Pro Max:
- Cero dependencias externas CDN (autocontenido).
- Estilo gráfico de grado industrial tipo terminal de trading Bloomberg/Linear.
- Bisel óptico mecanizado con diodos LED de alta fidelidad.
- Cifras tabulares monoespaciadas y telemetría en tiempo real.
"""

def generate_console_html() -> str:
    return """<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SISTEMA DE LUCES 2.0 | CONSOLA CUANTITATIVA INDUSTRIAL</title>
    <link rel="stylesheet" href="/static/styles.css">
</head>
<body>
    
    <!-- ENCABEZADO SUPERIOR INDUSTRIAL (TOPBAR) -->
    <header class="console-header">
        <div class="brand-section">
            <div class="brand-badge">PRO MAX 2.0</div>
            <div class="brand-title">SISTEMA DE LUCES</div>
            <div class="pair-selector-bar">
                <button class="pair-tab active" data-pair="XAUUSD">XAUUSD</button>
                <button class="pair-tab" data-pair="TSLA">TSLA</button>
                <button class="pair-tab" data-pair="AAPL">AAPL</button>
            </div>
        </div>

        <div class="system-status-pills">
            <div class="status-pill">
                <div class="status-dot healthy" id="status-dot"></div>
                <span>DATOS: <strong id="val-health" class="tabular-nums">HEALTHY</strong></span>
            </div>
            <div class="status-pill">
                <span>LATENCIA: <strong id="val-latency" class="tabular-nums">1.2ms</strong></span>
            </div>
            <div class="status-pill">
                <span>MODELO: <strong id="val-model-id" class="tabular-nums">kalman-ofi-v2.0</strong></span>
            </div>
            <div class="status-pill">
                <span>UTC: <strong id="val-clock" class="tabular-nums">--:--:--</strong></span>
            </div>
            <button id="btn-hard-veto" class="pair-tab" style="background-color: var(--ruby-600); color: var(--ruby-400); border-color: var(--ruby-400); font-weight: 700;">
                [⌘V] HARD VETO
            </button>
        </div>
    </header>

    <!-- CUERPO PRINCIPAL EN 3 COLUMNAS -->
    <main class="console-main">
        
        <!-- COLUMNA 1: BALIZA FÍSICA Y ESTADO DE DECISIÓN -->
        <section class="console-card">
            <div class="card-header">
                <span class="card-title">BALIZA ÓPTICA DE DECISIÓN</span>
                <span id="badge-action" class="brand-badge" style="color: var(--amber-400);">MONITOR</span>
            </div>

            <!-- BISEL MECANIZADO DE HARDWARE -->
            <div class="optical-telemetry-container">
                <div class="optical-bezel traffic-light-bezel">
                    <div id="light-red" class="diode diode-red inactive">
                        <div class="specular-dot light-specular"></div>
                    </div>
                    <div id="light-yellow" class="diode diode-yellow active">
                        <div class="specular-dot light-specular"></div>
                    </div>
                    <div id="light-green" class="diode diode-green inactive">
                        <div class="specular-dot light-specular"></div>
                    </div>
                </div>
                <div id="text-beacon-state" class="beacon-state-text YELLOW">AMARILLO / STANDBY</div>
            </div>

            <!-- PROBABILIDAD Y UTILIDADES -->
            <div class="kpi-grid">
                <div class="kpi-cell">
                    <span class="kpi-label">CONFIANZA CALIBRADA</span>
                    <span id="val-confidence" class="kpi-value tabular-nums">50.0%</span>
                </div>
                <div class="kpi-cell">
                    <span class="kpi-label">CALIDAD CALIBRACIÓN</span>
                    <span id="val-calib" class="kpi-value tabular-nums">0.92</span>
                </div>
                <div class="kpi-cell">
                    <span class="kpi-label">UTILIDAD LONG (NETA)</span>
                    <span id="val-u-long" class="kpi-value tabular-nums">+0.00%</span>
                </div>
                <div class="kpi-cell">
                    <span class="kpi-label">UTILIDAD SHORT (NETA)</span>
                    <span id="val-u-short" class="kpi-value tabular-nums">+0.00%</span>
                </div>
            </div>

            <!-- ESPECTRO BID / ASK -->
            <div class="spectrum-bar-container">
                <div style="display: flex; justify-content: space-between; font-size: 10px; color: var(--text-muted);">
                    <span>PRESIÓN COMPRADORA</span>
                    <span>PRESIÓN VENDEDORA</span>
                </div>
                <div class="spectrum-bar">
                    <div id="bar-bid" class="spectrum-segment-bid" style="width: 50%;"></div>
                    <div id="bar-ask" class="spectrum-segment-ask" style="width: 50%;"></div>
                </div>
            </div>

            <!-- ESPECTRO AGUDO DE EJECUCIÓN & RIESGO SIMULADO -->
            <div style="display: flex; flex-direction: column; gap: var(--space-xs); border-top: 1px solid var(--border-subtle); padding-top: var(--space-sm); margin-top: var(--space-xs);">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <span class="kpi-label">RIESGO SIMULADO</span>
                    <span id="badge-risk-tier" class="brand-badge" style="color: var(--emerald-400);">OPTIMAL_TOUCH</span>
                </div>
                <div style="display: flex; justify-content: space-between; align-items: baseline;">
                    <span id="val-simulated-risk-pct" class="kpi-value tabular-nums" style="font-size: 20px; font-weight: 700; color: var(--text-primary);">12.4%</span>
                    <span style="font-size: 10px; color: var(--text-muted);">VaR 95%: <strong id="val-sim-var" class="tabular-nums text-sand-300">1.25%</strong> | CVaR: <strong id="val-sim-cvar" class="tabular-nums text-sand-300">1.68%</strong></span>
                </div>
                <div class="spectrum-bar" style="height: 6px; background-color: var(--obsidian-800);">
                    <div id="bar-risk-gauge" class="spectrum-segment-risk" style="width: 12.4%; height: 100%; background-color: var(--emerald-500); transition: width 0.1s ease, background-color 0.2s ease;"></div>
                </div>
                <div style="display: flex; justify-content: space-between; font-size: 9px; color: var(--text-muted);">
                    <span>SLIPPAGE AGUDO: <strong id="val-acute-slip" class="tabular-nums">0.02 pips</strong></span>
                    <span>AGUDEZA: <strong id="val-acute-sharpness" class="tabular-nums">18.2 / 100</strong></span>
                </div>
            </div>
        </section>

        <!-- COLUMNA 2: MICROESTRUCTURA CUANTITATIVA Y FLUIDEZ L2 -->
        <section class="console-card">
            <div class="card-header">
                <span class="card-title">MICROESTRUCTURA & COINTEGRACIÓN (L2)</span>
                <span class="brand-badge">NIVELES K=5</span>
            </div>

            <div class="kpi-grid" style="grid-template-columns: repeat(2, 1fr);">
                <div class="kpi-cell">
                    <span class="kpi-label">KALMAN SPREAD Z-SCORE</span>
                    <span id="val-kalman-z" class="kpi-value tabular-nums">0.00</span>
                    <span style="font-size: 10px; color: var(--text-muted);">BETA ADAPTATIVO: <strong id="val-kalman-beta" class="tabular-nums text-sand-300">-18.50</strong></span>
                </div>
                <div class="kpi-cell">
                    <span class="kpi-label">ORDER FLOW IMBALANCE (OFI)</span>
                    <span id="val-ofi" class="kpi-value tabular-nums">0.00</span>
                    <span style="font-size: 10px; color: var(--text-muted);">DECAIMIENTO: <strong>κ = 0.65</strong></span>
                </div>
                <div class="kpi-cell">
                    <span class="kpi-label">STOIKOV MICRO-PRICE DELTA</span>
                    <span id="val-micro-delta" class="kpi-value tabular-nums">0 ppm</span>
                    <span style="font-size: 10px; color: var(--text-muted);">DESPLAZAMIENTO COLA</span>
                </div>
                <div class="kpi-cell">
                    <span class="kpi-label">TOXICIDAD VPIN (50 CUBOS)</span>
                    <span id="val-vpin" class="kpi-value tabular-nums" style="color: var(--emerald-400);">0.12</span>
                    <span style="font-size: 10px; color: var(--emerald-400);">RIESGO ADVERSO BAJO</span>
                </div>
            </div>

            <!-- REGISTRO DE RAZONES CANÓNICAS -->
            <div style="display: flex; flex-direction: column; gap: var(--space-xs);">
                <span class="kpi-label">CÓDIGOS DE RAZÓN EMITIDOS</span>
                <div id="list-reasons" class="reason-tags-list">
                    <span class="reason-tag">MONITOR_HYSTERESIS_HOLD</span>
                </div>
            </div>

            <!-- TABLA DE ÚLTIMAS TRANSICIONES -->
            <div style="flex: 1; display: flex; flex-direction: column; gap: var(--space-xs); overflow: hidden;">
                <span class="kpi-label">HISTORIAL DE EVENTOS RECIENTES</span>
                <div style="overflow-y: auto; max-height: 180px; border: 1px solid var(--border-subtle); border-radius: 4px;">
                    <table class="dense-table">
                        <thead>
                            <tr>
                                <th>HORA (UTC)</th>
                                <th>PAR</th>
                                <th>ESTADO</th>
                                <th>ACCIÓN</th>
                                <th>Z-SCORE</th>
                                <th>CONFIANZA</th>
                            </tr>
                        </thead>
                        <tbody id="table-history-body">
                            <tr>
                                <td class="tabular-nums">--:--:--</td>
                                <td>XAUUSD</td>
                                <td style="color: var(--amber-400);">YELLOW</td>
                                <td>MONITOR</td>
                                <td class="tabular-nums">0.00</td>
                                <td class="tabular-nums">50.0%</td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </div>
        </section>

        <!-- COLUMNA 3: SUPERVISIÓN HUMANA, DIALES Y TESORERÍA -->
        <section class="console-card">
            <div class="card-header">
                <span class="card-title">SUPERVISIÓN & TESORERÍA DE RIESGO</span>
                <span class="brand-badge">HITL</span>
            </div>

            <!-- TESORERÍA DE EVIDENCIA -->
            <div class="kpi-grid">
                <div class="kpi-cell">
                    <span class="kpi-label">PRESUPUESTO RESTANTE</span>
                    <span id="val-remaining-budget" class="kpi-value tabular-nums" style="color: var(--emerald-400);">$200.00</span>
                    <span style="font-size: 10px; color: var(--text-muted);">LÍMITE DIARIO: $200.00 (2.0%)</span>
                </div>
                <div class="kpi-cell">
                    <span class="kpi-label">BRIER SCORE (CALIB)</span>
                    <span id="val-brier-score" class="kpi-value tabular-nums">0.102</span>
                    <span style="font-size: 10px; color: var(--text-muted);">ALARMA: &gt; 0.165</span>
                </div>
            </div>

            <!-- DIALES DE CONTROL EN CALIENTE -->
            <div style="display: flex; flex-direction: column; gap: var(--space-sm); border: 1px solid var(--border-subtle); padding: var(--space-sm); border-radius: 4px; background-color: var(--bg-inset);">
                <span class="kpi-label">DIALES INTERACTIVOS DEL OPERADOR</span>
                
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <span style="font-size: 11px; color: var(--text-secondary);">UMBRAL ENTRADA (T_in):</span>
                    <strong id="dial-t-entry" class="tabular-nums" style="color: var(--text-primary);">0.45</strong>
                </div>
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <span style="font-size: 11px; color: var(--text-secondary);">UMBRAL SALIDA (T_out):</span>
                    <strong id="dial-t-exit" class="tabular-nums" style="color: var(--text-primary);">0.15</strong>
                </div>
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <span style="font-size: 11px; color: var(--text-secondary);">Z-SCORE CRÍTICO:</span>
                    <strong id="dial-z-crit" class="tabular-nums" style="color: var(--text-primary);">1.20</strong>
                </div>
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <span style="font-size: 11px; color: var(--text-secondary);">OFI CRÍTICO (L2):</span>
                    <strong id="dial-ofi-crit" class="tabular-nums" style="color: var(--text-primary);">20.0</strong>
                </div>
            </div>

            <!-- PUERTA CAMPEÓN / RETADOR -->
            <div style="display: flex; flex-direction: column; gap: var(--space-xs); border: 1px solid var(--border-subtle); padding: var(--space-sm); border-radius: 4px; background-color: var(--bg-inset);">
                <span class="kpi-label">PUERTA CAMPEÓN / RETADOR ML</span>
                <div style="display: flex; justify-content: space-between; font-size: 11px;">
                    <span style="color: var(--text-secondary);">ESTUDIANTE ML:</span>
                    <span style="color: var(--text-primary);">IQL + AWBC</span>
                </div>
                <div style="display: flex; justify-content: space-between; font-size: 11px;">
                    <span style="color: var(--text-secondary);">TICKS SOMBRA:</span>
                    <strong class="tabular-nums" style="color: var(--text-primary);">10,000 / 10,000</strong>
                </div>
                <div style="display: flex; justify-content: space-between; font-size: 11px;">
                    <span style="color: var(--text-secondary);">DIEBOLD-MARIANO:</span>
                    <strong style="color: var(--emerald-400);">p &lt; 0.001 (SUPERIOR)</strong>
                </div>
                <div style="margin-top: 4px; font-size: 10px; color: var(--text-muted);">
                    * Promoción a producción bloqueada hasta firma criptográfica Ed25519 del operador.
                </div>
            </div>

            <!-- MONITOR DE OPERATIVAS SIMULADAS EN VIVO -->
            <div style="display: flex; flex-direction: column; gap: var(--space-xs); border: 1px solid var(--border-subtle); padding: var(--space-sm); border-radius: 4px; background-color: var(--bg-inset);">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <span class="kpi-label">OPERATIVA SIMULADA (MODELO)</span>
                    <span id="val-sim-op-status" class="brand-badge" style="color: var(--text-muted);">STANDBY</span>
                </div>
                <div style="display: flex; justify-content: space-between; font-size: 11px;">
                    <span style="color: var(--text-secondary);">POSICIÓN ACTIVA:</span>
                    <strong id="val-sim-op-dir" class="tabular-nums" style="color: var(--text-primary);">NINGUNA</strong>
                </div>
                <div style="display: flex; justify-content: space-between; font-size: 11px;">
                    <span style="color: var(--text-secondary);">ENTRADA AGUDA:</span>
                    <strong id="val-sim-op-entry" class="tabular-nums" style="color: var(--text-primary);">--</strong>
                </div>
                <div style="display: flex; justify-content: space-between; font-size: 11px;">
                    <span style="color: var(--text-secondary);">PNL FLOTANTE:</span>
                    <strong id="val-sim-op-pnl" class="tabular-nums" style="color: var(--text-muted);">$0.00</strong>
                </div>
                <div style="display: flex; justify-content: space-between; font-size: 10px; color: var(--text-muted); border-top: 1px solid var(--border-subtle); padding-top: 4px; margin-top: 2px;">
                    <span>WIN: <strong id="val-sim-win-rate" class="tabular-nums text-sand-300">50.0%</strong></span>
                    <span>OPS: <strong id="val-sim-total-trades" class="tabular-nums">0</strong></span>
                    <span>PNL ACUM: <strong id="val-sim-realized-pnl" class="tabular-nums">$0.00</strong></span>
                </div>
            </div>

        </section>

    </main>

    <!-- PALETA DE COMANDOS MODAL (⌘K) -->
    <div id="cmd-palette" class="command-palette-backdrop">
        <div class="command-palette-modal">
            <input id="cmd-input" type="text" class="command-input" placeholder="Escribe un comando... (ej: 'veto', 'gold', 'tsla', 'mute')">
            <ul class="command-list">
                <li class="command-item" data-action="veto">
                    <span>Activar / Desactivar Hard Veto Manual</span>
                    <span class="command-shortcut">⌘V</span>
                </li>
                <li class="command-item" data-action="pair-XAUUSD">
                    <span>Cambiar Activo a XAUUSD (Oro vs DXY)</span>
                    <span class="command-shortcut">1</span>
                </li>
                <li class="command-item" data-action="pair-TSLA">
                    <span>Cambiar Activo a TSLA (Beta SP500)</span>
                    <span class="command-shortcut">2</span>
                </li>
                <li class="command-item" data-action="pair-AAPL">
                    <span>Cambiar Activo a AAPL (Ancla SP500)</span>
                    <span class="command-shortcut">3</span>
                </li>
                <li class="command-item" data-action="mute">
                    <span>Silenciar Micro-Clicks Web Audio</span>
                    <span class="command-shortcut">Space</span>
                </li>
            </ul>
        </div>
    </div>

    <script src="/static/app.js"></script>
</body>
</html>
"""

# Alias para compatibilidad
render_industrial_console_html = generate_console_html
