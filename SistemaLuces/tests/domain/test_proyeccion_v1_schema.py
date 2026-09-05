"""Pruebas exhaustivas para ProyeccionLecturaV1 y schemas/proyeccion_v1.json (RF-L015, RNF-L012, RB-L001)."""

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import unittest

from tests.conftest import REPO_ROOT

from sistema_luces.domain.api import (
    DocumentoVistaV1,
    ProyeccionLecturaV1,
    validar_proyeccion_lectura_v1,
)
from sistema_luces.domain.vocabulary import (
    DIRECCIONES_CANONICAS_PERMITIDAS,
    MAPEO_CANONICA_A_DIRECTION,
    MAPEO_DIRECCION_A_CANONICA,
    MAPEO_LUZ_A_DIRECCION_CANONICA,
    parse_direccion_canonica,
)


class ProyeccionV1SchemaTests(unittest.TestCase):
    def setUp(self) -> None:
        self.now_utc = datetime(2026, 8, 30, 12, 0, 0, tzinfo=timezone.utc)
        self.cutoff_utc = datetime(2026, 8, 30, 11, 59, 59, tzinfo=timezone.utc)
        self.valid_uuid = "123e4567-e89b-12d3-a456-426614174000"
        self.valid_hash = "a" * 64

    def _crear_proyeccion_valida_verde(self) -> ProyeccionLecturaV1:
        return ProyeccionLecturaV1(
            schema_version=1,
            generated_at_utc=self.now_utc,
            environment="REPLAY",
            instrument="US500",
            market_cutoff_utc=self.cutoff_utc,
            data_age_ms=100,
            health_state="HEALTHY",
            light="GREEN",
            direction="LARGO",
            reason_codes=("MODEL_BULLISH_SIGNAL", "FEED_HEALTHY"),
            model_id="logreg-champion-v1",
            model_version="1.0.0",
            model_hash=self.valid_hash,
            policy_version="policy-v1",
            transitions=(),
            simulations=(),
            metrics=(),
            incidents=(),
            kill_switch_active=False,
            ui_state="exito",
            as_of_event_id=self.valid_uuid,
            next_cursor=None,
            session="NY_REGULAR",
        )

    def _crear_proyeccion_valida_amarilla_no_data(self) -> ProyeccionLecturaV1:
        return ProyeccionLecturaV1(
            schema_version=1,
            generated_at_utc=self.now_utc,
            environment="NO_DATA",
            instrument="US500",
            market_cutoff_utc=None,
            data_age_ms=None,
            health_state="NO_DATA",
            light="YELLOW",
            direction="MONITORIZAR",
            reason_codes=("NO_DATA_YELLOW",),
            model_id=None,
            model_version=None,
            model_hash=None,
            policy_version="policy-v1",
            transitions=(),
            simulations=(),
            metrics=(),
            incidents=(),
            kill_switch_active=False,
            ui_state="vacio",
            as_of_event_id=None,
            next_cursor=None,
            session=None,
        )

    def test_proyeccion_v1_valida_campos_completos(self) -> None:
        proy_verde = self._crear_proyeccion_valida_verde()
        res = validar_proyeccion_lectura_v1(proy_verde)
        self.assertTrue(res.exito)
        self.assertEqual("US500", res.datos.instrument)
        self.assertEqual("GREEN", res.datos.light)
        self.assertEqual("LARGO", res.datos.direction)

        proy_no_data = self._crear_proyeccion_valida_amarilla_no_data()
        res_nd = validar_proyeccion_lectura_v1(proy_no_data)
        self.assertTrue(res_nd.exito)
        self.assertEqual("NO_DATA", res_nd.datos.environment)
        self.assertEqual("YELLOW", res_nd.datos.light)
        self.assertEqual("MONITORIZAR", res_nd.datos.direction)

    def test_proyeccion_v1_restringe_instrumento_operativo_a_us500(self) -> None:
        for invalid_inst in ["GOLD", "XAUUSD", "EURUSD", "AAPL", "SPX", ""]:
            proy = ProyeccionLecturaV1(
                schema_version=1,
                generated_at_utc=self.now_utc,
                environment="REPLAY",
                instrument=invalid_inst,  # type: ignore[arg-type]
                market_cutoff_utc=self.cutoff_utc,
                data_age_ms=100,
                health_state="HEALTHY",
                light="GREEN",
                direction="LARGO",
                reason_codes=(),
                model_id="mod-1",
                model_version="1.0.0",
                model_hash=self.valid_hash,
                policy_version="policy-v1",
                transitions=(),
                simulations=(),
                metrics=(),
                incidents=(),
                kill_switch_active=False,
                ui_state="exito",
                as_of_event_id=self.valid_uuid,
            )
            res = validar_proyeccion_lectura_v1(proy)
            self.assertFalse(res.exito)
            self.assertEqual("INSTRUMENT_NOT_ALLOWED", res.error.codigo)

    def test_proyeccion_v1_rechaza_entornos_prohibidos(self) -> None:
        for probe in ["LIVE", "REAL", "PROD", "PRODUCTION", " live ", "REAL\n"]:
            proy = ProyeccionLecturaV1(
                schema_version=1,
                generated_at_utc=self.now_utc,
                environment=probe,  # type: ignore[arg-type]
                instrument="US500",
                market_cutoff_utc=self.cutoff_utc,
                data_age_ms=100,
                health_state="HEALTHY",
                light="YELLOW",
                direction="MONITORIZAR",
                reason_codes=(),
                model_id=None,
                model_version=None,
                model_hash=None,
                policy_version="policy-v1",
                transitions=(),
                simulations=(),
                metrics=(),
                incidents=(),
                kill_switch_active=False,
                ui_state="vacio",
                as_of_event_id=None,
            )
            res = validar_proyeccion_lectura_v1(proy)
            self.assertFalse(res.exito)
            self.assertEqual("ENVIRONMENT_NOT_ALLOWED", res.error.codigo)

    def test_proyeccion_v1_invariante_amarillo_fuerza_monitorizar(self) -> None:
        for bad_dir in ["LARGO", "CORTO"]:
            proy = ProyeccionLecturaV1(
                schema_version=1,
                generated_at_utc=self.now_utc,
                environment="REPLAY",
                instrument="US500",
                market_cutoff_utc=self.cutoff_utc,
                data_age_ms=100,
                health_state="HEALTHY",
                light="YELLOW",
                direction=bad_dir,  # type: ignore[arg-type]
                reason_codes=(),
                model_id="mod-1",
                model_version="1.0.0",
                model_hash=self.valid_hash,
                policy_version="policy-v1",
                transitions=(),
                simulations=(),
                metrics=(),
                incidents=(),
                kill_switch_active=False,
                ui_state="parcial",
                as_of_event_id=self.valid_uuid,
            )
            res = validar_proyeccion_lectura_v1(proy)
            self.assertFalse(res.exito)
            self.assertEqual("VALIDATION_ERROR", res.error.codigo)
            self.assertIn("MONITORIZAR", res.error.mensaje_seguro)

    def test_proyeccion_v1_invariante_verde_exige_largo(self) -> None:
        for bad_dir in ["CORTO", "MONITORIZAR"]:
            proy = ProyeccionLecturaV1(
                schema_version=1,
                generated_at_utc=self.now_utc,
                environment="REPLAY",
                instrument="US500",
                market_cutoff_utc=self.cutoff_utc,
                data_age_ms=100,
                health_state="HEALTHY",
                light="GREEN",
                direction=bad_dir,  # type: ignore[arg-type]
                reason_codes=(),
                model_id="mod-1",
                model_version="1.0.0",
                model_hash=self.valid_hash,
                policy_version="policy-v1",
                transitions=(),
                simulations=(),
                metrics=(),
                incidents=(),
                kill_switch_active=False,
                ui_state="exito",
                as_of_event_id=self.valid_uuid,
            )
            res = validar_proyeccion_lectura_v1(proy)
            self.assertFalse(res.exito)
            self.assertEqual("VALIDATION_ERROR", res.error.codigo)
            self.assertIn("LARGO", res.error.mensaje_seguro)

    def test_proyeccion_v1_invariante_rojo_exige_corto(self) -> None:
        for bad_dir in ["LARGO", "MONITORIZAR"]:
            proy = ProyeccionLecturaV1(
                schema_version=1,
                generated_at_utc=self.now_utc,
                environment="REPLAY",
                instrument="US500",
                market_cutoff_utc=self.cutoff_utc,
                data_age_ms=100,
                health_state="HEALTHY",
                light="RED",
                direction=bad_dir,  # type: ignore[arg-type]
                reason_codes=(),
                model_id="mod-1",
                model_version="1.0.0",
                model_hash=self.valid_hash,
                policy_version="policy-v1",
                transitions=(),
                simulations=(),
                metrics=(),
                incidents=(),
                kill_switch_active=False,
                ui_state="exito",
                as_of_event_id=self.valid_uuid,
            )
            res = validar_proyeccion_lectura_v1(proy)
            self.assertFalse(res.exito)
            self.assertEqual("VALIDATION_ERROR", res.error.codigo)
            self.assertIn("CORTO", res.error.mensaje_seguro)

    def test_proyeccion_v1_invariante_no_data_fuerza_amarillo(self) -> None:
        for non_yellow in ["GREEN", "RED"]:
            proy = ProyeccionLecturaV1(
                schema_version=1,
                generated_at_utc=self.now_utc,
                environment="NO_DATA",
                instrument="US500",
                market_cutoff_utc=None,
                data_age_ms=None,
                health_state="NO_DATA",
                light=non_yellow,  # type: ignore[arg-type]
                direction="LARGO" if non_yellow == "GREEN" else "CORTO",
                reason_codes=(),
                model_id=None,
                model_version=None,
                model_hash=None,
                policy_version="policy-v1",
                transitions=(),
                simulations=(),
                metrics=(),
                incidents=(),
                kill_switch_active=False,
                ui_state="vacio",
                as_of_event_id=None,
            )
            res = validar_proyeccion_lectura_v1(proy)
            self.assertFalse(res.exito)
            self.assertEqual("VALIDATION_ERROR", res.error.codigo)

    def test_proyeccion_v1_invariante_as_of_event_id_nulo_fuerza_amarillo(self) -> None:
        proy = ProyeccionLecturaV1(
            schema_version=1,
            generated_at_utc=self.now_utc,
            environment="REPLAY",
            instrument="US500",
            market_cutoff_utc=self.cutoff_utc,
            data_age_ms=100,
            health_state="HEALTHY",
            light="GREEN",
            direction="LARGO",
            reason_codes=(),
            model_id="mod-1",
            model_version="1.0.0",
            model_hash=self.valid_hash,
            policy_version="policy-v1",
            transitions=(),
            simulations=(),
            metrics=(),
            incidents=(),
            kill_switch_active=False,
            ui_state="exito",
            as_of_event_id=None,  # Missing event ID
        )
        res = validar_proyeccion_lectura_v1(proy)
        self.assertFalse(res.exito)
        self.assertEqual("VALIDATION_ERROR", res.error.codigo)

    def test_proyeccion_v1_fechas_naive_son_rechazadas(self) -> None:
        naive_now = datetime(2026, 8, 30, 12, 0, 0)
        proy_naive_gen = ProyeccionLecturaV1(
            schema_version=1,
            generated_at_utc=naive_now,
            environment="REPLAY",
            instrument="US500",
            market_cutoff_utc=self.cutoff_utc,
            data_age_ms=100,
            health_state="HEALTHY",
            light="GREEN",
            direction="LARGO",
            reason_codes=(),
            model_id="mod-1",
            model_version="1.0.0",
            model_hash=self.valid_hash,
            policy_version="policy-v1",
            transitions=(),
            simulations=(),
            metrics=(),
            incidents=(),
            kill_switch_active=False,
            ui_state="exito",
            as_of_event_id=self.valid_uuid,
        )
        self.assertFalse(validar_proyeccion_lectura_v1(proy_naive_gen).exito)

        proy_naive_cutoff = ProyeccionLecturaV1(
            schema_version=1,
            generated_at_utc=self.now_utc,
            environment="REPLAY",
            instrument="US500",
            market_cutoff_utc=datetime(2026, 8, 30, 11, 59, 59),
            data_age_ms=100,
            health_state="HEALTHY",
            light="GREEN",
            direction="LARGO",
            reason_codes=(),
            model_id="mod-1",
            model_version="1.0.0",
            model_hash=self.valid_hash,
            policy_version="policy-v1",
            transitions=(),
            simulations=(),
            metrics=(),
            incidents=(),
            kill_switch_active=False,
            ui_state="exito",
            as_of_event_id=self.valid_uuid,
        )
        self.assertFalse(validar_proyeccion_lectura_v1(proy_naive_cutoff).exito)

    def test_proyeccion_v1_causalidad_temporal_cutoff_posterior_rechazado(self) -> None:
        future_cutoff = self.now_utc + timedelta(seconds=10)
        proy = ProyeccionLecturaV1(
            schema_version=1,
            generated_at_utc=self.now_utc,
            environment="REPLAY",
            instrument="US500",
            market_cutoff_utc=future_cutoff,
            data_age_ms=100,
            health_state="HEALTHY",
            light="GREEN",
            direction="LARGO",
            reason_codes=(),
            model_id="mod-1",
            model_version="1.0.0",
            model_hash=self.valid_hash,
            policy_version="policy-v1",
            transitions=(),
            simulations=(),
            metrics=(),
            incidents=(),
            kill_switch_active=False,
            ui_state="exito",
            as_of_event_id=self.valid_uuid,
        )
        res = validar_proyeccion_lectura_v1(proy)
        self.assertFalse(res.exito)
        self.assertEqual("VALIDATION_ERROR", res.error.codigo)

    def test_proyeccion_v1_ausencia_modelo_campeon_fuerza_amarillo(self) -> None:
        for missing_kwargs in [
            {"model_id": None, "model_version": "1.0.0", "model_hash": self.valid_hash},
            {"model_id": "mod-1", "model_version": None, "model_hash": self.valid_hash},
            {"model_id": "mod-1", "model_version": "1.0.0", "model_hash": None},
        ]:
            proy = ProyeccionLecturaV1(
                schema_version=1,
                generated_at_utc=self.now_utc,
                environment="REPLAY",
                instrument="US500",
                market_cutoff_utc=self.cutoff_utc,
                data_age_ms=100,
                health_state="HEALTHY",
                light="GREEN",
                direction="LARGO",
                reason_codes=(),
                model_id=missing_kwargs["model_id"],
                model_version=missing_kwargs["model_version"],
                model_hash=missing_kwargs["model_hash"],
                policy_version="policy-v1",
                transitions=(),
                simulations=(),
                metrics=(),
                incidents=(),
                kill_switch_active=False,
                ui_state="exito",
                as_of_event_id=self.valid_uuid,
            )
            res = validar_proyeccion_lectura_v1(proy)
            self.assertFalse(res.exito)
            self.assertEqual("VALIDATION_ERROR", res.error.codigo)

    def test_proyeccion_v1_health_state_anomalo_fuerza_amarillo(self) -> None:
        for unhealthy in ["INITIALIZING", "STALE", "GAPPED", "ERROR", "STOPPED"]:
            proy = ProyeccionLecturaV1(
                schema_version=1,
                generated_at_utc=self.now_utc,
                environment="REPLAY",
                instrument="US500",
                market_cutoff_utc=self.cutoff_utc,
                data_age_ms=100,
                health_state=unhealthy,
                light="GREEN",
                direction="LARGO",
                reason_codes=(),
                model_id="mod-1",
                model_version="1.0.0",
                model_hash=self.valid_hash,
                policy_version="policy-v1",
                transitions=(),
                simulations=(),
                metrics=(),
                incidents=(),
                kill_switch_active=False,
                ui_state="parcial",
                as_of_event_id=self.valid_uuid,
            )
            res = validar_proyeccion_lectura_v1(proy)
            self.assertFalse(res.exito)
            self.assertEqual("VALIDATION_ERROR", res.error.codigo)

    def test_proyeccion_v1_kill_switch_activo_fuerza_amarillo(self) -> None:
        proy = ProyeccionLecturaV1(
            schema_version=1,
            generated_at_utc=self.now_utc,
            environment="REPLAY",
            instrument="US500",
            market_cutoff_utc=self.cutoff_utc,
            data_age_ms=100,
            health_state="HEALTHY",
            light="GREEN",
            direction="LARGO",
            reason_codes=(),
            model_id="mod-1",
            model_version="1.0.0",
            model_hash=self.valid_hash,
            policy_version="policy-v1",
            transitions=(),
            simulations=(),
            metrics=(),
            incidents=(),
            kill_switch_active=True,
            ui_state="error",
            as_of_event_id=self.valid_uuid,
        )
        res = validar_proyeccion_lectura_v1(proy)
        self.assertFalse(res.exito)
        self.assertEqual("VALIDATION_ERROR", res.error.codigo)

    def test_proyeccion_v1_datos_obsoletos_fuerzan_amarillo(self) -> None:
        proy = ProyeccionLecturaV1(
            schema_version=1,
            generated_at_utc=self.now_utc,
            environment="REPLAY",
            instrument="US500",
            market_cutoff_utc=self.cutoff_utc,
            data_age_ms=5001,  # > 5000 ms = stale
            health_state="HEALTHY",
            light="GREEN",
            direction="LARGO",
            reason_codes=(),
            model_id="mod-1",
            model_version="1.0.0",
            model_hash=self.valid_hash,
            policy_version="policy-v1",
            transitions=(),
            simulations=(),
            metrics=(),
            incidents=(),
            kill_switch_active=False,
            ui_state="exito",
            as_of_event_id=self.valid_uuid,
        )
        res = validar_proyeccion_lectura_v1(proy)
        self.assertFalse(res.exito)
        self.assertEqual("VALIDATION_ERROR", res.error.codigo)

    def test_proyeccion_v1_hashes_y_uuids_invalidos_son_rechazados(self) -> None:
        # Invalid hash
        proy_bad_hash = ProyeccionLecturaV1(
            schema_version=1,
            generated_at_utc=self.now_utc,
            environment="REPLAY",
            instrument="US500",
            market_cutoff_utc=self.cutoff_utc,
            data_age_ms=100,
            health_state="HEALTHY",
            light="YELLOW",
            direction="MONITORIZAR",
            reason_codes=(),
            model_id="mod-1",
            model_version="1.0.0",
            model_hash="invalid-hash",
            policy_version="policy-v1",
            transitions=(),
            simulations=(),
            metrics=(),
            incidents=(),
            kill_switch_active=False,
            ui_state="vacio",
            as_of_event_id=self.valid_uuid,
        )
        self.assertFalse(validar_proyeccion_lectura_v1(proy_bad_hash).exito)

        # Invalid UUID
        proy_bad_uuid = ProyeccionLecturaV1(
            schema_version=1,
            generated_at_utc=self.now_utc,
            environment="REPLAY",
            instrument="US500",
            market_cutoff_utc=self.cutoff_utc,
            data_age_ms=100,
            health_state="HEALTHY",
            light="YELLOW",
            direction="MONITORIZAR",
            reason_codes=(),
            model_id="mod-1",
            model_version="1.0.0",
            model_hash=self.valid_hash,
            policy_version="policy-v1",
            transitions=(),
            simulations=(),
            metrics=(),
            incidents=(),
            kill_switch_active=False,
            ui_state="vacio",
            as_of_event_id="not-a-uuid",
        )
        self.assertFalse(validar_proyeccion_lectura_v1(proy_bad_uuid).exito)

    def test_proyeccion_v1_serializacion_roundtrip_determinista(self) -> None:
        original = self._crear_proyeccion_valida_verde()
        data_dict = original.to_dict()

        # Check key types in dict
        self.assertEqual(1, data_dict["schema_version"])
        self.assertEqual("2026-08-30T12:00:00Z", data_dict["generated_at_utc"])
        self.assertEqual("2026-08-30T11:59:59Z", data_dict["market_cutoff_utc"])
        self.assertEqual("GREEN", data_dict["light"])
        self.assertEqual("LARGO", data_dict["direction"])
        self.assertEqual(["MODEL_BULLISH_SIGNAL", "FEED_HEALTHY"], data_dict["reason_codes"])

        # Deserialization from dict
        reconstructed = ProyeccionLecturaV1.from_dict(data_dict)
        self.assertEqual(original.schema_version, reconstructed.schema_version)
        self.assertEqual(original.generated_at_utc, reconstructed.generated_at_utc)
        self.assertEqual(original.market_cutoff_utc, reconstructed.market_cutoff_utc)
        self.assertEqual(original.environment, reconstructed.environment)
        self.assertEqual(original.instrument, reconstructed.instrument)
        self.assertEqual(original.light, reconstructed.light)
        self.assertEqual(original.direction, reconstructed.direction)
        self.assertEqual(original.reason_codes, reconstructed.reason_codes)

        # JSON Round-Trip deterministic byte-a-byte
        canonical_json = original.to_canonical_json()
        canonical_bytes = original.to_canonical_bytes()
        self.assertEqual(canonical_json.encode("utf-8"), canonical_bytes)

        reconstructed_from_json = ProyeccionLecturaV1.from_json(canonical_json)
        self.assertEqual(canonical_bytes, reconstructed_from_json.to_canonical_bytes())

    def test_proyeccion_v1_esquema_json_valido_y_completo(self) -> None:
        schema_path = REPO_ROOT / "schemas" / "proyeccion_v1.json"
        self.assertTrue(schema_path.exists(), "schemas/proyeccion_v1.json no existe")

        content = json.loads(schema_path.read_text(encoding="utf-8"))
        self.assertEqual("https://json-schema.org/draft/2020-12/schema", content.get("$schema"))
        self.assertEqual("sistema-luces/proyeccion-v1", content.get("title"))
        self.assertFalse(content.get("additionalProperties", True))

        required_props = set(content.get("required", []))
        properties = content.get("properties", {})

        # All required props must be in properties
        self.assertTrue(required_props.issubset(set(properties.keys())))

        # Validate that our serialized dict conforms to the schema keys
        proy_dict = self._crear_proyeccion_valida_verde().to_dict()
        dict_keys = set(proy_dict.keys())
        schema_prop_keys = set(properties.keys())
        self.assertTrue(dict_keys.issubset(schema_prop_keys), f"Claves no cubiertas en esquema: {dict_keys - schema_prop_keys}")

    def test_proyeccion_v1_consumer_contract_backward_compat(self) -> None:
        # Consumer verifies schema version
        payload = self._crear_proyeccion_valida_amarilla_no_data().to_dict()
        self.assertEqual(1, payload["schema_version"])
        self.assertIn(payload["light"], ["GREEN", "YELLOW", "RED"])
        self.assertIn(payload["direction"], ["LARGO", "MONITORIZAR", "CORTO"])

        # Multichannel representation check: direction matches light
        self.assertEqual("MONITORIZAR", payload["direction"])
        self.assertIsNone(payload["model_id"])
        self.assertIsNone(payload["model_version"])
        self.assertIsNone(payload["model_hash"])

    def test_vocabulary_direccion_canonica_funciones(self) -> None:
        # Valid Spanish canonical directions
        for d in ["LARGO", "MONITORIZAR", "CORTO"]:
            res = parse_direccion_canonica(d)
            self.assertTrue(res.exito)
            self.assertEqual(d, res.datos)

        # English to Spanish parsing
        self.assertEqual("LARGO", parse_direccion_canonica("LONG").datos)
        self.assertEqual("CORTO", parse_direccion_canonica("SHORT").datos)
        self.assertEqual("MONITORIZAR", parse_direccion_canonica("MONITOR").datos)

        # Invalid direction
        self.assertFalse(parse_direccion_canonica("BUY").exito)
        self.assertFalse(parse_direccion_canonica("").exito)
        self.assertFalse(parse_direccion_canonica(123).exito)  # type: ignore[arg-type]

        # Mappings
        self.assertEqual("LARGO", MAPEO_LUZ_A_DIRECCION_CANONICA["GREEN"])
        self.assertEqual("MONITORIZAR", MAPEO_LUZ_A_DIRECCION_CANONICA["YELLOW"])
        self.assertEqual("CORTO", MAPEO_LUZ_A_DIRECCION_CANONICA["RED"])

        self.assertEqual("LONG", MAPEO_CANONICA_A_DIRECTION["LARGO"])
        self.assertEqual("SHORT", MAPEO_CANONICA_A_DIRECTION["CORTO"])
        self.assertEqual("MONITOR", MAPEO_CANONICA_A_DIRECTION["MONITORIZAR"])

    def test_proyeccion_v1_telemetria_cuantitativa_completa(self) -> None:
        """Verifica serialización, round-trip y validación con las 13 métricas cuantitativas y balancines."""
        balancin = {
            "key": "SP500_AAPL",
            "name": "S&P 500 vs. AAPL",
            "category": "Ancla Sistémica",
            "symbol_y": "AAPL",
            "symbol_x": "US500",
            "price_y": 185.00,
            "price_x": 5000.20,
            "beta_kalman": 0.037,
            "z_score": -1.65,
            "ofi": 41.0,
            "micro_price": 185.12,
            "mid_price": 185.00,
            "light": "GREEN",
            "direction": "LARGO",
            "composite_score": 0.78,
            "confidence_pct": 89.0,
            "action": "LARGO",
        }

        proy = ProyeccionLecturaV1(
            schema_version=1,
            generated_at_utc=self.now_utc,
            environment="REPLAY",
            instrument="US500",
            market_cutoff_utc=self.cutoff_utc,
            data_age_ms=45,
            health_state="HEALTHY",
            light="GREEN",
            direction="LARGO",
            reason_codes=("MODEL_BULLISH_SIGNAL",),
            model_id="logreg-champion-v1",
            model_version="1.0.0",
            model_hash=self.valid_hash,
            policy_version="policy-v1",
            transitions=(),
            simulations=(),
            metrics=(),
            incidents=(),
            kill_switch_active=False,
            ui_state="exito",
            as_of_event_id=self.valid_uuid,
            next_cursor=None,
            session="NY_REGULAR",
            bid=5000.00,
            ask=5000.40,
            spread=0.40,
            mid_price=5000.20,
            micro_price=5000.28,
            beta_kalman=1.042,
            z_score=-1.25,
            desbalance_ofi=35.2,
            balancines=(balancin,),
            drawdown_diario_pct=0.0,
            limite_por_trade_pct=50.0,
            slots_concurrentes_usados=0,
            slots_concurrentes_max=1,
            pnl_paper_acumulado=196.00,
            secuencia=1402,
            hash_snapshot="a" * 64,
            salud_feed="HEALTHY",
        )

        res = validar_proyeccion_lectura_v1(proy)
        self.assertTrue(res.exito, f"Validación falló: {res.error if not res.exito else ''}")

        # Roundtrip dict
        d = proy.to_dict()
        self.assertEqual(5000.00, d["bid"])
        self.assertEqual(5000.40, d["ask"])
        self.assertEqual(0.40, d["spread"])
        self.assertEqual(5000.20, d["mid_price"])
        self.assertEqual(5000.28, d["micro_price"])
        self.assertEqual(1.042, d["beta_kalman"])
        self.assertEqual(-1.25, d["z_score"])
        self.assertEqual(35.2, d["desbalance_ofi"])
        self.assertEqual(1, len(d["balancines"]))
        self.assertEqual("SP500_AAPL", d["balancines"][0]["key"])
        self.assertEqual(0.0, d["drawdown_diario_pct"])
        self.assertEqual(50.0, d["limite_por_trade_pct"])
        self.assertEqual(0, d["slots_concurrentes_usados"])
        self.assertEqual(1, d["slots_concurrentes_max"])
        self.assertEqual(196.00, d["pnl_paper_acumulado"])
        self.assertEqual(1402, d["secuencia"])
        self.assertEqual("a" * 64, d["hash_snapshot"])
        self.assertEqual("HEALTHY", d["salud_feed"])

        # Reconstructed
        reconstructed = ProyeccionLecturaV1.from_dict(d)
        self.assertEqual(proy.bid, reconstructed.bid)
        self.assertEqual(proy.ask, reconstructed.ask)
        self.assertEqual(proy.spread, reconstructed.spread)
        self.assertEqual(proy.mid_price, reconstructed.mid_price)
        self.assertEqual(proy.micro_price, reconstructed.micro_price)
        self.assertEqual(proy.beta_kalman, reconstructed.beta_kalman)
        self.assertEqual(proy.z_score, reconstructed.z_score)
        self.assertEqual(proy.desbalance_ofi, reconstructed.desbalance_ofi)
        self.assertEqual(proy.salud_feed, reconstructed.salud_feed)
        self.assertEqual(proy.pnl_paper_acumulado, reconstructed.pnl_paper_acumulado)

        # Canonical JSON & bytes roundtrip
        json_str = proy.to_canonical_json()
        from_json = ProyeccionLecturaV1.from_json(json_str)
        self.assertEqual(proy.to_dict(), from_json.to_dict())

    def test_balancin_item_v1_dataclass(self) -> None:
        """Verifica BalancinItemV1 to_dict y from_dict."""
        from sistema_luces.domain.proyeccion_lectura_v1 import BalancinItemV1

        b = BalancinItemV1(
            key="GOLD_DXY",
            name="ORO vs. DÓLAR (DXY)",
            category="Macro Inverso",
            symbol_y="XAU/USD",
            symbol_x="DXY",
            price_y=2050.0,
            price_x=104.0,
            beta_kalman=-18.5,
            z_score=-0.45,
            ofi=12.0,
            micro_price=2050.15,
            mid_price=2050.0,
            light="YELLOW",
            direction="MONITORIZAR",
            composite_score=0.12,
            confidence_pct=68.0,
            action="MONITORIZAR",
        )
        d = b.to_dict()
        self.assertEqual("GOLD_DXY", d["key"])
        self.assertEqual(-18.5, d["beta_kalman"])

        b2 = BalancinItemV1.from_dict(d)
        self.assertEqual(b.key, b2.key)
        self.assertEqual(b.beta_kalman, b2.beta_kalman)
        self.assertEqual(b.z_score, b2.z_score)


if __name__ == "__main__":
    unittest.main()
