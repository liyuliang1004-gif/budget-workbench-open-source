from dataclasses import dataclass
from pathlib import Path

from openpyxl import load_workbook
from openpyxl.worksheet.worksheet import Worksheet

from backend.services.calculation_check_service import to_number
from backend.services.format_check_service import MONTH_ALIASES, find_field, find_headers, find_month_columns, has_value, normalize_header


@dataclass
class SalesBudgetRow:
    year: int
    month: int
    group_code: str
    group_name: str | None
    shop_code: str
    shop_name: str | None
    product_code: str
    product_name: str | None
    category: str | None
    budget_quantity: float
    average_price: float
    budget_sales_amount: float
    cost_price: float
    budget_cost_amount: float
    budget_gross_profit: float
    source_file_id: int
    budget_version: int


@dataclass
class ExpenseBudgetRow:
    year: int
    month: int
    group_code: str
    shop_code: str
    expense_category: str
    expense_item: str
    budget_expense_amount: float
    source_file_id: int
    budget_version: int


@dataclass
class ParsedBudget:
    sales_rows: list[SalesBudgetRow]
    expense_rows: list[ExpenseBudgetRow]


MAX_TEMPLATE_SCAN_COLUMN = 80
PRODUCT_PLACEHOLDER_PREFIX = "NAME::"


def row_headers(ws: Worksheet, row_number: int, max_column: int = MAX_TEMPLATE_SCAN_COLUMN) -> dict[str, int]:
    headers = {}
    for column in range(1, min(ws.max_column, max_column) + 1):
        normalized = normalize_header(ws.cell(row=row_number, column=column).value)
        if normalized and normalized not in headers:
            headers[normalized] = column
    return headers


def find_template_header_row(ws: Worksheet, required_alias_groups: list[set[str]], max_row: int = 8) -> tuple[int, dict[str, int]]:
    for row_number in range(1, min(ws.max_row, max_row) + 1):
        headers = row_headers(ws, row_number)
        if all(find_field(headers, aliases) is not None for aliases in required_alias_groups):
            return row_number, headers
    return 1, find_headers(ws)


def month_from_value(value) -> int | None:
    normalized = normalize_header(value)
    for month, aliases in MONTH_ALIASES.items():
        if normalized in {normalize_header(alias) for alias in aliases}:
            return month
    return None


def find_2026_marker_column(ws: Worksheet, header_row: int) -> int | None:
    candidates = []
    for row_number in range(max(1, header_row - 2), header_row + 1):
        for column in range(1, min(ws.max_column, MAX_TEMPLATE_SCAN_COLUMN) + 1):
            value = ws.cell(row=row_number, column=column).value
            text = str(value or "")
            if value == 2026 or "2026" in text:
                candidates.append(column)
    return max(candidates) if candidates else None


def find_template_month_columns(ws: Worksheet, header_row: int) -> dict[int, int]:
    start_column = find_2026_marker_column(ws, header_row)
    month_columns = {}
    for column in range((start_column or 1), min(ws.max_column, MAX_TEMPLATE_SCAN_COLUMN) + 1):
        month = month_from_value(ws.cell(row=header_row, column=column).value)
        if month and month not in month_columns:
            month_columns[month] = column
    if len(month_columns) >= 12:
        return {month: month_columns[month] for month in range(1, 13) if month in month_columns}
    return find_month_columns(row_headers(ws, header_row))


def sheet_uses_wan(ws: Worksheet, max_row: int = 4) -> bool:
    for row_number in range(1, min(ws.max_row, max_row) + 1):
        for column in range(1, min(ws.max_column, MAX_TEMPLATE_SCAN_COLUMN) + 1):
            if "万元" in str(ws.cell(row=row_number, column=column).value or ""):
                return True
    return False


def normalize_product_code(product_code, product_name: str) -> str:
    if has_value(product_code):
        return str(product_code)
    return f"{PRODUCT_PLACEHOLDER_PREFIX}{product_name}"


def has_any_number(ws: Worksheet, row_number: int, month_columns: dict[int, int]) -> bool:
    return any(to_number(ws.cell(row=row_number, column=column).value) is not None for column in month_columns.values())


