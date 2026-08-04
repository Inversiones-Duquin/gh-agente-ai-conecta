"""Template HTML para reporte comparativo — dos periodos, KPIs duales, graficos overlay."""
import json


def build_comparative_html(periodo_1: dict, periodo_2: dict, center_name: str,
                           fecha_desde_1: str, fecha_hasta_1: str,
                           fecha_desde_2: str, fecha_hasta_2: str) -> str:
    """Construye HTML completo para reporte comparativo entre dos periodos."""

    # Extraer datos
    data1 = periodo_1.get("data", periodo_1.get("items", []))
    data2 = periodo_2.get("data", periodo_2.get("items", []))

    # Totales
    def _totals(data):
        neto = sum(float(r.get("neto", r.get("venta_neta", 0)) or 0) for r in data)
        margen = sum(float(r.get("margen", 0)) or 0 for r in data)
        und = sum(int(r.get("cant_vendida", r.get("unidades", 0)) or 0) for r in data)
        tickets = len(data)
        return neto, margen, und, tickets

    n1, m1, u1, t1 = _totals(data1)
    n2, m2, u2, t2 = _totals(data2)

    def _pct(a, b):
        if b and b != 0:
            return round(((a - b) / abs(b)) * 100, 2)
        return 0

    var_neto = _pct(n2, n1)
    var_margen = _pct(m2, m1)
    var_und = _pct(u2, u1)
    margen_pct1 = round((m1 / n1 * 100), 1) if n1 else 0
    margen_pct2 = round((m2 / n2 * 100), 1) if n2 else 0

    # Top productos combinados
    productos = {}
    for r in data1:
        nombre = (r.get("descripcion_item", r.get("producto", "")) or "").strip()
        if nombre:
            neto_val = float(r.get("neto", r.get("venta_neta", 0)) or 0)
            und_val = int(r.get("cant_vendida", r.get("unidades", 0)) or 0)
            productos[nombre] = {"neto_p1": neto_val, "und_p1": und_val, "neto_p2": 0, "und_p2": 0}
    for r in data2:
        nombre = (r.get("descripcion_item", r.get("producto", "")) or "").strip()
        if nombre:
            neto_val = float(r.get("neto", r.get("venta_neta", 0)) or 0)
            und_val = int(r.get("cant_vendida", r.get("unidades", 0)) or 0)
            if nombre in productos:
                productos[nombre]["neto_p2"] = neto_val
                productos[nombre]["und_p2"] = und_val
            else:
                productos[nombre] = {"neto_p1": 0, "und_p1": 0, "neto_p2": neto_val, "und_p2": und_val}

    top = sorted(productos.items(), key=lambda x: x[1]["neto_p2"] + x[1]["neto_p1"], reverse=True)[:10]

    # Datos para graficos (top 5 por periodo)
    def _chart_data(data, key_n="neto", key_u="cant_vendida", limit=5):
        sorted_data = sorted(data, key=lambda x: float(x.get(key_n, x.get("venta_neta", 0)) or 0), reverse=True)[:limit]
        return {
            "labels": json.dumps([(r.get("descripcion_item", r.get("producto", "")) or "").strip()[:30] for r in sorted_data]),
            "neto": json.dumps([float(r.get(key_n, r.get("venta_neta", 0)) or 0) for r in sorted_data]),
            "und": json.dumps([int(r.get(key_u, r.get("unidades", 0)) or 0) for r in sorted_data]),
        }

    chart1 = _chart_data(data1)
    chart2 = _chart_data(data2)

    # ── Build HTML ──────────────────────────────────────────────────────────
    arrow = "&#9650;" if var_neto >= 0 else "&#9660;"
    arrow_color = "#16a34a" if var_neto >= 0 else "#dc2626"

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Reporte Comparativo — {center_name}</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
  :root {{
    --ink: #1a1a1a;
    --paper: #fafaf9;
    --muted: #78716c;
    --border: #e7e5e4;
    --accent: #2563eb;
    --accent-dim: #dbeafe;
    --green: #16a34a;
    --red: #dc2626;
    --amber: #d97706;
  }}
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
    background: var(--paper); color: var(--ink);
    max-width: 1100px; margin: 0 auto; padding: 48px 32px;
    line-height: 1.5;
    -webkit-font-smoothing: antialiased;
  }}

  /* ── Masthead ──────────────────────────────────────────────── */
  .masthead {{
    display: flex; justify-content: space-between; align-items: flex-end;
    padding-bottom: 32px; margin-bottom: 40px;
    border-bottom: 2px solid var(--ink);
  }}
  .masthead h1 {{
    font-size: 28px; font-weight: 700; letter-spacing: -0.5px; line-height: 1.15;
  }}
  .masthead .meta {{
    text-align: right; font-size: 13px; color: var(--muted);
  }}
  .masthead .meta strong {{ color: var(--ink); }}

  /* ── KPI Grid ───────────────────────────────────────────────── */
  .kpi-grid {{
    display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px;
    margin-bottom: 40px;
  }}
  .kpi-card {{
    background: #fff; border: 1px solid var(--border); border-radius: 8px;
    padding: 20px; position: relative; transition: box-shadow 0.15s;
  }}
  .kpi-card:hover {{ box-shadow: 0 4px 12px rgba(0,0,0,0.06); }}
  .kpi-card .label {{
    font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px;
    color: var(--muted); margin-bottom: 8px; font-weight: 600;
  }}
  .kpi-card .values {{ display: flex; flex-direction: column; gap: 2px; }}
  .kpi-card .p1 {{ font-size: 22px; font-weight: 700; color: var(--ink); }}
  .kpi-card .p2 {{ font-size: 22px; font-weight: 700; color: var(--accent); }}
  .kpi-card .delta {{
    font-size: 13px; font-weight: 600; margin-top: 4px;
  }}
  .delta.up {{ color: var(--green); }}
  .delta.down {{ color: var(--red); }}

  /* ── Section headings ───────────────────────────────────────── */
  .section-title {{
    font-size: 16px; font-weight: 700; letter-spacing: -0.3px;
    margin: 40px 0 16px; padding-bottom: 8px;
    border-bottom: 1px solid var(--border);
    display: flex; justify-content: space-between; align-items: baseline;
  }}
  .section-title .period-tag {{
    font-size: 11px; font-weight: 500; color: var(--muted);
    text-transform: uppercase; letter-spacing: 0.5px;
  }}

  /* ── Tables ─────────────────────────────────────────────────── */
  table {{
    width: 100%; border-collapse: collapse; font-size: 14px;
    margin-bottom: 32px;
  }}
  thead th {{
    text-align: left; padding: 12px 16px; font-size: 11px;
    text-transform: uppercase; letter-spacing: 0.5px; color: var(--muted);
    font-weight: 600; border-bottom: 2px solid var(--ink);
    background: #fff;
  }}
  thead th.num {{ text-align: right; }}
  tbody td {{
    padding: 10px 16px; border-bottom: 1px solid var(--border);
    vertical-align: middle;
  }}
  tbody td.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
  tbody tr:hover {{ background: var(--accent-dim); }}
  .product-name {{ font-weight: 600; }}
  .product-ref {{ font-size: 11px; color: var(--muted); }}
  .var-cell {{ font-weight: 600; font-size: 12px; }}

  /* ── Chart area ─────────────────────────────────────────────── */
  .chart-row {{
    display: grid; grid-template-columns: 1fr 1fr; gap: 24px;
    margin-bottom: 40px;
  }}
  .chart-box {{
    background: #fff; border: 1px solid var(--border); border-radius: 8px;
    padding: 20px;
  }}
  .chart-box h3 {{
    font-size: 13px; font-weight: 600; margin-bottom: 16px; color: var(--muted);
    text-transform: uppercase; letter-spacing: 0.5px;
  }}
  .chart-box canvas {{ max-height: 280px; }}

  /* ── Footer ─────────────────────────────────────────────────── */
  .footer {{
    margin-top: 48px; padding-top: 16px; border-top: 1px solid var(--border);
    font-size: 12px; color: var(--muted); text-align: center;
  }}
  .footer span {{ margin: 0 12px; }}

  /* ── Print ──────────────────────────────────────────────────── */
  @media print {{
    body {{ padding: 24px; }}
    .kpi-grid {{ grid-template-columns: repeat(4, 1fr); }}
    .chart-row {{ grid-template-columns: 1fr 1fr; }}
  }}
