"""Endpoints de catalogo de productos."""
from typing import Optional
from i2dw.dw_core import call_api

def buscar_productos(texto: str, buscar_por: str = "nombre", limite: int = 200) -> dict:
    """Busca productos por nombre o referencia. Usar para 'cuantos productos de tipo X hay'."""
    return call_api("GET", "/productos/", {"q": texto, "buscar_por": buscar_por, "limit": limite})
