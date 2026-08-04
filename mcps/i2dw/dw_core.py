# -*- coding: utf-8 -*-
"""Core del cliente DW: config, token, HTTP helper."""
import json, logging, os, time
from typing import Any, Dict, Optional

import requests
from botocore.exceptions import BotoCoreError, ClientError
from aws_clients import get_secrets_client
from i2dw.dw_errors import error_response

logger = logging.getLogger("dw-core")

BASE_URL = os.getenv("DW_API_BASE_URL", "https://api.inversionesduquin.online")
API_PREFIX = "/api/v2"
SECRET_NAME = os.getenv("DW_API_SECRET_NAME", "")
TOKEN_TTL = 1500
REQUEST_TIMEOUT = 120
REQUEST_TIMEOUT_SLOW = 120
MAX_RESPONSE_CHARS = 500000
MAX_LIST_ITEMS = 5000
MAX_ADMIN_LIST_ITEMS = 5000

_token_cache: Optional[str] = None
_token_loaded_at: float = 0.0


def get_token(region: str = "us-east-2") -> str:
    """Obtiene Bearer token desde Secrets Manager (clave 'pat') o env var DW_API_TOKEN."""
    global _token_cache, _token_loaded_at
    now = time.time()
    if _token_cache and (now - _token_loaded_at) < TOKEN_TTL:
        return _token_cache

    env_token = os.getenv("DW_API_TOKEN", "")
    if env_token:
        _token_cache = env_token; _token_loaded_at = now
        logger.info("Token desde env DW_API_TOKEN"); return _token_cache

    try:
        client = get_secrets_client(region)
        resp = client.get_secret_value(SecretId=SECRET_NAME)
        secret_str = resp.get("SecretString", "").strip()
        try:
            secret = json.loads(secret_str)
        except json.JSONDecodeError:
            _token_cache = secret_str; _token_loaded_at = now; return _token_cache
        token = secret.get("pat") or secret.get("api_key") or secret.get("token")
        if not token:
            raise ValueError(f"Token no encontrado. Keys: {list(secret.keys())}")
        _token_cache = token; _token_loaded_at = now
        logger.info("Token cargado desde Secrets Manager"); return _token_cache
    except (BotoCoreError, ClientError) as e:
        logger.error("Error token: %s", e)
        if _token_cache: return _token_cache
        raise


