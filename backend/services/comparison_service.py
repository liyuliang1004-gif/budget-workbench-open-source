from collections import defaultdict
from dataclasses import dataclass, replace

from sqlalchemy import func, or_
from sqlalchemy.orm import Query, Session

from backend.database.models import ActualExpenseDetail, ActualSalesDetail, ExpenseBudgetDetail, SalesBudgetDetail
from backend.services.expense_category_service import classify_actual_expense_category
from backend.services.metadata_service import list_groups_shops


@dataclass
class DashboardContext:
    year: int
    budget_version: int
    month: int | None
    group_code: str | None
    group_name: str | None
    shop_code: str | None
    shop_name: str | None
    product_code: str | None
    product_name: str | None
    data_view: str
    top_n: int


def round2(value: float | None) -> float:
    return round(float(value or 0), 2)


def amount_wan(value: float | None) -> str:
    return f"{round2((value or 0) / 10000)} 万元"


UNCLASSIFIED_ACTUAL_EXPENSE = "未分类实际费用"
ACTUAL_ONLY_EXPENSE_CATEGORY = ""


def clean_expense_text(value: str | None, fallback: str) -> str:
    text = str(value or "").strip()
    if not text or text == UNCLASSIFIED_ACTUAL_EXPENSE:
        return fallback
    return text


def budget_expense_item_key(row: ExpenseBudgetDetail) -> tuple[str, str]:
    category = clean_expense_text(row.expense_category, "未分类预算费用")
    item = clean_expense_text(row.expense_item, category)
    return category, item


def actual_expense_item_key(row: ActualExpenseDetail) -> tuple[str, str]:
    item = clean_expense_text(row.expense_item, "未命名实际费用")
    category = classify_actual_expense_category(item, row.expense_category)
    if category == UNCLASSIFIED_ACTUAL_EXPENSE:
        category = ACTUAL_ONLY_EXPENSE_CATEGORY
    return category, item


def ratio(numerator: float, denominator: float) -> float | None:
    return round(numerator / denominator, 6) if denominator else None


def normalize_view(value: str | None) -> str:
    return value if value in {"budget", "actual", "comparison"} else "comparison"


def resolve_names(filters: dict, app_state=None) -> DashboardContext:
    registry = list_groups_shops(app_state)
    groups = registry.get("operation_groups", [])
    group_code = filters.get("group_code") or None
    shop_code = filters.get("shop_code") or None
    group_name = filters.get("group_name") or None
    shop_name = filters.get("shop_name") or None
    for group in groups:
        if group_code and group["group_code"] == group_code:
            group_name = group["group_name"]
        for shop in group.get("shops", []):
            if shop_code and shop["shop_code"] == shop_code:
                shop_name = shop["shop_name"]
                group_code = group_code or group["group_code"]
                group_name = group_name or group["group_name"]
    return DashboardContext(
        year=int(filters.get("year") or 2026),
        budget_version=int(filters.get("budget_version") or 1),
        month=int(filters["month"]) if filters.get("month") not in ("", None) else None,
        group_code=group_code,
        group_name=group_name,
        shop_code=shop_code,
        shop_name=shop_name,
        product_code=filters.get("product_code") or None,
        product_name=filters.get("product_name") or None,
        data_view=normalize_view(filters.get("data_view")),
        top_n=max(1, min(int(filters.get("top_n") or 10), 50)),
    )


def apply_budget_sales_filters(query: Query, ctx: DashboardContext) -> Query:
    query = query.filter(SalesBudgetDetail.year == ctx.year, SalesBudgetDetail.budget_version == ctx.budget_version)
    if ctx.month:
        query = query.filter(SalesBudgetDetail.month == ctx.month)
    if ctx.group_code:
        query = query.filter(or_(SalesBudgetDetail.group_code == ctx.group_code, SalesBudgetDetail.group_name == ctx.group_name))
    elif ctx.group_name:
        query = query.filter(SalesBudgetDetail.group_name == ctx.group_name)
    if ctx.shop_code:
        query = query.filter(or_(SalesBudgetDetail.shop_code == ctx.shop_code, SalesBudgetDetail.shop_name == ctx.shop_name))
    elif ctx.shop_name:
        query = query.filter(SalesBudgetDetail.shop_name == ctx.shop_name)
    if ctx.product_code:
        query = query.filter(SalesBudgetDetail.product_code == ctx.product_code)
    if ctx.product_name:
        query = query.filter(SalesBudgetDetail.product_name == ctx.product_name)
    return query


def apply_budget_expense_filters(query: Query, ctx: DashboardContext) -> Query:
    query = query.filter(ExpenseBudgetDetail.year == ctx.year, ExpenseBudgetDetail.budget_version == ctx.budget_version)
    if ctx.month:
        query = query.filter(ExpenseBudgetDetail.month == ctx.month)
    if ctx.group_code:
        query = query.filter(ExpenseBudgetDetail.group_code == ctx.group_code)
    if ctx.shop_code:
        query = query.filter(ExpenseBudgetDetail.shop_code == ctx.shop_code)
    return query


