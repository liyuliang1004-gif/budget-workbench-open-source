from dataclasses import dataclass
from pathlib import Path

from openpyxl.utils import get_column_letter
from sqlalchemy.orm import Session

from backend.config import AMOUNT_TOLERANCE
from backend.database.models import UploadCheckResult, UploadedFile
from backend.services.budget_workbook import load_budget_workbook
from backend.services.check_status_service import update_file_check_status
from backend.services.format_check_service import find_field, find_headers, find_month_columns, has_value


@dataclass
class CalculationIssue:
    severity: str
    error_code: str
    error_message: str
    sheet_name: str | None = None
    cell_address: str | None = None
    row_number: int | None = None
    column_name: str | None = None
    product_code: str | None = None
    product_name: str | None = None
    month: int | None = None
    uploaded_value: str | None = None
    expected_value: str | None = None
    diff_value: str | None = None
    suggestion: str | None = None


def to_number(value) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).replace(",", "").strip())
    except ValueError:
        return None


def has_formula(workbook, sheet_name: str, row_number: int, column: int | None) -> bool:
    if workbook is None or column is None or sheet_name not in workbook.sheetnames:
        return False
    value = workbook[sheet_name].cell(row=row_number, column=column).value
    return isinstance(value, str) and value.startswith("=")


def cell_address(row_number: int, column: int | None) -> str | None:
    return f"{get_column_letter(column)}{row_number}" if column else None


def sheet_uses_wan(ws) -> bool:
    for row_number in range(1, min(ws.max_row, 4) + 1):
        for column in range(1, min(ws.max_column, 80) + 1):
            if "万元" in str(ws.cell(row=row_number, column=column).value or ""):
                return True
    return False


def add_issue_rows(file_id: int, issues: list[CalculationIssue], db: Session) -> None:
    rows = [
        UploadCheckResult(
            file_id=file_id,
            check_type="calculation",
            severity=issue.severity,
            error_code=issue.error_code,
            error_message=issue.error_message,
            sheet_name=issue.sheet_name,
            cell_address=issue.cell_address,
            row_number=issue.row_number,
            column_name=issue.column_name,
            product_code=issue.product_code,
            product_name=issue.product_name,
            month=issue.month,
            uploaded_value=issue.uploaded_value,
            expected_value=issue.expected_value,
            diff_value=issue.diff_value,
            suggestion=issue.suggestion,
        )
        for issue in issues
    ]
    if rows:
        db.add_all(rows)


def read_quantity_sheet(wb) -> dict[str, dict]:
    if "任务分解-数量" not in wb.sheetnames:
        return {}
    ws = wb["任务分解-数量"]
    headers = find_headers(ws)
    month_columns = find_month_columns(headers)
    product_code_col = find_field(headers, {"产品编码", "产品长代码"})
    product_name_col = find_field(headers, {"产品名称"})
    price_col = find_field(headers, {"平均销售单价", "销售单价", "单价"})
    rows = {}
    for row_number in range(2, ws.max_row + 1):
        product_name = ws.cell(row=row_number, column=product_name_col).value if product_name_col else None
        if not has_value(product_name):
            continue
        rows[str(product_name).strip()] = {
            "product_code": str(product_code) if has_value(product_code := (ws.cell(row=row_number, column=product_code_col).value if product_code_col else None)) else None,
            "product_name": str(product_name).strip(),
            "average_price": to_number(ws.cell(row=row_number, column=price_col).value) if price_col else None,
            "months": {month: to_number(ws.cell(row=row_number, column=column).value) for month, column in month_columns.items()},
        }
    return rows


