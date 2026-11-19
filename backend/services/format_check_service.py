from dataclasses import dataclass
from pathlib import Path

from openpyxl.worksheet.worksheet import Worksheet
from sqlalchemy.orm import Session

from backend.database.models import UploadCheckResult, UploadedFile
from backend.services.budget_workbook import load_budget_workbook

REQUIRED_SHEETS = [
    "任务分解-数量",
    "任务分解-金额",
    "任务分解-成本",
    "费用预算",
    "利润分解表",
]
EXPECTED_TEMPLATE_VERSION = "V1.0"

MONTH_ALIASES = {
    month: {f"{month}月", f"{month:02d}月", f"{month} 月"}
    for month in range(1, 13)
}
MONTH_ALIASES.update(
    {
        1: MONTH_ALIASES[1] | {"一月"},
        2: MONTH_ALIASES[2] | {"二月"},
        3: MONTH_ALIASES[3] | {"三月"},
        4: MONTH_ALIASES[4] | {"四月"},
        5: MONTH_ALIASES[5] | {"五月"},
        6: MONTH_ALIASES[6] | {"六月"},
        7: MONTH_ALIASES[7] | {"七月"},
        8: MONTH_ALIASES[8] | {"八月"},
        9: MONTH_ALIASES[9] | {"九月"},
        10: MONTH_ALIASES[10] | {"十月"},
        11: MONTH_ALIASES[11] | {"十一月"},
        12: MONTH_ALIASES[12] | {"十二月"},
    }
)

HEADER_RULES = {
    "任务分解-数量": {
        "required": {"产品名称": {"产品名称"}},
        "months": True,
    },
    "任务分解-金额": {
        "required": {"产品名称": {"产品名称"}},
        "months": True,
    },
    "任务分解-成本": {
        "required": {"产品名称": {"产品名称"}, "成本价": {"成本价", "成本价（元）"}},
        "months": True,
    },
    "费用预算": {
        "required": {"预算项目": {"预算项目"}, "预算小项": {"预算小项"}},
        "months": True,
    },
    "预算价格表": {
        "required": {
            "产品编码": {"产品长代码", "产品编码"},
            "品类": {"类别", "品类"},
            "产品名称": {"产品名称"},
            "统一出厂价": {"统一出厂价"},
            "补贴标准": {"补贴标准"},
            "补贴后价格": {"补贴后价格", "内部交易价格"},
        },
        "months": False,
    },
}


@dataclass
class CheckIssue:
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


def normalize_header(value) -> str:
    return str(value).strip().replace(" ", "") if value is not None else ""


def has_value(value) -> bool:
    return value is not None and str(value).strip() != ""


def find_headers(ws: Worksheet) -> dict[str, int]:
    best_headers = {}
    best_score = -1
    max_column = min(ws.max_column, 80)
    for row_number in range(1, min(ws.max_row, 8) + 1):
        headers = {}
        month_count = 0
        for column in range(1, max_column + 1):
            normalized = normalize_header(ws.cell(row=row_number, column=column).value)
            if not normalized:
                continue
            headers.setdefault(normalized, column)
            if any(normalized in {normalize_header(alias) for alias in aliases} for aliases in MONTH_ALIASES.values()):
                month_count += 1
        score = len(set(headers) & {"产品编码", "产品长代码", "品类", "产品名称", "成本价", "预算项目", "预算小项"}) * 10 + month_count
        if score > best_score:
            best_headers = headers
            best_score = score
    return best_headers


def find_field(headers: dict[str, int], aliases: set[str]) -> int | None:
    normalized_aliases = {normalize_header(alias) for alias in aliases}
    for header, column in headers.items():
        if header in normalized_aliases:
            return column
    return None


def find_month_columns(headers: dict[str, int]) -> dict[int, int]:
    month_columns = {}
    for month, aliases in MONTH_ALIASES.items():
        column = find_field(headers, aliases)
        if column is not None:
            month_columns[month] = column
    return month_columns


def find_month_columns_in_sheet(ws: Worksheet) -> dict[int, int]:
    best_columns = {}
    for row_number in range(1, min(ws.max_row, 8) + 1):
        month_columns = find_month_columns(
            {
                normalize_header(ws.cell(row=row_number, column=column).value): column
                for column in range(1, min(ws.max_column, 80) + 1)
                if normalize_header(ws.cell(row=row_number, column=column).value)
            }
        )
        if len(month_columns) > len(best_columns):
            best_columns = month_columns
    return best_columns