def apply_actual_sales_filters(query: Query, ctx: DashboardContext) -> Query:
    query = query.filter(ActualSalesDetail.year == ctx.year)
    if ctx.month:
        query = query.filter(ActualSalesDetail.month == ctx.month)
    if ctx.group_name:
        query = query.filter(ActualSalesDetail.group_name == ctx.group_name)
    if ctx.shop_name:
        query = query.filter(ActualSalesDetail.shop_name == ctx.shop_name)
    if ctx.product_code:
        query = query.filter(ActualSalesDetail.product_code == ctx.product_code)
    if ctx.product_name:
        query = query.filter(ActualSalesDetail.product_name == ctx.product_name)
    return query


def apply_actual_expense_filters(query: Query, ctx: DashboardContext) -> Query:
    query = query.filter(ActualExpenseDetail.year == ctx.year)
    if ctx.month:
        query = query.filter(ActualExpenseDetail.month == ctx.month)
    if ctx.group_name:
        query = query.filter(ActualExpenseDetail.group_name == ctx.group_name)
    if ctx.shop_name:
        query = query.filter(ActualExpenseDetail.shop_name == ctx.shop_name)
    return query


def sales_totals(rows, prefix: str) -> dict:
    quantity_field = "budget_quantity" if prefix == "budget" else "actual_quantity"
    sales_field = "budget_sales_amount" if prefix == "budget" else "actual_sales_amount"
    cost_field = "budget_cost_amount" if prefix == "budget" else "actual_cost_amount"
    quantity = sum(getattr(row, quantity_field) or 0 for row in rows)
    sales = sum(getattr(row, sales_field) or 0 for row in rows)
    cost = sum(getattr(row, cost_field) or 0 for row in rows)
    return {"quantity": quantity, "sales": sales, "cost": cost, "gross": sales - cost}


def build_summary_values(budget_sales: dict, actual_sales: dict, budget_expense: float, actual_expense: float, data_view: str) -> dict:
    values: dict[str, float | None] = {}
    if data_view in {"budget", "comparison"}:
        budget_profit = budget_sales["sales"] - budget_sales["cost"] - budget_expense
        values.update(
            {
                "budget_quantity": round2(budget_sales["quantity"]),
                "budget_sales_amount": round2(budget_sales["sales"]),
                "budget_cost_amount": round2(budget_sales["cost"]),
                "budget_gross_profit": round2(budget_sales["gross"]),
                "budget_expense_amount": round2(budget_expense),
                "budget_profit_amount": round2(budget_profit),
                "budget_cost_rate": ratio(budget_sales["cost"], budget_sales["sales"]),
                "budget_expense_rate": ratio(budget_expense, budget_sales["sales"]),
                "budget_profit_rate": ratio(budget_profit, budget_sales["sales"]),
            }
        )
    if data_view in {"actual", "comparison"}:
        actual_profit = actual_sales["sales"] - actual_sales["cost"] - actual_expense
        values.update(
            {
                "actual_quantity": round2(actual_sales["quantity"]),
                "actual_sales_amount": round2(actual_sales["sales"]),
                "actual_cost_amount": round2(actual_sales["cost"]),
                "actual_gross_profit": round2(actual_sales["gross"]),
                "actual_expense_amount": round2(actual_expense),
                "actual_profit_amount": round2(actual_profit),
                "actual_cost_rate": ratio(actual_sales["cost"], actual_sales["sales"]),
                "actual_expense_rate": ratio(actual_expense, actual_sales["sales"]),
                "actual_profit_rate": ratio(actual_profit, actual_sales["sales"]),
            }
        )
    if data_view == "comparison":
        budget_profit = budget_sales["sales"] - budget_sales["cost"] - budget_expense
        actual_profit = actual_sales["sales"] - actual_sales["cost"] - actual_expense
        values.update(
            {
                "quantity_diff": round2(actual_sales["quantity"] - budget_sales["quantity"]),
                "quantity_completion_rate": ratio(actual_sales["quantity"], budget_sales["quantity"]),
                "sales_diff": round2(actual_sales["sales"] - budget_sales["sales"]),
                "sales_completion_rate": ratio(actual_sales["sales"], budget_sales["sales"]),
                "cost_diff": round2(actual_sales["cost"] - budget_sales["cost"]),
                "cost_usage_rate": ratio(actual_sales["cost"], budget_sales["cost"]),
                "gross_profit_diff": round2(actual_sales["gross"] - budget_sales["gross"]),
                "expense_diff": round2(actual_expense - budget_expense),
                "expense_usage_rate": ratio(actual_expense, budget_expense),
                "profit_diff": round2(actual_profit - budget_profit),
                "profit_rate_diff": round2((ratio(actual_profit, actual_sales["sales"]) or 0) - (ratio(budget_profit, budget_sales["sales"]) or 0)),
            }
        )
    return values


def view_mode(ctx: DashboardContext) -> str:
    level = "product" if ctx.product_code or ctx.product_name else "shop" if ctx.shop_code or ctx.shop_name else "group" if ctx.group_code or ctx.group_name else "department"
    return f"{level}_{'month' if ctx.month else 'year'}"


