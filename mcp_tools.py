# -*- coding: utf-8 -*-
"""Herramientas del agente: MCP Gateway, Knowledge Base y utilidades."""

import json
import logging
import time
from typing import Any, Dict, List, Optional

from dw_tools import DW_TOOLS
from mcp_gateway_client import MCPGatewayClient
from strands import tool

logger = logging.getLogger("bedrock-agentcore-agent")

# ---------------------------------------------------------------------------
# Estado global del módulo
# ---------------------------------------------------------------------------
mcp_client: Optional[MCPGatewayClient] = None

_tools_cache: Optional[List[Dict[str, Any]]] = None
_tools_cache_ts: float = 0.0
_TOOLS_CACHE_TTL = 300  # 5 minutos


# ---------------------------------------------------------------------------
# Inicialización
# ---------------------------------------------------------------------------


def init_mcp_client(gateway_id: str, region: str) -> Optional[MCPGatewayClient]:
    """Inicializa (o retorna) el cliente MCP Gateway."""
    global mcp_client
    if mcp_client is not None:
        return mcp_client
    try:
        mcp_client = MCPGatewayClient(gateway_id, region)
        logger.info("MCP Gateway inicializado: %s", gateway_id)
    except Exception as e:
        logger.warning("MCP Gateway no disponible (se continúa sin MCP): %s", e)
        mcp_client = None
    return mcp_client


# ---------------------------------------------------------------------------
# Herramientas @tool
# ---------------------------------------------------------------------------


@tool
def mcp_call_tool(tool_name: str, arguments: Optional[Dict[str, Any]] = None) -> dict:
    """Ejecuta una herramienta del gateway MCP externo.

    Revisa en el system prompt la lista de herramientas MCP disponibles antes
    de usar esta función. Usa el nombre exacto de la herramienta (sin prefijo).

    #Args:
        tool_name: Nombre exacto de la herramienta MCP a ejecutar (sin 'mcp_').
        arguments: Diccionario con los argumentos de la herramienta.

    #Returns:
        Resultado de la herramienta MCP en formato JSON.
    """
    if mcp_client is None:
        return {"status": "error", "content": [{"text": "MCP Gateway no disponible"}]}

    args = arguments or {}
    logger.info("MCP call: %s", tool_name)
    result = mcp_client.call_tool(tool_name, args)

    if "error" in result:
        return {
            "status": "error",
            "content": [{"text": f"Error en MCP {tool_name}: {result['error']}"}],
        }

    return {
        "status": "success",
        "content": [{"text": MCPGatewayClient.format_tool_result(result)}],
    }


@tool
def mcp_list_available_tools() -> dict:
    """Lista las herramientas disponibles en el gateway MCP externo.

    Útil para descubrir capacidades antes de usar mcp_call_tool.

    #Returns:
        Lista de herramientas con nombre, descripción y si tienen inputSchema.
    """
    if mcp_client is None:
        return {"status": "error", "content": [{"text": "MCP Gateway no disponible"}]}

    tools = mcp_client.list_tools(force_refresh=True)
    simplified = [
        {
            "name": t.get("name"),
            "description": t.get("description", ""),
            "has_input_schema": bool(t.get("inputSchema")),
        }
        for t in tools
    ]

    return {
        "status": "success",
        "content": [{"text": json.dumps(simplified, ensure_ascii=False, indent=2)}],
    }


# ---------------------------------------------------------------------------
# Integración con el agente
# ---------------------------------------------------------------------------


def get_mcp_tool_specs(force_refresh: bool = False) -> List[Dict[str, Any]]:
    """Tool specs cacheadas de las herramientas MCP para el system prompt."""
    global _tools_cache, _tools_cache_ts

    if mcp_client is None:
        return []

    now = time.time()
    if (
        not force_refresh
        and _tools_cache is not None
        and (now - _tools_cache_ts) < _TOOLS_CACHE_TTL
    ):
        return _tools_cache

    try:
        raw = mcp_client.list_tools(force_refresh=force_refresh)
        specs = []
        for t in raw:
            name = t.get("name", "desconocida")
            specs.append({
                "toolSpec": {
                    "name": f"mcp_{name}",
                    "description": t.get("description", f"Herramienta MCP: {name}"),
                    "inputSchema": {"json": t.get("inputSchema", {})},
                }
            })
        _tools_cache = specs
        _tools_cache_ts = now
        logger.info("MCP tool specs cacheadas: %d", len(specs))
        return specs
    except Exception as e:
        logger.error("Error obteniendo MCP tool specs: %s", e)
        return _tools_cache or []


def build_mcp_prompt_section() -> str:
    """Sección de system prompt con las herramientas MCP disponibles."""
    specs = get_mcp_tool_specs()
    if not specs:
        return ""

    lines = ["\nHerramientas MCP externas disponibles:"]
    for s in specs:
        ts = s["toolSpec"]
        desc = ts.get("description", "")
        if len(desc) > 200:
            desc = desc[:197] + "..."
        lines.append(f"- {ts['name']}: {desc}")
    return "\n".join(lines)


def get_agent_tools() -> list:
    """Devuelve la lista de herramientas @tool para pasar al Agent.

    Incluye las 12 herramientas directas del DW (dw_*) más las herramientas
    MCP para tool discovery y fallback.
    """
    return DW_TOOLS + [mcp_call_tool, mcp_list_available_tools]
