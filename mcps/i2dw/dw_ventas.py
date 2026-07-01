"""Endpoints de ventas (requieren permisos RBAC)."""
from typing import Optional
from i2dw.dw_core import call_api, REQUEST_TIMEOUT_SLOW

def get_ventas(id_co: int, fecha_desde: str, fecha_hasta: str) -> dict:
    """Ventas diarias x centro."""
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

# -- Nuevos modos de ventas --

def buscar_ventas(producto: str, fecha_desde: str, fecha_hasta: str,
                  id_co: Optional[int] = None, limite: int = 100) -> dict:
    """Busca ventas por nombre, referencia o ID de producto."""
    return call_api("GET", "/ventas/", {"q": producto, "fecha_desde": fecha_desde,
                    "fecha_hasta": fecha_hasta, "id_co": id_co, "limit": limite})

def buscar_ventas_por_referencia(referencia: str, fecha_desde: str, fecha_hasta: str,
                                  id_co: Optional[int] = None, limite: int = 100) -> dict:
    """Busca ventas por referencia exacta/parcial de producto."""
    return call_api("GET", "/ventas/", {"referencia": referencia, "fecha_desde": fecha_desde,
                    "fecha_hasta": fecha_hasta, "id_co": id_co, "limit": limite})

def top_productos(limite: int, fecha_desde: str, fecha_hasta: str,
                  id_co: Optional[int] = None, ordenar_por: str = "cantidad") -> dict:
    """Top N productos mas vendidos en un periodo."""
    return call_api("GET", "/ventas/", {"top": limite, "fecha_desde": fecha_desde,
                    "fecha_hasta": fecha_hasta, "id_co": id_co, "ordenar_por": ordenar_por})

def margen_por_dimension(dimension: str, fecha_desde: str, fecha_hasta: str,
                          id_co: Optional[int] = None, limite: int = 50) -> dict:
    """Margen agrupado por categoria, seccion, producto o proveedor."""
    return call_api("GET", "/ventas/", {"agrupar_por": dimension, "fecha_desde": fecha_desde,
                    "fecha_hasta": fecha_hasta, "id_co": id_co, "limit": limite})

def comparar_periodos(id_co: int, fecha_desde: str, fecha_hasta: str, comparar_con: str) -> dict:
    """Compara ventas entre dos periodos."""
    return call_api("GET", "/ventas/", {"id_co": id_co, "fecha_desde": fecha_desde,
                    "fecha_hasta": fecha_hasta, "comparar_con": comparar_con}, timeout=REQUEST_TIMEOUT_SLOW)

def ticket_promedio(fecha_desde: str, fecha_hasta: str, id_co: Optional[int] = None) -> dict:
    """Ticket promedio diario."""
    return call_api("GET", "/ventas/", {"modo": "ticket", "fecha_desde": fecha_desde,
                    "fecha_hasta": fecha_hasta, "id_co": id_co})

def rotacion_inventario(fecha_desde: str, fecha_hasta: str,
                         id_co: Optional[int] = None, limite: int = 50) -> dict:
    """Dias de inventario por producto."""
    return call_api("GET", "/ventas/", {"modo": "rotacion", "fecha_desde": fecha_desde,
                    "fecha_hasta": fecha_hasta, "id_co": id_co, "limit": limite})
