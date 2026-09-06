"""Renderizado de Vistas e Interfaz de Usuario para el Sistema de Luces (V1 US500).

Implementa:
1. SISTEMA-VISUAL.md §1:
   - Diseño sobrio, plano, de alta densidad técnica (estilo profesional compatible con Trading Journal).
   - Eliminación total de resplandores (glow box-shadow), blur, glassmorphism y gradientes de fantasía.
   - Tipografía tabular monospace (`font-variant-numeric: tabular-nums`) para todas las cifras y métricas.
2. Barra Superior de Monitoreo Cuantitativo (`.quant-topbar`):
   - Cotización US500 (Bid, Ask, Spread).
   - Microestructura (Micro-Price, Mid-Price, OFI Imbalance).
   - Cointegración & Balancines (Kalman Beta β_t, Z-Score).
   - Motor de Riesgo (Drawdown diario, límite por trade, slots concurrentes, P&L paper acumulado).
   - Linaje del corte (data_age_ms, secuencia, hash de snapshot, salud del feed).
3. Panel de Telemetría Multi-Activo (`.multi-asset-table`):
   - 3 Balancines Macro/Momentum/Ancla (GOLD/DXY, US500/TSLA, US500/AAPL) + US500 Compuesto.
4. Panel de Rendimiento y Verificación de Validación:
   - Precisión (Hit Rate), Tasa de Error, Sharpe Ratio, Drawdown Máximo.
5. Los 7 estados canónicos de interfaz (RF-L020, SISTEMA-VISUAL §6):
   - cargando, vacio (NO_DATA), parcial, error, obsoleto, conflicto, exito.
6. Vocabulario canónico en español (RB-L001, RF-L017):
   - VERDE = LARGO
   - AMARILLO = MONITORIZAR
   - ROJO = CORTO
7. Formateo honesto y transparente:
   - Cero métricas ficticias hardcodeadas.
   - N/A explícito con tooltip razonado cuando no hay datos verificados.
"""

from __future__ import annotations

import html
from typing import Any, Dict

from sistema_luces.domain.api import ProyeccionLecturaV1, VistaLectura
from sistema_luces.domain.vocabulary import (
    ESTADOS_UI_PERMITIDOS,
    EstadoUI,
    obtener_color_luz,
    obtener_texto_direccion,
    obtener_texto_luz,
)


def format_metric_value(val: float | int | None, unit: str = "", null_reason: str = "Sin datos") -> str:
    """Formatea valores numéricos con tipografía tabular o emite N/A con tooltip explicativo."""
    if val is None:
        return f'<span class="metric-na" title="{html.escape(null_reason)}">N/A</span>'
    if isinstance(val, int):
        formatted = f"{val:,}"
    elif isinstance(val, float):
        formatted = f"{val:,.2f}"
    else:
        formatted = html.escape(str(val))
    return f"{formatted} {unit}".strip()


def deducir_estado_ui(vista: VistaLectura | ProyeccionLecturaV1, ui_state_override: EstadoUI | None = None) -> EstadoUI:
    """Deduce determinísticamente el estado de interfaz según el estado de salud y datos."""
    if ui_state_override in ESTADOS_UI_PERMITIDOS:
        return ui_state_override

    health = getattr(vista, "health_state", "NO_DATA")
    event_id = getattr(vista, "as_of_event_id", None)
    age_ms = getattr(vista, "data_age_ms", None)
    market_data = getattr(vista, "market_data", {})
    market_closed = isinstance(market_data, dict) and market_data.get("market_state") == "CLOSED"

    if health in {"NO_DATA", "INITIALIZING"} or not event_id:
        return "vacio"
    if (age_ms is not None and age_ms > 5000 and not market_closed) or health in {"STALE", "GAPPED"}:
        return "obsoleto"
    vista_state = getattr(vista, "ui_state", None)
    if isinstance(vista_state, str) and vista_state in ESTADOS_UI_PERMITIDOS:
        return vista_state  # type: ignore[return-value]
    if health == "HEALTHY":
        return "exito"
    if health in {"ERROR", "FAILED"}:
        return "error"
    return "parcial"


