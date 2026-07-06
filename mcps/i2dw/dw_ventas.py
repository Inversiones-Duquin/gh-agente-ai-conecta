"""Endpoints de ventas (requieren permisos RBAC)."""
from typing import Optional
from i2dw.dw_core import call_api, REQUEST_TIMEOUT_SLOW


def get_ventas(fecha_desde: str,
               fecha_hasta: str,
               id_co: Optional[int] = None) -> dict:
    """Ventas diarias. Si no se especifica id_co, retorna todos los centros."""
    return call_api("GET",
                    "/ventas/", {
                        "id_co": id_co,
                        "fecha_desde": fecha_desde,
                        "fecha_hasta": fecha_hasta
                    },
                    timeout=REQUEST_TIMEOUT_SLOW)


def resumen_ventas(fecha_desde: str,
                   fecha_hasta: str,
                   id_co: Optional[int] = None) -> dict:
    """Resumen de ventas con totales sumados listo para responder al usuario.

    Consulta la API del DW, recibe todos los datos, suma las metricas clave
    y entrega un resumen ejecutivo con totales netos, bruto, costo, margen,
    descuento e impuesto. Ideal para preguntas como 'Cuanto vendimos ayer?'
    o 'Cuanto vendimos hoy?'.
    """
    import json, logging
    logger = logging.getLogger("dw-ventas")

    # Usar API agregada por centro: 1 fila por centro, imposible truncar
    params = {
        "agrupar_por": "co",
        "fecha_desde": fecha_desde,
        "fecha_hasta": fecha_hasta,
        "limit": 100
    }
    if id_co:
        params["id_co"] = id_co
    result = call_api("GET", "/ventas/", params, timeout=REQUEST_TIMEOUT_SLOW)

    # Extraer datos del formato de respuesta
    raw_text = result.get("content", [{}])[0].get("text", "[]")
    try:
        data = json.loads(raw_text)
    except (json.JSONDecodeError, TypeError):
        return {
            "status": "error",
            "content": [{
                "text": "No se pudieron procesar los datos de ventas."
            }]
        }

    # La API puede devolver lista directa o dict con clave de datos
    if isinstance(data, dict):
        ventas = data.get("datos", data.get("data", data.get("items", [])))
    elif isinstance(data, list):
        ventas = data
    else:
        ventas = []

    if not ventas:
        return {
            "status":
            "success",
            "content": [{
                "text":
                json.dumps(
                    {
                        "mensaje":
                        "No se encontraron ventas para el periodo consultado.",
                        "periodo": f"{fecha_desde} a {fecha_hasta}",
                        "total_neto": 0,
                        "total_bruto": 0,
                        "total_costo": 0,
                        "total_margen": 0,
                        "total_descuento": 0,
                        "total_impuesto": 0,
                        "centros_reportados": 0
                    },
                    ensure_ascii=False)
            }]
        }

    # Sumar totales desde datos agregados por centro (1 fila por centro)
    total_neto = 0
    total_costo = 0
    total_margen = 0
    total_descuento = 0
    total_impuesto = 0
    centros = set()

    for v in ventas:
        total_neto += float(v.get("neto", 0) or 0)
        total_costo += float(v.get("costo", 0) or 0)
        total_margen += float(v.get("margen", 0) or 0)
        total_descuento += float(v.get("descuento", 0) or 0)
        total_impuesto += float(v.get("impuesto", 0) or 0)
        co = str(v.get("id_grupo") or v.get("grupo") or "")
        if co:
            centros.add(co)

    # Calcular margen porcentual
    margen_pct = round(
        (total_margen / total_neto * 100), 2) if total_neto > 0 else 0

    resumen = {
        "periodo": f"{fecha_desde} a {fecha_hasta}",
        "total_neto": round(total_neto, 2),
        "total_costo": round(total_costo, 2),
        "total_margen": round(total_margen, 2),
        "margen_porcentual": margen_pct,
        "total_descuento": round(total_descuento, 2),
        "total_impuesto": round(total_impuesto, 2),
        "centros_reportados": len(centros),
    }

    logger.info("Resumen de ventas generado: %s", resumen)
    return {
        "status": "success",
        "content": [{
            "text": json.dumps(resumen, ensure_ascii=False)
        }]
    }


