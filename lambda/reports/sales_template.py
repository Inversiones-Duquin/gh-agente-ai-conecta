"""Template HTML interactivo para reporte de ventas — Chart.js, KPIs, tabla."""
import json
from datetime import datetime


def _fmt(value):
    return f"${float(value):,.0f}"


def _compute_kpis(data):
    """Extrae KPIs de los datos de ventas."""
    neto_list = [float(r.get("neto", 0)) for r in data]
    bruto_list = [float(r.get("bruto", 0)) for r in data]
    margen_list = [float(r.get("margen", 0)) for r in data]
    desc_list = [float(r.get("descuento", 0)) for r in data]
    imp_list = [float(r.get("impuesto", 0)) for r in data]
    margin_pcts = [float(r.get("margen_porcentaje", 0)) for r in data]

    t_neto = sum(neto_list)
    t_bruto = sum(bruto_list)
    t_margen = sum(margen_list)
    avg_margin = t_margen / t_neto * 100 if t_neto > 0 else 0

    best = max(data, key=lambda r: float(r.get("neto", 0)))
    worst = min(data, key=lambda r: float(r.get("neto", 0)))
    prom = t_neto / len(data) if data else 0
    bv = (float(best["neto"]) / prom - 1) * 100 if prom > 0 else 0
    wv = (1 - float(worst["neto"]) / prom) * 100 if prom > 0 else 0

    return {
        "labels": [r.get("fecha", "") for r in data],
        "neto": neto_list, "margin": margin_pcts,
        "t_neto": t_neto, "t_bruto": t_bruto, "t_margen": t_margen,
        "t_desc": sum(desc_list), "t_imp": sum(imp_list),
        "avg_margin": avg_margin, "prom": prom,
        "best": best, "worst": worst, "bv": bv, "wv": wv,
        "margin_min": min(margin_pcts), "margin_max": max(margin_pcts),
        "margin_avg": sum(margin_pcts) / len(margin_pcts) if margin_pcts else 0,
        "count": len(data),
    }