def title_for_mode(mode: str, data_view: str) -> str:
    view_label = {"budget": "预算", "actual": "实际经营", "comparison": "预算实际"}.get(data_view, "预算实际")
    titles = {
        "department_year": f"部门全年{view_label}总览",
        "department_month": f"部门单月{view_label}复盘",
        "group_year": f"运营组全年{view_label}总览",
        "group_month": f"运营组单月{view_label}复盘",
        "shop_year": f"单店全年{view_label}总览",
        "shop_month": f"单店单月{view_label}复盘",
        "product_year": f"单品全年各店铺售卖分析",
        "product_month": f"单品单月各店铺售卖分析",
    }
    return titles.get(mode, f"{view_label}总览")


def breadcrumb(ctx: DashboardContext) -> list[str]:
    return [
        f"{ctx.year}年",
        f"第{ctx.budget_version}版",
        f"{ctx.month}月" if ctx.month else "全年",
        ctx.group_name or "全部运营组",
        ctx.shop_name or "全部店铺",
        ctx.product_name or ctx.product_code or "全部产品",
        {"budget": "预算", "actual": "实际", "comparison": "预算 vs 实际"}[ctx.data_view],
    ]


def group_budget_rows(rows, keys: tuple[str, ...]) -> dict[tuple, dict]:
    result = defaultdict(lambda: {"budget_quantity": 0.0, "budget_sales_amount": 0.0, "budget_cost_amount": 0.0, "budget_gross_profit": 0.0})
    for row in rows:
        key = tuple(getattr(row, field, None) for field in keys)
        item = result[key]
        item["budget_quantity"] += row.budget_quantity or 0
        item["budget_sales_amount"] += row.budget_sales_amount or 0
        item["budget_cost_amount"] += row.budget_cost_amount or 0
        item["budget_gross_profit"] += row.budget_gross_profit or 0
    return result


def group_budget_expenses(rows, keys: tuple[str, ...]) -> dict[tuple, float]:
    result = defaultdict(float)
    for row in rows:
        key = tuple(getattr(row, field, None) for field in keys)
        result[key] += row.budget_expense_amount or 0
    return result


def group_actual_expenses(rows, keys: tuple[str, ...]) -> dict[tuple, float]:
    result = defaultdict(float)
    for row in rows:
        key = tuple(getattr(row, field, None) for field in keys)
        result[key] += row.actual_expense_amount or 0
    return result


def group_actual_rows(rows, keys: tuple[str, ...]) -> dict[tuple, dict]:
    result = defaultdict(lambda: {"actual_quantity": 0.0, "actual_sales_amount": 0.0, "actual_cost_amount": 0.0, "actual_gross_profit": 0.0})
    for row in rows:
        key = tuple(getattr(row, field, None) for field in keys)
        item = result[key]
        item["actual_quantity"] += row.actual_quantity or 0
        item["actual_sales_amount"] += row.actual_sales_amount or 0
        item["actual_cost_amount"] += row.actual_cost_amount or 0
        item["actual_gross_profit"] += row.actual_gross_profit or 0
    return result


def merge_grouped(budget_grouped: dict, actual_grouped: dict, keys: tuple[str, ...], data_view: str) -> list[dict]:
    rows = []
    for key in sorted(set(budget_grouped) | set(actual_grouped)):
        row = {field: key[index] for index, field in enumerate(keys)}
        row.update({field: round2(value) for field, value in budget_grouped.get(key, {}).items()})
        row.update({field: round2(value) for field, value in actual_grouped.get(key, {}).items()})
        if data_view == "comparison":
            budget_sales = row.get("budget_sales_amount", 0) or 0
            actual_sales = row.get("actual_sales_amount", 0) or 0
            budget_profit = row.get("budget_profit_amount", row.get("budget_gross_profit", 0)) or 0
            actual_profit = row.get("actual_profit_amount", row.get("actual_gross_profit", 0)) or 0
            row["sales_diff"] = round2(actual_sales - budget_sales)
            row["sales_completion_rate"] = ratio(actual_sales, budget_sales)
            row["profit_diff"] = round2(actual_profit - budget_profit)
        rows.append(row)
    return rows


def merge_sales_and_expenses(budget_rows, actual_rows, budget_expense_rows, actual_expense_rows, keys: tuple[str, ...], data_view: str) -> list[dict]:
    budget_grouped = group_budget_rows(budget_rows, keys)
    actual_grouped = group_actual_rows(actual_rows, keys)
    budget_expenses = group_budget_expenses(budget_expense_rows, keys)
    actual_expenses = group_actual_expenses(actual_expense_rows, keys)
    for key, values in budget_grouped.items():
        expense = budget_expenses.get(key, 0.0)
        values["budget_expense_amount"] = expense
        values["budget_profit_amount"] = values["budget_sales_amount"] - values["budget_cost_amount"] - expense
    for key, values in actual_grouped.items():
        expense = actual_expenses.get(key, 0.0)
        values["actual_expense_amount"] = expense
        values["actual_profit_amount"] = values["actual_sales_amount"] - values["actual_cost_amount"] - expense
    return merge_grouped(budget_grouped, actual_grouped, keys, data_view)


