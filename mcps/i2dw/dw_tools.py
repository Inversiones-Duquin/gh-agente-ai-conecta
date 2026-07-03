# -*- coding: utf-8 -*-
"""Herramientas @tool del Data Warehouse — Bearer token directo desde Secrets Manager."""
from typing import Optional
from strands import tool

from i2dw.dw_health import health_check as _health_check, health_db as _health_db
from i2dw.dw_auth import validate_token as _validate_token
from i2dw.dw_centros import get_centros_all as _get_centros_all
from i2dw.dw_ventas import (
    get_ventas as _get_ventas, get_ventas_item as _get_ventas_item,
    get_ventas_clientes as _get_ventas_clientes, get_ventas_mpagos as _get_ventas_mpagos,
    buscar_ventas as _buscar_ventas, buscar_ventas_por_referencia as _buscar_ventas_por_referencia,
    top_productos as _top_productos, margen_por_dimension as _margen_por_dimension,
    comparar_periodos as _comparar_periodos, ticket_promedio as _ticket_promedio,
    rotacion_inventario as _rotacion_inventario, resumen_ventas as _resumen_ventas,
    comparar_ventas as _comparar_ventas,
)
from i2dw.dw_productos import (get_productos_paginated as _get_productos_paginated,
                                 get_productos_all as _get_productos_all,
                                 get_criterios_producto as _get_criterios_producto,
                                 buscar_productos as _buscar_productos)
from i2dw.dw_proveedores import (obtener_reporte_proveedores as _obtener_reporte_proveedores,
                                   listar_proveedores as _listar_proveedores,
                                   buscar_proveedor_por_nombre as _buscar_proveedor_por_nombre,
                                   productos_estancados as _productos_estancados,
                                   reporte_proveedor_top as _reporte_proveedor_top)


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
def dw_get_ventas(fecha_desde: str, fecha_hasta: str, id_co: Optional[int] = None) -> dict:
    """Ventas diarias. Si no se especifica id_co, retorna TODOS los centros de operacion. Neto, bruto, subtotal, impuesto, descuento, costo, margen."""
    return _get_ventas(fecha_desde, fecha_hasta, id_co)


@tool
def dw_resumen_ventas(fecha_desde: str, fecha_hasta: str, id_co: Optional[int] = None) -> dict:
    """Resumen ejecutivo de ventas con totales sumados. Responde 'Cuanto vendimos hoy/ayer/este mes'.
    Retorna total_neto, total_bruto, total_costo, total_margen, margen_porcentual, total_descuento,
    total_impuesto y centros_reportados. Usa esta herramienta cuando el usuario pregunte por el total
    de ventas sin pedir desglose por centro o producto."""
    return _resumen_ventas(fecha_desde, fecha_hasta, id_co)


@tool
def dw_comparar_ventas(fecha_desde_1: str, fecha_hasta_1: str,
                        fecha_desde_2: str, fecha_hasta_2: str,
                        id_co: Optional[int] = None) -> dict:
    """Compara dos periodos de ventas con diferencias y % de crecimiento.
    Args:
        fecha_desde_1, fecha_hasta_1: Periodo actual (ej: este mes).
        fecha_desde_2, fecha_hasta_2: Periodo anterior (ej: mes pasado).
        id_co: Opcional, centro especifico.
    Retorna: venta_neta_actual, venta_neta_anterior, diferencia_neta, crecimiento_neta_pct,
    margen_actual, margen_anterior, diferencia_margen, crecimiento_margen_pct,
    ticket_promedio_actual, ticket_promedio_anterior, centros_reportados.
    Usar para: 'comparame este mes vs el anterior', 'como vamos vs año pasado?',
    'crecimos?', 'que % crecimos?', 'como estuvo junio vs mayo?'."""
    return _comparar_ventas(fecha_desde_1, fecha_hasta_1, fecha_desde_2, fecha_hasta_2, id_co)

@tool
def dw_get_ventas_item(id_item: int, fecha_desde: str, fecha_hasta: str, id_co: Optional[int] = None) -> dict:
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
def dw_buscar_productos(texto: str, buscar_por: str = "nombre", limite: int = 200) -> dict:
    """Busca productos en el catalogo por nombre o referencia. Usar para 'cuantos productos de tipo X', 'productos que contengan Y'."""
    return _buscar_productos(texto, buscar_por, limite)

@tool
def dw_get_criterios_producto(id_item: int) -> dict:
    """Criterios de clasificacion (planes 001-007): plan, procedencia, seccion, categoria, etc."""
    return _get_criterios_producto(id_item)

