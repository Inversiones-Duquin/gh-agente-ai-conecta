"""Endpoints de clasificaciones (planes 003-007)."""
from typing import Optional
from i2dw.dw_core import call_api

def get_clasificaciones(tipo: str, q: Optional[str] = None) -> dict:
    """Lista valores de clasificacion: categorias, subcategorias, marcas, secciones, proveedores.
    tipo: 'categorias', 'subcategorias', 'marcas', 'secciones', 'proveedores'
    q: texto opcional para filtrar por descripcion parcial."""
    return call_api("GET", f"/clasificaciones/{tipo}", {"q": q})