def value_is_number(value) -> bool:
    if value is None or value == "":
        return False
    if isinstance(value, (int, float)):
        return True
    try:
        float(str(value).replace(",", "").strip())
    except ValueError:
        return False
    return True


def add_file_issue(issues: list[CheckIssue], severity: str, error_code: str, message: str, suggestion: str) -> None:
    issues.append(
        CheckIssue(
            severity=severity,
            error_code=error_code,
            error_message=message,
            suggestion=suggestion,
        )
    )


def read_template_version(workbook) -> str | None:
    keywords = workbook.properties.keywords or ""
    for part in str(keywords).replace("；", ";").split(";"):
        if "模板版本" not in part:
            continue
        _, _, version = part.partition(":")
        version = version.strip()
        return version or None
    return None


def check_template_version(workbook, uploaded_file: UploadedFile, issues: list[CheckIssue]) -> None:
    template_version = read_template_version(workbook)
    if template_version:
        uploaded_file.template_version = template_version
    if template_version and template_version != EXPECTED_TEMPLATE_VERSION:
        issues.append(
            CheckIssue(
                severity="info",
                error_code="TEMPLATE_VERSION_MISMATCH",
                error_message=f"模板版本为 {template_version}，不是当前推荐的 {EXPECTED_TEMPLATE_VERSION}，系统会继续按可识别结构检查。",
                uploaded_value=template_version,
                expected_value=EXPECTED_TEMPLATE_VERSION,
                suggestion="如系统能识别目标工作表、月份列和关键字段，可继续检查和入库；正式模板建议后续统一。",
            )
        )


def check_hidden_and_merged_cells(ws: Worksheet, issues: list[CheckIssue]) -> None:
    if ws.merged_cells.ranges:
        issues.append(
            CheckIssue(
                severity="warning",
                error_code="MERGED_CELL_WARNING",
                error_message=f"{ws.title} 存在合并单元格，后续解析前建议拆分。",
                sheet_name=ws.title,
                suggestion="取消关键表头和数据区域的合并单元格。",
            )
        )
    hidden_columns = [key for key, value in ws.column_dimensions.items() if value.hidden]
    if hidden_columns:
        issues.append(
            CheckIssue(
                severity="warning",
                error_code="HIDDEN_COLUMN_WARNING",
                error_message=f"{ws.title} 存在隐藏列：{', '.join(hidden_columns)}。",
                sheet_name=ws.title,
                suggestion="取消隐藏关键列，避免后续读取遗漏。",
            )
        )
    hidden_rows = [str(key) for key, value in ws.row_dimensions.items() if value.hidden]
    if hidden_rows:
        issues.append(
            CheckIssue(
                severity="warning",
                error_code="HIDDEN_ROW_WARNING",
                error_message=f"{ws.title} 存在隐藏行：{', '.join(hidden_rows)}。",
                sheet_name=ws.title,
                suggestion="取消隐藏关键行，避免后续读取遗漏。",
            )
        )


def check_headers(ws: Worksheet, issues: list[CheckIssue]) -> tuple[dict[str, int], dict[int, int]]:
    headers = find_headers(ws)
    rules = HEADER_RULES.get(ws.title)
    if not rules:
        return headers, {}

    for field_name, aliases in rules["required"].items():
        if find_field(headers, aliases) is None:
            issues.append(
                CheckIssue(
                    severity="error",
                    error_code="REQUIRED_HEADER_MISSING",
                    error_message=f"{ws.title} 缺少必要字段：{field_name}。",
                    sheet_name=ws.title,
                    column_name=field_name,
                    expected_value="/".join(sorted(aliases)),
                    suggestion=f"请在 {ws.title} 表头中补充 {field_name} 字段。",
                )
            )

    month_columns = find_month_columns(headers)
    if len(month_columns) < 12:
        month_columns = find_month_columns_in_sheet(ws)
    if rules["months"]:
        for month in range(1, 13):
            if month not in month_columns:
                issues.append(
                    CheckIssue(
                        severity="error",
                        error_code="MONTH_COLUMN_MISSING",
                        error_message=f"缺少 {month}月 列，无法读取月度预算数据。",
                        sheet_name=ws.title,
                        column_name=f"{month}月",
                        month=month,
                        expected_value=f"{month}月",
                        suggestion=f"请在 {ws.title} 表头中补充 {month}月 列。",
                    )
                )
    return headers, month_columns


def row_has_month_value(ws: Worksheet, row_number: int, month_columns: dict[int, int]) -> bool:
    return any(value_is_number(ws.cell(row=row_number, column=column).value) for column in month_columns.values())


