"""Motor de Riesgo y Evaluación de Tripwires (SPEC-001 §8, CA-15, CA-16, CA-17, CA-18, DM-12)."""

from datetime import datetime, timezone
import zoneinfo

from sistema_luces.domain.error import ErrorDominio
from sistema_luces.domain.manifest import RiskProfileV1
from sistema_luces.domain.result import Resultado, exito, fallo
from sistema_luces.domain.simulation import SimulacionV1
from sistema_luces.risk.blackout import CalendarioNoticias
from sistema_luces.risk.kill_switch import InterruptorEmergencia

NY_TZ = zoneinfo.ZoneInfo("America/New_York")


class MotorRiesgo:
    """Evalúa propuestas operativas contra la matriz de tripwires y límites versionados."""

    def __init__(
        self,
        profile: RiskProfileV1 | None = None,
        calendario: CalendarioNoticias | None = None,
        interruptor: InterruptorEmergencia | None = None,
    ) -> None:
        self.profile = profile or RiskProfileV1()
        self.calendario = calendario or CalendarioNoticias(
            blackout_minutes=self.profile.news_blackout_minutes
        )
        self.interruptor = interruptor or InterruptorEmergencia()

        self.posiciones_abiertas: list[SimulacionV1] = []
        self.perdida_diaria_realizada_cents: int = 0
        self.aperturas_diarias: int = 0
        self.rachas_perdidas_consecutivas: int = 0
        self.fecha_sesion_ny_actual: str = ""

    def reset_ny_midnight_if_needed(self, now_utc: datetime) -> None:
        """Resetea contadores a la medianoche de America/New_York (DM-12)."""
        ny_time = now_utc.astimezone(NY_TZ)
        fecha_str = ny_time.strftime("%Y-%m-%d")
        if self.fecha_sesion_ny_actual == "":
            self.fecha_sesion_ny_actual = fecha_str
        elif fecha_str != self.fecha_sesion_ny_actual:
            self.fecha_sesion_ny_actual = fecha_str
            self.perdida_diaria_realizada_cents = 0
            self.aperturas_diarias = 0
            self.rachas_perdidas_consecutivas = 0

    def reset_loss_streak_for_test(self) -> None:
        """Auxiliar de prueba para aislar el test de pérdida máxima diaria."""
        self.rachas_perdidas_consecutivas = 0

    def evaluar_propuesta(
        self,
        sim: SimulacionV1,
        now_utc: datetime,
    ) -> Resultado[bool]:
        """Evalúa si una propuesta de simulación cumple con todas las guardias de riesgo."""
        self.reset_ny_midnight_if_needed(now_utc)

        # 1. Invariante CA-18: Kill Switch activo bloquea cualquier apertura
        if self.interruptor.activo:
            return fallo(
                ErrorDominio(
                    codigo="RISK_LIMIT_HIT",
                    mensaje_seguro="Kill switch activo: no se permiten nuevas aperturas",
                    reintentable=False,
                    correlation_id=sim.correlation_id,
                    detalles={"reason": self.interruptor.motivo},
                )
            )

        # 2. Invariante CA-15: Contrato económico completo
        if (
            sim.stop is None
            or sim.target is None
            or sim.planned_entry is None
            or not sim.requested_quantity_simulated
        ):
            return fallo(
                ErrorDominio(
                    codigo="ECONOMIC_CONTRACT_INCOMPLETE",
                    mensaje_seguro="Propuesta rechazada por contrato económico incompleto",
                    reintentable=False,
                    correlation_id=sim.correlation_id,
                    detalles={},
                )
            )

        # 3. Ventana de noticias (Blackout)
        if self.calendario.esta_en_blackout(now_utc):
            return fallo(
                ErrorDominio(
                    codigo="RISK_LIMIT_HIT",
                    mensaje_seguro="Operación bloqueada por ventana de blackout de noticias",
                    reintentable=False,
                    correlation_id=sim.correlation_id,
                    detalles={"reason": "NEWS_BLACKOUT"},
                )
            )

        # 4. Invariante CA-16: Posición única simultánea en US500
        if len(self.posiciones_abiertas) >= self.profile.max_concurrent_positions:
            return fallo(
                ErrorDominio(
                    codigo="RISK_LIMIT_HIT",
                    mensaje_seguro="Propuesta solapada rechazada: límite de 1 posición abierta alcanzado",
                    reintentable=False,
                    correlation_id=sim.correlation_id,
                    detalles={
                        "open_positions": len(self.posiciones_abiertas),
                        "reason": "OVERLAPPING_POSITION",
                    },
                )
            )

        # 5. Invariante CA-17: Riesgo por operación <= USD 50 ($50.00 = 5000 cents)
        distancia_stop = abs(sim.planned_entry - sim.stop)
        # riesgo en USD = (distancia_stop * requested_quantity) / 10000.0
        riesgo_usd = (distancia_stop * sim.requested_quantity_simulated) / 10000.0
        max_riesgo_usd = self.profile.max_risk_per_trade_usd_cents / 100.0
        if riesgo_usd > max_riesgo_usd:
            return fallo(
                ErrorDominio(
                    codigo="RISK_LIMIT_HIT",
                    mensaje_seguro=f"Riesgo por operación (${riesgo_usd:.2f}) excede el límite permitido (${max_riesgo_usd:.2f})",
                    reintentable=False,
                    correlation_id=sim.correlation_id,
                    detalles={"risk_usd": riesgo_usd, "max_allowed": max_riesgo_usd},
                )
            )

        # 6. Invariante CA-17: Pérdida máxima diaria acumulada ($250.00 = 25000 cents)
        if self.perdida_diaria_realizada_cents >= self.profile.max_daily_loss_usd_cents:
            self.interruptor.activar("DAILY_LOSS_LIMIT_HIT", now_utc)
            return fallo(
                ErrorDominio(
                    codigo="RISK_LIMIT_HIT",
                    mensaje_seguro="Límite de pérdida diaria alcanzado ($250). Kill switch activado.",
                    reintentable=False,
                    correlation_id=sim.correlation_id,
                    detalles={"daily_loss_cents": self.perdida_diaria_realizada_cents},
                )
            )

        # 7. Invariante CA-17: Racha de 3 pérdidas consecutivas
        if self.rachas_perdidas_consecutivas >= self.profile.max_consecutive_losses:
            return fallo(
                ErrorDominio(
                    codigo="RISK_LIMIT_HIT",
                    mensaje_seguro=f"Pausa operativa por racha de {self.rachas_perdidas_consecutivas} pérdidas consecutivas",
                    reintentable=False,
                    correlation_id=sim.correlation_id,
                    detalles={"consecutive_losses": self.rachas_perdidas_consecutivas},
                )
            )

        # 8. Invariante CA-17: Máximo de 10 aperturas diarias
        if self.aperturas_diarias >= self.profile.max_daily_openings:
            return fallo(
                ErrorDominio(
                    codigo="RISK_LIMIT_HIT",
                    mensaje_seguro=f"Límite máximo de {self.profile.max_daily_openings} aperturas diarias alcanzado",
                    reintentable=False,
                    correlation_id=sim.correlation_id,
                    detalles={"daily_openings": self.aperturas_diarias},
                )
            )

        return exito(True)

    def registrar_apertura(self, sim: SimulacionV1) -> None:
        self.reset_ny_midnight_if_needed(sim.proposed_at_utc)
        self.posiciones_abiertas.append(sim)
        self.aperturas_diarias += 1

    def registrar_cierre(self, sim: SimulacionV1, pnl_usd_cents: int) -> None:
        cierre_t = sim.closed_at_utc or sim.proposed_at_utc
        self.reset_ny_midnight_if_needed(cierre_t)
        self.posiciones_abiertas = [
            p for p in self.posiciones_abiertas if p.simulation_id != sim.simulation_id
        ]
        if pnl_usd_cents < 0:
            self.perdida_diaria_realizada_cents += abs(pnl_usd_cents)
            self.rachas_perdidas_consecutivas += 1
            if self.perdida_diaria_realizada_cents >= self.profile.max_daily_loss_usd_cents:
                self.interruptor.activar("DAILY_LOSS_LIMIT_HIT", cierre_t)
        else:
            self.rachas_perdidas_consecutivas = 0