def read_product_rows(ws, extra_aliases: dict[str, set[str]] | None = None) -> tuple[dict[str, dict], dict[int, int], dict[str, int]]:
    headers = find_headers(ws)
    month_columns = find_month_columns(headers)
    product_code_col = find_field(headers, {"产品编码", "产品长代码"})
    product_name_col = find_field(headers, {"产品名称"})
    rows = {}
    for row_number in range(2, ws.max_row + 1):
        product_name = ws.cell(row=row_number, column=product_name_col).value if product_name_col else None
        if not has_value(product_name):
            continue
        row = {
            "row_number": row_number,
            "product_code": str(product_code) if has_value(product_code := (ws.cell(row=row_number, column=product_code_col).value if product_code_col else None)) else None,
            "product_name": str(product_name).strip(),
            "months": {month: to_number(ws.cell(row=row_number, column=column).value) for month, column in month_columns.items()},
            "month_columns": month_columns,
        }
        if extra_aliases:
            for key, aliases in extra_aliases.items():
                column = find_field(headers, aliases)
                row[key] = to_number(ws.cell(row=row_number, column=column).value) if column else None
        rows[str(product_name).strip()] = row
    return rows, month_columns, headers


def check_year_total(ws, issues: list[CalculationIssue], sheet_name: str) -> None:
    headers = find_headers(ws)
    month_columns = find_month_columns(headers)
    total_col = find_field(headers, {"年度合计", "全年合计", "合计"})
    if not total_col or not month_columns:
        return
    for row_number in range(2, ws.max_row + 1):
        month_sum = sum(to_number(ws.cell(row=row_number, column=column).value) or 0 for column in month_columns.values())
        uploaded_total = to_number(ws.cell(row=row_number, column=total_col).value)
        if uploaded_total is None:
            continue
        diff = uploaded_total - month_sum
        if abs(diff) > AMOUNT_TOLERANCE:
            issues.append(
                CalculationIssue(
                    severity="error",
                    error_code="yearly_total_mismatch",
                    error_message=f"{sheet_name} 第 {row_number} 行年度合计不等于 1-12 月汇总。",
                    sheet_name=sheet_name,
                    cell_address=cell_address(row_number, total_col),
                    row_number=row_number,
                    column_name="年度合计",
                    uploaded_value=str(uploaded_total),
                    expected_value=str(month_sum),
                    diff_value=str(diff),
                    suggestion="请检查年度合计公式或 1-12 月金额。",
                )
            )


def row_is_total(ws, row_number: int, headers: dict[str, int], month_columns: dict[int, int]) -> bool:
    ignored_columns = set(month_columns.values())
    total_col = find_field(headers, {"年度合计", "全年合计", "合计"})
    if total_col:
        ignored_columns.add(total_col)
    for column in range(1, ws.max_column + 1):
        if column in ignored_columns:
            continue
        value = ws.cell(row=row_number, column=column).value
        if value is None:
            continue
        text = str(value).strip()
        if text in {"合计", "总计", "小计", "全年合计", "年度合计"} or text.endswith("合计"):
            return True
    return False


def check_sheet_total_row(ws, issues: list[CalculationIssue], sheet_name: str, expected_monthly: dict[int, float]) -> None:
    headers = find_headers(ws)
    month_columns = find_month_columns(headers)
    if not month_columns:
        return
    total_col = find_field(headers, {"年度合计", "全年合计", "合计"})
    total_row = next((row_number for row_number in range(2, ws.max_row + 1) if row_is_total(ws, row_number, headers, month_columns)), None)
    if total_row is None:
        return
    for month, column in month_columns.items():
        uploaded = to_number(ws.cell(row=total_row, column=column).value)
        if uploaded is None:
            continue
        expected = round(expected_monthly.get(month, 0.0), 2)
        diff = uploaded - expected
        if abs(diff) > AMOUNT_TOLERANCE:
            issues.append(
                CalculationIssue(
                    severity="error",
                    error_code="workbook_total_mismatch",
                    error_message=f"{sheet_name} 自带合计行 {month}月 与系统重算结果不一致。",
                    sheet_name=sheet_name,
                    cell_address=cell_address(total_row, column),
                    row_number=total_row,
                    column_name=f"{month}月",
                    month=month,
                    uploaded_value=str(uploaded),
                    expected_value=str(expected),
                    diff_value=str(diff),
                    suggestion="请检查表格合计行公式或明细数据，避免上传表自带合计与系统汇总口径不一致。",
                )
            )
    if total_col:
        uploaded_total = to_number(ws.cell(row=total_row, column=total_col).value)
        if uploaded_total is not None:
            expected_total = round(sum(expected_monthly.values()), 2)
            diff = uploaded_total - expected_total
            if abs(diff) > AMOUNT_TOLERANCE:
                issues.append(
                    CalculationIssue(
                        severity="error",
                        error_code="workbook_total_mismatch",
                        error_message=f"{sheet_name} 自带年度合计与系统重算结果不一致。",
                        sheet_name=sheet_name,
                        cell_address=cell_address(total_row, total_col),
                        row_number=total_row,
                        column_name="年度合计",
                        uploaded_value=str(uploaded_total),
                        expected_value=str(expected_total),
                        diff_value=str(diff),
                        suggestion="请检查表格年度合计公式或明细数据。",
                    )
                )


