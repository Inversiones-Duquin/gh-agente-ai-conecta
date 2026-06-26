"""Lambda handler — Gateway de Reportes (AgentCore)."""
import os, uuid, logging
from datetime import datetime, timedelta

import boto3

from api_client import api_get
from sales_template import build_html

logger = logging.getLogger()
logger.setLevel(logging.INFO)

BUCKET = os.getenv("REPORTS_BUCKET", "gigante-chatbot-reports-640928554769-us-east-2")
REGION = os.getenv("AWS_REGION", "us-east-2")


# ── Helpers ─────────────────────────────────────────────────────────────────

def _default_dates(fecha_desde, fecha_hasta):
    now = datetime.now()
    return (
        fecha_desde or (now - timedelta(days=30)).strftime("%Y-%m-%d"),
        fecha_hasta or now.strftime("%Y-%m-%d"),
    )


def _resolve_center(id_co):
    data = api_get("/centros/all")
    centros = data if isinstance(data, list) else data.get("data", [])
    for c in centros:
        cid = str(c.get("id_co", "")).lstrip("0") or "0"
        if cid == str(id_co):
            return f"{c.get('nombre', 'Centro '+str(id_co))} ({c.get('id_co','')})"
    return f"Centro {id_co}"


# ── Report generators ──────────────────────────────────────────────────────

def generar_reporte_ventas(id_co, fecha_desde=None, fecha_hasta=None):
    fecha_desde, fecha_hasta = _default_dates(fecha_desde, fecha_hasta)

    # Datos
    api_data = api_get("/ventas/", {"id_co": id_co, "fecha_desde": fecha_desde, "fecha_hasta": fecha_hasta})
    data = api_data if isinstance(api_data, list) else api_data.get("data", [])
    if not data:
        return {"isError": True, "content": [{"type": "text", "text": "Sin datos para el periodo solicitado."}]}

    center_name = _resolve_center(id_co)

    # HTML
    html = build_html(data, center_name, fecha_desde, fecha_hasta)

    # S3
    now = datetime.now()
    short_id = uuid.uuid4().hex[:8]
    key = f"r/{short_id}.html"
    s3 = boto3.client("s3", region_name=REGION)
    s3.put_object(Bucket=BUCKET, Key=key, Body=html.encode("utf-8"), ContentType="text/html")
    # s3.amazonaws.com es mas corto que s3.us-east-2.amazonaws.com
    url = f"https://s3.{REGION}.amazonaws.com/{BUCKET}/{key}"
    logger.info("Reporte subido: %s", url)

    return {
        "content": [{"type": "text", "text": f"Reporte generado.\n\nDescargar: {url}\n\nCentro: {center_name}\nPeriodo: {fecha_desde} al {fecha_hasta}\nRegistros: {len(data)}"}],
    }


# ── Entrypoint ─────────────────────────────────────────────────────────────

def handler(event, context):
    name = event.get("toolName", "")
    args = event.get("arguments", {})

    if name == "generar_reporte_ventas":
        return generar_reporte_ventas(
            args.get("id_co"), args.get("fecha_desde"), args.get("fecha_hasta"))

    return {"isError": True, "content": [{"type": "text", "text": f"Unknown tool: {name}"}]}