def _build_chart_js(kpi):
    """Genera el bloque <script> de Chart.js. Soporta valores negativos."""
    margin_min = kpi["margin_min"]
    margin_max = kpi["margin_max"]
    # Rango dinamico con margen del 10%, permite negativos
    span = max(abs(margin_max - margin_min), 5)
    pad = span * 0.15
    y1_min = int((margin_min - pad) // 1)
    y1_max = int((margin_max + pad) // 1) + 1
    return f"""<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.7/dist/chart.umd.min.js"></script>
<script>
const ctx=document.getElementById('c').getContext('2d');
new Chart(ctx,{{type:'bar',data:{{labels:{json.dumps(kpi['labels'])},datasets:[
{{label:'Neto (COP)',data:{json.dumps(kpi['neto'])},backgroundColor:'#2D2DD5',borderRadius:4,yAxisID:'y',order:1}},
{{label:'Margen %',data:{json.dumps(kpi['margin'])},type:'line',borderColor:'#FCEE21',borderWidth:2,pointRadius:4,backgroundColor:'#FCEE21',yAxisID:'y1',order:0,tension:0.3}}
]}},options:{{responsive:true,maintainAspectRatio:false,
plugins:{{legend:{{position:'top'}},tooltip:{{callbacks:{{label:function(ctx){{return ctx.dataset.label+': '+(ctx.dataset.yAxisID==='y'?'$'+ctx.raw.toLocaleString():ctx.raw.toFixed(2)+'%');}}}}}}}},
scales:{{y:{{position:'left',title:{{display:true,text:'Neto (COP)'}},ticks:{{callback:function(v){{return '$'+(v/1e6).toFixed(1)+'M';}}}}}},
y1:{{position:'right',title:{{display:true,text:'Margen %'}},min:{y1_min},max:{y1_max},grid:{{drawOnChartArea:false}}}}}}}}}});
</script>"""


def _build_observations(kpi, data):
    """Analisis ejecutivo exhaustivo basado en datos reales."""
    obs = []
    margin_range = kpi['margin_max'] - kpi['margin_min']
    desc_pct = kpi['t_desc'] / kpi['t_bruto'] * 100 if kpi['t_bruto'] > 0 else 0
    imp_pct = kpi['t_imp'] / kpi['t_bruto'] * 100 if kpi['t_bruto'] > 0 else 0
    margin_avg = kpi['margin_avg']

    # 1. Rendimiento general
    obs.append(
        f"Rendimiento general: {kpi['count']} periodos analizados con un neto total de {_fmt(kpi['t_neto'])}, "
        f"promedio diario de {_fmt(kpi['prom'])}. Margen promedio de {margin_avg:.1f}% "
        f"({'estable' if margin_range < 2 else 'con variacion de ' + f'{margin_range:.1f} pp'})."
    )

    # 2. Analisis de margen
    if margin_range < 1:
        obs.append(f"Margen altamente consistente: oscilacion minima de {margin_range:.1f} pp, "
                   f"lo que indica control de costos y precios uniforme en el periodo.")
    elif margin_range < 2:
        obs.append(f"Margen con leve variacion ({margin_range:.1f} pp entre {kpi['margin_min']:.1f}% y {kpi['margin_max']:.1f}%). "
                   f"Dentro de rangos operativos normales.")
    else:
        obs.append(f"Margen con dispersion significativa de {margin_range:.1f} pp "
                   f"(min: {kpi['margin_min']:.1f}%, max: {kpi['margin_max']:.1f}%). "
                   f"Se recomienda investigar causas de la volatilidad.")

    # 3. Descuentos e impuestos
    if desc_pct > 5:
        obs.append(f"Alerta: descuentos representan {desc_pct:.1f}% del bruto "
                   f"({_fmt(kpi['t_desc'])}). Evaluar politica de descuentos y su impacto en margen.")
    else:
        obs.append(f"Descuentos controlados: {desc_pct:.1f}% del bruto ({_fmt(kpi['t_desc'])}). "
                   f"Carga impositiva: {imp_pct:.1f}% sobre el bruto ({_fmt(kpi['t_imp'])}).")

    # 4. Mejor vs peor periodo
    if kpi['bv'] > 0:
        obs.append(
            f"Mejor periodo: {kpi['best']['fecha']} con {_fmt(kpi['best']['neto'])} neto "
            f"(+{kpi['bv']:.0f}% sobre el promedio). Peor: {kpi['worst']['fecha']} con "
            f"{_fmt(kpi['worst']['neto'])} (-{kpi['wv']:.0f}% vs promedio)."
        )

    # 5. Tendencia (basado en primeros vs ultimos)
    if len(data) >= 4:
        first_half = sum(float(r.get('neto', 0)) for r in data[:len(data)//2]) / (len(data)//2)
        second_half = sum(float(r.get('neto', 0)) for r in data[len(data)//2:]) / (len(data) - len(data)//2)
        if second_half > first_half * 1.05:
            obs.append(f"Tendencia alcista: el promedio de la segunda mitad del periodo "
                       f"({_fmt(second_half)}) supera en {((second_half/first_half)-1)*100:.1f}% "
                       f"a la primera mitad ({_fmt(first_half)}).")
        elif second_half < first_half * 0.95:
            obs.append(f"Tendencia a la baja: el promedio de la segunda mitad ({_fmt(second_half)}) "
                       f"esta {((1-second_half/first_half))*100:.1f}% por debajo de la primera ({_fmt(first_half)}).")
        else:
            obs.append(f"Rendimiento estable entre la primera y segunda mitad del periodo "
                       f"({_fmt(first_half)} vs {_fmt(second_half)}).")

    return obs


def _build_table_rows(data):
    """Genera filas HTML de la tabla de datos."""
    rows = []
    tn = tb = ts = ti = td = tm = 0.0
    for r in data:
        n, b, s, i, d, m = [float(r.get(k, 0)) for k in
                             ("neto", "bruto", "subtotal", "impuesto", "descuento", "margen")]
        tn += n; tb += b; ts += s; ti += i; td += d; tm += m
        pct = float(r.get("margen_porcentaje", 0))
        rows.append(
            f"<tr><td>{r.get('fecha','')}</td><td>{_fmt(n)}</td><td>{_fmt(b)}</td>"
            f"<td>{_fmt(s)}</td><td>{_fmt(i)}</td><td>{_fmt(d)}</td>"
            f"<td>{_fmt(m)}</td><td>{pct:.2f}%</td></tr>"
        )
    avg_m = tm / tn * 100 if tn > 0 else 0
    total_row = (
        f"<tr class='total-row'><td>TOTALES</td><td>{_fmt(tn)}</td><td>{_fmt(tb)}</td>"
        f"<td>{_fmt(ts)}</td><td>{_fmt(ti)}</td><td>{_fmt(td)}</td>"
        f"<td>{_fmt(tm)}</td><td>{avg_m:.2f}%</td></tr>"
    )
    return "".join(rows), total_row


CSS = """
:root{--blue:#2D2DD5;--gray:#6E6E6E;--yellow:#FCEE21;--white:#FFF;--bg:#F5F5F7;--border:#E0E0E0}
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:Arial,Helvetica,sans-serif;background:var(--bg);color:var(--gray);line-height:1.5;padding:20px 40px;max-width:1400px;margin:0 auto}
.header{background:var(--blue);color:var(--white);padding:32px 40px;border-radius:8px;margin-bottom:32px}
.header h1{font-size:26px;font-weight:700;margin-bottom:4px}
.header h2{font-size:15px;font-weight:400;opacity:.9}
.meta{font-size:13px;opacity:.85;margin-top:12px;display:flex;gap:32px;flex-wrap:wrap}
.kpi-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin-bottom:32px}
.kpi-card{background:var(--white);border:1px solid var(--border);border-radius:8px;padding:20px;text-align:center}
.kpi-value{font-size:24px;font-weight:700;color:var(--blue)}
.kpi-label{font-size:11px;color:var(--gray);text-transform:uppercase;letter-spacing:.5px}
.kpi-sub{font-size:10px;color:var(--gray);margin-top:4px}
.chart-section{background:var(--white);border-radius:8px;padding:24px;border:1px solid var(--border);margin-bottom:32px}
.chart-section h3{font-size:16px;margin-bottom:16px}
.chart-wrap{position:relative;height:350px}
.obs-section{background:var(--white);border-radius:8px;padding:24px;border:1px solid var(--border);margin-bottom:32px}
.obs-section h3{font-size:16px;margin-bottom:12px}
.obs-section ul{list-style:none;padding:0}
.obs-section li{font-size:13px;padding:6px 0;border-bottom:1px solid var(--border);display:flex;gap:8px}
.obs-section li::before{content:'-';color:var(--yellow);font-weight:bold}
.table-section{background:var(--white);border-radius:8px;padding:24px;border:1px solid var(--border);overflow-x:auto}
.table-section h3{font-size:16px;margin-bottom:12px}
table{width:100%;border-collapse:collapse;font-size:12px}
th{background:var(--blue);color:var(--white);padding:10px 8px;text-align:right;font-weight:600}
th:first-child,td:first-child{text-align:left}
td{padding:8px;border-bottom:1px solid var(--border);text-align:right}
tr:nth-child(even) td{background:#FAFAFC}
.total-row td{font-weight:700;background:var(--blue)!important;color:var(--white)}
.footer{text-align:center;margin-top:40px;font-size:11px;color:var(--gray)}
.print-btn{display:block;margin:24px auto;padding:12px 24px;background:var(--blue);color:var(--white);border:none;border-radius:8px;font-size:14px;font-weight:600;cursor:pointer}
.print-btn:hover{opacity:.9}
@media print{.print-btn{display:none}}
@media(max-width:900px){body{padding:16px}.kpi-grid{grid-template-columns:repeat(2,1fr)}}
@page{size:landscape;margin:10mm}
@media print{.table-section{page-break-before:always}.chart-section{page-break-inside:avoid}.kpi-grid{page-break-inside:avoid}}
"""


def build_html(data, center_name, date_from, date_to):
    """Genera HTML completo del reporte de ventas."""
    kpi = _compute_kpis(data)
    rows_html, total_row = _build_table_rows(data)
    obs_html = "\n".join(f"<li>{o}</li>" for o in _build_observations(kpi, data))
    chart_js = _build_chart_js(kpi)
    now = datetime.now()

    return f"""<!DOCTYPE html><html lang="es">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Reporte de Ventas - {center_name}</title>
<style>{CSS}</style></head>
<body>
<div class="header"><h1>GIGANTE DEL HOGAR</h1><h2>Reporte de Ventas por Centro de Operacion</h2>
<div class="meta"><span><b>Centro:</b> {center_name}</span><span><b>Periodo:</b> {date_from} al {date_to}</span><span><b>Generado:</b> {now.strftime('%d/%m/%Y %H:%M')}</span></div></div>
<div class="kpi-grid">
<div class="kpi-card"><div class="kpi-value">{_fmt(kpi['t_neto'])}</div><div class="kpi-label">Total Neto</div><div class="kpi-sub">{kpi['count']} dias</div></div>
<div class="kpi-card"><div class="kpi-value">{_fmt(kpi['prom'])}</div><div class="kpi-label">Promedio Diario</div><div class="kpi-sub">Mejor: {kpi['best']['fecha']}</div></div>
<div class="kpi-card"><div class="kpi-value">{_fmt(kpi['t_margen'])}</div><div class="kpi-label">Margen Total</div><div class="kpi-sub">{kpi['avg_margin']:.1f}% del neto</div></div>
<div class="kpi-card"><div class="kpi-value">{kpi['margin_min']:.1f}% - {kpi['margin_max']:.1f}%</div><div class="kpi-label">Rango de Margen</div><div class="kpi-sub">Media: {kpi['margin_avg']:.1f}%</div></div>
</div>
<div class="chart-section"><h3>Neto Diario y Tendencia de Margen (%)</h3><div class="chart-wrap"><canvas id="c"></canvas></div></div>
<div class="obs-section"><h3>Observaciones</h3><ul>{obs_html}</ul></div>
<div class="table-section"><h3>Datos de Ventas</h3>
<table><thead><tr><th>Fecha</th><th>Neto</th><th>Bruto</th><th>Subtotal</th><th>Impuesto</th><th>Descuento</th><th>Margen</th><th>% Margen</th></tr></thead>
<tbody>{rows_html}{total_row}</tbody></table></div>
<button class="print-btn" onclick="window.print()">Guardar como PDF</button>
<div class="footer"><p>Gigante del Hogar - Reporte generado automaticamente. {now.year}</p></div>
{chart_js}
</body></html>"""
