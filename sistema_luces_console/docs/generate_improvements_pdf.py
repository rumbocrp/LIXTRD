#!/usr/bin/env python3
"""Generador del Documento PDF de Propuesta de Mejoras Técnicas y Telemetría Avanzada."""

import subprocess
from pathlib import Path

def create_improvements_html() -> str:
    return """<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <title>PROPUESTA DE MEJORAS TÉCNICAS: ANALÍTICA L2, ESPACIO LATENTE Y EXPLICABILIDAD ML</title>
    <style>
        @page {
            size: A4;
            margin: 20mm 15mm 20mm 15mm;
            @bottom-right {
                content: counter(page);
                font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
                font-size: 9pt;
                color: #71717a;
            }
            @bottom-left {
                content: "SISTEMA DE LUCES 2.0 · PROPUESTA DE MEJORAS & ML TELEMETRY";
                font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
                font-size: 8pt;
                color: #71717a;
            }
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            color: #18181b;
            background-color: #ffffff;
            line-height: 1.5;
            font-size: 9.5pt;
        }

        h1, h2, h3, h4 {
            color: #09090b;
            font-weight: 700;
            page-break-after: avoid;
        }

        h1 {
            font-size: 20pt;
            border-bottom: 2px solid #18181b;
            padding-bottom: 6px;
            margin-top: 0;
            margin-bottom: 12px;
            letter-spacing: -0.02em;
        }

        h2 {
            font-size: 13pt;
            border-bottom: 1px solid #e4e4e7;
            padding-bottom: 4px;
            margin-top: 20px;
            margin-bottom: 8px;
            text-transform: uppercase;
            letter-spacing: 0.04em;
            color: #27272a;
        }

        h3 {
            font-size: 10.5pt;
            margin-top: 12px;
            margin-bottom: 4px;
            color: #3f3f46;
        }

        p {
            margin-bottom: 8px;
            text-align: justify;
        }

        .cover-page {
            page-break-after: always;
            height: 90vh;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            padding: 40px 20px;
        }

        .cover-badge {
            display: inline-block;
            background: #09090b;
            color: #f4f4f5;
            padding: 4px 10px;
            font-size: 9pt;
            font-weight: 700;
            letter-spacing: 0.1em;
            text-transform: uppercase;
            border-radius: 4px;
            margin-bottom: 20px;
        }

        .cover-title {
            font-size: 26pt;
            font-weight: 800;
            line-height: 1.15;
            letter-spacing: -0.03em;
            color: #09090b;
            margin-bottom: 15px;
        }

        .cover-subtitle {
            font-size: 12pt;
            color: #52525b;
            line-height: 1.4;
            margin-bottom: 30px;
        }

        .cover-meta {
            border-top: 1px solid #e4e4e7;
            padding-top: 20px;
            font-size: 9pt;
            color: #71717a;
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 15px;
        }

        table {
            width: 100%;
            border-collapse: collapse;
            margin: 10px 0;
            font-size: 8.5pt;
        }

        th {
            background-color: #f4f4f5;
            color: #27272a;
            text-align: left;
            font-weight: 700;
            padding: 5px 7px;
            border-top: 1px solid #d4d4d8;
            border-bottom: 1px solid #d4d4d8;
            text-transform: uppercase;
            font-size: 7.5pt;
            letter-spacing: 0.05em;
        }

        td {
            padding: 5px 7px;
            border-bottom: 1px solid #e4e4e7;
            vertical-align: top;
        }

        tr:nth-child(even) td {
            background-color: #fafafa;
        }

        code, pre {
            font-family: "SF Mono", "Menlo", "Consolas", monospace;
            font-size: 8pt;
        }

        code {
            background-color: #f4f4f5;
            padding: 1px 3px;
            border-radius: 3px;
            border: 1px solid #e4e4e7;
            color: #09090b;
        }

        pre {
            background-color: #18181b;
            color: #f4f4f5;
            padding: 8px 10px;
            border-radius: 4px;
            overflow-x: auto;
            margin: 8px 0;
            line-height: 1.3;
        }

        .callout {
            border-left: 3px solid #09090b;
            background-color: #fafafa;
            padding: 8px 12px;
            margin: 10px 0;
            border-radius: 0 4px 4px 0;
        }

        .callout-title {
            font-weight: 700;
            font-size: 8.5pt;
            text-transform: uppercase;
            margin-bottom: 3px;
            color: #09090b;
        }

        .toc-list {
            list-style: none;
            padding-left: 0;
            margin: 15px 0;
        }

        .toc-item {
            display: flex;
            justify-content: space-between;
            padding: 4px 0;
            border-bottom: 1px dotted #d4d4d8;
            font-size: 9pt;
        }

        .page-break {
            page-break-before: always;
        }
    </style>
</head>
<body>

    <!-- PORTADA -->
    <div class="cover-page">
        <div>
            <div class="cover-badge">ESPECIFICACIÓN DE PRÓXIMA GENERACIÓN · FASE 7+</div>
            <div class="cover-title">PROPUESTA DE MEJORAS TÉCNICAS, ANALÍTICA L2 & TELEMETRÍA DE MACHINE LEARNING</div>
            <div class="cover-subtitle">
                Monografía de Vistas Avanzadas, Métricas de Microestructura, Estimación Ornstein-Uhlenbeck, Explicabilidad por Gradientes y Análisis de Incertidumbre Epistémica.
            </div>
        </div>

        <div class="callout">
            <div class="callout-title">ALCANCE Y COMPATIBILIDAD CON SISTEMA DE LUCES 2.0</div>
            <p style="margin: 0; font-size: 8.5pt;">
                Este documento define la hoja de ruta para la <strong>Capa Institucional de Analítica y Explicabilidad</strong>. Todas las propuestas se diseñan como extensiones modulares sobre la arquitectura existente (Fases 0 a 6), preservando el estándar <strong>Anti-AI Slop</strong> y la latencia sub-milisegundo.
            </p>
        </div>

        <div class="cover-meta">
            <div>
                <strong>Sistema:</strong> Sistema de Luces 2.0 (Motor Cuantitativo)<br>
                <strong>Módulos:</strong> L2 DOM · JEPA D=256 · IQL · AWBC · HITL<br>
                <strong>Repositorio:</strong> /Users/nuevo/sistema_luces_console/
            </div>
            <div>
                <strong>Versión:</strong> Propuesta v1.0 (Borrador Técnico)<br>
                <strong>Fecha:</strong> Septiembre 2026<br>
                <strong>Clasificación:</strong> Confidencial / Documento de Arquitectura
            </div>
        </div>
    </div>

    <!-- ÍNDICE -->
    <h1>ÍNDICE DE LA PROPUESTA TÉCNICA</h1>
    <ul class="toc-list">
        <li class="toc-item"><span><strong>1. Vista de Profundidad L2 en Cascada (DOM Heatmap & Dinámica de Colas)</strong></span><span>Pág. 2</span></li>
        <li class="toc-item"><span><strong>2. Vista de Desacople Lead-Lag & Reversión a la Media Ornstein-Uhlenbeck</strong></span><span>Pág. 3</span></li>
        <li class="toc-item"><span><strong>3. Vista de Telemetría del Espacio Latente (I-JEPA D=256 &rarr; 2D/3D)</strong></span><span>Pág. 4</span></li>
        <li class="toc-item"><span><strong>4. Vista de Explicabilidad y Atribución de Gradientes (Integrated Gradients / SHAP)</strong></span><span>Pág. 5</span></li>
        <li class="toc-item"><span><strong>5. Desglose de Incertidumbre: Epistémica vs. Aleatoria</strong></span><span>Pág. 6</span></li>
        <li class="toc-item"><span><strong>6. Panel de Rendimiento de Setups & Shadow Run Analytics</strong></span><span>Pág. 7</span></li>
        <li class="toc-item"><span><strong>7. Matriz de Correlación Dinámica Multi-Activo (Heatmap N&times;N)</strong></span><span>Pág. 8</span></li>
    </ul>

    <div class="page-break"></div>

    <!-- SECCIÓN 1 -->
    <h2>1. Vista de Profundidad L2 en Cascada (DOM Heatmap & Dinámica de Colas)</h2>
    <p>
        Actualmente, el sistema calcula el <strong>Order Flow Imbalance (OFI)</strong> sobre $K=5$ niveles. La propuesta incorpora un panel de <strong>Escalera de Profundidad (DOM) de 10 niveles</strong> con mapa de calor de persistencia temporal.
    </p>

    <h3>1.1 Formulaciones Matemáticas de Microestructura</h3>
    <ul>
        <li><strong>Ratio de Profundidad L2 ($\text{Depth Ratio}$):</strong> Mide la asimetría de liquidez pasiva:
            <pre>Depth_Ratio_t = sum_{k=1}^{10} V_{bid, k} / sum_{k=1}^{10} V_{ask, k}</pre>
        </li>
        <li><strong>Tasa de Cancelación / Reposición ($\delta_{\text{cancel}}$):</strong> Identifica si las órdenes en los niveles $2-5$ son genuinas o cancelaciones algorítmicas de tipo <em>spoofing</em>:
            <pre>delta_cancel = sum (I(Delta P == 0 and Delta V < 0 and Trade_Executed == 0))</pre>
        </li>
        <li><strong>Detección de Órdenes Ocultas (*Iceberg Blocks*):</strong>
            Algoritmo de Cont et al. (2014): si el volumen ejecutado en el mejor Bid supera el tamaño visible $V_{\text{bid}, 1}$ sin que el precio se mueva a la baja, se detecta un bloque institucional pasivo recargándose.
        </li>
    </ul>

    <!-- SECCIÓN 2 -->
    <h2>2. Vista de Desacople Lead-Lag & Reversión Ornstein-Uhlenbeck</h2>
    <p>
        Proporciona al operador una comprensión matemática rigurosa de cuánto tiempo tardará el precio en corregir un desacople de cointegración.
    </p>

    <h3>2.1 Proceso Estocástico Ornstein-Uhlenbeck (OU)</h3>
    <p>
        El residuo de cointegración $S_t = Y_t - (\alpha_t + \beta_t X_t)$ se modela como una ecuación diferencial estocástica continua:
    </p>
    <pre>dS_t = theta_OU * (mu - S_t) dt + sigma_OU * dW_t</pre>
    
    <table>
        <thead>
            <tr>
                <th>Parámetro OU</th>
                <th>Fórmula de Estimación MLE</th>
                <th>Utilidad Práctica para el Operador</th>
            </tr>
        </thead>
        <tbody>
            <tr>
                <td><strong>Velocidad de Reversión ($\theta_{\text{OU}}$)</strong></td>
                <td>$\theta = -\frac{1}{\Delta t} \ln(b)$, donde $S_t = a + b S_{t-1} + \epsilon$</td>
                <td>Indica con qué fuerza el precio es atraído hacia su media.</td>
            </tr>
            <tr>
                <td><strong>Vida Media del Spread ($T_{1/2}$)</strong></td>
                <td>$T_{1/2} = \frac{\ln(2)}{\theta_{\text{OU}}}$</td>
                <td><strong>Tiempo esperado de duración del trade</strong> (en ticks o segundos).</td>
            </tr>
            <tr>
                <td><strong>Bandas de Desviación ($\sigma_{\text{eq}}$)</strong></td>
                <td>$\sigma_{\text{eq}} = \frac{\sigma_{\text{OU}}}{\sqrt{2 \theta_{\text{OU}}}}$</td>
                <td>Define los niveles de Take Profit dinámico cuando $Z \to 0$.</td>
            </tr>
        </tbody>
    </table>

    <div class="page-break"></div>

    <!-- SECCIÓN 3 -->
    <h2>3. Vista de Telemetría del Espacio Latente (I-JEPA $D=256 \to 2D$)</h2>
    <p>
        El codificador I-JEPA genera vectores continuos de 256 dimensiones. La propuesta implementa una proyección dimensional en tiempo real mediante <strong>PCA incremental</strong> o <strong>UMAP en streaming</strong>.
    </p>

    <h3>3.1 Diagnóstico de Anomalías y Fuera de Distribución (OOD)</h3>
    <p>
        • <strong>Mapeo Geométrico:</strong> Los trades ganadores históricos forman un clúster compacto $\mathcal{K}_{\text{profitable}} \subset \mathbb{R}^2$.<br>
        • <strong>Distancia de Mahalanobis en Espacio Latente ($d_M$):</strong>
    </p>
    <pre>d_M(z_t, mu_K) = sqrt( (z_t - mu_K)^T * Sigma^{-1} * (z_t - mu_K) )</pre>
    <div class="callout">
        <div class="callout-title">DETECCIÓN TEMPRANA DE RÉGIMEN DESCONOCIDO</div>
        <p style="margin: 0; font-size: 8.5pt;">
            Si el vector latente actual $z_t$ se aleja más de $3.5\sigma$ del centroide histórico, el sistema activa la alerta <code>OOD_REGIME_WARNING</code>, informando al operador que el mercado está en un estado nunca antes visto durante el entrenamiento.
        </p>
    </div>

    <!-- SECCIÓN 4 -->
    <h2>4. Vista de Explicabilidad y Atribución de Gradientes</h2>
    <p>
        Responde a la pregunta fundamental del operador en cada tick: <em>"¿Por qué el modelo de ML o el semáforo eligió BUY en lugar de HOLD?"</em>
    </p>

    <h3>4.1 Método de Gradientes Integrados (Sundararajan et al., 2017)</h3>
    <pre>IG_i(x) = (x_i - x'_i) * int_0^1 ( partial F(x' + alpha*(x - x')) / partial x_i ) d_alpha</pre>
    <p>Descompone la probabilidad de decisión en barras porcentuales en vivo:</p>
    <table>
        <thead>
            <tr>
                <th>Variable de Entrada</th>
                <th>Atribución en Tick Actual (%)</th>
                <th>Impacto en la Decisión</th>
            </tr>
        </thead>
        <tbody>
            <tr>
                <td><strong>Order Flow Imbalance L2 ($K=5$)</strong></td>
                <td><strong>$+42.5\%$</strong></td>
                <td>Fuerte acumulación pasiva en Bid empujando hacia BUY.</td>
            </tr>
            <tr>
                <td><strong>Kalman Spread Z-Score</strong></td>
                <td><strong>$+31.0\%$</strong></td>
                <td>Activo subvalorado respecto al ancla macro ($Z = -1.95$).</td>
            </tr>
            <tr>
                <td><strong>Stoikov Micro-Price Delta</strong></td>
                <td><strong>$+16.5\%$</strong></td>
                <td>Micro-precio cotiza con prima de $350\text{ ppm}$ sobre el mid.</td>
            </tr>
            <tr>
                <td><strong>Correlación Dinámica EWMA</strong></td>
                <td><strong>$+10.0\%$</strong></td>
                <td>Vínculo intermercado confirmado ($\rho = -0.88$).</td>
            </tr>
        </tbody>
    </table>

    <div class="page-break"></div>

    <!-- SECCIÓN 5 -->
    <h2>5. Desglose de Incertidumbre: Epistémica vs. Aleatoria</h2>
    <p>
        El modelo de Machine Learning (IQL + AWBC) separa cuantitativamente dos tipos de incertidumbre antes de autorizar cualquier operación:
    </p>

    <table>
        <thead>
            <tr>
                <th>Tipo de Incertidumbre</th>
                <th>Origen Físico / Matemático</th>
                <th>Métrica en Tiempo Real</th>
                <th>Acción del Sistema</th>
            </tr>
        </thead>
        <tbody>
            <tr>
                <td><strong>Incertidumbre Epistémica</strong> (Falta de datos)</td>
                <td>El modelo nunca vio un patrón similar en el historial.</td>
                <td>Dispersión de Redes Gemelas: $\Delta Q = |Q_1(s, a) - Q_2(s, a)|$</td>
                <td>Si $\Delta Q &gt; 0.08 \implies$ <strong>Veto automático a AMARILLO</strong>.</td>
            </tr>
            <tr>
                <td><strong>Incertidumbre Aleatoria</strong> (Ruido de mercado)</td>
                <td>Estocasticidad inherente del flujo de órdenes.</td>
                <td>Entropía de la Política: $\mathcal{H}(\pi_\phi) = -\sum \pi \ln \pi$</td>
                <td>Modula el dimensionamiento Kelly ($\kappa_{\text{Kelly}}$).</td>
            </tr>
        </tbody>
    </table>

    <!-- SECCIÓN 6 -->
    <h2>6. Panel de Rendimiento de Setups & Shadow Run Analytics</h2>
    <p>
        Permite auditar la evolución de tus setups y el progreso de los modelos retadores en sombra.
    </p>
    <ul>
        <li><strong>Curva de Aprendizaje Comparativa (Shadow Benchmark):</strong> Gráfico acumulativo del PnL teórico del modelo retador frente al campeón vigente durante los 10,000 ticks en sombra.</li>
        <li><strong>Actualización Continua de Diebold-Mariano ($p$-value):</strong> Medición continua de la significancia estadística de la ventaja del retador.</li>
        <li><strong>Métricas por Setup del Operador:</strong> Sharpe intradiario, Sortino, $E[R]$ y ratio de acierto en ventana móvil de 20 trades.</li>
    </ul>

    <!-- SECCIÓN 7 -->
    <h2>7. Matriz de Correlación Dinámica Multi-Activo (Heatmap $N \times N$)</h2>
    <p>
        Calcula un tensor de covarianza de alta frecuencia mediante EWMA calibrada ($\lambda = 0.96$) para los activos principales:
    </p>
    <pre>XAUUSD · DXY · S&P 500 (/ES) · TSLA · AAPL · US10Y · EURUSD</pre>
    <p>
        Permite detectar al instante rotaciones de liquidez intersectoriales (ej. dinero saliendo de bonos del tesoro US10Y e ingresando masivamente al Oro o TSLA) antes de que se refleje en el precio individual del activo.
    </p>

    <div style="margin-top: 40px; border-top: 2px solid #09090b; padding-top: 12px; font-size: 8.5pt; color: #71717a; text-align: center;">
        SISTEMA DE LUCES 2.0 · DOCUMENTO DE ESPECIFICACIÓN TÉCNICA DE MEJORAS<br>
        Generado para archivo en docs/ y revisión de arquitectura.
    </div>

</body>
</html>
"""

