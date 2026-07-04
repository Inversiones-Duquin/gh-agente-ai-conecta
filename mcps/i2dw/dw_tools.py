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
    producto_mas_vendido as _producto_mas_vendido,
    categoria_top as _categoria_top,
    centros_por_venta as _centros_por_venta,
    comparar_productos as _comparar_productos,
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
    """[USO RESTRINGIDO] Datos diarios crudos de ventas. SOLO para analisis detallados dia a dia.
    Para totales usa dw_resumen_ventas. Para rankings de tiendas usa dw_centros_por_venta.
    Para comparar periodos usa dw_comparar_ventas. NO uses esta para 'cuanto vendimos' o rankings."""
    return _get_ventas(fecha_desde, fecha_hasta, id_co)


@tool
def dw_resumen_ventas(fecha_desde: str, fecha_hasta: str, id_co: Optional[int] = None) -> dict:
    """Total de ventas corporativo. Usa ESTA herramienta para: 'cuanto vendimos?', 'como cerro el mes?',
    'ventas totales de julio?', 'cuanto facturamos ayer?', 'como vamos hoy?'.
    Retorna total_neto, total_costo, total_margen, margen_porcentual, total_descuento, total_impuesto.
    NO uses esta para rankings de tiendas — para eso usa dw_centros_por_venta."""
    return _resumen_ventas(fecha_desde, fecha_hasta, id_co)


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
    """[CATALOGO - NO USAR PARA RANKINGS] Catalogo paginado de productos.
    SOLO para navegar el listado de productos. Para rankings de ventas usa dw_top_productos."""
    return _get_productos_paginated(page, page_size)

@tool
def dw_get_productos_all(id_item: Optional[int] = None) -> dict:
    """[CATALOGO - NO USAR PARA RANKINGS] Lista productos del catalogo (max 500).
    SOLO para buscar informacion de productos especificos por ID.
    Para rankings de productos mas vendidos USA dw_top_productos.
    Para buscar el producto mas vendido USA dw_producto_mas_vendido.
    NUNCA uses esta herramienta para 'top productos', 'los mas vendidos' o rankings."""
    return _get_productos_all(id_item)

@tool
def dw_buscar_productos(texto: str, buscar_por: str = "nombre", limite: int = 200) -> dict:
    """[SOLO CATALOGO - NO MUESTRA VENTAS] Busca productos en el catalogo por nombre o referencia.
    Retorna id, descripcion, referencia — pero NO ventas, NO neto, NO margen.
    SOLO para: 'cuantos productos tipo X hay?', 'existe el producto Y?'.
    Para ventas de un producto USA dw_buscar_ventas. Para top productos USA dw_top_productos."""
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
    """[BUSCAR VENTAS POR CODIGO DE REFERENCIA - TWO-STEP OBLIGATORIO]
    PASO 1: Busca en catalogo -> /productos?q={referencia}&buscar_por=referencia -> obtiene id_item.
    PASO 2: Busca ventas -> /ventas/productos?id_item={id}&fecha_desde=...&fecha_hasta=...
    USA para buscar ventas cuando el usuario da un CODIGO (ej: 'PAN09', 'GA04491').
    PROHIBIDO usar /ventas?referencia= — no es confiable para descubrir productos."""
    return _buscar_ventas_por_referencia(referencia, fecha_desde, fecha_hasta, id_co, limite)

@tool
def dw_buscar_ventas(producto: str, fecha_desde: str, fecha_hasta: str,
                      id_co: Optional[int] = None, limite: int = 5) -> dict:
    """[VENTAS DE UN PRODUCTO - USA ESTA] Busca cuanto vendio un producto por nombre.
    Hace two-step automatico: 1) catalogo -> id_item, 2) ventas agregadas con neto y margen.
    USA PARA: 'cuanto vendio X?', 'ventas de Y en junio?', 'como le fue a Z este mes?'.
    NUNCA uses dw_buscar_productos para preguntas de ventas — esa solo devuelve catalogo sin ventas."""
    return _buscar_ventas(producto, fecha_desde, fecha_hasta, id_co, limite)

