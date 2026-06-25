"""Endpoints publicos de health check."""
from dw_core import call_api

def health_check() -> dict:
    """Verifica que la API este en ejecucion."""
    return call_api("GET", "/health")

def health_db() -> dict:
    """Verifica conexion a SQL Server."""
    return call_api("GET", "/health/db")
