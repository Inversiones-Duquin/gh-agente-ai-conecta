# -*- coding: utf-8 -*-
"""
Agente conversacional Gigante del Hogar — Bedrock AgentCore + MCP Gateway.

Entrypoint principal que orquesta: memoria, system prompt, herramientas MCP,
Knowledge Base, Data Warehouse y generación de reportes.
"""

import sys
import os

# Necesario para que las librerías (pydantic, strands, dateutil, etc.)
# encuentren six.py y typing_extensions.py que están en /libs
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "libs"))
# Necesario para que los modulos en mcps/ sean importables
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "mcps"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "mcps", "i2dw"))

import logging
import time
import traceback
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
from mcp_tools import (
    build_mcp_prompt_section,
    get_agent_tools,
    init_mcp_client,
)
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
MODEL_ID = "amazon.nova-2-lite-v1:0"
INFERENCE_PROFILE_ID = "us.amazon.nova-2-lite-v1:0"

PROMPT_TABLE = os.getenv("PROMPT_TABLE_NAME", "")
PROMPT_ID = os.getenv("PROMPT_ID", "")
DEFAULT_PROMPT_ID = os.getenv("DEFAULT_PROMPT_ID", "default-dw-sales-v1")
ALLOW_DYNAMODB_SCAN_FOR_DEFAULT = os.getenv("ALLOW_DYNAMODB_SCAN_FOR_DEFAULT",
                                            "").lower() in ("1", "true", "yes",
                                                            "on")
SYSTEM_PROMPT_CACHE_TTL = int(
    os.getenv("SYSTEM_PROMPT_CACHE_TTL_SECONDS", "300"))

KNOWLEDGE_BASE_ID = os.getenv("BEDROCK_KNOWLEDGE_BASE_ID", "9KMNZ8UPF1")
RAG_NUM_RESULTS = 10
AGENT_MEMORY_TOP_K = 5

DW_API_SECRET_NAME = os.getenv("DW_API_SECRET_NAME", "gigante/dw-api")
DW_API_TOKEN_TTL = int(os.getenv("DW_API_TOKEN_TTL_SECONDS", "1500"))
DW_API_ID_CIA_DEFAULT = os.getenv("DW_API_ID_CIA_DEFAULT", "1")
DW_API_MAX_ROWS = int(os.getenv("DW_API_MAX_ROWS", "50"))
DW_API_TIMEOUT = int(os.getenv("DW_API_REQUEST_TIMEOUT", "60"))

REPORTS_GATEWAY_ID = os.getenv("REPORTS_GATEWAY_ID", "reports-gateway-yt5gh2old4")
REPORTS_GATEWAY_REGION = os.getenv("REPORTS_GATEWAY_REGION", "us-east-2")

MCP_GATEWAY_ID = os.getenv("MCP_GATEWAY_ID", "i2d-dw-gateway-lv6e91yj9s")
MCP_GATEWAY_REGION = os.getenv("MCP_GATEWAY_REGION", "us-east-2")

# =============================================================================
# Estado global
# =============================================================================
current_session: Optional[str] = None
_prompt_cache: Optional[str] = None
_prompt_source: Optional[str] = None
_prompt_loaded_at: float = 0.0

# Inicializar MCP (no bloquea si falla)
init_mcp_client(MCP_GATEWAY_ID, MCP_GATEWAY_REGION)


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

    Usa esta herramienta para preguntas sobre documentación del proyecto,
    arquitectura, despliegue, AgentCore, WebSocket, Lambdas, DynamoDB, SQS,
    SNS, prompts o memoria.

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
    """Retorna la fecha actual del sistema. Usa esta herramienta para calcular
    periodos relativos como 'semana pasada', 'este mes', 'ayer', 'ultimos 7 dias', etc.
    No necesitas argumentos.
    """
    import json
    from datetime import datetime
    hoy = datetime.now()
    return {"status": "success", "content": [{"text": json.dumps({
        "fecha": hoy.strftime("%Y-%m-%d"),
        "dia_semana": hoy.strftime("%A"),
        "semana": hoy.isocalendar()[1],
        "mes": hoy.month,
        "ano": hoy.year,
    }, ensure_ascii=False)}]}


