"""Adversarial stress-test harness for ProyeccionLecturaV1, schemas/proyeccion_v1.json,
deterministic JSON serialization, hash integrity, and quantitative UI telemetry.
Executed by Challenger 1 (Milestones 2 & 3).
"""

from dataclasses import replace
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
import random
import unittest

from tests.conftest import REPO_ROOT

from sistema_luces.domain.api import (
    BalancinItemV1,
    DocumentoVistaV1,
    ProyeccionLecturaV1,
    VistaLectura,
    validar_proyeccion_lectura_v1,
)
from sistema_luces.domain.vocabulary import (
    DIRECCIONES_CANONICAS_PERMITIDAS,
    ENTORNOS_PERMITIDOS,
    ESTADOS_UI_PERMITIDOS,
    LUCES_PERMITIDAS,
    parse_direccion_canonica,
    parse_environment,
    parse_estado_ui,
    parse_instrument,
    parse_light,
)
from sistema_luces.presentation.views import format_metric_value, render_dashboard_html


class TestProyeccionV1ChallengerStress(unittest.TestCase):
    """Rigorous empirical challenge for ProyeccionLecturaV1 schema, serialization, and invariants."""

    def setUp(self) -> None:
        self.now_utc = datetime(2026, 8, 30, 12, 0, 0, tzinfo=timezone.utc)
        self.cutoff_utc = datetime(2026, 8, 30, 11, 59, 59, tzinfo=timezone.utc)
        self.valid_uuid = "123e4567-e89b-12d3-a456-426614174000"
        self.valid_hash = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"

        self.balancin_sample = BalancinItemV1(
            key="SP500_AAPL",
            name="S&P 500 vs. AAPL",
            category="Ancla Sistémica",
            symbol_y="AAPL",
            symbol_x="US500",
            price_y=185.00,
            price_x=5000.20,
            beta_kalman=0.037,
            z_score=-1.65,
            ofi=41.0,
            micro_price=185.12,
            mid_price=185.00,
            light="GREEN",
            direction="LARGO",
            composite_score=0.78,
            confidence_pct=89.0,
            action="LARGO",
        )

        self.proy_gold = ProyeccionLecturaV1(
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
            transitions=({"from": "YELLOW", "to": "GREEN"},),
            simulations=({"pnl": 150.0},),
            metrics=({"hit_rate": 0.65},),
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
            balancines=(self.balancin_sample,),
            drawdown_diario_pct=0.0,
            limite_por_trade_pct=50.0,
            slots_concurrentes_usados=0,
            slots_concurrentes_max=1,
            pnl_paper_acumulado=196.00,
            secuencia=1402,
            hash_snapshot=self.valid_hash,
            salud_feed="HEALTHY",
        )

    # -------------------------------------------------------------------------
    # 1. Deterministic JSON Serialization & Hash Integrity
    # -------------------------------------------------------------------------
    def test_canonical_json_byte_level_determinism_across_reconstructions(self) -> None:
        """Verify that 100 round-trip serializations produce the EXACT same byte sequence and SHA-256 hash."""
        initial_json = self.proy_gold.to_canonical_json()
        initial_bytes = self.proy_gold.to_canonical_bytes()
        initial_hash = hashlib.sha256(initial_bytes).hexdigest()

        for _ in range(100):
            parsed = ProyeccionLecturaV1.from_json(initial_json)
            reserialized_json = parsed.to_canonical_json()
            reserialized_bytes = parsed.to_canonical_bytes()
            reserialized_hash = hashlib.sha256(reserialized_bytes).hexdigest()

            self.assertEqual(initial_json, reserialized_json)
            self.assertEqual(initial_bytes, reserialized_bytes)
            self.assertEqual(initial_hash, reserialized_hash)

    def test_canonical_json_key_order_independence(self) -> None:
        """Verify that dictionary key insertion order in input does NOT affect canonical JSON output."""
        base_dict = self.proy_gold.to_dict()
        canonical_bytes_ref = self.proy_gold.to_canonical_bytes()

        for seed in range(50):
            rng = random.Random(seed)
            items = list(base_dict.items())
            rng.shuffle(items)
            shuffled_dict = dict(items)

            reconstructed = ProyeccionLecturaV1.from_dict(shuffled_dict)
            self.assertEqual(
                canonical_bytes_ref,
                reconstructed.to_canonical_bytes(),
                f"Determinism failed with seed {seed}",
            )

    def test_canonical_json_rejects_nan_and_inf(self) -> None:
        """Verify that float('nan'), float('inf'), and float('-inf') are rejected by canonical serialization."""
        for bad_val in [float("nan"), float("inf"), float("-inf")]:
            with self.subTest(bad_val=bad_val):
                proy_nan = replace(self.proy_gold, beta_kalman=bad_val)
                with self.assertRaises(ValueError):
                    proy_nan.to_canonical_json()

    def test_subsecond_datetime_precision_roundtrip(self) -> None:
        """Verify microsecond and subsecond precision preserves exact ISO8601 formatting."""
        dt_with_micros = datetime(2026, 8, 30, 12, 0, 0, 654321, tzinfo=timezone.utc)
        dt_without_micros = datetime(2026, 8, 30, 12, 0, 0, 0, tzinfo=timezone.utc)

        p1 = replace(self.proy_gold, generated_at_utc=dt_with_micros)
        d1 = p1.to_dict()
        self.assertEqual("2026-08-30T12:00:00.654321Z", d1["generated_at_utc"])
        p1_rec = ProyeccionLecturaV1.from_dict(d1)
        self.assertEqual(dt_with_micros, p1_rec.generated_at_utc)

        p2 = replace(self.proy_gold, generated_at_utc=dt_without_micros)
        d2 = p2.to_dict()
        self.assertEqual("2026-08-30T12:00:00Z", d2["generated_at_utc"])
        p2_rec = ProyeccionLecturaV1.from_dict(d2)
        self.assertEqual(dt_without_micros, p2_rec.generated_at_utc)

    # -------------------------------------------------------------------------
    # 2. Schema Validation Edge Cases & Boundaries
    # -------------------------------------------------------------------------
    def test_schema_version_boundary_enforcement(self) -> None:
        """Only schema_version == 1 is permitted."""
        for invalid_v in [0, 2, -1, 100]:
            p = replace(self.proy_gold, schema_version=invalid_v)
            res = validar_proyeccion_lectura_v1(p)
            self.assertFalse(res.exito)
            self.assertEqual("SCHEMA_UNSUPPORTED", res.error.codigo)

    def test_data_age_ms_boundary_matrix(self) -> None:
        """data_age_ms: None (ok in yellow), 0 (ok), 5000 (boundary ok), 5001 (must force YELLOW), negative (rejected)."""
        # 0 ms age -> GREEN ok
        p0 = replace(self.proy_gold, data_age_ms=0)
        self.assertTrue(validar_proyeccion_lectura_v1(p0).exito)

        # 5000 ms age -> GREEN boundary ok
        p5000 = replace(self.proy_gold, data_age_ms=5000)
        self.assertTrue(validar_proyeccion_lectura_v1(p5000).exito)

        # 5001 ms age -> GREEN must FAIL
        p5001 = replace(self.proy_gold, data_age_ms=5001)
        res5001 = validar_proyeccion_lectura_v1(p5001)
        self.assertFalse(res5001.exito)
        self.assertEqual("VALIDATION_ERROR", res5001.error.codigo)

        # 5001 ms age -> YELLOW must PASS
        p5001_yellow = replace(
            self.proy_gold,
            data_age_ms=5001,
            light="YELLOW",
            direction="MONITORIZAR",
        )
        self.assertTrue(validar_proyeccion_lectura_v1(p5001_yellow).exito)

        # Negative age -> always invalid
        for neg_age in [-1, -100, -999999]:
            p_neg = replace(self.proy_gold, data_age_ms=neg_age)
            res_neg = validar_proyeccion_lectura_v1(p_neg)
            self.assertFalse(res_neg.exito)
            self.assertEqual("VALIDATION_ERROR", res_neg.error.codigo)

    def test_hash_syntax_stress(self) -> None:
        """model_hash must strictly be 64-char hex."""
        valid_hashes = [
            "a" * 64,
            "0123456789abcdef" * 4,
            "0123456789ABCDEF" * 4,
            "E3B0C44298FC1C149AFBF4C8996FB92427AE41E4649B934CA495991B7852B855",
        ]
        for h in valid_hashes:
            p = replace(self.proy_gold, model_hash=h)
            self.assertTrue(validar_proyeccion_lectura_v1(p).exito)

        invalid_hashes = [
            "",
            "a" * 63,  # 63 chars (too short)
            "a" * 65,  # 65 chars (too long)
            "g" * 64,  # non-hex char
            " " * 64,
            "0" * 63 + "z",
            "12345",
            "../etc/passwd",
        ]
        for h in invalid_hashes:
            p = replace(self.proy_gold, model_hash=h)
            res = validar_proyeccion_lectura_v1(p)
            self.assertFalse(res.exito, f"Should reject invalid hash: {h}")
            self.assertEqual("VALIDATION_ERROR", res.error.codigo)

    def test_uuid_syntax_stress(self) -> None:
        """as_of_event_id must strictly be a valid UUID v4 format."""
        valid_uuids = [
            "00000000-0000-0000-0000-000000000000",
            "123e4567-e89b-12d3-a456-426614174000",
            "ABCDEF01-2345-6789-ABCD-EF0123456789",
        ]
        for u in valid_uuids:
            p = replace(self.proy_gold, as_of_event_id=u)
            self.assertTrue(validar_proyeccion_lectura_v1(p).exito)

        invalid_uuids = [
            "",
            "not-a-uuid",
            "123e4567-e89b-12d3-a456",
            "123e4567-e89b-12d3-a456-4266141740001",
            "123e4567_e89b_12d3_a456_426614174000",
            "<script>alert(1)</script>",
        ]
        for u in invalid_uuids:
            p = replace(self.proy_gold, as_of_event_id=u)
            res = validar_proyeccion_lectura_v1(p)
            self.assertFalse(res.exito, f"Should reject invalid uuid: {u}")
            self.assertEqual("VALIDATION_ERROR", res.error.codigo)

    # -------------------------------------------------------------------------
    # 3. Exhaustive Light & Direction Matrix
    # -------------------------------------------------------------------------
    def test_exhaustive_light_direction_bijection_matrix(self) -> None:
        """Verify that every (light, direction) pair outside the canonical bijection is strictly rejected."""
        all_lights = ["GREEN", "YELLOW", "RED"]
        all_dirs = ["LARGO", "MONITORIZAR", "CORTO"]
        valid_pairs = {
            ("GREEN", "LARGO"),
            ("YELLOW", "MONITORIZAR"),
            ("RED", "CORTO"),
        }

        for l in all_lights:
            for d in all_dirs:
                p = replace(self.proy_gold, light=l, direction=d)
                res = validar_proyeccion_lectura_v1(p)
                if (l, d) in valid_pairs:
                    self.assertTrue(res.exito, f"Valid pair ({l}, {d}) failed")
                else:
                    self.assertFalse(res.exito, f"Invalid pair ({l}, {d}) was unexpectedly accepted")
                    self.assertEqual("VALIDATION_ERROR", res.error.codigo)

    def test_invalid_direction_strings_rejected(self) -> None:
        """Arbitrary direction strings must fail vocabulary validation."""
        for invalid_dir in ["BUY", "SELL", "LONG_EXTRA", "SHORT_EXTRA", "FLAT", "HOLD", "NONE", "", " "]:
            p = replace(self.proy_gold, direction=invalid_dir)
            res = validar_proyeccion_lectura_v1(p)
            self.assertFalse(res.exito)
            self.assertEqual("VALIDATION_ERROR", res.error.codigo)

    # -------------------------------------------------------------------------
    # 4. Quantitative Telemetry Extreme Numbers & Edge Floats
    # -------------------------------------------------------------------------
    def test_quantitative_metrics_extreme_values_handling(self) -> None:
        """Verify handling of extreme but valid numeric values across all telemetry dimensions."""
        extreme_proy = replace(
            self.proy_gold,
            bid=0.0,
            ask=0.0001,
            spread=0.0001,
            mid_price=0.00005,
            micro_price=0.00005,
            beta_kalman=-100000.55,
            z_score=15.75,
            desbalance_ofi=-100.0,
            drawdown_diario_pct=99.99,
            limite_por_trade_pct=100.0,
            slots_concurrentes_usados=10,
            slots_concurrentes_max=10,
            pnl_paper_acumulado=-543210.99,
            secuencia=2147483647,
        )

        res = validar_proyeccion_lectura_v1(extreme_proy)
        self.assertTrue(res.exito)

        d = extreme_proy.to_dict()
        self.assertEqual(-100000.55, d["beta_kalman"])
        self.assertEqual(15.75, d["z_score"])
        self.assertEqual(-543210.99, d["pnl_paper_acumulado"])
        self.assertEqual(2147483647, d["secuencia"])

        reconstructed = ProyeccionLecturaV1.from_dict(d)
        self.assertEqual(extreme_proy.beta_kalman, reconstructed.beta_kalman)
        self.assertEqual(extreme_proy.pnl_paper_acumulado, reconstructed.pnl_paper_acumulado)

    def test_quantitative_metrics_all_none_handling(self) -> None:
        """Verify that setting all quantitative telemetry fields to None is valid (empty/initializing state)."""
        none_proy = replace(
            self.proy_gold,
            environment="NO_DATA",
            health_state="NO_DATA",
            light="YELLOW",
            direction="MONITORIZAR",
            model_id=None,
            model_version=None,
            model_hash=None,
            as_of_event_id=None,
            data_age_ms=None,
            market_cutoff_utc=None,
            ui_state="vacio",
            bid=None,
            ask=None,
            spread=None,
            mid_price=None,
            micro_price=None,
            beta_kalman=None,
            z_score=None,
            desbalance_ofi=None,
            balancines=(),
            drawdown_diario_pct=None,
            limite_por_trade_pct=None,
            slots_concurrentes_usados=None,
            slots_concurrentes_max=None,
            pnl_paper_acumulado=None,
            secuencia=None,
            hash_snapshot=None,
            salud_feed=None,
        )

        res = validar_proyeccion_lectura_v1(none_proy)
        self.assertTrue(res.exito)

        json_bytes = none_proy.to_canonical_bytes()
        rec = ProyeccionLecturaV1.from_json(json_bytes)
        self.assertIsNone(rec.bid)
        self.assertIsNone(rec.beta_kalman)
        self.assertIsNone(rec.pnl_paper_acumulado)
        self.assertEqual((), rec.balancines)

    # -------------------------------------------------------------------------
    # 5. Schema JSON Validation (schemas/proyeccion_v1.json)
    # -------------------------------------------------------------------------
    def test_schema_json_disallows_additional_properties(self) -> None:
        """Ensure schemas/proyeccion_v1.json explicitly forbids additionalProperties."""
        schema_file = REPO_ROOT / "schemas" / "proyeccion_v1.json"
        schema_json = json.loads(schema_file.read_text(encoding="utf-8"))

        self.assertFalse(schema_json.get("additionalProperties", True))

        gold_dict = self.proy_gold.to_dict()
        for k in gold_dict.keys():
            self.assertIn(k, schema_json["properties"], f"Missing property in schema: {k}")

    # -------------------------------------------------------------------------
    # 6. UI Dashboard Resiliency with Edge Values
    # -------------------------------------------------------------------------
    def test_ui_dashboard_renders_cleanly_with_extreme_and_none_values(self) -> None:
        """Verify UI rendering never produces Python exceptions or unescaped strings."""
        none_proy = replace(
            self.proy_gold,
            environment="NO_DATA",
            health_state="NO_DATA",
            light="YELLOW",
            direction="MONITORIZAR",
            model_id=None,
            model_version=None,
            model_hash=None,
            as_of_event_id=None,
            data_age_ms=None,
            ui_state="vacio",
            bid=None,
            ask=None,
            spread=None,
            mid_price=None,
            micro_price=None,
            beta_kalman=None,
            z_score=None,
            desbalance_ofi=None,
            balancines=(),
            drawdown_diario_pct=None,
            limite_por_trade_pct=None,
            slots_concurrentes_usados=None,
            slots_concurrentes_max=None,
            pnl_paper_acumulado=None,
            secuencia=None,
            hash_snapshot=None,
            salud_feed=None,
        )
        html_none = render_dashboard_html(none_proy)
        self.assertIn("N/A", html_none)
        self.assertIn("AMARILLO · MONITORIZAR", html_none)

        extreme_proy = replace(
            self.proy_gold,
            bid=123456.78,
            ask=123457.00,
            spread=0.22,
            mid_price=123456.89,
            micro_price=123456.95,
            beta_kalman=-99.99,
            z_score=-3.45,
            desbalance_ofi=-88.0,
            pnl_paper_acumulado=-12500.50,
        )
        html_extreme = render_dashboard_html(extreme_proy)
        self.assertIn("123,456.78 USD / 123,457.00 USD", html_extreme)
        self.assertIn("-99.99", html_extreme)
        self.assertIn("-3.45 σ", html_extreme)
        self.assertIn("-$12,500.50 USD", html_extreme)

    # -------------------------------------------------------------------------
    # 7. Nested Objects & Protocol Serialization Stress
    # -------------------------------------------------------------------------
    def test_nested_complex_items_serialization(self) -> None:
        """Verify transitions, simulations, and balancines containing dataclasses and nested dicts serialize cleanly."""
        nested_proy = replace(
            self.proy_gold,
            transitions=(
                {"step": 1, "timestamp": datetime(2026, 8, 30, 11, 58, 0, tzinfo=timezone.utc), "details": {"score": 0.9}},
            ),
            simulations=(
                {"id": "sim-001", "pnl": 120.50, "nested_meta": {"tags": ["fast", "scalp"]}},
            ),
            balancines=(
                self.balancin_sample,
                {
                    "key": "GOLD_DXY",
                    "name": "ORO vs. DÓLAR (DXY)",
                    "category": "Macro Inverso",
                    "symbol_y": "XAU/USD",
                    "symbol_x": "DXY",
                    "price_y": 2050.0,
                    "price_x": 104.0,
                    "beta_kalman": -18.5,
                    "z_score": -0.45,
                    "ofi": 12.0,
                    "micro_price": 2050.15,
                    "mid_price": 2050.0,
                    "light": "YELLOW",
                    "direction": "MONITORIZAR",
                    "composite_score": 0.12,
                    "confidence_pct": 68.0,
                    "action": "MONITORIZAR",
                },
            ),
        )

        d = nested_proy.to_dict()
        self.assertEqual("2026-08-30T11:58:00Z", d["transitions"][0]["timestamp"])
        self.assertEqual(2, len(d["balancines"]))
        self.assertEqual("SP500_AAPL", d["balancines"][0]["key"])
        self.assertEqual("GOLD_DXY", d["balancines"][1]["key"])

        json_str = nested_proy.to_canonical_json()
        reconstructed = ProyeccionLecturaV1.from_json(json_str)
        self.assertEqual(nested_proy.to_dict(), reconstructed.to_dict())

    # -------------------------------------------------------------------------
    # 8. Unicode & UTF-8 Character Integrity
    # -------------------------------------------------------------------------
    def test_unicode_utf8_preservation_without_ascii_escaping(self) -> None:
        """Verify Greek letters (β, σ), Spanish accents (Ó, é, í), and symbols are preserved in canonical UTF-8."""
        unicode_proy = replace(
            self.proy_gold,
            reason_codes=("SEÑAL_ESTABILIZACIÓN_ÓPTIMA", "CONVERGENCIA_β_σ"),
        )
        json_str = unicode_proy.to_canonical_json()
        self.assertIn("SEÑAL_ESTABILIZACIÓN_ÓPTIMA", json_str)
        self.assertIn("CONVERGENCIA_β_σ", json_str)
        self.assertNotIn("\\u00d3", json_str)  # No ASCII escape codes

        raw_bytes = unicode_proy.to_canonical_bytes()
        decoded = raw_bytes.decode("utf-8")
        self.assertEqual(json_str, decoded)

    # -------------------------------------------------------------------------
    # 9. Injected Broker & Untrusted Property Stripping
    # -------------------------------------------------------------------------
    def test_injected_broker_and_untrusted_fields_are_stripped(self) -> None:
        """Verify that any untrusted keys (e.g. 'broker', 'order_id') injected into JSON/dict are safely discarded."""
        payload_with_injection = self.proy_gold.to_dict()
        payload_with_injection["broker"] = "Pepperstone"
        payload_with_injection["send_order"] = True
        payload_with_injection["account_balance_real"] = 1000000.0

        reconstructed = ProyeccionLecturaV1.from_dict(payload_with_injection)
        re_dict = reconstructed.to_dict()

        self.assertNotIn("broker", re_dict)
        self.assertNotIn("send_order", re_dict)
        self.assertNotIn("account_balance_real", re_dict)

    # -------------------------------------------------------------------------
    # 10. Sanitization in Core UI Metadata
    # -------------------------------------------------------------------------
    def test_xss_injection_sanitization_in_core_metadata_and_balancines(self) -> None:
        """Stress-test that model_id, policy_version, reason_codes, and balancines are HTML escaped."""
        xss_payload = "<img src=x onerror=alert('PWNED')>"
        xss_balancin = BalancinItemV1(
            key="XSS_TEST",
            name=f"Name {xss_payload}",
            category=f"Category {xss_payload}",
            symbol_y=f"Y {xss_payload}",
            symbol_x=f"X {xss_payload}",
            action=f"Action {xss_payload}",
            price_y=100.0,
            price_x=100.0,
            beta_kalman=1.0,
            z_score=0.0,
            ofi=0.0,
            micro_price=100.0,
            mid_price=100.0,
            light="YELLOW",
            direction="MONITORIZAR",
        )

        xss_proy = replace(
            self.proy_gold,
            environment="REPLAY",
            health_state="HEALTHY",
            reason_codes=(f"REASON {xss_payload}",),
            model_id=f"MOD {xss_payload}",
            policy_version=f"POL {xss_payload}",
            balancines=(xss_balancin,),
        )

        html = render_dashboard_html(xss_proy)
        # Raw '<img src=x' must NEVER appear in output
        self.assertNotIn("<img src=x", html)
        # Escaped '&lt;img src=x' must appear
        self.assertIn("&lt;img src=x", html)


if __name__ == "__main__":
    unittest.main()
