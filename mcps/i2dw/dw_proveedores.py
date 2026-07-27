"""Endpoints de proveedores: reporte, busqueda, indice."""
import difflib
import json, logging, time
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Optional
from i2dw.dw_core import call_api, REQUEST_TIMEOUT_SLOW, MAX_ADMIN_LIST_ITEMS

logger = logging.getLogger("dw-proveedores")
_index_cache: Optional[dict] = None
_index_ts: float = 0.0


def _descargar_lote(fecha_desde: str, fecha_hasta: str, proveedor_id: str) -> list:
    """Descarga un lote de datos del proveedor. Retorna lista de filas."""
    import json as _json
    result = call_api("GET", "/ventas-proveedores/", {
        "fecha_inicio": fecha_desde, "fecha_fin": fecha_hasta,
        "proveedor_id": proveedor_id
    }, timeout=REQUEST_TIMEOUT_SLOW)
    raw = result.get("content", [{}])[0].get("text", "{}")
    try:
        data = _json.loads(raw)
        return data.get("datos", data.get("data", []))
    except (_json.JSONDecodeError, TypeError):
        return []


def _acumular(filas: list, por_producto: dict, por_tienda: dict, por_categoria: dict):
    """Acumula metricas de un lote en los diccionarios globales."""
    for f in filas:
        nombre = f.get("descripcion_articulo", "")
        tienda = f.get("punto_de_venta", "")
        cat = f.get("categoria", "")
        unds = int(f.get("cantidad_vendida", 0) or 0)
        neto = float(f.get("venta_neta", 0) or 0)
        costo = float(f.get("coste_venta", 0) or 0)
        inv = int(f.get("cantidad_inventario", 0) or 0)
        por_producto[nombre]["unidades"] += unds
        por_producto[nombre]["venta_neta"] += neto
        por_producto[nombre]["costo"] += costo
        por_producto[nombre]["inventario"] += inv
        por_tienda[tienda]["unidades"] += unds
        por_tienda[tienda]["venta_neta"] += neto
        por_tienda[tienda]["costo"] += costo
        if cat:
            por_categoria[cat]["unidades"] += unds
            por_categoria[cat]["venta_neta"] += neto
            por_categoria[cat]["costo"] += costo


