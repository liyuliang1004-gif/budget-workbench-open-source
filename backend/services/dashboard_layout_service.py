import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from backend.config import BASE_DIR, DASHBOARD_LAYOUT_RELATIVE_PATH
from backend.database.models import ActualExpenseDetail, ActualSalesDetail, ExpenseBudgetDetail, SalesBudgetDetail
from backend.services.comparison_service import (
    apply_actual_expense_filters,
    apply_actual_sales_filters,
    apply_budget_expense_filters,
    apply_budget_sales_filters,
    dashboard_overview,
    ratio,
    resolve_names,
    round2,
)
from backend.services.expense_category_service import classify_actual_expense_category


TREND_CHART_TYPES = ["line", "smooth_line", "area", "step_line", "scatter", "bar", "horizontal_bar"]
RANKING_CHART_TYPES = ["bar_table", "bar", "horizontal_bar", "table"]
CUSTOM_CHART_TYPES = ["bar_table", "bar", "horizontal_bar", "table", "line", "smooth_line", "area", "step_line", "scatter"]

STANDARD_WIDGETS = [
    {"id": "metric_cards", "title": "核心指标卡", "kind": "standard", "category": "指标", "allowed_chart_types": ["metric"], "default_chart_type": "metric", "default_width": "full"},
    {"id": "actual_coverage", "title": "实际数据覆盖", "kind": "standard", "category": "状态", "allowed_chart_types": ["status"], "default_chart_type": "status", "default_width": "full"},
    {"id": "sales_trend", "title": "销售额趋势", "kind": "standard", "category": "趋势", "allowed_chart_types": TREND_CHART_TYPES, "default_chart_type": "line", "default_width": "half"},
    {"id": "profit_trend", "title": "利润额趋势", "kind": "standard", "category": "趋势", "allowed_chart_types": TREND_CHART_TYPES, "default_chart_type": "line", "default_width": "half"},
    {"id": "cost_trend", "title": "成本额趋势", "kind": "standard", "category": "趋势", "allowed_chart_types": TREND_CHART_TYPES, "default_chart_type": "line", "default_width": "half"},
    {"id": "expense_trend", "title": "费用额趋势", "kind": "standard", "category": "趋势", "allowed_chart_types": TREND_CHART_TYPES, "default_chart_type": "line", "default_width": "half"},
    {"id": "sales_ranking", "title": "销售表现排名", "kind": "standard", "category": "排名", "allowed_chart_types": RANKING_CHART_TYPES, "default_chart_type": "bar_table", "default_width": "half"},
    {"id": "expense_overrun", "title": "费用项目使用情况", "kind": "standard", "category": "排名", "allowed_chart_types": RANKING_CHART_TYPES, "default_chart_type": "bar_table", "default_width": "half"},
    {"id": "comparison_detail", "title": "预算实际对比明细", "kind": "standard", "category": "明细", "allowed_chart_types": ["table"], "default_chart_type": "table", "default_width": "half"},
    {"id": "expense_category_detail", "title": "费用预算实际按费用项展开", "kind": "standard", "category": "明细", "allowed_chart_types": ["table"], "default_chart_type": "table", "default_width": "half"},
    {"id": "health_insights", "title": "主要经营提醒", "kind": "standard", "category": "提醒", "allowed_chart_types": ["insight"], "default_chart_type": "insight", "default_width": "half"},
]

METRICS = [
    {"id": "sales_amount", "label": "销售额", "format": "amount"},
    {"id": "cost_amount", "label": "成本额", "format": "amount"},
    {"id": "gross_profit", "label": "毛利额", "format": "amount"},
    {"id": "expense_amount", "label": "费用额", "format": "amount"},
    {"id": "profit_amount", "label": "利润额", "format": "amount"},
    {"id": "profit_rate", "label": "利润率", "format": "percent"},
    {"id": "expense_rate", "label": "费用率", "format": "percent"},
    {"id": "sales_completion_rate", "label": "销售达成率", "format": "percent"},
    {"id": "expense_usage_rate", "label": "费用使用率", "format": "percent"},
    {"id": "annual_completion_rate", "label": "全年达成率", "format": "percent"},
    {"id": "same_period_completion_rate", "label": "同期达成率", "format": "percent"},
]

DIMENSIONS = [
    {"id": "month", "label": "月份"},
    {"id": "group", "label": "运营组"},
    {"id": "shop", "label": "店铺"},
    {"id": "product", "label": "产品"},
    {"id": "expense_category", "label": "费用大项"},
]

