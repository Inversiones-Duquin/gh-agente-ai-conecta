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
    ventas_por_clasificacion as _ventas_por_clasificacion,
    ticket_promedio as _ticket_promedio,
    rotacion_inventario as _rotacion_inventario,
    inventario_dias as _inventario_dias,
    comparar_ventas as _comparar_ventas,
    comparar_productos as _comparar_productos,
)
from i2dw.dw_centros import get_centros_all as _get_centros_all
from i2dw.dw_productos import buscar_productos as _buscar_productos
from i2dw.dw_inventarios import (inventario_por_bodega as _inventario_por_bodega,
                                   inventario_por_centro as _inventario_por_centro,
                                   rotacion_articulos as _rotacion_articulos,
                                   inventario_productos_por_bodega as _inventario_productos_por_bodega)
from i2dw.dw_clasificaciones import get_clasificaciones as _get_clasificaciones
from i2dw.dw_proveedores import (obtener_reporte_proveedores as _obtener_reporte_proveedores,
                                   buscar_proveedor_por_nombre as _buscar_proveedor_por_nombre,
                                   productos_estancados as _productos_estancados,
                                   venta_cero_por_centro as _venta_cero_por_centro,
                                   ranking_proveedores_venta_cero as _ranking_proveedores_venta_cero,
                                   reporte_proveedor_top as _reporte_proveedor_top)


# -- @tool wrappers ----------------------------------------------------------

@tool
def dw_get_centros_all() -> dict:
    """[SOLO PARA BUSCAR IDs] Lista todos los centros de operacion con su id_co y nombre.
    USA SOLO cuando necesites el ID numerico de un CO (ej: '001' para Bazurto).
    NO uses antes de herramientas de ventas — solo para inventarios o consultas que requieran id_co numerico."""
    return _get_centros_all()


@tool
def dw_clasificaciones(tipo: str, q: Optional[str] = None) -> dict:
    """Lista valores de clasificacion disponibles. USA para validar nombres antes de filtrar.
    tipo: 'categorias', 'subcategorias', 'marcas', 'secciones', 'proveedores'
    q: opcional, filtra por texto (ej: 'CONGELADOS').
    Usar cuando el usuario pregunta por una categoria/marca/seccion y necesitas verificar que existe."""
    return _get_clasificaciones(tipo, q)


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
                            ordenar_por: str = "neto",
                            limit: int = 20) -> dict:
    """Ventas por cliente o por centro. USA limit=20 para 'top clientes'.
    agrupar_por: 'cliente' (default) o 'co' (ranking de clientes por tienda).
    ordenar_por: 'neto', 'cantidad' o 'margen'. Incluye nombre_co, margen y margen_porcentaje."""
    return _get_ventas_clientes(fecha_desde, fecha_hasta, id_co, id_cliente,
                                agrupar_por, orden, ordenar_por, limit)

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
    """[SOLO PARA PRODUCTOS] Busca cuanto vendio un PRODUCTO por nombre. 1 sola llamada.
    USA: 'cuanto vendio el ventilador X?', 'ventas de olla a presion?'.
    NO usar para categorias, marcas, secciones o proveedores — para esos usa dw_ventas_por_dimension."""
    return _buscar_ventas(producto, fecha_desde, fecha_hasta, id_co, limite)

@tool
def dw_top_productos(limite: int, fecha_desde: str, fecha_hasta: str,
                      id_co: Optional[int] = None, ordenar_por: str = "venta_neta") -> dict:
    """[RANKINGS DE PRODUCTOS] Top N productos mas vendidos en un periodo.
    ordenar_por: 'venta_neta' (default), 'cantidad' o 'costo'.
    USA para: 'top 10 productos', 'los mas vendidos del mes', 'ranking de productos'."""
    return _top_productos(limite, fecha_desde, fecha_hasta, id_co, ordenar_por)

@tool
def dw_ventas_por_clasificacion(dimension: str, filtro: str, fecha_desde: str,
                                  fecha_hasta: str, id_co: Optional[int] = None,
                                  limit: int = 30, orden: str = "desc",
                                  ordenar_por: str = "venta_neta") -> dict:
    """[VENTAS POR MARCA/CATEGORIA/SECCION] Batching interno: descarga TODOS los productos, acumula totales.
    OBLIGATORIO para: 'cuanto vendio la marca X?', 'productos de categoria Y?', 'marca Disney?'.
    dimension: 'marca', 'categoria', 'subcategoria' o 'seccion'.
    filtro: nombre EXACTO de la clasificacion. USA el nombre que devuelve dw_clasificaciones.
    Ej: dw_clasificaciones('marcas','Disney') -> 'GH DISNEY' -> dw_ventas_por_clasificacion('marca','GH DISNEY',...).
    El TOTAL en el encabezado es la suma REAL de TODOS los productos (el batching garantiza datos completos)."""
    return _ventas_por_clasificacion(dimension, fecha_desde, fecha_hasta, filtro,
                                      id_co, limit, orden, ordenar_por)