def check_workbook_self_totals(
    wb,
    monthly_sales: dict[int, float],
    monthly_cost: dict[int, float],
    monthly_expenses: dict[int, float],
    issues: list[CalculationIssue],
) -> None:
    sheet_totals = {
        "任务分解-金额": monthly_sales,
        "任务分解-成本": monthly_cost,
        "费用预算": monthly_expenses,
        "利润分解表": {
            month: (monthly_sales.get(month, 0.0) - monthly_cost.get(month, 0.0) - monthly_expenses.get(month, 0.0))
            for month in range(1, 13)
        },
    }
    for sheet_name, expected_monthly in sheet_totals.items():
        if sheet_name in wb.sheetnames:
            check_sheet_total_row(wb[sheet_name], issues, sheet_name, expected_monthly)


def check_sales_amount(wb, quantities: dict[str, dict], issues: list[CalculationIssue], formula_wb=None) -> dict[int, float]:
    monthly_sales = {month: 0.0 for month in range(1, 13)}
    if "任务分解-金额" not in wb.sheetnames:
        return monthly_sales
    ws = wb["任务分解-金额"]
    amount_rows, _, _ = read_product_rows(ws)
    for product_name, quantity_row in quantities.items():
        amount_row = amount_rows.get(product_name)
        if amount_row is None:
            continue
        for month, quantity in quantity_row["months"].items():
            uploaded = amount_row["months"].get(month)
            if uploaded is None:
                continue
            monthly_sales[month] += uploaded
            column = amount_row["month_columns"].get(month)
            if quantity is not None and not has_value(uploaded) and not has_formula(formula_wb, "任务分解-金额", amount_row["row_number"], column):
                issues.append(
                    CalculationIssue(
                        severity="error",
                        error_code="sales_amount_missing",
                        error_message=f"{product_name} {month}月 上传销售额为空。",
                        sheet_name="任务分解-金额",
                        cell_address=cell_address(amount_row["row_number"], column),
                        row_number=amount_row["row_number"],
                        column_name=f"{month}月",
                        product_code=amount_row.get("product_code"),
                        product_name=quantity_row.get("product_name"),
                        month=month,
                        suggestion="请检查销售额公式是否缺失。",
                    )
                )
    check_year_total(ws, issues, "任务分解-金额")
    return monthly_sales