DATA_VIEWS = [
    {"id": "budget", "label": "预算"},
    {"id": "actual", "label": "实际"},
    {"id": "comparison", "label": "预算 vs 实际"},
]

SORT_OPTIONS = [
    {"id": "budget", "label": "预算值"},
    {"id": "actual", "label": "实际值"},
    {"id": "diff", "label": "差异"},
    {"id": "rate", "label": "达成率/使用率"},
]

FORBIDDEN_COMBINATIONS = [
    {
        "dimension": "product",
        "metrics": ["expense_amount", "expense_rate", "profit_amount", "profit_rate"],
        "reason": "产品维度暂未建立费用分摊规则，不能展示产品费用率、产品利润额或产品利润率。",
    }
]

METRIC_BY_ID = {item["id"]: item for item in METRICS}
STANDARD_BY_ID = {item["id"]: item for item in STANDARD_WIDGETS}
DIMENSION_BY_ID = {item["id"]: item for item in DIMENSIONS}
VALID_CHART_TYPES = {
    "metric",
    "status",
    "line",
    "smooth_line",
    "area",
    "step_line",
    "scatter",
    "bar",
    "horizontal_bar",
    "bar_table",
    "table",
    "insight",
}
VALID_TOP_N = {5, 10, 20, 50}


def get_dashboard_layout_path(app_state=None) -> Path:
    override = getattr(app_state, "dashboard_layout_path_override", None) if app_state else None
    return Path(override) if override else BASE_DIR / DASHBOARD_LAYOUT_RELATIVE_PATH


def default_dashboard_layout() -> dict[str, Any]:
    widgets = []
    order = 10
    visible_defaults = {
        "metric_cards",
        "actual_coverage",
        "sales_trend",
        "profit_trend",
        "sales_ranking",
        "expense_overrun",
        "comparison_detail",
        "expense_category_detail",
        "health_insights",
    }
    for item in STANDARD_WIDGETS:
        widgets.append(
            {
                "id": item["id"],
                "module_id": item["id"],
                "kind": "standard",
                "title": item["title"],
                "visible": item["id"] in visible_defaults,
                "order": order,
                "width": item["default_width"],
                "chart_type": item["default_chart_type"],
                "expanded": False,
            }
        )
        order += 10
    return {"version": 1, "widgets": widgets}


def widget_catalog() -> dict[str, Any]:
    return {
        "standard_widgets": STANDARD_WIDGETS,
        "metrics": METRICS,
        "dimensions": DIMENSIONS,
        "data_views": DATA_VIEWS,
        "sort_options": SORT_OPTIONS,
        "chart_types": [
            {"id": "line", "label": "折线图"},
            {"id": "smooth_line", "label": "平滑折线图"},
            {"id": "area", "label": "面积图"},
            {"id": "step_line", "label": "阶梯图"},
            {"id": "scatter", "label": "散点图"},
            {"id": "bar", "label": "柱状图"},
            {"id": "horizontal_bar", "label": "横向柱状图"},
            {"id": "bar_table", "label": "图表+表格"},
            {"id": "table", "label": "表格"},
            {"id": "metric", "label": "指标卡"},
            {"id": "status", "label": "状态块"},
            {"id": "insight", "label": "提醒"},
        ],
        "top_n_options": sorted(VALID_TOP_N),
        "forbidden_combinations": FORBIDDEN_COMBINATIONS,
    }


def read_dashboard_layout(app_state=None) -> dict[str, Any]:
    path = get_dashboard_layout_path(app_state)
    if not path.exists():
        return default_dashboard_layout()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return validate_layout(payload)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"首页配置文件无法读取：{exc}") from exc


def write_dashboard_layout(payload: dict[str, Any], app_state=None) -> dict[str, Any]:
    layout = validate_layout(payload)
    path = get_dashboard_layout_path(app_state)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(layout, ensure_ascii=False, indent=2), encoding="utf-8")
    return layout


def reset_dashboard_layout(app_state=None) -> dict[str, Any]:
    layout = default_dashboard_layout()
    path = get_dashboard_layout_path(app_state)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(layout, ensure_ascii=False, indent=2), encoding="utf-8")
    return layout


