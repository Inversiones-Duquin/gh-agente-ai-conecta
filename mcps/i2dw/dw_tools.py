# -*- coding: utf-8 -*-
"""Herramientas @tool del Data Warehouse — Bearer token directo desde Secrets Manager."""
from typing import Optional
from strands import tool

from i2dw.dw_ventas import (
    get_ventas as _get_ventas, get_ventas_item as _get_ventas_item,
    get_ventas_clientes as _get_ventas_clientes,
    buscar_ventas as _buscar_ventas,
    top_productos as _top_productos, ventas_por_dimension as _ventas_por_dimension,
    ventas_por_medio_pago as _ventas_por_medio_pago,
    ticket_promedio as _ticket_promedio,
    rotacion_inventario as _rotacion_inventario,
    inventario_dias as _inventario_dias,
    comparar_ventas as _comparar_ventas,
    comparar_productos as _comparar_productos,
)
from i2dw.dw_productos import buscar_productos as _buscar_productos
from i2dw.dw_proveedores import (obtener_reporte_proveedores as _obtener_reporte_proveedores,
                                   buscar_proveedor_por_nombre as _buscar_proveedor_por_nombre,
                                   productos_estancados as _productos_estancados,
                                   reporte_proveedor_top as _reporte_proveedor_top)


# -- @tool wrappers ----------------------------------------------------------

@tool
def dw_buscar_proveedor_por_nombre(nombre: str) -> dict:
    """Busca proveedores por nombre o ID (fuzzy, admin + catalogo plan 007)."""
    return _buscar_proveedor_por_nombre(nombre)

@tool
def dw_get_ventas(fecha_desde: str, fecha_hasta: str, id_co: Optional[int] = None) -> dict:
    """[USO RESTRINGIDO] Datos diarios crudos de ventas. SOLO para analisis detallados dia a dia.
    Para totales usa dw_ventas_por_dimension. NO uses esta para 'cuanto vendimos' o rankings."""
    return _get_ventas(fecha_desde, fecha_hasta, id_co)

@tool
def dw_comparar_ventas(fecha_desde_1: str, fecha_hasta_1: str,
                        fecha_desde_2: str, fecha_hasta_2: str,
                        id_co: Optional[int] = None) -> dict:
    """[SOLO PARA TOTALES CORPORATIVOS] Compara VENTA TOTAL entre dos periodos.
    USA para: 'cuanto crecimos vs mes pasado?', 'como vamos vs año pasado?'.
    Retorna: totales de venta neta y margen + % crecimiento + mejor/peor CENTRO.
    NO USA para comparar PRODUCTOS — para eso existe dw_comparar_productos."""
    return _comparar_ventas(fecha_desde_1, fecha_hasta_1, fecha_desde_2, fecha_hasta_2, id_co)

@tool
def dw_get_ventas_item(id_item: int, fecha_desde: str, fecha_hasta: str,
                        id_co: Optional[int] = None,
                        agrupar_por: str = "documento",
                        orden: str = "desc",
                        ordenar_por: str = "neto") -> dict:
    """[VENTAS DE UN PRODUCTO POR ID] Detalle de ventas de un item.
    id_item: ID numerico del producto (obligatorio).
    agrupar_por: 'documento' (detalle), 'co' (por tienda, incluye inventario) o 'cliente'.
    ordenar_por: 'neto', 'cantidad' o 'fecha'. orden: 'asc' o 'desc'.
    Incluye margen, margen_porcentaje y nombre_co. Si no sabes el id_item, usa dw_buscar_ventas."""
    return _get_ventas_item(id_item, fecha_desde, fecha_hasta, id_co,
                            agrupar_por, orden, ordenar_por)

@tool
def dw_get_ventas_clientes(fecha_desde: str, fecha_hasta: str,
                            id_co: Optional[int] = None,
                            id_cliente: Optional[int] = None,
                            agrupar_por: str = "cliente",
                            orden: str = "desc",
                            ordenar_por: str = "neto") -> dict:
    """Ventas por cliente o por centro.
    agrupar_por: 'cliente' (default) o 'co' (ranking de clientes por tienda).
    ordenar_por: 'neto', 'cantidad' o 'margen'. Incluye nombre_co, margen y margen_porcentaje."""
    return _get_ventas_clientes(fecha_desde, fecha_hasta, id_co, id_cliente,
                                agrupar_por, orden, ordenar_por)

@tool
def dw_ventas_por_medio_pago(fecha_desde: str, fecha_hasta: str,
                               id_co: Optional[int] = None,
                               orden: str = "desc",
                               ordenar_por: str = "neto") -> dict:
    """Ventas agrupadas por medio de pago. Una sola llamada, resultado directo.
    ordenar_por: 'neto' o 'cantidad'. orden: 'asc' o 'desc'.
    USA para: 'como pagan mis clientes?', 'efectivo vs tarjeta?'."""
    return _ventas_por_medio_pago(fecha_desde, fecha_hasta, id_co, orden, ordenar_por)

@tool
def dw_buscar_productos(texto: str, buscar_por: str = "nombre", limite: int = 200) -> dict:
    """[SOLO CATALOGO - NO MUESTRA VENTAS] Busca productos en el catalogo por nombre o referencia.
    Retorna id, descripcion, referencia — pero NO ventas, NO neto, NO margen.
    SOLO para: 'cuantos productos tipo X hay?', 'existe el producto Y?'.
    Para ventas de un producto USA dw_buscar_ventas. Para top productos USA dw_top_productos."""
    return _buscar_productos(texto, buscar_por, limite)

