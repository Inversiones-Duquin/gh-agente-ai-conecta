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
_reports_client: Any = None  # HTTP+SigV4 client (bedrock-agentcore-runtime no existe)

_tools_cache: Optional[List[Dict[str, Any]]] = None
_tools_cache_ts: float = 0.0
_TOOLS_CACHE_TTL = 300  # 5 minutos


# ---------------------------------------------------------------------------
# Inicialización
# ---------------------------------------------------------------------------


class _HttpMCPClient:
    """Cliente MCP ligero via HTTP+SigV4 (no usa bedrock-agentcore-runtime)."""
    def __init__(self, gateway_id, region):
        import boto3, requests
        from botocore.auth import SigV4Auth
        from botocore.awsrequest import AWSRequest
        self.gateway_id = gateway_id
        self.region = region
        self.url = f"https://{gateway_id}.gateway.bedrock-agentcore.{region}.amazonaws.com/mcp"
        self.session = boto3.Session(region_name=region)
        self.SigV4Auth = SigV4Auth
        self.AWSRequest = AWSRequest
        self.requests = requests

    def call_tool(self, name, args):
        import json
        creds = self.session.get_credentials()
        body = json.dumps({"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":name,"arguments":args or {}}})
        req = self.AWSRequest(method="POST",url=self.url,data=body,headers={"Content-Type":"application/json"})
        self.SigV4Auth(creds,"bedrock-agentcore",self.region).add_auth(req)
        resp = self.requests.post(self.url,data=body,headers=dict(req.headers),timeout=60)
        data = resp.json()
        if "error" in data:
            return {"error": data["error"].get("message","Error")}
        r = data.get("result",{})
        if r.get("isError"):
            return {"error": r.get("content",[{}])[0].get("text","Error")}
        return r


def init_mcp_client(gateway_id: str, region: str) -> Optional[MCPGatewayClient]:
    """Inicializa los clientes MCP Gateway (i2dw + reports)."""
    global mcp_client, _reports_client
    import os
    if mcp_client is None:
        try:
            mcp_client = MCPGatewayClient(gateway_id, region)
            logger.info("MCP i2dw inicializado: %s", gateway_id)
        except Exception as e:
            logger.warning("MCP i2dw no disponible: %s", e)
    reports_id = os.getenv("REPORTS_GATEWAY_ID", "reports-gateway-yt5gh2old4")
    if _reports_client is None:
        try:
            _reports_client = _HttpMCPClient(reports_id, region)
            logger.info("MCP reports inicializado (HTTP): %s", reports_id)
        except Exception as e:
            logger.warning("MCP reports no disponible: %s", e)
    return mcp_client


# ---------------------------------------------------------------------------
# Herramientas @tool
# ---------------------------------------------------------------------------


@tool
def mcp_call_tool(tool_name: str, arguments: Optional[Dict[str, Any]] = None) -> dict:
    """Llama una herramienta via MCP Gateway. Solo para reportes (generar_reporte_*).

    Para datos (ventas, productos, centros, proveedores) usa las herramientas dw_* directamente.
    Para reportes usa mcp_call_tool con el Gateway de reportes.

    #Args:
        tool_name: Nombre de la herramienta MCP (ej: generar_reporte_ventas).
        arguments: Diccionario con los argumentos de la herramienta.

    #Returns:
        Resultado de la herramienta MCP.
    """
    if _reports_client is None:
        return {"status": "error", "content": [{"text": "Gateway de reportes no disponible"}]}

    args = arguments or {}
    logger.info("MCP reports call: %s", tool_name)
    result = _reports_client.call_tool(tool_name, args)

    if "error" in result:
        return {"status": "error", "content": [{"text": f"Error en reporte: {result['error']}"}]}

    return {"status": "success", "content": [{"text": str(result.get("content", [{}])[0].get("text", str(result)))}]}


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
