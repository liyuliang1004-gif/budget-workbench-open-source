import json
from dataclasses import dataclass
from pathlib import Path

from openpyxl import load_workbook
from openpyxl.utils import get_column_letter
from sqlalchemy.orm import Session

from backend.config import BASE_DIR
from backend.database.models import UploadCheckResult, UploadedFile
from backend.services.check_status_service import update_file_check_status
from backend.services.format_check_service import find_headers, find_month_columns

EXCEL_ERROR_VALUES = {"#DIV/0!", "#NAME?", "#VALUE!", "#REF!", "#N/A", "#NUM!", "#NULL!"}
FORMULA_RULE_PATH = BASE_DIR / "docs/03_校验规则/标准公式规则.json"


@dataclass
class FormulaIssue:
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
    suggestion: str | None = None


def load_formula_rules() -> dict:
    with FORMULA_RULE_PATH.open("r", encoding="utf-8") as file_obj:
        return json.load(file_obj)


def is_formula(value) -> bool:
    return isinstance(value, str) and value.startswith("=")


def cell_text(value) -> str:
    return "" if value is None else str(value)


def add_issue_rows(file_id: int, issues: list[FormulaIssue], db: Session) -> None:
    rows = [
        UploadCheckResult(
            file_id=file_id,
            check_type="formula",
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
            suggestion=issue.suggestion,
        )
        for issue in issues
    ]
    if rows:
        db.add_all(rows)


def scan_sheet_formulas(ws, rule: dict, issues: list[FormulaIssue]) -> None:
    headers = find_headers(ws)
    month_columns = find_month_columns(headers)
    product_code_col = headers.get("产品编码") or headers.get("产品长代码")
    product_name_col = headers.get("产品名称")
    required = any(item.get("required") for item in rule.get("critical_ranges", []))
    allow_manual = all(item.get("allow_manual_value", True) for item in rule.get("critical_ranges", []))
    expected_formula = "；".join(item.get("formula_type", "") for item in rule.get("critical_ranges", []))

    for row_number in range(2, ws.max_row + 1):
        for month, column in month_columns.items():
            cell = ws.cell(row=row_number, column=column)
            value = cell.value
            if value in EXCEL_ERROR_VALUES:
                code = "formula_ref_error" if value == "#REF!" else "formula_error_value"
                issues.append(
                    FormulaIssue(
                        severity="error",
                        error_code=code,
                        error_message=f"{ws.title} {cell.coordinate} 出现 Excel 错误值 {value}。",
                        sheet_name=ws.title,
                        cell_address=cell.coordinate,
                        row_number=row_number,
                        column_name=f"{month}月",
                        product_code=cell_text(ws.cell(row=row_number, column=product_code_col).value) if product_code_col else None,
                        product_name=cell_text(ws.cell(row=row_number, column=product_name_col).value) if product_name_col else None,
                        month=month,
                        uploaded_value=cell_text(value),
                        expected_value=expected_formula,
                        suggestion="请检查公式引用、除数和来源单元格。",
                    )
                )
                continue
            if is_formula(value) and "#REF!" in value:
                issues.append(
                    FormulaIssue(
                        severity="error",
                        error_code="formula_ref_error",
                        error_message=f"{ws.title} {cell.coordinate} 公式包含 #REF! 引用异常。",
                        sheet_name=ws.title,
                        cell_address=cell.coordinate,
                        row_number=row_number,
                        column_name=f"{month}月",
                        month=month,
                        uploaded_value=value,
                        expected_value=expected_formula,
                        suggestion="请恢复被删除或移动的引用单元格。",
                    )
                )
                continue
            if required and value is None:
                issues.append(
                    FormulaIssue(
                        severity="error",
                        error_code="formula_missing",
                        error_message=f"{ws.title} {cell.coordinate} 关键公式缺失。",
                        sheet_name=ws.title,
                        cell_address=cell.coordinate,
                        row_number=row_number,
                        column_name=f"{month}月",
                        month=month,
                        expected_value=expected_formula,
                        suggestion="请从标准模板复制并恢复该单元格公式。",
                    )
                )
                continue
            if required and not allow_manual and value is not None and not is_formula(value):
                issues.append(
                    FormulaIssue(
                        severity="error",
                        error_code="formula_overwritten",
                        error_message=f"{ws.title} {cell.coordinate} 公式被固定值覆盖。",
                        sheet_name=ws.title,
                        cell_address=cell.coordinate,
                        row_number=row_number,
                        column_name=f"{month}月",
                        product_code=cell_text(ws.cell(row=row_number, column=product_code_col).value) if product_code_col else None,
                        product_name=cell_text(ws.cell(row=row_number, column=product_name_col).value) if product_name_col else None,
                        month=month,
                        uploaded_value=cell_text(value),
                        expected_value=expected_formula,
                        suggestion="请恢复公式，不要手工覆盖关键计算单元格。",
                    )
                )


def run_formula_check(file_id: int, db: Session) -> dict:
    uploaded_file = db.get(UploadedFile, file_id)
    if uploaded_file is None:
        raise ValueError("未找到上传文件记录。")

    db.query(UploadCheckResult).filter(
        UploadCheckResult.file_id == file_id,
        UploadCheckResult.check_type == "formula",
    ).delete()

    issues: list[FormulaIssue] = []
    rules = load_formula_rules()
    file_path = Path(uploaded_file.file_path)
    try:
        workbook = load_workbook(file_path, data_only=False)
    except Exception as exc:
        issues.append(
            FormulaIssue(
                severity="error",
                error_code="formula_file_open_failed",
                error_message=f"公式检查无法打开文件：{exc}",
                suggestion="请确认文件未损坏并重新上传。",
            )
        )
        workbook = None

    if workbook is not None:
        for sheet_name, rule in rules.items():
            if sheet_name not in workbook.sheetnames:
                issues.append(
                    FormulaIssue(
                        severity="error",
                        error_code="formula_sheet_missing",
                        error_message=f"公式检查缺少工作表：{sheet_name}",
                        sheet_name=sheet_name,
                        expected_value=sheet_name,
                        suggestion=f"请恢复工作表：{sheet_name}。",
                    )
                )
                continue
            scan_sheet_formulas(workbook[sheet_name], rule, issues)

    add_issue_rows(file_id, issues, db)
    db.commit()
    status = update_file_check_status(file_id, db)
    return {
        "file_id": file_id,
        "check_type": "formula",
        "status": "检查完成",
        "error_count": sum(1 for issue in issues if issue.severity == "error"),
        "warning_count": sum(1 for issue in issues if issue.severity == "warning"),
        "check_status": status["check_status"],
    }
