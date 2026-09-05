"""Inicia el servidor HTTP de solo lectura en loopback 127.0.0.1:8080 del Sistema de Luces."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from sistema_luces.observability.projections import ProyectorVistas
from sistema_luces.storage.event_store import ArchivoEventos, ConsultaEventos
from sistema_luces.ui.server import ServidorLoopback


def cargar_proyector_desde_db(db_path: Path) -> tuple[ProyectorVistas, int]:
    """Reconstruye la vista completa desde un event log SQLite existente."""
    if not db_path.is_file():
        raise FileNotFoundError(f"No existe el event log indicado: {db_path}")
    almacen = ArchivoEventos(db_path)
    proyector = ProyectorVistas()
    cursor: str | None = None
    total = 0
    while True:
        resultado = almacen.leer(ConsultaEventos(cursor=cursor, limit=1000))
        if not resultado.exito:
            raise RuntimeError(resultado.error.mensaje_seguro if resultado.error else "No se pudo leer el event log")
        pagina = resultado.datos
        for evento in pagina.events:
            proyector.actualizar_desde_evento(evento)
        total += len(pagina.events)
        cursor = pagina.next_cursor
        if cursor is None:
            break
    return proyector, total


def main() -> None:
    parser = argparse.ArgumentParser(description="Servidor local de solo lectura del Sistema de Luces")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument(
        "--db-path",
        type=Path,
        default=Path(os.environ["SISTEMA_LUCES_DB_PATH"]) if os.environ.get("SISTEMA_LUCES_DB_PATH") else None,
        help="Event log SQLite que se reconstruirá antes de servir el dashboard",
    )
    args = parser.parse_args()

    if args.db_path is not None:
        proyector, event_count = cargar_proyector_desde_db(args.db_path.resolve())
        print(f"Event log reconstruido: {event_count} eventos desde {args.db_path.resolve()}")
    else:
        proyector = ProyectorVistas()
        event_count = 0
        print("NO_DATA: no se indicó --db-path ni SISTEMA_LUCES_DB_PATH.")
        print("Use scripts/ejecutar_demo_vivo.py para el replay demostrativo o indique un event log existente.")

    port = args.port
    servidor = ServidorLoopback(host="127.0.0.1", port=port, proyector=proyector)

    print(f"Servidor del Sistema de Luces activo en http://127.0.0.1:{port}/ (solo lectura, loopback, {event_count} eventos)")
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        servidor.shutdown()


if __name__ == "__main__":
    main()
