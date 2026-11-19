import csv
from dataclasses import asdict, is_dataclass
from datetime import datetime
from pathlib import Path

from fastapi import HTTPException, Request
from sqlalchemy.orm import Session

from backend.config import BASE_DIR, STANDARD_RELATIVE_PATH
from backend.database.models import (
    DepartmentBudgetSummary,
    ExpenseBudgetDetail,
    GroupBudgetSummary,
    SalesBudgetDetail,
    ShopBudgetSummary,
)


def ratio(numerator: float, denominator: float) -> float | None:
    return round(numerator / denominator, 6) if denominator else None


def get_standard_dir(app_state=None) -> Path:
    override = getattr(app_state, "standard_dir_override", None) if app_state else None
    standard_dir = Path(override) if override else BASE_DIR / STANDARD_RELATIVE_PATH
    standard_dir.mkdir(parents=True, exist_ok=True)
    return standard_dir


def clear_summary_tables(db: Session, budget_version: int | None = None) -> None:
    shop_query = db.query(ShopBudgetSummary)
    group_query = db.query(GroupBudgetSummary)
    department_query = db.query(DepartmentBudgetSummary)
    if budget_version is not None:
        shop_query = shop_query.filter(ShopBudgetSummary.budget_version == budget_version)
        group_query = group_query.filter(GroupBudgetSummary.budget_version == budget_version)
        department_query = department_query.filter(DepartmentBudgetSummary.budget_version == budget_version)
    shop_query.delete()
    group_query.delete()
    department_query.delete()


def expense_map(db: Session, keys: tuple[str, ...], budget_version: int | None = None) -> dict[tuple, float]:
    result = {}
    query = db.query(ExpenseBudgetDetail)
    if budget_version is not None:
        query = query.filter(ExpenseBudgetDetail.budget_version == budget_version)
    rows = query.all()
    for row in rows:
        key = tuple(getattr(row, field) for field in keys)
        result[key] = result.get(key, 0.0) + (row.budget_expense_amount or 0)
    return result


def summarize_sales(db: Session, keys: tuple[str, ...], budget_version: int | None = None) -> dict[tuple, dict]:
    result = {}
    query = db.query(SalesBudgetDetail)
    if budget_version is not None:
        query = query.filter(SalesBudgetDetail.budget_version == budget_version)
    for row in query.all():
        key = tuple(getattr(row, field) for field in keys)
        item = result.setdefault(
            key,
            {
                "sales_amount": 0.0,
                "cost_amount": 0.0,
                "gross_profit": 0.0,
            },
        )
        item["sales_amount"] += row.budget_sales_amount or 0
        item["cost_amount"] += row.budget_cost_amount or 0
        item["gross_profit"] += row.budget_gross_profit or 0
    return result


def build_summary_metrics(sales_amount: float, cost_amount: float, expense_amount: float) -> dict:
    gross_profit = sales_amount - cost_amount
    profit_amount = sales_amount - cost_amount - expense_amount
    return {
        "sales_amount": round(sales_amount, 2),
        "cost_amount": round(cost_amount, 2),
        "gross_profit": round(gross_profit, 2),
        "expense_amount": round(expense_amount, 2),
        "profit_amount": round(profit_amount, 2),
        "cost_rate": ratio(cost_amount, sales_amount),
        "expense_rate": ratio(expense_amount, sales_amount),
        "profit_rate": ratio(profit_amount, sales_amount),
    }


def normalize_budget_version(value: int | str | None) -> int | None:
    if value in ("", None):
        return None
    try:
        version = int(value)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="预算版本必须是正整数。") from None
    if version < 1:
        raise HTTPException(status_code=400, detail="预算版本必须从第 1 版开始。")
    return version


def has_imported_details(db: Session, budget_version: int | None = None) -> bool:
    sales_query = db.query(SalesBudgetDetail)
    expense_query = db.query(ExpenseBudgetDetail)
    if budget_version is not None:
        sales_query = sales_query.filter(SalesBudgetDetail.budget_version == budget_version)
        expense_query = expense_query.filter(ExpenseBudgetDetail.budget_version == budget_version)
    return sales_query.first() is not None or expense_query.first() is not None


