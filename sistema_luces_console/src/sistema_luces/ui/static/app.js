/**
 * Cliente WebSocket & Controlador de Consola Anti-AI Slop de Alta Frecuencia (5-6 Ticks/s).
 */

class TrafficLightClient {
    constructor() {
        this.ws = null;
        this.audioCtx = null;
        this.audioMuted = false;
        this.lastState = null;
        this.activeSymbol = "XAUUSD";
        this.isPollingFallback = false;
        
        this.initElements();
        this.initAudio();
        this.initKeyboard();
        this.initCommandPalette();
        this.connect();
    }

    initElements() {
        this.elHealth = document.getElementById("val-health");
        this.elStatusDot = document.getElementById("status-dot");
        this.elLatency = document.getElementById("val-latency");
        this.elModelId = document.getElementById("val-model-id");
        this.elClock = document.getElementById("val-clock");
        
        this.elBadgeAction = document.getElementById("badge-action");
        this.elLightRed = document.getElementById("light-red");
        this.elLightYellow = document.getElementById("light-yellow");
        this.elLightGreen = document.getElementById("light-green");
        this.elTextBeacon = document.getElementById("text-beacon-state");
        
        this.elConfidence = document.getElementById("val-confidence");
        this.elCalib = document.getElementById("val-calib");
        this.elULong = document.getElementById("val-u-long");
        this.elUShort = document.getElementById("val-u-short");
        this.elBarBid = document.getElementById("bar-bid");
        this.elBarAsk = document.getElementById("bar-ask");
        
        this.elKalmanZ = document.getElementById("val-kalman-z");
        this.elKalmanBeta = document.getElementById("val-kalman-beta");
        this.elOFI = document.getElementById("val-ofi");
        this.elMicroDelta = document.getElementById("val-micro-delta");
        this.elVPIN = document.getElementById("val-vpin");
        
        this.elRemainingBudget = document.getElementById("val-remaining-budget");
        this.elBrierScore = document.getElementById("val-brier-score");
        this.elReasons = document.getElementById("list-reasons");
        this.tableHistoryBody = document.getElementById("table-history-body");
        
        // Espectro agudo de ejecución y riesgo simulado
        this.elSimulatedRiskPct = document.getElementById("val-simulated-risk-pct");
        this.elBadgeRiskTier = document.getElementById("badge-risk-tier");
        this.elSimVar = document.getElementById("val-sim-var");
        this.elSimCvar = document.getElementById("val-sim-cvar");
        this.elBarRiskGauge = document.getElementById("bar-risk-gauge");
        this.elAcuteSlip = document.getElementById("val-acute-slip");
        this.elAcuteSharpness = document.getElementById("val-acute-sharpness");
        
        // Monitor de operativas simuladas
        this.elSimOpStatus = document.getElementById("val-sim-op-status");
        this.elSimOpDir = document.getElementById("val-sim-op-dir");
        this.elSimOpEntry = document.getElementById("val-sim-op-entry");
        this.elSimOpPnl = document.getElementById("val-sim-op-pnl");
        this.elSimWinRate = document.getElementById("val-sim-win-rate");
        this.elSimTotalTrades = document.getElementById("val-sim-total-trades");
        this.elSimRealizedPnl = document.getElementById("val-sim-realized-pnl");
        
        this.btnHardVeto = document.getElementById("btn-hard-veto");
        if (this.btnHardVeto) {
            this.btnHardVeto.addEventListener("click", () => this.toggleHardVeto());
        }

        // Selector de pares interactivo
        document.querySelectorAll(".pair-tab[data-pair]").forEach(tab => {
            tab.addEventListener("click", (e) => {
                const pair = e.target.dataset.pair;
                this.switchPair(pair);
            });
        });

        // Reloj UTC
        setInterval(() => {
            const now = new Date();
            this.elClock.textContent = now.toISOString().substring(11, 19);
        }, 1000);
    }

    initAudio() {
        try {
            const AudioContext = window.AudioContext || window.webkitAudioContext;
            if (AudioContext) {
                this.audioCtx = new AudioContext();
            }
        } catch (e) {
            console.warn("Web Audio no disponible");
        }
    }

