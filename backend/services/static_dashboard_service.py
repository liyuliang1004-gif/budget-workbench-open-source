import json
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from backend.config import BASE_DIR, STATIC_DASHBOARD_RELATIVE_PATH
from backend.services.comparison_service import dashboard_overview


MONEY_FIELDS = {
    "budget_sales_amount",
    "actual_sales_amount",
    "actual_sales_pending_amount",
    "sales_diff",
    "budget_cost_amount",
    "actual_cost_amount",
    "cost_diff",
    "budget_gross_profit",
    "actual_gross_profit",
    "gross_profit_diff",
    "budget_expense_amount",
    "actual_expense_amount",
    "expense_diff",
    "budget_profit_amount",
    "actual_profit_amount",
    "actual_profit_pending_amount",
    "profit_diff",
    "sales_amount",
    "cost_amount",
    "gross_profit",
    "expense_amount",
    "profit_amount",
}

QUANTITY_FIELDS = {"budget_quantity", "actual_quantity", "quantity_diff"}

PERCENT_FIELDS = {
    "budget_cost_rate",
    "actual_cost_rate",
    "cost_usage_rate",
    "budget_expense_rate",
    "actual_expense_rate",
    "expense_usage_rate",
    "budget_profit_rate",
    "actual_profit_rate",
    "profit_rate_diff",
    "quantity_completion_rate",
    "sales_completion_rate",
    "annual_completion_rate",
    "same_period_completion_rate",
    "annual_sales_completion_rate",
    "same_period_sales_completion_rate",
}


def get_static_dashboard_dir(app_state=None) -> Path:
    override = getattr(app_state, "static_dashboard_dir_override", None) if app_state else None
    dashboard_dir = Path(override) if override else BASE_DIR / STATIC_DASHBOARD_RELATIVE_PATH
    dashboard_dir.mkdir(parents=True, exist_ok=True)
    return dashboard_dir


def export_static_dashboard(db: Session, dashboard_type: str, year: int | None, group_code: str | None, app_state=None, budget_version: int | None = None) -> Path:
    if dashboard_type not in {"department", "group"}:
        raise ValueError("不支持的看板类型。")
    filters = {
        "year": year,
        "budget_version": budget_version,
        "group_code": group_code if dashboard_type == "group" else None,
        "data_view": "budget",
        "top_n": 20,
    }
    title = "部门预算总览" if dashboard_type == "department" else "运营组预算总览"
    prefix = "部门静态看板" if dashboard_type == "department" else "运营组静态看板"
    return export_dashboard_overview(db, filters, app_state, prefix=prefix, title=title, extra_label=group_code)


