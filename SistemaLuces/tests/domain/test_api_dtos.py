"""Pruebas para DTOs públicos V1 y sus validadores (SPEC-001 §5.2.1)."""

from datetime import datetime, timezone
import hashlib
import unittest

from sistema_luces.domain.api import (
    DocumentoVistaV1,
    ResumenEjecucion,
    ResumenImportacion,
    SolicitudConsulta,
    SolicitudImportacionDemo,
    SolicitudReplay,
    SolicitudShadow,
    VistaLectura,
    validar_documento_vista,
    validar_resumen_ejecucion,
    validar_resumen_importacion,
    validar_solicitud_consulta,
    validar_solicitud_importacion_demo,
    validar_solicitud_replay,
    validar_solicitud_shadow,
)


class ApiDtoTests(unittest.TestCase):
    def setUp(self) -> None:
        self.valid_uuid = "123e4567-e89b-12d3-a456-426614174000"
        self.valid_hash = "a" * 64
        self.t1 = datetime(2026, 8, 29, 9, 30, 0, tzinfo=timezone.utc)
        self.t2 = datetime(2026, 8, 29, 16, 0, 0, tzinfo=timezone.utc)

    def test_solicitud_replay_valida_y_rechaza_incoherencias(self) -> None:
        sol = SolicitudReplay(
            correlation_id=self.valid_uuid,
            environment="REPLAY",
            dataset_manifest_hash=self.valid_hash,
            range_start_utc=self.t1,
            range_end_utc=self.t2,
            clock_seed=20260829,
        )
        self.assertTrue(validar_solicitud_replay(sol).exito)

        # Inverted dates
        sol_inv = SolicitudReplay(
            correlation_id=self.valid_uuid,
            environment="REPLAY",
            dataset_manifest_hash=self.valid_hash,
            range_start_utc=self.t2,
            range_end_utc=self.t1,
            clock_seed=20260829,
        )
        self.assertFalse(validar_solicitud_replay(sol_inv).exito)

        # Naive datetime
        sol_naive = SolicitudReplay(
            correlation_id=self.valid_uuid,
            environment="REPLAY",
            dataset_manifest_hash=self.valid_hash,
            range_start_utc=datetime(2026, 8, 29, 9, 30),
            range_end_utc=self.t2,
            clock_seed=20260829,
        )
        self.assertFalse(validar_solicitud_replay(sol_naive).exito)

        # Bad hash
        sol_bad_hash = SolicitudReplay(
            correlation_id=self.valid_uuid,
            environment="REPLAY",
            dataset_manifest_hash="not-a-hash",
            range_start_utc=self.t1,
            range_end_utc=self.t2,
            clock_seed=20260829,
        )
        self.assertFalse(validar_solicitud_replay(sol_bad_hash).exito)

    def test_solicitud_shadow_valida_correctamente(self) -> None:
        sol = SolicitudShadow(
            correlation_id=self.valid_uuid,
            environment="SHADOW",
            source_profile_version="ctrader-demo-v1",
            capabilities_manifest_hash=self.valid_hash,
            expected_demo_account_hash=self.valid_hash,
        )
        self.assertTrue(validar_solicitud_shadow(sol).exito)

    def test_solicitud_importacion_demo_protege_contra_path_traversal(self) -> None:
        sol_ok = SolicitudImportacionDemo(
            correlation_id=self.valid_uuid,
            environment="BROKER_DEMO_OBSERVED",
            staged_copy="export_20260829.json",
            expected_sha256=self.valid_hash,
            adapter_version="demo-adapter-v1",
            expected_demo_account_hash=self.valid_hash,
        )
        self.assertTrue(validar_solicitud_importacion_demo(sol_ok).exito)

        # Malicious staged_copy paths
        for bad_path in ["/etc/passwd", "../tj.db", "sub/file.json", "c:\\boot.ini"]:
            sol_bad = SolicitudImportacionDemo(
                correlation_id=self.valid_uuid,
                environment="BROKER_DEMO_OBSERVED",
                staged_copy=bad_path,
                expected_sha256=self.valid_hash,
                adapter_version="demo-adapter-v1",
                expected_demo_account_hash=self.valid_hash,
            )
            res = validar_solicitud_importacion_demo(sol_bad)
            self.assertFalse(res.exito)
            self.assertEqual("VALIDATION_ERROR", res.error.codigo)

    def test_solicitud_consulta_limita_rango_1_a_200(self) -> None:
        for limit in [1, 50, 200]:
            sol = SolicitudConsulta(
                correlation_id=self.valid_uuid,
                environment="REPLAY",
                view="LIGHTS",
                as_of_event_id=None,
                cursor=None,
                limit=limit,
            )
            self.assertTrue(validar_solicitud_consulta(sol).exito)

        for bad_limit in [0, -1, 201, 1000]:
            sol = SolicitudConsulta(
                correlation_id=self.valid_uuid,
                environment="REPLAY",
                view="LIGHTS",
                as_of_event_id=None,
                cursor=None,
                limit=bad_limit,
            )
            self.assertFalse(validar_solicitud_consulta(sol).exito)

    def test_resumenes_validan_conteos_y_relaciones(self) -> None:
        res_exec = ResumenEjecucion(
            run_id=self.valid_uuid,
            environment="REPLAY",
            final_event_cutoff=self.valid_uuid,
            accepted_event_count=100,
            rejected_event_count=2,
            emitted_signal_count=10,
            opened_simulation_count=5,
            reason_codes=("RUN_COMPLETED",),
        )
        self.assertTrue(validar_resumen_ejecucion(res_exec).exito)

        res_imp = ResumenImportacion(
            import_id=self.valid_uuid,
            environment="BROKER_DEMO_OBSERVED",
            final_event_cutoff=None,
            accepted_count=10,
            rejected_count=1,
            matched_count=8,
            unmatched_count=2,
            reason_codes=("IMPORT_COMPLETED",),
        )
        self.assertTrue(validar_resumen_importacion(res_imp).exito)

        # Inconsistent counts (matched + unmatched > accepted)
        res_imp_bad = ResumenImportacion(
            import_id=self.valid_uuid,
            environment="BROKER_DEMO_OBSERVED",
            final_event_cutoff=None,
            accepted_count=10,
            rejected_count=0,
            matched_count=8,
            unmatched_count=5,  # 8 + 5 = 13 > 10
            reason_codes=(),
        )
        self.assertFalse(validar_resumen_importacion(res_imp_bad).exito)

    def test_documento_vista_valida_hash_de_json_canonico(self) -> None:
        raw_json = b'{"light":"GREEN","reason":"HEALTHY"}'
        expected_hash = hashlib.sha256(raw_json).hexdigest()

        doc_ok = DocumentoVistaV1(
            schema_id="sistema-luces/signal-v1",
            document_hash=expected_hash,
            canonical_json_utf8=raw_json,
        )
        self.assertTrue(validar_documento_vista(doc_ok).exito)

        doc_bad_hash = DocumentoVistaV1(
            schema_id="sistema-luces/signal-v1",
            document_hash="f" * 64,
            canonical_json_utf8=raw_json,
        )
        self.assertFalse(validar_documento_vista(doc_bad_hash).exito)


if __name__ == "__main__":
    unittest.main()
