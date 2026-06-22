# -*- coding: utf-8 -*-
"""Cliente sincrónico para el Gateway MCP de Bedrock AgentCore."""

import json
import logging
import time
from typing import Any, Dict, List, Optional

import boto3
from botocore.exceptions import BotoCoreError, ClientError

logger = logging.getLogger(__name__)

_CACHE_TTL = 300  # segundos


class MCPGatewayClient:
    """Cliente para interactuar con un Gateway MCP de Bedrock AgentCore.

    Uso:
        client = MCPGatewayClient("api-xxxxx", region="us-east-2")
        tools = client.list_tools()
        result = client.call_tool("mi_herramienta", {"param": "valor"})
    """

    def __init__(self, gateway_id: str, region: str = "us-east-2") -> None:
        if not gateway_id or not gateway_id.strip():
            raise ValueError("gateway_id no puede estar vacío")

        self.gateway_id = gateway_id.strip()
        self.region = region
        try:
            self.runtime_client = boto3.client(
                "bedrock-agentcore-runtime", region_name=region
            )
        except Exception as e:
            raise RuntimeError(
                f"bedrock-agentcore-runtime no disponible (boto3 {boto3.__version__}). "
                "Ejecuta en AWS o actualiza boto3."
            ) from e
        self.control_client = boto3.client(
            "bedrock-agentcore-control", region_name=region
        )
        self.gateway_url: Optional[str] = None
        self._tools_cache: Optional[List[Dict[str, Any]]] = None
        self._tools_ts: float = 0.0
        self._resources_cache: Optional[List[Dict[str, Any]]] = None
        self._resources_ts: float = 0.0
        self._init_gateway()

    # ------------------------------------------------------------------
    # Inicialización
    # ------------------------------------------------------------------

    def _init_gateway(self) -> None:
        try:
            resp = self.control_client.get_gateway(gatewayId=self.gateway_id)
            self.gateway_url = resp.get("gatewayUrl")
            logger.info("Gateway MCP: %s → %s", self.gateway_id, self.gateway_url)
        except (ClientError, BotoCoreError) as e:
            logger.error("Error inicializando gateway '%s': %s", self.gateway_id, e)
            raise

    # ------------------------------------------------------------------
    # Tools
    # ------------------------------------------------------------------

    def list_tools(self, force_refresh: bool = False) -> List[Dict[str, Any]]:
        """Lista herramientas MCP (con caché de %ds).""" % _CACHE_TTL
        if (
            not force_refresh
            and self._tools_cache is not None
            and (time.time() - self._tools_ts) < _CACHE_TTL
        ):
            return self._tools_cache

        try:
            resp = self._invoke("tools/list", {})
            tools = resp.get("tools", [])
            self._tools_cache = tools
            self._tools_ts = time.time()
            logger.info("MCP tools: %d disponibles", len(tools))
            return tools
        except (ClientError, BotoCoreError) as e:
            logger.error("Error listando tools MCP: %s", e)
            return self._tools_cache or []  # fallback a caché

    def call_tool(
        self, tool_name: str, arguments: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Ejecuta una herramienta MCP."""
        if not tool_name:
            return {"error": "tool_name vacío"}

        params: Dict[str, Any] = {"name": tool_name}
        if arguments is not None:
            params["arguments"] = arguments

        try:
            resp = self._invoke("tools/call", params)
            logger.info("MCP tool ejecutada: %s", tool_name)
            if resp.get("isError"):
                detail = resp.get("content", [{}])[0].get("text", "sin detalles")
                logger.warning("MCP tool '%s' reportó error: %s", tool_name, detail)
            return resp
        except (ClientError, BotoCoreError) as e:
            logger.error("Error en tool MCP '%s': %s", tool_name, e)
            return {"error": str(e), "tool_name": tool_name}

    # ------------------------------------------------------------------
    # Resources
    # ------------------------------------------------------------------

    def list_resources(self, force_refresh: bool = False) -> List[Dict[str, Any]]:
        """Lista recursos MCP (con caché)."""
        if (
            not force_refresh
            and self._resources_cache is not None
            and (time.time() - self._resources_ts) < _CACHE_TTL
        ):
            return self._resources_cache

        try:
            resp = self._invoke("resources/list", {})
            resources = resp.get("resources", [])
            self._resources_cache = resources
            self._resources_ts = time.time()
            logger.info("MCP resources: %d disponibles", len(resources))
            return resources
        except (ClientError, BotoCoreError) as e:
            logger.error("Error listando resources MCP: %s", e)
            return self._resources_cache or []

    def get_resource(self, resource_uri: str) -> Dict[str, Any]:
        """Lee un recurso MCP por URI."""
        if not resource_uri:
            return {"error": "resource_uri vacío"}

        try:
            resp = self._invoke("resources/read", {"uri": resource_uri})
            logger.info("MCP resource leído: %s", resource_uri)
            return resp
        except (ClientError, BotoCoreError) as e:
            logger.error("Error leyendo resource '%s': %s", resource_uri, e)
            return {"error": str(e), "resource_uri": resource_uri}

    # ------------------------------------------------------------------
    # Interno
    # ------------------------------------------------------------------

    def _invoke(self, method: str, params: Dict[str, Any]) -> Dict[str, Any]:
        return self.runtime_client.invoke_gateway(
            gatewayId=self.gateway_id, method=method, params=params
        )

    def invalidate_cache(self) -> None:
        """Invalida todas las cachés."""
        self._tools_cache = None
        self._tools_ts = 0.0
        self._resources_cache = None
        self._resources_ts = 0.0

    # ------------------------------------------------------------------
    # Helpers estáticos
    # ------------------------------------------------------------------

    @staticmethod
    def format_tool_result(result: Dict[str, Any]) -> str:
        """Formatea el resultado de una herramienta MCP para texto."""
        if "error" in result:
            return f"Error: {result['error']}"
        content = result.get("content", [])
        if isinstance(content, list) and content and isinstance(content[0], dict):
            return content[0].get("text", json.dumps(content, ensure_ascii=False))
        return json.dumps(content or result, ensure_ascii=False, indent=2)

    @staticmethod
    def tool_to_spec(tool: Dict[str, Any], prefix: str = "mcp_") -> Dict[str, Any]:
        """Convierte una herramienta MCP a formato toolSpec."""
        name = tool.get("name", "desconocida")
        return {
            "toolSpec": {
                "name": f"{prefix}{name}",
                "description": tool.get("description", f"Herramienta MCP: {name}"),
                "inputSchema": {"json": tool.get("inputSchema", {})},
            }
        }