def _extraer_totales(result: dict) -> dict:
    """Extrae totales de un resultado ya agregado por centro (agrupar_por=co)."""
    import json as _json
    raw = result.get("content", [{}])[0].get("text", "{}")
    try:
        data = _json.loads(raw)
    except (_json.JSONDecodeError, TypeError):
        return {
            "total_neto": 0,
            "total_margen": 0,
            "centros": 0,
            "por_centro": {}
        }

    # Si ya es un resumen (viene de resumen_ventas), devolverlo directo
    if "total_neto" in data:
        return data

    # Datos agregados por centro desde agrupar_por=co
    if isinstance(data, dict):
        items = data.get("datos", data.get("data", data.get("items", [])))
    elif isinstance(data, list):
        items = data
    else:
        items = []

    neto_total = margen_total = 0.0
    por_centro = {}
    for v in items:
        n = float(v.get("neto", 0) or 0)
        m = float(v.get("margen", 0) or 0)
        neto_total += n
        margen_total += m
        co = str(
            v.get("id_grupo") or v.get("grupo") or v.get("id_centro_operacion")
            or "")
        if co:
            por_centro[co] = {
                "neto": round(n, 2),
                "margen": round(m, 2),
                "margen_pct": round(v.get("margen_porcentaje", 0) or 0, 2)
            }

    return {
        "total_neto": round(neto_total, 2),
        "total_margen": round(margen_total, 2),
        "centros": len(por_centro),
        "por_centro": por_centro
    }


