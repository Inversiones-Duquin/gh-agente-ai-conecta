"""Endpoint de validacion de tokens."""
from i2dw.dw_core import call_api

def validate_token() -> dict:
    """Valida PAT y retorna user_id, username, role, session, permissions."""
    return call_api("POST", "/auth/validate")
