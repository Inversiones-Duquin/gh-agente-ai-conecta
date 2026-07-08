# Agente Conversacional — Gigante del Hogar

Agente de IA para consultas de negocio del Data Warehouse i2d_dw, desplegado en AWS Bedrock AgentCore con Amazon Nova Lite.

## Arquitectura

```
Chat UI -> AgentCore Runtime (HTTP) -> agent.py (Strands Agent)
                                         |
                                         +-> dw_* tools -> API i2d_dw (Secrets Manager)
                                         +-> generar_reporte_ventas -> Lambda reports-handler -> S3
                                         +-> search_knowledge_base -> Bedrock KB
                                         +-> fecha_actual
                                         +-> MCP Gateway (i2d-dw-gateway)
```

## Stack tecnologico

| Componente | Tecnologia |
|-----------|-----------|
| Runtime | AWS Bedrock AgentCore (direct_code_deploy) |
| Modelo | Amazon Nova Lite `us.amazon.nova-2-lite-v1:0` |
| Framework | Strands Agents |
| Lenguaje | Python 3.14 |
| Memoria | AgentCore Memory |
| System Prompt | DynamoDB (cache TTL 300s) + fallback en `prompts.py` |
| API Token | AWS Secrets Manager (`gigante/dw-api`) |
| Reportes | Lambda `reports-handler` -> S3 |

## Estructura del proyecto

```
agent.py              # Entrypoint principal
prompts.py            # System prompt (fallback)
aws_clients.py        # Clientes boto3 lazy
helpers.py            # Parseo de payload
mcp_gateway_client.py # Cliente MCP Gateway
mcp_tools.py          # Tools MCP + agregacion
build.py              # Script de build -> dist/agent-vXX.zip
mcps/i2dw/            # Modulos del Data Warehouse
  dw_core.py           # HTTP client, auth, rate limit, truncamiento
  dw_ventas.py         # Endpoints de ventas
  dw_productos.py      # Endpoints de catalogo
  dw_proveedores.py    # Endpoints de proveedores
  dw_centros.py        # Endpoints de centros
  dw_health.py         # Health checks
  dw_auth.py           # Validacion de token
  dw_errors.py         # Catalogo de errores
  dw_tools.py          # @tool wrappers + DW_TOOLS
lambda/reports/       # Lambda de generacion de reportes HTML
docs/                 # Documentacion
dist/                 # Builds (agent-vXX.zip)
```

## Variables de entorno

| Variable | Default | Descripcion |
|----------|---------|-------------|
| `AWS_REGION` | `us-east-2` | Region AWS |
| `BEDROCK_AGENTCORE_MEMORY_ID` | — | ID de memoria AgentCore |
| `BEDROCK_KNOWLEDGE_BASE_ID` | `9KMNZ8UPF1` | Knowledge Base ID |
| `PROMPT_TABLE_NAME` | — | Tabla DynamoDB de prompts |
| `PROMPT_ID` | — | ID especifico de prompt |
| `DEFAULT_PROMPT_ID` | `default-dw-sales-v1` | Prompt por defecto |
| `SYSTEM_PROMPT_CACHE_TTL_SECONDS` | `300` | TTL cache del prompt |
| `DW_API_BASE_URL` | `https://api.inversionesduquin.online` | URL base API DW |
| `DW_API_SECRET_NAME` | `gigante/dw-api` | Secret en Secrets Manager |
| `DW_API_TOKEN_TTL_SECONDS` | `1500` | TTL cache del token |
| `DW_API_MAX_ROWS` | `100` | Default max rows |
| `DW_API_REQUEST_TIMEOUT` | `60` | Timeout HTTP |
| `MCP_GATEWAY_ID` | `i2d-dw-gateway-lv6e91yj9s` | ID del MCP Gateway |
| `MCP_GATEWAY_REGION` | `us-east-2` | Region del Gateway |
| `REPORTS_GATEWAY_ID` | `reports-gateway-yt5gh2old4` | ID del Gateway de reportes |

## Configuracion del modelo

- **Modelo**: `us.amazon.nova-2-lite-v1:0` (inference profile)
- **max_tokens**: 4096
- **Prompt caching**: activado via `SystemContentBlock` con `cachePoint: default`
- **Contexto**: 300K tokens

## Deploy

### Build

```bash
python build.py
```

Genera `dist/agent-vXX.zip` (version auto-incremental). Usa el zip mas reciente como base y reemplaza los archivos modificados.

### Subir a S3

```bash
aws s3 cp dist/agent-vXX.zip s3://bedrock-agentcore-runtime-640928554769-us-east-2-c1bgkt4x5h/agent-vXX.zip --region us-east-2
```

### Actualizar runtime

```bash
aws bedrock-agentcore-control update-agent-runtime \
  --agent-runtime-id "chatbot_agentcore_runtime-rNW40I3NDQ" \
  --agent-runtime-artifact '{"codeConfiguration":{"code":{"s3":{"bucket":"bedrock-agentcore-runtime-640928554769-us-east-2-c1bgkt4x5h","prefix":"agent-vXX.zip"}},"runtime":"PYTHON_3_14","entryPoint":["agent.py"]}}' \
  --role-arn "arn:aws:iam::640928554769:role/service-role/AmazonBedrockAgentCoreRuntimeDefaultServiceRole-47yjj" \
  --network-configuration '{"networkMode":"PUBLIC"}' \
  --protocol-configuration '{"serverProtocol":"HTTP"}' \
  --lifecycle-configuration '{"idleRuntimeSessionTimeout":300,"maxLifetime":14400}' \
  --environment-variables '{"AWS_REGION":"us-east-2","BEDROCK_AGENTCORE_MEMORY_ID":"chatbot_agentcore_memory-S5780qFeNE","BEDROCK_KNOWLEDGE_BASE_ID":"9KMNZ8UPF1","DW_API_BASE_URL":"https://api.inversionesduquin.online","DW_API_ID_CIA_DEFAULT":"1","DW_API_MAX_ROWS":"100","DW_API_SECRET_NAME":"gigante/dw-api","DW_API_TOKEN_TTL_SECONDS":"1500","MCP_GATEWAY_ID":"i2d-dw-gateway-lv6e91yj9s","PROMPT_TABLE_NAME":"Chatbot-PromptsTable"}' \
  --metadata-configuration '{"requireMMDSV2":true}' \
  --region us-east-2
```

### Verificar estado

```bash
aws bedrock-agentcore-control get-agent-runtime \
  --agent-runtime-id "chatbot_agentcore_runtime-rNW40I3NDQ" \
  --region us-east-2 \
  --query "{v: agentRuntimeVersion, status: status, artifact: agentRuntimeArtifact.codeConfiguration.code.s3.prefix}"
```

### Actualizar prompt en DynamoDB

```bash
python -c "
import sys, boto3
sys.path.insert(0, 'mcps'); sys.path.insert(0, 'mcps/i2dw')
from prompts import DEFAULT_SYSTEM_PROMPT, PROMPT_VERSION
dynamodb = boto3.client('dynamodb', region_name='us-east-2')
dynamodb.put_item(
    TableName='Chatbot-PromptsTable',
    Item={'Id': {'S': 'default-dw-sales-v1'}, 'prompt': {'S': DEFAULT_SYSTEM_PROMPT}, 'version': {'S': PROMPT_VERSION}, 'is_default': {'BOOL': True}}
)
print(f'DynamoDB actualizado: {len(DEFAULT_SYSTEM_PROMPT)} chars, v{PROMPT_VERSION}')
"
```

## Decisiones de diseno

- **max_tokens=4096**: Limite explicito para optimizar cuota de throughput en Bedrock
- **Prompt caching**: System prompt envuelto en `SystemContentBlock` con cache point para reducir costos ~90%
- **System prompt TTL**: 300s desde DynamoDB, fallback al valor cacheado, luego a `DEFAULT_SYSTEM_PROMPT`
- **DW token desde Secrets Manager**: TTL 1500s, soporte para env var `DW_API_TOKEN`
- **Rate limit**: 429 -> 3 reintentos con backoff 30/60/90s
- **Truncamiento de respuesta**: Arrays limitados a max items, JSON truncado a max chars con halving progresivo
- **Tool execution inline**: Strands ejecuta tools dentro del ciclo HTTP. Consultas lentas (>55s) pueden causar timeout del Runtime