    playMicroClick(frequency = 800) {
        if (this.audioMuted || !this.audioCtx) return;
        if (this.audioCtx.state === 'suspended') {
            this.audioCtx.resume();
        }
        const osc = this.audioCtx.createOscillator();
        const gain = this.audioCtx.createGain();
        osc.type = "sine";
        osc.frequency.setValueAtTime(frequency, this.audioCtx.currentTime);
        gain.gain.setValueAtTime(0.04, this.audioCtx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.0001, this.audioCtx.currentTime + 0.03);
        osc.connect(gain);
        gain.connect(this.audioCtx.destination);
        osc.start();
        osc.stop(this.audioCtx.currentTime + 0.03);
    }

    initKeyboard() {
        window.addEventListener("keydown", (e) => {
            if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "v") {
                e.preventDefault();
                this.toggleHardVeto();
            } else if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
                e.preventDefault();
                this.toggleCommandPalette();
            } else if (e.code === "Space" && e.target.tagName !== "INPUT") {
                e.preventDefault();
                this.audioMuted = !this.audioMuted;
                this.playMicroClick(this.audioMuted ? 300 : 1000);
            } else if (e.key === "1") {
                this.switchPair("XAUUSD");
            } else if (e.key === "2") {
                this.switchPair("TSLA");
            } else if (e.key === "3") {
                this.switchPair("AAPL");
            } else if (e.key === "Escape") {
                this.closeCommandPalette();
            }
        });
    }

    initCommandPalette() {
        this.cmdPalette = document.getElementById("cmd-palette");
        this.cmdInput = document.getElementById("cmd-input");
        if (this.cmdPalette && this.cmdInput) {
            this.cmdPalette.addEventListener("click", (e) => {
                if (e.target === this.cmdPalette) this.closeCommandPalette();
            });
            document.querySelectorAll(".command-item").forEach(item => {
                item.addEventListener("click", () => {
                    const action = item.dataset.action;
                    this.executeAction(action);
                    this.closeCommandPalette();
                });
            });
        }
    }

    toggleCommandPalette() {
        if (!this.cmdPalette) return;
        const isOpen = this.cmdPalette.classList.contains("open");
        if (isOpen) {
            this.closeCommandPalette();
        } else {
            this.cmdPalette.classList.add("open");
            this.cmdInput.focus();
            this.cmdInput.value = "";
        }
    }

    closeCommandPalette() {
        if (this.cmdPalette) this.cmdPalette.classList.remove("open");
    }

    executeAction(action) {
        if (action === "veto") this.toggleHardVeto();
        else if (action === "mute") this.audioMuted = !this.audioMuted;
        else if (action.startsWith("pair-")) this.switchPair(action.replace("pair-", ""));
    }

    switchPair(pair) {
        this.activeSymbol = pair;
        document.querySelectorAll(".pair-tab[data-pair]").forEach(t => {
            if (t.dataset.pair === pair) t.classList.add("active");
            else t.classList.remove("active");
        });
        this.playMicroClick(1000);
    }

    async toggleHardVeto() {
        try {
            const res = await fetch("/api/veto", { method: "POST" });
            const data = await res.json();
            this.playMicroClick(data.is_hard_veto_active ? 400 : 1200);
        } catch (err) {
            console.error("Error al conmutar veto manual:", err);
        }
    }

    connect() {
        const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
        const wsUrl = `${protocol}//${window.location.host}/ws/telemetry`;
        
        try {
            this.ws = new WebSocket(wsUrl);

            this.ws.onmessage = (event) => {
                const data = JSON.parse(event.data);
                this.render(data);
            };

            this.ws.onclose = () => {
                this.startPollingFallback();
                setTimeout(() => this.connect(), 3000);
            };

            this.ws.onerror = () => {
                this.startPollingFallback();
            };
        } catch (e) {
            this.startPollingFallback();
        }
    }

    startPollingFallback() {
        if (this.isPollingFallback) return;
        this.isPollingFallback = true;
        
        setInterval(async () => {
            try {
                const res = await fetch(`/api/state?symbol=${this.activeSymbol}`);
                if (res.ok) {
                    const data = await res.json();
                    if (data.decision) {
                        this.render({
                            ...data.decision,
                            dials: data.dials,
                            treasury: data.treasury
                        });
                    }
                }
            } catch (err) {
                // Silencioso
            }
        }, 200); // 5 veces por segundo
    }

    render(data) {
        const state = data.state;
        
        // Diodos LED
        this.elLightRed.className = `diode diode-red ${state === "RED" ? "active" : "inactive"}`;
        this.elLightYellow.className = `diode diode-yellow ${state === "YELLOW" ? "active" : "inactive"}`;
        this.elLightGreen.className = `diode diode-green ${state === "GREEN" ? "active" : "inactive"}`;

        if (this.lastState && this.lastState !== state) {
            this.playMicroClick(state === "GREEN" ? 1200 : (state === "RED" ? 450 : 800));
        }
        this.lastState = state;

        // Texto de Estado y Acción
        if (state === "GREEN") {
            this.elTextBeacon.className = "beacon-state-text GREEN";
            this.elTextBeacon.textContent = "VERDE / COMPRA";
            this.elBadgeAction.style.color = "var(--emerald-400)";
        } else if (state === "RED") {
            this.elTextBeacon.className = "beacon-state-text RED";
            this.elTextBeacon.textContent = "ROJO / VENTA";
            this.elBadgeAction.style.color = "var(--ruby-400)";
        } else {
            this.elTextBeacon.className = "beacon-state-text YELLOW";
            this.elTextBeacon.textContent = "AMARILLO / STANDBY";
            this.elBadgeAction.style.color = "var(--amber-400)";
        }
        this.elBadgeAction.textContent = data.action;

        // Métricas Numéricas
        this.elConfidence.textContent = `${(data.confidence_score_ppm / 10000).toFixed(1)}%`;
        this.elULong.textContent = `${(data.net_utility_long_ppm / 10000).toFixed(2)}%`;
        this.elUShort.textContent = `${(data.net_utility_short_ppm / 10000).toFixed(2)}%`;
        
        const z_val = data.kalman_z_score_scaled / 100;
        this.elKalmanZ.textContent = z_val.toFixed(2);
        this.elKalmanBeta.textContent = (data.kalman_beta_scaled / 100).toFixed(2);
        
        const ofi_val = data.ofi_imbalance_scaled / 100;
        this.elOFI.textContent = ofi_val.toFixed(1);
        this.elMicroDelta.textContent = `${data.micro_price_mid_delta_ppm} ppm`;

        // Espectro de Presión Compradora/Vendedora
        const bid_pct = Math.max(10, Math.min(90, 50 + ofi_val * 0.8));
        this.elBarBid.style.width = `${bid_pct}%`;
        this.elBarAsk.style.width = `${100 - bid_pct}%`;

        // Tesorería
        if (data.treasury) {
            this.elRemainingBudget.textContent = `$${data.treasury.remaining_budget_usd.toFixed(2)}`;
            this.elBrierScore.textContent = data.treasury.rolling_brier_score.toFixed(3);
        }

        // Razones
        this.elReasons.innerHTML = "";
        data.reason_codes.forEach(r => {
            const span = document.createElement("span");
            span.className = "reason-tag";
            span.textContent = r;
            this.elReasons.appendChild(span);
        });

        // Botón de Veto
        if (data.dials && this.btnHardVeto) {
            if (data.dials.is_hard_veto_active) {
                this.btnHardVeto.textContent = "[⌘V] VETO ACTIVO";
                this.btnHardVeto.style.backgroundColor = "var(--ruby-500)";
                this.btnHardVeto.style.color = "#ffffff";
            } else {
                this.btnHardVeto.textContent = "[⌘V] HARD VETO";
                this.btnHardVeto.style.backgroundColor = "var(--ruby-600)";
                this.btnHardVeto.style.color = "var(--ruby-400)";
            }
        }

        // Espectro Agudo de Ejecución y Riesgo Simulado
        if (data.simulated_risk_pct !== undefined && this.elSimulatedRiskPct) {
            const risk_val = Number(data.simulated_risk_pct);
            this.elSimulatedRiskPct.textContent = `${risk_val.toFixed(1)}%`;
            if (this.elBarRiskGauge) {
                const clampedWidth = Math.min(100, Math.max(2, risk_val));
                this.elBarRiskGauge.style.width = `${clampedWidth}%`;
                if (risk_val > 50) {
                    this.elBarRiskGauge.style.backgroundColor = "var(--ruby-500)";
                } else if (risk_val > 25) {
                    this.elBarRiskGauge.style.backgroundColor = "var(--amber-500)";
                } else {
                    this.elBarRiskGauge.style.backgroundColor = "var(--emerald-500)";
                }
            }
        }

        if (data.acute_spectrum) {
            if (this.elBadgeRiskTier) {
                this.elBadgeRiskTier.textContent = data.acute_spectrum.spectrum_tier;
                if (data.acute_spectrum.spectrum_tier === "ACUTE_ADVERSE") {
                    this.elBadgeRiskTier.style.color = "var(--ruby-400)";
                } else if (data.acute_spectrum.spectrum_tier === "DEEP_SWEEP") {
                    this.elBadgeRiskTier.style.color = "var(--amber-400)";
                } else {
                    this.elBadgeRiskTier.style.color = "var(--emerald-400)";
                }
            }
            if (this.elAcuteSlip) {
                this.elAcuteSlip.textContent = `${data.acute_spectrum.slippage_pips.toFixed(2)} pips`;
            }
            if (this.elAcuteSharpness) {
                this.elAcuteSharpness.textContent = `${data.acute_spectrum.spectrum_sharpness_score.toFixed(1)} / 100`;
            }
        }

        if (data.risk_metrics) {
            if (this.elSimVar) this.elSimVar.textContent = `${data.risk_metrics.rolling_simulated_var_95_pct.toFixed(2)}%`;
            if (this.elSimCvar) this.elSimCvar.textContent = `${data.risk_metrics.rolling_simulated_cvar_95_pct.toFixed(2)}%`;
            if (this.elSimWinRate) this.elSimWinRate.textContent = `${data.risk_metrics.win_rate_pct.toFixed(1)}%`;
            if (this.elSimTotalTrades) this.elSimTotalTrades.textContent = data.risk_metrics.total_trades_count;
            if (this.elSimRealizedPnl) {
                const rpnl = data.risk_metrics.realized_pnl_usd;
                this.elSimRealizedPnl.textContent = `${rpnl >= 0 ? '+' : ''}$${rpnl.toFixed(2)}`;
                this.elSimRealizedPnl.style.color = rpnl >= 0 ? "var(--emerald-400)" : "var(--ruby-400)";
            }
        }

        // Operativa Simulada Activa
        if (data.active_operation && this.elSimOpStatus) {
            const op = data.active_operation;
            this.elSimOpStatus.textContent = "EN MERCADO";
            this.elSimOpStatus.style.color = op.direction === "LONG" ? "var(--emerald-400)" : "var(--ruby-400)";
            if (this.elSimOpDir) {
                this.elSimOpDir.textContent = `${op.direction} (${op.size.toFixed(1)}u)`;
                this.elSimOpDir.style.color = op.direction === "LONG" ? "var(--emerald-400)" : "var(--ruby-400)";
            }
            if (this.elSimOpEntry) this.elSimOpEntry.textContent = op.entry_price.toFixed(2);
            if (this.elSimOpPnl) {
                this.elSimOpPnl.textContent = `${op.pnl_usd >= 0 ? '+' : ''}$${op.pnl_usd.toFixed(2)}`;
                this.elSimOpPnl.style.color = op.pnl_usd >= 0 ? "var(--emerald-400)" : "var(--ruby-400)";
            }
        } else if (this.elSimOpStatus) {
            this.elSimOpStatus.textContent = "STANDBY";
            this.elSimOpStatus.style.color = "var(--text-muted)";
            if (this.elSimOpDir) {
                this.elSimOpDir.textContent = "NINGUNA";
                this.elSimOpDir.style.color = "var(--text-primary)";
            }
            if (this.elSimOpEntry) this.elSimOpEntry.textContent = "--";
            if (this.elSimOpPnl) {
                this.elSimOpPnl.textContent = "$0.00";
                this.elSimOpPnl.style.color = "var(--text-muted)";
            }
        }

        // Historial
        this.appendHistory(data);
    }

    appendHistory(data) {
        if (!this.tableHistoryBody) return;
        const now = new Date();
        const timeStr = now.toISOString().substring(11, 19);
        const z_val = (data.kalman_z_score_scaled / 100).toFixed(2);
        const conf_str = `${(data.confidence_score_ppm / 10000).toFixed(1)}%`;
        
        const tr = document.createElement("tr");
        tr.innerHTML = `
            <td class="tabular-nums">${timeStr}</td>
            <td>${data.instrument}</td>
            <td style="color: ${data.state === 'GREEN' ? 'var(--emerald-400)' : (data.state === 'RED' ? 'var(--ruby-400)' : 'var(--amber-400)')}; font-weight: 700;">${data.state}</td>
            <td>${data.action}</td>
            <td class="tabular-nums">${z_val}</td>
            <td class="tabular-nums">${conf_str}</td>
        `;
        
        this.tableHistoryBody.insertBefore(tr, this.tableHistoryBody.firstChild);
        if (this.tableHistoryBody.children.length > 8) {
            this.tableHistoryBody.removeChild(this.tableHistoryBody.lastChild);
        }
    }
}

document.addEventListener("DOMContentLoaded", () => {
    window.lucesClient = new TrafficLightClient();
});