# =============================================================================
# Herramientas: Reportes (Lambda directa)
# =============================================================================
def _invoke_reports_lambda(tool_name: str, args: dict) -> dict:
    """Llama la Lambda de reportes via boto3."""
    import json, boto3 as _boto3
    payload = {"toolName": tool_name, "arguments": args}
    lam = _boto3.client("lambda", region_name="us-east-2")
    resp = lam.invoke(FunctionName="reports-handler", InvocationType="RequestResponse", Payload=json.dumps(payload))
    result = json.loads(resp["Payload"].read())
    if result.get("isError"):
        return {"status": "error", "content": [{"text": result.get("content", [{}])[0].get("text", "Error en reporte")}]}
    return {"status": "success", "content": [{"text": result.get("content", [{}])[0].get("text", str(result))}]}


@tool
def generar_reporte_ventas(id_co: int, fecha_desde: str = "", fecha_hasta: str = "") -> dict:
    """Genera reporte HTML interactivo de ventas con graficos Chart.js, KPIs y tabla.

    Args:
        id_co: ID del centro de operaciones (ej: 1 para Bazurto).
        fecha_desde: Fecha inicio YYYY-MM-DD (opcional, default 30 dias atras).
        fecha_hasta: Fecha fin YYYY-MM-DD (opcional, default hoy).

    Retorna URL de descarga del reporte.
    """
    try:
        return _invoke_reports_lambda("generar_reporte_ventas",
            {"id_co": id_co, "fecha_desde": fecha_desde or None, "fecha_hasta": fecha_hasta or None})
    except Exception as e:
        logger.error("Error generando reporte: %s", e)
        return {"status": "error", "content": [{"text": "El servicio de reportes no esta disponible."}]}


# =============================================================================
# Entrypoint
# =============================================================================
@app.entrypoint
def invoke(payload, context):
    """Handler principal — procesa cada solicitud del agente."""
    global current_session

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

    current_session = session_id

    try:
        actor_id = (context.headers.get(
            "X-Amzn-Bedrock-AgentCore-Runtime-Custom-Actor-Id", "user")
                    if hasattr(context, "headers") else "user")

        # Memoria
        memory_config = AgentCoreMemoryConfig(
            memory_id=MEMORY_ID,
            session_id=session_id,
            actor_id=actor_id,
            retrieval_config={
                f"/users/{actor_id}/facts":
                RetrievalConfig(top_k=AGENT_MEMORY_TOP_K, relevance_score=0.5),
                f"/users/{actor_id}/preferences":
                RetrievalConfig(top_k=AGENT_MEMORY_TOP_K, relevance_score=0.5),
            },
        )

        # System prompt + MCP (con prompt caching)
        system_prompt = get_system_prompt()
        mcp_section = build_mcp_prompt_section()
        if mcp_section:
            system_prompt += "\n" + mcp_section

        # Envolver en SystemContentBlock con cache point para reducir costos 90%
        # Nova Lite: min 1,536 tokens para caching → ~6K chars ya califica
        cached_system_prompt = [
            {
                "text": system_prompt
            },
            {
                "cachePoint": {
                    "type": "default"
                }
            },
        ]

        # Herramientas
        tools = get_agent_tools() + [search_knowledge_base, fecha_actual, generar_reporte_ventas]
        session_mgr = AgentCoreMemorySessionManager(memory_config, REGION)
        # Usar inference profile directamente — el model ID base no soporta
        # on-demand throughput y el reintento crea un segundo Agent en la misma
        # sesión, lo cual no está permitido.
        model_id = INFERENCE_PROFILE_ID or MODEL_ID

        # Modelo con max_tokens explícito para optimizar cuota (Critical Warning de Bedrock)
        # Sin max_tokens explícito, Bedrock reserva el máximo del modelo (8K tokens)
        # → desperdicia cuota y puede causar ThrottlingException
        from strands.models.bedrock import BedrockModel
        model = BedrockModel(model_id=model_id, max_tokens=4096)

        agent = Agent(model=model,
                      session_manager=session_mgr,
                      system_prompt=cached_system_prompt,
                      tools=tools)

        logger.debug("Agente ejecutando con modelo=%s, tools=%d", model_id,
                     len(tools))

        result = agent(prompt)

        # Usar AgentResult.__str__() que itera TODOS los content blocks buscando texto
        response_text = str(result).strip()

        if not response_text:
            logger.warning(
                "Respuesta vacia — stop_reason=%s, content_blocks=%d, "
                "prompt_len=%d, session=%s",
                result.stop_reason,
                len(result.message.get("content", [])),
                len(prompt), session_id)

        logger.info(
            "OK — sessionId=%s, model=%s, source=%s, prompt_len=%d, response_len=%d",
            session_id, model_id, _prompt_source, len(prompt),
            len(response_text))

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