def trend_sections(budget_rows, actual_rows, budget_expense_rows, actual_expense_rows, ctx: DashboardContext) -> list[dict]:
    if ctx.month:
        return []
    rows = merge_sales_and_expenses(budget_rows, actual_rows, budget_expense_rows, actual_expense_rows, ("month",), ctx.data_view)
    actual_months = {row.month for row in [*actual_rows, *actual_expense_rows] if row.month}
    if ctx.data_view == "comparison":
        for row in rows:
            if row.get("month") not in actual_months:
                row["actual_sales_pending_amount"] = 0
                row["actual_profit_pending_amount"] = 0
                row["actual_sales_amount"] = None
                row["actual_profit_amount"] = None
            else:
                row["actual_sales_pending_amount"] = None
                row["actual_profit_pending_amount"] = None
    sections = []
    if ctx.data_view == "budget":
        sections.append({"id": "budget_sales_trend", "title": "预算销售额趋势（万元）", "type": "line", "x_field": "month", "series": [{"name": "预算销售额", "field": "budget_sales_amount"}], "rows": rows})
        sections.append({"id": "budget_cost_trend", "title": "预算成本额趋势（万元）", "type": "line", "x_field": "month", "series": [{"name": "预算成本额", "field": "budget_cost_amount"}], "rows": rows})
        sections.append({"id": "budget_expense_trend", "title": "预算费用额趋势（万元）", "type": "line", "x_field": "month", "series": [{"name": "预算费用额", "field": "budget_expense_amount"}], "rows": rows})
        sections.append({"id": "budget_profit_trend", "title": "预算利润额趋势（万元）", "type": "line", "x_field": "month", "series": [{"name": "预算利润额", "field": "budget_profit_amount"}], "rows": rows})
    elif ctx.data_view == "actual":
        sections.append({"id": "actual_sales_trend", "title": "实际销售额趋势（万元）", "type": "line", "x_field": "month", "series": [{"name": "实际销售额", "field": "actual_sales_amount"}], "rows": rows})
        sections.append({"id": "actual_cost_trend", "title": "实际成本额趋势（万元）", "type": "line", "x_field": "month", "series": [{"name": "实际成本额", "field": "actual_cost_amount"}], "rows": rows})
        sections.append({"id": "actual_expense_trend", "title": "实际费用额趋势（万元）", "type": "line", "x_field": "month", "series": [{"name": "实际费用额", "field": "actual_expense_amount"}], "rows": rows})
        sections.append({"id": "actual_profit_trend", "title": "实际利润额趋势（万元）", "type": "line", "x_field": "month", "series": [{"name": "实际利润额", "field": "actual_profit_amount"}], "rows": rows})
    else:
        sections.append({"id": "sales_comparison_trend", "title": "销售额预算 vs 实际趋势（万元）", "type": "line", "x_field": "month", "series": [{"name": "预算销售额", "field": "budget_sales_amount"}, {"name": "实际销售额", "field": "actual_sales_amount"}, {"name": "实际销售额（未上传）", "field": "actual_sales_pending_amount", "dashed": True}], "rows": rows})
        sections.append({"id": "cost_comparison_trend", "title": "成本额预算 vs 实际趋势（万元）", "type": "line", "x_field": "month", "series": [{"name": "预算成本额", "field": "budget_cost_amount"}, {"name": "实际成本额", "field": "actual_cost_amount"}], "rows": rows})
        sections.append({"id": "expense_comparison_trend", "title": "费用额预算 vs 实际趋势（万元）", "type": "line", "x_field": "month", "series": [{"name": "预算费用额", "field": "budget_expense_amount"}, {"name": "实际费用额", "field": "actual_expense_amount"}], "rows": rows})
        sections.append({"id": "profit_comparison_trend", "title": "利润额预算 vs 实际趋势（万元）", "type": "line", "x_field": "month", "series": [{"name": "预算利润额", "field": "budget_profit_amount"}, {"name": "实际利润额", "field": "actual_profit_amount"}, {"name": "实际利润额（未上传）", "field": "actual_profit_pending_amount", "dashed": True}], "rows": rows})
    return sections


def ranking_dimension(mode: str) -> tuple[str, ...]:
    if mode.startswith("product"):
        return ("group_name", "shop_name", "product_name")
    if mode.startswith("shop"):
        return ("product_name",)
    if mode.startswith("group"):
        return ("shop_name",)
    return ("group_name",)


def label_from_row(row: dict, keys: tuple[str, ...]) -> str:
    for key in reversed(keys):
        if row.get(key):
            return str(row[key])
    return "未命名"


def sort_key_for_view(row: dict, data_view: str, mode: str) -> tuple[float, float]:
    if data_view == "budget":
        return (float(row.get("budget_sales_amount") or 0), 0.0)
    if data_view == "actual":
        return (float(row.get("actual_sales_amount") or 0), float(row.get("budget_sales_amount") or 0))
    return (float(row.get("actual_sales_amount") or 0), float(row.get("budget_sales_amount") or 0))