def comparar_ventas(fecha_desde_1: str,
                    fecha_hasta_1: str,
                    fecha_desde_2: str,
                    fecha_hasta_2: str,
                    id_co: Optional[int] = None) -> dict:
    """Compara dos periodos de ventas: suma, calcula diferencias y porcentajes de crecimiento.

    Args:
        fecha_desde_1, fecha_hasta_1: Periodo actual (ej: este mes).
        fecha_desde_2, fecha_hasta_2: Periodo anterior a comparar (ej: mes pasado).
        id_co: Opcional, centro de operacion especifico.

    Retorna comparacion lista para responder: totales de cada periodo, diferencia absoluta
    y porcentaje de crecimiento para neto, margen, ticket promedio, y centros reportados.
    Usar para: 'comparame este mes contra el anterior', 'como vamos vs año pasado',
    'crecimos?', 'que porcentaje crecimos?', 'como estuvo junio contra mayo?'.
    """
    import json as _json, logging as _logging
    _logger = _logging.getLogger("dw-ventas")

    # Usar API agregada por centro — devuelve una fila por centro, no datos diarios crudos
    params1 = {
        "agrupar_por": "co",
        "fecha_desde": fecha_desde_1,
        "fecha_hasta": fecha_hasta_1,
        "limit": 100
    }
    params2 = {
        "agrupar_por": "co",
        "fecha_desde": fecha_desde_2,
        "fecha_hasta": fecha_hasta_2,
        "limit": 100
    }
    if id_co:
        params1["id_co"] = id_co
        params2["id_co"] = id_co
    r1 = call_api("GET", "/ventas/", params1, timeout=REQUEST_TIMEOUT_SLOW)
    r2 = call_api("GET", "/ventas/", params2, timeout=REQUEST_TIMEOUT_SLOW)

    t1 = _extraer_totales(r1)
    t2 = _extraer_totales(r2)

    def _pct(actual, anterior):
        if anterior and anterior != 0:
            return round(((actual - anterior) / abs(anterior)) * 100, 2)
        return None

    # Comparar centro por centro
    por_centro_comp = []
    todos_centros = set(t1.get("por_centro", {}).keys()) | set(
        t2.get("por_centro", {}).keys())
    for co in sorted(todos_centros):
        c1 = t1.get("por_centro", {}).get(co, {
            "neto": 0,
            "margen": 0,
            "margen_pct": 0
        })
        c2 = t2.get("por_centro", {}).get(co, {
            "neto": 0,
            "margen": 0,
            "margen_pct": 0
        })
        por_centro_comp.append({
            "id_centro":
            co,
            "neto_actual":
            c1["neto"],
            "neto_anterior":
            c2["neto"],
            "diferencia_neta":
            round(c1["neto"] - c2["neto"], 2),
            "crecimiento_pct":
            _pct(c1["neto"], c2["neto"]),
            "margen_actual":
            c1["margen"],
            "margen_anterior":
            c2["margen"],
            "margen_pct_actual":
            c1["margen_pct"],
            "margen_pct_anterior":
            c2["margen_pct"],
        })

    # Ordenar: el que mas crecio primero
    por_centro_comp.sort(key=lambda x: x["crecimiento_pct"]
                         if x["crecimiento_pct"] is not None else -999,
                         reverse=True)
    mejor = por_centro_comp[0] if por_centro_comp else None
    peor = por_centro_comp[-1] if por_centro_comp else None

    comparacion = {
        "periodo_actual":
        f"{fecha_desde_1} a {fecha_hasta_1}",
        "periodo_anterior":
        f"{fecha_desde_2} a {fecha_hasta_2}",
        "venta_neta_actual":
        t1["total_neto"],
        "venta_neta_anterior":
        t2["total_neto"],
        "diferencia_neta":
        round(t1["total_neto"] - t2["total_neto"], 2),
        "crecimiento_neta_pct":
        _pct(t1["total_neto"], t2["total_neto"]),
        "margen_actual":
        t1["total_margen"],
        "margen_anterior":
        t2["total_margen"],
        "diferencia_margen":
        round(t1["total_margen"] - t2["total_margen"], 2),
        "crecimiento_margen_pct":
        _pct(t1["total_margen"], t2["total_margen"]),
        "ticket_promedio_actual":
        round(t1["total_neto"] /
              t1["centros"], 2) if t1.get("centros", 0) > 0 else 0,
        "ticket_promedio_anterior":
        round(t2["total_neto"] /
              t2["centros"], 2) if t2.get("centros", 0) > 0 else 0,
        "centros_reportados":
        t1.get("centros", 0),
        "mejor_centro":
        mejor,
        "peor_centro":
        peor,
        "comparacion_por_centro":
        por_centro_comp,
    }

    _logger.info(
        "Comparacion generada: actual=%s, anterior=%s, crecimiento=%s%%, mejor=%s, peor=%s",
        t1["total_neto"], t2["total_neto"],
        comparacion["crecimiento_neta_pct"],
        mejor["id_centro"] if mejor else "-",
        peor["id_centro"] if peor else "-")
    return {
        "status": "success",
        "content": [{
            "text": _json.dumps(comparacion, ensure_ascii=False)
        }]
    }


def get_ventas_item(id_item: int,
                    fecha_desde: str,
                    fecha_hasta: str,
                    id_co: Optional[int] = None) -> dict:
    """Ventas x producto con cliente y documento."""
    return call_api(
        "GET", "/ventas/item", {
            "id_co": id_co,
            "id_item": id_item,
            "fecha_desde": fecha_desde,
            "fecha_hasta": fecha_hasta
        })


def get_ventas_clientes(fecha_desde: str,
                        fecha_hasta: str,
                        id_co: Optional[int] = None,
                        id_cliente: Optional[int] = None) -> dict:
    """Ventas agrupadas x cliente."""
    return call_api(
        "GET", "/ventas/clientes", {
            "fecha_desde": fecha_desde,
            "fecha_hasta": fecha_hasta,
            "id_co": id_co,
            "id_cliente": id_cliente
        })