@tool
def dw_obtener_reporte_proveedores(fecha_inicio: Optional[str] = None, fecha_fin: Optional[str] = None,
                                    proveedor_id: Optional[str] = None) -> dict:
    """Reporte ventas/inventario/costo x proveedor (plan 007). ATENCION: mensaje/datos, NO status/data. Si usuario menciona proveedor, USA ESTA HERRAMIENTA."""
    return _obtener_reporte_proveedores(fecha_inicio, fecha_fin, proveedor_id)


# -- Nuevas herramientas de analisis avanzado --

@tool
def dw_buscar_ventas_por_referencia(referencia: str, fecha_desde: str, fecha_hasta: str,
                                     id_co: Optional[int] = None, limite: int = 100) -> dict:
    """Busca ventas por referencia de producto. Usar cuando el usuario pida buscar por referencia."""
    return _buscar_ventas_por_referencia(referencia, fecha_desde, fecha_hasta, id_co, limite)

@tool
def dw_buscar_ventas(producto: str, fecha_desde: str, fecha_hasta: str,
                      id_co: Optional[int] = None, limite: int = 100) -> dict:
    """Busca ventas por nombre, referencia o ID de producto. Usar cuando el usuario pregunte por un producto especifico."""
    return _buscar_ventas(producto, fecha_desde, fecha_hasta, id_co, limite)

@tool
def dw_top_productos(limite: int, fecha_desde: str, fecha_hasta: str,
                      id_co: Optional[int] = None, ordenar_por: str = "cantidad") -> dict:
    """Top N productos mas vendidos. Usar para 'productos mas vendidos', 'top ventas', rankings."""
    return _top_productos(limite, fecha_desde, fecha_hasta, id_co, ordenar_por)

@tool
def dw_margen_por_dimension(dimension: str, fecha_desde: str, fecha_hasta: str,
                              id_co: Optional[int] = None, limite: int = 50) -> dict:
    """Margen agrupado por categoria/seccion/producto/proveedor. Usar para 'categoria mas rentable', 'margen por seccion'."""
    return _margen_por_dimension(dimension, fecha_desde, fecha_hasta, id_co, limite)

@tool
def dw_comparar_periodos(id_co: int, fecha_desde: str, fecha_hasta: str, comparar_con: str) -> dict:
    """Compara ventas entre dos periodos (ej: este mes vs mes pasado)."""
    return _comparar_periodos(id_co, fecha_desde, fecha_hasta, comparar_con)

@tool
def dw_ticket_promedio(fecha_desde: str, fecha_hasta: str, id_co: Optional[int] = None) -> dict:
    """Ticket promedio diario. Usar para 'cuanto gastan en promedio', 'ticket promedio'."""
    return _ticket_promedio(fecha_desde, fecha_hasta, id_co)

@tool
def dw_rotacion_inventario(fecha_desde: str, fecha_hasta: str,
                            id_co: Optional[int] = None, limite: int = 50) -> dict:
    """Dias de inventario por producto. Usar para 'productos con sobrestock', 'baja rotacion'."""
    return _rotacion_inventario(fecha_desde, fecha_hasta, id_co, limite)

@tool
def dw_productos_estancados(proveedor_id: Optional[str] = None, fecha_corte: Optional[str] = None) -> dict:
    """Productos con stock que no han vendido. Usar para 'productos estancados', 'no se vende'."""
    return _productos_estancados(proveedor_id, fecha_corte)

@tool
def dw_reporte_proveedor_top(limite: int, fecha_inicio: str, fecha_fin: str,
                               proveedor_id: str, ordenar_por: str = "cantidad") -> dict:
    """Top productos de un proveedor especifico."""
    return _reporte_proveedor_top(limite, fecha_inicio, fecha_fin, proveedor_id, ordenar_por)


DW_TOOLS = [
    dw_health_check, dw_health_db, dw_validate_token,
    dw_get_centros_all,
    dw_listar_proveedores, dw_buscar_proveedor_por_nombre,
    dw_get_ventas, dw_resumen_ventas, dw_comparar_ventas,
    dw_get_ventas_item, dw_get_ventas_clientes, dw_get_ventas_mpagos,
    dw_get_productos_paginated, dw_get_productos_all, dw_buscar_productos, dw_get_criterios_producto,
    dw_obtener_reporte_proveedores,
    dw_buscar_ventas, dw_buscar_ventas_por_referencia, dw_top_productos, dw_margen_por_dimension,
    dw_comparar_periodos, dw_ticket_promedio, dw_rotacion_inventario,
    dw_productos_estancados, dw_reporte_proveedor_top,
]
