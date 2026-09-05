"""Módulo de Casos y Snapshots Causales S30/S60 (WP-05)."""

from sistema_luces.cases.builder import (
    CasoV1,
    ConstructorCaso,
    SolicitudCaso,
    validar_caso,
    validar_solicitud_caso,
)
from sistema_luces.cases.features import (
    calcular_snapshot_features,
    calcular_snapshot_hash,
)
from sistema_luces.cases.windows import (
    VentanaTemporal,
    alinear_ventana,
    es_cierre_de_ventana,
    obtener_limites_ventana,
    siguiente_cierre_de_ventana,
)

__all__ = [
    "CasoV1",
    "ConstructorCaso",
    "SolicitudCaso",
    "VentanaTemporal",
    "alinear_ventana",
    "calcular_snapshot_features",
    "calcular_snapshot_hash",
    "es_cierre_de_ventana",
    "obtener_limites_ventana",
    "siguiente_cierre_de_ventana",
    "validar_caso",
    "validar_solicitud_caso",
]
