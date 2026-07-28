"""Endpoints de inventarios — stock real por producto, bodega y centro."""
from typing import Optional
from i2dw.dw_core import call_api, REQUEST_TIMEOUT_SLOW


def inventario_por_bodega(id_co: Optional[str] = None,
                           limit: int = 30,
                           orden: str = "desc") -> dict:
    """Stock agrupado por bodega. Opcionalmente filtra por CO.
    USA para: 'stock por bodega', 'inventario en bodega X', 'que bodega tiene mas stock?'."""
    import json as _json

    params = {"agrupar_por": "bodega", "limit": limit,
              "orden": orden, "ordenar_por": "cantidad"}
    if id_co:
        params["id_co"] = id_co

    result = call_api("GET", "/inventarios/", params,
                      timeout=REQUEST_TIMEOUT_SLOW)

    raw = result.get("content", [{}])[0].get("text", "{}")
    try:
        data = _json.loads(raw)
        filas = data if isinstance(data, list) else data.get("data", data.get("items", data.get("datos", [])))
    except (_json.JSONDecodeError, TypeError):
        filas = []

    if not filas:
        return {"status": "success", "content": [{"text": "Sin datos de inventario por bodega."}]}

    total_cantidad = sum(float(f.get("cantidad", 0) or 0) for f in filas)
    items = []
    for f in filas:
        items.append({
            "id_bodega": str(f.get("id_bodega", "")),
            "bodega": (f.get("bodega") or "").strip(),
            "cantidad": f.get("cantidad", 0),
        })

    encabezado = (
        f"Inventario por bodega" + (f" (CO {id_co})" if id_co else "") + f": "
        f"{len(items)} bodegas, {total_cantidad:,.0f} unidades totales."
    )

    return {"status": "success", "content": [
        {"text": encabezado},
        {"text": _json.dumps({
            "agrupacion": "bodega",
            "id_co": id_co,
            "total_bodegas": len(items),
            "total_unidades": total_cantidad,
            "bodegas": items,
        }, ensure_ascii=False)}
    ]}


def inventario_por_centro(limit: int = 30,
                           orden: str = "desc") -> dict:
    """Stock agrupado por centro de operacion. Ranking de COs por inventario.
    USA para: 'que tienda tiene mas stock?', 'inventario por tienda', 'ranking de stock por CO'."""
    import json as _json

    result = call_api("GET", "/inventarios/", {
        "agrupar_por": "co", "limit": limit,
        "orden": orden, "ordenar_por": "cantidad",
    }, timeout=REQUEST_TIMEOUT_SLOW)

    raw = result.get("content", [{}])[0].get("text", "{}")
    try:
        data = _json.loads(raw)
        filas = data if isinstance(data, list) else data.get("data", data.get("items", data.get("datos", [])))
    except (_json.JSONDecodeError, TypeError):
        filas = []

    if not filas:
        return {"status": "success", "content": [{"text": "Sin datos de inventario por centro."}]}

    total_cantidad = sum(float(f.get("cantidad", 0) or 0) for f in filas)
    items = []
    for f in filas:
        items.append({
            "id_co": str(f.get("id_co", "")),
            "co": (f.get("co") or "").strip(),
            "ciudad": (f.get("ciudad") or "").strip(),
            "cantidad": f.get("cantidad", 0),
        })

    encabezado = (
        f"Inventario por centro de operacion: "
        f"{len(items)} COs, {total_cantidad:,.0f} unidades totales."
    )

    return {"status": "success", "content": [
        {"text": encabezado},
        {"text": _json.dumps({
            "agrupacion": "co",
            "total_centros": len(items),
            "total_unidades": total_cantidad,
            "centros": items,
        }, ensure_ascii=False)}
    ]}


def rotacion_articulos(q: Optional[str] = None,
                        id_co: Optional[str] = None,
                        limit: int = 30,
                        orden: str = "desc") -> dict:
    """Ranking de productos por cantidad en inventario (stock real).
    USA para: 'productos con mas stock?', 'que articulo tiene mas inventario?',
    'rotacion de inventario', 'productos con menos stock?'.
    q: busqueda por nombre o referencia.
    id_co: filtrar por centro de operacion."""
    import json as _json

    params = {"limit": limit, "orden": orden, "ordenar_por": "cantidad"}
    if q:
        params["q"] = q
    if id_co:
        params["id_co"] = id_co

    result = call_api("GET", "/inventarios/", params,
                      timeout=REQUEST_TIMEOUT_SLOW)

    raw = result.get("content", [{}])[0].get("text", "{}")
    try:
        data = _json.loads(raw)
        filas = data if isinstance(data, list) else data.get("data", data.get("items", data.get("datos", [])))
    except (_json.JSONDecodeError, TypeError):
        filas = []

    if not filas:
        msg = f"Sin datos de inventario para '{q}'." if q else "Sin datos de inventario."
        return {"status": "success", "content": [{"text": msg}]}

    total_cantidad = sum(float(f.get("cantidad", 0) or 0) for f in filas)
    items = []
    for f in filas:
        items.append({
            "id_producto": f.get("id_producto", ""),
            "producto": (f.get("producto") or "").strip(),
            "referencia": (f.get("referencia") or "").strip(),
            "cantidad": f.get("cantidad", 0),
        })

    encabezado = (
        f"Inventario por producto" + (f" (CO {id_co})" if id_co else "") +
        (f" '{q}'" if q else "") + f": "
        f"{len(items)} productos, {total_cantidad:,.0f} unidades totales."
    )

    return {"status": "success", "content": [
        {"text": encabezado},
        {"text": _json.dumps({
            "filtro": q,
            "id_co": id_co,
            "total_productos": len(items),
            "total_unidades": total_cantidad,
            "productos": items,
        }, ensure_ascii=False)}
    ]}
