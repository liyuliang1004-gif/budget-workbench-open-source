from __future__ import annotations

import re
from io import BytesIO
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from sqlalchemy.orm import Session

from backend.config import BASE_DIR, PLANNING_REPORT_RELATIVE_PATH
from backend.database.models import ActualExpenseDetail, ActualSalesDetail, BudgetPrice, ExpenseBudgetDetail, SalesBudgetDetail
from backend.services.metadata_service import list_groups_shops


MONTHS = list(range(1, 13))
PRICE_SOURCES = {"actual", "budget", "uploaded"}


@dataclass
class ProductPlanRow:
    month: int
    group_name: str
    shop_name: str
    product_code: str
    product_name: str
    category: str
    reference_sales_amount: float
    reference_quantity: float
    reference_cost_amount: float
    product_share: float
    sales_price: float
    cost_price: float


@dataclass
class ExpensePlanRow:
    month: int
    expense_category: str
    expense_item: str
    reference_expense_amount: float
    reference_month_sales_amount: float
    expense_rate: float


def get_planning_report_dir(app_state=None) -> Path:
    override = getattr(app_state, "planning_report_dir_override", None) if app_state is not None else None
    output_dir = Path(override) if override else BASE_DIR / PLANNING_REPORT_RELATIVE_PATH
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def list_planning_options(db: Session, reference_year: int | None = None, app_state=None) -> dict[str, Any]:
    year_filter = reference_year or datetime.now().year
    actual_rows = db.query(ActualSalesDetail).filter(ActualSalesDetail.year == year_filter).all()
    budget_rows = db.query(SalesBudgetDetail).filter(SalesBudgetDetail.year == year_filter).all()
    groups: dict[str, dict[str, str]] = {}
    shops: dict[str, dict[str, str]] = {}

    registry = list_groups_shops(app_state)
    for group in registry.get("operation_groups", []):
        group_name = str(group.get("group_name") or "").strip()
        group_code = str(group.get("group_code") or "").strip()
        if group_name:
            groups[group_name] = {"group_code": group_code, "group_name": group_name}
        for shop in group.get("shops", []):
            shop_name = str(shop.get("shop_name") or "").strip()
            shop_code = str(shop.get("shop_code") or "").strip()
            if shop_name:
                shops[shop_name] = {"shop_code": shop_code, "shop_name": shop_name, "group_name": group_name}

    for row in actual_rows:
        if row.group_name:
            groups[row.group_name] = {"group_code": "", "group_name": row.group_name}
        if row.shop_name:
            shops[row.shop_name] = {"shop_code": "", "shop_name": row.shop_name, "group_name": row.group_name or ""}

    for row in budget_rows:
        if row.group_name or row.group_code:
            group_name = row.group_name or row.group_code
            groups[group_name] = {"group_code": row.group_code or "", "group_name": group_name}
        if row.shop_name or row.shop_code:
            shop_name = row.shop_name or row.shop_code
            shops[shop_name] = {
                "shop_code": row.shop_code or "",
                "shop_name": shop_name,
                "group_name": row.group_name or row.group_code or "",
            }

    return {
        "reference_year": year_filter,
        "groups": sorted(groups.values(), key=lambda item: item["group_name"]),
        "shops": sorted(shops.values(), key=lambda item: (item["group_name"], item["shop_name"])),
    }