def validate_layout(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="首页配置必须是对象。")
    widgets = payload.get("widgets")
    if not isinstance(widgets, list):
        raise HTTPException(status_code=400, detail="首页配置缺少 widgets 列表。")
    normalized_widgets = [validate_widget(item, index) for index, item in enumerate(widgets)]
    return {"version": int(payload.get("version") or 1), "widgets": normalized_widgets}


def validate_widget(item: dict[str, Any], index: int = 0) -> dict[str, Any]:
    if not isinstance(item, dict):
        raise HTTPException(status_code=400, detail="首页模块配置必须是对象。")
    kind = item.get("kind") or "standard"
    if kind not in {"standard", "custom"}:
        raise HTTPException(status_code=400, detail="首页模块类型不正确。")
    width = item.get("width") or "half"
    if width not in {"half", "full"}:
        raise HTTPException(status_code=400, detail="首页模块宽度只能是 half 或 full。")
    chart_type = item.get("chart_type")
    if kind == "standard":
        module_id = item.get("module_id") or item.get("id")
        definition = STANDARD_BY_ID.get(module_id)
        if not definition:
            raise HTTPException(status_code=400, detail=f"未知首页标准模块：{module_id}")
        chart_type = chart_type or definition["default_chart_type"]
        if chart_type not in definition["allowed_chart_types"]:
            raise HTTPException(status_code=400, detail=f"{definition['title']} 不支持 {chart_type} 图表类型。")
        return {
            "id": str(item.get("id") or module_id),
            "module_id": module_id,
            "kind": "standard",
            "title": str(item.get("title") or definition["title"]),
            "visible": bool(item.get("visible", True)),
            "order": int(item.get("order") or (index + 1) * 10),
            "width": width,
            "chart_type": chart_type,
            "expanded": bool(item.get("expanded", False)),
        }
    custom_config = item.get("custom_config") or {}
    validated_custom = validate_custom_config(custom_config)
    chart_type = chart_type or "bar_table"
    if chart_type not in CUSTOM_CHART_TYPES:
        raise HTTPException(status_code=400, detail="自定义图表只支持系统目录中的图表类型。")
    return {
        "id": str(item.get("id") or f"custom_{index + 1}"),
        "module_id": item.get("module_id") or "custom",
        "kind": "custom",
        "title": str(item.get("title") or build_custom_title(validated_custom)),
        "visible": bool(item.get("visible", True)),
        "order": int(item.get("order") or (index + 1) * 10),
        "width": width,
        "chart_type": chart_type,
        "expanded": bool(item.get("expanded", False)),
        "custom_config": validated_custom,
    }


def validate_custom_config(config: dict[str, Any]) -> dict[str, Any]:
    metric = config.get("metric")
    dimension = config.get("dimension")
    data_view = config.get("data_view") or "comparison"
    sort_by = config.get("sort_by") or "actual"
    top_n = int(config.get("top_n") or 10)
    if metric not in METRIC_BY_ID:
        raise HTTPException(status_code=400, detail="自定义图表指标不正确。")
    if dimension not in DIMENSION_BY_ID:
        raise HTTPException(status_code=400, detail="自定义图表维度不正确。")
    if data_view not in {"budget", "actual", "comparison"}:
        raise HTTPException(status_code=400, detail="自定义图表数据视图不正确。")
    if sort_by not in {"budget", "actual", "diff", "rate"}:
        raise HTTPException(status_code=400, detail="自定义图表排序方式不正确。")
    if top_n not in VALID_TOP_N:
        raise HTTPException(status_code=400, detail="自定义图表 TOP N 只能选择 5、10、20、50。")
    if dimension == "product" and metric in {"expense_amount", "expense_rate", "profit_amount", "profit_rate"}:
        raise HTTPException(status_code=400, detail="产品维度暂未建立费用分摊规则，不能展示产品费用率、产品利润额或产品利润率。")
    return {"metric": metric, "dimension": dimension, "data_view": data_view, "sort_by": sort_by, "top_n": top_n}


def build_custom_title(config: dict[str, Any]) -> str:
    dimension = DIMENSION_BY_ID[config["dimension"]]["label"]
    metric = METRIC_BY_ID[config["metric"]]["label"]
    return f"按{dimension}的{metric} TOP{config['top_n']}"


