"""Construcción de Dataset Causal y Matrices de Aprendizaje (WP-06)."""

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
from typing import Any, Sequence
import uuid

from sistema_luces.cases.builder import CasoV1
from sistema_luces.domain.error import ErrorDominio
from sistema_luces.domain.event import canonical_json_bytes
from sistema_luces.domain.result import Resultado, exito, fallo
from sistema_luces.learning.labels import EtiquetaV1


@dataclass(frozen=True)
class MuestraAprendizajeV1:
    case_id: str
    timestamp_utc: datetime
    features: dict[str, Any]
    feature_vector: tuple[float, ...]
    label_long_outcome: str
    label_long_binary: int  # 1 si TAKE_PROFIT, 0 en otro caso
    label_short_outcome: str
    label_short_binary: int  # 1 si TAKE_PROFIT, 0 en otro caso
    realized_points_long: int
    realized_points_short: int


@dataclass(frozen=True)
class DatasetCausalV1:
    dataset_id: str
    feature_names: tuple[str, ...]
    n_samples: int
    X: tuple[tuple[float, ...], ...]
    y_long: tuple[int, ...]
    y_short: tuple[int, ...]
    sample_timestamps_utc: tuple[datetime, ...]
    case_ids: tuple[str, ...]
    feature_set_version: str
    dataset_manifest_hash: str
    created_at_utc: datetime


class ConstructorDatasetCausal:
    """Combina Casos V1 y Etiquetas V1 maduras para formar matrices de entrenamiento causales."""

    def construir_dataset(
        self,
        casos: Sequence[CasoV1],
        etiquetas_long: Sequence[EtiquetaV1],
        etiquetas_short: Sequence[EtiquetaV1],
        feature_keys: Sequence[str] | None = None,
        feature_set_version: str = "features-v1",
        dataset_id: str | None = None,
    ) -> Resultado[DatasetCausalV1]:
        map_casos = {c.case_id: c for c in casos}
        map_long = {e.case_id: e for e in etiquetas_long if e.direction == "LONG"}
        map_short = {e.case_id: e for e in etiquetas_short if e.direction == "SHORT"}

        # Identificar casos que tienen ambas etiquetas maduras
        valid_case_ids: list[str] = []
        for cid, caso in map_casos.items():
            if not caso.eligible_for_signal:
                continue
            eti_l = map_long.get(cid)
            eti_s = map_short.get(cid)
            if eti_l and eti_s and eti_l.status == "MATURE" and eti_s.status == "MATURE":
                valid_case_ids.append(cid)

        # Ordenar por timestamp
        valid_case_ids.sort(key=lambda cid: map_casos[cid].market_event_cutoff)

        if not valid_case_ids:
            return fallo(
                ErrorDominio(
                    codigo="INSUFFICIENT_OR_UNKNOWN_DATA",
                    mensaje_seguro="No hay muestras validas con casos y etiquetas maduras",
                    reintentable=False,
                    correlation_id="",
                    detalles={},
                )
            )

        # Determinar claves de features
        if feature_keys is not None:
            names = tuple(feature_keys)
        else:
            first_case = map_casos[valid_case_ids[0]]
            keys = [k for k in first_case.feature_snapshot.keys() if k != "feature_snapshot_hash"]
            names = tuple(sorted(keys))

        x_rows: list[tuple[float, ...]] = []
        y_l_list: list[int] = []
        y_s_list: list[int] = []
        ts_list: list[datetime] = []
        cids_list: list[str] = []

        for cid in valid_case_ids:
            caso = map_casos[cid]
            eti_l = map_long[cid]
            eti_s = map_short[cid]

            vec: list[float] = []
            for k in names:
                val = caso.feature_snapshot.get(k)
                if val is None:
                    vec.append(0.0)
                elif isinstance(val, (int, float)):
                    vec.append(float(val))
                else:
                    vec.append(0.0)

            x_rows.append(tuple(vec))
            y_l_list.append(1 if eti_l.outcome == "TAKE_PROFIT" else 0)
            y_s_list.append(1 if eti_s.outcome == "TAKE_PROFIT" else 0)
            ts_list.append(caso.market_event_cutoff)
            cids_list.append(cid)

        actual_id = dataset_id or str(uuid.uuid4())
        now_utc = datetime.now(timezone.utc)

        manifest_dict = {
            "dataset_id": actual_id,
            "feature_set_version": feature_set_version,
            "feature_names": list(names),
            "n_samples": len(x_rows),
            "first_sample_utc": ts_list[0].isoformat(),
            "last_sample_utc": ts_list[-1].isoformat(),
        }
        manifest_hash = hashlib.sha256(canonical_json_bytes(manifest_dict)).hexdigest()

        dataset = DatasetCausalV1(
            dataset_id=actual_id,
            feature_names=names,
            n_samples=len(x_rows),
            X=tuple(x_rows),
            y_long=tuple(y_l_list),
            y_short=tuple(y_s_list),
            sample_timestamps_utc=tuple(ts_list),
            case_ids=tuple(cids_list),
            feature_set_version=feature_set_version,
            dataset_manifest_hash=manifest_hash,
            created_at_utc=now_utc,
        )

        return exito(dataset)