def ranking_sections(budget_rows, actual_rows, budget_expense_rows, actual_expense_rows, ctx: DashboardContext, mode: str) -> list[dict]:
    keys = ranking_dimension(mode)
    rows = merge_grouped(group_budget_rows(budget_rows, keys), group_actual_rows(actual_rows, keys), keys, ctx.data_view)
    for row in rows:
        row["name"] = label_from_row(row, keys)
    ranked = sorted(rows, key=lambda item: sort_key_for_view(item, ctx.data_view, mode), reverse=True)[: ctx.top_n]
    sections = [
        {
            "id": "sales_ranking",
            "title": "销售表现排名" if ctx.data_view == "comparison" else ("预算销售排名" if ctx.data_view == "budget" else "实际销售排名"),
            "type": "ranking_table",
            "rows": ranked,
        }
    ]
    if not mode.startswith("product") and ctx.data_view == "comparison":
        expense_rows = expense_overrun_rows(budget_expense_rows, actual_expense_rows, ctx.top_n)
        sections.append({"id": "expense_overrun", "title": "费用项目使用情况", "type": "expense_table", "rows": expense_rows})
    return sections


def expense_overrun_rows(budget_rows, actual_rows, top_n: int) -> list[dict]:
    budget = defaultdict(float)
    actual = defaultdict(float)
    budget_categories: dict[str, str] = {}
    actual_categories: dict[str, str] = {}
    for row in budget_rows:
        category, item = budget_expense_item_key(row)
        budget[item] += row.budget_expense_amount or 0
        if category and item not in budget_categories:
            budget_categories[item] = category
    for row in actual_rows:
        category, item = actual_expense_item_key(row)
        actual[item] += row.actual_expense_amount or 0
        if category and item not in actual_categories:
            actual_categories[item] = category
    rows = []
    for item in set(budget) | set(actual):
        category = budget_categories.get(item) or actual_categories.get(item) or ""
        budget_amount = budget.get(item, 0.0)
        actual_amount = actual.get(item, 0.0)
        diff = actual_amount - budget_amount
        rows.append({"expense_category": category, "expense_item": item, "budget_expense_amount": round2(budget_amount), "actual_expense_amount": round2(actual_amount), "expense_diff": round2(diff), "expense_usage_rate": ratio(actual_amount, budget_amount)})
    return sorted(rows, key=lambda item: float(item.get("actual_expense_amount") or 0), reverse=True)[:top_n]


def add_completion_rates(rows: list[dict], annual_budget_rows, same_period_budget_rows, actual_rows, keys: tuple[str, ...]) -> list[dict]:
    annual_budget = group_budget_rows(annual_budget_rows, keys)
    same_period_budget = group_budget_rows(same_period_budget_rows, keys)
    actual = group_actual_rows(actual_rows, keys)
    for row in rows:
        key = tuple(row.get(field) for field in keys)
        actual_sales = actual.get(key, {}).get("actual_sales_amount", row.get("actual_sales_amount", 0) or 0)
        annual_budget_sales = annual_budget.get(key, {}).get("budget_sales_amount", 0)
        same_period_budget_sales = same_period_budget.get(key, {}).get("budget_sales_amount", row.get("budget_sales_amount", 0) or 0)
        row["annual_completion_rate"] = ratio(actual_sales, annual_budget_sales)
        row["same_period_completion_rate"] = ratio(actual_sales, same_period_budget_sales)
    return rows


def expense_category_rows(budget_rows, actual_rows, data_view: str) -> list[dict]:
    budget = defaultdict(float)
    actual = defaultdict(float)
    budget_categories: dict[str, str] = {}
    actual_categories: dict[str, str] = {}
    for row in budget_rows:
        category, item = budget_expense_item_key(row)
        budget[item] += row.budget_expense_amount or 0
        if category and item not in budget_categories:
            budget_categories[item] = category
    for row in actual_rows:
        category, item = actual_expense_item_key(row)
        actual[item] += row.actual_expense_amount or 0
        if category and item not in actual_categories:
            actual_categories[item] = category
    rows = []
    for expense_item in sorted(set(budget) | set(actual)):
        category = budget_categories.get(expense_item) or actual_categories.get(expense_item) or ""
        item = {"expense_category": category, "expense_item": expense_item}
        if data_view in {"budget", "comparison"}:
            item["budget_expense_amount"] = round2(budget.get(expense_item, 0))
        if data_view in {"actual", "comparison"}:
            item["actual_expense_amount"] = round2(actual.get(expense_item, 0))
        if data_view == "comparison":
            item["expense_diff"] = round2(actual.get(expense_item, 0) - budget.get(expense_item, 0))
            item["expense_usage_rate"] = ratio(actual.get(expense_item, 0), budget.get(expense_item, 0))
        rows.append(item)
    return sorted(rows, key=lambda item: abs(float(item.get("expense_diff") or item.get("actual_expense_amount") or item.get("budget_expense_amount") or 0)), reverse=True)