def run_aggregate(db: Session, app_state=None, budget_version: int | str | None = None, allow_empty: bool = False) -> dict:
    normalized_version = normalize_budget_version(budget_version)
    if not has_imported_details(db, normalized_version):
        if not allow_empty:
            version_text = f"第 {normalized_version} 版" if normalized_version else "当前"
            raise HTTPException(status_code=400, detail=f"{version_text}暂无已入库预算数据，不能生成汇总表。")
        clear_summary_tables(db, normalized_version)
        db.commit()
        return {
            "status": "empty",
            "budget_version": normalized_version,
            "shop_rows": 0,
            "group_rows": 0,
            "department_rows": 0,
            "message": "已入库数据为空，已清空对应汇总结果。",
        }

    clear_summary_tables(db, normalized_version)

    shop_sales = summarize_sales(db, ("year", "month", "budget_version", "group_code", "shop_code"), normalized_version)
    shop_expenses = expense_map(db, ("year", "month", "budget_version", "group_code", "shop_code"), normalized_version)
    for (year, month, budget_version, group_code, shop_code), values in shop_sales.items():
        expense_amount = shop_expenses.get((year, month, budget_version, group_code, shop_code), 0.0)
        metrics = build_summary_metrics(values["sales_amount"], values["cost_amount"], expense_amount)
        db.add(ShopBudgetSummary(year=year, month=month, budget_version=budget_version, group_code=group_code, shop_code=shop_code, **metrics))

    group_sales = summarize_sales(db, ("year", "month", "budget_version", "group_code"), normalized_version)
    group_expenses = expense_map(db, ("year", "month", "budget_version", "group_code"), normalized_version)
    for (year, month, budget_version, group_code), values in group_sales.items():
        expense_amount = group_expenses.get((year, month, budget_version, group_code), 0.0)
        metrics = build_summary_metrics(values["sales_amount"], values["cost_amount"], expense_amount)
        db.add(GroupBudgetSummary(year=year, month=month, budget_version=budget_version, group_code=group_code, **metrics))

    department_sales = summarize_sales(db, ("year", "month", "budget_version"), normalized_version)
    department_expenses = expense_map(db, ("year", "month", "budget_version"), normalized_version)
    for (year, month, budget_version), values in department_sales.items():
        expense_amount = department_expenses.get((year, month, budget_version), 0.0)
        metrics = build_summary_metrics(values["sales_amount"], values["cost_amount"], expense_amount)
        db.add(DepartmentBudgetSummary(year=year, month=month, budget_version=budget_version, **metrics))

    db.commit()
    export_standard_csv(db, app_state, normalized_version)
    return {
        "status": "success",
        "budget_version": normalized_version,
        "shop_rows": db.query(ShopBudgetSummary).filter(ShopBudgetSummary.budget_version == normalized_version).count()
        if normalized_version
        else db.query(ShopBudgetSummary).count(),
        "group_rows": db.query(GroupBudgetSummary).filter(GroupBudgetSummary.budget_version == normalized_version).count()
        if normalized_version
        else db.query(GroupBudgetSummary).count(),
        "department_rows": db.query(DepartmentBudgetSummary).filter(DepartmentBudgetSummary.budget_version == normalized_version).count()
        if normalized_version
        else db.query(DepartmentBudgetSummary).count(),
        "message": f"第 {normalized_version} 版预算汇总已重新计算" if normalized_version else "预算汇总已重新计算",
    }