@tool
def dw_ventas_por_dimension(dimension: str, fecha_desde: str, fecha_hasta: str,
                              id_co: Optional[int] = None, limit: int = 20,
                              orden: str = "desc", ordenar_por: str = "neto",
                              filtro: Optional[str] = None) -> dict:
    """[HERRAMIENTA UNICA] Ventas agrupadas por 1 o mas dimensiones.
    OBLIGATORIO: llama fecha_actual() PRIMERO si el usuario no especifica fechas.
    Usa ULTIMO_MES_COMPLETO de fecha_actual() como periodo por defecto.
    dimension: 'co', 'categoria', 'subcategoria', 'seccion', 'marca', 'proveedor', 'producto', 'ciudad'
    Combina: 'co,categoria', 'ciudad,categoria', 'co,producto'
    filtro: texto para buscar en resultados (ej: 'CONGELADOS', 'BAZURTO').
    USA filtro cuando pregunten por una entidad especifica dentro de una dimension.
    Ej: 'en que tiendas se vendio CONGELADOS?' -> dimension='co,categoria', filtro='CONGELADOS'
    NO inventes fechas. Sin fecha explicita -> fecha_actual() primero."""
    return _ventas_por_dimension(dimension, fecha_desde, fecha_hasta, id_co, limit, orden, ordenar_por, filtro)

@tool
def dw_ticket_promedio(fecha_desde: str, fecha_hasta: str, id_co: Optional[int] = None) -> dict:
    """Ticket promedio diario. Usar para 'cuanto gastan en promedio', 'ticket promedio'."""
    return _ticket_promedio(fecha_desde, fecha_hasta, id_co)

@tool
def dw_inventario_por_bodega(id_co: Optional[str] = None,
                                limit: int = 30,
                                orden: str = "desc") -> dict:
    """[STOCK POR BODEGA] Cantidad de inventario agrupado por bodega/almacen.
    USA para: 'stock por bodega', 'que bodega tiene mas inventario?', 'inventario en bodegas de CO X'.
    id_co: ID NUMERICO del centro de operacion (ej: '001' para Bazurto).
    Si no sabes el ID, busca primero con dw_get_centros_all.
    NO uses nombres como 'Bazurto', solo IDs numericos."""
    return _inventario_por_bodega(id_co, limit, orden)


@tool
def dw_inventario_productos_por_bodega(nombre_bodega: Optional[str] = None,
                                         id_bodega: Optional[str] = None,
                                         limit: int = 30,
                                         orden: str = "desc") -> dict:
    """[PRODUCTOS EN BODEGA] Stock detallado de productos en una bodega especifica.
    USA para: 'productos en bodega X?', 'stock de BODEGA PRINCIPAL',
    'inventario de bodega BOSQUE HOGAR'.
    nombre_bodega: nombre parcial o completo de la bodega (ej: 'BODEGA PRINCIPAL').
    id_bodega: ID numerico si lo conoces (ej: '90107').
    Usa dw_inventario_por_bodega PRIMERO si no sabes el nombre exacto de la bodega."""
    return _inventario_productos_por_bodega(nombre_bodega, id_bodega, limit, orden)


@tool
def dw_inventario_por_centro(limit: int = 30,
                               orden: str = "desc") -> dict:
    """[STOCK POR TIENDA] Cantidad de inventario agrupado por centro de operacion.
    USA para: 'que tienda tiene mas stock?', 'ranking de inventario por CO', 'inventario por tienda'.
    Retorna ranking de COs con id_co, nombre, ciudad y cantidad total de unidades.
    Los IDs devueltos son los que debes usar para filtrar otras consultas (ej: id_co='001')."""
    return _inventario_por_centro(limit, orden)


@tool
def dw_rotacion_articulos(q: Optional[str] = None,
                            id_co: Optional[str] = None,
                            limit: int = 30,
                            orden: str = "desc") -> dict:
    """[ROTACION POR STOCK REAL] Productos rankeados por cantidad en inventario.
    USA para: 'productos con mas stock?', 'que articulo tiene mayor inventario?',
    'productos con menos existencias?', 'buscar inventario de X'.
    q: busqueda opcional por nombre o referencia del producto.
    id_co: ID NUMERICO del centro (ej: '001' para Bazurto). Usa dw_get_centros_all si no sabes el ID.
    orden='asc' para ver los productos con MENOS stock (riesgo de quiebre)."""
    return _rotacion_articulos(q, id_co, limit, orden)


