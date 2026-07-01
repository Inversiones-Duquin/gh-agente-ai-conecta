"""Endpoints de proveedores: reporte, busqueda, indice."""
import difflib
import json, logging, time
from typing import Optional
from i2dw.dw_core import call_api, REQUEST_TIMEOUT_SLOW, MAX_ADMIN_LIST_ITEMS

logger = logging.getLogger("dw-proveedores")
_index_cache: Optional[dict] = None
_index_ts: float = 0.0


def obtener_reporte_proveedores(fecha_inicio: Optional[str] = None, fecha_fin: Optional[str] = None,
                                proveedor_id: Optional[str] = None) -> dict:
    """Reporte ventas/inventario/costo x proveedor (plan 007)."""
    return call_api("GET", "/ventas-proveedores/", {"fecha_inicio": fecha_inicio, "fecha_fin": fecha_fin,
                    "proveedor_id": proveedor_id}, timeout=REQUEST_TIMEOUT_SLOW)

def reporte_proveedor_consolidado(fecha_inicio: Optional[str] = None, fecha_fin: Optional[str] = None,
                                   proveedor_id: Optional[str] = None) -> dict:
    """Reporte consolidado sin desglose diario."""
    return call_api("GET", "/ventas-proveedores/consolidado", {"fecha_inicio": fecha_inicio,
                    "fecha_fin": fecha_fin, "proveedor_id": proveedor_id})

def productos_estancados(proveedor_id: Optional[str] = None, fecha_corte: Optional[str] = None) -> dict:
    """Productos con stock que no han vendido recientemente."""
    return call_api("GET", "/ventas-proveedores/venta-cero",
                    {"fecha_fin": fecha_corte, "proveedor_id": proveedor_id})

def reporte_proveedor_top(limite: int, fecha_inicio: str, fecha_fin: str,
                           proveedor_id: str, ordenar_por: str = "cantidad") -> dict:
    """Top productos de un proveedor."""
    return call_api("GET", "/ventas-proveedores/", {"top": limite, "fecha_inicio": fecha_inicio,
                    "fecha_fin": fecha_fin, "proveedor_id": proveedor_id, "ordenar_por": ordenar_por})

def reporte_proveedor_categoria(fecha_inicio: str, fecha_fin: str, proveedor_id: str) -> dict:
    """Ventas de proveedor agrupadas por categoria."""
    return call_api("GET", "/ventas-proveedores/", {"agrupar_por": "categoria",
                    "fecha_inicio": fecha_inicio, "fecha_fin": fecha_fin, "proveedor_id": proveedor_id})

def reporte_proveedor_rotacion(fecha_inicio: str, fecha_fin: str, proveedor_id: str) -> dict:
    """Rotacion de inventario de un proveedor."""
    return call_api("GET", "/ventas-proveedores/", {"modo": "rotacion",
                    "fecha_inicio": fecha_inicio, "fecha_fin": fecha_fin, "proveedor_id": proveedor_id})

def reporte_proveedor_comparar(fecha_inicio: str, fecha_fin: str, proveedor_id: str, comparar_con: str) -> dict:
    """Compara ventas de proveedor entre dos periodos."""
    return call_api("GET", "/ventas-proveedores/", {"fecha_inicio": fecha_inicio, "fecha_fin": fecha_fin,
                    "proveedor_id": proveedor_id, "comparar_con": comparar_con})


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