def check_required_data(ws: Worksheet, headers: dict[str, int], month_columns: dict[int, int], issues: list[CheckIssue]) -> None:
    product_code_col = find_field(headers, {"产品编码", "产品长代码"})
    product_name_col = find_field(headers, {"产品名称"})
    budget_item_col = find_field(headers, {"预算项目"})
    budget_subitem_col = find_field(headers, {"预算小项"})

    for row_number in range(2, ws.max_row + 1):
        if ws.title in {"任务分解-数量", "任务分解-金额", "任务分解-成本"}:
            if not row_has_month_value(ws, row_number, month_columns):
                continue
            product_code = ws.cell(row=row_number, column=product_code_col).value if product_code_col else None
            product_name = ws.cell(row=row_number, column=product_name_col).value if product_name_col else None
            if not has_value(product_code):
                issues.append(
                    CheckIssue(
                        severity="info",
                        error_code="REQUIRED_PRODUCT_CODE_MISSING",
                        error_message=f"{ws.title} 第 {row_number} 行产品编码为空，系统将按产品名称识别。",
                        sheet_name=ws.title,
                        row_number=row_number,
                        column_name="产品编码",
                        product_name=str(product_name) if has_value(product_name) else None,
                        suggestion="如需和外部系统对码，建议补充产品编码；不补充也可按产品名称入库。",
                    )
                )
            if not has_value(product_name):
                issues.append(
                    CheckIssue(
                        severity="info",
                        error_code="REQUIRED_PRODUCT_NAME_MISSING",
                        error_message=f"{ws.title} 第 {row_number} 行有预算数据但产品名称为空，系统不会把该行作为产品明细入库。",
                        sheet_name=ws.title,
                        row_number=row_number,
                        column_name="产品名称",
                        product_code=str(product_code) if has_value(product_code) else None,
                        suggestion="如果该行是合计/辅助行可忽略；如果是实际产品，请补充产品名称。最终是否漏数以系统重算合计对账为准。",
                    )
                )
        elif ws.title == "费用预算":
            if not row_has_month_value(ws, row_number, month_columns):
                continue
            budget_item = ws.cell(row=row_number, column=budget_item_col).value if budget_item_col else None
            budget_subitem = ws.cell(row=row_number, column=budget_subitem_col).value if budget_subitem_col else None
            if not has_value(budget_item) or not has_value(budget_subitem):
                issues.append(
                    CheckIssue(
                        severity="info",
                        error_code="REQUIRED_EXPENSE_ITEM_MISSING",
                        error_message=f"费用预算第 {row_number} 行有金额但预算项目或预算小项为空，系统不会把该行作为费用明细入库。",
                        sheet_name=ws.title,
                        row_number=row_number,
                        suggestion="如果该行是辅助/公式行可忽略；如果是实际费用，请补充预算项目和预算小项。最终是否漏数以系统重算合计对账为准。",
                    )
                )
        elif ws.title == "预算价格表":
            price_columns = [
                find_field(headers, {"统一出厂价"}),
                find_field(headers, {"补贴标准"}),
                find_field(headers, {"补贴后价格", "内部交易价格"}),
            ]
            if not any(column and has_value(ws.cell(row=row_number, column=column).value) for column in price_columns):
                continue
            product_code = ws.cell(row=row_number, column=product_code_col).value if product_code_col else None
            if not has_value(product_code):
                issues.append(
                    CheckIssue(
                        severity="error",
                        error_code="REQUIRED_PRICE_PRODUCT_CODE_MISSING",
                        error_message=f"预算价格表第 {row_number} 行已有价格数据，但产品编码为空。",
                        sheet_name=ws.title,
                        row_number=row_number,
                        column_name="产品编码",
                        suggestion="请补充产品编码，或清空该行价格数据。",
                    )
                )


