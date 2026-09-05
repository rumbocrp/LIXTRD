"""Diales de Control Humano e Interruptor de Veto Manual en Tiempo Real (Fase 2)."""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Any

@dataclass
class HumanControlDials:
    """
    Diales interactivos del operador para modular la agresividad del motor
    y aplicar paradas de pánico o clamps de confianza en noticias de alto impacto.
    """
    t_entry: float = 0.45                # Umbral de activación [0.35, 0.65]
    t_exit: float = 0.15                 # Umbral de salida rápida [0.10, 0.25]
    z_critical: float = 1.20             # Umbral crítico de Kalman Z-score [1.0, 2.0]
    ofi_critical: float = 20.0           # Umbral de volumen OFI institucional [10, 50]
    max_confidence_clamp: float = 1.0    # Clamp de confianza máxima [0.0, 1.0]
    is_hard_veto_active: bool = False    # Parada atómica de pánico (⌘V / Botón Rojo)
    max_spread_friction_ratio: float = 0.35 # Límite de costo de spread sobre alfa (35%)

    def set_t_entry(self, val: float) -> float:
        self.t_entry = max(0.30, min(0.70, float(val)))
        return self.t_entry

    def set_t_exit(self, val: float) -> float:
        self.t_exit = max(0.05, min(0.30, float(val)))
        return self.t_exit

    def set_z_critical(self, val: float) -> float:
        self.z_critical = max(0.8, min(2.5, float(val)))
        return self.z_critical

    def set_ofi_critical(self, val: float) -> float:
        self.ofi_critical = max(5.0, min(100.0, float(val)))
        return self.ofi_critical

    def set_confidence_clamp(self, val: float) -> float:
        self.max_confidence_clamp = max(0.0, min(1.0, float(val)))
        return self.max_confidence_clamp

    def toggle_hard_veto(self) -> bool:
        """Activa o desactiva la parada de emergencia en <1.0ms."""
        self.is_hard_veto_active = not self.is_hard_veto_active
        return self.is_hard_veto_active

    def to_dict(self) -> Dict[str, Any]:
        return {
            "t_entry": self.t_entry,
            "t_exit": self.t_exit,
            "z_critical": self.z_critical,
            "ofi_critical": self.ofi_critical,
            "max_confidence_clamp": self.max_confidence_clamp,
            "is_hard_veto_active": self.is_hard_veto_active,
            "max_spread_friction_ratio": self.max_spread_friction_ratio,
        }