def table_sections(
    budget_rows,
    actual_rows,
    budget_expense_rows,
    actual_expense_rows,
    annual_budget_rows,
    same_period_budget_rows,
    ctx: DashboardContext,
    mode: str,
) -> list[dict]:
    if mode.startswith("product"):
        keys = ("group_name", "shop_name", "product_name")
        title = "产品-店铺预算实际对比明细"
    elif mode.startswith("shop"):
        keys = ("product_name",)
        title = "店铺产品预算实际对比明细"
    elif mode.startswith("group"):
        keys = ("shop_name",)
        title = "运营组店铺预算实际对比明细"
    else:
        keys = ("group_name",)
        title = "预算实际对比明细"
    rows = merge_grouped(group_budget_rows(budget_rows, keys), group_actual_rows(actual_rows, keys), keys, ctx.data_view)
    rows = add_completion_rates(rows, annual_budget_rows, same_period_budget_rows, actual_rows, keys)
    rows = sorted(rows, key=lambda item: sort_key_for_view(item, ctx.data_view, mode), reverse=True)[:50]
    sections = [{"id": "comparison_detail", "title": title, "type": "detail_table", "rows": rows}]
    if not mode.startswith("product"):
        sections.append({"id": "expense_category_detail", "title": "费用预算实际按费用项展开", "type": "expense_category_table", "rows": expense_category_rows(budget_expense_rows, actual_expense_rows, ctx.data_view)})
    return sections


def metric_cards(values: dict, data_view: str) -> list[dict]:
    if data_view == "budget":
        return [
            {"id": "budget_sales", "label": "预算销售额", "value": values.get("budget_sales_amount"), "format": "amount"},
            {"id": "budget_cost", "label": "预算成本额", "value": values.get("budget_cost_amount"), "format": "amount"},
            {"id": "budget_expense", "label": "预算费用额", "value": values.get("budget_expense_amount"), "format": "amount"},
            {"id": "budget_profit", "label": "预算利润额", "value": values.get("budget_profit_amount"), "format": "amount"},
            {"id": "budget_cost_rate", "label": "预算成本率", "value": values.get("budget_cost_rate"), "format": "percent"},
            {"id": "budget_expense_rate", "label": "预算费用率", "value": values.get("budget_expense_rate"), "format": "percent"},
        ]
    if data_view == "actual":
        return [
            {"id": "actual_sales", "label": "实际销售额", "value": values.get("actual_sales_amount"), "format": "amount"},
            {"id": "actual_cost", "label": "实际成本额", "value": values.get("actual_cost_amount"), "format": "amount"},
            {"id": "actual_expense", "label": "实际费用额", "value": values.get("actual_expense_amount"), "format": "amount"},
            {"id": "actual_profit", "label": "实际利润额", "value": values.get("actual_profit_amount"), "format": "amount"},
            {"id": "actual_profit_rate", "label": "实际利润率", "value": values.get("actual_profit_rate"), "format": "percent"},
            {"id": "actual_expense_rate", "label": "实际费用率", "value": values.get("actual_expense_rate"), "format": "percent"},
        ]
    return [
        {"id": "sales", "label": "销售额", "value": values.get("actual_sales_amount"), "format": "amount", "sub_value": values.get("budget_sales_amount"), "sub_label": "预算", "diff": values.get("sales_diff"), "rate": values.get("sales_completion_rate")},
        {"id": "cost", "label": "成本额", "value": values.get("actual_cost_amount"), "format": "amount", "sub_value": values.get("budget_cost_amount"), "sub_label": "预算", "diff": values.get("cost_diff"), "rate": values.get("cost_usage_rate")},
        {"id": "expense", "label": "费用额", "value": values.get("actual_expense_amount"), "format": "amount", "sub_value": values.get("budget_expense_amount"), "sub_label": "预算", "diff": values.get("expense_diff"), "rate": values.get("expense_usage_rate")},
        {"id": "profit", "label": "利润额", "value": values.get("actual_profit_amount"), "format": "amount", "sub_value": values.get("budget_profit_amount"), "sub_label": "预算", "diff": values.get("profit_diff"), "rate": values.get("actual_profit_rate")},
        {"id": "annual_completion", "label": "全年达成率", "value": values.get("annual_sales_completion_rate"), "format": "percent"},
        {"id": "same_period_completion", "label": "同期达成率", "value": values.get("same_period_sales_completion_rate"), "format": "percent"},
        {"id": "profit_rate", "label": "利润率", "value": values.get("actual_profit_rate"), "format": "percent", "sub_value": values.get("budget_profit_rate"), "sub_label": "预算", "diff": values.get("profit_rate_diff")},
        {"id": "expense_rate", "label": "费用率", "value": values.get("actual_expense_rate"), "format": "percent", "sub_value": values.get("budget_expense_rate"), "sub_label": "预算", "diff": values.get("expense_usage_rate")},
    ]