def dashboard_widgets_data(db: Session, payload: dict[str, Any], app_state=None) -> dict[str, Any]:
    filters = payload.get("filters") or {}
    widgets = [validate_widget(item, index) for index, item in enumerate(payload.get("widgets") or [])]
    overview = dashboard_overview(db, filters, app_state)
    widget_data = []
    for widget in sorted([item for item in widgets if item.get("visible", True)], key=lambda item: item["order"]):
        if widget["kind"] == "custom":
            widget_data.append(build_custom_widget_data(db, filters, widget, app_state))
        else:
            widget_data.append({"id": widget["id"], "module_id": widget["module_id"], "kind": "standard", "chart_type": widget["chart_type"], "width": widget["width"], "data": extract_standard_widget_data(overview, widget)})
    return {"overview": overview, "widgets": widget_data}


def extract_standard_widget_data(overview: dict[str, Any], widget: dict[str, Any]) -> Any:
    module_id = widget["module_id"]
    if module_id == "metric_cards":
        return overview.get("metric_cards") or []
    if module_id == "actual_coverage":
        return overview.get("actual_coverage")
    if module_id in {"sales_trend", "profit_trend", "cost_trend", "expense_trend"}:
        keyword = module_id.split("_")[0]
        return [section for section in overview.get("trend_sections", []) if keyword in section.get("id", "")]
    if module_id in {"sales_ranking", "expense_overrun"}:
        return next((section for section in overview.get("ranking_sections", []) if section.get("id") == module_id), None)
    if module_id in {"comparison_detail", "expense_category_detail"}:
        return next((section for section in overview.get("table_sections", []) if section.get("id") == module_id), None)
    if module_id == "health_insights":
        return overview.get("health_insights") or []
    return None


def build_custom_widget_data(db: Session, filters: dict[str, Any], widget: dict[str, Any], app_state=None) -> dict[str, Any]:
    config = widget["custom_config"]
    scoped_filters = {**filters, "data_view": config["data_view"], "top_n": config["top_n"]}
    ctx = resolve_names(scoped_filters, app_state)
    budget_sales_rows = apply_budget_sales_filters(db.query(SalesBudgetDetail), ctx).all()
    actual_sales_rows = apply_actual_sales_filters(db.query(ActualSalesDetail), ctx).all()
    product_scoped = config["dimension"] == "product"
    budget_expense_rows = [] if product_scoped else apply_budget_expense_filters(db.query(ExpenseBudgetDetail), ctx).all()
    actual_expense_rows = [] if product_scoped else apply_actual_expense_filters(db.query(ActualExpenseDetail), ctx).all()
    grouped = group_custom_rows(config["dimension"], budget_sales_rows, actual_sales_rows, budget_expense_rows, actual_expense_rows)
    rows = []
    for name, values in grouped.items():
        row = {"name": name, **calculate_custom_metrics(values)}
        rows.append(row)
    metric_field = field_for_metric(config["metric"], config["data_view"])
    sort_field = field_for_sort(config["sort_by"], config["metric"], config["data_view"])
    rows = sorted(rows, key=lambda item: float(item.get(sort_field) or 0), reverse=True)[: config["top_n"]]
    return {
        "id": widget["id"],
        "module_id": widget["module_id"],
        "kind": "custom",
        "title": widget["title"],
        "chart_type": widget["chart_type"],
        "width": widget["width"],
        "metric": config["metric"],
        "metric_label": METRIC_BY_ID[config["metric"]]["label"],
        "format": METRIC_BY_ID[config["metric"]]["format"],
        "dimension": config["dimension"],
        "dimension_label": DIMENSION_BY_ID[config["dimension"]]["label"],
        "value_field": metric_field,
        "rows": rows,
    }


def group_custom_rows(dimension: str, budget_sales_rows, actual_sales_rows, budget_expense_rows, actual_expense_rows) -> dict[str, dict[str, float]]:
    grouped: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for row in budget_sales_rows:
        key = dimension_key(dimension, row)
        grouped[key]["budget_sales_amount"] += row.budget_sales_amount or 0
        grouped[key]["budget_cost_amount"] += row.budget_cost_amount or 0
        grouped[key]["budget_gross_profit"] += row.budget_gross_profit or 0
    for row in actual_sales_rows:
        key = dimension_key(dimension, row)
        grouped[key]["actual_sales_amount"] += row.actual_sales_amount or 0
        grouped[key]["actual_cost_amount"] += row.actual_cost_amount or 0
        grouped[key]["actual_gross_profit"] += row.actual_gross_profit or 0
    for row in budget_expense_rows:
        key = dimension_key(dimension, row, expense=True)
        grouped[key]["budget_expense_amount"] += row.budget_expense_amount or 0
    for row in actual_expense_rows:
        key = dimension_key(dimension, row, expense=True)
        grouped[key]["actual_expense_amount"] += row.actual_expense_amount or 0
    return grouped