def render_dashboard_html(
    vista: VistaLectura | ProyeccionLecturaV1,
    quant_state: Dict[str, Any] | None = None,
    ui_state: EstadoUI | None = None,
) -> str:
    """Genera el dashboard web completo, denso, sobrio y honesto del Sistema de Luces."""
    # Extracción y sanitización de variables
    inst_escaped = html.escape(str(getattr(vista, "instrument", "US500")))
    env_escaped = html.escape(str(getattr(vista, "environment", "NO_DATA")))
    health_raw = str(getattr(vista, "health_state", "NO_DATA"))
    health_escaped = html.escape(health_raw)
    light = getattr(vista, "light", "YELLOW")
    if light not in {"GREEN", "YELLOW", "RED"}:
        light = "YELLOW"
    model_id = getattr(vista, "model_id", None)
    model_id_escaped = html.escape(str(model_id)) if model_id else "N/A"
    policy_ver_escaped = html.escape(str(getattr(vista, "policy_version", "policy-v1")))
    event_id = getattr(vista, "as_of_event_id", None)
    as_of_event_escaped = html.escape(str(event_id)) if event_id else "N/A"
    data_age_ms = getattr(vista, "data_age_ms", None)
    kill_switch_active = bool(getattr(vista, "kill_switch_active", False))

    # Determinar estado de UI canónico
    estado_activo = deducir_estado_ui(vista, ui_state)

    # Vocabulario canónico en español (RB-L001)
    texto_luz = obtener_texto_luz(light)
    color_luz = obtener_color_luz(light)

    # Si estamos en estado vacío / error / conflicto, forzar semáforo en Amarillo / Monitorizar
    if estado_activo in {"vacio", "cargando", "error", "conflicto", "obsoleto"}:
        light = "YELLOW"
        texto_luz = "MONITORIZAR"
        color_luz = "AMARILLO"

    # Extracción de telemetría cuantitativa
    q = quant_state or {}
    has_data = estado_activo not in {"vacio", "cargando"} and bool(event_id)
    market_data = getattr(vista, "market_data", {})
    if not isinstance(market_data, dict):
        market_data = {}
    market_assets_raw = getattr(vista, "market_assets", ())
    market_assets_by_symbol = {
        str(asset.get("provider_symbol")): asset
        for asset in market_assets_raw
        if isinstance(asset, dict) and asset.get("provider_symbol")
    }

    us500_price = market_data.get("last_price")
    if us500_price is None:
        us500_price = q.get("us500_price") if "us500_price" in q else getattr(vista, "mid_price", None)
    bid_val = getattr(vista, "bid", None) if getattr(vista, "bid", None) is not None else q.get("bid")
    ask_val = getattr(vista, "ask", None) if getattr(vista, "ask", None) is not None else q.get("ask")
    spread_val = getattr(vista, "spread", None) if getattr(vista, "spread", None) is not None else (
        round(ask_val - bid_val, 2) if (bid_val is not None and ask_val is not None) else q.get("spread")
    )
    mid_val = getattr(vista, "mid_price", None) if getattr(vista, "mid_price", None) is not None else (
        round((bid_val + ask_val) / 2.0, 2) if (bid_val is not None and ask_val is not None) else q.get("mid_price")
    )
    micro_val = getattr(vista, "micro_price", None) if getattr(vista, "micro_price", None) is not None else q.get("micro_price")
    beta_kalman_val = getattr(vista, "beta_kalman", None) if getattr(vista, "beta_kalman", None) is not None else q.get("beta_kalman")
    z_score_val = getattr(vista, "z_score", None) if getattr(vista, "z_score", None) is not None else q.get("z_score")
    ofi_val = getattr(vista, "desbalance_ofi", None) if getattr(vista, "desbalance_ofi", None) is not None else q.get("desbalance_ofi")

    # Métricas de validación del modelo
    hit_rate = q.get("hit_rate_pct")
    error_rate = q.get("error_rate_pct")
    sharpe = q.get("sharpe_ratio")
    max_dd = q.get("max_drawdown_pct")

    # Riesgo
    drawdown_val = getattr(vista, "drawdown_diario_pct", None) if getattr(vista, "drawdown_diario_pct", None) is not None else q.get("drawdown_diario_pct")
    limite_trade_val = getattr(vista, "limite_por_trade_pct", None) if getattr(vista, "limite_por_trade_pct", None) is not None else q.get("limite_por_trade_pct")
    slots_usados = getattr(vista, "slots_concurrentes_usados", None) if getattr(vista, "slots_concurrentes_usados", None) is not None else q.get("slots_concurrentes_usados")
    slots_max = getattr(vista, "slots_concurrentes_max", None) if getattr(vista, "slots_concurrentes_max", None) is not None else q.get("slots_concurrentes_max", 1)
    pnl_paper = getattr(vista, "pnl_paper_acumulado", None) if getattr(vista, "pnl_paper_acumulado", None) is not None else q.get("pnl_paper_acumulado")

    # Linaje
    secuencia_val = getattr(vista, "secuencia", None) if getattr(vista, "secuencia", None) is not None else q.get("secuencia")
    snapshot_hash = getattr(vista, "hash_snapshot", None) if getattr(vista, "hash_snapshot", None) is not None else q.get("hash_snapshot")

    # Balancines list: solo si se proporcionan datos en la proyección o quant_state
    balancines_raw = getattr(vista, "balancines", ()) or q.get("balancines", ())
    balancines_items: list[dict[str, Any]] = []
    if has_data and balancines_raw:
        for b in balancines_raw:
            if hasattr(b, "to_dict") and callable(b.to_dict):
                balancines_items.append(b.to_dict())
            elif isinstance(b, dict):
                balancines_items.append(b)

    # Si no hay datos (vacio o sin evento), limpiar campos
    if not has_data:
        us500_price = None
        bid_val = None
        ask_val = None
        spread_val = None
        mid_val = None
        micro_val = None
        beta_kalman_val = None
        z_score_val = None
        ofi_val = None
        hit_rate = None
        error_rate = None
        sharpe = None
        max_dd = None
        drawdown_val = None
        limite_trade_val = None
        slots_usados = None
        pnl_paper = None
        secuencia_val = None
        snapshot_hash = None
        balancines_items = []

    # Banners segun el estado canonico de UI
    banners_html = ""
    if getattr(vista, "environment", "") == "SINTETICO":
        banners_html += """
        <div class="banner banner-synthetic">
            <strong>LABORATORIO SINTETICO</strong> - Datos generados para pruebas y benchmarking. No apto para operativa real ni demo observada.
        </div>
        """

    if market_data:
        provider_banner = html.escape(str(market_data.get("provider") or "Fuente publica"))
        symbol_banner = html.escape(str(market_data.get("provider_symbol") or "^GSPC"))
        quote_status_banner = html.escape(str(market_data.get("quote_status") or "N/A"))
        market_state_banner = str(market_data.get("market_state") or "UNKNOWN")
        if market_state_banner == "CLOSED":
            market_copy = "MERCADO CERRADO - el ultimo valor valido permanece visible y no se simula movimiento."
        else:
            market_copy = "MERCADO ABIERTO - el stream actualiza cuando Yahoo publica un nuevo mensaje."
        banners_html += f"""
        <div class="banner banner-warning">
            <strong>{provider_banner} . {symbol_banner}</strong> - {market_copy}
            Estado de cotizacion del proveedor: <strong>{quote_status_banner}</strong>.
            Esta observacion publica no sustituye bid/ask de broker ni certifica la luz.
        </div>
        """

    if estado_activo == "cargando":
        banners_html += f"""
        <div class="banner banner-info">
            <strong>Cargando telemetria</strong> - Esperando inicializacion del entorno {env_escaped}. Ningun dato anterior es presentado como actual.
        </div>
        """
    elif estado_activo == "vacio":
        banners_html += f"""
        <div class="banner banner-info">
            <strong>Todavia no hay evidencia</strong> - El entorno {env_escaped} no ha registrado eventos. El sistema permanece en estado seguro <strong>AMARILLO (MONITORIZAR)</strong>.
        </div>
        """
    elif estado_activo == "obsoleto":
        banners_html += """
        <div class="banner banner-warning">
            <strong>Datos obsoletos</strong> - La telemetria ha superado el umbral de latencia (&gt;5000 ms) o el feed esta degradado. Luz forzada a <strong>AMARILLO (MONITORIZAR)</strong>.
        </div>
        """
    elif estado_activo == "error":
        banners_html += """
        <div class="banner banner-danger">
            <strong>Condicion de error</strong> - Se detecto una anomalia en el procesamiento. Modo de seguridad activado: <strong>MONITORIZAR</strong>.
        </div>
        """
    elif estado_activo == "conflicto":
        banners_html += """
        <div class="banner banner-danger">
            <strong>Conflicto de versiones / Esquema</strong> - Incompatibilidad detectada en el contrato de datos. Vista congelada en estado seguro.
        </div>
        """
    elif estado_activo == "parcial":
        banners_html += """
        <div class="banner banner-info">
            <strong>Telemetria parcial</strong> - Se presentan unicamente los datos verificados disponibles. Las metricas no maduras se muestran como N/A.
        </div>
        """
    elif estado_activo == "exito":
        banners_html += f"""
        <div class="banner banner-success">
            <strong>Telemetria integra y verificada</strong> - Secuencia sincronizada hasta el evento {as_of_event_escaped}.
        </div>
        """

    # Estado de las 3 lámparas del semáforo plano (SISTEMA-VISUAL §1: sin glow, plano)
    is_green = light == "GREEN"
    is_yellow = light == "YELLOW"
    is_red = light == "RED"

    green_class = "lamp-green lamp-active" if is_green else "lamp-green lamp-inactive"
    yellow_class = "lamp-yellow lamp-active" if is_yellow else "lamp-yellow lamp-inactive"
    red_class = "lamp-red lamp-active" if is_red else "lamp-red lamp-inactive"

    action_badge_color = "#22c55e" if is_green else ("#ef4444" if is_red else "#eab308")

    # Formateo de códigos de razón
    reasons = getattr(vista, "reason_codes", ())
    if reasons:
        reason_list = "".join(f"<li>{html.escape(str(r))}</li>" for r in reasons)
    elif estado_activo == "vacio":
        reason_list = "<li>NO_DATA_YELLOW (Sin eventos procesados)</li>"
    else:
        reason_list = "<li>Sin códigos de razón activos</li>"

    # Formateo de valores de barra superior cuantitativa
    top_bid = format_metric_value(bid_val, "USD", "Sin cotización disponible")
    top_ask = format_metric_value(ask_val, "USD", "Sin cotización disponible")
    top_spread = format_metric_value(spread_val, "pts", "N/A")
    top_mid = format_metric_value(mid_val, "USD", "Sin cotización disponible")
    top_micro = format_metric_value(micro_val, "USD", "Sin cálculo de microestructura")
    top_beta = format_metric_value(beta_kalman_val, "", "Requiere modelo Kalman")
    top_z = format_metric_value(z_score_val, "σ", "Requiere modelo Kalman")
    top_ofi = format_metric_value(ofi_val, "", "Sin flujo de órdenes")
    top_drawdown = format_metric_value(drawdown_val, "%", "Sin historial de riesgo")
    top_slots = f"{slots_usados} / {slots_max}" if slots_usados is not None and slots_max is not None else '<span class="metric-na" title="Sin perfil de concurrencia verificado">N/A</span>'
    top_pnl = (f"+${pnl_paper:,.2f} USD" if (pnl_paper is not None and pnl_paper >= 0) else (f"-${abs(pnl_paper):,.2f} USD" if pnl_paper is not None else '<span class="metric-na" title="Sin P&L validado">N/A</span>'))
    top_age = f"{data_age_ms} ms" if data_age_ms is not None else '<span class="metric-na" title="Sin corte temporal">N/A</span>'
    top_sec = f"#{secuencia_val}" if secuencia_val is not None else '<span class="metric-na" title="Sin secuencia">N/A</span>'
    top_hash = f"{snapshot_hash[:8]}..." if snapshot_hash else '<span class="metric-na" title="Sin snapshot">N/A</span>'

    market_provider = html.escape(str(market_data.get("provider") or "N/A"))
    market_symbol = html.escape(str(market_data.get("provider_symbol") or "N/A"))
    market_state_raw = str(market_data.get("market_state") or "UNKNOWN")
    market_state_text = "MERCADO CERRADO" if market_state_raw == "CLOSED" else (
        "MERCADO ABIERTO" if market_state_raw == "REGULAR" else "ESTADO DE MERCADO DESCONOCIDO"
    )
    market_state_escaped = html.escape(market_state_text)
    quote_status_escaped = html.escape(str(market_data.get("quote_status") or "N/A"))
    transport_escaped = html.escape(str(market_data.get("transport") or "N/A"))
    granularity_escaped = html.escape(str(market_data.get("data_granularity") or "N/A"))
    source_timestamp_escaped = html.escape(str(market_data.get("source_timestamp_utc") or "N/A"))
    received_timestamp_escaped = html.escape(str(market_data.get("received_at_utc") or "N/A"))
    fetch_latency = market_data.get("fetch_latency_ms")
    fetch_latency_text = f"{fetch_latency} ms" if isinstance(fetch_latency, (int, float)) else "N/A"
    source_to_receive = market_data.get("source_to_receive_ms")
    source_to_receive_text = f"{source_to_receive} ms" if isinstance(source_to_receive, (int, float)) else "N/A"
    connection_age = market_data.get("connection_age_ms")
    connection_age_text = f"{connection_age} ms" if isinstance(connection_age, (int, float)) else "N/A"
    if market_data:
        top_quote_label = f"S&amp;P 500 · {market_provider}"
        top_quote_value = format_metric_value(us500_price, str(market_data.get("currency") or "USD"), "Precio no disponible")
        top_quote_detail = f"{market_symbol} · {market_state_escaped}"
    else:
        top_quote_label = "US500 Cotización"
        top_quote_value = f"{top_bid} / {top_ask}"
        top_quote_detail = f"Spread: {top_spread}"

    asset_definitions = (
        ("^GSPC", "S&P 500", "Índice"),
        ("TSLA", "Tesla", "Acción"),
        ("AAPL", "Apple", "Acción"),
        ("GC=F", "Oro", "Futuro continuo · no spot"),
    )
    market_asset_rows_html = ""
    for symbol, fallback_name, fallback_kind in asset_definitions:
        asset = market_assets_by_symbol.get(symbol, {})
        display_name = html.escape(str(asset.get("display_name") or fallback_name))
        kind = html.escape(str(asset.get("instrument_type") or fallback_kind))
        currency = str(asset.get("currency") or "USD")
        last_price = format_metric_value(asset.get("last_price"), currency, "Sin cotización recibida")
        previous_close = format_metric_value(asset.get("previous_close"), currency, "Sin cierre anterior")
        change = format_metric_value(asset.get("change"), "pts", "Sin variación recibida")
        change_pct = format_metric_value(asset.get("change_pct"), "%", "Sin variación porcentual")
        state = str(asset.get("market_state") or "UNKNOWN")
        state_text = "ABIERTO" if state == "REGULAR" else ("CERRADO" if state == "CLOSED" else "DESCONOCIDO")
        source_timestamp = html.escape(str(asset.get("source_timestamp_utc") or "N/A"))
        age = asset.get("data_age_ms")
        age_text = f"{int(age)} ms" if isinstance(age, (int, float)) else "N/A"
        transport = html.escape(str(asset.get("transport") or "N/A"))
        quote_status = html.escape(str(asset.get("quote_status") or "N/A"))
        asset_diagnostic = asset.get("diagnostico_semaforo")
        diagnostic_hidden = " hidden"
        diagnostic_empty_hidden = ""
        diagnostic_position = 0.0
        diagnostic_summary = "N/A"
        if isinstance(asset_diagnostic, dict):
            candidate = asset_diagnostic.get("probability_long_pct")
            green = asset_diagnostic.get("threshold_green_pct")
            red = asset_diagnostic.get("threshold_red_pct")
            if all(isinstance(value, (int, float)) for value in (candidate, green, red)):
                diagnostic_position = max(0.0, min(100.0, float(candidate)))
                diagnostic_hidden = ""
                diagnostic_empty_hidden = " hidden"
                diagnostic_summary = f"{diagnostic_position:.1f}% · R≤{float(red):.1f} · V≥{float(green):.1f}"
        market_asset_rows_html += f"""
            <tr data-market-symbol="{html.escape(symbol, quote=True)}">
                <td><strong>{display_name}</strong><br><span class="text-dim font-tabular">{html.escape(symbol)} · {kind}</span></td>
                <td class="font-tabular" data-asset-field="last-price">{last_price}</td>
                <td class="font-tabular" data-asset-field="previous-close">{previous_close}</td>
                <td class="font-tabular" data-asset-field="change">{change} · {change_pct}</td>
                <td class="font-tabular" data-asset-field="market-state">{state_text}</td>
                <td class="font-tabular" data-asset-field="source-time">{source_timestamp}</td>
                <td class="font-tabular" data-asset-field="data-age">{age_text}</td>
                <td class="font-tabular" data-asset-field="transport-status">{transport}<br><span class="text-dim">{quote_status}</span></td>
                <td>
                    <div class="asset-diagnostic" data-asset-diagnostic role="progressbar"
                        aria-label="Diagnóstico individual de {display_name}" aria-valuemin="0" aria-valuemax="100"
                         aria-valuenow="{diagnostic_position:.1f}"{diagnostic_hidden}>
                        <div class="asset-signal-track" aria-hidden="true">
                            <i class="asset-zone-red"></i><i class="asset-zone-yellow"></i><i class="asset-zone-green"></i>
                            <span data-asset-marker style="left: {diagnostic_position:.2f}%"></span>
                        </div>
                        <strong class="font-tabular" data-asset-diagnostic-summary>{diagnostic_summary}</strong>
                    </div>
                    <span class="metric-na" data-asset-diagnostic-empty{diagnostic_empty_hidden}>N/A · sin fórmula verificada</span>
                </td>
            </tr>
        """

    # Diagnóstico de transición: estructura estable para actualización parcial del DOM.
    diagnostico = getattr(vista, "diagnostico_semaforo", None)
    diagnostic_panel_hidden = " hidden"
    diagnostic_empty_hidden = ""
    diagnostic_position = 0.0
    diagnostic_summary = "N/A"
    diagnostic_red_label = "ROJO ≤ N/A"
    diagnostic_green_label = "VERDE ≥ N/A"
    diagnostic_distance = "N/A — sin señal verificable"
    diagnostic_meta = "Umbrales: N/A · Evento fuente: N/A"
    diagnostic_safety = ""
    diagnostic_safety_hidden = " hidden"
    if has_data and isinstance(diagnostico, dict):
        prob_long = diagnostico.get("probability_long_pct")
        prob_short = diagnostico.get("probability_short_pct")
        threshold_green = diagnostico.get("threshold_green_pct")
        threshold_red = diagnostico.get("threshold_red_pct")
        if all(isinstance(v, (int, float)) for v in (prob_long, prob_short, threshold_green, threshold_red)):
            diagnostic_position = max(0.0, min(100.0, float(prob_long)))
            green_threshold = float(threshold_green)
            red_threshold = float(threshold_red)
            if diagnostic_position >= green_threshold:
                distance_text = f"VERDE alcanzado por +{diagnostic_position - green_threshold:.1f} pp"
            elif diagnostic_position <= red_threshold:
                distance_text = f"ROJO alcanzado por +{red_threshold - diagnostic_position:.1f} pp"
            else:
                distance_text = (
                    f"Faltan {green_threshold - diagnostic_position:.1f} pp para VERDE · "
                    f"{diagnostic_position - red_threshold:.1f} pp para ROJO"
                )
            threshold_source = html.escape(str(diagnostico.get("threshold_source", "no especificada")))
            source_event = html.escape(str(diagnostico.get("source_event_id", "N/A")))
            diagnostic_panel_hidden = ""
            diagnostic_empty_hidden = " hidden"
            diagnostic_summary = f"{diagnostic_position:.1f}% LARGO · {float(prob_short):.1f}% CORTO"
            diagnostic_red_label = f"ROJO ≤ {red_threshold:.1f}%"
            diagnostic_green_label = f"VERDE ≥ {green_threshold:.1f}%"
            diagnostic_distance = distance_text
            diagnostic_meta = (
                f"Umbral verde: {green_threshold:.1f}% · Umbral rojo: {red_threshold:.1f}% · "
                f"Fuente de umbrales: {threshold_source} · Evento fuente: {source_event}"
            )
            if estado_activo in {"obsoleto", "error", "conflicto"}:
                diagnostic_safety = (
                    "La barra describe la señal base; la salida operativa permanece "
                    f"AMARILLO por seguridad ({html.escape(estado_activo)})."
                )
                diagnostic_safety_hidden = ""

    diagnostic_html = f"""
        <section id="diagnostic-panel" class="diagnostic-panel" aria-labelledby="diagnostic-title"{diagnostic_panel_hidden}>
            <div class="diagnostic-heading">
                <h3 id="diagnostic-title">Diagnóstico de transición</h3>
                <strong class="font-tabular" data-bind="diagnostic-summary">{diagnostic_summary}</strong>
            </div>
            <div id="diagnostic-progress" class="signal-scale" role="progressbar"
                 aria-label="Probabilidad larga actual y umbrales del semáforo"
                 aria-valuemin="0" aria-valuemax="100" aria-valuenow="{diagnostic_position:.1f}">
                <div class="signal-zones" aria-hidden="true">
                    <span class="zone-red"></span><span class="zone-yellow"></span><span class="zone-green"></span>
                </div>
                <span id="diagnostic-marker" class="signal-marker" style="left: {diagnostic_position:.2f}%" aria-hidden="true"></span>
            </div>
            <div class="signal-labels font-tabular">
                <span data-bind="diagnostic-red">{diagnostic_red_label}</span>
                <span>AMARILLO</span>
                <span data-bind="diagnostic-green">{diagnostic_green_label}</span>
            </div>
            <p class="diagnostic-result font-tabular" data-bind="diagnostic-distance">{diagnostic_distance}</p>
            <p class="diagnostic-meta font-tabular" data-bind="diagnostic-meta">{diagnostic_meta}</p>
            <p id="diagnostic-safety" class="diagnostic-safety"{diagnostic_safety_hidden}>{diagnostic_safety}</p>
        </section>
        <div id="diagnostic-empty" class="diagnostic-empty"{diagnostic_empty_hidden}>
            <strong>Diagnóstico de transición:</strong> N/A — todavía no existe un evento SIGNAL_EMITTED con probabilidades verificables.
        </div>
    """

    # Formateo de métricas en tarjetas inferiores
    price_display = format_metric_value(us500_price, "USD", "Precio no disponible")
    bid_display = format_metric_value(bid_val, "", "N/A")
    ask_display = format_metric_value(ask_val, "", "N/A")
    previous_close_display = format_metric_value(market_data.get("previous_close"), "USD", "No entregado por Yahoo")
    day_open_display = format_metric_value(market_data.get("day_open"), "USD", "No entregado por Yahoo")
    day_high_display = format_metric_value(market_data.get("day_high"), "USD", "No entregado por Yahoo")
    day_low_display = format_metric_value(market_data.get("day_low"), "USD", "No entregado por Yahoo")
    change_display = format_metric_value(market_data.get("change"), "pts", "No entregado por Yahoo")
    change_pct_display = format_metric_value(market_data.get("change_pct"), "%", "No entregado por Yahoo")
    volume_display = format_metric_value(market_data.get("day_volume"), "", "No entregado por Yahoo")
    hit_rate_display = format_metric_value(hit_rate, "%", "Sin cálculo validado")
    error_rate_display = format_metric_value(error_rate, "%", "Sin cálculo validado")
    sharpe_display = format_metric_value(sharpe, "", "Requiere historial verificado")
    max_dd_display = format_metric_value(max_dd, "%", "Requiere historial verificado")

    # Construcción de filas del panel de balancines multi-activo
    balancines_rows_html = ""
    if balancines_items:
        for b in balancines_items:
            b_name = html.escape(str(b.get("name", "")))
            b_cat = html.escape(str(b.get("category", "")))
            py_str = format_metric_value(b.get("price_y"), "", "N/A")
            px_str = format_metric_value(b.get("price_x"), "", "N/A")
            b_beta = format_metric_value(b.get("beta_kalman"), "", "N/A")
            b_z = format_metric_value(b.get("z_score"), "σ", "N/A")
            b_ofi = format_metric_value(b.get("ofi"), "", "N/A")
            b_micro = format_metric_value(b.get("micro_price"), "", "N/A")
            b_mid = format_metric_value(b.get("mid_price"), "", "N/A")
            b_dir = html.escape(str(b.get("direction", "MONITORIZAR")))
            b_light = str(b.get("light", "YELLOW"))
            badge_cls = "badge-green" if b_light == "GREEN" else ("badge-red" if b_light == "RED" else "badge-yellow")
            b_score = b.get("composite_score")
            b_green = b.get("threshold_green")
            b_red = b.get("threshold_red")
            b_confidence = b.get("confidence_pct")
            b_source = html.escape(str(b.get("source_name") or "N/A"))
            b_age = b.get("data_age_ms")
            b_age_text = f"{b_age} ms" if isinstance(b_age, (int, float)) else "N/A"
            relation_diagnostic = '<span class="metric-na" title="Score o umbral ausente">N/A</span>'
            if isinstance(b_score, (int, float)) and isinstance(b_green, (int, float)) and isinstance(b_red, (int, float)):
                score = float(b_score)
                if score >= 0:
                    target = abs(float(b_green))
                    progress = min(100.0, (score / target) * 100.0) if target > 0 else 0.0
                    toward = "verde"
                else:
                    target = abs(float(b_red))
                    progress = min(100.0, (abs(score) / target) * 100.0) if target > 0 else 0.0
                    toward = "rojo"
                relation_diagnostic = f"""
                    <div class="relation-diagnostic font-tabular">
                        <div class="relation-progress" role="progressbar" aria-label="{b_name}: avance hacia {toward}"
                             aria-valuemin="0" aria-valuemax="100" aria-valuenow="{progress:.1f}">
                            <span style="width: {progress:.2f}%"></span>
                        </div>
                        <strong>{progress:.1f}% hacia {toward}</strong>
                        <small>Score {score:+.3f} · objetivo {target:.3f}</small>
                        <small>Confianza: {f'{float(b_confidence):.1f}%' if isinstance(b_confidence, (int, float)) else 'N/A'}</small>
                    </div>
                """

            balancines_rows_html += f"""
            <tr>
                <td class="font-tabular"><strong>{b_name}</strong><br><span class="text-dim">{b_cat}</span></td>
                <td class="font-tabular">{py_str} / {px_str}</td>
                <td class="font-tabular">{b_beta}</td>
                <td class="font-tabular">{b_z}</td>
                <td class="font-tabular">{b_ofi}</td>
                <td class="font-tabular">{b_micro} / {b_mid}</td>
                <td>{relation_diagnostic}</td>
                <td class="font-tabular">{b_source}<br><span class="text-dim">Edad: {b_age_text}</span></td>
                <td><span class="badge {badge_cls} font-tabular">{b_dir}</span></td>
            </tr>
            """
    else:
        balancines_rows_html = """
        <tr>
            <td colspan="9" style="text-align: center; color: var(--text-muted); padding: 1.25rem;" class="font-tabular">
                <em>Todavía no hay una captura multi-activo con procedencia verificable.</em>
            </td>
        </tr>
        """

    doc_count = len(getattr(vista, "documents", ()))

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Sistema de Luces — Índice de Mercado {inst_escaped}</title>
    <script defer src="/assets/dashboard-v1.js"></script>
    <style>
        :root {{
            --bg-base: #0f172a;
            --bg-card: #1e293b;
            --bg-card-alt: #0f172a;
            --border-card: #334155;
            --border-highlight: #475569;
            --text-main: #f8fafc;
            --text-muted: #94a3b8;
            --text-dim: #64748b;
            --green: #22c55e;
            --yellow: #eab308;
            --red: #ef4444;
            --blue: #3b82f6;
        }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
            background: var(--bg-base);
            color: var(--text-main);
            min-height: 100vh;
            padding: 1.25rem;
            line-height: 1.5;
        }}

        /* Tipografía tabular monospace para cifras cuantitativas */
        .font-tabular {{
            font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
            font-variant-numeric: tabular-nums;
        }}

        header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding-bottom: 0.85rem;
            border-bottom: 1px solid var(--border-card);
            margin-bottom: 1rem;
            flex-wrap: wrap;
            gap: 0.75rem;
        }}
        .brand {{
            display: flex;
            align-items: center;
            gap: 0.75rem;
        }}
        .brand h1 {{
            font-size: 1.3rem;
            font-weight: 700;
            color: var(--text-main);
            letter-spacing: -0.01em;
        }}
        .brand-sub {{
            font-size: 0.78rem;
            color: var(--text-muted);
        }}
        .badges-group {{
            display: flex;
            gap: 0.4rem;
            align-items: center;
            flex-wrap: wrap;
        }}
        .badge {{
            display: inline-flex;
            align-items: center;
            gap: 0.3rem;
            padding: 0.25rem 0.55rem;
            border-radius: 3px;
            font-size: 0.72rem;
            font-weight: 600;
            text-transform: uppercase;
            border: 1px solid transparent;
        }}
        .badge-env {{ background: #1e293b; color: #94a3b8; border-color: var(--border-card); }}
        .badge-health {{ background: #1e293b; color: #60a5fa; border-color: #3b82f6; }}
        .badge-state {{ background: #334155; color: #f8fafc; border-color: var(--border-highlight); }}
        .badge-loopback {{ background: #1e293b; color: #4ade80; border-color: #22c55e; }}
        .badge-green {{ background: #166534; color: #f0fdf4; border-color: #22c55e; }}
        .badge-yellow {{ background: #854d0e; color: #fefce8; border-color: #eab308; }}
        .badge-red {{ background: #991b1b; color: #fef2f2; border-color: #ef4444; }}

        /* Topbar de Monitoreo Cuantitativo Denso */
        .quant-topbar {{
            background: var(--bg-card);
            border: 1px solid var(--border-card);
            border-radius: 4px;
            padding: 0.6rem 0.85rem;
            margin-bottom: 1rem;
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
            gap: 0.75rem;
            align-items: center;
        }}
        .quant-strip-item {{
            border-right: 1px solid var(--border-card);
            padding-right: 0.6rem;
        }}
        .quant-strip-item:last-child {{
            border-right: none;
            padding-right: 0;
        }}
        .strip-lbl {{
            font-size: 0.68rem;
            text-transform: uppercase;
            font-weight: 700;
            color: var(--text-dim);
            margin-bottom: 0.15rem;
        }}
        .strip-val {{
            font-size: 0.95rem;
            font-weight: 700;
            color: var(--text-main);
        }}

        /* Banners de Estado */
        .banner {{
            padding: 0.75rem 1rem;
            border-radius: 4px;
            margin-bottom: 1rem;
            font-size: 0.84rem;
            line-height: 1.4;
            border: 1px solid transparent;
        }}
        .banner-info {{ background: #1e293b; border-color: #3b82f6; color: #93c5fd; }}
        .banner-success {{ background: #1e293b; border-color: #22c55e; color: #86efac; }}
        .banner-warning {{ background: #1e293b; border-color: #eab308; color: #fde047; }}
        .banner-danger {{ background: #1e293b; border-color: #ef4444; color: #fca5a5; }}
        .banner-synthetic {{ background: #1e293b; border-color: #a855f7; color: #d8b4fe; }}

        /* Layout Grid */
        .main-grid {{
            display: grid;
            grid-template-columns: 280px 1fr;
            gap: 1rem;
            margin-bottom: 1.25rem;
        }}
        @media (max-width: 960px) {{
            .main-grid {{ grid-template-columns: 1fr; }}
        }}

        /* Tarjetas */
        .card {{
            background: var(--bg-card);
            border: 1px solid var(--border-card);
            border-radius: 4px;
            padding: 1rem;
        }}
        .card-title {{
            font-size: 0.88rem;
            font-weight: 700;
            color: var(--text-main);
            margin-bottom: 0.75rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid var(--border-card);
            padding-bottom: 0.4rem;
        }}

        /* Semáforo Plano Sobrio (Sin Glow ni Gradientes) */
        .traffic-housing {{
            background: #090d16;
            border: 1px solid var(--border-card);
            border-radius: 6px;
            padding: 0.85rem;
            display: flex;
            justify-content: center;
            gap: 0.75rem;
            margin: 0.85rem auto;
            width: fit-content;
        }}
        .lamp {{
            width: 54px;
            height: 54px;
            border-radius: 4px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 0.7rem;
            font-weight: 700;
            border: 1px solid var(--border-card);
        }}
        .lamp-red {{ background: #450a0a; color: #fca5a5; }}
        .lamp-yellow {{ background: #422006; color: #fef08a; }}
        .lamp-green {{ background: #052e16; color: #86efac; }}
        .lamp-active.lamp-red {{ background: #991b1b; color: #fef2f2; border-color: #ef4444; }}
        .lamp-active.lamp-yellow {{ background: #854d0e; color: #fefce8; border-color: #eab308; }}
        .lamp-active.lamp-green {{ background: #166534; color: #f0fdf4; border-color: #22c55e; }}
        .lamp-inactive {{ opacity: 0.3; }}

        .action-label {{
            font-size: 1.1rem;
            font-weight: 700;
            text-align: center;
            color: {action_badge_color};
            margin-top: 0.4rem;
        }}

        /* Barra diagnóstica divergente: número, umbrales y texto; el color nunca es la única señal. */
        .diagnostic-panel, .diagnostic-empty {{
            margin-top: 1rem;
            padding: 0.8rem;
            border: 1px solid var(--border-highlight);
            border-radius: 4px;
            background: var(--bg-card-alt);
            font-size: 0.76rem;
        }}
        [hidden] {{ display: none !important; }}
        .diagnostic-heading {{ display: flex; justify-content: space-between; gap: 0.75rem; align-items: baseline; }}
        .diagnostic-heading h3 {{ font-size: 0.82rem; }}
        .signal-scale {{ position: relative; margin-top: 0.65rem; height: 18px; }}
        .signal-zones {{ display: grid; grid-template-columns: 35fr 30fr 35fr; height: 100%; border: 1px solid #64748b; }}
        .zone-red {{ background: #7f1d1d; }}
        .zone-yellow {{ background: #713f12; }}
        .zone-green {{ background: #14532d; }}
        .signal-marker {{
            position: absolute; top: -5px; width: 3px; height: 28px; background: #f8fafc;
            border: 1px solid #020617; transform: translateX(-50%);
        }}
        .signal-labels {{ display: flex; justify-content: space-between; margin-top: 0.3rem; font-size: 0.65rem; color: var(--text-muted); }}
        .diagnostic-result {{ margin-top: 0.55rem; color: var(--text-main); font-weight: 700; }}
        .diagnostic-meta {{ margin-top: 0.2rem; color: var(--text-muted); }}
        .diagnostic-safety {{ margin-top: 0.55rem; padding-top: 0.45rem; border-top: 1px solid var(--border-card); color: #fde047; }}
        .relation-diagnostic {{ min-width: 150px; display: grid; gap: 0.15rem; }}
        .relation-progress {{ height: 7px; background: #334155; border: 1px solid #475569; }}
        .relation-progress span {{ display: block; height: 100%; background: #60a5fa; }}
        .relation-diagnostic small {{ color: var(--text-muted); }}
        .asset-diagnostic {{ min-width: 150px; display: grid; gap: 0.25rem; }}
        .asset-signal-track {{ position: relative; height: 8px; border: 1px solid var(--border-highlight); display: grid; grid-template-columns: 35fr 30fr 35fr; }}
        .asset-signal-track i {{ display: block; }}
        .asset-zone-red {{ background: #7f1d1d; }}
        .asset-zone-yellow {{ background: #713f12; }}
        .asset-zone-green {{ background: #14532d; }}
        .asset-signal-track span {{ position: absolute; top: -3px; width: 2px; height: 14px; background: var(--text-main); transform: translateX(-50%); }}

        /* Métricas */
        .metrics-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
            gap: 0.75rem;
            margin-top: 0.5rem;
        }}
        .metric-box {{
            background: var(--bg-card-alt);
            border: 1px solid var(--border-card);
            border-radius: 4px;
            padding: 0.65rem;
            text-align: center;
        }}
        .metric-title {{ font-size: 0.68rem; color: var(--text-muted); text-transform: uppercase; font-weight: 600; }}
        .metric-value {{ font-size: 1.1rem; font-weight: 700; margin-top: 0.25rem; }}

        /* Tablas Densas */
        .table-responsive {{
            overflow-x: auto;
            margin-top: 0.5rem;
        }}
        table.dense-table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 0.8rem;
            text-align: left;
        }}
        table.dense-table th {{
            background: #0f172a;
            color: var(--text-muted);
            font-size: 0.7rem;
            text-transform: uppercase;
            padding: 0.45rem 0.6rem;
            border-bottom: 1px solid var(--border-card);
            font-weight: 700;
        }}
        table.dense-table td {{
            padding: 0.5rem 0.6rem;
            border-bottom: 1px solid #1e293b;
            color: var(--text-main);
        }}
        table.dense-table tr:hover {{
            background: rgba(255, 255, 255, 0.02);
        }}

        .metric-na {{ color: var(--text-dim); font-style: italic; }}
        .text-dim {{ color: var(--text-dim); font-size: 0.72rem; }}

        /* Meta y Linaje */
        .meta-list {{
            list-style: none;
            font-size: 0.78rem;
            line-height: 1.6;
        }}
        .meta-list li {{
            display: flex;
            justify-content: space-between;
            border-bottom: 1px solid #1e293b;
            padding: 0.25rem 0;
        }}
        .meta-label {{ color: var(--text-muted); }}
        .meta-val {{ font-weight: 600; color: #e2e8f0; }}

        footer {{
            border-top: 1px solid var(--border-card);
            padding-top: 0.85rem;
            font-size: 0.72rem;
            color: var(--text-dim);
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 0.5rem;
        }}
    </style>
</head>
<body>

    <div id="dashboard-current-region">

    <header>
        <div class="brand">
            <span style="font-size: 1.4rem;">🚦</span>
            <div>
                <h1>Sistema de Luces — <span data-bind="instrument">{inst_escaped}</span></h1>
                <div class="brand-sub">Índice de Mercado y Observabilidad de Cuentas Demo</div>
            </div>
        </div>
        <div class="badges-group">
            <span class="badge badge-env" data-bind="environment">{env_escaped}</span>
            <span class="badge badge-health" data-bind="health">{health_escaped}</span>
            <span class="badge badge-state" data-bind="ui-state">ESTADO: {estado_activo.upper()}</span>
            <span class="badge badge-loopback font-tabular">● 127.0.0.1</span>
        </div>
    </header>

    <!-- Barra Superior de Monitoreo Cuantitativo Denso (Milestone 3) -->
    <div class="quant-topbar">
        <div class="quant-strip-item">
            <div class="strip-lbl" data-bind="top-quote-label">{top_quote_label}</div>
            <div class="strip-val font-tabular" data-bind="top-quote-value">{top_quote_value}</div>
            <div class="text-dim font-tabular" data-bind="top-quote-detail">{top_quote_detail}</div>
        </div>
        <div class="quant-strip-item">
            <div class="strip-lbl">Microestructura & OFI</div>
            <div class="strip-val font-tabular">MP: <span data-bind="top-micro">{top_micro}</span></div>
            <div class="text-dim font-tabular">Mid: <span data-bind="top-mid">{top_mid}</span> | OFI: <span data-bind="top-ofi">{top_ofi}</span></div>
        </div>
        <div class="quant-strip-item">
            <div class="strip-lbl">Cointegración & Kalman</div>
            <div class="strip-val font-tabular">β_t: <span data-bind="top-beta">{top_beta}</span></div>
            <div class="text-dim font-tabular">Z-Score: <span data-bind="top-z">{top_z}</span></div>
        </div>
        <div class="quant-strip-item">
            <div class="strip-lbl">Motor de Riesgo</div>
            <div class="strip-val font-tabular">DD: {top_drawdown}</div>
            <div class="text-dim font-tabular">Slots: {top_slots} | Paper: {top_pnl}</div>
        </div>
        <div class="quant-strip-item">
            <div class="strip-lbl">Linaje & Latencia</div>
            <div class="strip-val font-tabular">Edad: <span data-bind="top-age">{top_age}</span></div>
            <div class="text-dim font-tabular">Sec: <span data-bind="top-sequence">{top_sec}</span> | Hash: <span data-bind="top-hash">{top_hash}</span></div>
        </div>
    </div>

    {banners_html}

    <main class="main-grid">

        <!-- Columna Semáforo Central -->
        <div class="card">
            <div class="card-title">
                <span>Semáforo Operativo</span>
                <span class="badge badge-env font-tabular" data-bind="light-badge">{light}</span>
            </div>

            <div class="traffic-housing">
                <div class="lamp {red_class}" data-lamp="RED">ROJO</div>
                <div class="lamp {yellow_class}" data-lamp="YELLOW">AMARILLO</div>
                <div class="lamp {green_class}" data-lamp="GREEN">VERDE</div>
            </div>

            <div class="action-label" data-bind="action-label">{color_luz} · {texto_luz}</div>
            <div style="text-align: center; font-size: 0.78rem; color: var(--text-muted); margin-top: 0.25rem;">
                Dirección Canónica: <strong data-bind="canonical-direction">{texto_luz}</strong>
            </div>

            {diagnostic_html}

            <div style="margin-top: 1rem;">
                <div style="font-size: 0.72rem; font-weight: 700; color: var(--text-muted); text-transform: uppercase; margin-bottom: 0.35rem;">
                    Códigos de Razón:
                </div>
                <ul data-bind="reason-codes" style="padding-left: 1.1rem; font-size: 0.74rem; color: #cbd5e1;" class="font-tabular">
                    {reason_list}
                </ul>
            </div>
        </div>

        <!-- Columna de Telemetría Multi-Activo y Gobernanza -->
        <div style="display: flex; flex-direction: column; gap: 1rem;">

            <div class="card">
                <div class="card-title">
                    <span>Cotizaciones observadas — Yahoo Finance</span>
                    <span style="font-size: 0.72rem; color: var(--text-muted);">SP500 · TSLA · AAPL · oro</span>
                </div>
                <div class="table-responsive">
                    <table class="dense-table">
                        <thead>
                            <tr>
                                <th>Instrumento</th>
                                <th>Último</th>
                                <th>Cierre anterior</th>
                                <th>Variación</th>
                                <th>Mercado</th>
                                <th>Timestamp Yahoo</th>
                                <th>Antigüedad</th>
                                <th>Transporte / estado</th>
                                <th>Diagnóstico individual</th>
                            </tr>
                        </thead>
                        <tbody id="market-assets-body">
                            {market_asset_rows_html}
                        </tbody>
                    </table>
                </div>
                <p class="text-dim" style="margin-top: 0.65rem;">
                    Son cotizaciones públicas independientes. No implican bid/ask ejecutable, correlación ni señal operativa.
                </p>
            </div>

            <!-- Tarjeta de Precios y Cotización -->
            <div class="card">
                <div class="card-title">
                    <span>Cotización pública del índice</span>
                    <span style="font-size: 0.72rem; color: var(--text-muted);" data-bind="market-source">{market_provider} · {market_symbol}</span>
                </div>
                <div class="metrics-grid">
                    <div class="metric-box">
                        <div class="metric-title">Último Precio</div>
                        <div class="metric-value font-tabular" data-bind="market-last">{price_display}</div>
                    </div>
                    <div class="metric-box">
                        <div class="metric-title">Cierre anterior</div>
                        <div class="metric-value font-tabular" data-bind="market-previous">{previous_close_display}</div>
                    </div>
                    <div class="metric-box">
                        <div class="metric-title">Apertura</div>
                        <div class="metric-value font-tabular" data-bind="market-open">{day_open_display}</div>
                    </div>
                    <div class="metric-box">
                        <div class="metric-title">Máximo / Mínimo</div>
                        <div class="metric-value font-tabular" data-bind="market-high-low">{day_high_display} / {day_low_display}</div>
                    </div>
                    <div class="metric-box">
                        <div class="metric-title">Variación</div>
                        <div class="metric-value font-tabular" data-bind="market-change">{change_display} · {change_pct_display}</div>
                    </div>
                    <div class="metric-box">
                        <div class="metric-title">Volumen del proveedor</div>
                        <div class="metric-value font-tabular" data-bind="market-volume">{volume_display}</div>
                    </div>
                </div>
                <ul class="meta-list font-tabular" style="margin-top: 0.8rem;">
                    <li><span class="meta-label">Estado de mercado:</span> <span class="meta-val" data-bind="market-state">{market_state_escaped}</span></li>
                    <li><span class="meta-label">Timestamp Yahoo:</span> <span class="meta-val" data-bind="source-timestamp">{source_timestamp_escaped}</span></li>
                    <li><span class="meta-label">Recibido por el monitor:</span> <span class="meta-val" data-bind="received-timestamp">{received_timestamp_escaped}</span></li>
                    <li><span class="meta-label">Transporte / granularidad:</span> <span class="meta-val" data-bind="transport-granularity">{transport_escaped} / {granularity_escaped}</span></li>
                    <li><span class="meta-label">Latencia de consulta:</span> <span class="meta-val" data-bind="fetch-latency">{fetch_latency_text}</span></li>
                    <li><span class="meta-label">Fuente → recepción:</span> <span class="meta-val" data-bind="source-receive-latency">{source_to_receive_text}</span></li>
                    <li><span class="meta-label">Edad de conexión:</span> <span class="meta-val" data-bind="connection-age">{connection_age_text}</span></li>
                    <li><span class="meta-label">Estado de cotización:</span> <span class="meta-val" data-bind="quote-status">{quote_status_escaped}</span></li>
                    <li><span class="meta-label">Bid / Ask ejecutables:</span> <span class="meta-val" data-bind="bid-ask">{bid_display} / {ask_display}</span></li>
                </ul>
            </div>

            <!-- Panel de Rendimiento y Verificación -->
            <div class="card">
                <div class="card-title">
                    <span>Métricas de Validación</span>
                    <span style="font-size: 0.72rem; color: var(--text-muted);">Sin extrapolaciones ficticias</span>
                </div>
                <div class="metrics-grid">
                    <div class="metric-box">
                        <div class="metric-title">Precisión (Hit Rate)</div>
                        <div class="metric-value font-tabular">{hit_rate_display}</div>
                    </div>
                    <div class="metric-box">
                        <div class="metric-title">Tasa de Error</div>
                        <div class="metric-value font-tabular">{error_rate_display}</div>
                    </div>
                    <div class="metric-box">
                        <div class="metric-title">Sharpe Ratio</div>
                        <div class="metric-value font-tabular">{sharpe_display}</div>
                    </div>
                    <div class="metric-box">
                        <div class="metric-title">Drawdown Máximo</div>
                        <div class="metric-value font-tabular">{max_dd_display}</div>
                    </div>
                </div>
            </div>

            <!-- Panel de Telemetría Multi-Activo (Balancines Financieros) -->
            <div class="card">
                <div class="card-title">
                    <span>Telemetría Multi-Activo — Balancines Cuantitativos</span>
                    <span style="font-size: 0.72rem; color: var(--text-muted);">Sin defaults ficticios</span>
                </div>
                <div class="table-responsive">
                    <table class="dense-table">
                        <thead>
                            <tr>
                                <th>Par Balancín / Categoría</th>
                                <th>Precios (Y / X)</th>
                                <th>Kalman β_t</th>
                                <th>Z-Score</th>
                                <th>OFI Imbalance</th>
                                <th>Micro / Mid</th>
                                <th>Diagnóstico</th>
                                <th>Procedencia</th>
                                <th>Acción</th>
                            </tr>
                        </thead>
                        <tbody>
                            {balancines_rows_html}
                        </tbody>
                    </table>
                </div>
            </div>

            <!-- Panel de Gobernanza, Modelo y Seguridad -->
            <div class="card">
                <div class="card-title">
                    <span>Gobernanza y Linaje de Modelo</span>
                </div>
                <ul class="meta-list font-tabular">
                    <li><span class="meta-label">ID de Modelo:</span> <span class="meta-val">{model_id_escaped}</span></li>
                    <li><span class="meta-label">Versión de Política:</span> <span class="meta-val">{policy_ver_escaped}</span></li>
                    <li><span class="meta-label">Evento As-Of:</span> <span class="meta-val">{as_of_event_escaped}</span></li>
                    <li><span class="meta-label">Kill Switch Activo:</span> <span class="meta-val">{'SÍ' if kill_switch_active else 'NO'}</span></li>
                    <li><span class="meta-label">Documentos en Vista:</span> <span class="meta-val">{doc_count}</span></li>
                </ul>
            </div>

        </div>

    </main>

    <footer>
        <div class="font-tabular">🔒 Modo de Sólo Lectura | Cero capacidades de órdenes | Escucha exclusiva en 127.0.0.1:8080</div>
        <div class="font-tabular">Elementos cada 2 s · sin recargar la página · <span data-bind="poll-timestamp">Esperando primer corte</span></div>
    </footer>

    <div id="update-status" role="status" aria-atomic="true" class="text-dim">Conectando actualización incremental…</div>

    </div>

</body>
</html>"""


__all__ = [
    "format_metric_value",
    "deducir_estado_ui",
    "render_dashboard_html",
]
