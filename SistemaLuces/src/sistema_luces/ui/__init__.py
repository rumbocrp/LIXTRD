"""Módulo de Interfaz de Usuario Local Loopback 127.0.0.1 (SPEC-001 §10.6, CA-24)."""

from sistema_luces.ui.server import ManejadorServidorLoopback, ServidorLoopback
from sistema_luces.ui.views import render_dashboard_html

__all__ = [
    "ServidorLoopback",
    "ManejadorServidorLoopback",
    "render_dashboard_html",
]
