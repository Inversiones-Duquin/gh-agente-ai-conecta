"""Endpoints de inventarios — stock real por producto, bodega y centro.
PATRON: batching por CO cuando la respuesta alcanza el limite del API (500 items)."""
from typing import Optional
from collections import defaultdict
from i2dw.dw_core import call_api, REQUEST_TIMEOUT_SLOW

_API_LIMIT = 500


def _extraer_filas(result: dict) -> list:
    """Extrae la lista de items de la respuesta del API."""
    import json as _json
    raw = result.get("content", [{}])[0].get("text", "{}")
    try:
        data = _json.loads(raw)
        return data if isinstance(data, list) else data.get("data", data.get("items", data.get("datos", [])))
    except (_json.JSONDecodeError, TypeError):
        return []


def _descargar_lotes(params_base: dict) -> list:
    """Descarga TODOS los items usando batching por CO si es necesario.
    1. Sin filtro de CO y respuesta llena (500 items) → divide por CO y acumula.
    2. Con filtro de CO o respuesta parcial → retorna directo (no se puede batchear mas)."""
    import logging
    _logger = logging.getLogger("dw-inventarios")

    p = dict(params_base) if params_base else {}
    p["limit"] = _API_LIMIT
    tiene_filtro_co = bool(p.get("id_co"))

    r = call_api("GET", "/inventarios/", p, timeout=REQUEST_TIMEOUT_SLOW)
    filas = _extraer_filas(r)

    # Sin truncacion o no se puede dividir mas → retornar
    if len(filas) < _API_LIMIT or tiene_filtro_co:
        return filas

    # Truncacion detectada: batching por CO
    _logger.info("Inventario: %d items (tope API). Batching por CO...", len(filas))

    r_co = call_api("GET", "/inventarios/", {
        "agrupar_por": "co", "limit": 100,
        "orden": "desc", "ordenar_por": "cantidad",
    }, timeout=REQUEST_TIMEOUT_SLOW)
    cos = _extraer_filas(r_co)

    if len(cos) <= 1:
        return filas

    agrupar = p.get("agrupar_por", "producto")
    acumuladas = defaultdict(lambda: {"cantidad": 0.0})

    for co in cos:
        id_co = str(co.get("id_co", ""))
        if not id_co:
            continue
        lote_params = dict(p)
        lote_params["id_co"] = str(id_co).zfill(3)
        lote_params["limit"] = _API_LIMIT

        lote_filas = _extraer_filas(
            call_api("GET", "/inventarios/", lote_params, timeout=REQUEST_TIMEOUT_SLOW))

        for f in lote_filas:
            # Clave compuesta: producto + dimension de agrupacion
            partes = [str(f.get("id_producto", f.get("producto", "")))]
            for dim in agrupar.split(","):
                val = str(f.get(dim, f.get(f"id_{dim}", "")))
                if val and dim != "producto":
                    partes.append(val)
            key = "|".join(partes)

            acumuladas[key]["cantidad"] += float(f.get("cantidad", 0) or 0)
            for campo in f:
                if campo not in acumuladas[key] and campo != "cantidad":
                    acumuladas[key][campo] = f.get(campo, "")

    _logger.info("Batching: %d COs → %d items unicos", len(cos), len(acumuladas))

    return [dict({"cantidad": d["cantidad"]}, **{k: v for k, v in d.items() if k != "cantidad"})
            for d in acumuladas.values()]


def inventario_por_bodega(id_co: Optional[str] = None,
                           limit: int = 30,
                           orden: str = "desc") -> dict:
    """Stock agrupado por bodega. Batching automatico si hay mas de 500 bodegas."""
    import json as _json

    params = {"agrupar_por": "bodega", "orden": orden, "ordenar_por": "cantidad"}
    if id_co:
        params["id_co"] = str(id_co).zfill(3)

    filas = _descargar_lotes(params)

    if not filas:
        return {"status": "success", "content": [{"text": "Sin datos de inventario por bodega."}]}

    filas.sort(key=lambda x: float(x.get("cantidad", 0) or 0), reverse=(orden == "desc"))
    total_cantidad = sum(float(f.get("cantidad", 0) or 0) for f in filas)
    items = [{
        "id_bodega": str(f.get("id_bodega", "")),
        "bodega": (f.get("bodega") or "").strip(),
        "cantidad": f.get("cantidad", 0),
    } for f in filas]

    top_n = items[:limit]
    encabezado = (
        f"Inventario por bodega" + (f" (CO {id_co})" if id_co else "") + f": "
        f"{len(items)} bodegas, {total_cantidad:,.0f} unidades totales"
        + (f" (top {len(top_n)} mostradas)" if len(items) > limit else "")
        + "."
    )

    return {"status": "success", "content": [
        {"text": encabezado},
        {"text": _json.dumps({
            "agrupacion": "bodega", "id_co": id_co,
            "total_bodegas": len(items), "total_unidades": total_cantidad,
            "bodegas": top_n,
        }, ensure_ascii=False)}
    ]}


