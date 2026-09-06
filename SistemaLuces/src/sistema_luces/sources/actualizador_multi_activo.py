"""Servicio de polling multi-activo que actualiza los proyectores con datos en vivo de Yahoo Finance.

Este servicio consulta periódicamente los precios de cada instrumento (US500, XAUUSD, TSLA, AAPL)
y alimenta los proyectores correspondientes para que el dashboard muestre datos actualizados.
"""

from __future__ import annotations

import threading
import time
from datetime import datetime, timezone
from typing import Dict, Any, Optional
import logging

from sistema_luces.config.multi_asset_config import (
    CONFIGURACION_INSTRUMENTOS,
    INSTRUMENTOS_PERMITIDOS,
    obtener_config_instrumento,
)
from sistema_luces.domain.event import SobreEventoV1, compute_payload_hash
from sistema_luces.observability.projections import ProyectorVistas

import yfinance as yf

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ActualizadorMultiActivo:
    """Servicio que hace polling de Yahoo Finance para múltiples activos y actualiza proyectores."""
    
    def __init__(
        self,
        proyectores: Dict[str, ProyectorVistas],
        intervalo_segundos: float = 5.0,
    ) -> None:
        """
        Args:
            proyectores: Diccionario de proyectores por instrumento
            intervalo_segundos: Frecuencia de actualización (default 5 segundos)
        """
        self.proyectores = proyectores
        self.intervalo = intervalo_segundos
        self._ejecutando = False
        self._hilo: Optional[threading.Thread] = None
        self._ultimo_error: Dict[str, str] = {}
        
    def iniciar(self) -> None:
        """Inicia el hilo de polling en background."""
        if self._ejecutando:
            logger.warning("El actualizador ya está en ejecución")
            return
            
        self._ejecutando = True
        self._hilo = threading.Thread(target=self._bucle_polling, daemon=True)
        self._hilo.start()
        logger.info(f"Actualizador multi-activo iniciado (intervalo={self.intervalo}s)")
        
    def detener(self) -> None:
        """Detiene el hilo de polling."""
        self._ejecutando = False
        if self._hilo and self._hilo.is_alive():
            self._hilo.join(timeout=5.0)
        logger.info("Actualizador multi-activo detenido")
        
    def _bucle_polling(self) -> None:
        """Bucle principal que consulta Yahoo Finance y actualiza proyectores."""
        while self._ejecutando:
            try:
                self._actualizar_todos_activos()
            except Exception as e:
                logger.error(f"Error en bucle de polling: {e}")
            
            # Dormir intervalo
            for _ in range(int(self.intervalo * 10)):
                if not self._ejecutando:
                    break
                time.sleep(0.1)
                
    def _actualizar_todos_activos(self) -> None:
        """Consulta Yahoo Finance para cada activo y actualiza su proyector."""
        ahora_utc = datetime.now(timezone.utc)
        
        for instrumento in INSTRUMENTOS_PERMITIDOS:
            try:
                config = obtener_config_instrumento(instrumento)
                # InstrumentoConfig es un dataclass, acceder por atributo, no por clave
                simbolo_yahoo = config.simbolo_yahoo
                
                # Obtener datos de Yahoo Finance
                ticker = yf.Ticker(simbolo_yahoo)
                data = ticker.history(period="1d", interval="1m", timeout=8)
                
                if data.empty:
                    logger.warning(f"{instrumento}: Sin datos de Yahoo (mercado cerrado?)")
                    continue
                    
                # Extraer último precio
                ultimo_cierre = float(data["Close"].iloc[-1])
                ultimo_volumen = int(data["Volume"].iloc[-1])
                timestamp_index = data.index[-1]
                
                # Asegurar timezone UTC
                if timestamp_index.tzinfo is None:
                    timestamp_index = timestamp_index.replace(tzinfo=timezone.utc)
                else:
                    timestamp_index = timestamp_index.astimezone(timezone.utc)
                
                # Crear evento sintético para alimentar el proyector
                evento = self._crear_evento_mercado(
                    instrumento=instrumento,
                    simbolo_yahoo=simbolo_yahoo,
                    precio=ultimo_cierre,
                    volumen=ultimo_volumen,
                    timestamp=timestamp_index,
                    recibido_en=ahora_utc,
                )
                
                # Actualizar proyector
                resultado = self.proyectores[instrumento].actualizar_desde_evento(evento)
                
                if resultado.exito:
                    logger.debug(f"{instrumento}: Actualizado a {ultimo_cierre:.2f}")
                else:
                    logger.error(f"{instrumento}: Error al actualizar proyector - {resultado.error.mensaje_seguro}")
                    
            except Exception as e:
                error_msg = f"{type(e).__name__}: {str(e)}"
                self._ultimo_error[instrumento] = error_msg
                logger.error(f"{instrumento}: Error en polling - {error_msg}")
    
    def _crear_evento_mercado(
        self,
        instrumento: str,
        simbolo_yahoo: str,
        precio: float,
        volumen: int,
        timestamp: datetime,
        recibido_en: datetime,
    ) -> SobreEventoV1:
        """Crea un evento de mercado válido para alimentar el proyector."""
        import uuid
        
        # Escalar precio (2 decimales para la mayoría de instrumentos)
        precio_escala = 100
        precio_scaled = int(precio * precio_escala)
        
        payload = {
            "provider": "Yahoo Finance",
            "provider_symbol": simbolo_yahoo,
            "instrument": instrumento,
            "price_scale": precio_escala,
            "last_price_scaled": precio_scaled,
            "day_volume": volumen,
            "source_timestamp_utc": timestamp.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            "received_at_utc": recibido_en.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            "market_state": "REGULAR",
            "transport": "REST_POLLING",
            "data_granularity": "1m",
            "quote_status": "REAL_TIME",
        }
        
        event_id = str(uuid.uuid4())
        correlation_id = str(uuid.uuid4())
        
        return SobreEventoV1(
            event_id=event_id,
            event_type="QUOTE_TICK",
            schema_version=1,
            occurred_at_utc=timestamp,
            received_at_utc=recibido_en,
            persisted_at_utc=None,
            source="yahoo_polling",
            environment="SHADOW",
            source_account_id_hash=None,
            instrument=instrumento,
            symbol_id=simbolo_yahoo,
            source_sequence=int(timestamp.timestamp() * 1000),
            correlation_id=correlation_id,
            causation_id=None,
            payload_hash=compute_payload_hash(payload),
            previous_hash=None,
            payload=payload,
        )


def crear_servicio_actualizacion(
    proyectores: Dict[str, ProyectorVistas],
    intervalo: float = 5.0,
) -> ActualizadorMultiActivo:
    """Factory para crear el servicio de actualización."""
    return ActualizadorMultiActivo(proyectores=proyectores, intervalo_segundos=intervalo)