def call_api(method: str, path: str, params: Optional[Dict[str, Any]] = None,
             body: Optional[Dict[str, Any]] = None, timeout: int = REQUEST_TIMEOUT,
             max_items: int = MAX_LIST_ITEMS, max_chars: int = MAX_RESPONSE_CHARS) -> Dict[str, Any]:
    """Llama endpoint i2d_dw con Bearer token, trunca y limita arrays."""
    token = get_token()
    url = f"{BASE_URL}{API_PREFIX}{path}"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    clean_params = {k: v for k, v in (params or {}).items() if v is not None} if params else None

    try:
        if method == "GET":
            resp = requests.get(url, headers=headers, params=clean_params, timeout=timeout)
        elif method == "POST":
            headers["Content-Type"] = "application/json"
            resp = requests.post(url, headers=headers, params=clean_params, json=body or {}, timeout=timeout)
        else:
            return {"status": "error", "content": [{"text": f"Metodo no soportado: {method}"}]}

        try:
            data = resp.json()
        except json.JSONDecodeError:
            data = {"status": "error", "content": [{"text": resp.text}]}

        # Rate limit: reintentar hasta 3 veces con backoff
        if resp.status_code == 429:
            for attempt in range(3):
                wait = (attempt + 1) * 30
                logger.warning("Rate limit 429 en %s %s - esperando %ds (intento %d/3)", method, path, wait, attempt + 1)
                time.sleep(wait)
                resp = requests.get(url, headers=headers, params=clean_params, timeout=timeout) if method == "GET" else \
                       requests.post(url, headers=headers, params=clean_params, json=body or {}, timeout=timeout)
                if resp.status_code != 429:
                    try: data = resp.json()
                    except json.JSONDecodeError: data = {"status": "error", "content": [{"text": resp.text}]}
                    break
            if resp.status_code == 429:
                return error_response("RATE_LIMITED", method=method, path=path)

        if resp.status_code >= 400:
            detail = data.get("detail", data.get("message", str(data)))
            logger.error("API error %s %s -> %s: %s", method, path, resp.status_code, detail)
            err_map = {400: "BAD_REQUEST", 401: "UNAUTHORIZED", 403: "FORBIDDEN",
                       404: "NOT_FOUND", 500: "SERVER_ERROR", 503: "SERVICE_UNAVAILABLE"}
            name = err_map.get(resp.status_code, "SERVER_ERROR")
            return error_response(name, method=method, path=path, status=resp.status_code)

        # Truncar arrays
        total_items = 0; array_key_found = None
        if isinstance(data, list):
            total_items = len(data); data = {"data": data}; array_key_found = "data"
        elif isinstance(data, dict):
            for key in ("datos", "data", "items"):
                if key in data and isinstance(data[key], list):
                    total_items = len(data[key]); array_key_found = key; break

        if array_key_found and total_items > max_items:
            data[array_key_found] = data[array_key_found][:max_items]
            data["_truncado"] = True; data["_total_registros"] = total_items; data["_mostrados"] = max_items

        text = json.dumps(data, ensure_ascii=False)

        while len(text) > max_chars and array_key_found and len(data.get(array_key_found, [])) > 5:
            keep = max(5, len(data[array_key_found]) // 2)
            data[array_key_found] = data[array_key_found][:keep]
            data["_truncado"] = True; data["_total_registros"] = total_items; data["_mostrados"] = keep
            text = json.dumps(data, ensure_ascii=False)

        if len(text) > max_chars:
            text = text[:max_chars - 20] + '..."}}'

        return {"status": "success", "content": [{"text": text}]}

    except requests.exceptions.Timeout:
        return error_response("TIMEOUT", method=method, path=path)
    except requests.exceptions.ConnectionError as e:
        return error_response("CONNECTION_ERROR", method=method, path=path, detail=str(e))
    except Exception as e:
        return error_response("INTERNAL_ERROR", method=method, path=path, detail=str(e))


def download_all(path: str, params: dict, *,
                 key_field: str = "id_producto",
                 timeout: int = None) -> list:
    """Descarga TODOS los items de un endpoint usando batching por fecha.
    Sin limit — el API devuelve todo. Si el periodo es largo, divide en semanas
    y acumula deduplicando por key_field."""
    import json as _json
    from datetime import datetime, timedelta

    timeout = timeout or REQUEST_TIMEOUT_SLOW

    # Parsear rango de fechas
    fd = params.get("fecha_desde") or params.get("fecha_inicio") or ""
    fh = params.get("fecha_hasta") or params.get("fecha_fin") or ""
    try:
        d1 = datetime.strptime(fd, "%Y-%m-%d")
        d2 = datetime.strptime(fh, "%Y-%m-%d")
    except (ValueError, TypeError):
        # Sin fechas: llamada unica con el maximo del API
        p = dict(params)
        p["limit"] = 500
        p["orden"] = "desc"
        r = call_api("GET", path, p, timeout=timeout)
        raw = r.get("content", [{}])[0].get("text", "{}")
        try:
            data = _json.loads(raw)
            return data if isinstance(data, list) else data.get("data", data.get("items", data.get("datos", [])))
        except (_json.JSONDecodeError, TypeError):
            return []

    # Batching por fecha con sub-division si un lote se trunca (500 items exactos)
    acumuladas = {}
    cola = [(d1, d2)]  # (inicio, fin) de cada chunk por procesar

    while cola:
        chunk_start, chunk_end = cola.pop(0)
        chunk_days = (chunk_end - chunk_start).days + 1

        p = dict(params)
        p["fecha_desde" if "fecha_desde" in params else "fecha_inicio"] = chunk_start.strftime("%Y-%m-%d")
        p["fecha_hasta" if "fecha_hasta" in params else "fecha_fin"] = chunk_end.strftime("%Y-%m-%d")
        p["limit"] = 500  # Maximo que acepta el API
        p["orden"] = "desc"

        r = call_api("GET", path, p, timeout=timeout)
        raw = r.get("content", [{}])[0].get("text", "{}")
        try:
            data = _json.loads(raw)
            filas = data if isinstance(data, list) else data.get("data", data.get("items", data.get("datos", [])))
        except (_json.JSONDecodeError, TypeError):
            filas = []

        # Si se trunca (exacto 500 items) y el rango es > 1 dia, sub-dividir
        if len(filas) >= 500 and chunk_days > 1:
            mid = chunk_start + timedelta(days=chunk_days // 2)
            cola.insert(0, (mid, chunk_end))
            cola.insert(0, (chunk_start, mid - timedelta(days=1)))
            continue

        for f in filas:
            key = str(f.get(key_field, f.get("id_co", f.get("id_bodega", f.get("id_item", "")))))
            if key not in acumuladas:
                acumuladas[key] = dict(f)
            else:
                for campo in ("cantidad", "venta_neta", "neto", "margen", "cant_vendida",
                              "cantidad_inv", "cantidad_vendida", "costo", "venta_costo"):
                    if campo in f and campo in acumuladas[key]:
                        try:
                            acumuladas[key][campo] = float(acumuladas[key].get(campo, 0) or 0) + float(f.get(campo, 0) or 0)
                        except (ValueError, TypeError):
                            pass

    return list(acumuladas.values())
