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
                  limite: int = 100) -> dict:
    """Busca ventas con two-step: catalogo primero (LIKE prefix), ventas despues.

    Flujo:
    1. Si no es un ID numerico puro, busca en /productos?q=&buscar_por=nombre
    2. Con los IDs encontrados, consulta /ventas?q={id_item}&fecha_desde=&fecha_hasta=
    3. Si es un ID numerico, busca directo en ventas
    """
    import json, logging
    logger = logging.getLogger("dw-ventas")

    # Si es un ID numerico puro, buscar directo en ventas
    if producto.strip().isdigit():
        return call_api(
            "GET", "/ventas/", {
                "q": producto,
                "fecha_desde": fecha_desde,
                "fecha_hasta": fecha_hasta,
                "id_co": id_co,
                "limit": limite
            })

    # Paso 1: Buscar en catalogo con multiples estrategias
    productos = []
    estrategias = []

    # Estrategia A: nombre completo (prefix match)
    prod_result = call_api("GET",
                           "/productos/", {
                               "q": producto,
                               "buscar_por": "nombre",
                               "limit": 10
                           },
                           timeout=REQUEST_TIMEOUT_SLOW)
    prod_text = prod_result.get("content", [{}])[0].get("text", "[]")
    try:
        data = json.loads(prod_text)
        prods = data if isinstance(data, list) else data.get(
            "data", data.get("items", []))
        if prods:
            productos = prods
            estrategias.append("nombre completo")
    except (json.JSONDecodeError, TypeError):
        pass

    # Estrategia B: por referencia (el usuario pudo dar una ref)
    if not productos:
        ref_result = call_api("GET",
                              "/productos/", {
                                  "q": producto,
                                  "buscar_por": "referencia",
                                  "limit": 10
                              },
                              timeout=REQUEST_TIMEOUT_SLOW)
        ref_text = ref_result.get("content", [{}])[0].get("text", "[]")
        try:
            data = json.loads(ref_text)
            prods = data if isinstance(data, list) else data.get(
                "data", data.get("items", []))
            if prods:
                productos = prods
                estrategias.append("referencia")
        except (json.JSONDecodeError, TypeError):
            pass

    # Estrategia C: primeras 3 palabras clave (mas tolerante con prefix)
    if not productos:
        palabras = producto.split()[:3]
        if palabras:
            short_q = " ".join(palabras)
            kw_result = call_api("GET",
                                 "/productos/", {
                                     "q": short_q,
                                     "buscar_por": "nombre",
                                     "limit": 10
                                 },
                                 timeout=REQUEST_TIMEOUT_SLOW)
            kw_text = kw_result.get("content", [{}])[0].get("text", "[]")
            try:
                data = json.loads(kw_text)
                prods = data if isinstance(data, list) else data.get(
                    "data", data.get("items", []))
                if prods:
                    productos = prods
                    estrategias.append(f"palabras clave: '{short_q}'")
            except (json.JSONDecodeError, TypeError):
                pass

    if not productos:
        # Sin resultados en catalogo
        logger.info("Catalogo sin resultados para '%s'", producto)
        return {"status": "success", "content": [{"text": json.dumps({
            "mensaje": f"No se encontro '{producto}' en el catalogo.",
            "resultados": []
        }, ensure_ascii=False)}]}

    # Ordenar por relevancia: preferir productos que EMPIECEN con las palabras buscadas
    # Filtrar stop words que causan falsos matches ("a", "de", "la", "el", "en", ...)
    STOP_WORDS = {"a", "de", "la", "el", "en", "con", "por", "para", "del", "los",
                  "las", "un", "una", "y", "o", "que", "es", "se", "su", "al", "lo"}
    query_words = [w for w in producto.lower().split() if w not in STOP_WORDS]
    if not query_words:
        query_words = producto.lower().split()  # si todas son stop words, usar todas

    def _score(p):
        name = str(p.get("descripcion") or p.get("nombre") or "").lower()
        name_words = name.split()
        score = 0
        for qw in query_words:
            if qw in name_words:
                score += 1
                pos = name_words.index(qw)
                if pos <= 1:
                    score += 3
        # Penalizar nombres con palabras de accesorio
        ACC_WORDS = {"cacha", "manija", "asa", "tapa", "accesorio", "repuesto",
                     "control", "caja", "pinonera", "condensador", "base", "soporte"}
        for aw in ACC_WORDS:
            if aw in name_words:
                score -= 2
        return score

    productos.sort(key=_score, reverse=True)

    # Paso 2: Para los productos mas relevantes, buscar ventas agregadas
    resultados = []
    ids_buscados = set()

    for p in productos[:10]:  # buscar ventas de los 10 mas relevantes
        pid = p.get("id", p.get("id_item", ""))
        if not pid or pid in ids_buscados:
            continue
        ids_buscados.add(pid)

        ventas_result = call_api("GET",
                                 "/ventas/productos", {
                                     "id_item": int(pid),
                                     "fecha_desde": fecha_desde,
                                     "fecha_hasta": fecha_hasta,
                                     "id_co": id_co,
                                 },
                                 timeout=REQUEST_TIMEOUT_SLOW)

        ventas_text = ventas_result.get("content", [{}])[0].get("text", "[]")
        try:
            ventas = json.loads(ventas_text)
            if isinstance(ventas, dict):
                ventas = ventas.get("data", ventas.get("ventas", ventas.get("datos", [])))
            if isinstance(ventas, list) and ventas:
                for v in ventas:
                    v["_catalogo_match"] = str(p.get("descripcion", p.get("nombre", "")))
                resultados.extend(ventas)
        except (json.JSONDecodeError, TypeError):
            continue

    if not resultados:
        nombres = ", ".join(
            str(p.get("descripcion", p.get("id", ""))) for p in productos[:5])
        return {
            "status":
            "success",
            "content": [{
                "text":
                json.dumps(
                    {
                        "mensaje":
                        f"Se encontraron productos en catalogo ({nombres}) pero sin ventas en el periodo.",
                        "productos_encontrados": len(productos),
                        "resultados": []
                    },
                    ensure_ascii=False)
            }]
        }

    # Calcular total para que el LLM no tenga que sumar
    total_neta = sum(
        float(r.get("venta_neta", 0) or r.get("neto", 0) or 0)
        for r in resultados
    )
    total_items = len(resultados)

    # Construir resumen claro para el LLM
    resumen = f"Se encontraron {len(productos)} productos en catalogo. "
    if total_items > 0 and total_neta > 0:
        resumen += f"{total_items} productos registraron ventas por un total de ${total_neta:,.0f} en el periodo."
    else:
        resumen += "Ninguno registro ventas en el periodo."

    resultados = resultados[:limite]
    return {
        "status":
        "success",
        "content": [{
            "text":
            json.dumps(
                {
                    "resumen": resumen,
                    "total_venta_neta": round(total_neta, 2),
                    "productos_con_venta": total_items,
                    "productos_encontrados": len(productos),
                    "metodo":
                    f"two-step (catalogo x {', '.join(estrategias)} + ventas)",
                    "resultados": resultados
                },
                ensure_ascii=False)
        }]
    }


