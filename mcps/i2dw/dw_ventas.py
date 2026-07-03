"""Endpoints de ventas (requieren permisos RBAC)."""
from typing import Optional
from i2dw.dw_core import call_api, REQUEST_TIMEOUT_SLOW

def get_ventas(fecha_desde: str, fecha_hasta: str, id_co: Optional[int] = None) -> dict:
    """Ventas diarias. Si no se especifica id_co, retorna todos los centros."""
    return call_api("GET", "/ventas/", {"id_co": id_co, "fecha_desde": fecha_desde, "fecha_hasta": fecha_hasta},
                    timeout=REQUEST_TIMEOUT_SLOW)


def resumen_ventas(fecha_desde: str, fecha_hasta: str, id_co: Optional[int] = None) -> dict:
    """Resumen de ventas con totales sumados listo para responder al usuario.

    Consulta la API del DW, recibe todos los datos, suma las metricas clave
    y entrega un resumen ejecutivo con totales netos, bruto, costo, margen,
    descuento e impuesto. Ideal para preguntas como 'Cuanto vendimos ayer?'
    o 'Cuanto vendimos hoy?'.
    """
    import json, logging
    logger = logging.getLogger("dw-ventas")

    # Usar limites altos para asegurar que todos los registros del periodo se incluyan
    result = call_api("GET", "/ventas/",
                      {"id_co": id_co, "fecha_desde": fecha_desde, "fecha_hasta": fecha_hasta},
                      timeout=REQUEST_TIMEOUT_SLOW, max_items=5000, max_chars=500000)

    # Extraer datos del formato de respuesta
    raw_text = result.get("content", [{}])[0].get("text", "[]")
    try:
        data = json.loads(raw_text)
    except (json.JSONDecodeError, TypeError):
        return {"status": "error", "content": [{"text": "No se pudieron procesar los datos de ventas."}]}

    # La API puede devolver lista directa o dict con clave de datos
    if isinstance(data, dict):
        ventas = data.get("datos", data.get("data", data.get("items", [])))
    elif isinstance(data, list):
        ventas = data
    else:
        ventas = []

    if not ventas:
        return {"status": "success", "content": [{"text": json.dumps({
            "mensaje": "No se encontraron ventas para el periodo consultado.",
            "periodo": f"{fecha_desde} a {fecha_hasta}",
            "total_neto": 0, "total_bruto": 0, "total_costo": 0,
            "total_margen": 0, "total_descuento": 0, "total_impuesto": 0,
            "centros_reportados": 0
        }, ensure_ascii=False)}]}

    # Sumar todas las metricas
    total_neto = 0
    total_bruto = 0
    total_costo = 0
    total_margen = 0
    total_descuento = 0
    total_impuesto = 0
    centros = set()

    for v in ventas:
        total_neto += float(v.get("neto", 0) or 0)
        total_bruto += float(v.get("bruto", 0) or 0)
        total_costo += float(v.get("costo", 0) or 0)
        total_margen += float(v.get("margen", 0) or 0)
        total_descuento += float(v.get("descuento", 0) or 0)
        total_impuesto += float(v.get("impuesto", 0) or 0)
        co = v.get("centro_operacion") or v.get("id_co") or v.get("punto_de_venta", "")
        if co:
            centros.add(str(co))

    # Calcular margen porcentual
    margen_pct = round((total_margen / total_neto * 100), 2) if total_neto > 0 else 0

    resumen = {
        "periodo": f"{fecha_desde} a {fecha_hasta}",
        "total_neto": round(total_neto, 2),
        "total_bruto": round(total_bruto, 2),
        "total_costo": round(total_costo, 2),
        "total_margen": round(total_margen, 2),
        "margen_porcentual": margen_pct,
        "total_descuento": round(total_descuento, 2),
        "total_impuesto": round(total_impuesto, 2),
        "centros_reportados": len(centros),
    }

    logger.info("Resumen de ventas generado: %s", resumen)
    return {"status": "success", "content": [{"text": json.dumps(resumen, ensure_ascii=False)}]}

