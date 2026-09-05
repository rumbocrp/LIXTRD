"""Modulo de fuentes de mercado, reloj de dominio, replay y cTrader demo read-only (SPEC-001 §5.3, §10.2, WP-03, WP-10)."""

from sistema_luces.sources.clock import RelojDominio
from sistema_luces.sources.ctrader_demo import (
    CAPABILITIES_READ_ONLY_PERMITIDAS,
    AdaptadorCTraderDemoReadOnly,
    MetadatosCuentaCTrader,
    SesionCTraderDemo,
    SolicitudConexionCTrader,
    validar_capacidades_read_only,
    validar_metadatos_cuenta_demo,
)
from sistema_luces.sources.replay import (
    FuenteReplay,
    ResumenFuente,
    SesionReplay,
    SolicitudFuente,
)
from sistema_luces.sources.yahoo_sp500 import (
    AdaptadorYahooSP500,
    SIMBOLO_YAHOO_SP500,
)
from sistema_luces.sources.yahoo_multi_asset import AdaptadorYahooMultiActivo, SIMBOLOS_YAHOO_MONITOR

__all__ = [
    "CAPABILITIES_READ_ONLY_PERMITIDAS",
    "AdaptadorCTraderDemoReadOnly",
    "AdaptadorYahooSP500",
    "AdaptadorYahooMultiActivo",
    "FuenteReplay",
    "MetadatosCuentaCTrader",
    "RelojDominio",
    "ResumenFuente",
    "SesionCTraderDemo",
    "SesionReplay",
    "SolicitudConexionCTrader",
    "SolicitudFuente",
    "SIMBOLO_YAHOO_SP500",
    "SIMBOLOS_YAHOO_MONITOR",
    "validar_capacidades_read_only",
    "validar_metadatos_cuenta_demo",
]