def buscar_ventas_por_referencia(referencia: str,
                                 fecha_desde: str,
                                 fecha_hasta: str,
                                 id_co: Optional[int] = None,
                                 limite: int = 100) -> dict:
    """Two-step: busca en catalogo por referencia, luego ventas por id_item."""
    import json
    # Paso 1: buscar producto por referencia en catalogo
    cat = call_api("GET", "/productos/",
                   {"q": referencia, "buscar_por": "referencia", "limit": 3},
                   timeout=REQUEST_TIMEOUT_SLOW)
    cat_text = cat.get("content", [{}])[0].get("text", "[]")
    try:
        data = json.loads(cat_text)
        prods = data if isinstance(data, list) else data.get("data", data.get("items", []))
    except (json.JSONDecodeError, TypeError):
        prods = []

    if not prods:
        return {"status": "success", "content": [{"text": json.dumps({
            "mensaje": f"No se encontro producto con referencia '{referencia}'."
        }, ensure_ascii=False)}]}

    # Paso 2: buscar ventas del primer producto
    pid = prods[0].get("id", prods[0].get("id_item", ""))
    if not pid:
        return {"status": "success", "content": [{"text": json.dumps({
            "mensaje": f"Producto encontrado pero sin id_item."
        }, ensure_ascii=False)}]}

    return call_api("GET", "/ventas/productos",
                    {"id_item": int(pid), "fecha_desde": fecha_desde,
                     "fecha_hasta": fecha_hasta, "id_co": id_co},
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


def margen_por_dimension(dimension: str,
                         fecha_desde: str,
                         fecha_hasta: str,
                         id_co: Optional[int] = None,
                         limite: int = 50) -> dict:
    """Margen agrupado por categoria, seccion, producto o proveedor."""
    return call_api("GET",
                    "/ventas/", {
                        "agrupar_por": dimension,
                        "fecha_desde": fecha_desde,
                        "fecha_hasta": fecha_hasta,
                        "id_co": id_co,
                        "limit": limite
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


def categoria_top(fecha_desde: str,
                  fecha_hasta: str,
                  id_co: Optional[int] = None,
                  ordenar_por: str = "margen") -> dict:
    """Categoria top por margen o venta neta. Una sola llamada, resultado directo.
    Usa /ventas?agrupar_por=categoria&limit=1.
    ordenar_por: 'margen' (default, mas rentable) o 'venta_neta' (mas volumen)."""
    return call_api("GET",
                    "/ventas/", {
                        "agrupar_por": "categoria",
                        "fecha_desde": fecha_desde,
                        "fecha_hasta": fecha_hasta,
                        "id_co": id_co,
                        "limit": 1,
                        "ordenar_por": ordenar_por
                    },
                    timeout=REQUEST_TIMEOUT_SLOW)


def centros_por_venta(fecha_desde: str,
                      fecha_hasta: str,
                      orden: str = "desc",
                      limite: int = 5) -> dict:
    """Sedes ordenadas por venta neta. El API agrupa, suma y ordena — retorna solo N filas.
    Usa /ventas?agrupar_por=co&orden=asc|desc&limit=N.
    orden='asc' = las que menos venden primero. orden='desc' = las que mas venden primero."""
    return call_api("GET",
                    "/ventas/", {
                        "agrupar_por": "co",
                        "fecha_desde": fecha_desde,
                        "fecha_hasta": fecha_hasta,
                        "orden": orden,
                        "limit": limite
                    },
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