def dimension_key(dimension: str, row, expense: bool = False) -> str:
    if dimension == "month":
        return f"{row.month}月"
    if dimension == "group":
        return getattr(row, "group_name", None) or getattr(row, "group_code", None) or "未命名运营组"
    if dimension == "shop":
        return getattr(row, "shop_name", None) or getattr(row, "shop_code", None) or "未命名店铺"
    if dimension == "product":
        return getattr(row, "product_name", None) or getattr(row, "product_code", None) or "未命名产品"
    if dimension == "expense_category":
        if expense and isinstance(row, ActualExpenseDetail):
            return classify_actual_expense_category(row.expense_item, row.expense_category)
        return getattr(row, "expense_category", None) or "未分类"
    return "未分类"


def calculate_custom_metrics(values: dict[str, float]) -> dict[str, float | None]:
    budget_sales = values.get("budget_sales_amount", 0)
    actual_sales = values.get("actual_sales_amount", 0)
    budget_cost = values.get("budget_cost_amount", 0)
    actual_cost = values.get("actual_cost_amount", 0)
    budget_expense = values.get("budget_expense_amount", 0)
    actual_expense = values.get("actual_expense_amount", 0)
    budget_profit = budget_sales - budget_cost - budget_expense
    actual_profit = actual_sales - actual_cost - actual_expense
    return {
        "budget_sales_amount": round2(budget_sales),
        "actual_sales_amount": round2(actual_sales),
        "sales_diff": round2(actual_sales - budget_sales),
        "sales_completion_rate": ratio(actual_sales, budget_sales),
        "budget_cost_amount": round2(budget_cost),
        "actual_cost_amount": round2(actual_cost),
        "cost_diff": round2(actual_cost - budget_cost),
        "budget_gross_profit": round2(values.get("budget_gross_profit", budget_sales - budget_cost)),
        "actual_gross_profit": round2(values.get("actual_gross_profit", actual_sales - actual_cost)),
        "budget_expense_amount": round2(budget_expense),
        "actual_expense_amount": round2(actual_expense),
        "expense_diff": round2(actual_expense - budget_expense),
        "expense_usage_rate": ratio(actual_expense, budget_expense),
        "budget_profit_amount": round2(budget_profit),
        "actual_profit_amount": round2(actual_profit),
        "profit_diff": round2(actual_profit - budget_profit),
        "budget_profit_rate": ratio(budget_profit, budget_sales),
        "actual_profit_rate": ratio(actual_profit, actual_sales),
        "budget_expense_rate": ratio(budget_expense, budget_sales),
        "actual_expense_rate": ratio(actual_expense, actual_sales),
    }


def field_for_metric(metric: str, data_view: str) -> str:
    prefix = "budget" if data_view == "budget" else "actual"
    mapping = {
        "sales_amount": f"{prefix}_sales_amount",
        "cost_amount": f"{prefix}_cost_amount",
        "gross_profit": f"{prefix}_gross_profit",
        "expense_amount": f"{prefix}_expense_amount",
        "profit_amount": f"{prefix}_profit_amount",
        "profit_rate": f"{prefix}_profit_rate",
        "expense_rate": f"{prefix}_expense_rate",
        "sales_completion_rate": "sales_completion_rate",
        "expense_usage_rate": "expense_usage_rate",
        "annual_completion_rate": "sales_completion_rate",
        "same_period_completion_rate": "sales_completion_rate",
    }
    return mapping[metric]


def field_for_sort(sort_by: str, metric: str, data_view: str) -> str:
    if sort_by == "diff":
        if metric == "expense_amount":
            return "expense_diff"
        if metric == "profit_amount":
            return "profit_diff"
        if metric == "cost_amount":
            return "cost_diff"
        return "sales_diff"
    if sort_by == "rate":
        if metric in {"expense_amount", "expense_rate", "expense_usage_rate"}:
            return "expense_usage_rate"
        return "sales_completion_rate"
    if sort_by == "budget":
        return field_for_metric(metric, "budget")
    if sort_by == "actual":
        return field_for_metric(metric, "actual")
    return field_for_metric(metric, data_view)