def check_cost_amount(wb, quantities: dict[str, dict], issues: list[CalculationIssue], formula_wb=None) -> dict[int, float]:
    monthly_cost = {month: 0.0 for month in range(1, 13)}
    if "任务分解-成本" not in wb.sheetnames:
        return monthly_cost
    ws = wb["任务分解-成本"]
    cost_rows, _, _ = read_product_rows(ws, {"cost_price": {"成本价"}})
    amount_divisor = 10000 if sheet_uses_wan(ws) else 1
    for product_name, quantity_row in quantities.items():
        cost_row = cost_rows.get(product_name)
        if cost_row is None:
            continue
        cost_price = cost_row.get("cost_price")
        for month, quantity in quantity_row["months"].items():
            if quantity is None:
                continue
            if cost_price is None:
                issues.append(
                    CalculationIssue(
                        severity="error",
                        error_code="cost_price_missing",
                        error_message=f"{product_name} 缺少成本价，无法重算 {month}月 成本额。",
                        sheet_name="任务分解-成本",
                        product_code=cost_row.get("product_code"),
                        product_name=quantity_row.get("product_name"),
                        month=month,
                        suggestion="请补充成本价或价格表中的内部交易价格。",
                    )
                )
                continue
            expected = quantity * cost_price / amount_divisor
            uploaded = cost_row["months"].get(month)
            column = cost_row["month_columns"].get(month)
            monthly_cost[month] += expected
            if uploaded is None and has_formula(formula_wb, "任务分解-成本", cost_row["row_number"], column):
                uploaded = expected
            if uploaded is None:
                issues.append(
                    CalculationIssue(
                        severity="error",
                        error_code="cost_amount_missing",
                        error_message=f"{product_name} {month}月 上传成本额为空。",
                        sheet_name="任务分解-成本",
                        cell_address=cell_address(cost_row["row_number"], column),
                        row_number=cost_row["row_number"],
                        column_name=f"{month}月",
                        product_code=cost_row.get("product_code"),
                        product_name=quantity_row.get("product_name"),
                        month=month,
                        expected_value=str(expected),
                        suggestion="请检查成本额公式是否缺失。",
                    )
                )
                continue
            diff = uploaded - expected
            if abs(diff) > AMOUNT_TOLERANCE:
                issues.append(
                    CalculationIssue(
                        severity="error",
                        error_code="cost_amount_mismatch",
                        error_message=f"{product_name} {month}月 成本额与系统重算结果不一致。",
                        sheet_name="任务分解-成本",
                        cell_address=cell_address(cost_row["row_number"], column),
                        row_number=cost_row["row_number"],
                        column_name=f"{month}月",
                        product_code=cost_row.get("product_code"),
                        product_name=quantity_row.get("product_name"),
                        month=month,
                        uploaded_value=str(uploaded),
                        expected_value=str(expected),
                        diff_value=str(diff),
                        suggestion="检查销量、成本价或成本额公式是否被覆盖。",
                    )
                )
    check_year_total(ws, issues, "任务分解-成本")
    return monthly_cost


def check_expenses(wb, issues: list[CalculationIssue]) -> dict[int, float]:
    monthly_expenses = {month: 0.0 for month in range(1, 13)}
    if "费用预算" not in wb.sheetnames:
        return monthly_expenses
    ws = wb["费用预算"]
    headers = find_headers(ws)
    month_columns = find_month_columns(headers)
    item_col = find_field(headers, {"预算项目"})
    subitem_col = find_field(headers, {"预算小项"})
    for row_number in range(2, ws.max_row + 1):
        if row_is_total(ws, row_number, headers, month_columns):
            continue
        item = ws.cell(row=row_number, column=item_col).value if item_col else None
        subitem = ws.cell(row=row_number, column=subitem_col).value if subitem_col else None
        row_has_amount = False
        for month, column in month_columns.items():
            raw = ws.cell(row=row_number, column=column).value
            if raw is None or raw == "":
                continue
            row_has_amount = True
            amount = to_number(raw)
            if amount is None:
                issues.append(
                    CalculationIssue(
                        severity="error",
                        error_code="expense_amount_not_number",
                        error_message=f"费用预算第 {row_number} 行 {month}月 金额不是数字。",
                        sheet_name="费用预算",
                        cell_address=cell_address(row_number, column),
                        row_number=row_number,
                        column_name=f"{month}月",
                        month=month,
                        uploaded_value=str(raw),
                        suggestion="请填写数字金额，不要填写文本。",
                    )
                )
            else:
                monthly_expenses[month] += amount
        if row_has_amount and (not has_value(item) or not has_value(subitem)):
            issues.append(
                CalculationIssue(
                    severity="error",
                    error_code="expense_item_missing",
                    error_message=f"费用预算第 {row_number} 行有金额，但预算项目或预算小项为空。",
                    sheet_name="费用预算",
                    row_number=row_number,
                    suggestion="请补充预算项目和预算小项，或清空该行金额。",
                )
            )
    check_year_total(ws, issues, "费用预算")
    return monthly_expenses