def model_to_dict(row) -> dict:
    return {column.name: getattr(row, column.name) for column in row.__table__.columns}


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8-sig")
        return
    with path.open("w", encoding="utf-8-sig", newline="") as file_obj:
        writer = csv.DictWriter(file_obj, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def export_standard_csv(db: Session, app_state=None, budget_version: int | None = None) -> list[str]:
    standard_dir = get_standard_dir(app_state)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    version_label = f"_第{budget_version}版" if budget_version else ""
    sales_query = db.query(SalesBudgetDetail)
    expense_query = db.query(ExpenseBudgetDetail)
    shop_query = db.query(ShopBudgetSummary)
    group_query = db.query(GroupBudgetSummary)
    department_query = db.query(DepartmentBudgetSummary)
    if budget_version is not None:
        sales_query = sales_query.filter(SalesBudgetDetail.budget_version == budget_version)
        expense_query = expense_query.filter(ExpenseBudgetDetail.budget_version == budget_version)
        shop_query = shop_query.filter(ShopBudgetSummary.budget_version == budget_version)
        group_query = group_query.filter(GroupBudgetSummary.budget_version == budget_version)
        department_query = department_query.filter(DepartmentBudgetSummary.budget_version == budget_version)
    exports = [
        (f"销售预算明细{version_label}_{timestamp}.csv", [model_to_dict(row) for row in sales_query.all()]),
        (f"费用预算明细{version_label}_{timestamp}.csv", [model_to_dict(row) for row in expense_query.all()]),
        (f"店铺预算汇总{version_label}_{timestamp}.csv", [model_to_dict(row) for row in shop_query.all()]),
        (f"运营组预算汇总{version_label}_{timestamp}.csv", [model_to_dict(row) for row in group_query.all()]),
        (f"部门预算汇总{version_label}_{timestamp}.csv", [model_to_dict(row) for row in department_query.all()]),
    ]
    paths = []
    for filename, rows in exports:
        path = standard_dir / filename
        write_csv(path, rows)
        paths.append(str(path))
    return paths


def sum_rows(rows) -> dict:
    totals = {"sales_amount": 0.0, "cost_amount": 0.0, "gross_profit": 0.0, "expense_amount": 0.0, "profit_amount": 0.0}
    for row in rows:
        for key in totals:
            totals[key] += getattr(row, key) or 0
    return {key: round(value, 2) for key, value in totals.items()}


def apply_detail_filters(query, model, filters: dict | None = None):
    if not filters:
        return query
    for field in ("year", "month", "group_code", "shop_code", "category", "product_name"):
        value = filters.get(field)
        if value in ("", None) or not hasattr(model, field):
            continue
        column = getattr(model, field)
        if field in {"year", "month"}:
            value = int(value)
        query = query.filter(column == value)
    return query


def apply_summary_filters(query, model, filters: dict | None = None):
    if not filters:
        return query
    for field in ("year", "month", "group_code", "shop_code"):
        value = filters.get(field)
        if value in ("", None) or not hasattr(model, field):
            continue
        column = getattr(model, field)
        if field in {"year", "month"}:
            value = int(value)
        query = query.filter(column == value)
    return query


def name_maps(sales_rows) -> tuple[dict[str, str], dict[tuple[str, str], str]]:
    group_names = {}
    shop_names = {}
    for row in sales_rows:
        if row.group_name:
            group_names[row.group_code] = row.group_name
        if row.shop_name:
            shop_names[(row.group_code, row.shop_code)] = row.shop_name
    return group_names, shop_names


def enrich_group_rows(rows: list[dict], group_names: dict[str, str]) -> list[dict]:
    for row in rows:
        row["group_name"] = group_names.get(row.get("group_code"), row.get("group_code"))
    return rows


def enrich_shop_rows(rows: list[dict], shop_names: dict[tuple[str, str], str], group_names: dict[str, str]) -> list[dict]:
    for row in rows:
        row["group_name"] = group_names.get(row.get("group_code"), row.get("group_code"))
        row["shop_name"] = shop_names.get((row.get("group_code"), row.get("shop_code")), row.get("shop_code"))
    return rows


def summarize_detail_rows(sales_rows, expense_rows) -> dict:
    sales_amount = sum(row.budget_sales_amount or 0 for row in sales_rows)
    cost_amount = sum(row.budget_cost_amount or 0 for row in sales_rows)
    expense_amount = sum(row.budget_expense_amount or 0 for row in expense_rows)
    return build_summary_metrics(sales_amount, cost_amount, expense_amount)


def group_detail_summary(sales_rows, expense_rows, keys: tuple[str, ...]) -> list[dict]:
    result = {}
    for row in sales_rows:
        key = tuple(getattr(row, field) for field in keys)
        item = result.setdefault(key, {"sales_amount": 0.0, "cost_amount": 0.0, "expense_amount": 0.0})
        item["sales_amount"] += row.budget_sales_amount or 0
        item["cost_amount"] += row.budget_cost_amount or 0
    for row in expense_rows:
        key_values = []
        skip = False
        for field in keys:
            if not hasattr(row, field):
                skip = True
                break
            key_values.append(getattr(row, field))
        if skip:
            continue
        item = result.setdefault(tuple(key_values), {"sales_amount": 0.0, "cost_amount": 0.0, "expense_amount": 0.0})
        item["expense_amount"] += row.budget_expense_amount or 0
    rows = []
    for key, values in result.items():
        row = {field: key[index] for index, field in enumerate(keys)}
        row.update(build_summary_metrics(values["sales_amount"], values["cost_amount"], values["expense_amount"]))
        rows.append(row)
    return rows


def aggregate_summary(db: Session, budget_version: int | None = None, filters: dict | None = None) -> dict:
    department_query = db.query(DepartmentBudgetSummary)
    group_query = db.query(GroupBudgetSummary)
    shop_query = db.query(ShopBudgetSummary)
    sales_query = db.query(SalesBudgetDetail)
    expense_query = db.query(ExpenseBudgetDetail)
    if budget_version is not None:
        department_query = department_query.filter(DepartmentBudgetSummary.budget_version == budget_version)
        group_query = group_query.filter(GroupBudgetSummary.budget_version == budget_version)
        shop_query = shop_query.filter(ShopBudgetSummary.budget_version == budget_version)
        sales_query = sales_query.filter(SalesBudgetDetail.budget_version == budget_version)
        expense_query = expense_query.filter(ExpenseBudgetDetail.budget_version == budget_version)
    department_query = apply_summary_filters(department_query, DepartmentBudgetSummary, filters)
    group_query = apply_summary_filters(group_query, GroupBudgetSummary, filters)
    shop_query = apply_summary_filters(shop_query, ShopBudgetSummary, filters)
    sales_query = apply_detail_filters(sales_query, SalesBudgetDetail, filters)
    expense_filters = dict(filters or {})
    if expense_filters.get("product_name") or expense_filters.get("category"):
        expense_filters["_skip_product_expenses"] = True
    expense_query = apply_detail_filters(expense_query, ExpenseBudgetDetail, expense_filters)
    department_rows = department_query.all()
    group_rows = group_query.all()
    shop_rows = shop_query.all()
    sales_rows = sales_query.all()
    expense_rows = [] if (filters or {}).get("product_name") or (filters or {}).get("category") else expense_query.all()
    group_names, shop_names = name_maps(sales_rows)
    product_filtered = bool((filters or {}).get("product_name") or (filters or {}).get("category"))
    department_total = summarize_detail_rows(sales_rows, expense_rows) if filters else sum_rows(department_rows)
    monthly_trend = (
        group_detail_summary(sales_rows, expense_rows, ("year", "month", "budget_version"))
        if filters
        else [model_to_dict(row) for row in sorted(department_rows, key=lambda item: (item.year, item.month))]
    )
    group_summary_rows = (
        group_detail_summary(sales_rows, expense_rows, ("year", "month", "budget_version", "group_code"))
        if filters or product_filtered
        else [model_to_dict(row) for row in group_rows]
    )
    shop_summary_rows = (
        group_detail_summary(sales_rows, expense_rows, ("year", "month", "budget_version", "group_code", "shop_code"))
        if filters or product_filtered
        else [model_to_dict(row) for row in shop_rows]
    )
    return {
        "budget_version": budget_version,
        "department_total": department_total,
        "monthly_trend": sorted(monthly_trend, key=lambda item: (item.get("year") or 0, item.get("month") or 0)),
        "group_summary": enrich_group_rows(group_summary_rows, group_names),
        "shop_summary": enrich_shop_rows(shop_summary_rows, shop_names, group_names),
        "product_summary": product_summary(sales_rows, "product_name"),
        "category_summary": product_summary(sales_rows, "category"),
        "expense_summary": expense_summary(expense_rows),
    }


def product_summary(rows, field: str) -> list[dict]:
    result = {}
    for row in rows:
        key = getattr(row, field) or "未分类"
        item = result.setdefault(key, {"key": key, field: key, "quantity": 0.0, "sales_amount": 0.0, "cost_amount": 0.0, "gross_profit": 0.0})
        item["quantity"] += row.budget_quantity or 0
        item["sales_amount"] += row.budget_sales_amount or 0
        item["cost_amount"] += row.budget_cost_amount or 0
        item["gross_profit"] += row.budget_gross_profit or 0
    return [{key: round(value, 2) if isinstance(value, float) else value for key, value in item.items()} for item in result.values()]


def expense_summary(rows) -> dict:
    by_category = {}
    by_item = {}
    by_month = {}
    for row in rows:
        by_category[row.expense_category] = by_category.get(row.expense_category, 0) + row.budget_expense_amount
        by_item[row.expense_item] = by_item.get(row.expense_item, 0) + row.budget_expense_amount
        by_month[row.month] = by_month.get(row.month, 0) + row.budget_expense_amount
    return {
        "by_category": [{"key": key, "amount": round(value, 2)} for key, value in by_category.items()],
        "by_item": [{"key": key, "amount": round(value, 2)} for key, value in by_item.items()],
        "by_month": [{"month": key, "amount": round(value, 2)} for key, value in sorted(by_month.items())],
    }


def dashboard_data(db: Session, filters: dict) -> dict:
    budget_version = filters.get("budget_version")
    if budget_version in ("", None):
        budget_version = None
    else:
        budget_version = int(budget_version)
    summary = aggregate_summary(db, budget_version, filters)
    return {
        "filters": filters,
        "summary": summary["department_total"],
        "data": summary,
    }
