"""Particiones Walk-Forward, Purga y Embargo sin Fuga de Datos (SPEC-001 §6.8, CA-26, WP-06)."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Sequence

from sistema_luces.domain.error import ErrorDominio
from sistema_luces.domain.result import Resultado, exito, fallo


@dataclass(frozen=True)
class SolicitudParticionWalkForward:
    n_samples: int
    sample_timestamps_utc: tuple[datetime, ...]
    horizon_seconds: int = 300
    embargo_seconds: int = 300
    n_folds: int = 3
    min_train_samples: int = 40
    correlation_id: str = ""


@dataclass(frozen=True)
class ParticionFoldV1:
    fold_index: int
    train_indices: tuple[int, ...]
    test_indices: tuple[int, ...]
    purged_indices: tuple[int, ...]
    embargoed_indices: tuple[int, ...]
    train_start_utc: datetime
    train_end_utc: datetime
    test_start_utc: datetime
    test_end_utc: datetime


def verificar_cero_fuga(
    train_indices: Sequence[int],
    test_indices: Sequence[int],
    sample_timestamps_utc: Sequence[datetime],
    horizon_seconds: int = 300,
    embargo_seconds: int = 300,
    correlation_id: str = "",
) -> Resultado[bool]:
    """Verifica formalmente que ninguna muestra de train se traslapa con test ni viola el embargo (CA-26)."""
    horizon_delta = timedelta(seconds=horizon_seconds)
    embargo_delta = timedelta(seconds=embargo_seconds)

    test_set = set(test_indices)
    for idx_train in train_indices:
        if idx_train in test_set:
            return fallo(
                ErrorDominio(
                    codigo="VALIDATION_ERROR",
                    mensaje_seguro=f"Fuga de datos detectada: indice {idx_train} presente simultaneamente en train y test",
                    reintentable=False,
                    correlation_id=correlation_id,
                    detalles={"indice": idx_train},
                )
            )

    for idx_test in test_indices:
        t_test_start = sample_timestamps_utc[idx_test]
        t_test_end = t_test_start + horizon_delta

        for idx_train in train_indices:
            t_train_start = sample_timestamps_utc[idx_train]
            t_train_end = t_train_start + horizon_delta

            # Caso 1: Train anterior a Test, pero su horizonte de maduración invade el inicio de test
            if t_train_start <= t_test_start and t_train_end > t_test_start:
                return fallo(
                    ErrorDominio(
                        codigo="VALIDATION_ERROR",
                        mensaje_seguro=(
                            f"Fuga de datos detectada: Muestra train {idx_train} ({t_train_start.isoformat()}) "
                            f"madura en {t_train_end.isoformat()}, traslapando con test {idx_test} ({t_test_start.isoformat()})"
                        ),
                        reintentable=False,
                        correlation_id=correlation_id,
                        detalles={
                            "train_index": idx_train,
                            "test_index": idx_test,
                            "train_horizon_end": t_train_end.isoformat(),
                            "test_start": t_test_start.isoformat(),
                        },
                    )
                )

            # Caso 2: Train posterior a Test, pero se encuentra dentro de la ventana de embargo
            if t_train_start >= t_test_start and t_train_start < (t_test_end + embargo_delta):
                return fallo(
                    ErrorDominio(
                        codigo="VALIDATION_ERROR",
                        mensaje_seguro=(
                            f"Violacion de embargo detectada: Muestra train {idx_train} ({t_train_start.isoformat()}) "
                            f"inicia antes del fin de embargo de test {idx_test} ({(t_test_end + embargo_delta).isoformat()})"
                        ),
                        reintentable=False,
                        correlation_id=correlation_id,
                        detalles={
                            "train_index": idx_train,
                            "test_index": idx_test,
                            "embargo_end": (t_test_end + embargo_delta).isoformat(),
                        },
                    )
                )

    return exito(True)


class GeneradorParticionesWalkForward:
    """Genera particiones walk-forward aplicando purga estricta y embargo de autocorrelación."""

    def generar_folds(self, solicitud: SolicitudParticionWalkForward) -> Resultado[list[ParticionFoldV1]]:
        n = solicitud.n_samples
        if n < solicitud.min_train_samples + solicitud.n_folds:
            return fallo(
                ErrorDominio(
                    codigo="VALIDATION_ERROR",
                    mensaje_seguro=f"Muestras insuficientes ({n}) para {solicitud.n_folds} folds con min_train={solicitud.min_train_samples}",
                    reintentable=False,
                    correlation_id=solicitud.correlation_id,
                    detalles={"n_samples": n},
                )
            )

        timestamps = solicitud.sample_timestamps_utc
        horizon_delta = timedelta(seconds=solicitud.horizon_seconds)
        embargo_delta = timedelta(seconds=solicitud.embargo_seconds)

        test_pool_size = n - solicitud.min_train_samples
        fold_test_size = max(1, test_pool_size // solicitud.n_folds)

        folds: list[ParticionFoldV1] = []

        for f in range(solicitud.n_folds):
            test_start = solicitud.min_train_samples + f * fold_test_size
            test_end = test_start + fold_test_size if f < solicitud.n_folds - 1 else n
            test_indices = tuple(range(test_start, test_end))

            raw_train_candidates = list(range(0, test_start))

            t_test_start = timestamps[test_start]

            # Purga: Excluir muestras de train cuyo horizonte invade test_start
            train_indices_list: list[int] = []
            purged_indices_list: list[int] = []

            for idx in raw_train_candidates:
                t_sample_start = timestamps[idx]
                t_sample_end = t_sample_start + horizon_delta
                if t_sample_end > t_test_start:
                    purged_indices_list.append(idx)
                else:
                    train_indices_list.append(idx)

            train_indices = tuple(train_indices_list)
            purged_indices = tuple(purged_indices_list)
            embargoed_indices: tuple[int, ...] = ()

            if not train_indices:
                return fallo(
                    ErrorDominio(
                        codigo="VALIDATION_ERROR",
                        mensaje_seguro=f"Fold {f} quedo sin muestras de entrenamiento tras la purga",
                        reintentable=False,
                        correlation_id=solicitud.correlation_id,
                        detalles={"fold": f},
                    )
                )

            # Verificar cero fuga antes de retornar
            res_leak = verificar_cero_fuga(
                train_indices=train_indices,
                test_indices=test_indices,
                sample_timestamps_utc=timestamps,
                horizon_seconds=solicitud.horizon_seconds,
                embargo_seconds=solicitud.embargo_seconds,
                correlation_id=solicitud.correlation_id,
            )
            if not res_leak.exito:
                return fallo(res_leak.error)

            fold = ParticionFoldV1(
                fold_index=f,
                train_indices=train_indices,
                test_indices=test_indices,
                purged_indices=purged_indices,
                embargoed_indices=embargoed_indices,
                train_start_utc=timestamps[train_indices[0]],
                train_end_utc=timestamps[train_indices[-1]],
                test_start_utc=timestamps[test_indices[0]],
                test_end_utc=timestamps[test_indices[-1]],
            )
            folds.append(fold)

        return exito(folds)
