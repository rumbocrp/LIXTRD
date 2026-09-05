"""Modulo de almacenamiento e integridad SQLite (SPEC-001 §4.3, §5.3, WP-02)."""

from sistema_luces.storage.event_store import (
    ArchivoEventos,
    ConsultaEventos,
    EntradaAuditoriaV1,
    InformeIntegridad,
    LoteEventosV1,
    PaginaEventos,
    RangoEventos,
    ReciboAuditoria,
    ReciboEvento,
    ReciboLote,
    RegistroAuditoria,
)
from sistema_luces.storage.sqlite import conectar_db, inicializar_db
from sistema_luces.storage.backup import (
    copiar_base_segura,
    restaurar_backup,
    verificar_backup_integro,
)

__all__ = [
    "ArchivoEventos",
    "ConsultaEventos",
    "EntradaAuditoriaV1",
    "InformeIntegridad",
    "LoteEventosV1",
    "PaginaEventos",
    "RangoEventos",
    "ReciboAuditoria",
    "ReciboEvento",
    "ReciboLote",
    "RegistroAuditoria",
    "conectar_db",
    "inicializar_db",
    "copiar_base_segura",
    "restaurar_backup",
    "verificar_backup_integro",
]
