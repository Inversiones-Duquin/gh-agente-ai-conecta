# -*- coding: utf-8 -*-
"""Herramientas @tool del Data Warehouse — Bearer token directo desde Secrets Manager."""
from typing import Optional
from strands import tool

from i2dw.dw_health import health_check as _health_check, health_db as _health_db
from i2dw.dw_auth import validate_token as _validate_token
from i2dw.dw_centros import get_centros_all as _get_centros_all
from i2dw.dw_ventas import (get_ventas as _get_ventas, get_ventas_item as _get_ventas_item,
                              get_ventas_clientes as _get_ventas_clientes, get_ventas_mpagos as _get_ventas_mpagos)
from i2dw.dw_productos import (get_productos_paginated as _get_productos_paginated,
                                 get_productos_all as _get_productos_all,
                                 get_criterios_producto as _get_criterios_producto)
from i2dw.dw_proveedores import (obtener_reporte_proveedores as _obtener_reporte_proveedores,
                                   listar_proveedores as _listar_proveedores,
                                   buscar_proveedor_por_nombre as _buscar_proveedor_por_nombre)


# -- @tool wrappers ----------------------------------------------------------

@tool
def dw_health_check() -> dict:
    """Verifica que la API este en ejecucion. Publico."""
    return _health_check()

@tool
def dw_health_db() -> dict:
    """Verifica conexion a SQL Server (i2d_dw). Publico."""
    return _health_db()

@tool
def dw_validate_token() -> dict:
    """Valida PAT, retorna user_id, username, role, session y permisos."""
    return _validate_token()

@tool
def dw_get_centros_all() -> dict:
    """Lista centros de operacion con id_co y nombre. Usar para resolver nombres de tiendas."""
    return _get_centros_all()

@tool
def dw_listar_proveedores() -> dict:
    """Lista proveedores registrados con criterio_mayor_id y nombre."""
    return _listar_proveedores()

@tool
def dw_buscar_proveedor_por_nombre(nombre: str) -> dict:
    """Busca proveedores por nombre o ID (fuzzy, admin + catalogo plan 007)."""
    return _buscar_proveedor_por_nombre(nombre)

@tool
def dw_get_ventas(id_co: int, fecha_desde: str, fecha_hasta: str) -> dict:
    """Ventas diarias x centro. Neto, bruto, subtotal, impuesto, descuento, costo, margen."""
    return _get_ventas(id_co, fecha_desde, fecha_hasta)

@tool
def dw_get_ventas_item(id_co: int, id_item: int, fecha_desde: str, fecha_hasta: str) -> dict:
    """Ventas x producto con cliente y documento (CREDITO/POS/CONSUMIDOR FINAL)."""
    return _get_ventas_item(id_co, id_item, fecha_desde, fecha_hasta)

@tool
def dw_get_ventas_clientes(fecha_desde: str, fecha_hasta: str, id_co: Optional[int] = None,
                           id_cliente: Optional[int] = None) -> dict:
    """Ventas agrupadas x cliente. Fechas requeridas, id_co e id_cliente opcionales."""
    return _get_ventas_clientes(fecha_desde, fecha_hasta, id_co, id_cliente)

@tool
def dw_get_ventas_mpagos(fecha_desde: str, fecha_hasta: str, id_co: Optional[int] = None) -> dict:
    """Ventas x medio de pago (efectivo, tarjetas, etc.)."""
    return _get_ventas_mpagos(fecha_desde, fecha_hasta, id_co)

@tool
def dw_get_productos_paginated(page: int = 1, page_size: int = 50) -> dict:
    """Catalogo paginado. Navegar con has_next/has_previous."""
    return _get_productos_paginated(page, page_size)

@tool
def dw_get_productos_all(id_item: Optional[int] = None) -> dict:
    """Todos los productos sin paginacion. id_item opcional."""
    return _get_productos_all(id_item)

@tool
def dw_get_criterios_producto(id_item: int) -> dict:
    """Criterios de clasificacion (planes 001-007): plan, procedencia, seccion, categoria, etc."""
    return _get_criterios_producto(id_item)

@tool
def dw_obtener_reporte_proveedores(fecha_inicio: Optional[str] = None, fecha_fin: Optional[str] = None,
                                    proveedor_id: Optional[str] = None) -> dict:
    """Reporte ventas/inventario/costo x proveedor (plan 007). ATENCION: mensaje/datos, NO status/data. Si usuario menciona proveedor, USA ESTA HERRAMIENTA."""
    return _obtener_reporte_proveedores(fecha_inicio, fecha_fin, proveedor_id)


DW_TOOLS = [
    dw_health_check, dw_health_db, dw_validate_token,
    dw_get_centros_all,
    dw_listar_proveedores, dw_buscar_proveedor_por_nombre,
    dw_get_ventas, dw_get_ventas_item, dw_get_ventas_clientes, dw_get_ventas_mpagos,
    dw_get_productos_paginated, dw_get_productos_all, dw_get_criterios_producto,
    dw_obtener_reporte_proveedores,
]