def export_dashboard_overview(db: Session, filters: dict, app_state=None, prefix: str = "当前视角经营看板", title: str | None = None, extra_label: str | None = None) -> Path:
    overview = dashboard_overview(db, filters, app_state)
    base_dir = get_static_dashboard_dir(app_state)
    version = overview.get("filters", {}).get("budget_version") or filters.get("budget_version")
    version_text = f"第{version}版" if version else "全部版本"
    view_mode = overview.get("view_mode") or "dashboard"
    dashboard_dir = base_dir / f"{safe_filename(prefix)}_{safe_filename(view_mode)}_{version_text}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    (dashboard_dir / "assets").mkdir(parents=True, exist_ok=True)
    (dashboard_dir / "data").mkdir(parents=True, exist_ok=True)
    payload = {
        "export_title": title or overview.get("title") or "经营工作台经营看板",
        "extra_label": extra_label,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "overview": overview,
    }
    (dashboard_dir / "data" / "dashboard-data.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    (dashboard_dir / "README_查看说明.txt").write_text("双击 index.html 即可查看静态经营看板。本看板不需要启动后端服务。", encoding="utf-8")
    index_path = dashboard_dir / "index.html"
    index_path.write_text(render_overview_html(payload), encoding="utf-8")
    return index_path


def safe_filename(value: str) -> str:
    return "".join(char for char in str(value or "") if char not in "/\\:*?\"<>|").strip() or "看板"


def render_overview_html(payload: dict) -> str:
    overview = payload["overview"]
    title = payload["export_title"]
    filter_text = " / ".join(overview.get("breadcrumb") or [])
    empty_notice = "<p class='empty'>暂无汇总数据</p>" if not has_overview_data(overview) else ""
    metric_html = "\n".join(render_metric_card(card) for card in overview.get("metric_cards", []))
    trend_html = "\n".join(render_trend_section(section) for section in overview.get("trend_sections", [])[:4])
    ranking_html = "\n".join(render_report_module(section.get("title", "排名"), section.get("rows", []), section.get("id")) for section in overview.get("ranking_sections", []))
    detail_html = "\n".join(render_report_module(section.get("title", "明细"), section.get("rows", []), section.get("id")) for section in overview.get("table_sections", []))
    insight_html = "\n".join(f"<li class='insight {escape(item.get('level'))}'>{escape(item.get('message'))}</li>" for item in overview.get("health_insights", []))
    data_json = json.dumps(payload, ensure_ascii=False, default=str)
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(title)}</title>
  <style>
    :root {{ color-scheme: light; --blue:#2563eb; --green:#16a34a; --red:#dc2626; --orange:#f97316; --purple:#7c3aed; --text:#162033; --muted:#66758f; --line:#dbe5f3; --bg:#f3f7fc; }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; color: var(--text); background: radial-gradient(circle at top right, rgba(37,99,235,.13), transparent 30%), var(--bg); }}
    .shell {{ display: grid; grid-template-columns: 240px 1fr; min-height: 100vh; }}
    aside {{ background: linear-gradient(180deg, #071a33, #0b2746); color: #fff; padding: 24px 18px; }}
    aside h1 {{ font-size: 22px; margin: 0 0 28px; }}
    aside p {{ color: #b9c7dc; line-height: 1.7; }}
    main {{ padding: 22px; }}
    .topbar {{ display:flex; justify-content:space-between; gap:16px; align-items:flex-start; margin-bottom:18px; }}
    .title h2 {{ margin:0 0 8px; font-size:24px; }}
    .title p {{ margin:0; color:var(--muted); font-size:13px; }}
    .badge {{ display:inline-flex; align-items:center; padding:6px 10px; border-radius:999px; background:#dcfce7; color:#166534; font-weight:700; font-size:12px; }}
    .cover {{ background:linear-gradient(135deg, #ffffff, #f8fbff); border:1px solid var(--line); border-radius:8px; padding:18px; box-shadow:0 14px 38px rgba(31,58,96,.08); margin-bottom:14px; }}
    .metrics {{ display:grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap:14px; }}
    .metric {{ background:#fff; border:1px solid var(--line); border-radius:8px; padding:16px; box-shadow:0 8px 24px rgba(31, 58, 96, .06); }}
    .metric span {{ display:block; color:var(--muted); font-size:12px; margin-bottom:8px; }}
    .metric strong {{ display:block; font-size:24px; }}
    .trend-grid {{ display:grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap:14px; margin-top:14px; align-items:start; }}
    .report-stack {{ display:grid; gap:14px; margin-top:14px; }}
    .card {{ background:#fff; border:1px solid var(--line); border-radius:8px; padding:16px; box-shadow:0 8px 24px rgba(31, 58, 96, .06); overflow:hidden; }}
    .card h3 {{ margin:0 0 12px; font-size:16px; }}
    .report-module {{ background:#fff; border:1px solid var(--line); border-radius:8px; box-shadow:0 10px 28px rgba(31,58,96,.06); overflow:hidden; }}
    .report-module summary {{ list-style:none; cursor:pointer; display:flex; justify-content:space-between; gap:12px; align-items:center; padding:14px 16px; font-weight:800; background:linear-gradient(90deg, #f8fbff, #fff); border-bottom:1px solid var(--line); }}
    .report-module summary::-webkit-details-marker {{ display:none; }}
    .report-module summary span {{ font-size:16px; }}
    .report-module summary small {{ color:var(--muted); font-weight:700; white-space:nowrap; }}
    .report-module summary::after {{ content:"收起"; color:var(--blue); font-size:12px; border:1px solid #bfdbfe; border-radius:999px; padding:3px 8px; }}
    .report-module:not([open]) summary::after {{ content:"展开"; }}
    .module-body {{ padding:14px 16px 16px; }}
    svg {{ width:100%; height:260px; overflow:visible; }}
    .axis {{ stroke:#d7e2f0; stroke-width:1; }}
    .series-0 {{ fill:none; stroke:var(--blue); stroke-width:3; }}
    .series-1 {{ fill:none; stroke:#9bd417; stroke-width:3; }}
    .series-2 {{ fill:none; stroke:#64748b; stroke-width:3; stroke-dasharray:6 6; }}
    .point-0 {{ fill:var(--blue); }}
    .point-1 {{ fill:#9bd417; }}
    .point-2 {{ fill:#64748b; }}
    .table-scroll {{ width:100%; overflow:auto; border:1px solid #e5edf7; border-radius:8px; }}
    table {{ width:100%; min-width:900px; border-collapse:collapse; font-size:12px; }}
    th, td {{ border-bottom:1px solid #e5edf7; padding:8px 10px; text-align:right; white-space:nowrap; }}
    th:first-child, td:first-child {{ text-align:left; }}
    th {{ background:#f6f9fd; color:#52627a; font-weight:700; }}
    .bar-row {{ display:grid; grid-template-columns: 160px 1fr 110px; gap:10px; align-items:center; margin:8px 0; font-size:12px; }}
    .bar-track {{ height:9px; border-radius:999px; background:#e8eef8; overflow:hidden; }}
    .bar-fill {{ height:100%; border-radius:999px; background:linear-gradient(90deg, #2563eb, #60a5fa); }}
    .insights {{ margin:0; padding-left:18px; line-height:1.9; }}
    .empty {{ background:#fff7ed; color:#9a3412; border:1px solid #fed7aa; border-radius:8px; padding:12px; }}
    .footer {{ color:var(--muted); font-size:12px; margin:24px 0 8px; }}
    @media (max-width: 980px) {{ .shell {{ display:block; }} aside {{ border-radius:0 0 16px 16px; }} .metrics, .trend-grid {{ grid-template-columns:1fr; }} main {{ padding:14px; }} }}
  </style>
</head>
<body>
  <div class="shell">
    <aside>
      <h1>经营工作台经营看板</h1>
      <p>这是从首页当前视角导出的离线 HTML 页面，可直接发给同事查看，不需要启动预算系统。</p>
      <p>{escape(payload.get("generated_at"))}</p>
    </aside>
    <main>
      <div class="topbar">
        <div class="title">
          <h2>{escape(title)}</h2>
          <p>{escape(filter_text)}</p>
          {f"<p>补充筛选：{escape(payload.get('extra_label'))}</p>" if payload.get("extra_label") else ""}
        </div>
        <span class="badge">当前视角</span>
      </div>
      {empty_notice}
      <section class="cover"><h3>核心指标</h3><div class="metrics">{metric_html}</div></section>
      <section class="trend-grid">{trend_html}</section>
      <section class="report-stack">
        {ranking_html}
        {detail_html}
        <details class='report-module' open><summary><span>主要经营提醒（{len(overview.get("health_insights", []))} 条）</span><small>点击展开或收起</small></summary><div class='module-body'><ul class="insights">{insight_html}</ul></div></details>
      </section>
      <p class="footer">本页面为只读离线看板，数据快照已内嵌在页面中。</p>
    </main>
  </div>
  <script type="application/json" id="dashboard-data">{escape(data_json)}</script>
</body>
</html>"""


def has_overview_data(overview: dict) -> bool:
    return any(card.get("value") for card in overview.get("metric_cards", [])) or any(section.get("rows") for section in overview.get("trend_sections", []))


def money(value) -> str:
    return f"{((value or 0) / 10000):,.2f} 万元"


def percent(value) -> str:
    return "" if value is None else f"{value:.2%}"


def render_metric_card(card: dict) -> str:
    value = format_value(card.get("value"), card.get("format"))
    sub = ""
    if card.get("sub_value") is not None:
        sub = f"<span>{escape(card.get('sub_label') or '')}：{format_value(card.get('sub_value'), card.get('format'))}</span>"
    return f"<div class='metric'><span>{escape(card.get('label'))}</span><strong>{escape(value)}</strong>{sub}</div>"


def render_trend_section(section: dict) -> str:
    rows = section.get("rows", [])
    series = [item for item in section.get("series", []) if "未上传" not in item.get("name", "")]
    chart = render_svg_chart(rows, section.get("x_field"), series)
    return f"<div class='card'><h3>{escape(section.get('title'))}</h3>{chart}</div>"


def render_svg_chart(rows: list[dict], x_field: str, series: list[dict]) -> str:
    if not rows or not series:
        return "<p class='empty'>暂无趋势数据</p>"
    width, height = 900, 260
    padding_left, padding_right, padding_top, padding_bottom = 54, 20, 18, 34
    points_by_series = []
    all_values = []
    for item in series:
        points = []
        for index, row in enumerate(rows):
            raw_value = row.get(item.get("field"))
            if raw_value is None:
                points.append(None)
                continue
            value = float(raw_value) / 10000
            points.append(value)
            all_values.append(value)
        points_by_series.append(points)
    if not all_values:
        return "<p class='empty'>暂无趋势数据</p>"
    min_value = min(min(all_values), 0)
    max_value = max(max(all_values), 0)
    if min_value == max_value:
        max_value = min_value + 1
    plot_width = width - padding_left - padding_right
    plot_height = height - padding_top - padding_bottom

    def x_pos(index: int) -> float:
        return padding_left + (plot_width * index / max(len(rows) - 1, 1))

    def y_pos(value: float) -> float:
        return padding_top + (max_value - value) / (max_value - min_value) * plot_height

    grid = []
    for step in range(5):
        y = padding_top + plot_height * step / 4
        grid.append(f"<line class='axis' x1='{padding_left}' y1='{y:.1f}' x2='{width - padding_right}' y2='{y:.1f}' />")
    line_html = []
    for series_index, points in enumerate(points_by_series):
        path_parts = []
        for index, value in enumerate(points):
            if value is None:
                continue
            path_parts.append(f"{x_pos(index):.1f},{y_pos(value):.1f}")
        if path_parts:
            line_html.append(f"<polyline class='series-{series_index % 3}' points='{' '.join(path_parts)}' />")
            for index, value in enumerate(points):
                if value is not None:
                    line_html.append(f"<circle class='point-{series_index % 3}' cx='{x_pos(index):.1f}' cy='{y_pos(value):.1f}' r='3.5' />")
    labels = []
    for index, row in enumerate(rows):
        labels.append(f"<text x='{x_pos(index):.1f}' y='{height - 10}' text-anchor='middle' font-size='11' fill='#66758f'>{escape(row.get(x_field))}月</text>")
    legend = []
    for series_index, item in enumerate(series):
        color = ["#2563eb", "#9bd417", "#64748b"][series_index % 3]
        legend.append(f"<span><i style='display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:5px;background:{color}'></i>{escape(item.get('name'))}</span>")
    return f"<div style='display:flex;gap:14px;justify-content:center;font-size:12px;color:#66758f;margin-bottom:8px;'>{''.join(legend)}</div><svg viewBox='0 0 {width} {height}'>{''.join(grid)}{''.join(line_html)}{''.join(labels)}</svg>"


def render_report_module(title: str, rows: list[dict], section_id: str | None = None) -> str:
    row_count = len(rows)
    summary_title = f"{title}（{row_count} 行）"
    if not rows:
        body = "<p class='empty'>暂无数据</p>"
    elif section_id in {"sales_ranking", "expense_overrun"}:
        body = f"{render_bar_list(rows, section_id)}{render_table(rows)}"
    else:
        body = render_table(rows)
    return (
        f"<details class='report-module' open>"
        f"<summary><span>{escape(summary_title)}</span><small>点击展开或收起</small></summary>"
        f"<div class='module-body'>{body}</div>"
        f"</details>"
    )


def render_table_card(title: str, rows: list[dict], section_id: str | None = None) -> str:
    if not rows:
        return f"<div class='card'><h3>{escape(title)}</h3><p class='empty'>暂无数据</p></div>"
    if section_id in {"sales_ranking", "expense_overrun"}:
        return f"<div class='card'><h3>{escape(title)}</h3>{render_bar_list(rows, section_id)}{render_table(rows)}</div>"
    return f"<div class='card'><h3>{escape(title)}</h3>{render_table(rows)}</div>"


def render_bar_list(rows: list[dict], section_id: str | None) -> str:
    if section_id == "expense_overrun":
        value_key = "actual_expense_amount"
        label_key = "expense_item"
    else:
        value_key = "actual_sales_amount" if any(row.get("actual_sales_amount") for row in rows) else "budget_sales_amount"
        label_key = "name"
    max_value = max(float(row.get(value_key) or 0) for row in rows) or 1
    items = []
    for row in rows[:8]:
        value = float(row.get(value_key) or 0)
        width = min(max(value / max_value * 100, 2), 100)
        items.append(
            f"<div class='bar-row'><span>{escape(row.get(label_key) or row.get('expense_category') or '未命名')}</span><div class='bar-track'><div class='bar-fill' style='width:{width:.1f}%'></div></div><strong>{escape(money(value))}</strong></div>"
        )
    return "".join(items)


def render_table(rows: list[dict]) -> str:
    headers = [key for key in rows[0].keys() if key not in {"id"}]
    head = "".join(f"<th>{escape(column_label(key))}</th>" for key in headers)
    body_rows = []
    for row in rows:
        cells = "".join(f"<td>{escape(format_cell(key, row.get(key)))}</td>" for key in headers)
        body_rows.append(f"<tr>{cells}</tr>")
    return f"<div class='table-scroll'><table><thead><tr>{head}</tr></thead><tbody>{''.join(body_rows)}</tbody></table></div>"


def column_label(key: str) -> str:
    labels = {
        "name": "名称",
        "month": "月份",
        "group_name": "运营组",
        "group_code": "运营组编码",
        "shop_name": "店铺",
        "shop_code": "店铺编码",
        "product_name": "产品",
        "product_code": "产品编码",
        "category": "品类",
        "expense_category": "费用大项",
        "expense_item": "费用小项",
        "budget_quantity": "预算数量",
        "actual_quantity": "实际数量",
        "quantity_diff": "数量差异",
        "budget_sales_amount": "预算销售额",
        "actual_sales_amount": "实际销售额",
        "sales_diff": "销售差异",
        "budget_cost_amount": "预算成本额",
        "actual_cost_amount": "实际成本额",
        "cost_diff": "成本差异",
        "budget_gross_profit": "预算毛利额",
        "actual_gross_profit": "实际毛利额",
        "gross_profit_diff": "毛利差异",
        "budget_expense_amount": "预算费用额",
        "actual_expense_amount": "实际费用额",
        "expense_diff": "费用差异",
        "budget_profit_amount": "预算利润额",
        "actual_profit_amount": "实际利润额",
        "profit_diff": "利润差异",
        "budget_cost_rate": "预算成本率",
        "actual_cost_rate": "实际成本率",
        "cost_usage_rate": "成本使用率",
        "budget_expense_rate": "预算费用率",
        "actual_expense_rate": "实际费用率",
        "expense_usage_rate": "费用使用率",
        "budget_profit_rate": "预算利润率",
        "actual_profit_rate": "实际利润率",
        "profit_rate_diff": "利润率差异",
        "quantity_completion_rate": "数量完成率",
        "sales_completion_rate": "完成率",
        "annual_completion_rate": "全年达成率",
        "same_period_completion_rate": "同期达成率",
        "annual_sales_completion_rate": "全年销售达成率",
        "same_period_sales_completion_rate": "同期销售达成率",
        "sales_amount": "销售额",
        "cost_amount": "成本额",
        "gross_profit": "毛利额",
        "expense_amount": "费用额",
        "profit_amount": "利润额",
        "profit_rate": "利润率",
        "expense_rate": "费用率",
        "value": "数值",
        "label": "项目",
    }
    return labels.get(key, key)


def format_cell(key: str, value) -> str:
    if value is None:
        return "-"
    if key == "month":
        return f"{value}月"
    if key in PERCENT_FIELDS or key.endswith("_rate"):
        return percent(float(value))
    if key in QUANTITY_FIELDS:
        return f"{float(value):,.2f}"
    if key in MONEY_FIELDS or key.endswith("_amount") or key.endswith("_diff"):
        return money(float(value))
    return str(value)


def format_value(value, format_type: str | None) -> str:
    if value is None:
        return "-"
    if format_type == "amount":
        return money(float(value))
    if format_type == "percent":
        return percent(float(value))
    return str(value)


def escape(value) -> str:
    return (
        str(value or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )
