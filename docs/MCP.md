# MCP Gateway & Data Warehouse

## Arquitectura MCP

```
Agente (Strands)
  |
  +-> dw_* tools (Python directo)
  |     |
  |     +-> dw_core.call_api() -> HTTPS -> api.inversionesduquin.online/api/v2
  |                                          |
  |                                          +-> SQL Server (i2d_dw)
  |
  +-> MCP Gateway (i2d-dw-gateway-lv6e91yj9s)
  |     |
  |     +-> Lambda targets -> API i2d_dw
  |
  +-> mcp_call_tool() [uso externo]
```

## Data Warehouse Client (`dw_core.py`)

### Configuracion

```python
BASE_URL = "https://api.inversionesduquin.online"  # DW_API_BASE_URL
API_PREFIX = "/api/v2"
SECRET_NAME = "gigante/dw-api"                      # DW_API_SECRET_NAME
TOKEN_TTL = 1500                                     # DW_API_TOKEN_TTL_SECONDS
REQUEST_TIMEOUT = 120                                # timeout HTTP (segundos)
REQUEST_TIMEOUT_SLOW = 120                           # timeout consultas pesadas
MAX_RESPONSE_CHARS = 500000                          # truncamiento de respuesta
MAX_LIST_ITEMS = 5000                                # max items en arrays
MAX_ADMIN_LIST_ITEMS = 5000                          # max items admin
```

### Autenticacion

Token Bearer almacenado en AWS Secrets Manager (`gigante/dw-api`, clave `pat`). Cache TTL 1500s. Soporta fallback a variable de entorno `DW_API_TOKEN`.

### call_api()

Funcion central que maneja todas las llamadas HTTP al DW:

1. Obtiene token Bearer (cache o Secrets Manager)
2. Construye request HTTP
3. Maneja rate limiting (429 -> 3 reintentos con backoff 30/60/90s)
4. Mapea errores HTTP al catalogo de `dw_errors.py`
5. Trunca arrays grandes (> max_items)
6. Trunca JSON grande (> max_chars) con halving progresivo
7. Retorna `{"status": "success", "content": [{"text": "..."}]}`

### Catalogo de errores (`dw_errors.py`)

Errores mapeados por nombre, no por codigo:

| Nombre | Mensaje |
|--------|---------|
| `BAD_REQUEST` | Parametros invalidos |
| `UNAUTHORIZED` | Sin autorizacion |
| `FORBIDDEN` | Sin permisos |
| `NOT_FOUND` | Recurso no existe |
| `RATE_LIMITED` | Demasiadas solicitudes |
| `SERVER_ERROR` | Error interno |
| `SERVICE_UNAVAILABLE` | Servicio no disponible |
| `TIMEOUT` | No respondio a tiempo |
| `CONNECTION_ERROR` | Error de conexion |
| `EMPTY_DATA` | Sin datos |
| `PARSE_ERROR` | Datos no procesables |
| `INTERNAL_ERROR` | Error interno |

Todos los errores se loguean en CloudWatch con contexto. El mensaje al usuario es generico.

## Endpoints de la API

### Ventas

| Endpoint | Descripcion | Parametros clave |
|----------|-------------|------------------|
| `GET /ventas/` | Ventas agrupadas | `fecha_desde`, `fecha_hasta`, `id_co`, `agrupar_por`, `ordenar_por_agrupado`, `orden`, `limit` |
| `GET /ventas/productos` | Ventas por producto | `fecha_desde`, `fecha_hasta`, `id_co`, `id_item`, `q`, `referencia`, `comparar_con`, `proveedor_id`, `ordenar_por`, `limit` |
| `GET /ventas/item` | Ventas detalle x producto | `id_co`, `id_item`, `fecha_desde`, `fecha_hasta` |
| `GET /ventas/clientes` | Ventas x cliente | `fecha_desde`, `fecha_hasta`, `id_co`, `id_cliente` |
| `GET /ventas/mpagos` | Ventas x medio de pago | `fecha_desde`, `fecha_hasta`, `id_co`, `orden`, `ordenar_por` |

### Productos

| Endpoint | Descripcion |
|----------|-------------|
| `GET /productos/` | Buscar productos (`q`, `buscar_por`, `limit`) |
| `GET /productos/all` | Todos los productos (limitado a 500) |
| `GET /productos/{id}` | Criterios de un producto |

### Proveedores

| Endpoint | Descripcion |
|----------|-------------|
| `GET /ventas-proveedores/` | Reporte ventas/inventario/costo por proveedor |
| `GET /ventas-proveedores/venta-cero` | Productos estancados |
| `GET /admin/proveedores/` | Lista de proveedores |

### Health

| Endpoint | Descripcion |
|----------|-------------|
| `GET /health` | Estado de la API |
| `GET /health/db` | Conexion a SQL Server |

## Dimensiones de agrupacion

`GET /ventas/?agrupar_por=` acepta:

| Dimension | Plan | Descripcion |
|-----------|------|-------------|
| `co` | — | Centro de operacion |
| `categoria` | 004 | Categoria de producto |
| `subcategoria` | 005 | Subcategoria de producto |
| `seccion` | 003 | Seccion |
| `marca` | — | Marca |
| `proveedor` | 007 | Proveedor |
| `producto` | — | Producto individual |

## Campos calculados por la API

La API calcula y devuelve:

- `subtotal` = `neto - impuesto`
- `margen` = `subtotal - costo`
- `margen_porcentaje` = `margen / subtotal * 100`

**El MCP confia en estos valores. No los recalcula.**

## Gateway Configuration

### i2d-dw-gateway (lv6e91yj9s)

Gateway MCP que expone las herramientas del DW como recursos MCP. Usado para acceso externo y descubrimiento de herramientas.

- **Region**: us-east-2
- **Protocolo**: MCP (Streamable HTTP)
- **Autenticacion**: AWS_IAM + API Key

### reports-gateway (yt5gh2old4)

Gateway para generacion de reportes.

- **Target**: Lambda `reports-handler` (Python 3.13, 256MB)
- **Funcion**: generar reportes HTML interactivos con Chart.js

## OpenAPI Specs

Los archivos `mcps/i2dw/openapi-*.json` documentan la superficie del API. Son referencia para configuracion del Gateway, no se cargan en runtime.
