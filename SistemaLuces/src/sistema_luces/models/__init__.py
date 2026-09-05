"""Paquete de Modelos, Calibración y Evaluación Predictiva (SPEC-001 §6.8, WP-07)."""

from sistema_luces.domain.manifest import ModelGatePolicyV1, validar_model_gate_policy
from sistema_luces.models.baseline import (
    ModeloBaseV1,
    ModeloPredictivoV1,
    ModeloRegresionLogisticaV1,
    calcular_hash_modelo,
    sigmoid,
)
from sistema_luces.models.calibration import CalibradorLogistico
from sistema_luces.models.drift import DetectorDrift, InformeDriftV1
from sistema_luces.models.gate import (
    DecisionCompuertaModelo,
    EvaluacionModeloV1,
    EvaluadorCompuertaModelo,
)
from sistema_luces.models.metrics import (
    calcular_brier_score,
    calcular_ece,
    calcular_intervalo_wilson_95,
    calcular_log_loss,
    calcular_utilidad_neta_con_ci,
)
from sistema_luces.models.registry import RegistroModelos

# Alias en español para contratos
PoliticaCompuertaModeloV1 = ModelGatePolicyV1
validar_politica_compuerta_modelo = validar_model_gate_policy

__all__ = [
    "RegistroModelos",
    "ModeloPredictivoV1",
    "ModeloBaseV1",
    "ModeloRegresionLogisticaV1",
    "CalibradorLogistico",
    "EvaluadorCompuertaModelo",
    "EvaluacionModeloV1",
    "DecisionCompuertaModelo",
    "ModelGatePolicyV1",
    "PoliticaCompuertaModeloV1",
    "validar_model_gate_policy",
    "validar_politica_compuerta_modelo",
    "DetectorDrift",
    "InformeDriftV1",
    "calcular_brier_score",
    "calcular_ece",
    "calcular_log_loss",
    "calcular_intervalo_wilson_95",
    "calcular_utilidad_neta_con_ci",
    "calcular_hash_modelo",
    "sigmoid",
]