def health_insights(values: dict, data_view: str) -> list[dict]:
    insights = []
    if data_view == "comparison":
        sales_rate = values.get("same_period_sales_completion_rate") or values.get("sales_completion_rate") or 0
        annual_rate = values.get("annual_sales_completion_rate") or 0
        expense_diff = values.get("expense_diff") or 0
        profit_diff = values.get("profit_diff") or 0
        cost_rate = values.get("cost_usage_rate") or 0
        insights.append({"level": "success" if sales_rate >= 1 else "warning", "message": f"同期销售达成率 {round2(sales_rate * 100)}%，{'达到预算节奏' if sales_rate >= 1 else '低于同期预算'}。"})
        insights.append({"level": "success" if annual_rate >= 1 else "info", "message": f"全年预算达成率 {round2(annual_rate * 100)}%，用于判断全年目标进度。"})
        insights.append({"level": "danger" if expense_diff > 0 else "success", "message": f"费用较预算{'超支' if expense_diff > 0 else '节省'} {amount_wan(abs(expense_diff))}。"})
        insights.append({"level": "danger" if profit_diff < 0 else "success", "message": f"利润较预算{'减少' if profit_diff < 0 else '增加'} {amount_wan(abs(profit_diff))}。"})
        insights.append({"level": "warning" if cost_rate > 1 else "success", "message": f"成本使用率 {round2(cost_rate * 100)}%，{'高于预算成本' if cost_rate > 1 else '未超过预算成本'}。"})
        return insights
    if data_view == "budget":
        budget_profit = values.get("budget_profit_amount") or 0
        budget_expense_rate = values.get("budget_expense_rate") or 0
        return [
            {"level": "danger" if budget_profit < 0 else "success", "message": f"预算利润额 {round2(budget_profit)} 元，{'当前预算为亏损结构' if budget_profit < 0 else '当前预算为盈利结构'}。"},
            {"level": "warning" if budget_expense_rate > 0.35 else "success", "message": f"预算费用率 {round2(budget_expense_rate * 100)}%，{'费用压力偏高' if budget_expense_rate > 0.35 else '费用率处于可控区间'}。"},
            {"level": "info", "message": "预算视图用于检查全年目标结构，请重点看利润趋势和费用大项。"},
        ]
    actual_profit = values.get("actual_profit_amount") or 0
    actual_expense_rate = values.get("actual_expense_rate") or 0
    return [
        {"level": "danger" if actual_profit < 0 else "success", "message": f"实际利润额 {round2(actual_profit)} 元，{'当前实际经营亏损' if actual_profit < 0 else '当前实际经营盈利'}。"},
        {"level": "warning" if actual_expense_rate > 0.35 else "success", "message": f"实际费用率 {round2(actual_expense_rate * 100)}%，{'费用占比偏高' if actual_expense_rate > 0.35 else '费用占比可控'}。"},
        {"level": "info", "message": "实际视图用于观察已发生经营结果，不包含预算差异字段。"},
    ]


def product_options(db: Session, ctx: DashboardContext) -> list[dict]:
    option_ctx = replace(ctx, product_code=None, product_name=None)
    budget_rows = apply_budget_sales_filters(
        db.query(SalesBudgetDetail.product_code, SalesBudgetDetail.product_name), option_ctx
    ).group_by(SalesBudgetDetail.product_code, SalesBudgetDetail.product_name).order_by(func.max(SalesBudgetDetail.id)).all()
    actual_rows = apply_actual_sales_filters(
        db.query(ActualSalesDetail.product_code, ActualSalesDetail.product_name), option_ctx
    ).group_by(ActualSalesDetail.product_code, ActualSalesDetail.product_name).order_by(func.min(ActualSalesDetail.id)).all()
    options = {}
    for row in budget_rows:
        name = row.product_name or row.product_code
        if name:
            options[name] = {"product_key": f"{row.product_code or ''}::{name}", "product_code": row.product_code, "product_name": name}
    for row in actual_rows:
        name = row.product_name or row.product_code
        if name and name not in options:
            options[name] = {"product_key": f"{row.product_code or ''}::{name}", "product_code": row.product_code, "product_name": name}
    return sorted(options.values(), key=lambda item: item["product_name"])[:1500]


def range_label(months: list[int]) -> str:
    if not months:
        return "暂无实际数据"
    if len(months) == 1:
        return f"{months[0]}月"
    if months == list(range(months[0], months[-1] + 1)):
        return f"{months[0]}-{months[-1]}月"
    return "、".join(f"{month}月" for month in months)


def actual_coverage(actual_rows, actual_expense_rows) -> dict:
    months = sorted({row.month for row in [*actual_rows, *actual_expense_rows] if row.month})
    group_names = sorted({row.group_name for row in [*actual_rows, *actual_expense_rows] if row.group_name})
    shop_names = sorted({row.shop_name for row in [*actual_rows, *actual_expense_rows] if row.shop_name})
    message = "暂无实际经营数据，预算 vs 实际视图只能展示预算目标。" if not months else (
        f"实际数据覆盖 {range_label(months)}，{len(group_names)} 个运营组、{len(shop_names)} 个店铺。"
    )
    return {
        "has_actual_data": bool(months),
        "months": months,
        "month_label": range_label(months),
        "group_count": len(group_names),
        "shop_count": len(shop_names),
        "groups": group_names[:8],
        "shops": shop_names[:8],
        "sales_row_count": len(actual_rows),
        "expense_row_count": len(actual_expense_rows),
        "message": message,
    }