def check_profit(wb, monthly_sales: dict[int, float], monthly_cost: dict[int, float], monthly_expenses: dict[int, float], issues: list[CalculationIssue], formula_wb=None) -> None:
    if "利润分解表" not in wb.sheetnames:
        return
    ws = wb["利润分解表"]
    headers = find_headers(ws)
    month_columns = find_month_columns(headers)
    item_col = find_field(headers, {"项目", "预算项目"})
    if not item_col:
        return
    for row_number in range(2, ws.max_row + 1):
        item = str(ws.cell(row=row_number, column=item_col).value or "")
        for month, column in month_columns.items():
            raw = ws.cell(row=row_number, column=column).value
            if raw == "#DIV/0!":
                sales_is_zero = (monthly_sales.get(month, 0) or 0) == 0
                issues.append(
                    CalculationIssue(
                        severity="warning" if sales_is_zero else "error",
                        error_code="rate_div_zero_reminder" if sales_is_zero else "rate_div_zero_error",
                        error_message=f"利润分解表第 {row_number} 行 {month}月 出现 #DIV/0!。"
                        + ("销售额为 0 时率类公式无法计算，作为提醒处理。" if sales_is_zero else ""),
                        sheet_name="利润分解表",
                        cell_address=cell_address(row_number, column),
                        row_number=row_number,
                        column_name=f"{month}月",
                        month=month,
                        uploaded_value=str(raw),
                        suggestion="销售额为 0 时，率类公式没有校验意义，不阻止入库；如需展示请把模板公式改为销售额为 0 时显示 0 或空值。"
                        if sales_is_zero
                        else "销售额不为 0 时出现除零错误，请检查公式除数和来源单元格。",
                    )
                )
            if item == "利润":
                uploaded = to_number(raw)
                expected = monthly_sales.get(month, 0) - monthly_cost.get(month, 0) - monthly_expenses.get(month, 0)
                if uploaded is None and has_formula(formula_wb, "利润分解表", row_number, column):
                    uploaded = expected
                if uploaded is None:
                    continue
                diff = uploaded - expected
                if abs(diff) > AMOUNT_TOLERANCE:
                    issues.append(
                        CalculationIssue(
                            severity="error",
                            error_code="profit_amount_mismatch",
                            error_message=f"利润分解表 {month}月 利润与系统重算结果不一致。",
                            sheet_name="利润分解表",
                            cell_address=cell_address(row_number, column),
                            row_number=row_number,
                            column_name=f"{month}月",
                            month=month,
                            uploaded_value=str(uploaded),
                            expected_value=str(expected),
                            diff_value=str(diff),
                            suggestion="请检查销售额、成本额、费用额和利润公式。",
                        )
                    )
    check_year_total(ws, issues, "利润分解表")


def run_calculation_check(file_id: int, db: Session, *, workbook_cache=None) -> dict:
    uploaded_file = db.get(UploadedFile, file_id)
    if uploaded_file is None:
        raise ValueError("未找到上传文件记录。")

    issues: list[CalculationIssue] = []
    try:
        file_path = Path(uploaded_file.file_path)
        wb = load_budget_workbook(file_path, data_only=True, cache=workbook_cache)
        formula_wb = load_budget_workbook(file_path, data_only=False, cache=workbook_cache)
    except Exception as exc:
        issues.append(
            CalculationIssue(
                severity="error",
                error_code="calculation_file_open_failed",
                error_message=f"计算校验无法打开文件：{exc}",
                suggestion="请确认文件未损坏并重新上传。",
            )
        )
        wb = None
        formula_wb = None

    if wb is not None:
        quantities = read_quantity_sheet(wb)
        monthly_sales = check_sales_amount(wb, quantities, issues, formula_wb)
        monthly_cost = check_cost_amount(wb, quantities, issues, formula_wb)
        monthly_expenses = check_expenses(wb, issues)
        check_profit(wb, monthly_sales, monthly_cost, monthly_expenses, issues, formula_wb)
        check_workbook_self_totals(wb, monthly_sales, monthly_cost, monthly_expenses, issues)

    db.query(UploadCheckResult).filter(
        UploadCheckResult.file_id == file_id,
        UploadCheckResult.check_type == "calculation",
    ).delete()
    add_issue_rows(file_id, issues, db)
    db.commit()
    status = update_file_check_status(file_id, db)
    return {
        "file_id": file_id,
        "check_type": "calculation",
        "status": "检查完成",
        "error_count": sum(1 for issue in issues if issue.severity == "error"),
        "warning_count": sum(1 for issue in issues if issue.severity == "warning"),
        "check_status": status["check_status"],
    }