</style>
</head>
<body>

<!-- ── Masthead ──────────────────────────────────────────────── -->
<header class="masthead">
  <div>
    <h1>Reporte Comparativo</h1>
    <p style="color:var(--muted);font-size:14px;margin-top:4px;">{center_name}</p>
  </div>
  <div class="meta">
    <strong>P1</strong> {fecha_desde_1} &rarr; {fecha_hasta_1}<br>
    <strong>P2</strong> {fecha_desde_2} &rarr; {fecha_hasta_2}<br>
    <span style="font-size:11px">{len(data1)} vs {len(data2)} registros</span>
  </div>
</header>

<!-- ── KPI Grid ──────────────────────────────────────────────── -->
<div class="kpi-grid">
  <div class="kpi-card">
    <div class="label">Venta Neta</div>
    <div class="values">
      <div class="p1">${n1:,.0f}</div>
      <div class="p2">${n2:,.0f}</div>
    </div>
    <div class="delta {'up' if var_neto >= 0 else 'down'}">{arrow} {abs(var_neto):.1f}%</div>
  </div>
  <div class="kpi-card">
    <div class="label">Margen Bruto</div>
    <div class="values">
      <div class="p1">{margen_pct1}%</div>
      <div class="p2">{margen_pct2}%</div>
    </div>
    <div class="delta {'up' if var_margen >= 0 else 'down'}">{'&#9650;' if var_margen >= 0 else '&#9660;'} {abs(var_margen):.1f}%</div>
  </div>
  <div class="kpi-card">
    <div class="label">Unidades Vendidas</div>
    <div class="values">
      <div class="p1">{u1:,}</div>
      <div class="p2">{u2:,}</div>
    </div>
    <div class="delta {'up' if var_und >= 0 else 'down'}">{'&#9650;' if var_und >= 0 else '&#9660;'} {abs(var_und):.1f}%</div>
  </div>
  <div class="kpi-card">
    <div class="label">Ticket Promedio</div>
    <div class="values">
      <div class="p1">${(n1/u1):,.0f if u1 else 0}</div>
      <div class="p2">${(n2/u2):,.0f if u2 else 0}</div>
    </div>
    <div class="delta" style="color:var(--muted)">por transaccion</div>
  </div>
