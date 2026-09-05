"""Pruebas para Resultado discriminado y ErrorDominio (SPEC-001 §5.1)."""

import dataclasses
import unittest

from sistema_luces.domain.error import CODIGOS_ERROR_PERMITIDOS, CodigoErrorDominio, ErrorDominio
from sistema_luces.domain.result import Exito, Fallo, Resultado, exito, fallo


class ResultAndErrorTests(unittest.TestCase):
    def test_codigos_error_contiene_exactamente_los_21_codigos_de_la_spec(self) -> None:
        expected = {
            "VALIDATION_ERROR",
            "SCHEMA_UNSUPPORTED",
            "ENVIRONMENT_NOT_ALLOWED",
            "INSTRUMENT_NOT_ALLOWED",
            "SOURCE_NOT_DEMO",
            "CAPABILITY_DENIED",
            "DUPLICATE_EVENT",
            "OUT_OF_ORDER",
            "STALE_FEED",
            "GAPPED_FEED",
            "CLOCK_ROLLBACK",
            "STORAGE_UNAVAILABLE",
            "INTEGRITY_ERROR",
            "MODEL_UNAVAILABLE",
            "ECONOMIC_CONTRACT_INCOMPLETE",
            "RISK_LIMIT_HIT",
            "SIGNAL_EXPIRED",
            "IMPORT_INVALID",
            "RECONCILIATION_FAILED",
            "NOT_FOUND",
            "INTERNAL_ERROR",
        }
        self.assertEqual(expected, CODIGOS_ERROR_PERMITIDOS)
        self.assertEqual(21, len(CODIGOS_ERROR_PERMITIDOS))

    def test_exito_es_frozen_y_porta_datos(self) -> None:
        resultado: Resultado[int] = exito(42)
        self.assertTrue(resultado.exito)
        self.assertEqual(42, resultado.datos)
        with self.assertRaises(dataclasses.FrozenInstanceError):
            resultado.datos = 100  # type: ignore[misc]

    def test_fallo_es_frozen_y_porta_error_seguro(self) -> None:
        err = ErrorDominio(
            codigo="VALIDATION_ERROR",
            mensaje_seguro="Entrada invalida",
            reintentable=False,
            correlation_id="123e4567-e89b-12d3-a456-426614174000",
            detalles={"campo": "precio", "valor": -1},
        )
        resultado: Resultado[int] = fallo(err)
        self.assertFalse(resultado.exito)
        self.assertEqual("VALIDATION_ERROR", resultado.error.codigo)
        self.assertEqual("Entrada invalida", resultado.error.mensaje_seguro)
        self.assertFalse(resultado.error.reintentable)
        self.assertEqual("123e4567-e89b-12d3-a456-426614174000", resultado.error.correlation_id)
        self.assertEqual(-1, resultado.error.detalles.get("valor"))

        with self.assertRaises(dataclasses.FrozenInstanceError):
            resultado.error = err  # type: ignore[misc]

    def test_error_dominio_valida_codigo_permitido(self) -> None:
        with self.assertRaises(ValueError):
            ErrorDominio(
                codigo="UNKNOWN_ERROR",  # type: ignore[arg-type]
                mensaje_seguro="Invalido",
                reintentable=False,
                correlation_id="uuid",
                detalles={},
            )


if __name__ == "__main__":
    unittest.main()