@tool
def dw_rotacion_inventario(fecha_desde: str, fecha_hasta: str,
                            id_co: Optional[int] = None, limite: int = 20) -> dict:
    """[ROTACION POR VENTAS] Ranking de productos por unidades vendidas.
    USA para: 'productos mas vendidos?', 'que productos mas rotan en ventas?'.
    Muestra unidades vendidas Y venta_neta. NO usar para stock — para eso usa dw_rotacion_articulos."""
    return _rotacion_inventario(fecha_desde, fecha_hasta, id_co, limite)

@tool
def dw_inventario_dias(fecha_desde: str, fecha_hasta: str,
                        id_co: Optional[int] = None, limite: int = 50) -> dict:
    """[ROTACION DE INVENTARIO] Dias de inventario por producto. Control financiero.
    USA para: 'rotacion de inventario', 'dias de inventario', 'productos con sobrestock'.
    NO confundir con dw_rotacion_inventario (ranking por unidades vendidas)."""
    return _inventario_dias(fecha_desde, fecha_hasta, id_co, limite)

@tool
def dw_productos_estancados(proveedor_id: str,
                               dia_periodo_inferior: int = 0,
                               dia_periodo_superior: int = 30,
                               limit: int = 30) -> dict:
    """[PRODUCTOS SIN VENTA] Productos con stock que NO han vendido en N dias. ERP SIESA.
    proveedor_id: REQUERIDO. ID del criterio mayor del proveedor (plan 007).
    Usa dw_buscar_proveedor_por_nombre PRIMERO si no sabes el ID.
    dia_periodo_inferior: minimo de dias sin venta (default 0, usa 30 para 'mas de 1 mes').
    dia_periodo_superior: maximo de dias sin venta (default 30, usa 90 para 'trimestre').
    El encabezado contiene el TOTAL real de productos y stock."""
    return _productos_estancados(proveedor_id, dia_periodo_inferior, dia_periodo_superior, limit)

@tool
def dw_venta_cero_por_centro(proveedor_id: str,
                                dia_periodo_inferior: int = 0,
                                dia_periodo_superior: int = 30) -> dict:
    """[VENTA CERO POR TIENDA] Top 5 tiendas con mas stock sin venta + top 5 productos por tienda.
    Batching interno: recorre todos los productos estancados del proveedor y agrupa por centro.
    proveedor_id: REQUERIDO. ID del criterio mayor. Usa dw_buscar_proveedor_por_nombre primero.
    dia_periodo_inferior/superior: rango de dias sin venta (default 0-30)."""
    return _venta_cero_por_centro(proveedor_id, dia_periodo_inferior, dia_periodo_superior)


@tool
def dw_ranking_proveedores_venta_cero(dia_periodo_inferior: int = 0,
                                        dia_periodo_superior: int = 30,
                                        top_n: int = 10) -> dict:
    """[RANKING PROVEEDORES SIN VENTA] Top N proveedores con mas stock estancado.
    Consulta TODOS los proveedores del indice y rankea por stock sin venta.
    dia_periodo_inferior/superior: rango de dias sin venta (default 0-30).
    ADVERTENCIA: puede ser lento (~30s) porque consulta cada proveedor individualmente."""
    return _ranking_proveedores_venta_cero(dia_periodo_inferior, dia_periodo_superior, top_n)


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
    dw_clasificaciones, dw_get_centros_all,
    dw_get_ventas, dw_comparar_ventas,
    dw_get_ventas_item, dw_get_ventas_clientes, dw_ventas_por_medio_pago,
    dw_buscar_productos,
    dw_obtener_reporte_proveedores,
    dw_buscar_ventas, dw_top_productos, dw_ventas_por_clasificacion, dw_ventas_por_dimension,
    dw_buscar_proveedor_por_nombre,
    dw_ticket_promedio, dw_inventario_por_bodega, dw_inventario_productos_por_bodega,
    dw_inventario_por_centro,
    dw_rotacion_articulos, dw_rotacion_inventario, dw_inventario_dias,
    dw_productos_estancados, dw_venta_cero_por_centro, dw_ranking_proveedores_venta_cero,
    dw_reporte_proveedor_top,
    dw_comparar_productos,
]