def read_product_sheet(
    workbook,
    sheet_name: str,
    value_multiplier: float = 1.0,
    extra_aliases: dict[str, set[str]] | None = None,
) -> dict[str, dict]:
    if sheet_name not in workbook.sheetnames:
        return {}
    ws = workbook[sheet_name]
    _, headers = find_template_header_row(ws, [{"产品名称"}])
    header_row = next(
        (row for row in range(1, min(ws.max_row, 8) + 1) if row_headers(ws, row).get(normalize_header("产品名称")) == find_field(headers, {"产品名称"})),
        1,
    )
    month_columns = find_template_month_columns(ws, header_row)
    product_code_col = find_field(headers, {"产品编码", "产品长代码"})
    product_name_col = find_field(headers, {"产品名称"})
    category_col = find_field(headers, {"品类", "类别"})
    rows = {}
    for row_number in range(header_row + 1, ws.max_row + 1):
        raw_product_name = ws.cell(row=row_number, column=product_name_col).value if product_name_col else None
        if not has_value(raw_product_name) or not has_any_number(ws, row_number, month_columns):
            continue
        product_name = str(raw_product_name).strip()
        product_code = normalize_product_code(ws.cell(row=row_number, column=product_code_col).value if product_code_col else None, product_name)
        row = {
            "row_number": row_number,
            "product_code": product_code,
            "product_name": product_name,
            "category": str(ws.cell(row=row_number, column=category_col).value).strip() if category_col and has_value(ws.cell(row=row_number, column=category_col).value) else None,
            "months": {
                month: (round(value * value_multiplier, 2) if (value := to_number(ws.cell(row=row_number, column=column).value)) is not None else None)
                for month, column in month_columns.items()
            },
            "month_columns": month_columns,
        }
        if extra_aliases:
            for key, aliases in extra_aliases.items():
                column = find_field(headers, aliases)
                row[key] = to_number(ws.cell(row=row_number, column=column).value) if column else None
        rows[product_name] = row
    return rows


def read_price_table(workbook) -> dict[str, dict[str, float]]:
    if "预算价格表" not in workbook.sheetnames:
        return {}
    ws = workbook["预算价格表"]
    headers = find_headers(ws)
    product_code_col = find_field(headers, {"产品编码", "产品长代码"})
    prices = {}
    for row_number in range(2, ws.max_row + 1):
        product_code = ws.cell(row=row_number, column=product_code_col).value if product_code_col else None
        if not has_value(product_code):
            continue
        average_price_col = find_field(headers, {"平均销售单价"}) or find_field(headers, {"统一出厂价"})
        cost_price_col = (
            find_field(headers, {"补贴后价格"})
            or find_field(headers, {"内部交易价格"})
            or find_field(headers, {"内部交易价"})
            or find_field(headers, {"统一出厂价"})
            or find_field(headers, {"成本价"})
        )
        prices[str(product_code)] = {
            "average_price": to_number(ws.cell(row=row_number, column=average_price_col).value) if average_price_col else None,
            "cost_price": to_number(ws.cell(row=row_number, column=cost_price_col).value) if cost_price_col else None,
        }
    return prices


def read_cost_prices(workbook) -> dict[str, float]:
    if "任务分解-成本" not in workbook.sheetnames:
        return {}
    ws = workbook["任务分解-成本"]
    headers = find_headers(ws)
    product_code_col = find_field(headers, {"产品编码", "产品长代码"})
    cost_col = find_field(headers, {"成本价"})
    costs = {}
    for row_number in range(2, ws.max_row + 1):
        product_code = ws.cell(row=row_number, column=product_code_col).value if product_code_col else None
        if has_value(product_code) and cost_col:
            cost = to_number(ws.cell(row=row_number, column=cost_col).value)
            if cost is not None:
                costs[str(product_code)] = cost
    return costs


def is_total_label(value) -> bool:
    text = str(value or "").strip()
    return text in {"合计", "总计", "小计", "年度合计", "全年合计"} or text.endswith("合计")