@tool
def dw_top_productos(limite: int, fecha_desde: str, fecha_hasta: str,
                      id_co: Optional[int] = None, ordenar_por: str = "cantidad") -> dict:
    """[HERRAMIENTA PRINCIPAL PARA RANKINGS DE PRODUCTOS] Top N productos por ventas en un periodo.
    USA ESTA para: 'top 20 productos mas vendidos', 'productos estrella del mes',
    'ranking de productos', 'los mas vendidos', 'que productos lideran ventas?'.
    NUNCA uses dw_get_productos_all ni dw_get_productos_paginated para rankings — son catalogo, no ventas."""
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


@tool
def dw_producto_mas_vendido(fecha_desde: str, fecha_hasta: str,
                              id_co: Optional[int] = None,
                              proveedor_id: Optional[str] = None) -> dict:
    """Producto #1 con mayor venta neta. Resultado directo (1 fila), sin calculos.
    USA ESTA para: 'producto mas vendido del mes', 'que producto facturo mas?',
    'producto estrella de junio', 'lo mas vendido del proveedor X'.
    Para top N (no solo #1) usa dw_top_productos. NUNCA uses catalogo para esto."""
    return _producto_mas_vendido(fecha_desde, fecha_hasta, id_co, proveedor_id)


@tool
def dw_categoria_top(fecha_desde: str, fecha_hasta: str,
                      id_co: Optional[int] = None,
                      ordenar_por: str = "margen") -> dict:
    """Categoria mas rentable o con mayor venta. Resultado directo, 1 sola llamada.
    ordenar_por: 'margen' para la mas rentable, 'venta_neta' para la de mayor volumen.
    Usar para: 'categoria mas rentable', 'categoria con mas ventas',
    'que categoria dejo mas margen este mes?'."""
    return _categoria_top(fecha_desde, fecha_hasta, id_co, ordenar_por)


@tool
def dw_comparar_productos(fecha_desde: str, fecha_hasta: str,
                            comparar_con: str, limite: int = 10) -> dict:
    """[PRODUCTOS QUE CRECEN O CAEN] Compara CADA PRODUCTO entre dos periodos. 1 SOLA llamada.
    comparar_con: fecha inicio del periodo anterior (YYYY-MM-DD). Ej: '2026-05-01'.
    Retorna: productos_que_crecieron[] y productos_que_cayeron[] con variacion_pct y neto.
    USA ESTA para: 'que productos cayeron?', 'cuales crecieron vs mes pasado?',
    'productos con mayor caida en junio vs mayo', 'comparativa de productos entre periodos'.
    NO confundir con dw_comparar_ventas que compara TOTALES, no productos individuales."""
    return _comparar_productos(fecha_desde, fecha_hasta, comparar_con, limite)


@tool
def dw_centros_por_venta(fecha_desde: str, fecha_hasta: str,
                           orden: str = "desc", limite: int = 5) -> dict:
    """[HERRAMIENTA PRINCIPAL PARA RANKINGS DE TIENDAS] Retorna sedes ordenadas por venta neta.
    La API agrupa, suma y ordena — el resultado son solo N filas exactas, sin calculos del MCP.
    orden='asc' = las que MENOS venden primero. orden='desc' = las que MAS venden primero.
    USA ESTA para: 'que tiendas menos han vendido?', 'top tiendas del mes',
    'cuales son las sedes con menor facturacion?', 'ranking de tiendas por venta',
    'que sede vendio mas?', 'cuales son las 5 tiendas que mas facturaron?'.
    NO uses dw_get_ventas ni dw_resumen_ventas para rankings de tiendas."""
    return _centros_por_venta(fecha_desde, fecha_hasta, orden, limite)


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
    dw_producto_mas_vendido, dw_categoria_top, dw_centros_por_venta,
    dw_comparar_productos,
]
