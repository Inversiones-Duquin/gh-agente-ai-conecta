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
MODEL_ID = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
INFERENCE_PROFILE_ID = "us.anthropic.claude-haiku-4-5-20251001-v1:0"

# Ruteo por complejidad
MODEL_NOVA_MICRO = "us.amazon.nova-micro-v1:0"                    # Orquestador (gratis/casi)
MODEL_HAIKU = "us.anthropic.claude-haiku-4-5-20251001-v1:0"       # Baja complejidad
MODEL_SONNET = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"     # Alta complejidad

# Prompt del clasificador (sin herramientas, solo clasifica la intencion)
CLASSIFIER_PROMPT = """Clasifica la solicitud del usuario en EXACTAMENTE una categoria. Responde SOLO con la palabra clave.

Categorias:
- greeting: Saludo, agradecimiento, despedida, "hola", "gracias", "como estas", ayuda basica.
- report: Reporte de ventas, KPIs, top productos, ranking, comparativas, inventario, rotacion, Excel, PDF.
- analysis: Analisis gerencial, explicacion compleja, recomendacion estrategica, diagnostico, "por que", "como mejorar".
- large: Solicitud muy amplia o sin filtros (ej: "dame todas las ventas", "todo el año", "todos los productos")."""

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

REPORTS_GATEWAY_ID = os.getenv("REPORTS_GATEWAY_ID",
                               "reports-gateway-yt5gh2old4")
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
    """[LLAMAR SIEMPRE PRIMERO] Retorna la fecha actual y el ULTIMO_MES_COMPLETO pre-calculado.
    Para 'ultimo mes' o 'mes pasado' usa las fechas que aparecen en ULTIMO_MES_COMPLETO.
    NO calcules fechas manualmente — usa los valores exactos de esta herramienta."""
    import json
    from datetime import datetime, timedelta
    hoy = datetime.now()

    # Inicio y fin de periodos comunes
    inicio_mes_actual = hoy.replace(day=1)
    fin_mes_anterior = inicio_mes_actual - timedelta(days=1)
    inicio_mes_anterior = fin_mes_anterior.replace(day=1)
    inicio_semana = hoy - timedelta(days=hoy.weekday())
    inicio_trimestre = hoy.replace(month=((hoy.month - 1) // 3) * 3 + 1, day=1)

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


@tool
def generar_reporte_comparativo(id_co: int, fecha_desde_1: str,
                                fecha_hasta_1: str, fecha_desde_2: str,
                                fecha_hasta_2: str) -> dict:
    """Genera reporte HTML comparativo entre dos periodos. KPIs duales, graficos overlay, tabla con variacion %.
    USA para: 'compara junio vs mayo', 'reporte comparativo Bazurto', 'como vamos vs mes pasado'.

    Args:
        id_co: ID del centro de operaciones (ej: 1 para Bazurto).
        fecha_desde_1: Inicio periodo actual YYYY-MM-DD.
        fecha_hasta_1: Fin periodo actual YYYY-MM-DD.
        fecha_desde_2: Inicio periodo anterior YYYY-MM-DD.
        fecha_hasta_2: Fin periodo anterior YYYY-MM-DD.

    Retorna URL de descarga del reporte comparativo."""
    try:
        return _invoke_reports_lambda(
            "generar_reporte_comparativo", {
                "id_co": id_co,
                "fecha_desde_1": fecha_desde_1,
                "fecha_hasta_1": fecha_hasta_1,
                "fecha_desde_2": fecha_desde_2,
                "fecha_hasta_2": fecha_hasta_2,
            })
    except Exception as e:
        logger.error("Error generando reporte comparativo: %s", e)
        return {
            "status": "error",
            "content": [{
                "text": "El servicio de reportes no esta disponible."
            }]
        }


# =============================================================================
# Clasificador de solicitudes — decide que modelo usar
# =============================================================================
def classify_request(prompt: str) -> tuple:
    """Clasifica la solicitud con Nova Lite (rapido, barato).
    Retorna (categoria, modelo_sugerido)."""
    import boto3 as _boto3
    try:
        br = _boto3.client("bedrock-runtime", region_name=REGION)
        resp = br.converse(
            modelId=MODEL_NOVA_MICRO,
            messages=[{
                "role": "user",
                "content": [{
                    "text": prompt
                }]
            }],
            system=[{
                "text": CLASSIFIER_PROMPT
            }],
            inferenceConfig={
                "maxTokens": 10,
                "temperature": 0.0
            },
        )
        category = resp["output"]["message"]["content"][0]["text"].strip(
        ).lower()
        # Normalizar
        if "greeting" in category:
            return ("greeting", MODEL_HAIKU)
        elif "report" in category:
            return ("report", MODEL_SONNET)      # Alta complejidad
        elif "analysis" in category:
            return ("analysis", MODEL_SONNET)    # Alta complejidad
        elif "large" in category:
            return ("large", None)
        else:
            return ("report", MODEL_HAIKU)       # Default: baja complejidad
    except Exception as e:
        logger.warning("Clasificador fallo: %s — usando Haiku", e)
        return ("report", MODEL_HAIKU)


# =============================================================================
# Resiliencia — sanitizacion, retry, fallback
# =============================================================================
import re
import uuid as _uuid

TOOL_ID_PATTERN = re.compile(r'^[a-zA-Z0-9_-]+$')
MAX_RETRIES = 3
BACKOFF_BASE = 1


def _is_session_toxic(session_mgr, session_id) -> bool:
    """Detecta sesiones problematicas: >10 eventos o tool calls huerfanas.
    Sesiones con muchos reintentos fallidos se vuelven toxicas para ConverseStream."""
    try:
        events = session_mgr.repository.get(session_id, [])
        total = len(events)
        tool_uses = sum(1 for e in events if any("toolUse" in b for b in e.get("content", [])))
        tool_results = sum(1 for e in events if any("toolResult" in b for b in e.get("content", [])))
        # Si hay mas toolUse que toolResult → huerfano → sesion toxica
        # O si hay >10 eventos (muchos reintentos fallidos)
        return total > 10 or tool_uses > tool_results
    except Exception:
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


def _invoke_agent_with_retry(agent, prompt, model_id):
    """Invoca el agente con 3 niveles de defensa:
    1. Normal
    2. Retry tras sanitizar tool IDs
    3. Fallback sin tools (solo texto)"""
    import time as _time
    last_error = None

    for attempt in range(MAX_RETRIES):
        try:
            result = agent(prompt)
            return _sanitize_tool_ids(result), None
        except Exception as e:
            last_error = e
            error_str = str(e)

            if "toolUse" in error_str and "toolResult" in error_str:
                logger.warning("Tool ID mismatch — retry %d/%d", attempt + 1, MAX_RETRIES)
                _time.sleep(BACKOFF_BASE ** attempt)
                continue
            elif "Throttling" in error_str or "throttling" in error_str.lower():
                wait = BACKOFF_BASE ** attempt
                logger.warning("Throttled — esperando %ds (intento %d/%d)", wait, attempt + 1, MAX_RETRIES)
                _time.sleep(wait)
                continue
            else:
                break

    # Fallback: si el error persiste, devolver el error
    logger.error("Agente fallo tras %d intentos: %s", MAX_RETRIES, last_error)
    return None, last_error


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

    # Ruteo de modelo segun complejidad
    category, suggested_model = classify_request(prompt)
    logger.info("Clasificacion: '%s' → modelo=%s", category, suggested_model
                or "PEDIR_FILTROS")

    # Solicitud muy amplia → pedir filtros
    if suggested_model is None:
        return {
            "response":
            ("Tu solicitud es muy amplia y puede generar un error por exceso de datos. "
             "Por favor, acota la consulta con alguno de estos filtros:\n"
             "- Un rango de fechas especifico (ej: 'junio 2026', 'ultima semana')\n"
             "- Una tienda o centro de operacion (ej: 'Bazurto', 'Castellana')\n"
             "- Una categoria, marca o proveedor especifico\n"
             "- Un limite de resultados (ej: 'top 10', 'top 20')\n\n"
             "¿Puedes reformular tu consulta?")
        }

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

        # Herramientas
        tools = get_agent_tools() + [
            search_knowledge_base, fecha_actual, generar_reporte_ventas
        ]
        session_mgr = AgentCoreMemorySessionManager(memory_config, REGION)

        # Detectar sesion con tool calls huerfanas de intentos previos fallidos
        if _is_session_toxic(session_mgr, session_id):
            logger.warning("Sesion %s corrupta — creando nueva sesion", session_id)
            session_id = str(_uuid.uuid4())
            memory_config.session_id = session_id
            session_mgr = AgentCoreMemorySessionManager(memory_config, REGION)

        # Modelo seleccionado por el clasificador (o default si fallo)
        model_id = suggested_model or INFERENCE_PROFILE_ID or MODEL_ID

        # System prompt con cache point solo para modelos que lo soportan
        # Claude + Nova: soportan prompt caching nativo en Bedrock
        # Solo Claude y Nova soportan prompt caching en Bedrock
        model_lower = model_id.lower()
        supports_cache = any(m in model_lower for m in ("claude", "nova"))
        if supports_cache:
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
        else:
            cached_system_prompt = [{"text": system_prompt}]

        # Modelo con max_tokens explícito para optimizar cuota (Critical Warning de Bedrock)
        from strands.models.bedrock import BedrockModel
        model = BedrockModel(model_id=model_id, max_tokens=4096, temperature=0)

        agent = Agent(model=model,
                      session_manager=session_mgr,
                      system_prompt=cached_system_prompt,
                      tools=tools)

        logger.info("Ejecutando — model=%s, category=%s, tools=%d", model_id,
                    category, len(tools))

        # Invocar con retry + sanitizacion de tool IDs
        result, agent_error = _invoke_agent_with_retry(agent, prompt, model_id)

        if agent_error is not None:
            raise agent_error

        # Usar AgentResult.__str__() que itera TODOS los content blocks buscando texto
        response_text = str(result).strip()

        if not response_text:
            logger.warning(
                "Respuesta vacia — stop_reason=%s, content_blocks=%d, "
                "prompt_len=%d, session=%s", result.stop_reason,
                len(result.message.get("content", [])), len(prompt),
                session_id)

        # Extraer stats de cache del response
        cache_tokens = 0
        total_tokens = 0
        try:
            usage = result.message.get("usage", {})
            cache_tokens = usage.get("cacheReadInputTokens", 0)
            total_tokens = usage.get("inputTokens", 0)
        except (AttributeError, KeyError, TypeError):
            pass

        cache_pct = f", cache={cache_tokens}/{total_tokens} ({round(cache_tokens/total_tokens*100,1)}%)" if total_tokens > 0 else ""
        logger.info(
            "OK — sessionId=%s, model=%s, category=%s, prompt_len=%d, response_len=%d%s",
            session_id, model_id, category, len(prompt), len(response_text),
            cache_pct)

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
