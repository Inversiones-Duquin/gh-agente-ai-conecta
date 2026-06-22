# -*- coding: utf-8 -*-
"""Funciones auxiliares para parsing de payload y logging."""

import json
import logging
from typing import Any, Dict

logger = logging.getLogger("bedrock-agentcore-agent")


def extract_prompt_and_session(payload: Dict[str, Any]) -> tuple:
    """Extrae prompt y sessionId soportando múltiples formatos de payload.

    Formatos:
      - Nivel superior: payload["prompt"], payload["sessionId"]
      - Anidado: payload["data"]["text"], payload["data"]["sessionId"]
      - AgentCore directo: payload["inputText"]

    Returns:
        Tupla (prompt: str, session_id: str).
    """
    prompt = None
    session_id = None

    # Prompt
    if "prompt" in payload:
        prompt = payload.get("prompt", "")
    elif "inputText" in payload:
        prompt = payload.get("inputText", "")
    elif "data" in payload and isinstance(payload.get("data"), dict):
        prompt = payload["data"].get("text", "")

    # SessionId
    if "sessionId" in payload:
        session_id = payload.get("sessionId", "default")
    elif "data" in payload and isinstance(payload.get("data"), dict):
        session_id = payload["data"].get("sessionId", "default")

    if prompt is None:
        prompt = ""
    if not session_id:
        session_id = "default"

    return prompt, session_id


def log_payload_debug(payload: Dict[str, Any]) -> None:
    """Registra información detallada del payload para depuración."""
    logger.debug("Tipo de payload: %s", type(payload))
    logger.debug("Claves disponibles: %s", list(payload.keys()))

    try:
        logger.debug(
            "Payload completo (JSON):\n%s",
            json.dumps(payload, indent=2, ensure_ascii=False),
        )
    except Exception:
        logger.debug("Payload completo (str): %s", str(payload))
