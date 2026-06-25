# -*- coding: utf-8 -*-
"""Core del cliente DW: config, token, HTTP helper."""
import json, logging, os, time
from typing import Any, Dict, Optional

import requests
from botocore.exceptions import BotoCoreError, ClientError
from aws_clients import get_secrets_client

logger = logging.getLogger("dw-core")

BASE_URL = "https://api.inversionesduquin.online"
API_PREFIX = "/api/v2"
SECRET_NAME = "gigante/dw-api"
TOKEN_TTL = 1500
REQUEST_TIMEOUT = 60
REQUEST_TIMEOUT_SLOW = 180
MAX_RESPONSE_CHARS = 12000
MAX_LIST_ITEMS = 30
MAX_ADMIN_LIST_ITEMS = 200

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
                wait = (attempt + 1) * 30  # 30s, 60s, 90s
                logger.warning("Rate limit 429 en %s %s — esperando %ds (intento %d/3)",
                               method, path, wait, attempt + 1)
                time.sleep(wait)
                resp = requests.get(url, headers=headers, params=clean_params, timeout=timeout) if method == "GET" else \
                       requests.post(url, headers=headers, params=clean_params, json=body or {}, timeout=timeout)
                if resp.status_code != 429:
                    try:
                        data = resp.json()
                    except json.JSONDecodeError:
                        data = {"status": "error", "content": [{"text": resp.text}]}
                    break

        if resp.status_code >= 400:
            detail = data.get("detail", data.get("message", str(data)))
            return {"status": "error", "http_status": resp.status_code,
                    "content": [{"text": f"Error {resp.status_code}: {detail}"}]}

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
        logger.error("Timeout %s %s", method, path)
        return {"status": "error", "content": [{"text": "Timeout: API no respondio a tiempo"}]}
    except requests.exceptions.ConnectionError as e:
        logger.error("Conexion %s %s: %s", method, path, e)
        return {"status": "error", "content": [{"text": f"Error de conexion: {e}"}]}
    except Exception as e:
        logger.error("Error %s %s: %s", method, path, e)
        return {"status": "error", "content": [{"text": f"Error: {e}"}]}
