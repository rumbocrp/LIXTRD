"""Configuración multi-activo para el Sistema de Luces - Fase 1.

Define los 4 activos principales con sus símbolos Yahoo, perfiles y configuración específica.
"""

from dataclasses import dataclass
from typing import Dict, FrozenSet, Optional


@dataclass(frozen=True)
class InstrumentoConfig:
    """Configuración por instrumento del Sistema de Luces."""
    
    simbolo_interno: str  # Ej: US500, XAUUSD, TSLA, AAPL
    simbolo_yahoo: str    # Ej: ^GSPC, GC=F, TSLA, AAPL
    nombre_mostrar: str   # Nombre para UI
    categoria: str        # Indice, Forex/Commodity, Accion
    moneda: str           # USD, EUR, etc.
    precio_scale: int     # Escala de precios (100, 1000, etc.)
    tick_size: float      # Tamaño mínimo de movimiento
    lote_min: int         # Lote mínimo operable
    lote_step: int        # Incremento de lote
    lote_max: int         # Lote máximo
    punto_valor: float    # Valor por punto
    economic_ready: bool  # ¿Listo para operativa económica?
    umbrales_luz: tuple[float, float]  # (threshold_red, threshold_green)
    

INSTRUMENTOS_PERMITIDOS: FrozenSet[str] = frozenset({
    "US500",
    "XAUUSD", 
    "TSLA",
    "AAPL",
})

CONFIGURACION_INSTRUMENTOS: Dict[str, InstrumentoConfig] = {
    "US500": InstrumentoConfig(
        simbolo_interno="US500",
        simbolo_yahoo="^GSPC",
        nombre_mostrar="S&P 500 (US500)",
        categoria="Indice",
        moneda="USD",
        precio_scale=100,
        tick_size=0.25,
        lote_min=1,
        lote_step=1,
        lote_max=10,
        punto_valor=50.0,
        economic_ready=True,
        umbrales_luz=(35.0, 65.0),
    ),
    "XAUUSD": InstrumentoConfig(
        simbolo_interno="XAUUSD",
        simbolo_yahoo="GC=F",  # Futuro de oro COMEX - proxy para XAUUSD spot
        nombre_mostrar="Oro Spot (XAU/USD)",
        categoria="Commodity",
        moneda="USD",
        precio_scale=10,
        tick_size=0.10,
        lote_min=1,
        lote_step=1,
        lote_max=5,
        punto_valor=100.0,
        economic_ready=False,  # Requiere validación adicional
        umbrales_luz=(30.0, 70.0),  # Umbrales más amplios por volatilidad
    ),
    "TSLA": InstrumentoConfig(
        simbolo_interno="TSLA",
        simbolo_yahoo="TSLA",
        nombre_mostrar="Tesla Inc. (TSLA)",
        categoria="Accion",
        moneda="USD",
        precio_scale=100,
        tick_size=0.01,
        lote_min=1,
        lote_step=1,
        lote_max=20,
        punto_valor=1.0,
        economic_ready=False,  # Requiere modelo específico
        umbrales_luz=(25.0, 75.0),  # High-beta: umbrales más extremos
    ),
    "AAPL": InstrumentoConfig(
        simbolo_interno="AAPL",
        simbolo_yahoo="AAPL",
        nombre_mostrar="Apple Inc. (AAPL)",
        categoria="Accion",
        moneda="USD",
        precio_scale=100,
        tick_size=0.01,
        lote_min=1,
        lote_step=1,
        lote_max=20,
        punto_valor=1.0,
        economic_ready=False,  # Requiere modelo específico
        umbrales_luz=(35.0, 65.0),
    ),
}

# Símbolos Yahoo permitidos para validación
SIMBOLOS_YAHOO_VALIDOS: FrozenSet[str] = frozenset({
    "^GSPC",  # S&P 500
    "GC=F",   # Oro futuro COMEX (proxy XAUUSD)
    "TSLA",   # Tesla
    "AAPL",   # Apple
})

def obtener_config_instrumento(simbolo: str) -> Optional[InstrumentoConfig]:
    """Obtiene la configuración de un instrumento por su símbolo interno."""
    return CONFIGURACION_INSTRUMENTOS.get(simbolo)


def validar_simbolo_yahoo(simbolo: str) -> bool:
    """Valida que un símbolo Yahoo sea permitido."""
    return simbolo in SIMBOLOS_YAHOO_VALIDOS


def mapear_yahoo_a_interno(simbolo_yahoo: str) -> Optional[str]:
    """Mapea un símbolo Yahoo a su símbolo interno equivalente."""
    for interno, config in CONFIGURACION_INSTRUMENTOS.items():
        if config.simbolo_yahoo == simbolo_yahoo:
            return interno
    return None
