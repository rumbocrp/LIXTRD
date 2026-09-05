"""Métricas de evaluación predictiva y calibración (SPEC-001 §6.7, §6.8, CA-26, DM-5, WP-07)."""

import math
from typing import Sequence


def calcular_brier_score(y_true: Sequence[int], probs_scaled: Sequence[int]) -> int:
    """Calcula el Brier Score escalado como entero 0..1_000_000.

    Brier = (1/N) * sum((p_i - y_i)^2)
    """
    n = len(y_true)
    if n == 0:
        return 0

    sum_sq_err = 0.0
    for y, p_int in zip(y_true, probs_scaled):
        p = p_int / 1_000_000.0
        err = p - float(y)
        sum_sq_err += err * err

    brier = sum_sq_err / n
    return max(0, min(1_000_000, int(round(brier * 1_000_000))))


def calcular_ece(y_true: Sequence[int], probs_scaled: Sequence[int], n_bins: int = 10) -> int:
    """Calcula el Expected Calibration Error (ECE) escalado como entero 0..1_000_000.

    Divide el rango [0, 1] en n_bins particiones uniformes y calcula la diferencia
    absoluta ponderada entre la precisión y la confianza promedio por bin.
    """
    n = len(y_true)
    if n == 0:
        return 0

    bin_counts = [0] * n_bins
    bin_correct = [0.0] * n_bins
    bin_conf_sum = [0.0] * n_bins

    for y, p_int in zip(y_true, probs_scaled):
        p = max(0.0, min(1.0, p_int / 1_000_000.0))
        # Determinar índice del bin 0..(n_bins-1)
        b_idx = min(n_bins - 1, int(p * n_bins))
        bin_counts[b_idx] += 1
        bin_correct[b_idx] += float(y)
        bin_conf_sum[b_idx] += p

    ece = 0.0
    for count, correct, conf_sum in zip(bin_counts, bin_correct, bin_conf_sum):
        if count > 0:
            acc = correct / count
            conf = conf_sum / count
            weight = count / n
            ece += weight * abs(acc - conf)

    return max(0, min(1_000_000, int(round(ece * 1_000_000))))


def calcular_log_loss(y_true: Sequence[int], probs_scaled: Sequence[int], eps: float = 1e-15) -> float:
    """Calcula la pérdida logarítmica (Log Loss / Cross-Entropy) con acotamiento epsilon."""
    n = len(y_true)
    if n == 0:
        return 0.0

    total_loss = 0.0
    for y, p_int in zip(y_true, probs_scaled):
        p = max(eps, min(1.0 - eps, p_int / 1_000_000.0))
        loss = -(float(y) * math.log(p) + (1.0 - float(y)) * math.log(1.0 - p))
        total_loss += loss

    return total_loss / n


def calcular_intervalo_wilson_95(successes: int, total: int) -> tuple[float, float]:
    """Calcula el intervalo de confianza de Wilson del 95% para proporciones binomiales (DM-5).

    Utiliza z = 1.959964 (cuantil 97.5% de la normal estándar).
    """
    if total <= 0:
        return 0.0, 0.0

    z = 1.959963984540054
    z2 = z * z
    n = float(total)
    k = float(max(0, min(total, successes)))
    p_hat = k / n

    denominator = 1.0 + z2 / n
    center = (p_hat + z2 / (2.0 * n)) / denominator
    margin = (z / denominator) * math.sqrt((p_hat * (1.0 - p_hat) / n) + (z2 / (4.0 * n * n)))

    lower = max(0.0, center - margin)
    upper = min(1.0, center + margin)
    return lower, upper


def calcular_utilidad_neta_con_ci(
    realized_points: Sequence[int],
    cost_points_per_trade: int = 40,
) -> tuple[float, float, float]:
    """Calcula la utilidad neta media por operación y el intervalo de confianza del 95% de operaciones positivas."""
    n = len(realized_points)
    if n == 0:
        return 0.0, 0.0, 0.0

    net_points_list = [float(pts - cost_points_per_trade) for pts in realized_points]
    mean_net = sum(net_points_list) / n

    positive_trades = sum(1 for np in net_points_list if np > 0)
    ci_lower, ci_upper = calcular_intervalo_wilson_95(positive_trades, n)

    # Estimación de cota inferior de utilidad neta proporcional
    # Si la tasa mínima de win rate CI > break-even, la cota inferior es positiva
    ci_lower_utility = mean_net - 1.96 * (math.sqrt(sum((x - mean_net) ** 2 for x in net_points_list) / n) / math.sqrt(n)) if n > 1 else mean_net
    ci_upper_utility = mean_net + 1.96 * (math.sqrt(sum((x - mean_net) ** 2 for x in net_points_list) / n) / math.sqrt(n)) if n > 1 else mean_net

    return mean_net, ci_lower_utility, ci_upper_utility