def obtener_reporte_proveedores(fecha_desde: Optional[str] = None, fecha_hasta: Optional[str] = None,
                                proveedor_id: Optional[str] = None) -> dict:
    """Reporte del proveedor con totales agregados. Batching interno por semanas."""
    import json as _json

    # Si el periodo es mayor a 7 dias, dividir en lotes semanales
    try:
        d1 = datetime.strptime(fecha_desde or "", "%Y-%m-%d")
        d2 = datetime.strptime(fecha_hasta or "", "%Y-%m-%d")
        delta = (d2 - d1).days
    except (ValueError, TypeError):
        delta = 0
        d1 = d2 = None

    if delta > 7 and d1 and d2:
        # Batching: procesar por semanas
        por_producto = defaultdict(lambda: {"unidades": 0, "venta_neta": 0, "costo": 0, "inventario": 0})
        por_tienda = defaultdict(lambda: {"unidades": 0, "venta_neta": 0, "costo": 0})
        por_categoria = defaultdict(lambda: {"unidades": 0, "venta_neta": 0, "costo": 0})
        total_lotes = 0

        actual = d1
        while actual <= d2:
            fin_lote = min(actual + timedelta(days=6), d2)
            lote = _descargar_lote(
                actual.strftime("%Y-%m-%d"),
                fin_lote.strftime("%Y-%m-%d"),
                proveedor_id or ""
            )
            _acumular(lote, por_producto, por_tienda, por_categoria)
            total_lotes += 1
            actual = fin_lote + timedelta(days=1)

        logger.info("Proveedor %s: %d lotes procesados, %d productos",
                    proveedor_id, total_lotes, len(por_producto))
    else:
        # Periodo corto: una sola llamada
        filas = _descargar_lote(fecha_desde or "", fecha_hasta or "", proveedor_id or "")
        por_producto = defaultdict(lambda: {"unidades": 0, "venta_neta": 0, "costo": 0, "inventario": 0})
        por_tienda = defaultdict(lambda: {"unidades": 0, "venta_neta": 0, "costo": 0})
        por_categoria = defaultdict(lambda: {"unidades": 0, "venta_neta": 0, "costo": 0})
        _acumular(filas, por_producto, por_tienda, por_categoria)

    if not por_producto:
        return {"status": "success", "content": [{"text": _json.dumps({
            "mensaje": "Sin datos para el periodo solicitado.",
            "total_venta_neta": 0, "total_unidades": 0,
            "total_costo_venta": 0, "total_inventario": 0,
            "productos": 0, "tiendas": 0
        }, ensure_ascii=False)}]}

    # Totales desde los acumuladores
    total_unidades = sum(d["unidades"] for d in por_producto.values())
    total_neta = sum(d["venta_neta"] for d in por_producto.values())
    total_costo = sum(d["costo"] for d in por_producto.values())
    total_inv = sum(d["inventario"] for d in por_producto.values())

    top_productos = sorted(por_producto.items(), key=lambda x: x[1]["venta_neta"], reverse=True)[:10]
    top_tiendas = sorted(por_tienda.items(), key=lambda x: x[1]["venta_neta"], reverse=True)[:5]
    top_categorias = sorted(por_categoria.items(), key=lambda x: x[1]["venta_neta"], reverse=True)[:10]

    encabezado = (
        f"Proveedor {proveedor_id}: ${total_neta:,.0f} venta neta, "
        f"{total_unidades} unidades, ${total_costo:,.0f} costo, "
        f"{total_inv} en inventario, {len(por_producto)} productos en {len(por_tienda)} tiendas."
    )

    return {"status": "success", "content": [
        {"text": encabezado},
        {"text": _json.dumps({
            "proveedor_id": proveedor_id,
            "periodo": f"{fecha_desde} a {fecha_hasta}",
            "total_venta_neta": round(total_neta, 2),
            "total_unidades": total_unidades,
            "total_costo_venta": round(total_costo, 2),
            "total_inventario": total_inv,
            "total_productos": len(por_producto),
            "total_tiendas": len(por_tienda),
            "top_productos": [{"producto": n, "unidades": d["unidades"], "venta_neta": round(d["venta_neta"], 2), "costo": round(d["costo"], 2), "inventario": d["inventario"]} for n, d in top_productos],
            "top_tiendas": [{"tienda": n, "unidades": d["unidades"], "venta_neta": round(d["venta_neta"], 2), "costo": round(d["costo"], 2)} for n, d in top_tiendas],
            "por_categoria": [{"categoria": n, "unidades": d["unidades"], "venta_neta": round(d["venta_neta"], 2), "costo": round(d["costo"], 2)} for n, d in top_categorias],
        }, ensure_ascii=False)}
    ]}

