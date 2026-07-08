# Herramientas del Agente

El agente expone 26 herramientas `@tool` registradas en `DW_TOOLS`. Todas las herramientas de ventas usan el API del Data Warehouse via `dw_core.call_api()`.

## Herramienta principal unificada

### dw_ventas_por_dimension

Ventas agrupadas por cualquier dimension. **Usar para la mayoria de consultas.**

| Parametro | Valores | Default |
|-----------|---------|---------|
| `dimension` | `co`, `categoria`, `subcategoria`, `seccion`, `marca`, `proveedor`, `producto` | — |
| `fecha_desde` | `YYYY-MM-DD` | — |
| `fecha_hasta` | `YYYY-MM-DD` | — |
| `id_co` | ID de centro (opcional) | `None` |
| `limit` | Numero de resultados | 20 |
| `orden` | `asc` o `desc` | `desc` |
| `ordenar_por` | `neto`, `margen`, `margen_porcentaje`, `cantidad` | `neto` |

**Endpoint**: `GET /ventas/?agrupar_por={dimension}&ordenar_por_agrupado={ordenar_por}`

**Ejemplos**:
- "Cuanto vendimos?" -> `dw_ventas_por_dimension("co", "2026-06-01", "2026-06-30")`
- "Categoria mas rentable?" -> `dw_ventas_por_dimension("categoria", ..., ordenar_por="margen", limit=1)`
- "Tiendas que menos venden?" -> `dw_ventas_por_dimension("co", ..., orden="asc")`
- "Top 5 marcas?" -> `dw_ventas_por_dimension("marca", ..., limit=5)`

**Respuesta**: La API calcula `margen` y `margen_porcentaje`. El MCP los entrega en texto plano para que el LLM no recalcule.

---

## Ventas

### dw_get_ventas
`[USO RESTRINGIDO]` Datos diarios crudos. Solo para analisis detallados dia a dia. Preferir `dw_ventas_por_dimension`.

### dw_get_ventas_item
Ventas de un producto por ID numerico, con cliente y tipo de documento.

### dw_get_ventas_clientes
Ventas agrupadas por cliente.

### dw_ventas_por_medio_pago
Ventas agrupadas por medio de pago (efectivo, tarjetas, etc.).
**Endpoint**: `GET /ventas/mpagos`

| Parametro | Default |
|-----------|---------|
| `ordenar_por` | `neto` |
| `orden` | `desc` |

---

## Busqueda de productos y ventas

### dw_buscar_ventas
`[VENTAS DE UN PRODUCTO]` Busca cuanto vendio un producto por nombre. Flujo two-step automatico: catalogo -> id_item -> ventas agregadas con neto y margen.

**Endpoint**: `GET /ventas/productos?q={producto}` (1 sola llamada)

### dw_buscar_ventas_por_referencia
Busca ventas por codigo de referencia. Flujo two-step: catalogo por referencia -> id_item -> ventas.

### dw_buscar_productos
`[SOLO CATALOGO - NO MUESTRA VENTAS]` Busca productos en el catalogo por nombre o referencia. Retorna id, descripcion, referencia pero NO ventas, NO neto, NO margen.

### dw_producto_mas_vendido
Producto #1 con mayor venta neta. 1 sola llamada, resultado directo.
**Endpoint**: `GET /ventas/productos?limit=1`

| Parametro | Descripcion |
|-----------|-------------|
| `proveedor_id` | Opcional, filtrar por proveedor |

### dw_top_productos
`[RANKINGS DE PRODUCTOS]` Top N productos mas vendidos.
**Endpoint**: `GET /ventas/productos?limit=N`

| Parametro | Default |
|-----------|---------|
| `ordenar_por` | `venta_neta` |

---

## Comparativas

### dw_comparar_ventas
`[TOTALES CORPORATIVOS]` Compara venta total entre dos periodos. Retorna diferencia, % crecimiento, mejor/peor centro.

### dw_comparar_productos
`[PRODUCTOS QUE CRECEN O CAEN]` Compara cada producto entre dos periodos. 1 sola llamada a `/ventas/productos?comparar_con=`. Retorna `productos_que_crecieron`, `productos_que_cayeron`, `nuevos`, `desaparecidos`.

| Parametro | Descripcion |
|-----------|-------------|
| `comparar_con` | Fecha inicio del periodo anterior (`YYYY-MM-DD`) |

### dw_comparar_periodos
Compara ventas entre dos periodos (version legacy, requiere `id_co`).

---

## Inventario y rotacion

### dw_rotacion_inventario
Dias de inventario por producto. **Endpoint**: `GET /ventas/?modo=rotacion`

### dw_productos_estancados
Productos con stock que no han vendido. **Endpoint**: `GET /ventas-proveedores/venta-cero`

---

## Proveedores

### dw_obtener_reporte_proveedores
Reporte completo de proveedor: venta neta, unidades, costo, inventario por producto, tienda y categoria. El MCP agrega y resume.

### dw_reporte_proveedor_top
Top productos de un proveedor especifico.

### dw_listar_proveedores
Lista completa de proveedores.

### dw_buscar_proveedor_por_nombre
Busca proveedor por nombre o ID con matching fuzzy.

---

## Catalogo

### dw_get_productos_all
`[CATALOGO]` Lista productos (max 500). Solo para busquedas por ID. No usar para rankings.

### dw_get_productos_paginated
`[CATALOGO]` Catalogo paginado.

### dw_get_criterios_producto
Criterios de clasificacion (planes 001-007) de un producto.

---

## Utilidades

### fecha_actual
Retorna fecha, dia de la semana, semana, mes y ano del sistema. Usar antes de calcular periodos relativos.

### dw_get_centros_all
`[SOLO ADMINISTRATIVO]` Lista centros de operacion. No necesaria antes de las herramientas de ventas.

### generar_reporte_ventas
Genera reporte HTML interactivo con graficos, KPIs y tabla. Retorna URL de descarga.

### search_knowledge_base
Busca en la base de conocimiento del proyecto AWS.

---

## Health

### dw_health_check
Verifica que la API este en ejecucion.

### dw_health_db
Verifica conexion a SQL Server (i2d_dw).

### dw_validate_token
Valida el PAT y retorna user_id, username, role, session y permisos.

---

## Mapeo preguntas -> herramienta

| Pregunta | Herramienta |
|----------|-------------|
| Cuanto vendimos? | `dw_ventas_por_dimension("co", ...)` |
| Margen de tienda X? | `dw_ventas_por_dimension("co", ...)` |
| Categoria mas rentable? | `dw_ventas_por_dimension("categoria", ordenar_por="margen", limit=1)` |
| Tiendas que menos venden? | `dw_ventas_por_dimension("co", orden="asc")` |
| Top 10 productos? | `dw_top_productos(10, ...)` |
| Cuanto vendio X producto? | `dw_buscar_ventas("X", ...)` |
| Productos que cayeron vs mes pasado? | `dw_comparar_productos(..., comparar_con="...")` |
| Como vamos vs mes pasado? | `dw_comparar_ventas(...)` |
| Como pagan mis clientes? | `dw_ventas_por_medio_pago(...)` |
| Informe del proveedor X? | `dw_obtener_reporte_proveedores(proveedor_id="X")` |
| Productos con sobrestock? | `dw_productos_estancados()` |
| Cuantos productos tipo X hay? | `dw_buscar_productos("X")` |

## Reglas de uso

1. **NUNCA** uses `dw_get_productos_all` o `dw_buscar_productos` para rankings — son catalogo, no ventas
2. **NUNCA** uses `dw_get_centros_all` antes de herramientas de ventas — ellas ya devuelven nombres
3. **NUNCA** uses `dw_get_ventas` para totales o rankings — usa `dw_ventas_por_dimension`
4. **SIEMPRE** llama `fecha_actual()` antes de calcular periodos relativos
5. **CONFIA** en `margen_porcentaje` del API — no recalcules margen / neto
