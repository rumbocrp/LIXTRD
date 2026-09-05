"""API pública mínima de Sistema de Luces (SPEC-001 §5.2, CA-2, CA-28)."""

from sistema_luces.application.import_use_case import importar_demo_observada
from sistema_luces.application.query_use_case import consultar_vista
from sistema_luces.application.replay_use_case import ejecutar_replay
from sistema_luces.application.shadow_use_case import ejecutar_shadow

__all__ = [
    "consultar_vista",
    "ejecutar_replay",
    "ejecutar_shadow",
    "importar_demo_observada",
]