def same_period_months(ctx: DashboardContext, actual_rows, actual_expense_rows) -> list[int]:
    if ctx.month:
        return [ctx.month]
    months = sorted({row.month for row in [*actual_rows, *actual_expense_rows] if row.month})
    return months or list(range(1, 13))


def rows_for_months(rows, months: list[int]):
    month_set = set(months)
    return [row for row in rows if row.month in month_set]


def dashboard_overview(db: Session, filters: dict, app_state=None) -> dict:
    ctx = resolve_names(filters, app_state)
    if ctx.group_name and not ctx.group_code:
        row = db.query(SalesBudgetDetail).filter(SalesBudgetDetail.year == ctx.year, SalesBudgetDetail.budget_version == ctx.budget_version, SalesBudgetDetail.group_name == ctx.group_name).first()
        if row:
            ctx.group_code = row.group_code
    if ctx.shop_name and not ctx.shop_code:
        row = db.query(SalesBudgetDetail).filter(SalesBudgetDetail.year == ctx.year, SalesBudgetDetail.budget_version == ctx.budget_version, SalesBudgetDetail.shop_name == ctx.shop_name).first()
        if row:
            ctx.shop_code = row.shop_code
            ctx.group_code = ctx.group_code or row.group_code
            ctx.group_name = ctx.group_name or row.group_name
    mode = view_mode(ctx)
    budget_rows = apply_budget_sales_filters(db.query(SalesBudgetDetail), ctx).all()
    actual_rows = apply_actual_sales_filters(db.query(ActualSalesDetail), ctx).all()
    product_scoped = bool(ctx.product_code or ctx.product_name)
    budget_expense_rows = [] if product_scoped else apply_budget_expense_filters(db.query(ExpenseBudgetDetail), ctx).all()
    actual_expense_rows = [] if product_scoped else apply_actual_expense_filters(db.query(ActualExpenseDetail), ctx).all()
    annual_budget_rows = budget_rows
    if ctx.month is not None:
        annual_budget_rows = apply_budget_sales_filters(db.query(SalesBudgetDetail), replace(ctx, month=None)).all()
    coverage = actual_coverage(actual_rows, actual_expense_rows)
    months = same_period_months(ctx, actual_rows, actual_expense_rows)
    same_period_budget_rows = rows_for_months(annual_budget_rows, months)
    comparison_budget_rows = same_period_budget_rows if ctx.data_view == "comparison" else budget_rows
    comparison_budget_expense_rows = rows_for_months(budget_expense_rows, months) if ctx.data_view == "comparison" else budget_expense_rows
    summary_values = build_summary_values(
        sales_totals(comparison_budget_rows, "budget"),
        sales_totals(actual_rows, "actual"),
        sum(row.budget_expense_amount or 0 for row in comparison_budget_expense_rows),
        sum(row.actual_expense_amount or 0 for row in actual_expense_rows),
        ctx.data_view,
    )
    if ctx.data_view == "comparison":
        actual_sales_total = sales_totals(actual_rows, "actual")["sales"]
        annual_budget_sales = sales_totals(annual_budget_rows, "budget")["sales"]
        same_period_budget_sales = sales_totals(same_period_budget_rows, "budget")["sales"]
        summary_values["annual_sales_completion_rate"] = ratio(actual_sales_total, annual_budget_sales)
        summary_values["same_period_sales_completion_rate"] = ratio(actual_sales_total, same_period_budget_sales)
        summary_values["same_period_budget_sales_amount"] = round2(same_period_budget_sales)
    ranking = ranking_sections(comparison_budget_rows, actual_rows, comparison_budget_expense_rows, actual_expense_rows, ctx, mode)
    return {
        "view_mode": mode,
        "data_view": ctx.data_view,
        "title": title_for_mode(mode, ctx.data_view),
        "breadcrumb": breadcrumb(ctx),
        "filters": {
            "year": ctx.year,
            "budget_version": ctx.budget_version,
            "month": ctx.month,
            "group_code": ctx.group_code,
            "group_name": ctx.group_name,
            "shop_code": ctx.shop_code,
            "shop_name": ctx.shop_name,
            "product_code": ctx.product_code,
            "product_name": ctx.product_name,
            "data_view": ctx.data_view,
            "top_n": ctx.top_n,
        },
        "summary_cards": summary_values,
        "metric_cards": metric_cards(summary_values, ctx.data_view),
        "trend_sections": trend_sections(budget_rows, actual_rows, budget_expense_rows, actual_expense_rows, ctx),
        "ranking_sections": ranking,
        "table_sections": table_sections(comparison_budget_rows, actual_rows, comparison_budget_expense_rows, actual_expense_rows, annual_budget_rows, same_period_budget_rows, ctx, mode),
        "health_insights": health_insights(summary_values, ctx.data_view),
        "actual_coverage": coverage,
        "filter_options": {"products": product_options(db, ctx)},
        "quick_actions": [{"id": "export_current_view", "label": "导出当前视角"}, {"id": "ai_analysis", "label": "AI分析"}],
        "ranking_data": ranking[0]["rows"] if ranking else [],
    }
