#!/usr/bin/env python3
"""Script CLI para Ingestar Trades del Operador y Actualizar el Perfil del Modelo de ML."""

import sys
from pathlib import Path

# Agregar src al path
src_dir = Path(__file__).parent / "src"
sys.path.insert(0, str(src_dir))

from sistema_luces.imports.trade_importer import TradeImporter
from sistema_luces.storage.database import DecisionDatabase
from sistema_luces.learning.operator_profiler import OperatorBehavioralProfiler

def main():
    db = DecisionDatabase(db_path="luces.db")
    importer = TradeImporter()
    profiler = OperatorBehavioralProfiler()

    input_dir = Path(__file__).parent / "data" / "trades_input"
    print("=" * 80)
    print(" INGESTA DE OPERATIVA DEL OPERADOR · MOTOR DE APRENDIZAJE")
    print(f" Directorio de Entrada: {input_dir}")
    print("=" * 80)

    # Si se pasa un archivo específico por argumento CLI
    if len(sys.argv) > 1:
        files_to_process = [Path(sys.argv[1])]
    else:
        files_to_process = list(input_dir.glob("*.csv")) + list(input_dir.glob("*.json"))

    if not files_to_process:
        print("[!] No se encontraron archivos CSV o JSON en el directorio de entrada.")
        print(f"[i] Coloca tus archivos en: {input_dir}")
        return

    total_imported = 0
    total_skipped = 0

    for file_path in files_to_process:
        print(f"\n[>] Procesando: {file_path.name}...")
        if file_path.suffix.lower() == ".csv":
            report = importer.import_from_csv(file_path)
        else:
            report = importer.import_from_json(file_path)

        print(f"    • Total registros:    {report.total_records_found}")
        print(f"    • Válidos importados: {report.valid_records_imported}")
        print(f"    • Duplicados (skip):  {report.skipped_duplicates}")
        print(f"    • Hash SHA-256:       {report.file_sha256[:16]}...")

        if report.records:
            db.save_operator_trades_batch(report.records)
            total_imported += len(report.records)
        total_skipped += report.skipped_duplicates

    # Actualizar y mostrar el perfil cuantitativo
    all_trades_rows = db.get_operator_trades(limit=1000)
    print("\n" + "=" * 80)
    print(" RESUMEN CUANTITATIVO DE TU VENTAJA (EDGE) POR SETUP")
    print("=" * 80)
    
    perf = db.get_operator_performance_by_setup()
    if not perf:
        print("[-] Aún no hay trades cerrados para calcular métricas.")
    else:
        for setup, stats in perf.items():
            print(f"\n[SETUP: {setup}]")
            print(f"  • Total Trades:     {stats['total_trades']}")
            print(f"  • Win Rate:         {stats['win_rate_pct']}% (Wins: {stats['wins']} | Losses: {stats['losses']})")
            print(f"  • Retorno Medio:    {stats['avg_r_multiple']} R")
            print(f"  • PnL Neto Total:   ${stats['total_pnl_usd']:,.2f}")

    print("\n" + "=" * 80)
    print(f"[✓] Proceso completado: {total_imported} trades guardados inmutablemente en luces.db.")
    print("=" * 80)

if __name__ == "__main__":
    main()
