"""Laboratorio Cuantitativo Sintético Aislado (RF-L003, RNF-L003, RB-L012).

Ejecución experimental y benchmarking de modelos de Kalman, OFI y balancines.
Todos los artefactos y resultados generados por este script quedan estrictamente
etiquetados bajo environment="SINTETICO".
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from sistema_luces.domain.vocabulary import parse_environment
from sistema_luces.quant.cross_asset import MotorMultiActivo


def ejecutar_laboratorio_sintetico(pasos: int = 10, verbose: bool = True) -> dict[str, object]:
    """Ejecuta una corrida de simulación sintética aislada en el laboratorio."""
    # Validación de procedencia
    env_res = parse_environment("SINTETICO")
    if not env_res.exito:
        raise ValueError("El entorno SINTETICO no esta habilitado en el vocabulario")

    motor = MotorMultiActivo()
    snapshots = []

    for i in range(pasos):
        snap = motor.paso_simulacion()
        snap["environment"] = "SINTETICO"
        snap["paso"] = i + 1
        snapshots.append(snap)
        if verbose:
            luz = snap.get("global_action", "N/A")
            score = snap.get("global_composite_score", 0.0)
            us500 = snap.get("us500_price", 0.0)
            print(f"  [Paso {i+1:02d}] US500={us500:.2f} | Score={score:+.4f} | Acción={luz} (SINTETICO)")

    resumen = {
        "environment": "SINTETICO",
        "pasos_ejecutados": pasos,
        "ultimo_precio_us500": snapshots[-1].get("us500_price") if snapshots else None,
        "hit_rate_pct": snapshots[-1].get("hit_rate_pct") if snapshots else None,
        "sharpe_ratio": snapshots[-1].get("sharpe_ratio") if snapshots else None,
        "max_drawdown_pct": snapshots[-1].get("max_drawdown_pct") if snapshots else None,
        "total_snapshots": len(snapshots),
    }
    return resumen


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Laboratorio Cuantitativo Sintético Aislado — Sistema de Luces"
    )
    parser.add_argument(
        "--pasos",
        type=int,
        default=10,
        help="Número de pasos de simulación a ejecutar (default: 10)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emitir resumen final en formato JSON",
    )
    args = parser.parse_args()

    if not args.json:
        print("=" * 70)
        print("🧪 LABORATORIO CUANTITATIVO SINTÉTICO (US500)")
        print("   AVISO: Datos sintéticos aislados. Cero interacción con broker o servidor.")
        print("=" * 70)

    resumen = ejecutar_laboratorio_sintetico(pasos=args.pasos, verbose=not args.json)

    if args.json:
        print(json.dumps(resumen, indent=2))
    else:
        print("-" * 70)
        print("✅ Ejecución completada exitosamente en entorno SINTETICO.")
        print(f"   Pasos: {resumen['pasos_ejecutados']} | Entorno: {resumen['environment']}")
        print("=" * 70)

    return 0


if __name__ == "__main__":
    sys.exit(main())
