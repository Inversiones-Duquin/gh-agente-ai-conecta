"""Cliente HTTP para la API i2d_dw — token, config, GET requests."""
import json, os, logging
import boto3, requests

logger = logging.getLogger(__name__)

BASE_URL = os.getenv("DW_API_BASE_URL", "https://api.inversionesduquin.online/api/v2")
REGION = os.getenv("AWS_REGION", "us-east-2")
SECRET_NAME = os.getenv("DW_API_SECRET_NAME", "")

_token_cache = None


def get_token():
    """Obtiene Bearer token desde Secrets Manager o env var DW_API_TOKEN."""
    global _token_cache
    if _token_cache:
        return _token_cache
    env_token = os.getenv("DW_API_TOKEN", "")
    if env_token:
        _token_cache = env_token
        return _token_cache
    sm = boto3.client("secretsmanager", region_name=REGION)
    secret = json.loads(sm.get_secret_value(SecretId=SECRET_NAME)["SecretString"])
    _token_cache = secret.get("pat") or secret.get("api_key") or secret.get("token")
    return _token_cache


def api_get(path, params=None):
    """GET request a la API i2d_dw con Bearer token."""
    token = get_token()
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    r = requests.get(f"{BASE_URL}{path}", headers=headers, params=params, timeout=120)
    r.raise_for_status()
    return r.json()
