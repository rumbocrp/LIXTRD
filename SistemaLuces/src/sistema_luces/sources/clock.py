"""Reloj de dominio determinista y gestion de sesiones NY con DST (SPEC-001 §5.2.1, §12.1, DM-12, CA-23)."""

from datetime import datetime, time, timezone
import zoneinfo
from typing import Literal

_NY_TZ = zoneinfo.ZoneInfo("America/New_York")


class RelojDominio:
    """Reloj de dominio controlado para simulaciones y replay determinista."""

    def __init__(
        self,
        tiempo_inicial_utc: datetime | None = None,
        clock_seed: int = 20260829,
        tiempo_inicial: datetime | None = None,
    ) -> None:
        self._clock_seed = clock_seed
        t_inicial = tiempo_inicial if tiempo_inicial is not None else tiempo_inicial_utc
        if t_inicial is None:
            self._tiempo_actual_utc = datetime(2026, 8, 29, 13, 30, 0, tzinfo=timezone.utc)
        else:
            if t_inicial.tzinfo is None:
                self._tiempo_actual_utc = t_inicial.replace(tzinfo=timezone.utc)
            else:
                self._tiempo_actual_utc = t_inicial.astimezone(timezone.utc)

    @property
    def clock_seed(self) -> int:
        return self._clock_seed

    def ahora_utc(self) -> datetime:
        """Devuelve el instante actual del dominio en UTC."""
        return self._tiempo_actual_utc

    def avanzar_hasta(self, t_utc: datetime) -> None:
        """Avanza monotonicamente el tiempo de dominio hacia el futuro."""
        if t_utc.tzinfo is None:
            target_utc = t_utc.replace(tzinfo=timezone.utc)
        else:
            target_utc = t_utc.astimezone(timezone.utc)

        if target_utc < self._tiempo_actual_utc:
            raise ValueError(
                f"Clock rollback detectado: no se permite retroceder el reloj de "
                f"{self._tiempo_actual_utc.isoformat()} a {target_utc.isoformat()}"
            )
        self._tiempo_actual_utc = target_utc

    def hora_ny(self) -> datetime:
        """Devuelve la hora actual en zona America/New_York (respetando EDT/EST)."""
        return self._tiempo_actual_utc.astimezone(_NY_TZ)

    def fecha_sesion_ny(self) -> str:
        """Devuelve la fecha actual de la sesion NY en formato YYYY-MM-DD."""
        return self.hora_ny().strftime("%Y-%m-%d")

    def es_fin_de_semana_ny(self) -> bool:
        """Comprueba si en New York es sabado (5) o domingo (6)."""
        return self.hora_ny().weekday() in (5, 6)

    def en_sesion_ny(self) -> bool:
        """Comprueba si el reloj esta dentro del horario regular de sesion NY (09:30 - 16:00, L-V)."""
        if self.es_fin_de_semana_ny():
            return False
        ny_time = self.hora_ny().time()
        return time(9, 30) <= ny_time <= time(16, 0)

    def es_inicio_sesion_ny(self) -> bool:
        """Comprueba si coincide exactamente con la apertura de sesion NY (09:30)."""
        if self.es_fin_de_semana_ny():
            return False
        return self.hora_ny().time() == time(9, 30)

    def es_cierre_sesion_ny(self) -> bool:
        """Comprueba si coincide exactamente con el cierre de sesion NY (16:00)."""
        if self.es_fin_de_semana_ny():
            return False
        return self.hora_ny().time() == time(16, 0)
