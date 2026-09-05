"""Registro inmutable de modelos y evaluador de compuerta (SPEC-001 §6.8, PROJECT.md § Interface Contracts, WP-07)."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
from typing import Any, Sequence
import uuid

from sistema_luces.cases.builder import CasoV1
from sistema_luces.domain.error import ErrorDominio
from sistema_luces.domain.manifest import ModelGatePolicyV1
from sistema_luces.domain.result import Resultado, exito, fallo
from sistema_luces.models.baseline import ModeloPredictivoV1
from sistema_luces.models.calibration import CalibradorLogistico
from sistema_luces.models.gate import DecisionCompuertaModelo, EvaluacionModeloV1, EvaluadorCompuertaModelo


class RegistroModelos:
    """Almacén inmutable de artefactos de modelos predictivos indexados por ID y hash SHA-256."""

    def __init__(self, gate_evaluator: EvaluadorCompuertaModelo | None = None) -> None:
        self._models_by_id: dict[str, ModeloPredictivoV1] = {}
        self._models_by_hash: dict[str, ModeloPredictivoV1] = {}
        self._calibrators_by_model_id: dict[str, CalibradorLogistico] = {}
        self._gate_evaluator = gate_evaluator or EvaluadorCompuertaModelo()

    def registrar(self, modelo: ModeloPredictivoV1) -> Resultado[str]:
        """Registra un artefacto de modelo de forma inmutable e idempotente.

        Retorna el modelo_id si es exitoso. Si ya existe con hash idéntico, es idempotente;
        si ya existe con distinto hash para el mismo ID, falla con INTEGRITY_ERROR.
        """
        if not modelo.model_id or not modelo.model_hash:
            return fallo(
                ErrorDominio(
                    codigo="VALIDATION_ERROR",
                    mensaje_seguro="El modelo debe tener un model_id y model_hash validos",
                    reintentable=False,
                    correlation_id="",
                    detalles={},
                )
            )

        # Verificar si ya existe por ID
        existing_id = self._models_by_id.get(modelo.model_id)
        if existing_id is not None:
            if existing_id.model_hash == modelo.model_hash:
                return exito(modelo.model_id)  # Idempotente
            else:
                return fallo(
                    ErrorDominio(
                        codigo="INTEGRITY_ERROR",
                        mensaje_seguro="Conflicto de integridad: modelo ya registrado con distinto hash",
                        reintentable=False,
                        correlation_id="",
                        detalles={"model_id": modelo.model_id, "existing_hash": existing_id.model_hash, "new_hash": modelo.model_hash},
                    )
                )

        # Verificar si ya existe por Hash
        existing_hash = self._models_by_hash.get(modelo.model_hash)
        if existing_hash is not None and existing_hash.model_id != modelo.model_id:
            # Mismo contenido con distinto ID: permitimos indexar ambos
            pass

        self._models_by_id[modelo.model_id] = modelo
        self._models_by_hash[modelo.model_hash] = modelo
        return exito(modelo.model_id)

    def registrar_calibrador(self, modelo_id: str, calibrador: CalibradorLogistico) -> Resultado[str]:
        """Asocia un calibrador OOF validado a un modelo registrado."""
        if modelo_id not in self._models_by_id:
            return fallo(
                ErrorDominio(
                    codigo="MODEL_UNAVAILABLE",
                    mensaje_seguro=f"Modelo {modelo_id} no encontrado en el registro",
                    reintentable=False,
                    correlation_id="",
                    detalles={"model_id": modelo_id},
                )
            )
        self._calibrators_by_model_id[modelo_id] = calibrador
        return exito(calibrador.calibration_id)

    def obtener(self, modelo_id_o_hash: str) -> Resultado[ModeloPredictivoV1]:
        """Obtiene un modelo por su ID o por su hash SHA-256."""
        if modelo_id_o_hash in self._models_by_id:
            return exito(self._models_by_id[modelo_id_o_hash])
        if modelo_id_o_hash in self._models_by_hash:
            return exito(self._models_by_hash[modelo_id_o_hash])
        return fallo(
            ErrorDominio(
                codigo="MODEL_UNAVAILABLE",
                mensaje_seguro=f"Modelo no disponible en el registro: {modelo_id_o_hash}",
                reintentable=False,
                correlation_id="",
                detalles={"query": modelo_id_o_hash},
            )
        )

    def obtener_calibrador(self, modelo_id: str) -> Resultado[CalibradorLogistico]:
        """Obtiene el calibrador asociado a un modelo."""
        if modelo_id in self._calibrators_by_model_id:
            return exito(self._calibrators_by_model_id[modelo_id])
        return fallo(
            ErrorDominio(
                codigo="NOT_FOUND",
                mensaje_seguro=f"Calibrador no encontrado para el modelo: {modelo_id}",
                reintentable=False,
                correlation_id="",
                detalles={"model_id": modelo_id},
            )
        )

    def listar(self) -> Resultado[list[str]]:
        """Lista todos los IDs de modelos registrados."""
        return exito(sorted(list(self._models_by_id.keys())))

    def evaluar_compuerta(
        self,
        evaluacion: EvaluacionModeloV1,
        politica: ModelGatePolicyV1,
    ) -> Resultado[DecisionCompuertaModelo]:
        """Evalúa un modelo candidato contra la política de compuerta."""
        return self._gate_evaluator.evaluar(evaluacion=evaluacion, politica=politica)

    def predecir_calibrado(self, modelo_id: str, caso: CasoV1) -> Resultado[int]:
        """Calcula la probabilidad calibrada LONG (0..1_000_000) para un caso causal."""
        res_m = self.obtener(modelo_id)
        if not res_m.exito:
            return fallo(res_m.error)
        modelo = res_m.datos

        res_raw = modelo.predecir_raw(caso.feature_snapshot)
        if not res_raw.exito:
            return fallo(res_raw.error)
        raw_l, _ = res_raw.datos

        calibrador = self._calibrators_by_model_id.get(modelo_id)
        if calibrador is not None:
            calib_l = calibrador.calibrar(raw_l)
            return exito(calib_l)
        else:
            return exito(raw_l)

    def predecir_calibrado_par(self, modelo_id: str, caso: CasoV1) -> Resultado[tuple[int, int]]:
        """Calcula las probabilidades calibradas LONG y SHORT (0..1_000_000) para un caso causal."""
        res_m = self.obtener(modelo_id)
        if not res_m.exito:
            return fallo(res_m.error)
        modelo = res_m.datos

        res_raw = modelo.predecir_raw(caso.feature_snapshot)
        if not res_raw.exito:
            return fallo(res_raw.error)
        raw_l, raw_s = res_raw.datos

        calibrador = self._calibrators_by_model_id.get(modelo_id)
        if calibrador is not None:
            calib_l = calibrador.calibrar(raw_l)
            calib_s = calibrador.calibrar(raw_s)
            return exito((calib_l, calib_s))
        else:
            return exito((raw_l, raw_s))
