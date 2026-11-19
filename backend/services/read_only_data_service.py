from __future__ import annotations

from typing import Any, Literal

from sqlalchemy.orm import Query, Session

from backend.database.models import ActualExpenseDetail, ActualSalesDetail, ExpenseBudgetDetail, SalesBudgetDetail
from backend.services.comparison_service import (
    apply_actual_expense_filters,
    apply_actual_sales_filters,
    apply_budget_expense_filters,
    apply_budget_sales_filters,
    dashboard_overview,
    resolve_names,
)


ReadOnlyDataset = Literal["budget_sales", "budget_expenses", "actual_sales", "actual_expenses"]
MAX_PAGE_SIZE = 200


DATASET_CATALOG = {
    "budget_sales": {
        "title": "预算销售明细",
        "description": "按年度、预算版本、月份、运营组、店铺和产品读取预算销量、销售额、成本额和毛利额。",
    },
    "budget_expenses": {
        "title": "预算费用明细",
        "description": "按年度、预算版本、月份、运营组和店铺读取预算费用大项、小项和金额。",
    },
    "actual_sales": {
        "title": "实际销售明细",
        "description": "按年度、月份、运营组、店铺和产品读取实际销量、销售额、成本额和毛利额。",
    },
    "actual_expenses": {
        "title": "实际费用明细",
        "description": "按年度、月份、运营组和店铺读取实际费用大项、小项和金额。",
    },
}


def read_only_catalog() -> dict[str, Any]:
    return {
        "mode": "read_only",
        "datasets": DATASET_CATALOG,
        "summary": "经营汇总支持预算、实际、预算 vs 实际三种视图。",
        "limits": {"default_page_size": 50, "max_page_size": MAX_PAGE_SIZE},
        "security": "不提供新增、修改、删除、上传、入库、汇总执行、导出或数据库文件访问能力。",
    }


def _page_values(page: int, page_size: int) -> tuple[int, int]:
    return max(1, int(page)), max(1, min(int(page_size), MAX_PAGE_SIZE))


def _serialize_budget_sales(row: SalesBudgetDetail) -> dict[str, Any]:
    return {
        "year": row.year,
        "budget_version": row.budget_version,
        "month": row.month,
        "group_code": row.group_code,
        "group_name": row.group_name,
        "shop_code": row.shop_code,
        "shop_name": row.shop_name,
        "product_code": row.product_code,
        "product_name": row.product_name,
        "category": row.category,
        "budget_quantity": row.budget_quantity,
        "average_price": row.average_price,
        "budget_sales_amount": row.budget_sales_amount,
        "cost_price": row.cost_price,
        "budget_cost_amount": row.budget_cost_amount,
        "budget_gross_profit": row.budget_gross_profit,
    }


def _serialize_budget_expense(row: ExpenseBudgetDetail) -> dict[str, Any]:
    return {
        "year": row.year,
        "budget_version": row.budget_version,
        "month": row.month,
        "group_code": row.group_code,
        "shop_code": row.shop_code,
        "expense_category": row.expense_category,
        "expense_item": row.expense_item,
        "budget_expense_amount": row.budget_expense_amount,
    }


def _serialize_actual_sales(row: ActualSalesDetail) -> dict[str, Any]:
    return {
        "year": row.year,
        "month": row.month,
        "group_name": row.group_name,
        "shop_name": row.shop_name,
        "product_code": row.product_code,
        "product_name": row.product_name,
        "category": row.category,
        "actual_quantity": row.actual_quantity,
        "actual_sales_amount": row.actual_sales_amount,
        "actual_cost_amount": row.actual_cost_amount,
        "actual_gross_profit": row.actual_gross_profit,
        "actual_sales_unit_price": row.actual_sales_unit_price,
        "actual_cost_unit_price": row.actual_cost_unit_price,
    }


def _serialize_actual_expense(row: ActualExpenseDetail) -> dict[str, Any]:
    return {
        "year": row.year,
        "month": row.month,
        "group_name": row.group_name,
        "shop_name": row.shop_name,
        "expense_category": row.expense_category,
        "expense_item": row.expense_item,
        "actual_expense_amount": row.actual_expense_amount,
    }


def _query_for_dataset(db: Session, dataset: ReadOnlyDataset, filters: dict[str, Any], app_state=None) -> tuple[Query, Any, Any]:
    context = resolve_names(filters, app_state)
    if dataset == "budget_sales":
        return apply_budget_sales_filters(db.query(SalesBudgetDetail), context), SalesBudgetDetail, _serialize_budget_sales
    if dataset == "budget_expenses":
        return apply_budget_expense_filters(db.query(ExpenseBudgetDetail), context), ExpenseBudgetDetail, _serialize_budget_expense
    if dataset == "actual_sales":
        return apply_actual_sales_filters(db.query(ActualSalesDetail), context), ActualSalesDetail, _serialize_actual_sales
    if dataset == "actual_expenses":
        return apply_actual_expense_filters(db.query(ActualExpenseDetail), context), ActualExpenseDetail, _serialize_actual_expense
    raise ValueError(f"未知只读数据集：{dataset}")


def query_read_only_records(
    db: Session,
    dataset: ReadOnlyDataset,
    filters: dict[str, Any],
    *,
    page: int = 1,
    page_size: int = 50,
    app_state=None,
) -> dict[str, Any]:
    normalized_page, normalized_size = _page_values(page, page_size)
    query, model, serializer = _query_for_dataset(db, dataset, filters, app_state)
    total = query.order_by(None).count()
    rows = (
        query.order_by(model.year.asc(), model.month.asc(), model.id.asc())
        .offset((normalized_page - 1) * normalized_size)
        .limit(normalized_size)
        .all()
    )
    return {
        "mode": "read_only",
        "dataset": dataset,
        "title": DATASET_CATALOG[dataset]["title"],
        "filters": {key: value for key, value in filters.items() if value not in (None, "")},
        "page": normalized_page,
        "page_size": normalized_size,
        "total": total,
        "has_more": normalized_page * normalized_size < total,
        "items": [serializer(row) for row in rows],
    }


def query_read_only_summary(db: Session, filters: dict[str, Any], app_state=None) -> dict[str, Any]:
    overview = dashboard_overview(db, filters, app_state)
    return {
        "mode": "read_only",
        "view_mode": overview["view_mode"],
        "data_view": overview["data_view"],
        "title": overview["title"],
        "breadcrumb": overview["breadcrumb"],
        "filters": overview["filters"],
        "summary": overview["summary_cards"],
        "actual_coverage": overview["actual_coverage"],
        "trends": overview["trend_sections"],
        "rankings": overview["ranking_sections"],
        "health_insights": overview["health_insights"],
    }