def get_ventas_mpagos(fecha_desde: str,
                      fecha_hasta: str,
                      id_co: Optional[int] = None) -> dict:
    """Ventas x medio de pago."""
    return call_api("GET", "/ventas/mpagos", {
        "fecha_desde": fecha_desde,
        "fecha_hasta": fecha_hasta,
        "id_co": id_co
    })


# -- Nuevos modos de ventas --


def buscar_ventas(producto: str,
                  fecha_desde: str,
                  fecha_hasta: str,
                  id_co: Optional[int] = None,
                  limite: int = 20) -> dict:
    """Busca ventas de un producto por nombre. UNA sola llamada a /ventas/productos?q=.
    Ideal para 'cuanto vendio X en el periodo Y?'."""
    import json, logging, unicodedata
    logger = logging.getLogger("dw-ventas")

    # Normalizar: quitar acentos para busqueda tolerante ("presión" -> "presion")
    producto = ''.join(
        c for c in unicodedata.normalize('NFD', producto)
        if unicodedata.category(c) != 'Mn'
    )

    params = {
        "fecha_desde": fecha_desde, "fecha_hasta": fecha_hasta,
        "limit": 200, "ordenar_por": "venta_neta"
    }
    if id_co:
        params["id_co"] = id_co

    # Numerico = id_item. Texto = q (busqueda por nombre en la misma tabla)
    if producto.strip().isdigit():
        params["id_item"] = int(producto)
    else:
        params["q"] = producto

    result = call_api("GET", "/ventas/productos", params, timeout=REQUEST_TIMEOUT_SLOW)
    raw = result.get("content", [{}])[0].get("text", "[]")
    try:
        data = json.loads(raw)
        resultados = data if isinstance(data, list) else \
                     data.get("data", data.get("ventas", data.get("items", [])))
    except (json.JSONDecodeError, TypeError):
        resultados = []

    if not resultados:
        return {"status": "success", "content": [{"text": json.dumps({
            "mensaje": f"No se encontraron ventas de '{producto}' en {fecha_desde} a {fecha_hasta}."
        }, ensure_ascii=False)}]}

    # Ya vienen ordenados por venta_neta DESC desde la API
    total_neta = sum(float(r.get("venta_neta", 0) or r.get("neto", 0) or 0)
                     for r in resultados)
    total_und = sum(int(r.get("cant_vendida", 0) or 0) for r in resultados)

    encabezado = (
        f"TOTAL: {len(resultados)} productos de '{producto}' vendieron "
        f"${total_neta:,.0f} ({total_und} unidades) en {fecha_desde} a {fecha_hasta}."
    )

    return {"status": "success", "content": [
        {"text": encabezado},
        {"text": json.dumps({
            "total_venta_neta": round(total_neta, 2),
            "total_unidades": total_und,
            "productos_encontrados": len(resultados),
            "top_productos": resultados[:limite]
        }, ensure_ascii=False)}
    ]}


def buscar_ventas_por_referencia(referencia: str,
                                 fecha_desde: str,
                                 fecha_hasta: str,
                                 id_co: Optional[int] = None,
                                 limite: int = 100) -> dict:
    """Busca ventas por referencia de producto. Una sola llamada a /ventas/productos?referencia=."""
    return call_api("GET", "/ventas/productos",
                    {"referencia": referencia, "fecha_desde": fecha_desde,
                     "fecha_hasta": fecha_hasta, "id_co": id_co, "limit": limite},
                    timeout=REQUEST_TIMEOUT_SLOW)


def top_productos(limite: int,
                  fecha_desde: str,
                  fecha_hasta: str,
                  id_co: Optional[int] = None,
                  ordenar_por: str = "venta_neta") -> dict:
    """Top N productos mas vendidos. Usa /ventas/productos?limit=N ya ordenado por venta_neta."""
    return call_api("GET",
                    "/ventas/productos", {
                        "fecha_desde": fecha_desde,
                        "fecha_hasta": fecha_hasta,
                        "id_co": id_co,
                        "ordenar_por": ordenar_por,
                        "limit": limite
                    },
                    timeout=REQUEST_TIMEOUT_SLOW)