def export_next_year_budget_workbooks(db: Session, payload: dict[str, Any], app_state=None) -> list[Path]:
    context = build_planning_context(db, payload)
    output_dir = get_planning_report_dir(app_state)
    file_name = safe_file_name(
        f"{context['target_year']}年预算编制_{context['shop_name']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    )
    output_path = output_dir / file_name
    workbook = build_planning_workbook(context)
    workbook.save(output_path)
    return [output_path]


def import_product_price_table(db: Session, year: int, file_bytes: bytes, price_kind: str) -> dict[str, Any]:
    if price_kind not in {"sales", "cost"}:
        raise ValueError("价格表类型只能是 sales 或 cost。")
    check = check_product_price_table(file_bytes, price_kind)
    if check["error_count"]:
        messages = [str(issue["message"]) for issue in check["issues"] if issue["severity"] == "error"]
        raise ValueError("；".join(messages) or "价格表检查未通过。")
    workbook = load_workbook(BytesIO(file_bytes), data_only=True)
    sheet = workbook.active
    rows = list(sheet.iter_rows(values_only=True))
    if not rows:
        raise ValueError("价格表为空。")

    header_index = find_price_header_index(rows, price_kind)
    headers = [normalize_header(value) for value in rows[header_index]]
    product_code_index = find_first_index(headers, ["产品编码", "产品代码", "产品长代码", "编码", "sku", "SKU"])
    product_name_index = find_first_index(headers, ["产品名称", "商品名称", "品名", "名称"])
    value_index = find_first_index(
        headers,
        ["销售价", "销售价格", "预算销售价", "建议销售价", "单价", "售价"] if price_kind == "sales" else ["成本价", "成本价格", "产品成本", "单位成本", "店铺成本价", "成本"],
    )
    if value_index is None:
        raise ValueError("未识别到销售价列。" if price_kind == "sales" else "未识别到成本价列。")
    if product_code_index is None and product_name_index is None:
        raise ValueError("价格表必须包含产品编码或产品名称。")

    imported_count = 0
    for raw_row in rows[header_index + 1 :]:
        product_code = normalize_text(raw_row[product_code_index]) if product_code_index is not None and product_code_index < len(raw_row) else None
        product_name = normalize_text(raw_row[product_name_index]) if product_name_index is not None and product_name_index < len(raw_row) else None
        if not product_code and product_name:
            product_code = f"NAME::{product_name}"
        price_value = parse_float(raw_row[value_index] if value_index < len(raw_row) else None)
        if not product_code or price_value is None:
            continue
        existing = db.query(BudgetPrice).filter(BudgetPrice.year == year, BudgetPrice.product_code == product_code).one_or_none()
        if existing is None:
            existing = BudgetPrice(year=year, product_code=product_code)
            db.add(existing)
        if price_kind == "sales":
            existing.average_price = price_value
        else:
            existing.cost_price = price_value
        imported_count += 1
    db.commit()
    return {
        "success": True,
        "year": year,
        "price_type": "销售价格表" if price_kind == "sales" else "产品成本表",
        "imported_count": imported_count,
    }


def build_price_check_issue(
    price_kind: str,
    message: str,
    severity: str = "error",
    row_number: int | None = None,
    column_name: str | None = None,
    suggestion: str | None = None,
) -> dict[str, Any]:
    return {
        "severity": severity,
        "check_type": "销售价格表检查" if price_kind == "sales" else "产品成本表检查",
        "message": message,
        "sheet_name": "Sheet1",
        "row_number": row_number,
        "column_name": column_name,
        "suggestion": suggestion or "请按系统价格/成本表模板整理后重新上传。",
    }


def price_value_candidates(price_kind: str) -> list[str]:
    return (
        ["销售价", "销售价格", "预算销售价", "建议销售价", "单价", "售价"]
        if price_kind == "sales"
        else ["成本价", "成本价格", "产品成本", "单位成本", "店铺成本价", "成本"]
    )


def check_product_price_table(file_bytes: bytes, price_kind: str) -> dict[str, Any]:
    if price_kind not in {"sales", "cost"}:
        raise ValueError("价格表类型只能是 sales 或 cost。")
    price_type = "销售价格表" if price_kind == "sales" else "产品成本表"
    issues: list[dict[str, Any]] = []
    try:
        workbook = load_workbook(BytesIO(file_bytes), data_only=True, read_only=True)
    except Exception:
        issues.append(build_price_check_issue(price_kind, f"{price_type}不是有效的 Excel 文件。"))
        return build_price_check_response(price_kind, 0, 0, issues)

    try:
        sheet = workbook.active
        rows = list(sheet.iter_rows(values_only=True))
    finally:
        workbook.close()

    if not rows:
        issues.append(build_price_check_issue(price_kind, f"{price_type}为空。"))
        return build_price_check_response(price_kind, 0, 0, issues)

    header_index = None
    selected_headers: list[str] = []
    product_code_index = None
    product_name_index = None
    value_index = None
    for index, row in enumerate(rows[:10]):
        headers = [normalize_header(value) for value in row]
        current_code_index = find_first_index(headers, ["产品编码", "产品代码", "产品长代码", "编码", "sku", "SKU"])
        current_name_index = find_first_index(headers, ["产品名称", "商品名称", "品名", "名称"])
        current_value_index = find_first_index(headers, price_value_candidates(price_kind))
        has_product_column = current_code_index is not None or current_name_index is not None
        has_value_column = current_value_index is not None
        if has_product_column:
            header_index = index
            selected_headers = headers
            product_code_index = current_code_index
            product_name_index = current_name_index
            value_index = current_value_index
            if has_value_column:
                break
        elif header_index is None and has_value_column:
            header_index = index
            selected_headers = headers
            value_index = current_value_index

    if header_index is None:
        issues.append(build_price_check_issue(price_kind, f"未识别到{price_type}表头。", suggestion="表头需包含产品编码或产品名称，以及销售价/成本价列。"))
        return build_price_check_response(price_kind, 0, 0, issues)

    if product_code_index is None and product_name_index is None:
        issues.append(build_price_check_issue(price_kind, "价格表必须包含产品编码或产品名称。", row_number=header_index + 1, column_name="产品编码/产品名称"))
    if value_index is None:
        label = "销售价列" if price_kind == "sales" else "成本价列"
        issues.append(build_price_check_issue(price_kind, f"未识别到{label}。", row_number=header_index + 1, column_name=label))
    if any(issue["severity"] == "error" for issue in issues):
        return build_price_check_response(price_kind, 0, 0, issues)

    row_count = 0
    valid_count = 0
    for excel_row_number, raw_row in enumerate(rows[header_index + 1 :], start=header_index + 2):
        if all(value in ("", None) for value in raw_row):
            continue
        row_count += 1
        product_code = normalize_text(raw_row[product_code_index]) if product_code_index is not None and product_code_index < len(raw_row) else None
        product_name = normalize_text(raw_row[product_name_index]) if product_name_index is not None and product_name_index < len(raw_row) else None
        price_value = parse_float(raw_row[value_index] if value_index is not None and value_index < len(raw_row) else None)
        if not product_code and not product_name:
            issues.append(build_price_check_issue(price_kind, "产品编码和产品名称都为空，该行不会导入。", "warning", excel_row_number, "产品编码/产品名称"))
            continue
        if price_value is None:
            issues.append(build_price_check_issue(price_kind, "价格不是有效数字，该行不会导入。", "warning", excel_row_number, selected_headers[value_index] if value_index is not None and value_index < len(selected_headers) else "价格"))
            continue
        valid_count += 1

    if row_count == 0:
        issues.append(build_price_check_issue(price_kind, f"{price_type}没有可读取的数据行。", "warning", header_index + 2))
    if valid_count == 0 and row_count > 0:
        issues.append(build_price_check_issue(price_kind, f"{price_type}没有可导入的有效产品价格。"))
    return build_price_check_response(price_kind, row_count, valid_count, issues)


def build_price_check_response(price_kind: str, row_count: int, valid_count: int, issues: list[dict[str, Any]]) -> dict[str, Any]:
    error_count = len([issue for issue in issues if issue["severity"] == "error"])
    warning_count = len([issue for issue in issues if issue["severity"] == "warning"])
    return {
        "status": "failed" if error_count else "checked",
        "price_type": "销售价格表" if price_kind == "sales" else "产品成本表",
        "row_count": row_count,
        "valid_count": valid_count,
        "error_count": error_count,
        "warning_count": warning_count,
        "issues": issues,
    }


def build_planning_context(db: Session, payload: dict[str, Any]) -> dict[str, Any]:
    reference_year = int(payload.get("reference_year") or datetime.now().year)
    target_year = int(payload.get("target_year") or reference_year + 1)
    group_name = normalize_text(payload.get("group_name"))
    shop_name = normalize_text(payload.get("shop_name"))
    growth_rate = parse_rate(payload.get("target_growth_rate"), 0)
    sales_price_adjustment_rate = parse_rate(payload.get("sales_price_adjustment_rate"), 0)
    cost_price_adjustment_rate = parse_rate(payload.get("cost_price_adjustment_rate"), 0)
    sales_price_source = normalize_price_source(payload.get("sales_price_source"))
    cost_price_source = normalize_price_source(payload.get("cost_price_source"))
    reference_spring_month = int(payload.get("reference_spring_month") or 2)
    target_spring_month = int(payload.get("target_spring_month") or reference_spring_month)

    budget_version = int(payload.get("budget_version") or 1)
    actual_sales = query_actual_sales(db, reference_year, group_name, shop_name)
    if actual_sales:
        source_type = "actual"
        product_rows, monthly_sales = build_product_rows_from_actual(
            actual_sales,
            sales_price_adjustment_rate,
            cost_price_adjustment_rate,
        )
        expense_rows = build_expense_rows_from_actual(db, reference_year, group_name, shop_name, monthly_sales)
    else:
        source_type = "budget"
        product_rows, monthly_sales = build_product_rows_from_budget(
            db,
            reference_year,
            group_name,
            shop_name,
            sales_price_adjustment_rate,
            cost_price_adjustment_rate,
            budget_version,
        )
        expense_rows = build_expense_rows_from_budget(db, reference_year, group_name, shop_name, monthly_sales, budget_version)

    if not product_rows:
        raise ValueError("没有找到可用于编制明年预算的参考销售数据。请先导入今年实际销售，或确保已有预算数据。")
    apply_selected_price_sources(
        db,
        reference_year,
        target_year,
        budget_version,
        product_rows,
        sales_price_source,
        cost_price_source,
        group_name,
        shop_name,
    )

    resolved_group_name = group_name or product_rows[0].group_name
    resolved_shop_name = shop_name or product_rows[0].shop_name
    reference_total_sales = sum(monthly_sales.values())
    target_sales_amount = payload.get("target_sales_amount")
    if target_sales_amount is None or target_sales_amount == "":
        target_sales_amount = reference_total_sales * (1 + growth_rate)
    else:
        target_sales_amount = float(target_sales_amount)

    month_weights = build_month_weights(monthly_sales)
    month_weights = shift_spring_month_weight(month_weights, reference_spring_month, target_spring_month)
    month_targets = {month: float(target_sales_amount) * month_weights.get(month, 0) for month in MONTHS}

    return {
        "source_type": source_type,
        "reference_year": reference_year,
        "target_year": target_year,
        "group_name": resolved_group_name,
        "shop_name": resolved_shop_name,
        "reference_total_sales": reference_total_sales,
        "target_sales_amount": float(target_sales_amount),
        "growth_rate": growth_rate,
        "sales_price_adjustment_rate": sales_price_adjustment_rate,
        "cost_price_adjustment_rate": cost_price_adjustment_rate,
        "sales_price_source": sales_price_source,
        "cost_price_source": cost_price_source,
        "reference_spring_month": reference_spring_month,
        "target_spring_month": target_spring_month,
        "monthly_sales": monthly_sales,
        "month_weights": month_weights,
        "month_targets": month_targets,
        "product_rows": product_rows,
        "expense_rows": expense_rows,
    }


def normalize_price_source(value: Any) -> str:
    source = normalize_text(value) or "actual"
    if source == "reference":
        source = "actual"
    if source not in PRICE_SOURCES:
        raise ValueError("销售价来源和成本价来源只能选择：参考今年实际、参考今年预算、使用导入价。")
    return source


def apply_selected_price_sources(
    db: Session,
    reference_year: int,
    target_year: int,
    budget_version: int,
    product_rows: list[ProductPlanRow],
    sales_price_source: str,
    cost_price_source: str,
    group_name: str | None,
    shop_name: str | None,
) -> None:
    if sales_price_source == "budget" or cost_price_source == "budget":
        apply_reference_budget_prices(
            db,
            reference_year,
            budget_version,
            product_rows,
            sales_price_source == "budget",
            cost_price_source == "budget",
            group_name,
            shop_name,
        )
    if sales_price_source == "uploaded" or cost_price_source == "uploaded":
        apply_uploaded_budget_prices(db, target_year, product_rows, sales_price_source == "uploaded", cost_price_source == "uploaded")


def apply_reference_budget_prices(
    db: Session,
    reference_year: int,
    budget_version: int,
    product_rows: list[ProductPlanRow],
    use_sales_price: bool,
    use_cost_price: bool,
    group_name: str | None,
    shop_name: str | None,
) -> None:
    query = db.query(SalesBudgetDetail).filter(
        SalesBudgetDetail.year == reference_year,
        SalesBudgetDetail.budget_version == budget_version,
    )
    if group_name:
        query = query.filter(SalesBudgetDetail.group_name == group_name)
    if shop_name:
        query = query.filter(SalesBudgetDetail.shop_name == shop_name)
    prices_by_month_code: dict[tuple[int, str], SalesBudgetDetail] = {}
    prices_by_code: dict[str, SalesBudgetDetail] = {}
    for price in query.all():
        code = price.product_code or (f"NAME::{price.product_name}" if price.product_name else "")
        if not code:
            continue
        prices_by_month_code[(price.month, code)] = price
        prices_by_code.setdefault(code, price)
        if price.product_name:
            prices_by_month_code[(price.month, f"NAME::{price.product_name}")] = price
            prices_by_code.setdefault(f"NAME::{price.product_name}", price)
    for row in product_rows:
        price = prices_by_month_code.get((row.month, row.product_code)) or prices_by_code.get(row.product_code)
        if price is None and row.product_name:
            price = prices_by_month_code.get((row.month, f"NAME::{row.product_name}")) or prices_by_code.get(f"NAME::{row.product_name}")
        if price is None:
            continue
        if use_sales_price and price.average_price is not None:
            row.sales_price = float(price.average_price)
        if use_cost_price and price.cost_price is not None:
            row.cost_price = float(price.cost_price)


def apply_uploaded_budget_prices(
    db: Session,
    target_year: int,
    product_rows: list[ProductPlanRow],
    use_sales_price: bool,
    use_cost_price: bool,
) -> None:
    price_rows = db.query(BudgetPrice).filter(BudgetPrice.year == target_year).all()
    prices_by_code = {row.product_code: row for row in price_rows}
    unique_products: dict[str, ProductPlanRow] = {}
    for row in product_rows:
        unique_products.setdefault(row.product_code, row)
        if row.product_name:
            unique_products.setdefault(f"NAME::{row.product_name}", row)

    errors: list[str] = []
    if use_sales_price:
        missing_sales = []
        for key, item in unique_products.items():
            if key != item.product_code:
                continue
            price = prices_by_code.get(item.product_code) or prices_by_code.get(f"NAME::{item.product_name}")
            if price is None or price.average_price is None:
                missing_sales.append(item.product_name)
        if not price_rows or not any(price.average_price is not None for price in price_rows):
            errors.append("未上传销售价表，不能使用导入价生成明年预算表。")
        elif missing_sales:
            errors.append(f"导入销售价表缺少 {len(missing_sales)} 个产品：{format_missing_names(missing_sales)}。")
    if use_cost_price:
        missing_cost = []
        for key, item in unique_products.items():
            if key != item.product_code:
                continue
            price = prices_by_code.get(item.product_code) or prices_by_code.get(f"NAME::{item.product_name}")
            if price is None or price.cost_price is None:
                missing_cost.append(item.product_name)
        if not price_rows or not any(price.cost_price is not None for price in price_rows):
            errors.append("未上传成本价表，不能使用导入价生成明年预算表。")
        elif missing_cost:
            errors.append(f"导入成本价表缺少 {len(missing_cost)} 个产品：{format_missing_names(missing_cost)}。")
    if errors:
        raise ValueError("；".join(errors))

    for row in product_rows:
        price = prices_by_code.get(row.product_code) or prices_by_code.get(f"NAME::{row.product_name}")
        if price is None:
            continue
        if use_sales_price and price.average_price is not None:
            row.sales_price = float(price.average_price)
        if use_cost_price and price.cost_price is not None:
            row.cost_price = float(price.cost_price)


def format_missing_names(names: list[str]) -> str:
    visible = [name for name in names if name][:5]
    suffix = "等" if len(names) > 5 else ""
    return "、".join(visible) + suffix


def query_actual_sales(db: Session, reference_year: int, group_name: str | None, shop_name: str | None) -> list[ActualSalesDetail]:
    query = db.query(ActualSalesDetail).filter(ActualSalesDetail.year == reference_year)
    if group_name:
        query = query.filter(ActualSalesDetail.group_name == group_name)
    if shop_name:
        query = query.filter(ActualSalesDetail.shop_name == shop_name)
    return query.all()


def build_product_rows_from_actual(
    actual_sales: list[ActualSalesDetail],
    sales_price_adjustment_rate: float,
    cost_price_adjustment_rate: float,
) -> tuple[list[ProductPlanRow], dict[int, float]]:
    monthly_sales: dict[int, float] = defaultdict(float)
    grouped: dict[tuple[int, str, str], dict[str, Any]] = {}

    for row in actual_sales:
        amount = float(row.actual_sales_amount or 0)
        monthly_sales[row.month] += amount
        key = (row.month, row.product_code or f"NAME::{row.product_name}", row.product_name)
        bucket = grouped.setdefault(
            key,
            {
                "month": row.month,
                "group_name": row.group_name,
                "shop_name": row.shop_name,
                "product_code": row.product_code or f"NAME::{row.product_name}",
                "product_name": row.product_name,
                "category": row.category or "",
                "sales": 0.0,
                "quantity": 0.0,
                "cost": 0.0,
            },
        )
        bucket["sales"] += amount
        bucket["quantity"] += float(row.actual_quantity or 0)
        bucket["cost"] += float(row.actual_cost_amount or 0)

    product_rows: list[ProductPlanRow] = []
    for item in grouped.values():
        month_sales = monthly_sales.get(item["month"], 0)
        quantity = item["quantity"]
        sales_price = item["sales"] / quantity if quantity else 0
        cost_price = item["cost"] / quantity if quantity else 0
        product_rows.append(
            ProductPlanRow(
                month=item["month"],
                group_name=item["group_name"],
                shop_name=item["shop_name"],
                product_code=item["product_code"],
                product_name=item["product_name"],
                category=item["category"],
                reference_sales_amount=item["sales"],
                reference_quantity=quantity,
                reference_cost_amount=item["cost"],
                product_share=item["sales"] / month_sales if month_sales else 0,
                sales_price=sales_price * (1 + sales_price_adjustment_rate),
                cost_price=cost_price * (1 + cost_price_adjustment_rate),
            )
        )

    return sorted(product_rows, key=lambda item: (item.month, item.product_code, item.product_name)), dict(monthly_sales)


def build_product_rows_from_budget(
    db: Session,
    reference_year: int,
    group_name: str | None,
    shop_name: str | None,
    sales_price_adjustment_rate: float,
    cost_price_adjustment_rate: float,
    budget_version: int,
) -> tuple[list[ProductPlanRow], dict[int, float]]:
    query = db.query(SalesBudgetDetail).filter(
        SalesBudgetDetail.year == reference_year,
        SalesBudgetDetail.budget_version == budget_version,
    )
    if group_name:
        query = query.filter(SalesBudgetDetail.group_name == group_name)
    if shop_name:
        query = query.filter(SalesBudgetDetail.shop_name == shop_name)
    budget_rows = query.all()
    monthly_sales: dict[int, float] = defaultdict(float)
    grouped: dict[tuple[int, str, str], dict[str, Any]] = {}
    for row in budget_rows:
        amount = float(row.budget_sales_amount or 0)
        monthly_sales[row.month] += amount
        product_code = row.product_code or f"NAME::{row.product_name}"
        key = (row.month, product_code, row.product_name or product_code)
        bucket = grouped.setdefault(
            key,
            {
                "month": row.month,
                "group_name": row.group_name or row.group_code,
                "shop_name": row.shop_name or row.shop_code,
                "product_code": product_code,
                "product_name": row.product_name or product_code,
                "category": row.category or "",
                "sales": 0.0,
                "quantity": 0.0,
                "cost": 0.0,
                "average_price": 0.0,
                "cost_price": 0.0,
            },
        )
        bucket["sales"] += amount
        bucket["quantity"] += float(row.budget_quantity or 0)
        bucket["cost"] += float(row.budget_cost_amount or 0)
        bucket["average_price"] = float(row.average_price or bucket["average_price"] or 0)
        bucket["cost_price"] = float(row.cost_price or bucket["cost_price"] or 0)

    product_rows: list[ProductPlanRow] = []
    for item in grouped.values():
        month_sales = monthly_sales.get(item["month"], 0)
        quantity = item["quantity"]
        sales_price = item["average_price"] or (item["sales"] / quantity if quantity else 0)
        cost_price = item["cost_price"] or (item["cost"] / quantity if quantity else 0)
        product_rows.append(
            ProductPlanRow(
                month=item["month"],
                group_name=item["group_name"],
                shop_name=item["shop_name"],
                product_code=item["product_code"],
                product_name=item["product_name"],
                category=item["category"],
                reference_sales_amount=item["sales"],
                reference_quantity=quantity,
                reference_cost_amount=item["cost"],
                product_share=item["sales"] / month_sales if month_sales else 0,
                sales_price=sales_price * (1 + sales_price_adjustment_rate),
                cost_price=cost_price * (1 + cost_price_adjustment_rate),
            )
        )

    return sorted(product_rows, key=lambda item: (item.month, item.product_code, item.product_name)), dict(monthly_sales)


def build_expense_rows_from_actual(
    db: Session,
    reference_year: int,
    group_name: str | None,
    shop_name: str | None,
    monthly_sales: dict[int, float],
) -> list[ExpensePlanRow]:
    query = db.query(ActualExpenseDetail).filter(ActualExpenseDetail.year == reference_year)
    if group_name:
        query = query.filter(ActualExpenseDetail.group_name == group_name)
    if shop_name:
        query = query.filter(ActualExpenseDetail.shop_name == shop_name)
    grouped: dict[tuple[int, str, str], float] = defaultdict(float)
    for row in query.all():
        grouped[(row.month, row.expense_category or "未分类费用", row.expense_item or "未命名费用")] += float(row.actual_expense_amount or 0)
    return build_expense_plan_rows(grouped, monthly_sales)


def build_expense_rows_from_budget(
    db: Session,
    reference_year: int,
    group_name: str | None,
    shop_name: str | None,
    monthly_sales: dict[int, float],
    budget_version: int,
) -> list[ExpensePlanRow]:
    query = db.query(ExpenseBudgetDetail).filter(
        ExpenseBudgetDetail.year == reference_year,
        ExpenseBudgetDetail.budget_version == budget_version,
    )
    if group_name:
        sales_groups = db.query(SalesBudgetDetail.group_code).filter(SalesBudgetDetail.group_name == group_name).distinct().all()
        group_codes = [item[0] for item in sales_groups]
        if group_codes:
            query = query.filter(ExpenseBudgetDetail.group_code.in_(group_codes))
    if shop_name:
        sales_shops = db.query(SalesBudgetDetail.shop_code).filter(SalesBudgetDetail.shop_name == shop_name).distinct().all()
        shop_codes = [item[0] for item in sales_shops]
        if shop_codes:
            query = query.filter(ExpenseBudgetDetail.shop_code.in_(shop_codes))
    grouped: dict[tuple[int, str, str], float] = defaultdict(float)
    for row in query.all():
        grouped[(row.month, row.expense_category or "未分类费用", row.expense_item or "未命名费用")] += float(row.budget_expense_amount or 0)
    return build_expense_plan_rows(grouped, monthly_sales)


def build_expense_plan_rows(grouped: dict[tuple[int, str, str], float], monthly_sales: dict[int, float]) -> list[ExpensePlanRow]:
    rows: list[ExpensePlanRow] = []
    for (month, category, item), amount in grouped.items():
        month_sales = monthly_sales.get(month, 0)
        rows.append(
            ExpensePlanRow(
                month=month,
                expense_category=category,
                expense_item=item,
                reference_expense_amount=amount,
                reference_month_sales_amount=month_sales,
                expense_rate=amount / month_sales if month_sales else 0,
            )
        )
    return sorted(rows, key=lambda item: (item.month, item.expense_category, item.expense_item))


def build_month_weights(monthly_sales: dict[int, float]) -> dict[int, float]:
    total = sum(monthly_sales.values())
    if total <= 0:
        return {month: 1 / 12 for month in MONTHS}
    return {month: monthly_sales.get(month, 0) / total for month in MONTHS}


def shift_spring_month_weight(weights: dict[int, float], reference_spring_month: int, target_spring_month: int) -> dict[int, float]:
    offset = target_spring_month - reference_spring_month
    if offset == 0:
        return weights
    shifted = {month: 0.0 for month in MONTHS}
    for month in MONTHS:
        source_month = month - offset
        if 1 <= source_month <= 12:
            shifted[month] = weights.get(source_month, 0)
    shifted_total = sum(shifted.values())
    if shifted_total <= 0:
        return weights
    return {month: shifted[month] / shifted_total for month in MONTHS}


def build_planning_workbook(context: dict[str, Any]) -> Workbook:
    wb = Workbook()
    wb.remove(wb.active)
    create_parameter_sheet(wb, context)
    create_product_adjust_sheet(wb, context)
    create_expense_adjust_sheet(wb, context)
    create_product_month_sheet(wb, "任务分解-金额", context, "I", 10000)
    create_product_month_sheet(wb, "任务分解-数量", context, "M", 1)
    create_product_month_sheet(wb, "任务分解-成本", context, "Q", 10000)
    create_expense_budget_sheet(wb, context)
    create_profit_sheet(wb)
    create_check_sheet(wb, context)
    for ws in wb.worksheets:
        apply_common_style(ws)
    return wb


def create_parameter_sheet(wb: Workbook, context: dict[str, Any]) -> None:
    ws = wb.create_sheet("预算编制参数")
    headers = [
        "年度",
        "参考年",
        "运营组",
        "店铺",
        "参考年销售额",
        "明年销售目标",
        "月份",
        "参考月销售额",
        "系统月度占比",
        "手工月度占比",
        "生效月度占比",
        "明年月度销售目标",
        "春节节奏说明",
    ]
    ws.append(headers)
    spring_note = f"参考年春节月份 {context['reference_spring_month']} 月，目标年春节月份 {context['target_spring_month']} 月；可在手工月度占比列微调。"
    for month in MONTHS:
        row = [
            context["target_year"],
            context["reference_year"],
            context["group_name"],
            context["shop_name"],
            round(context["reference_total_sales"], 2),
            round(context["target_sales_amount"], 2),
            month,
            round(context["monthly_sales"].get(month, 0), 2),
            context["month_weights"].get(month, 0),
            "",
            f'=IF(J{month + 1}="",I{month + 1},J{month + 1})',
            f"=$F{month + 1}*K{month + 1}",
            spring_note if month == 1 else "",
        ]
        ws.append(row)


def create_product_adjust_sheet(wb: Workbook, context: dict[str, Any]) -> None:
    ws = wb.create_sheet("产品预算调整")
    headers = [
        "运营组",
        "月份",
        "产品编码",
        "产品名称",
        "参考年产品销售额",
        "系统建议产品占比",
        "手工调整产品占比",
        "生效产品占比",
        "明年产品销售额",
        "参考销售价",
        "手工销售价",
        "生效销售价",
        "明年数量",
        "参考成本价",
        "手工成本价",
        "生效成本价",
        "明年成本额",
        "品类",
    ]
    ws.append(headers)
    for row_index, item in enumerate(context["product_rows"], start=2):
        param_row = item.month + 1
        ws.append(
            [
                item.group_name,
                item.month,
                item.product_code,
                item.product_name,
                round(item.reference_sales_amount, 2),
                item.product_share,
                "",
                f'=IF(G{row_index}="",F{row_index},G{row_index})',
                f"='预算编制参数'!$L${param_row}*H{row_index}",
                round(item.sales_price, 4),
                "",
                f'=IF(K{row_index}="",J{row_index},K{row_index})',
                f"=IF(L{row_index}=0,0,I{row_index}/L{row_index})",
                round(item.cost_price, 4),
                "",
                f'=IF(O{row_index}="",N{row_index},O{row_index})',
                f"=M{row_index}*P{row_index}",
                item.category,
            ]
        )


def create_expense_adjust_sheet(wb: Workbook, context: dict[str, Any]) -> None:
    ws = wb.create_sheet("费用预算调整")
    headers = [
        "月份",
        "费用大项",
        "费用项",
        "参考年费用额",
        "参考年月销售额",
        "系统建议费用率",
        "手工调整费用率",
        "生效费用率",
        "明年费用预算",
    ]
    ws.append(headers)
    for row_index, item in enumerate(context["expense_rows"], start=2):
        param_row = item.month + 1
        ws.append(
            [
                item.month,
                item.expense_category,
                item.expense_item,
                round(item.reference_expense_amount, 2),
                round(item.reference_month_sales_amount, 2),
                item.expense_rate,
                "",
                f'=IF(G{row_index}="",F{row_index},G{row_index})',
                f"='预算编制参数'!$L${param_row}*H{row_index}",
            ]
        )


def create_product_month_sheet(wb: Workbook, title: str, context: dict[str, Any], source_column: str, divisor: int) -> None:
    ws = wb.create_sheet(title)
    headers = ["产品编码", "产品名称", *MONTHS, "合计"]
    ws.append(headers)
    source_range = f"${source_column}:$" + source_column
    seen: dict[str, ProductPlanRow] = {}
    for item in context["product_rows"]:
        seen.setdefault(item.product_code, item)
    for row_index, item in enumerate(sorted(seen.values(), key=lambda row: (row.product_code, row.product_name)), start=2):
        values = [item.product_code, item.product_name]
        for month_col_index, month in enumerate(MONTHS, start=3):
            month_col = get_column_letter(month_col_index)
            formula = (
                f"=SUMIFS('产品预算调整'!{source_range},"
                f'\'产品预算调整\'!$B:$B,{month_col}$1,'
                f'\'产品预算调整\'!$C:$C,$A{row_index})'
            )
            if divisor != 1:
                formula += f"/{divisor}"
            values.append(formula)
        total_start = get_column_letter(3)
        total_end = get_column_letter(14)
        values.append(f"=SUM({total_start}{row_index}:{total_end}{row_index})")
        ws.append(values)


def create_expense_budget_sheet(wb: Workbook, context: dict[str, Any]) -> None:
    ws = wb.create_sheet("费用预算")
    headers = ["费用大项", "费用项", *MONTHS, "合计"]
    ws.append(headers)
    unique_items: dict[tuple[str, str], ExpensePlanRow] = {}
    for item in context["expense_rows"]:
        unique_items.setdefault((item.expense_category, item.expense_item), item)
    for row_index, item in enumerate(sorted(unique_items.values(), key=lambda row: (row.expense_category, row.expense_item)), start=2):
        values = [item.expense_category, item.expense_item]
        for month_col_index, _month in enumerate(MONTHS, start=3):
            month_col = get_column_letter(month_col_index)
            formula = (
                f'=SUMIFS(\'费用预算调整\'!$I:$I,'
                f'\'费用预算调整\'!$A:$A,{month_col}$1,'
                f'\'费用预算调整\'!$B:$B,$A{row_index},'
                f'\'费用预算调整\'!$C:$C,$B{row_index})/10000'
            )
            values.append(formula)
        values.append(f"=SUM(C{row_index}:N{row_index})")
        ws.append(values)


def create_profit_sheet(wb: Workbook) -> None:
    ws = wb.create_sheet("利润分解表")
    headers = ["项目", "口径", *MONTHS, "合计"]
    ws.append(headers)
    rows = [
        ("销售额", "万元", "SUM('任务分解-金额'!{col}2:{col}200)"),
        ("成本额", "万元", "SUM('任务分解-成本'!{col}2:{col}200)"),
        ("利润额", "万元", "{col}2-{col}3-SUM('费用预算'!{col}2:{col}200)"),
        ("费用额", "万元", "SUM('费用预算'!{col}2:{col}200)"),
        ("毛利额", "万元", "{col}2-{col}3"),
        ("利润率", "%", "IF({col}2=0,0,{col}4/{col}2)"),
        ("费用率", "%", "IF({col}2=0,0,{col}5/{col}2)"),
    ]
    for row_index, (name, unit, formula_template) in enumerate(rows, start=2):
        values = [name, unit]
        for month_col_index in range(3, 15):
            col = get_column_letter(month_col_index)
            values.append(f"={formula_template.format(col=col)}")
        values.append(f"=SUM(C{row_index}:N{row_index})" if row_index <= 6 else "")
        ws.append(values)


def create_check_sheet(wb: Workbook, context: dict[str, Any]) -> None:
    ws = wb.create_sheet("校验汇总")
    rows = [
        ["项目", "说明"],
        ["参考数据来源", "今年实际经营数据" if context["source_type"] == "actual" else "预算数据兜底"],
        ["销售目标", "明年全年销售目标是权威口径，月度节奏和产品结构只负责拆分。"],
        ["产品结构", "优先使用参考年同月产品销售占比；缺失月份可在产品预算调整表中手工补充。"],
        ["价格成本", "销售价和成本价默认来自参考年，可在产品预算调整表中逐产品手工覆盖。"],
        ["费用预算", "按费用小项使用参考年同月费用率生成，可在费用预算调整表中手工覆盖。"],
        ["春节节奏", "当前按春节月份迁移月度权重，细节可在预算编制参数表手工调整。"],
    ]
    for row in rows:
        ws.append(row)


def apply_common_style(ws) -> None:
    header_fill = PatternFill("solid", fgColor="EAF2FF")
    for cell in ws[1]:
        cell.font = Font(bold=True, color="1F2937")
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center", vertical="center")
    ws.freeze_panes = "A2"
    for column_cells in ws.columns:
        column_letter = get_column_letter(column_cells[0].column)
        max_length = max(len(str(cell.value)) if cell.value is not None else 0 for cell in column_cells[:80])
        ws.column_dimensions[column_letter].width = min(max(max_length + 2, 12), 28)
    for row in ws.iter_rows():
        for cell in row:
            cell.alignment = Alignment(vertical="center")
            if isinstance(cell.value, float) and abs(cell.value) < 1:
                cell.number_format = "0.00%"
            elif isinstance(cell.value, (int, float)):
                cell.number_format = "#,##0.00"
    for cell in ws[1][2:14]:
        cell.number_format = "0月"


def safe_file_name(name: str) -> str:
    cleaned = re.sub(r"[\\/:*?\"<>|]", "_", name)
    return cleaned.replace(" ", "_")


def parse_rate(value: Any, default: float) -> float:
    if value is None or value == "":
        return default
    parsed = float(value)
    if abs(parsed) > 1:
        return parsed / 100
    return parsed


def parse_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(",", "").replace("元", "")
    if text.endswith("%"):
        return float(text[:-1]) / 100
    try:
        return float(text)
    except ValueError:
        return None


def normalize_header(value: Any) -> str:
    return str(value or "").strip().replace(" ", "").replace("\n", "")


def find_first_index(headers: list[str], candidates: list[str]) -> int | None:
    normalized_candidates = {normalize_header(candidate).lower() for candidate in candidates}
    for index, header in enumerate(headers):
        if header.lower() in normalized_candidates:
            return index
    for index, header in enumerate(headers):
        lowered = header.lower()
        if any(candidate in lowered for candidate in normalized_candidates):
            return index
    return None


def find_price_header_index(rows: list[tuple], price_kind: str) -> int:
    value_candidates = ["销售价", "销售价格", "预算销售价", "建议销售价", "单价", "售价"] if price_kind == "sales" else ["成本价", "成本价格", "产品成本", "单位成本", "店铺成本价", "成本"]
    for index, row in enumerate(rows[:10]):
        headers = [normalize_header(value) for value in row]
        has_product = find_first_index(headers, ["产品编码", "产品代码", "产品长代码", "编码", "sku", "SKU", "产品名称", "商品名称", "品名", "名称"]) is not None
        has_value = find_first_index(headers, value_candidates) is not None
        if has_product and has_value:
            return index
    raise ValueError("未识别到价格表表头。请确认表格包含产品编码或产品名称，以及销售价/成本价列。")


def normalize_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
