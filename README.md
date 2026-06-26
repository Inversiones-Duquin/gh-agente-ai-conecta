# Agente Conversacional - Gigante del Hogar

Agente de IA para consultas de negocio del Data Warehouse i2d_dw, desplegado en AWS Bedrock AgentCore.

## Arquitectura

```
Usuario -> WebSocket -> Lambda -> AgentCore Runtime (Nova Lite)
                                    |
                                    +-> dw_* tools -> API i2d_dw (Secrets Manager)
                                    +-> generar_reporte_ventas -> Lambda reports-handler -> S3
                                    +-> search_knowledge_base -> Bedrock KB
```

## Estructura del proyecto

```
mcps/i2dw/          # 13 herramientas de consulta al DW
lambda/reports/     # Lambda de generacion de reportes HTML
agent.py            # Entrypoint del agente
prompts.py          # System prompt (fallback, tambien en DynamoDB)
build.py            # Script de build -> dist/agent-vXX.zip
```

## Herramientas disponibles

**Datos**: `dw_get_ventas`, `dw_get_ventas_item`, `dw_get_ventas_clientes`, `dw_get_ventas_mpagos`, `dw_get_productos_paginated`, `dw_get_productos_all`, `dw_get_criterios_producto`, `dw_get_centros_all`, `dw_obtener_reporte_proveedores`, `dw_listar_proveedores`, `dw_buscar_proveedor_por_nombre`

**Reportes**: `generar_reporte_ventas(id_co, fecha_desde?, fecha_hasta?)`

**Utilidades**: `fecha_actual()`, `search_knowledge_base(query)`

## Deploy

```bash
python build.py                                    # Construir zip
aws s3 cp dist/agent-vXX.zip s3://<bucket>/        # Subir
aws bedrock-agentcore-control update-agent-runtime # Desplegar
```

## Configuracion

Variables de entorno principales: `DW_API_SECRET_NAME`, `DW_API_BASE_URL`, `PROMPT_TABLE_NAME`, `MCP_GATEWAY_ID`.

El token de la API se obtiene de Secrets Manager (`gigante/dw-api`), nunca en codigo ni variables de entorno.