def ventas_por_dimension(dimension: str,
                         fecha_desde: str,
                         fecha_hasta: str,
                         id_co: Optional[int] = None,
                         limit: int = 20,
                         orden: str = "desc",
                         ordenar_por: str = "neto") -> dict:
    """Ventas agrupadas por dimension. Una sola llamada, resultado directo.
    dimension: 'categoria', 'seccion', 'marca', 'proveedor', 'producto', 'co'
    orden: 'asc' (menor primero) o 'desc' (mayor primero)
    ordenar_por: 'neto', 'margen', 'margen_porcentaje', 'cantidad'
    Ej: categoria mas rentable -> dimension='categoria', ordenar_por='margen'
        tiendas que menos venden -> dimension='co', orden='asc'"""
    return call_api("GET",
                    "/ventas/", {
                        "agrupar_por": dimension,
                        "fecha_desde": fecha_desde,
                        "fecha_hasta": fecha_hasta,
                        "id_co": id_co,
                        "limit": limit,
                        "orden": orden,
                        "ordenar_por_agrupado": ordenar_por,
                    },
                    timeout=REQUEST_TIMEOUT_SLOW)


def ventas_por_medio_pago(fecha_desde: str,
                          fecha_hasta: str,
                          id_co: Optional[int] = None,
                          orden: str = "desc",
                          ordenar_por: str = "neto") -> dict:
    """Ventas agrupadas por medio de pago. Una sola llamada.
    ordenar_por: 'neto', 'cantidad'. orden: 'asc' o 'desc'."""
    return call_api("GET",
                    "/ventas/mpagos", {
                        "fecha_desde": fecha_desde,
                        "fecha_hasta": fecha_hasta,
                        "id_co": id_co,
                        "orden": orden,
                        "ordenar_por": ordenar_por,
                    },
                    timeout=REQUEST_TIMEOUT_SLOW)


def comparar_periodos(id_co: int, fecha_desde: str, fecha_hasta: str,
                      comparar_con: str) -> dict:
    """Compara ventas entre dos periodos."""
    return call_api("GET",
                    "/ventas/", {
                        "id_co": id_co,
                        "fecha_desde": fecha_desde,
                        "fecha_hasta": fecha_hasta,
                        "comparar_con": comparar_con
                    },
                    timeout=REQUEST_TIMEOUT_SLOW)


def ticket_promedio(fecha_desde: str,
                    fecha_hasta: str,
                    id_co: Optional[int] = None) -> dict:
    """Ticket promedio diario."""
    return call_api("GET",
                    "/ventas/", {
                        "modo": "ticket",
                        "fecha_desde": fecha_desde,
                        "fecha_hasta": fecha_hasta,
                        "id_co": id_co
                    },
                    timeout=REQUEST_TIMEOUT_SLOW)


def rotacion_inventario(fecha_desde: str,
                        fecha_hasta: str,
                        id_co: Optional[int] = None,
                        limite: int = 50) -> dict:
    """Dias de inventario por producto."""
    return call_api("GET",
                    "/ventas/", {
                        "modo": "rotacion",
                        "fecha_desde": fecha_desde,
                        "fecha_hasta": fecha_hasta,
                        "id_co": id_co,
                        "limit": limite
                    },
                    timeout=REQUEST_TIMEOUT_SLOW)


# -- Endpoints optimizados: 1 llamada, resultado directo, sin calculos --


def producto_mas_vendido(fecha_desde: str,
                         fecha_hasta: str,
                         id_co: Optional[int] = None,
                         proveedor_id: Optional[str] = None) -> dict:
    """Producto con mayor venta neta en un periodo. Una sola llamada, resultado directo.
    Usa /ventas/productos?limit=1 que ordena por venta_neta DESC.
    Opcional: filtrar por id_co o proveedor_id."""
    params = {
        "fecha_desde": fecha_desde,
        "fecha_hasta": fecha_hasta,
        "limit": 1
    }
    if id_co:
        params["id_co"] = id_co
    if proveedor_id:
        params["proveedor_id"] = proveedor_id
    return call_api("GET",
                    "/ventas/productos",
                    params,
                    timeout=REQUEST_TIMEOUT_SLOW)