def build_issue_rows(file_id: int, issues: list[CheckIssue]) -> list[UploadCheckResult]:
    return [
        UploadCheckResult(
            file_id=file_id,
            check_type="format",
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


def run_format_check(file_id: int, db: Session, *, workbook_cache=None) -> dict:
    uploaded_file = db.get(UploadedFile, file_id)
    if uploaded_file is None:
        raise ValueError("未找到上传文件记录。")

    issues: list[CheckIssue] = []
    file_path = Path(uploaded_file.file_path)
    if not file_path.exists():
        add_file_issue(issues, "error", "FILE_NOT_FOUND", "上传文件不存在。", "请重新上传预算表。")
    elif file_path.stat().st_size == 0:
        add_file_issue(issues, "error", "EMPTY_FILE", "上传文件为空。", "请重新导出完整预算表后上传。")
    if uploaded_file.file_name.startswith("~$"):
        add_file_issue(issues, "error", "TEMP_FILE_NAME", "文件名包含临时文件标记 ~$。", "请关闭表格后上传正式文件。")
    if file_path.suffix.lower() != ".xlsx":
        add_file_issue(issues, "error", "UNSUPPORTED_EXTENSION", "文件扩展名不是 .xlsx。", "请另存为 .xlsx 后重新上传。")

    duplicate = (
        db.query(UploadedFile)
        .filter(UploadedFile.file_hash == uploaded_file.file_hash, UploadedFile.id != uploaded_file.id)
        .first()
    )
    if duplicate:
        add_file_issue(issues, "warning", "DUPLICATE_FILE_HASH", "检测到相同文件 hash，可能重复上传。", "请确认是否重复上传。")

    if not any(issue.severity == "error" for issue in issues):
        try:
            workbook = load_budget_workbook(file_path, data_only=False, cache=workbook_cache)
        except Exception as exc:
            add_file_issue(issues, "error", "FILE_OPEN_FAILED", f"文件无法打开：{exc}", "请确认文件未损坏且为标准 .xlsx。")
            workbook = None

        if workbook is not None:
            check_template_version(workbook, uploaded_file, issues)
            if not workbook.sheetnames:
                add_file_issue(issues, "error", "NO_WORKSHEET", "工作簿无任何工作表。", "请使用标准预算模板。")
            for sheet_name in REQUIRED_SHEETS:
                if sheet_name not in workbook.sheetnames:
                    issues.append(
                        CheckIssue(
                            severity="error",
                            error_code="MISSING_SHEET",
                            error_message=f"缺少必要工作表：{sheet_name}",
                            sheet_name=sheet_name,
                            expected_value=sheet_name,
                            suggestion=f"请补充或恢复工作表：{sheet_name}。",
                        )
                    )
            for sheet_name in workbook.sheetnames:
                if sheet_name not in REQUIRED_SHEETS:
                    issues.append(
                        CheckIssue(
                            severity="info",
                            error_code="UNEXPECTED_SHEET_NAME",
                            error_message=f"检测到非导入工作表：{sheet_name}，系统将忽略该工作表。",
                            sheet_name=sheet_name,
                            uploaded_value=sheet_name,
                            suggestion="系统只读取任务分解和费用/利润主表；额外工作表不会影响入库。",
                        )
                    )
            for sheet_name in REQUIRED_SHEETS:
                if sheet_name not in workbook.sheetnames:
                    continue
                ws = workbook[sheet_name]
                check_hidden_and_merged_cells(ws, issues)
                headers, month_columns = check_headers(ws, issues)
                check_required_data(ws, headers, month_columns, issues)

    db.query(UploadCheckResult).filter(
        UploadCheckResult.file_id == file_id,
        UploadCheckResult.check_type == "format",
    ).delete()
    issue_rows = build_issue_rows(file_id, issues)
    if issue_rows:
        db.add_all(issue_rows)

    error_count = sum(1 for issue in issues if issue.severity == "error")
    warning_count = sum(1 for issue in issues if issue.severity == "warning")
    if error_count:
        uploaded_file.check_status = "检查失败"
    elif warning_count:
        uploaded_file.check_status = "检查警告"
    else:
        uploaded_file.check_status = "检查通过"
    uploaded_file.error_count = error_count
    uploaded_file.warning_count = warning_count
    db.commit()
    db.refresh(uploaded_file)

    return {
        "file_id": uploaded_file.id,
        "file_name": uploaded_file.file_name,
        "check_status": uploaded_file.check_status,
        "error_count": error_count,
        "warning_count": warning_count,
        "message": "格式检查完成",
    }


def serialize_check_result(result: UploadCheckResult) -> dict:
    return {
        "id": result.id,
        "file_id": result.file_id,
        "check_type": result.check_type,
        "severity": result.severity,
        "error_code": result.error_code,
        "error_message": result.error_message,
        "sheet_name": result.sheet_name,
        "cell_address": result.cell_address,
        "row_number": result.row_number,
        "column_name": result.column_name,
        "product_code": result.product_code,
        "product_name": result.product_name,
        "month": result.month,
        "uploaded_value": result.uploaded_value,
        "expected_value": result.expected_value,
        "diff_value": result.diff_value,
        "suggestion": result.suggestion,
        "created_at": result.created_at.isoformat() if result.created_at else None,
    }
