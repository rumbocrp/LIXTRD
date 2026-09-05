"""Módulo de Veto y Supervisión en Tiempo Real del Instructor (Fase 5)."""

from __future__ import annotations
import numpy as np
from typing import Tuple, List, Dict, Any, Optional
from sistema_luces.domain.models import DecisionLuzContract
from sistema_luces.domain.vocabulary import TrafficLightColor, ActionType, ReasonCode

class InstructorVetoGuardrail:
    """
    Interrumpe en tiempo real (<1.0ms) cualquier acción propuesta por el modelo de ML (Estudiante)
    si viola las restricciones del Sistema de Luces (Profesor/Oracle) o si su incertidumbre supera el 25%.
    """
    def __init__(self, max_allowed_uncertainty: float = 0.25):
        self.max_allowed_uncertainty = max_allowed_uncertainty

    def evaluate_and_intercept(
        self,
        student_probs: np.ndarray, # [p_hold, p_buy, p_sell]
        teacher_decision: DecisionLuzContract,
        student_advantage: float = 0.0,
        q_variance: float = 0.0,
    ) -> Tuple[TrafficLightColor, ActionType, List[ReasonCode], bool]:
        """
        Evalúa la acción del estudiante y aplica veto si es necesario.
        Retorna: (final_state, final_action, reason_codes, was_vetoed)
        """
        reasons = list(teacher_decision.reason_codes)
        student_action_idx = int(np.argmax(student_probs))
        
        # Mapeo de acción del estudiante
        if student_action_idx == 1:
            student_action = ActionType.BUY
            student_state = TrafficLightColor.GREEN
        elif student_action_idx == 2:
            student_action = ActionType.SELL
            student_state = TrafficLightColor.RED
        else:
            student_action = ActionType.MONITOR
            student_state = TrafficLightColor.YELLOW

        # 1. Regla de Veto por Conflicto Directo Prohibido
        # Si el profesor dice VERDE y el estudiante propone VENDER (o viceversa)
        if (teacher_decision.state == TrafficLightColor.GREEN and student_action == ActionType.SELL) or \
           (teacher_decision.state == TrafficLightColor.RED and student_action == ActionType.BUY):
            reasons.append(ReasonCode.MONITOR_POLICY)
            return TrafficLightColor.YELLOW, ActionType.MONITOR, reasons, True

        # 2. Regla de Incertidumbre Epistémica en Zona Amarilla del Profesor
        # Si el profesor está en AMARILLO (espera/precaución)
        if teacher_decision.state == TrafficLightColor.YELLOW:
            # Calcular entropía / incertidumbre del estudiante: 1.0 - max(prob)
            student_confidence = float(np.max(student_probs))
            epistemic_uncertainty = 1.0 - student_confidence

            if student_action != ActionType.MONITOR:
                # Si el estudiante quiere operar en zona amarilla del profesor:
                # Exige ventaja positiva estricta e incertidumbre <= 25%
                if epistemic_uncertainty > self.max_allowed_uncertainty or student_advantage <= 0.0 or q_variance > 0.05:
                    reasons.append(ReasonCode.MONITOR_POLICY)
                    return TrafficLightColor.YELLOW, ActionType.MONITOR, reasons, True

        # 3. Acción aprobada por el instructor
        return student_state, student_action, reasons, False