</div>

<!-- ── Top Products ──────────────────────────────────────────── -->
<div class="section-title">
  Top 10 Productos
  <span class="period-tag">Comparativo P1 &rarr; P2</span>
</div>
<table>
  <thead>
    <tr>
      <th>Producto</th>
      <th class="num">Venta Neta P1</th>
      <th class="num">Venta Neta P2</th>
      <th class="num">Variacion</th>
      <th class="num">Und P1</th>
      <th class="num">Und P2</th>
    </tr>
  </thead>
  <tbody>
    {''.join(f'''
    <tr>
      <td><span class="product-name">{nombre[:60]}</span></td>
      <td class="num">${d['neto_p1']:,.0f}</td>
      <td class="num">${d['neto_p2']:,.0f}</td>
      <td class="num"><span class="var-cell" style="color:{'var(--green)' if _pct(d['neto_p2'], d['neto_p1']) >= 0 else 'var(--red)'}">{'&#9650;' if _pct(d['neto_p2'], d['neto_p1']) >= 0 else '&#9660;'} {abs(_pct(d['neto_p2'], d['neto_p1'])):.1f}%</span></td>
      <td class="num">{d['und_p1']:,}</td>
      <td class="num">{d['und_p2']:,}</td>
    </tr>''' for nombre, d in top)}
  </tbody>
</table>

<!-- ── Charts ─────────────────────────────────────────────────── -->
<div class="chart-row">
  <div class="chart-box">
    <h3>Top 5 — {fecha_desde_1} al {fecha_hasta_1}</h3>
    <canvas id="chartP1"></canvas>
  </div>
  <div class="chart-box">
    <h3>Top 5 — {fecha_desde_2} al {fecha_hasta_2}</h3>
    <canvas id="chartP2"></canvas>
  </div>
</div>

<!-- ── Footer ────────────────────────────────────────────────── -->
<footer class="footer">
  <span>Gigante del Hogar</span>&bull;<span>Analista Comercial</span>&bull;<span>{center_name}</span>
</footer>

<!-- ── Charts JS ─────────────────────────────────────────────── -->
<script>
const P1 = {{
  labels: {chart1["labels"]},
  neto: {chart1["neto"]},
  und: {chart1["und"]},
}};
const P2 = {{
  labels: {chart2["labels"]},
  neto: {chart2["neto"]},
  und: {chart2["und"]},
}};

function fmtCOP(v) {{ return '$' + v.toLocaleString('es-CO', {{maximumFractionDigits:0}}); }}

function buildChart(canvasId, chartData, accentColor) {{
  new Chart(document.getElementById(canvasId), {{
    type: 'bar',
    data: {{
      labels: chartData.labels,
      datasets: [{{
        label: 'Venta Neta',
        data: chartData.neto,
        backgroundColor: accentColor,
        borderRadius: 4,
        borderSkipped: false,
      }}],
    }},
    options: {{
      responsive: true,
      maintainAspectRatio: false,
      plugins: {{
        legend: {{ display: false }},
        tooltip: {{
          callbacks: {{ label: ctx => fmtCOP(ctx.raw) }}
        }},
      }},
      scales: {{
        x: {{
          ticks: {{ maxRotation: 45, font: {{ size: 10 }} }},
        }},
        y: {{
          ticks: {{ callback: v => fmtCOP(v), font: {{ size: 10 }} }},
          grid: {{ color: '#f0f0f0' }},
        }},
      }},
    }},
  }});
}}

buildChart('chartP1', P1, '#94a3b8');
buildChart('chartP2', P2, '#2563eb');
</script>

</body>
</html>"""