def inventario_por_centro(limit: int = 30,
                           orden: str = "desc") -> dict:
    """Stock agrupado por centro de operacion. Tipicamente < 100 COs, no requiere batching."""
    import json as _json

    filas = _descargar_lotes({
        "agrupar_por": "co", "orden": orden, "ordenar_por": "cantidad",
    })

    if not filas:
        return {"status": "success", "content": [{"text": "Sin datos de inventario por centro."}]}

    filas.sort(key=lambda x: float(x.get("cantidad", 0) or 0), reverse=(orden == "desc"))
    total_cantidad = sum(float(f.get("cantidad", 0) or 0) for f in filas)
    items = [{
        "id_co": str(f.get("id_co", "")),
        "co": (f.get("co") or "").strip(),
        "ciudad": (f.get("ciudad") or "").strip(),
        "cantidad": f.get("cantidad", 0),
    } for f in filas]

    top_n = items[:limit]
    encabezado = (
        f"Inventario por centro: {len(items)} COs, {total_cantidad:,.0f} und totales"
        + (f" (top {len(top_n)} mostrados)" if len(items) > limit else "")
        + "."
    )

    return {"status": "success", "content": [
        {"text": encabezado},
        {"text": _json.dumps({
            "agrupacion": "co", "total_centros": len(items), "total_unidades": total_cantidad,
            "centros": top_n,
        }, ensure_ascii=False)}
    ]}


def rotacion_articulos(q: Optional[str] = None,
                        id_co: Optional[str] = None,
                        limit: int = 30,
                        orden: str = "desc") -> dict:
    """Ranking de productos por stock. Batching por CO si hay >500 productos."""
    import json as _json

    params = {"orden": orden, "ordenar_por": "cantidad"}
    if q:
        params["q"] = q
    if id_co:
        params["id_co"] = str(id_co).zfill(3)

    filas = _descargar_lotes(params)

    if not filas:
        msg = f"Sin datos de inventario para '{q}'." if q else "Sin datos de inventario."
        return {"status": "success", "content": [{"text": msg}]}

    filas.sort(key=lambda x: float(x.get("cantidad", 0) or 0), reverse=(orden == "desc"))
    total_cantidad = sum(float(f.get("cantidad", 0) or 0) for f in filas)
    items = [{
        "id_producto": f.get("id_producto", ""),
        "producto": (f.get("producto") or "").strip(),
        "referencia": (f.get("referencia") or "").strip(),
        "cantidad": f.get("cantidad", 0),
    } for f in filas]

    top_n = items[:limit]
    encabezado = (
        f"Inventario por producto" + (f" (CO {id_co})" if id_co else "") +
        (f" '{q}'" if q else "") + f": "
        f"{len(items)} productos, {total_cantidad:,.0f} und totales"
        + (f" (top {len(top_n)} mostrados)" if len(items) > limit else "")
        + "."
    )

    return {"status": "success", "content": [
        {"text": encabezado},
        {"text": _json.dumps({
            "filtro": q, "id_co": id_co,
            "total_productos": len(items), "total_unidades": total_cantidad,
            "productos": top_n,
        }, ensure_ascii=False)}
    ]}


def inventario_productos_por_bodega(nombre_bodega: Optional[str] = None,
                                      id_bodega: Optional[str] = None,
                                      limit: int = 30,
                                      orden: str = "desc") -> dict:
    """Productos en una bodega especifica. Batching por CO si hay >500 productos."""
    import json as _json

    params = {"agrupar_por": "producto,bodega", "orden": orden, "ordenar_por": "cantidad"}
    if nombre_bodega:
        params["nombre_bodega"] = nombre_bodega
    if id_bodega:
        params["id_bodega"] = str(id_bodega).zfill(5)

    filas = _descargar_lotes(params)

    if not filas:
        label = nombre_bodega or id_bodega or ""
        return {"status": "success", "content": [
            {"text": f"Sin datos de inventario para bodega '{label}'."}
        ]}

    filas.sort(key=lambda x: float(x.get("cantidad", 0) or 0), reverse=(orden == "desc"))
    total_cantidad = sum(float(f.get("cantidad", 0) or 0) for f in filas)
    items = [{
        "id_producto": f.get("id_producto", ""),
        "producto": (f.get("producto") or "").strip(),
        "referencia": (f.get("referencia") or "").strip(),
        "id_bodega": str(f.get("id_bodega", "")),
        "bodega": (f.get("bodega") or "").strip(),
        "cantidad": f.get("cantidad", 0),
    } for f in filas]

    label = nombre_bodega or f"ID {id_bodega}" or ""
    top_n = items[:limit]
    encabezado = (
        f"Bodega '{label}': {len(items)} productos, {total_cantidad:,.0f} und totales"
        + (f" (top {len(top_n)} mostrados)" if len(items) > limit else "")
        + "."
    )

    return {"status": "success", "content": [
        {"text": encabezado},
        {"text": _json.dumps({
            "bodega": label, "total_productos": len(items), "total_unidades": total_cantidad,
            "productos": top_n,
        }, ensure_ascii=False)}
    ]}
