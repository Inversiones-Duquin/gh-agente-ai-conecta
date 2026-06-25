"""Endpoint de centros de operacion."""
from dw_core import call_api

def get_centros_all() -> dict:
    """Lista centros con id_co y nombre."""
    return call_api("GET", "/centros/all")
