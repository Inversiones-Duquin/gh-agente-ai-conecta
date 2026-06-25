"""Endpoints de ventas (requieren permisos RBAC)."""
from typing import Optional
from dw_core import call_api, REQUEST_TIMEOUT_SLOW

def get_ventas(id_co: int, fecha_desde: str, fecha_hasta: str) -> dict:
    """Ventas diarias x centro. Neto, bruto, margen, etc."""
    return call_api("GET", "/ventas/", {"id_co": id_co, "fecha_desde": fecha_desde, "fecha_hasta": fecha_hasta},
                    timeout=REQUEST_TIMEOUT_SLOW)

def get_ventas_item(id_co: int, id_item: int, fecha_desde: str, fecha_hasta: str) -> dict:
    """Ventas x producto con cliente y documento."""
    return call_api("GET", "/ventas/item", {"id_co": id_co, "id_item": id_item,
                    "fecha_desde": fecha_desde, "fecha_hasta": fecha_hasta})

def get_ventas_clientes(fecha_desde: str, fecha_hasta: str, id_co: Optional[int] = None,
                        id_cliente: Optional[int] = None) -> dict:
    """Ventas agrupadas x cliente."""
    return call_api("GET", "/ventas/clientes", {"fecha_desde": fecha_desde, "fecha_hasta": fecha_hasta,
                    "id_co": id_co, "id_cliente": id_cliente})

def get_ventas_mpagos(fecha_desde: str, fecha_hasta: str, id_co: Optional[int] = None) -> dict:
    """Ventas x medio de pago."""
    return call_api("GET", "/ventas/mpagos", {"fecha_desde": fecha_desde, "fecha_hasta": fecha_hasta, "id_co": id_co})
