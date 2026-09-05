"""Pruebas para vocabulario cerrado y validadores (SPEC-001 §4.1, §12.2, OPT-2)."""

import decimal
import math
import unittest

from sistema_luces.domain.vocabulary import (
    ACTORES_PERMITIDOS,
    DIRECCIONES_PERMITIDAS,
    ENTORNOS_PERMITIDOS,
    ESTADOS_CONCILIACION_PERMITIDOS,
    FUENTES_PERMITIDAS,
    INSTRUMENTO_CANONICO,
    LUCES_PERMITIDAS,
    VENTANAS_DECISION_PERMITIDAS,
    parse_actor,
    parse_decision_window,
    parse_direction,
    parse_environment,
    parse_instrument,
    parse_light,
    parse_reconciliation_status,
    parse_source,
    validate_cost_scaled,
    validate_price_scaled,
    validate_probability_scaled,
    validate_quantity_scaled,
    validate_scale_factor,
)


class VocabularyTests(unittest.TestCase):
    def test_instrumento_canonico_es_solo_us500(self) -> None:
        self.assertEqual("US500", INSTRUMENTO_CANONICO)
        res_ok = parse_instrument("US500")
        self.assertTrue(res_ok.exito)
        self.assertEqual("US500", res_ok.datos)

        for invalid in ["XAUUSD", "DXY", "AAPL", "us500", ""]:
            res_fail = parse_instrument(invalid)
            self.assertFalse(res_fail.exito)
            self.assertEqual("INSTRUMENT_NOT_ALLOWED", res_fail.error.codigo)

    def test_entornos_permitidos_contiene_exactamente_seis_miembros(self) -> None:
        self.assertEqual(
            {"NO_DATA", "SINTETICO", "REPLAY", "SHADOW", "DEMO_OBSERVADO", "BROKER_DEMO_OBSERVED"},
            ENTORNOS_PERMITIDOS,
        )

    def test_parse_environment_detecta_y_rechaza_entornos_prohibidos_especificamente(self) -> None:
        # Forbidden environments matrix: LIVE, REAL, PROD, PRODUCTION (with whitespace/case variations)
        probes_prohibidos = [
            "LIVE", "live", "Live", " LIVE ", "lIvE\n", "\tLIVE\t",
            "REAL", "real", "Real", " REAL ",
            "PROD", "prod", "Prod", " PROD ",
            "PRODUCTION", "production", "Production", " PRODUCTION ",
        ]
        for probe in probes_prohibidos:
            res = parse_environment(probe, correlation_id="test-corr")
            self.assertFalse(res.exito, f"Falló al rechazar: {probe!r}")
            self.assertEqual("ENVIRONMENT_NOT_ALLOWED", res.error.codigo)
            self.assertIn("permitido", res.error.mensaje_seguro.lower())

        # Unknown environments give VALIDATION_ERROR
        for probe in ["STAGING", "TEST", "DEMO", "", "UNKNOWN"]:
            res = parse_environment(probe)
            self.assertFalse(res.exito)
            self.assertEqual("VALIDATION_ERROR", res.error.codigo)

        # Valid environments
        for valid in ["NO_DATA", "SINTETICO", "REPLAY", "SHADOW", "DEMO_OBSERVADO", "BROKER_DEMO_OBSERVED"]:
            res = parse_environment(valid)
            self.assertTrue(res.exito)
            self.assertEqual(valid, res.datos)

    def test_mapeos_canonicos_espanol_y_estados_ui(self) -> None:
        from sistema_luces.domain.vocabulary import (
            ESTADOS_UI_PERMITIDOS,
            obtener_color_luz,
            obtener_texto_direccion,
            obtener_texto_luz,
            parse_estado_ui,
        )

        self.assertEqual(
            {"cargando", "vacio", "parcial", "error", "obsoleto", "conflicto", "exito"},
            ESTADOS_UI_PERMITIDOS,
        )
        for st in ["cargando", "vacio", "parcial", "error", "obsoleto", "conflicto", "exito"]:
            self.assertTrue(parse_estado_ui(st).exito)
        self.assertFalse(parse_estado_ui("invalido").exito)

        self.assertEqual("LARGO", obtener_texto_luz("GREEN"))
        self.assertEqual("MONITORIZAR", obtener_texto_luz("YELLOW"))
        self.assertEqual("CORTO", obtener_texto_luz("RED"))

        self.assertEqual("VERDE", obtener_color_luz("GREEN"))
        self.assertEqual("AMARILLO", obtener_color_luz("YELLOW"))
        self.assertEqual("ROJO", obtener_color_luz("RED"))

        self.assertEqual("LARGO", obtener_texto_direccion("LONG"))
        self.assertEqual("CORTO", obtener_texto_direccion("SHORT"))
        self.assertEqual("MONITORIZAR", obtener_texto_direccion("MONITOR"))

    def test_luces_y_direcciones_permitidas(self) -> None:
        self.assertEqual({"GREEN", "YELLOW", "RED"}, LUCES_PERMITIDAS)
        self.assertEqual({"LONG", "SHORT", "MONITOR"}, DIRECCIONES_PERMITIDAS)

        for l in ["GREEN", "YELLOW", "RED"]:
            self.assertTrue(parse_light(l).exito)
        for invalid in ["BLUE", "green", "ORANGE", ""]:
            self.assertEqual("VALIDATION_ERROR", parse_light(invalid).error.codigo)

        for d in ["LONG", "SHORT", "MONITOR"]:
            self.assertTrue(parse_direction(d).exito)
        for invalid in ["BUY", "SELL", "long", ""]:
            self.assertEqual("VALIDATION_ERROR", parse_direction(invalid).error.codigo)

    def test_actores_fuentes_ventanas_y_conciliacion(self) -> None:
        self.assertEqual({"system", "operator", "import"}, ACTORES_PERMITIDOS)
        self.assertEqual(
            {"replay", "yahoo_finance", "ctrader_demo", "broker_demo_import", "journal_import", "simulator", "system", "operator"},
            FUENTES_PERMITIDAS,
        )
        self.assertEqual({"S30", "S60"}, VENTANAS_DECISION_PERMITIDAS)
        self.assertEqual(
            {"PENDING", "MATCHED", "PARTIAL", "UNMATCHED", "INVALID"},
            ESTADOS_CONCILIACION_PERMITIDOS,
        )

    def test_opt2_validacion_numerica_enteros_escalados(self) -> None:
        # Precios > 0
        self.assertTrue(validate_price_scaled(500100).exito)
        self.assertFalse(validate_price_scaled(0).exito)
        self.assertFalse(validate_price_scaled(-100).exito)

        # Cantidades > 0
        self.assertTrue(validate_quantity_scaled(100).exito)
        self.assertFalse(validate_quantity_scaled(0).exito)
        self.assertFalse(validate_quantity_scaled(-5).exito)

        # Escalas > 0
        self.assertTrue(validate_scale_factor(100).exito)
        self.assertFalse(validate_scale_factor(0).exito)
        self.assertFalse(validate_scale_factor(-1).exito)

        # Costos >= 0
        self.assertTrue(validate_cost_scaled(0).exito)
        self.assertTrue(validate_cost_scaled(40).exito)
        self.assertFalse(validate_cost_scaled(-1).exito)

        # Probabilidades / Ratios 0..1_000_000
        self.assertTrue(validate_probability_scaled(0).exito)
        self.assertTrue(validate_probability_scaled(500_000).exito)
        self.assertTrue(validate_probability_scaled(1_000_000).exito)
        self.assertFalse(validate_probability_scaled(-1).exito)
        self.assertFalse(validate_probability_scaled(1_000_001).exito)

    def test_opt2_rechaza_nan_infinity_y_no_finitos(self) -> None:
        for val in [float("nan"), float("inf"), float("-inf")]:
            self.assertFalse(validate_price_scaled(val).exito)  # type: ignore[arg-type]
            self.assertFalse(validate_cost_scaled(val).exito)  # type: ignore[arg-type]
            self.assertFalse(validate_probability_scaled(val).exito)  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