def comparar_productos(fecha_desde: str,
                       fecha_hasta: str,
                       comparar_con: str,
                       limite: int = 10) -> dict:
    """Productos que crecieron y cayeron entre dos periodos."""
    import json as _json, logging as _logging
    _logger = _logging.getLogger("dw-ventas")

    result = call_api("GET",
                      "/ventas/productos", {
                          "fecha_desde": fecha_desde,
                          "fecha_hasta": fecha_hasta,
                          "comparar_con": comparar_con,
                          "limit": 200
                      },
                      timeout=REQUEST_TIMEOUT_SLOW)

    raw = result.get("content", [{}])[0].get("text", "{}")
    try:
        data = _json.loads(raw)
    except (_json.JSONDecodeError, TypeError):
        return {
            "status": "error",
            "content": [{
                "text": "No se pudo procesar la comparacion."
            }]
        }

    if "data" in data:
        data = data["data"]
    actual = data.get("periodo_actual", {}).get("ventas", [])
    anterior = data.get("periodo_anterior", {}).get("ventas", [])

    if not actual and not anterior:
        return {
            "status":
            "success",
            "content": [{
                "text":
                _json.dumps(
                    {"mensaje": "Sin datos para el periodo solicitado."},
                    ensure_ascii=False)
            }]
        }

    # Indexar periodo anterior por id_item
    ant_idx = {}
    for p in anterior:
        pid = str(p.get("id_item", ""))
        if pid:
            ant_idx[pid] = float(p.get("venta_neta", 0) or 0)

    # Clasificar productos
    crecieron, cayeron, nuevos, desaparecidos = [], [], [], []
    for p in actual:
        pid = str(p.get("id_item", ""))
        neto_actual = float(p.get("venta_neta", 0) or 0)
        neto_anterior = ant_idx.pop(pid, 0)  # pop para trackear los que quedan

        item = {
            "id_item": pid,
            "referencia": p.get("referencia", ""),
            "descripcion": p.get("descripcion_item", ""),
            "neto_actual": round(neto_actual, 2),
            "neto_anterior": round(neto_anterior, 2),
        }

        if neto_anterior > 0 and neto_actual > 0:
            var_pct = round(
                ((neto_actual - neto_anterior) / neto_anterior) * 100, 2)
            item["variacion_pct"] = var_pct
            if var_pct > 0:
                crecieron.append(item)
            elif var_pct < 0:
                cayeron.append(item)
        elif neto_anterior == 0 and neto_actual > 0:
            nuevos.append(item)
        # productos con neto_actual == 0 no aparecen (sin ventas en periodo actual)

    # Productos que estaban en anterior pero no en actual
    for pid, neto_ant in ant_idx.items():
        if neto_ant > 0:
            desaparecidos.append({
                "id_item": pid,
                "neto_anterior": round(neto_ant, 2),
                "neto_actual": 0,
            })

    crecieron.sort(key=lambda x: x["variacion_pct"], reverse=True)
    cayeron.sort(key=lambda x: x["variacion_pct"])

    _logger.info(
        "Comparacion: %d crecieron, %d cayeron, %d nuevos, %d desaparecidos",
        len(crecieron), len(cayeron), len(nuevos), len(desaparecidos))

    return {
        "status":
        "success",
        "content": [{
            "text":
            _json.dumps(
                {
                    "periodo_actual": f"{fecha_desde} a {fecha_hasta}",
                    "periodo_anterior": comparar_con,
                    "productos_que_crecieron": crecieron[:limite],
                    "productos_que_cayeron": cayeron[:limite],
                    "productos_nuevos": nuevos[:limite],
                    "productos_desaparecidos": desaparecidos[:limite],
                },
                ensure_ascii=False)
        }]
    }
