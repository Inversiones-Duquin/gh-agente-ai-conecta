# -*- coding: utf-8 -*-
"""
Agente conversacional Gigante del Hogar — Bedrock AgentCore + MCP Gateway.

Entrypoint principal que orquesta: memoria, system prompt, herramientas MCP,
Knowledge Base, Data Warehouse y generación de reportes.
"""

import sys
import os

# Necesario para importar los modulos DW (i2dw como paquete + acceso directo)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "mcps"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "mcps", "i2dw"))

import logging
import re
import time
import traceback
import uuid as _uuid
from typing import Optional

from boto3.dynamodb.conditions import Attr

from aws_clients import (
    get_bedrock_agent_runtime,
    get_dynamodb_resource,
)
from bedrock_agentcore.memory.integrations.strands.config import (
    AgentCoreMemoryConfig,
    RetrievalConfig,
)
from bedrock_agentcore.memory.integrations.strands.session_manager import (
    AgentCoreMemorySessionManager, )
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from helpers import extract_prompt_and_session, log_payload_debug
from dw_tools import DW_TOOLS
from prompts import DEFAULT_SYSTEM_PROMPT
from strands import Agent, tool

# =============================================================================
# Logging
# =============================================================================
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("bedrock-agentcore-agent")
logging.getLogger("botocore").setLevel(logging.WARNING)
logging.getLogger("boto3").setLevel(logging.WARNING)

# =============================================================================
# App y configuración
# =============================================================================
app = BedrockAgentCoreApp()

MEMORY_ID = os.getenv("BEDROCK_AGENTCORE_MEMORY_ID")
REGION = os.getenv("AWS_REGION", "us-east-2")
MODEL_ID = "us.anthropic.claude-haiku-4-5-20251001-v1:0"

PROMPT_TABLE = os.getenv("PROMPT_TABLE_NAME", "")
PROMPT_ID = os.getenv("PROMPT_ID", "")
DEFAULT_PROMPT_ID = os.getenv("DEFAULT_PROMPT_ID", "default-dw-sales-v1")
ALLOW_DYNAMODB_SCAN_FOR_DEFAULT = os.getenv("ALLOW_DYNAMODB_SCAN_FOR_DEFAULT",
                                            "").lower() in ("1", "true", "yes",
                                                            "on")
SYSTEM_PROMPT_CACHE_TTL = int(
    os.getenv("SYSTEM_PROMPT_CACHE_TTL_SECONDS", "300"))

KNOWLEDGE_BASE_ID = os.getenv("BEDROCK_KNOWLEDGE_BASE_ID", "PMWZIGLYXK")
RAG_NUM_RESULTS = 10
AGENT_MEMORY_TOP_K = 5

DW_API_SECRET_NAME = os.getenv("DW_API_SECRET_NAME", "gigante/dw-api")
DW_API_TOKEN_TTL = int(os.getenv("DW_API_TOKEN_TTL_SECONDS", "1500"))
DW_API_ID_CIA_DEFAULT = os.getenv("DW_API_ID_CIA_DEFAULT", "1")
DW_API_MAX_ROWS = int(os.getenv("DW_API_MAX_ROWS", "50"))
DW_API_TIMEOUT = int(os.getenv("DW_API_REQUEST_TIMEOUT", "60"))

# =============================================================================
# Estado global — cache del system prompt
# =============================================================================
_prompt_cache: Optional[str] = None
_prompt_source: Optional[str] = None
_prompt_loaded_at: float = 0.0


# =============================================================================
# System prompt desde DynamoDB
# =============================================================================
def _load_prompt_from_dynamodb():
    dynamodb = get_dynamodb_resource(REGION)
    if not dynamodb or not PROMPT_TABLE:
        return None, "dynamodb_not_configured"

    table = dynamodb.Table(PROMPT_TABLE)
    try:
        item_id = (PROMPT_ID or "").strip() or (DEFAULT_PROMPT_ID
                                                or "").strip()
        if item_id:
            item = table.get_item(Key={"Id": item_id}).get("Item")
            if item and str(item.get("prompt", "")).strip():
                return item["prompt"], f"id:{item_id}"
            return None, "prompt_id_not_found" if not item else "prompt_id_empty"

        if not ALLOW_DYNAMODB_SCAN_FOR_DEFAULT:
            return None, "prompt_id_missing"

        # Scan: buscar is_default=true
        scan_kwargs = {
            "FilterExpression":
            Attr("is_default").eq(True)
            | Attr("is_default").eq("true") | Attr("is_default").eq("True")
            | Attr("is_default").eq(1)
        }
        resp = table.scan(**scan_kwargs)
        items = resp.get("Items", [])
        while not items and resp.get("LastEvaluatedKey"):
            resp = table.scan(**scan_kwargs,
                              ExclusiveStartKey=resp["LastEvaluatedKey"])
            items.extend(resp.get("Items", []))

        if items and str(items[0].get("prompt", "")).strip():
            return items[0]["prompt"], "default"
        return None, "default_not_found"
    except Exception as e:
        logger.error("Error DynamoDB prompt: %s\n%s", e,
                     traceback.format_exc())
        return None, "dynamodb_error"