@tool
def dw_obtener_reporte_proveedores(fecha_desde: Optional[str] = None, fecha_hasta: Optional[str] = None,
                                    proveedor_id: Optional[str] = None) -> dict:
    """Reporte completo de proveedor: venta neta, unidades, costo, inventario por producto, tienda y categoria.
    USA para 'como va el proveedor X?', 'informe de HACEB', 'reporte del proveedor 0444'."""
    return _obtener_reporte_proveedores(fecha_desde, fecha_hasta, proveedor_id)

@tool
def dw_buscar_ventas(producto: str, fecha_desde: str, fecha_hasta: str,
                      id_co: Optional[int] = None, limite: int = 5) -> dict:
    """[VENTAS DE UN PRODUCTO] Busca cuanto vendio un producto por nombre. 1 sola llamada.
    USA: 'cuanto vendio X?', 'ventas de Y en junio?', 'como le fue a Z este mes?'.
    NUNCA uses dw_buscar_productos para preguntas de ventas."""
    return _buscar_ventas(producto, fecha_desde, fecha_hasta, id_co, limite)

@tool
def dw_top_productos(limite: int, fecha_desde: str, fecha_hasta: str,
                      id_co: Optional[int] = None, ordenar_por: str = "venta_neta") -> dict:
    """[RANKINGS DE PRODUCTOS] Top N productos mas vendidos en un periodo.
    ordenar_por: 'venta_neta' (default), 'cantidad' o 'costo'.
    USA para: 'top 10 productos', 'los mas vendidos del mes', 'ranking de productos'."""
    return _top_productos(limite, fecha_desde, fecha_hasta, id_co, ordenar_por)

@tool
def dw_ventas_por_dimension(dimension: str, fecha_desde: str, fecha_hasta: str,
                              id_co: Optional[int] = None, limit: int = 20,
                              orden: str = "desc", ordenar_por: str = "neto") -> dict:
    """[HERRAMIENTA UNICA — USA PARA TODO] Ventas agrupadas.
    dimension = QUE agrupar: 'co', 'categoria', 'subcategoria', 'seccion', 'marca', 'proveedor', 'producto', 'ciudad'
    ordenar_por = COMO ordenar: 'neto', 'margen', 'margen_porcentaje', 'cantidad'
    orden = 'desc' (top) o 'asc' (bottom)
    ATENCION: dimension NUNCA es 'margen'. 'margen' es ordenar_por."""
    return _ventas_por_dimension(dimension, fecha_desde, fecha_hasta, id_co, limit, orden, ordenar_por)

@tool
def dw_ticket_promedio(fecha_desde: str, fecha_hasta: str, id_co: Optional[int] = None) -> dict:
    """Ticket promedio diario. Usar para 'cuanto gastan en promedio', 'ticket promedio'."""
    return _ticket_promedio(fecha_desde, fecha_hasta, id_co)

@tool
def dw_rotacion_inventario(fecha_desde: str, fecha_hasta: str,
                            id_co: Optional[int] = None, limite: int = 20) -> dict:
    """[PRODUCTOS MAS/MENOS ROTADOS] Ranking de productos por unidades vendidas.
    Rotacion = cantidad de unidades vendidas. Mas rotacion = mas unidades vendidas.
    USA para: 'productos mas rotados?', 'que productos menos rotan?'."""
    return _rotacion_inventario(fecha_desde, fecha_hasta, id_co, limite)

@tool
def dw_inventario_dias(fecha_desde: str, fecha_hasta: str,
                        id_co: Optional[int] = None, limite: int = 50) -> dict:
    """[ROTACION DE INVENTARIO] Dias de inventario por producto. Control financiero.
    USA para: 'rotacion de inventario', 'dias de inventario', 'productos con sobrestock'.
    NO confundir con dw_rotacion_inventario (ranking por unidades vendidas)."""
    return _inventario_dias(fecha_desde, fecha_hasta, id_co, limite)

@tool
def dw_productos_estancados(proveedor_id: Optional[str] = None, fecha_corte: Optional[str] = None) -> dict:
    """Productos con stock que no han vendido. Usar para 'productos estancados', 'no se vende'."""
    return _productos_estancados(proveedor_id, fecha_corte)

@tool
def dw_reporte_proveedor_top(limite: int, fecha_desde: str, fecha_hasta: str,
                               proveedor_id: str, ordenar_por: str = "cantidad") -> dict:
    """Top productos de un proveedor especifico."""
    return _reporte_proveedor_top(limite, fecha_desde, fecha_hasta, proveedor_id, ordenar_por)

@tool
def dw_comparar_productos(fecha_desde: str, fecha_hasta: str,
                            comparar_con: str, limite: int = 10) -> dict:
    """[PRODUCTOS QUE CRECEN O CAEN] Compara CADA PRODUCTO entre dos periodos. 1 SOLA llamada.
    comparar_con: fecha inicio del periodo anterior (YYYY-MM-DD). Ej: '2026-05-01'.
    Retorna: productos_que_crecieron[] y productos_que_cayeron[] con variacion_pct y neto.
    USA: 'que productos cayeron?', 'cuales crecieron vs mes pasado?'."""
    return _comparar_productos(fecha_desde, fecha_hasta, comparar_con, limite)


DW_TOOLS = [
    dw_get_ventas, dw_comparar_ventas,
    dw_get_ventas_item, dw_get_ventas_clientes, dw_ventas_por_medio_pago,
    dw_buscar_productos,
    dw_obtener_reporte_proveedores,
    dw_buscar_ventas, dw_top_productos, dw_ventas_por_dimension,
    dw_buscar_proveedor_por_nombre,
    dw_ticket_promedio, dw_rotacion_inventario, dw_inventario_dias,
    dw_productos_estancados, dw_reporte_proveedor_top,
    dw_comparar_productos,
]
