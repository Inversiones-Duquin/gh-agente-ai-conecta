"""Endpoints de catalogo de productos."""
from typing import Optional
from dw_core import call_api

def get_productos_paginated(page: int = 1, page_size: int = 50) -> dict:
    """Catalogo paginado. Navegar con has_next/has_previous."""
    return call_api("GET", "/productos/", {"page": page, "page_size": page_size})

def get_productos_all(id_item: Optional[int] = None) -> dict:
    """Todos los productos sin paginacion."""
    return call_api("GET", "/productos/all", {"id_item": id_item})

def get_criterios_producto(id_item: int) -> dict:
    """Criterios plan 001-007 de un producto."""
    return call_api("GET", f"/productos/{id_item}")