def main():
    docs_dir = Path(__file__).parent
    html_file = docs_dir / "PROPUESTA_MEJORAS_VISTAS_TELEMETRIA_ML.html"
    pdf_file = docs_dir / "PROPUESTA_MEJORAS_VISTAS_TELEMETRIA_ML.pdf"
    md_file = docs_dir / "PROPUESTA_MEJORAS_VISTAS_TELEMETRIA_ML.md"

    print(f"[1/3] Generando HTML estructurado en: {html_file.name}...")
    html_content = create_improvements_html()
    html_file.write_text(html_content, encoding="utf-8")

    print(f"[2/3] Generando archivo Markdown en: {md_file.name}...")
    md_content = """# PROPUESTA DE MEJORAS TÉCNICAS: ANALÍTICA L2, ESPACIO LATENTE Y EXPLICABILIDAD ML

**Documento:** Especificación Técnica de Próxima Generación (Fase 7+)  
**Estado:** Propuesta Formal para Revisión (`proposal-ready`)  
**PDF Compilado:** [`docs/PROPUESTA_MEJORAS_VISTAS_TELEMETRIA_ML.pdf`](file:///Users/nuevo/sistema_luces_console/docs/PROPUESTA_MEJORAS_VISTAS_TELEMETRIA_ML.pdf)  

---

## 1. Vista de Profundidad L2 en Cascada (DOM Heatmap & Dinámica de Colas)
- **Multi-Level Depth Ratio:** $\\text{Depth Ratio}_t = \\frac{\\sum_{k=1}^{10} V_{B, k}}{\\sum_{k=1}^{10} V_{A, k}}$
- **Tasa de Cancelación / Spoofing:** $\\delta_{\\text{cancel}, k}$ identificando absorciones vs cancelaciones pasivas.
- **Detección de Icebergs:** Algoritmo de Cont, Kukanov & Stoikov (2014) y Lehalle & Laruelle (2018).

---

## 2. Vista de Desacople Lead-Lag & Reversión a la Media Ornstein-Uhlenbeck
- **Formulación SDE:** $dS_t = \\theta_{\\text{OU}} (\\mu - S_t) dt + \\sigma_{\\text{OU}} dW_t$
- **Vida Media del Spread:** $T_{1/2} = \\frac{\\ln(2)}{\\theta_{\\text{OU}}}$ (tiempo estimado de duración de la operación).
- **Prueba ADF Rodante:** $p$-valor confirmando persistencia de cointegración estadística.

---

## 3. Vista de Telemetría del Espacio Latente (I-JEPA $D=256 \\to 2D/3D$)
- **Mapeo Dimensional:** Reducción causal vía PCA y UMAP en streaming.
- **Distancia Mahalanobis:** $d_M(z_t, \\mu_{\\text{profitable}}) = \\sqrt{(z_t - \\mu)^T \\Sigma^{-1} (z_t - \\mu)}$
- **Alerta OOD:** Detección temprana de regímenes de mercado desconocidos fuera del conjunto de entrenamiento.

---

## 4. Vista de Explicabilidad y Atribución de Gradientes (Integrated Gradients / SHAP)
- **Ecuación Sundararajan et al. (2017):**
  $$\\text{IG}_i(x) = (x_i - x_i') \\times \\int_0^1 \\frac{\\partial F(x' + \\alpha(x - x'))}{\\partial x_i} d\\alpha$$
- **Desglose en Vivo por Tick:** Porcentaje exacto aportado por OFI ($42.5\\%$), Kalman Z ($31.0\\%$), Micro-Price ($16.5\\%$) y Correlación ($10.0\\%$).

---

## 5. Desglose de Incertidumbre: Epistémica vs. Aleatoria
- **Incertidumbre Epistémica:** $\\Delta Q = |Q_1(s, a) - Q_2(s, a)|$ (Dispersión de redes gemelas).
- **Incertidumbre Aleatoria:** $\\mathcal{H}(\\pi_\\phi) = -\\sum_a \\pi(a|s) \\ln \\pi(a|s)$ (Entropía softmax).
- **Auto-Veto Preventivo:** Si $\\Delta Q > 0.08$, el sistema fuerza standby amarillo automático.

---

## 6. Panel de Rendimiento de Setups & Shadow Run Analytics
- **Benchmark Comparativo:** Curva acumulativa del modelo Campeón vs Retador en los 10,000 ticks en sombra.
- **Prueba Diebold-Mariano en Vivo:** Seguimiento del $p$-valor de significancia estadística ($p < 0.01$).
- **Métricas por Setup:** Sharpe, Sortino, $E[R]$ y auditoría de capital protegido por el filtro defensivo.

---

## 7. Matriz de Correlación Dinámica Multi-Activo (Heatmap $N \\times N$)
- **Tensor de Covarianza EWMA ($\\lambda = 0.96$):**
  Cobertura cruzada en tiempo real de XAUUSD, DXY, S&P 500, TSLA, AAPL, US10Y y EURUSD para detectar rotaciones de liquidez institucionales.
"""
    md_file.write_text(md_content, encoding="utf-8")

    print(f"[3/3] Compilando PDF de alta fidelidad con Headless Chrome...")
    chrome_bin = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    cmd = [
        chrome_bin,
        "--headless",
        "--disable-gpu",
        "--no-pdf-header-footer",
        f"--print-to-pdf={pdf_file.resolve()}",
        str(html_file.resolve())
    ]
    
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode == 0:
        print(f"[✓] PDF generado con éxito: {pdf_file}")
        print(f"    • Tamaño: {pdf_file.stat().st_size / 1024:.1f} KB")
    else:
        print(f"[!] Error al compilar PDF: {res.stderr}")

if __name__ == "__main__":
    main()
