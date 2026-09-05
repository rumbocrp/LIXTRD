"""Pruebas para el adaptador cTrader Demo Read-Only (WP-10, CA-1, CA-2, CA-3, SPEC-001 §10.2, §10.3)."""

from datetime import datetime, timedelta, timezone
import unittest

from tests.acceptance.helpers import make_sha256, make_uuid

from sistema_luces.domain.error import ErrorDominio
from sistema_luces.domain.event import SobreEventoV1
from sistema_luces.sources.ctrader_demo import (
    CAPABILITIES_READ_ONLY_PERMITIDAS,
    AdaptadorCTraderDemoReadOnly,
    MetadatosCuentaCTrader,
    SesionCTraderDemo,
    SolicitudConexionCTrader,
    validar_capacidades_read_only,
    validar_metadatos_cuenta_demo,
)


class CTraderDemoAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.t0 = datetime(2026, 8, 29, 14, 30, 0, tzinfo=timezone.utc)
        self.demo_hash = make_sha256("demo-account-12345")
        self.adapter = AdaptadorCTraderDemoReadOnly()

    def test_validate_capabilities_allowlist(self) -> None:
        """SPEC-001 §10.2: Solo se permiten scopes read-only de la lista blanca."""
        # Válidas: conjunto o subconjunto de CAPABILITIES_READ_ONLY_PERMITIDAS
        res_ok = validar_capacidades_read_only(
            ("market_data.read", "account_metadata.read", "historical_executions.read"),
            correlation_id=make_uuid(1),
        )
        self.assertTrue(res_ok.exito)
        self.assertEqual(CAPABILITIES_READ_ONLY_PERMITIDAS, res_ok.datos)

        # Prohibidas: scopes de escritura u órdenes devuelven CAPABILITY_DENIED (CA-2)
        res_forbidden = validar_capacidades_read_only(
            ("market_data.read", "orders.write"),
            correlation_id=make_uuid(2),
        )
        self.assertFalse(res_forbidden.exito)
        self.assertEqual("CAPABILITY_DENIED", res_forbidden.error.codigo)

        res_forbidden2 = validar_capacidades_read_only(
            ("trade.execute",),
            correlation_id=make_uuid(3),
        )
        self.assertFalse(res_forbidden2.exito)
        self.assertEqual("CAPABILITY_DENIED", res_forbidden2.error.codigo)

    def test_demo_account_verification_ca3(self) -> None:
        """CA-3: Cuenta sin demo=true o con hash no coincidente es rechazada con SOURCE_NOT_DEMO."""
        meta_live = MetadatosCuentaCTrader(
            account_id_hash=self.demo_hash,
            is_demo=False,  # NO es demo
            broker_name="cTrader-Broker",
        )
        res_live = validar_metadatos_cuenta_demo(meta_live, expected_hash=self.demo_hash, correlation_id=make_uuid(10))
        self.assertFalse(res_live.exito)
        self.assertEqual("SOURCE_NOT_DEMO", res_live.error.codigo)

        meta_wrong_hash = MetadatosCuentaCTrader(
            account_id_hash=make_sha256("other-account"),
            is_demo=True,
            broker_name="cTrader-Broker",
        )
        res_wrong_hash = validar_metadatos_cuenta_demo(
            meta_wrong_hash,
            expected_hash=self.demo_hash,
            correlation_id=make_uuid(11),
        )
        self.assertFalse(res_wrong_hash.exito)
        self.assertEqual("SOURCE_NOT_DEMO", res_wrong_hash.error.codigo)

        meta_valid = MetadatosCuentaCTrader(
            account_id_hash=self.demo_hash,
            is_demo=True,
            broker_name="cTrader-Broker",
        )
        res_valid = validar_metadatos_cuenta_demo(meta_valid, expected_hash=self.demo_hash, correlation_id=make_uuid(12))
        self.assertTrue(res_valid.exito)

    def test_live_environment_rejection_ca1(self) -> None:
        """CA-1: Entorno LIVE devuelve ENVIRONMENT_NOT_ALLOWED y no conecta."""
        sol_live = SolicitudConexionCTrader(
            correlation_id=make_uuid(20),
            environment="LIVE",  # Prohibido
            capabilities=("market_data.read",),
            expected_demo_account_hash=self.demo_hash,
        )
        res = self.adapter.conectar(sol_live)
        self.assertFalse(res.exito)
        self.assertEqual("ENVIRONMENT_NOT_ALLOWED", res.error.codigo)

    def test_backpressure_queue_handling(self) -> None:
        """Manejo seguro de backpressure con cola acotada y seguimiento de descartes."""
        sol = SolicitudConexionCTrader(
            correlation_id=make_uuid(30),
            environment="SHADOW",
            capabilities=("market_data.read",),
            expected_demo_account_hash=self.demo_hash,
            max_queue_size=5,
        )
        meta = MetadatosCuentaCTrader(
            account_id_hash=self.demo_hash,
            is_demo=True,
            broker_name="cTrader-Broker",
        )
        res_conn = self.adapter.conectar(sol, metadatos=meta)
        self.assertTrue(res_conn.exito)
        sesion: SesionCTraderDemo = res_conn.datos

        # Encolar 10 eventos cuando la cola máxima es 5
        for i in range(10):
            raw_msg = {
                "type": "QUOTE_TICK",
                "bid": 500000 + i * 10,
                "ask": 500040 + i * 10,
                "timestamp_utc": self.t0 + timedelta(seconds=i),
                "sequence": i + 1,
            }
            sesion.recibir_mensaje_raw(raw_msg)

        # La sesión no explota, gestiona la cola y registra el descarte/sobrecarga
        self.assertLessEqual(sesion.tamano_cola(), 5)
        self.assertGreater(sesion.eventos_descartados, 0)

    def test_reconnect_and_heartbeat_lifecycle(self) -> None:
        """Manejo de reconexiones, seguimiento de last_safe_cutoff y eventos RECONNECTED."""
        sol = SolicitudConexionCTrader(
            correlation_id=make_uuid(40),
            environment="SHADOW",
            capabilities=("market_data.read",),
            expected_demo_account_hash=self.demo_hash,
        )
        meta = MetadatosCuentaCTrader(
            account_id_hash=self.demo_hash,
            is_demo=True,
            broker_name="cTrader-Broker",
        )
        res_conn = self.adapter.conectar(sol, metadatos=meta)
        self.assertTrue(res_conn.exito)
        sesion: SesionCTraderDemo = res_conn.datos

        # Simular corte y reconexión
        reconnect_time = self.t0 + timedelta(seconds=120)
        res_rec = sesion.registrar_reconexion(
            reconnected_at_utc=reconnect_time,
            duration_ms=2500,
        )
        self.assertTrue(res_rec.exito)
        self.assertEqual(1, sesion.reconnect_attempts)
        self.assertEqual(reconnect_time, sesion.last_safe_cutoff)

    def test_message_mapping_to_quote_tick_envelope(self) -> None:
        """Normalización de mensaje crudo a SobreEventoV1 canónico."""
        sol = SolicitudConexionCTrader(
            correlation_id=make_uuid(50),
            environment="SHADOW",
            capabilities=("market_data.read",),
            expected_demo_account_hash=self.demo_hash,
        )
        meta = MetadatosCuentaCTrader(
            account_id_hash=self.demo_hash,
            is_demo=True,
            broker_name="cTrader-Broker",
        )
        res_conn = self.adapter.conectar(sol, metadatos=meta)
        self.assertTrue(res_conn.exito)
        sesion = res_conn.datos

        raw_msg = {
            "type": "QUOTE_TICK",
            "bid": 500000,
            "ask": 500040,
            "price_scale": 100,
            "size_bid": 10,
            "size_ask": 10,
            "timestamp_utc": self.t0,
            "sequence": 1,
        }
        res_ev = sesion.mapear_mensaje_a_sobre(raw_msg)
        self.assertTrue(res_ev.exito)
        sobre: SobreEventoV1 = res_ev.datos
        self.assertEqual("QUOTE_TICK", sobre.event_type)
        self.assertEqual("ctrader_demo", sobre.source)
        self.assertEqual("SHADOW", sobre.environment)
        self.assertEqual("US500", sobre.instrument)
        self.assertEqual(500000, sobre.payload["bid"])
        self.assertEqual(500040, sobre.payload["ask"])


if __name__ == "__main__":
    unittest.main()