def productos_estancados(proveedor_id: str,
                          dia_periodo_inferior: int = 0,
                          dia_periodo_superior: int = 30,
                          limit: int = 30) -> dict:
    """Productos con stock que no han vendido en N dias. Llama al ERP SIESA via SOAP.
    proveedor_id: ID del criterio mayor (plan 007). REQUERIDO.
    dia_periodo_inferior: minimo de dias sin venta (default 0).
    dia_periodo_superior: maximo de dias sin venta (default 30).
    limit: cuantos productos top retornar al modelo (default 30, se piden 500 al API)."""
    import json as _json

    result = call_api("GET", "/ventas-proveedores/venta-cero", {
        "proveedor_id": proveedor_id,
        "dia_periodo_inferior": dia_periodo_inferior,
        "dia_periodo_superior": dia_periodo_superior,
        "limit": 500,  # maximo al API
    }, timeout=REQUEST_TIMEOUT_SLOW)

    raw = result.get("content", [{}])[0].get("text", "{}")
    try:
        data = _json.loads(raw)
        filas = data if isinstance(data, list) else data.get("datos", data.get("data", data.get("items", [])))
    except (_json.JSONDecodeError, TypeError):
        filas = []

    if not filas:
        return {"status": "success", "content": [
            {"text": f"Proveedor {proveedor_id}: sin productos estancados ({dia_periodo_inferior}-{dia_periodo_superior} dias)."}
        ]}

    # Calcular totales
    total_stock = sum(int(f.get("cant_existencia", 0) or 0) for f in filas)
    total_items = len(filas)

    # Top N por stock (los que mas preocupan)
    ordenados = sorted(filas, key=lambda x: int(x.get("cant_existencia", 0) or 0), reverse=True)
    top = ordenados[:limit]

    items = []
    for f in top:
        items.append({
            "id_item": f.get("id_item", ""),
            "referencia": (f.get("referencia") or "").strip(),
            "descripcion": (f.get("descripcion") or "").strip(),
            "id_co": f.get("id_co", ""),
            "cant_existencia": int(f.get("cant_existencia", 0) or 0),
            "dias_ult_venta": int(f.get("dias_ult_venta", 0) or 0),
            "ult_fecha_venta": f.get("ult_fecha_venta", ""),
            "ult_fecha_compra": f.get("ult_fecha_compra", ""),
        })

    encabezado = (
        f"Productos estancados proveedor {proveedor_id} "
        f"({dia_periodo_inferior}-{dia_periodo_superior} dias sin venta): "
        f"{total_items} productos, {total_stock} unidades en stock. "
        f"Top {len(items)} mostrados."
    )

    return {"status": "success", "content": [
        {"text": encabezado},
        {"text": _json.dumps({
            "proveedor_id": proveedor_id,
            "dias_sin_venta": f"{dia_periodo_inferior}-{dia_periodo_superior}",
            "total_productos": total_items,
            "total_stock": total_stock,
            "productos": items,
        }, ensure_ascii=False)}
    ]}

def venta_cero_por_centro(proveedor_id: str,
                           dia_periodo_inferior: int = 0,
                           dia_periodo_superior: int = 30) -> dict:
    """Agrupa productos sin venta por centro de operacion. Batching por rangos de dias.
    Retorna top 5 tiendas con mas stock estancado + top 5 productos por tienda."""
    import json as _json, logging as _logging
    from collections import defaultdict
    _logger = _logging.getLogger("dw-proveedores")

    # Batching: dividir rango de dias en chunks de 30 para no saturar la respuesta
    CHUNK = 30
    por_co = defaultdict(lambda: {"stock": 0, "productos": defaultdict(int)})
    total_items = 0

    lo = dia_periodo_inferior
    while lo < dia_periodo_superior:
        hi = min(lo + CHUNK, dia_periodo_superior)
        result = call_api("GET", "/ventas-proveedores/venta-cero", {
            "proveedor_id": proveedor_id,
            "dia_periodo_inferior": lo,
            "dia_periodo_superior": hi,
            "limit": 500,
        }, timeout=REQUEST_TIMEOUT_SLOW)

        raw = result.get("content", [{}])[0].get("text", "{}")
        try:
            data = _json.loads(raw)
            filas = data if isinstance(data, list) else data.get("datos", data.get("data", []))
        except (_json.JSONDecodeError, TypeError):
            filas = []

        for f in filas:
            co = str(f.get("id_co", "")).strip()
            stock = int(f.get("cant_existencia", 0) or 0)
            desc = (f.get("descripcion") or "").strip()
            if co:
                por_co[co]["stock"] += stock
                if desc:
                    por_co[co]["productos"][desc] += stock
        total_items += len(filas)
        lo = hi

    if not por_co:
        return {"status": "success", "content": [
            {"text": f"Proveedor {proveedor_id}: sin productos estancados ({dia_periodo_inferior}-{dia_periodo_superior} dias)."}
        ]}

    _logger.info("venta_cero_por_centro %s: %d items, %d tiendas",
                 proveedor_id, total_items, len(por_co))

    # Top 5 tiendas
    ranked_tiendas = sorted(por_co.items(), key=lambda x: x[1]["stock"], reverse=True)
    top_tiendas = []
    total_stock = 0

    for co, d in ranked_tiendas[:5]:
        total_stock += d["stock"]
        # Top 5 productos en esta tienda
        top_prods = sorted(d["productos"].items(), key=lambda x: x[1], reverse=True)[:5]
        top_tiendas.append({
            "id_co": co,
            "stock_estancado": d["stock"],
            "total_productos_estancados": len(d["productos"]),
            "top_5_productos": [
                {"producto": p[0], "stock": p[1]} for p in top_prods
            ],
        })

    encabezado = (
        f"Proveedor {proveedor_id}: {total_items} productos sin venta "
        f"({dia_periodo_inferior}-{dia_periodo_superior} dias), "
        f"{len(por_co)} tiendas, {total_stock} und stock total. "
        f"Top 5 tiendas con mas stock estancado."
    )

    return {"status": "success", "content": [
        {"text": encabezado},
        {"text": _json.dumps({
            "proveedor_id": proveedor_id,
            "dias_sin_venta": f"{dia_periodo_inferior}-{dia_periodo_superior}",
            "total_tiendas": len(por_co),
            "total_productos": total_items,
            "total_stock": total_stock,
            "top_5_tiendas": top_tiendas,
        }, ensure_ascii=False)}
    ]}


