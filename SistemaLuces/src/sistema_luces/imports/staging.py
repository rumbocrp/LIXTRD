"""Validador de archivos en copia staged (SPEC-001 §5.2.1, CA-19)."""

import hashlib
import os
from pathlib import Path

from sistema_luces.domain.error import ErrorDominio
from sistema_luces.domain.result import Resultado, exito, fallo


class ValidadorStaging:
    """Valida rutas relativas seguras, límites de tamaño (<=50MiB) y hash SHA-256."""

    def __init__(self, base_dir: Path | str | None = None, max_size_bytes: int = 52_428_800) -> None:
        self.base_dir = Path(base_dir) if base_dir is not None else Path.cwd()
        self.max_size_bytes = max_size_bytes

    def validar_y_leer(self, staged_copy: str, expected_sha256: str, correlation_id: str = "") -> Resultado[bytes]:
        """Valida que la ruta no haga path traversal, exista, no exceda el límite y coincida el SHA-256."""
        # 1. Comprobación estricta de path traversal
        if (
            not isinstance(staged_copy, str)
            or not staged_copy.strip()
            or staged_copy.startswith("/")
            or ".." in staged_copy
            or "\\" in staged_copy
        ):
            return fallo(
                ErrorDominio(
                    codigo="VALIDATION_ERROR",
                    mensaje_seguro="staged_copy contiene una ruta insegura o fuera del directorio permitido",
                    reintentable=False,
                    correlation_id=correlation_id,
                    detalles={"staged_copy": staged_copy},
                )
            )

        file_path = (self.base_dir / staged_copy).resolve()
        base_resolved = self.base_dir.resolve()

        # Comprobar que file_path está estrictamente dentro de base_dir
        try:
            file_path.relative_to(base_resolved)
        except ValueError:
            return fallo(
                ErrorDominio(
                    codigo="VALIDATION_ERROR",
                    mensaje_seguro="Acceso fuera del directorio base de staging bloqueado",
                    reintentable=False,
                    correlation_id=correlation_id,
                    detalles={"path": str(file_path)},
                )
            )

        if not file_path.exists() or not file_path.is_file():
            return fallo(
                ErrorDominio(
                    codigo="IMPORT_INVALID",
                    mensaje_seguro=f"El archivo staged no existe: {staged_copy}",
                    reintentable=False,
                    correlation_id=correlation_id,
                    detalles={"staged_copy": staged_copy},
                )
            )

        file_size = file_path.stat().st_size
        if file_size > self.max_size_bytes:
            return fallo(
                ErrorDominio(
                    codigo="VALIDATION_ERROR",
                    mensaje_seguro=f"El archivo ({file_size} bytes) excede el tamaño máximo permitido ({self.max_size_bytes} bytes)",
                    reintentable=False,
                    correlation_id=correlation_id,
                    detalles={"size_bytes": file_size, "max_allowed": self.max_size_bytes},
                )
            )

        try:
            content_bytes = file_path.read_bytes()
        except Exception as e:
            return fallo(
                ErrorDominio(
                    codigo="IMPORT_INVALID",
                    mensaje_seguro=f"Error al leer archivo staged: {e}",
                    reintentable=False,
                    correlation_id=correlation_id,
                    detalles={},
                )
            )

        computed_sha256 = hashlib.sha256(content_bytes).hexdigest()
        if computed_sha256.lower() != expected_sha256.lower():
            return fallo(
                ErrorDominio(
                    codigo="INTEGRITY_ERROR",
                    mensaje_seguro="El hash SHA-256 del archivo staged no coincide con el esperado",
                    reintentable=False,
                    correlation_id=correlation_id,
                    detalles={"expected": expected_sha256, "computed": computed_sha256},
                )
            )

        return exito(content_bytes)
