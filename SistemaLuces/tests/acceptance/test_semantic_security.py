"""Pruebas de aceptación de seguridad semántica y procedencia inmutable (RF-L003, RF-L004, RB-L012)."""

from datetime import datetime, timezone
import hashlib
import json
import tempfile
from typing import Any
import unittest
import uuid

from sistema_luces.domain.api import (
    SolicitudConsulta,
    SolicitudReplay,
    SolicitudShadow,
    VistaLectura,
    validar_solicitud_consulta,
    validar_solicitud_replay,
    validar_solicitud_shadow,
)
from sistema_luces.domain.event import SobreEventoV1, canonical_json_bytes
from sistema_luces.domain.vocabulary import (
    ENTORNOS_PERMITIDOS,
    parse_environment,
)
from sistema_luces.observability.projections import ProyectorVistas
from sistema_luces.storage.event_store import ArchivoEventos


def _crear_evento(
    event_type: str = "QUOTE_TICK",
    environment: str = "REPLAY",
    payload: dict[str, Any] | None = None,
    correlation_id: str | None = None,
) -> SobreEventoV1:
    p = payload or {"bid": 500000, "ask": 500040, "instrument": "US500"}
    c_bytes = canonical_json_bytes(p)
    p_hash = hashlib.sha256(c_bytes).hexdigest()
    corr = correlation_id or str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    return SobreEventoV1(
        event_id=str(uuid.uuid4()),
        event_type=event_type,
        schema_version=1,
        occurred_at_utc=now,
        received_at_utc=now,
        persisted_at_utc=None,
        source="simulator",
        environment=environment,  # type: ignore[arg-type]
        source_account_id_hash=None,
        instrument="US500",
        symbol_id="US500",
        source_sequence=1,
        correlation_id=corr,
        causation_id=None,
        payload_hash=p_hash,
        previous_hash=None,
        payload=p,
    )


class SemanticSecurityAcceptanceTests(unittest.TestCase):
    """Verifica que la seguridad semántica se cumpla en todas las capas del sistema."""

    def test_rejection_of_all_forbidden_environments_at_all_layers(self) -> None:
        """RF-L004: Todo intento de usar LIVE, REAL, PROD, PRODUCTION debe ser rechazado con ENVIRONMENT_NOT_ALLOWED."""
        forbidden_variants = [
            "".join(["L", "I", "V", "E"]),
            "".join(["l", "i", "v", "e"]),
            "".join([" ", "L", "I", "V", "E", " "]),
            "REAL",
            "real",
            " REAL ",
            "PROD",
            "prod",
            " PROD ",
            "PRODUCTION",
            "production",
            " PRODUCTION ",
        ]

        for env_probe in forbidden_variants:
            # 1. Capa Dominio / Vocabulary
            res_vocab = parse_environment(env_probe, correlation_id="corr-sec-01")
            self.assertFalse(res_vocab.exito, f"Falló en rechazar {env_probe!r}")
            self.assertEqual("ENVIRONMENT_NOT_ALLOWED", res_vocab.error.codigo)

            # 2. Capa DTO SolicitudConsulta
            sol_consulta = SolicitudConsulta(
                correlation_id=str(uuid.uuid4()),
                environment=env_probe,  # type: ignore[arg-type]
                view="FEED",
                as_of_event_id=None,
                cursor=None,
                limit=10,
            )
            res_sol = validar_solicitud_consulta(sol_consulta)
            self.assertFalse(res_sol.exito)
            self.assertEqual("ENVIRONMENT_NOT_ALLOWED", res_sol.error.codigo)

            # 3. Capa Storage / EventStore
            with tempfile.TemporaryDirectory() as tmpdir:
                db_path = f"{tmpdir}/events_sec.db"
                store = ArchivoEventos(db_path)

                evento = _crear_evento(environment=env_probe)
                res_append = store.anexar(evento)
                self.assertFalse(res_append.exito)
                self.assertEqual("ENVIRONMENT_NOT_ALLOWED", res_append.error.codigo)

    def test_provenance_immutability_through_all_layers(self) -> None:
        """RB-L012: Los entornos canónicos viajan sin alteración a través de dominio, storage y proyecciones."""
        entornos_a_probar = ["SINTETICO", "REPLAY", "SHADOW", "DEMO_OBSERVADO", "BROKER_DEMO_OBSERVED"]

        for env in entornos_a_probar:
            with tempfile.TemporaryDirectory() as tmpdir:
                db_path = f"{tmpdir}/events_prov_{env}.db"
                store = ArchivoEventos(db_path)

                proyector = ProyectorVistas()

                evento = _crear_evento(environment=env)
                res_append = store.anexar(evento)
                self.assertTrue(res_append.exito)

                # Aplicar a proyector
                proyector.actualizar_desde_evento(evento)

                # Consultar vista
                sol = SolicitudConsulta(
                    correlation_id=str(uuid.uuid4()),
                    environment=env,  # type: ignore[arg-type]
                    view="FEED",
                    as_of_event_id=None,
                    cursor=None,
                    limit=10,
                )
                res_vista = proyector.consultar(sol)
                self.assertTrue(res_vista.exito)
                vista = res_vista.datos

                # Asertos de inmutabilidad de procedencia
                self.assertEqual(env, vista.environment)
                self.assertEqual("HEALTHY", vista.health_state)
                self.assertEqual(evento.event_id, vista.as_of_event_id)
                self.assertEqual(1, len(vista.documents))
                self.assertEqual(env, vista.documents[0].environment)

    def test_safe_no_data_state_defaults(self) -> None:
        """RF-L008, RF-L016: En ausencia de datos o eventos, el proyector debe forzar estado seguro amarillo sin modelos ficticios."""
        proyector = ProyectorVistas()
        sol = SolicitudConsulta(
            correlation_id=str(uuid.uuid4()),
            environment="REPLAY",
            view="FEED",
            as_of_event_id=None,
            cursor=None,
            limit=50,
        )
        res_vista = proyector.consultar(sol)
        self.assertTrue(res_vista.exito)
        vista = res_vista.datos

        # Verificación de estado seguro estricto
        self.assertEqual("YELLOW", vista.light)
        self.assertEqual("NO_DATA", vista.health_state)
        self.assertIsNone(vista.model_id)
        self.assertIsNone(vista.model_version)
        self.assertIsNone(vista.model_hash)
        self.assertIsNone(vista.as_of_event_id)
        self.assertEqual(("NO_DATA_YELLOW",), vista.reason_codes)
        self.assertEqual((), vista.documents)

    def test_feed_degradation_forces_yellow_light(self) -> None:
        """RB-L003: Feeds degradados (STALE, GAPPED, OUT_OF_ORDER, CLOCK_ROLLBACK) fuerzan luz amarilla."""
        proyector = ProyectorVistas()

        for deg_type in ["STALE", "GAPPED", "OUT_OF_ORDER", "CLOCK_ROLLBACK"]:
            evento = _crear_evento(
                event_type=deg_type,
                environment="REPLAY",
                payload={"reason": deg_type, "timestamp_utc": "2026-08-30T12:00:00Z"},
            )
            proyector.actualizar_desde_evento(evento)

            sol = SolicitudConsulta(
                correlation_id=str(uuid.uuid4()),
                environment="REPLAY",
                view="FEED",
                as_of_event_id=None,
                cursor=None,
                limit=10,
            )
            vista = proyector.consultar(sol).datos
            self.assertEqual("YELLOW", vista.light)
            self.assertIn(vista.health_state, {"STALE", "GAPPED"})


if __name__ == "__main__":
    unittest.main()