def get_system_prompt() -> str:
    """System prompt con caché TTL + fallback al DEFAULT_SYSTEM_PROMPT."""
    global _prompt_cache, _prompt_source, _prompt_loaded_at

    now = time.time()
    if (SYSTEM_PROMPT_CACHE_TTL > 0 and _prompt_cache
            and (now - _prompt_loaded_at) < SYSTEM_PROMPT_CACHE_TTL):
        return _prompt_cache

    prompt, source = _load_prompt_from_dynamodb()
    if prompt and str(prompt).strip():
        _prompt_cache, _prompt_source, _prompt_loaded_at = prompt, source, now
        logger.debug("Prompt desde DynamoDB (%s)", source)
        return _prompt_cache

    if _prompt_cache:
        logger.warning("Manteniendo prompt en caché (source=%s)",
                       _prompt_source)
        return _prompt_cache

    logger.debug("Usando DEFAULT_SYSTEM_PROMPT (fallback)")
    _prompt_cache, _prompt_source, _prompt_loaded_at = (DEFAULT_SYSTEM_PROMPT,
                                                        "default_fallback",
                                                        now)
    return _prompt_cache


# =============================================================================
# Herramienta: Knowledge Base
# =============================================================================
@tool
def search_knowledge_base(query: str) -> dict:
    """Busca en la base de conocimiento del proyecto AWS.

    Usa esta herramienta para preguntas sobre documentación de procesos, procedimientos, manuales, guías, etc. 
    que estén en la base de conocimiento.

    #Args:
        query: Texto de búsqueda en lenguaje natural.

    #Returns:
        Resultados relevantes de la base de conocimiento.
    """
    bedrock = get_bedrock_agent_runtime(REGION)
    if not bedrock or not KNOWLEDGE_BASE_ID:
        return {
            "status": "error",
            "content": [{
                "text": "Knowledge Base no configurada"
            }]
        }

    try:
        resp = bedrock.retrieve(
            knowledgeBaseId=KNOWLEDGE_BASE_ID,
            retrievalQuery={"text": query},
            retrievalConfiguration={
                "vectorSearchConfiguration": {
                    "numberOfResults": RAG_NUM_RESULTS
                }
            },
        )
        results = resp.get("retrievalResults", [])
        if not results:
            return {
                "status": "success",
                "content": [{
                    "text": "Sin resultados."
                }]
            }

        formatted = []
        for i, r in enumerate(results, 1):
            text = r.get("content", {}).get("text", "")
            loc = r.get("location", "")
            score = r.get("score", 0)
            formatted.append(f"[{i}] (score: {score:.2f}) {loc}\n{text}")

        logger.info("KB consultada: '%s' → %d resultados", query, len(results))
        return {
            "status": "success",
            "content": [{
                "text": "\n\n".join(formatted)
            }]
        }

    except Exception as e:
        logger.error("Error KB: %s", e)
        return {"status": "error", "content": [{"text": f"Error: {e}"}]}