def get_ventas_item(id_item: int, fecha_desde: str, fecha_hasta: str, id_co: Optional[int] = None) -> dict:
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
        return call_api("GET", "/ventas/", {"q": producto, "fecha_desde": fecha_desde,
                        "fecha_hasta": fecha_hasta, "id_co": id_co, "limit": limite})

    # Paso 1: Buscar en catalogo con multiples estrategias
    productos = []
    estrategias = []

    # Estrategia A: nombre completo (prefix match)
    prod_result = call_api("GET", "/productos/", {"q": producto, "buscar_por": "nombre", "limit": 10},
                           timeout=REQUEST_TIMEOUT_SLOW)
    prod_text = prod_result.get("content", [{}])[0].get("text", "[]")
    try:
        data = json.loads(prod_text)
        prods = data if isinstance(data, list) else data.get("data", data.get("items", []))
        if prods:
            productos = prods
            estrategias.append("nombre completo")
    except (json.JSONDecodeError, TypeError):
        pass

    # Estrategia B: por referencia (el usuario pudo dar una ref)
    if not productos:
        ref_result = call_api("GET", "/productos/", {"q": producto, "buscar_por": "referencia", "limit": 10},
                            timeout=REQUEST_TIMEOUT_SLOW)
        ref_text = ref_result.get("content", [{}])[0].get("text", "[]")
        try:
            data = json.loads(ref_text)
            prods = data if isinstance(data, list) else data.get("data", data.get("items", []))
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
            kw_result = call_api("GET", "/productos/", {"q": short_q, "buscar_por": "nombre", "limit": 10},
                                timeout=REQUEST_TIMEOUT_SLOW)
            kw_text = kw_result.get("content", [{}])[0].get("text", "[]")
            try:
                data = json.loads(kw_text)
                prods = data if isinstance(data, list) else data.get("data", data.get("items", []))
                if prods:
                    productos = prods
                    estrategias.append(f"palabras clave: '{short_q}'")
            except (json.JSONDecodeError, TypeError):
                pass

    if not productos:
        # Fallback final: intentar busqueda directa en ventas (puede ser mas tolerante)
        logger.info("Catalogo sin resultados para '%s', intentando ventas directo", producto)
        return call_api("GET", "/ventas/", {"q": producto, "fecha_desde": fecha_desde,
                        "fecha_hasta": fecha_hasta, "id_co": id_co, "limit": limite},
                        timeout=REQUEST_TIMEOUT_SLOW)

    # Paso 2: Para cada producto encontrado, buscar sus ventas
    # Usamos el primer producto como termino de busqueda en ventas
    # porque /ventas?q= busca por id, referencia y nombre del producto
    resultados = []
    ids_buscados = set()

    for p in productos[:5]:  # max 5 productos para no saturar
        pid = p.get("id", p.get("id_item", ""))
        if not pid or pid in ids_buscados:
            continue
        ids_buscados.add(pid)

        ventas_result = call_api("GET", "/ventas/", {"q": str(pid), "fecha_desde": fecha_desde,
                                "fecha_hasta": fecha_hasta, "id_co": id_co, "limit": limite},
                                timeout=REQUEST_TIMEOUT_SLOW)

        ventas_text = ventas_result.get("content", [{}])[0].get("text", "[]")
        try:
            ventas = json.loads(ventas_text)
            if isinstance(ventas, dict):
                ventas = ventas.get("data", ventas.get("datos", []))
            if isinstance(ventas, list) and ventas:
                resultados.extend(ventas)
        except (json.JSONDecodeError, TypeError):
            continue

    if not resultados:
        nombres = ", ".join(str(p.get("descripcion", p.get("id", ""))) for p in productos[:5])
        return {"status": "success", "content": [{"text": json.dumps({
            "mensaje": f"Se encontraron productos en catalogo ({nombres}) pero sin ventas en el periodo.",
            "productos_encontrados": len(productos),
            "resultados": []
        }, ensure_ascii=False)}]}

    # Limitar y retornar
    resultados = resultados[:limite]
    return {"status": "success", "content": [{"text": json.dumps({
        "productos_encontrados": len(productos),
        "total_ventas": len(resultados),
        "metodo": f"two-step (catalogo x {', '.join(estrategias)} + ventas)",
        "resultados": resultados
    }, ensure_ascii=False)}]}

def buscar_ventas_por_referencia(referencia: str, fecha_desde: str, fecha_hasta: str,
                                  id_co: Optional[int] = None, limite: int = 100) -> dict:
    """Busca ventas por referencia exacta/parcial de producto."""
    return call_api("GET", "/ventas/", {"referencia": referencia, "fecha_desde": fecha_desde,
                    "fecha_hasta": fecha_hasta, "id_co": id_co, "limit": limite},
                    timeout=REQUEST_TIMEOUT_SLOW)

def top_productos(limite: int, fecha_desde: str, fecha_hasta: str,
                  id_co: Optional[int] = None, ordenar_por: str = "cantidad") -> dict:
    """Top N productos mas vendidos en un periodo."""
    return call_api("GET", "/ventas/", {"top": limite, "fecha_desde": fecha_desde,
                    "fecha_hasta": fecha_hasta, "id_co": id_co, "ordenar_por": ordenar_por},
                    timeout=REQUEST_TIMEOUT_SLOW)

def margen_por_dimension(dimension: str, fecha_desde: str, fecha_hasta: str,
                          id_co: Optional[int] = None, limite: int = 50) -> dict:
    """Margen agrupado por categoria, seccion, producto o proveedor."""
    return call_api("GET", "/ventas/", {"agrupar_por": dimension, "fecha_desde": fecha_desde,
                    "fecha_hasta": fecha_hasta, "id_co": id_co, "limit": limite},
                    timeout=REQUEST_TIMEOUT_SLOW)

def comparar_periodos(id_co: int, fecha_desde: str, fecha_hasta: str, comparar_con: str) -> dict:
    """Compara ventas entre dos periodos."""
    return call_api("GET", "/ventas/", {"id_co": id_co, "fecha_desde": fecha_desde,
                    "fecha_hasta": fecha_hasta, "comparar_con": comparar_con}, timeout=REQUEST_TIMEOUT_SLOW)

def ticket_promedio(fecha_desde: str, fecha_hasta: str, id_co: Optional[int] = None) -> dict:
    """Ticket promedio diario."""
    return call_api("GET", "/ventas/", {"modo": "ticket", "fecha_desde": fecha_desde,
                    "fecha_hasta": fecha_hasta, "id_co": id_co}, timeout=REQUEST_TIMEOUT_SLOW)

def rotacion_inventario(fecha_desde: str, fecha_hasta: str,
                         id_co: Optional[int] = None, limite: int = 50) -> dict:
    """Dias de inventario por producto."""
    return call_api("GET", "/ventas/", {"modo": "rotacion", "fecha_desde": fecha_desde,
                    "fecha_hasta": fecha_hasta, "id_co": id_co, "limit": limite},
                    timeout=REQUEST_TIMEOUT_SLOW)