def ranking_proveedores_venta_cero(dia_periodo_inferior: int = 0,
                                     dia_periodo_superior: int = 30,
                                     top_n: int = 10) -> dict:
    """Ranking de proveedores por stock sin venta. Batching: consulta cada proveedor del indice.
    Retorna top N proveedores con mas productos estancados."""
    import json as _json, logging as _logging
    _logger = _logging.getLogger("dw-proveedores")

    # Obtener indice de proveedores
    index = _construir_indice()
    proveedores = list(index.values())

    if not proveedores:
        return {"status": "success", "content": [{"text": "No se encontro indice de proveedores."}]}

    _logger.info("Ranking venta cero: %d proveedores a consultar", len(proveedores))

    ranking = []
    for p in proveedores:
        pid = p["criterio_mayor_id"]
        nombre = p["nombre"]
        try:
            result = call_api("GET", "/ventas-proveedores/venta-cero", {
                "proveedor_id": pid,
                "dia_periodo_inferior": dia_periodo_inferior,
                "dia_periodo_superior": dia_periodo_superior,
                "limit": 500,
            }, timeout=REQUEST_TIMEOUT_SLOW)

            raw = result.get("content", [{}])[0].get("text", "{}")
            data = _json.loads(raw)
            filas = data if isinstance(data, list) else data.get("datos", data.get("data", []))

            total_stock = sum(int(f.get("cant_existencia", 0) or 0) for f in filas)
            total_prods = len(filas)

            if total_stock > 0:
                ranking.append({
                    "proveedor_id": pid,
                    "nombre": nombre,
                    "productos_estancados": total_prods,
                    "stock_total": total_stock,
                })
        except Exception as e:
            _logger.warning("Error consultando proveedor %s: %s", pid, e)
            continue

    ranking.sort(key=lambda x: x["stock_total"], reverse=True)
    top = ranking[:top_n]

    if not top:
        return {"status": "success", "content": [
            {"text": f"Ningun proveedor tiene productos sin venta ({dia_periodo_inferior}-{dia_periodo_superior} dias)."}
        ]}

    total_stock_global = sum(r["stock_total"] for r in ranking)
    encabezado = (
        f"Ranking proveedores por stock sin venta ({dia_periodo_inferior}-{dia_periodo_superior} dias): "
        f"{len(ranking)} proveedores con {total_stock_global} und estancadas. Top {len(top)}:"
    )

    return {"status": "success", "content": [
        {"text": encabezado},
        {"text": _json.dumps({
            "dias_sin_venta": f"{dia_periodo_inferior}-{dia_periodo_superior}",
            "total_proveedores": len(ranking),
            "total_stock_global": total_stock_global,
            "ranking": top,
        }, ensure_ascii=False)}
    ]}


