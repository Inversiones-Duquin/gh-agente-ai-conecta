"""Endpoints de proveedores: reporte, busqueda, indice."""
import difflib
import json, logging, time
from typing import Optional
from dw_core import call_api, REQUEST_TIMEOUT_SLOW, MAX_ADMIN_LIST_ITEMS

logger = logging.getLogger("dw-proveedores")
_index_cache: Optional[dict] = None
_index_ts: float = 0.0


def obtener_reporte_proveedores(fecha_inicio: Optional[str] = None, fecha_fin: Optional[str] = None,
                                proveedor_id: Optional[str] = None) -> dict:
    """Reporte ventas/inventario/costo x proveedor (plan 007). ATENCION: usa mensaje/datos, NO status/data."""
    return call_api("GET", "/ventas-proveedores/", {"fecha_inicio": fecha_inicio, "fecha_fin": fecha_fin,
                    "proveedor_id": proveedor_id}, timeout=REQUEST_TIMEOUT_SLOW)


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
