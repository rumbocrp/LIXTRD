(() => {
    "use strict";

    const VISIBLE_INTERVAL_MS = 2000;
    const HIDDEN_INTERVAL_MS = 10000;
    const REQUEST_TIMEOUT_MS = 4000;
    const MAX_RETRY_MS = 30000;
    const safeUiStates = new Set(["vacio", "cargando", "error", "conflicto", "obsoleto"]);
    const lightText = {
        GREEN: { color: "VERDE", direction: "LARGO", css: "#22c55e" },
        YELLOW: { color: "AMARILLO", direction: "MONITORIZAR", css: "#eab308" },
        RED: { color: "ROJO", direction: "CORTO", css: "#ef4444" },
    };

    // FASE 1: Soporte multi-activo - leer instrumento de URL o default US500
    const urlParams = new URLSearchParams(window.location.search);
    const currentInstrument = urlParams.get("instrument") || "US500";
    const statusEndpoint = `/v1/status?instrument=${encodeURIComponent(currentInstrument)}`;

    let timerId = null;
    let requestRunning = false;
    let consecutiveFailures = 0;

    function finite(value) {
        return typeof value === "number" && Number.isFinite(value);
    }

    function numberText(value, digits = 2) {
        if (!finite(value)) {
            return "N/A";
        }
        return new Intl.NumberFormat("en-US", {
            minimumFractionDigits: digits,
            maximumFractionDigits: digits,
        }).format(value);
    }

    function metricText(value, unit = "", digits = 2) {
        const text = numberText(value, digits);
        return text === "N/A" || unit === "" ? text : `${text} ${unit}`;
    }

    function bindText(name, value) {
        document.querySelectorAll(`[data-bind="${name}"]`).forEach((node) => {
            node.textContent = value;
        });
    }

    function marketStateText(value) {
        if (value === "REGULAR") {
            return "MERCADO ABIERTO";
        }
        if (value === "CLOSED") {
            return "MERCADO CERRADO";
        }
        return "ESTADO DE MERCADO DESCONOCIDO";
    }

    function updateConnection(mode, message) {
        const region = document.getElementById("update-status");
        if (!region || region.dataset.mode === mode) {
            return;
        }
        region.dataset.mode = mode;
        region.textContent = message;
    }

    function updateReasons(reasons, uiState) {
        const list = document.querySelector('[data-bind="reason-codes"]');
        if (!list) {
            return;
        }
        const values = Array.isArray(reasons) && reasons.length > 0
            ? reasons.map(String)
            : [uiState === "vacio" ? "NO_DATA_YELLOW (Sin eventos procesados)" : "Sin codigos de razon activos"];
        const fragment = document.createDocumentFragment();
        values.forEach((value) => {
            const item = document.createElement("li");
            item.textContent = value;
            fragment.appendChild(item);
        });
        list.replaceChildren(fragment);
    }

    function updateLight(rawLight, uiState) {
        const requested = Object.hasOwn(lightText, rawLight) ? rawLight : "YELLOW";
        const light = safeUiStates.has(uiState) ? "YELLOW" : requested;
        const detail = lightText[light];

        bindText("light-badge", light);
        bindText("action-label", `${detail.color} . ${detail.direction}`);
        bindText("canonical-direction", detail.direction);

        const action = document.querySelector('[data-bind="action-label"]');
        if (action) {
            action.style.color = detail.css;
        }
        document.querySelectorAll("[data-lamp]").forEach((lamp) => {
            const lampName = lamp.dataset.lamp;
            lamp.classList.toggle("lamp-active", lampName === light);
            lamp.classList.toggle("lamp-inactive", lampName !== light);
        });
    }

    function validDiagnostic(value) {
        if (!value || typeof value !== "object") {
            return false;
        }
        const values = [
            value.probability_long_pct,
            value.probability_short_pct,
            value.threshold_green_pct,
            value.threshold_red_pct,
        ];
        return values.every(finite)
            && values.every((item) => item >= 0 && item <= 100)
            && value.threshold_red_pct <= value.threshold_green_pct;
    }

    function updateDiagnostic(value, uiState) {
        const panel = document.getElementById("diagnostic-panel");
        const empty = document.getElementById("diagnostic-empty");
        const progress = document.getElementById("diagnostic-progress");
        const marker = document.getElementById("diagnostic-marker");
        const safety = document.getElementById("diagnostic-safety");
        if (!panel || !empty || !progress || !marker || !safety) {
            return;
        }
        if (!validDiagnostic(value)) {
            panel.hidden = true;
            empty.hidden = false;
            return;
        }

        const position = Math.max(0, Math.min(100, value.probability_long_pct));
        const green = value.threshold_green_pct;
        const red = value.threshold_red_pct;
        let distance;
        if (position >= green) {
            distance = `VERDE alcanzado por +${numberText(position - green, 1)} pp`;
        } else if (position <= red) {
            distance = `ROJO alcanzado por +${numberText(red - position, 1)} pp`;
        } else {
            distance = `Faltan ${numberText(green - position, 1)} pp para VERDE . ${numberText(position - red, 1)} pp para ROJO`;
        }

        panel.hidden = false;
        empty.hidden = true;
        progress.setAttribute("aria-valuenow", numberText(position, 1));
        progress.setAttribute("aria-valuetext", `${numberText(position, 1)} por ciento largo`);
        marker.style.left = `${position.toFixed(2)}%`;
        bindText("diagnostic-summary", `${numberText(position, 1)}% LARGO . ${numberText(value.probability_short_pct, 1)}% CORTO`);
        bindText("diagnostic-red", `ROJO <= ${numberText(red, 1)}%`);
        bindText("diagnostic-green", `VERDE >= ${numberText(green, 1)}%`);
        bindText("diagnostic-distance", distance);
        bindText(
            "diagnostic-meta",
            `Umbral verde: ${numberText(green, 1)}% . Umbral rojo: ${numberText(red, 1)}% . Fuente de umbrales: ${String(value.threshold_source || "no especificada")} . Evento fuente: ${String(value.source_event_id || "N/A")}`,
        );

        const showSafety = ["obsoleto", "error", "conflicto"].includes(uiState);
        safety.hidden = !showSafety;
        safety.textContent = showSafety
            ? `La barra describe la senal base; la salida operativa permanece AMARILLO por seguridad (${uiState}).`
            : "";
    }

    function updateMarket(data) {
        const market = data.market_data && typeof data.market_data === "object" ? data.market_data : {};
        const provider = String(market.provider || "N/A");
        const symbol = String(market.provider_symbol || "N/A");
        const currency = String(market.currency || "USD");
        const state = marketStateText(market.market_state);
        const price = finite(market.last_price) ? market.last_price : data.mid_price;

        bindText("market-source", `${provider} . ${symbol}`);
        bindText("market-last", metricText(price, currency));
        bindText("market-previous", metricText(market.previous_close, currency));
        bindText("market-open", metricText(market.day_open, currency));
        bindText("market-high-low", `${metricText(market.day_high, currency)} / ${metricText(market.day_low, currency)}`);
        bindText("market-change", `${metricText(market.change, "pts")} . ${metricText(market.change_pct, "%")}`);
        bindText("market-volume", metricText(market.day_volume, "", 0));
        bindText("market-state", state);
        bindText("source-timestamp", String(market.source_timestamp_utc || "N/A"));
        bindText("received-timestamp", String(market.received_at_utc || "N/A"));
        bindText("transport-granularity", `${String(market.transport || "N/A")} / ${String(market.data_granularity || "N/A")}`);
        bindText("fetch-latency", metricText(market.fetch_latency_ms, "ms", 0));
        bindText("source-receive-latency", metricText(market.source_to_receive_ms, "ms", 0));
        bindText("connection-age", metricText(market.connection_age_ms, "ms", 0));
        bindText("quote-status", String(market.quote_status || "N/A"));
        bindText("bid-ask", `${metricText(data.bid)} / ${metricText(data.ask)}`);

        if (Object.keys(market).length > 0) {
            bindText("top-quote-label", `${data.instrument || "US500"} . ${provider}`);
            bindText("top-quote-value", metricText(price, currency));
            bindText("top-quote-detail", `${symbol} . ${state}`);
        } else {
            bindText("top-quote-label", `${data.instrument || "US500"} Cotizacion`);
            bindText("top-quote-value", `${metricText(data.bid, "USD")} / ${metricText(data.ask, "USD")}`);
            bindText("top-quote-detail", `Spread: ${metricText(data.spread, "pts")}`);
        }
    }

    function updateMarketAssets(assets) {
        const values = Array.isArray(assets) ? assets : [];
        const bySymbol = new Map(
            values
                .filter((asset) => asset && typeof asset === "object" && typeof asset.provider_symbol === "string")
                .map((asset) => [asset.provider_symbol, asset]),
        );
        document.querySelectorAll("[data-market-symbol]").forEach((row) => {
            const asset = bySymbol.get(row.dataset.marketSymbol);
            const diagnosticPanel = row.querySelector("[data-asset-diagnostic]");
            const diagnosticEmpty = row.querySelector("[data-asset-diagnostic-empty]");
            const diagnosticMarker = row.querySelector("[data-asset-marker]");
            const diagnosticSummary = row.querySelector("[data-asset-diagnostic-summary]");
            const set = (field, value) => {
                const cell = row.querySelector(`[data-asset-field="${field}"]`);
                if (cell) {
                    cell.textContent = value;
                }
            };
            if (!asset) {
                for (const field of ["last-price", "previous-close", "change", "market-state", "source-time", "data-age", "transport-status"]) {
                    set(field, "N/A");
                }
                if (diagnosticPanel && diagnosticEmpty) {
                    diagnosticPanel.hidden = true;
                    diagnosticEmpty.hidden = false;
                }
                return;
            }
            const currency = String(asset.currency || "USD");
            set("last-price", metricText(asset.last_price, currency));
            set("previous-close", metricText(asset.previous_close, currency));
            set("change", `${metricText(asset.change, "pts")} . ${metricText(asset.change_pct, "%")}`);
            set("market-state", asset.market_state === "REGULAR" ? "ABIERTO" : (asset.market_state === "CLOSED" ? "CERRADO" : "DESCONOCIDO"));
            set("source-time", String(asset.source_timestamp_utc || "N/A"));
            set("data-age", metricText(asset.data_age_ms, "ms", 0));
            set("transport-status", `${String(asset.transport || "N/A")} . ${String(asset.quote_status || "N/A")}`);
            const diagnostic = asset.diagnostico_semaforo;
            if (diagnosticPanel && diagnosticEmpty && diagnosticMarker && diagnosticSummary && validDiagnostic(diagnostic)) {
                const position = Math.max(0, Math.min(100, diagnostic.probability_long_pct));
                diagnosticPanel.hidden = false;
                diagnosticEmpty.hidden = true;
                diagnosticPanel.setAttribute("aria-valuenow", numberText(position, 1));
                diagnosticMarker.style.left = `${position.toFixed(2)}%`;
                diagnosticSummary.textContent = `${numberText(position, 1)}% . R<=${numberText(diagnostic.threshold_red_pct, 1)} . V>=${numberText(diagnostic.threshold_green_pct, 1)}`;
            } else if (diagnosticPanel && diagnosticEmpty) {
                diagnosticPanel.hidden = true;
                diagnosticEmpty.hidden = false;
            }
        });
    }

    function applyStatus(data) {
        const uiState = typeof data.ui_state === "string" ? data.ui_state : "parcial";
        bindText("instrument", String(data.instrument || "US500"));
        bindText("environment", String(data.environment || "NO_DATA"));
        bindText("health", String(data.health_state || "NO_DATA"));
        bindText("ui-state", `ESTADO: ${uiState.toUpperCase()}`);
        bindText("top-age", metricText(data.data_age_ms, "ms", 0));
        bindText("top-sequence", finite(data.secuencia) ? `#${numberText(data.secuencia, 0)}` : "N/A");
        bindText("top-hash", typeof data.hash_snapshot === "string" && data.hash_snapshot.length > 0
            ? `${data.hash_snapshot.slice(0, 8)}...`
            : "N/A");
        bindText("top-micro", metricText(data.micro_price, "USD"));
        bindText("top-mid", metricText(data.mid_price, "USD"));
        bindText("top-ofi", metricText(data.desbalance_ofi));
        bindText("top-beta", metricText(data.beta_kalman));
        bindText("top-z", metricText(data.z_score, "σ"));
        bindText("poll-timestamp", `Corte DOM: ${new Date().toLocaleTimeString("es-PA")}`);
        updateLight(data.light, uiState);
        updateReasons(data.reason_codes, uiState);
        updateDiagnostic(data.diagnostico_semaforo, uiState);
        updateMarket(data);
        updateMarketAssets(data.market_assets);
    }

    function schedule(delayMs) {
        if (timerId !== null) {
            window.clearTimeout(timerId);
        }
        timerId = window.setTimeout(requestStatus, delayMs);
    }

    async function requestStatus() {
        if (requestRunning) {
            return;
        }
        requestRunning = true;
        const controller = new AbortController();
        const timeoutId = window.setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
        try {
            const response = await fetch(statusEndpoint, {
                cache: "no-store",
                headers: { Accept: "application/json" },
                signal: controller.signal,
            });
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            const data = await response.json();
            if (!data || typeof data !== "object") {
                throw new Error("Respuesta de estado invalida");
            }
            consecutiveFailures = 0;
            window.requestAnimationFrame(() => applyStatus(data));
            updateConnection("connected", "Actualizacion incremental conectada.");
        } catch (_error) {
            consecutiveFailures += 1;
            updateConnection("retrying", "Actualizacion interrumpida; se conserva el ultimo dato verificado y se reintentara.");
        } finally {
            window.clearTimeout(timeoutId);
            requestRunning = false;
            const baseDelay = document.hidden ? HIDDEN_INTERVAL_MS : VISIBLE_INTERVAL_MS;
            const retryDelay = consecutiveFailures === 0
                ? baseDelay
                : Math.min(MAX_RETRY_MS, baseDelay * (2 ** Math.min(consecutiveFailures, 4)));
            schedule(retryDelay);
        }
    }

    document.addEventListener("visibilitychange", () => {
        if (!document.hidden) {
            schedule(0);
        }
    });

    schedule(0);
})();