def reporte_proveedor_top(limite: int, fecha_desde: str, fecha_hasta: str,
                           proveedor_id: str, ordenar_por: str = "cantidad") -> dict:
    """Top productos de un proveedor."""
    return call_api("GET", "/ventas-proveedores/", {"top": limite, "fecha_inicio": fecha_desde,
                    "fecha_fin": fecha_hasta, "proveedor_id": proveedor_id, "ordenar_por": ordenar_por},
                    timeout=REQUEST_TIMEOUT_SLOW)

def listar_proveedores() -> dict:
    """Lista proveedores admin con criterio_mayor_id y nombre."""
    return call_api("GET", "/admin/proveedores/", max_items=MAX_ADMIN_LIST_ITEMS, max_chars=50000)


def _construir_indice() -> dict:
    """Indice desde /admin/proveedores/ (sin paginacion — endpoint devuelve todo). Cache 1h."""
    global _index_cache, _index_ts
    now = time.time()
    if _index_cache is not None and (now - _index_ts) < 3600:
        return _index_cache

    logger.info("Cargando todos los proveedores desde admin...")
    # Sin page/page_size — el endpoint devuelve todo de una vez
    result = call_api("GET", "/admin/proveedores/", max_items=2000, max_chars=500000, timeout=120)
    text = result.get("content", [{}])[0].get("text", "[]")

    index = {}
    try:
        data = json.loads(text)
        proveedores = data if isinstance(data, list) else data.get("data", data.get("datos", []))
    except (json.JSONDecodeError, TypeError):
        proveedores = []

    for p in proveedores:
        pid = str(p.get("criterio_mayor_id", ""))
        nombre = (p.get("nombre") or "").strip()
        if pid and nombre:
            index[nombre.lower()] = {"criterio_mayor_id": pid, "nombre": nombre}

    _index_cache = index; _index_ts = now
    logger.info("Indice: %d proveedores cargados", len(index))
    return index


def buscar_proveedor_por_nombre(nombre: str) -> dict:
    """Busca proveedor x nombre/ID con matching fuzzy (admin + plan 007)."""
    q = nombre.lower().strip(); index = _construir_indice()

    # 1. ID exacto
    for key, entry in index.items():
        if entry["criterio_mayor_id"] == q:
            return {"status": "success", "content": [{"text": json.dumps(
                {"resultados": [entry], "total_coincidencias": 1, "busqueda": "ID exacto"}, ensure_ascii=False)}]}

    # 2. Fuzzy matching
    words = q.split()
    exact, contains, word_match, fuzzy = [], [], [], []
    for key, entry in index.items():
        if key == q: exact.append(entry)
        elif q in key: contains.append(entry)
        elif all(w in key for w in words): word_match.append(entry)
        elif any(w in key for w in words): fuzzy.append(entry)

    matches = exact + contains + word_match + fuzzy

    # 3. Fallback difflib: fuzzy matching sobre TODOS los nombres
    if not matches:
        all_names = list(index.keys())
        fuzzy_matches = difflib.get_close_matches(q, all_names, n=10, cutoff=0.4)
        if fuzzy_matches:
            matches = [index[name] for name in fuzzy_matches]

    # 4. Fallback: si es ID numerico, sugerir uso directo
    if not matches and q.isdigit() and len(q) >= 2:
        return {"status": "success", "content": [{"text": json.dumps({
            "mensaje": f"'{nombre}' no indexado, pero parece ID valido plan 007.",
            "accion": "USAR_DIRECTAMENTE", "proveedor_id_sugerido": q,
            "instruccion": f"Llama dw_obtener_reporte_proveedores(proveedor_id=\"{q}\") directamente."
        }, ensure_ascii=False)}]}

    if not matches:
        return {"status": "success", "content": [{"text": json.dumps({
            "mensaje": f"No se encontro '{nombre}' en {len(index)} proveedores.",
            "resultados": [], "total_proveedores_indexados": len(index)
        }, ensure_ascii=False)}]}

    return {"status": "success", "content": [{"text": json.dumps(
        {"resultados": matches[:15], "total_coincidencias": len(matches), "busqueda": nombre}, ensure_ascii=False)}]}
