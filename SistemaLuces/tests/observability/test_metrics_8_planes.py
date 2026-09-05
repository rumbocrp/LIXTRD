"""Pruebas del Cálculo de Métricas en los 8 Planos y Manejo de Nulls (SPEC-001 §6.7, CA-22)."""

from datetime import datetime, timedelta, timezone
import unittest

from sistema_luces.domain.metric import PLANOS_METRICOS_PERMITIDOS, SnapshotMetricoV1
from sistema_luces.observability.metrics import CalculadorMetricas8Planos


class TestMetricas8Planos(unittest.TestCase):
    """Verifica la generación de snapshots para los 8 planos y la regla de null con reason code."""

    def setUp(self) -> None:
        self.calculador = CalculadorMetricas8Planos()
        self.t0 = datetime(2026, 8, 29, 14, 30, 0, tzinfo=timezone.utc)
        self.t1 = datetime(2026, 8, 29, 21, 0, 0, tzinfo=timezone.utc)

    def test_todos_los_8_planos_son_generados(self) -> None:
        snapshots = self.calculador.calcular_snapshots(
            range_start_utc=self.t0,
            range_end_utc=self.t1,
            ny_session_date="2026-08-29",
            environment="REPLAY",
            eventos=[],
        )
        planos_generados = {s.metric_plane for s in snapshots}
        self.assertEqual(PLANOS_METRICOS_PERMITIDOS, planos_generados)

    def test_metricas_no_computables_retornan_null_con_reason_code_ca22(self) -> None:
        snapshots = self.calculador.calcular_snapshots(
            range_start_utc=self.t0,
            range_end_utc=self.t1,
            ny_session_date="2026-08-29",
            environment="REPLAY",
            eventos=[],
        )
        # Con 0 eventos, métricas de precisión o ratio deben ser null con INSUFFICIENT_OR_UNKNOWN_DATA
        metricas_insuficientes = [s for s in snapshots if s.value_int is None and s.value_ratio_scaled is None]
        self.assertGreater(len(metricas_insuficientes), 0)
        for s in metricas_insuficientes:
            self.assertEqual("INSUFFICIENT_OR_UNKNOWN_DATA", s.dimensions.get("reason_code"))
            self.assertEqual(0, s.raw_count)


if __name__ == "__main__":
    unittest.main()