# =============================================================================
# Herramienta: Fecha actual
# =============================================================================
@tool
def fecha_actual() -> dict:
    """[SOLO PARA FECHAS RELATIVAS] Retorna la fecha actual y el ULTIMO_MES_COMPLETO.
    Llama SOLO cuando el usuario NO da fechas explicitas. Si el usuario menciono mes/año, usa SUS fechas.
    Para 'ultimo mes' o 'mes pasado' usa las fechas que aparecen en ULTIMO_MES_COMPLETO.
    NO calcules fechas manualmente — usa los valores exactos de esta herramienta."""
    from datetime import datetime, timedelta
    hoy = datetime.now()

    inicio_mes_actual = hoy.replace(day=1)
    fin_mes_anterior = inicio_mes_actual - timedelta(days=1)
    inicio_mes_anterior = fin_mes_anterior.replace(day=1)

    periodos = {
        "hoy":
        hoy.strftime("%Y-%m-%d"),
        "ayer": (hoy - timedelta(days=1)).strftime("%Y-%m-%d"),
        "ULTIMO_MES_COMPLETO":
        f"{inicio_mes_anterior.strftime('%Y-%m-%d')} a {fin_mes_anterior.strftime('%Y-%m-%d')}",
        "mes_actual":
        f"{inicio_mes_actual.strftime('%Y-%m-%d')} a {hoy.strftime('%Y-%m-%d')}",
    }
    texto = (
        f"Hoy es {periodos['hoy']}. "
        f"Cuando el usuario diga 'ultimo mes', 'mes pasado', 'el mes anterior' usa SIEMPRE: "
        f"fecha_desde={inicio_mes_anterior.strftime('%Y-%m-%d')} y "
        f"fecha_hasta={fin_mes_anterior.strftime('%Y-%m-%d')}. "
        f"NO uses otro mes. "
        f"Ayer fue {periodos['ayer']}. "
        f"Mes actual en curso: {periodos['mes_actual']}.")
    return {"status": "success", "content": [{"text": texto}]}


# =============================================================================
# Herramientas: Reportes (Lambda directa)
# =============================================================================
def _invoke_reports_lambda(tool_name: str, args: dict) -> dict:
    """Llama la Lambda de reportes via boto3."""
    import json, boto3 as _boto3
    payload = {"toolName": tool_name, "arguments": args}
    lam = _boto3.client("lambda", region_name="us-east-2")
    resp = lam.invoke(FunctionName="reports-handler",
                      InvocationType="RequestResponse",
                      Payload=json.dumps(payload))
    result = json.loads(resp["Payload"].read())
    if result.get("isError"):
        return {
            "status":
            "error",
            "content": [{
                "text":
                result.get("content", [{}])[0].get("text", "Error en reporte")
            }]
        }
    return {
        "status":
        "success",
        "content": [{
            "text":
            result.get("content", [{}])[0].get("text", str(result))
        }]
    }


@tool
def generar_reporte_ventas(id_co: int,
                           fecha_desde: str = "",
                           fecha_hasta: str = "") -> dict:
    """Genera reporte HTML interactivo de ventas con graficos Chart.js, KPIs y tabla.

    Args:
        id_co: ID del centro de operaciones (ej: 1 para Bazurto).
        fecha_desde: Fecha inicio YYYY-MM-DD (opcional, default 30 dias atras).
        fecha_hasta: Fecha fin YYYY-MM-DD (opcional, default hoy).

    Retorna URL de descarga del reporte.
    """
    try:
        return _invoke_reports_lambda(
            "generar_reporte_ventas", {
                "id_co": id_co,
                "fecha_desde": fecha_desde or None,
                "fecha_hasta": fecha_hasta or None
            })
    except Exception as e:
        logger.error("Error generando reporte: %s", e)
        return {
            "status": "error",
            "content": [{
                "text": "El servicio de reportes no esta disponible."
            }]
        }


# =============================================================================
# Resiliencia — sanitizacion, retry, fallback
# =============================================================================

TOOL_ID_PATTERN = re.compile(r'^[a-zA-Z0-9_-]+$')
MAX_RETRIES = 3
BACKOFF_BASE = 2


def _is_session_toxic(session_mgr, session_id) -> bool:
    """Detecta sesiones con tool calls huerfanas."""
    try:
        msgs = session_mgr.list_messages(session_id, "default") or []
        tool_uses = 0
        tool_results = 0
        for m in msgs:
            content = m.to_message().get("content", [])
            for b in content:
                if isinstance(b, dict):
                    if "toolUse" in b: tool_uses += 1
                    if "toolResult" in b: tool_results += 1
        return tool_uses > tool_results
    except Exception as e:
        logger.warning("No se pudo verificar sesion: %s", e)
        return False


def _sanitize_tool_ids(result):
    """Reemplaza tool_use IDs invalidos en el resultado del agente.
    Esto previene ValidationException en la siguiente iteracion."""
    try:
        content = result.message.get("content", [])
        for block in content:
            if "toolUse" in block:
                tid = block["toolUse"].get("toolUseId", "")
                if not TOOL_ID_PATTERN.match(tid):
                    new_id = "tool_" + _uuid.uuid4().hex[:8]
                    block["toolUse"]["toolUseId"] = new_id
                    logger.warning("Sanitized tool_use ID: %s -> %s", tid, new_id)
    except Exception:
        pass
    return result


