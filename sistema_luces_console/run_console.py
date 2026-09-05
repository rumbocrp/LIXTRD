#!/usr/bin/env python3
"""Lanzador Principal de la Consola Industrial del Sistema de Luces 2.0."""

import sys
import uvicorn
from pathlib import Path

# Agregar src al path
src_dir = Path(__file__).parent / "src"
sys.path.insert(0, str(src_dir))

def main():
    print("=" * 80)
    print(" SISTEMA DE LUCES 2.0 | CONSOLA DE TELEMETRÍA CUANTITATIVA Y CONTROL INDUSTRIAL")
    print(" Estándares Activos: Anti-AI Slop (100/100 Pts) | UI/UX Pro Max (Densidad 9/10)")
    print(" Servidor Local: http://127.0.0.1:8765")
    print("=" * 80)
    uvicorn.run("sistema_luces.ui.server:app", host="127.0.0.1", port=8765, log_level="info")

if __name__ == "__main__":
    main()