def parse_sales_rows(workbook, file_id: int, year: int, group_code: str, group_name: str | None, shop_code: str, shop_name: str | None, budget_version: int) -> list[SalesBudgetRow]:
    if "任务分解-数量" not in workbook.sheetnames and "任务分解-金额" not in workbook.sheetnames:
        return []
    amount_multiplier = 10000 if "任务分解-金额" in workbook.sheetnames and sheet_uses_wan(workbook["任务分解-金额"]) else 1
    cost_multiplier = 10000 if "任务分解-成本" in workbook.sheetnames and sheet_uses_wan(workbook["任务分解-成本"]) else 1
    amount_rows = read_product_sheet(workbook, "任务分解-金额", amount_multiplier)
    quantity_rows = read_product_sheet(workbook, "任务分解-数量")
    cost_rows = read_product_sheet(workbook, "任务分解-成本", cost_multiplier, {"cost_price": {"成本价", "成本价（元）"}})
    sales_rows = []
    for product_name in sorted(set(amount_rows) | set(quantity_rows)):
        amount_row = amount_rows.get(product_name)
        quantity_row = quantity_rows.get(product_name)
        cost_row = cost_rows.get(product_name)
        identity_row = amount_row or quantity_row or cost_row
        if not identity_row:
            continue
        product_code = identity_row["product_code"]
        category = identity_row.get("category")
        cost_price = cost_row.get("cost_price") if cost_row else None
        for month in range(1, 13):
            quantity = (quantity_row or {}).get("months", {}).get(month)
            sales_amount = (amount_row or {}).get("months", {}).get(month)
            cost_amount = (cost_row or {}).get("months", {}).get(month)
            if quantity is None and sales_amount is None:
                continue
            quantity = quantity or 0.0
            sales_amount = sales_amount or 0.0
            if cost_amount is None:
                cost_amount = round(quantity * cost_price, 2) if cost_price is not None else 0.0
            average_price = round(sales_amount / quantity, 6) if quantity else None
            gross_profit = round(sales_amount - cost_amount, 2)
            sales_rows.append(
                SalesBudgetRow(
                    year=year,
                    month=month,
                    group_code=group_code,
                    group_name=group_name,
                    shop_code=shop_code,
                    shop_name=shop_name,
                    product_code=product_code,
                    product_name=product_name,
                    category=category,
                    budget_quantity=quantity,
                    average_price=average_price,
                    budget_sales_amount=sales_amount,
                    cost_price=cost_price,
                    budget_cost_amount=cost_amount,
                    budget_gross_profit=gross_profit,
                    source_file_id=file_id,
                    budget_version=budget_version,
                )
            )
    return sales_rows


def parse_expense_rows(workbook, file_id: int, year: int, group_code: str, shop_code: str, budget_version: int) -> list[ExpenseBudgetRow]:
    if "费用预算" not in workbook.sheetnames:
        return []
    ws = workbook["费用预算"]
    header_row, headers = find_template_header_row(ws, [{"预算项目"}, {"预算小项"}])
    # In 1.4 files the field row is usually row 3 and the month row is row 4.
    month_header_row = header_row + 1 if len(find_template_month_columns(ws, header_row)) < 12 else header_row
    month_columns = find_template_month_columns(ws, month_header_row)
    category_col = find_field(headers, {"预算项目", "费用大类"})
    item_col = find_field(headers, {"预算小项", "费用小项"})
    expense_rows = []
    current_category = None
    for row_number in range(month_header_row + 1, ws.max_row + 1):
        raw_category = ws.cell(row=row_number, column=category_col).value if category_col else None
        if has_value(raw_category):
            current_category = str(raw_category)
        raw_item = ws.cell(row=row_number, column=item_col).value if item_col else None
        if is_total_label(raw_category) or is_total_label(raw_item):
            continue
        if not has_value(raw_item) or not has_value(current_category):
            continue
        for month, column in month_columns.items():
            amount = to_number(ws.cell(row=row_number, column=column).value)
            if amount is None:
                continue
            expense_rows.append(
                ExpenseBudgetRow(
                    year=year,
                    month=month,
                    group_code=group_code,
                    shop_code=shop_code,
                    expense_category=current_category,
                    expense_item=str(raw_item),
                    budget_expense_amount=round(amount * 10000, 2),
                    source_file_id=file_id,
                    budget_version=budget_version,
                )
            )
    return expense_rows


def parse_budget_workbook(
    file_path: Path,
    file_id: int,
    year: int,
    group_code: str,
    group_name: str | None,
    shop_code: str,
    shop_name: str | None,
    budget_version: int = 1,
) -> ParsedBudget:
    workbook = load_workbook(file_path, data_only=True)
    return ParsedBudget(
        sales_rows=parse_sales_rows(workbook, file_id, year, group_code, group_name, shop_code, shop_name, budget_version),
        expense_rows=parse_expense_rows(workbook, file_id, year, group_code, shop_code, budget_version),
    )