def _invoke_agent_with_retry(agent, prompt):
    """Invoca el agente con retry para throttling y session corruption."""
    last_error = None

    for attempt in range(MAX_RETRIES):
        try:
            result = agent(prompt)
            return _sanitize_tool_ids(result), None
        except Exception as e:
            last_error = e
            error_str = str(e)

            # Session corrupta → señal para nueva sesion
            if "ValidationException" in type(e).__name__ and ("toolUse" in error_str or "toolResult" in error_str):
                logger.warning("Session corrupta (intento %d/%d)", attempt + 1, MAX_RETRIES)
                return None, last_error  # ← caller recrea sesion
            elif "Throttling" in error_str or "throttling" in error_str.lower():
                wait = BACKOFF_BASE ** attempt
                logger.warning("Throttled — esperando %ds (intento %d/%d)", wait, attempt + 1, MAX_RETRIES)
                time.sleep(wait)
                continue
            else:
                break

    logger.error("Agente fallo tras %d intentos: %s", MAX_RETRIES, last_error)
    return None, last_error


# =============================================================================
# Entrypoint
# =============================================================================
@app.entrypoint
def invoke(payload, context):
    """Handler principal — procesa cada solicitud del agente."""

    if payload is None:
        return {"error": "Payload is None"}
    if not isinstance(payload, dict):
        return {"error": f"Invalid payload type: {type(payload)}"}

    log_payload_debug(payload)
    prompt, session_id = extract_prompt_and_session(payload)

    logger.debug("prompt='%s...' (len=%d), sessionId='%s'", prompt[:100],
                 len(prompt), session_id)

    if not prompt or not prompt.strip():
        return {"error": "Prompt vacío"}

    if not MEMORY_ID:
        return {"error": "Memory not configured"}

    try:
        actor_id = (context.headers.get(
            "X-Amzn-Bedrock-AgentCore-Runtime-Custom-Actor-Id", "user")
                    if hasattr(context, "headers") else "user")

        # Memoria con limpieza de tool calls al restaurar sesion
        memory_config = AgentCoreMemoryConfig(
            memory_id=MEMORY_ID,
            session_id=session_id,
            actor_id=actor_id,
            filter_restored_tool_context=True,
            retrieval_config={
                f"/users/{actor_id}/facts":
                RetrievalConfig(top_k=AGENT_MEMORY_TOP_K, relevance_score=0.5),
                f"/users/{actor_id}/preferences":
                RetrievalConfig(top_k=AGENT_MEMORY_TOP_K, relevance_score=0.5),
            },
        )

        system_prompt = [{"text": get_system_prompt()}]

        # Herramientas: DW (24) + KB + fecha + reportes
        tools = DW_TOOLS + [
            search_knowledge_base, fecha_actual, generar_reporte_ventas
        ]
        session_mgr = AgentCoreMemorySessionManager(memory_config, REGION)

        # Modelo unico — sin clasificador
        from strands.models.bedrock import BedrockModel
        model = BedrockModel(model_id=MODEL_ID, max_tokens=4096, temperature=0)

        agent = Agent(model=model,
                      session_manager=session_mgr,
                      system_prompt=system_prompt,
                      tools=tools)

        logger.info("Ejecutando — model=%s, tools=%d", MODEL_ID, len(tools))

        # Invocar con retry + sanitizacion de tool IDs
        result, agent_error = _invoke_agent_with_retry(agent, prompt)

        if agent_error is not None:
            raise agent_error

        response_text = str(result).strip()

        if not response_text:
            logger.warning(
                "Respuesta vacia — stop_reason=%s, content_blocks=%d, "
                "prompt_len=%d, session=%s", result.stop_reason,
                len(result.message.get("content", [])), len(prompt),
                session_id)

        logger.info(
            "OK — sessionId=%s, prompt_len=%d, response_len=%d",
            session_id, len(prompt), len(response_text))

        return {"response": response_text}

    except Exception as e:
        logger.error("Error procesando solicitud: %s\n%s", e,
                     traceback.format_exc())
        return {"error": f"Error procesando la solicitud: {str(e)}"}


# =============================================================================
# Main
# =============================================================================
if __name__ == "__main__":
    app.run()
