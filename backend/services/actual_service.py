from collections import defaultdict
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile
from openpyxl import load_workbook
from sqlalchemy.orm import Session

from backend.database.models import ActualExpenseDetail, ActualImportBatch, ActualSalesDetail, ActualSalesRawLine
from backend.services.expense_category_service import classify_actual_expense_category
from backend.services.file_service import build_saved_file_name, get_upload_dir, normalize_budget_year, validate_budget_file_name
from backend.services.metadata_service import find_group_shop


SALES_HEADERS = {
    "月份",
    "产品长代码",
    "产品名称",
    "单据编号",
    "单位",
    "发货仓库",
    "购货单位",
    "实发数量",
    "销售单价",
    "销售金额",
    "店铺单位成本",
    "店铺成本金额",
    "店铺",
    "运营组",
}
EXPENSE_DETAIL_HEADER = "费用明细"
LEGACY_EXPENSE_DETAIL_HEADER = "事由"
EXPENSE_HEADERS = {"月份", "运营组", "店铺", EXPENSE_DETAIL_HEADER, "金额"}
HEADER_ALIASES = {LEGACY_EXPENSE_DETAIL_HEADER: EXPENSE_DETAIL_HEADER}


def normalize_text(value) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.endswith(".0") and text[:-2].isdigit():
        return text[:-2]
    return text


def parse_month(value) -> int | None:
    if value in ("", None):
        return None
    if isinstance(value, (int, float)):
        month = int(value)
        return month if 1 <= month <= 12 else None
    text = normalize_text(value).replace("月", "").replace("月份", "").strip()
    try:
        month = int(float(text))
    except ValueError:
        return None
    return month if 1 <= month <= 12 else None


def parse_number(value) -> float | None:
    if value in ("", None):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = normalize_text(value).replace(",", "")
    try:
        return float(text)
    except ValueError:
        return None


def round_money(value: float) -> float:
    return round(float(value or 0), 2)


def build_header_map(sheet) -> dict[str, int]:
    headers = {}
    for column_index, cell in enumerate(next(sheet.iter_rows(min_row=1, max_row=1, values_only=True)), start=1):
        header = normalize_text(cell)
        if header:
            headers[header] = column_index
            headers.setdefault(HEADER_ALIASES.get(header, header), column_index)
    return headers


def cell_value(row, headers: dict[str, int], name: str):
    column_index = headers.get(name)
    if column_index is None or column_index > len(row):
        return None
    return row[column_index - 1]


async def save_actual_upload(
    file: UploadFile,
    db: Session,
    app_state,
    year: int | str,
    file_type: str,
    group_code: str | None = None,
    shop_code: str | None = None,
) -> ActualImportBatch:
    if file_type not in {"actual_sales", "actual_expense"}:
        raise HTTPException(status_code=400, detail="实际经营文件类型不正确。")
    original_file_name = file.filename or ""
    validate_budget_file_name(original_file_name)
    normalized_year = normalize_budget_year(year)
    group_name = None
    shop_name = None
    if group_code or shop_code:
        group_name, shop_name = find_group_shop(group_code or "", shop_code or "", app_state)
    upload_dir = get_upload_dir(app_state) / "actual"
    upload_dir.mkdir(parents=True, exist_ok=True)
    saved_path = upload_dir / build_saved_file_name(original_file_name)
    with saved_path.open("wb") as output:
        while chunk := await file.read(1024 * 1024):
            output.write(chunk)
    batch = ActualImportBatch(
        batch_id=uuid4().hex,
        file_name=Path(original_file_name).name,
        file_path=str(saved_path),
        file_type=file_type,
        year=normalized_year,
        group_code=str(group_code or "").strip() or None,
        group_name=group_name,
        shop_code=str(shop_code or "").strip() or None,
        shop_name=shop_name,
        status="uploaded",
    )
    db.add(batch)
    db.commit()
    db.refresh(batch)
    return batch


def get_batch(db: Session, batch_id: str) -> ActualImportBatch:
    batch = db.query(ActualImportBatch).filter(ActualImportBatch.batch_id == batch_id).first()
    if batch is None:
        raise HTTPException(status_code=404, detail="未找到实际经营导入批次。")
    return batch


def is_imported_batch(batch: ActualImportBatch) -> bool:
    return batch.status == "imported" or batch.imported_at is not None


def load_first_sheet(batch: ActualImportBatch):
    path = Path(batch.file_path)
    if not path.exists():
        raise HTTPException(status_code=400, detail="实际经营文件不存在，请重新上传。")
    workbook = load_workbook(path, data_only=True, read_only=True)
    return workbook, workbook[workbook.sheetnames[0]]


def validate_headers(headers: dict[str, int], expected: set[str]) -> list[dict]:
    missing = sorted(expected - set(headers))
    return [
        {
            "severity": "error",
            "check_type": "格式检查",
            "message": f"缺少必要字段：{name}",
            "column_name": name,
            "suggestion": "请使用系统提供的实际经营表模板，或确认表头名称未被修改。",
        }
        for name in missing
    ]


def iter_sales_rows(batch: ActualImportBatch):
    workbook, sheet = load_first_sheet(batch)
    try:
        headers = build_header_map(sheet)
        for row_number, row in enumerate(sheet.iter_rows(min_row=2, values_only=True), start=2):
            if all(value in ("", None) for value in row):
                continue
            yield row_number, row, headers
    finally:
        workbook.close()


def iter_expense_rows(batch: ActualImportBatch):
    workbook, sheet = load_first_sheet(batch)
    try:
        headers = build_header_map(sheet)
        for row_number, row in enumerate(sheet.iter_rows(min_row=2, values_only=True), start=2):
            if all(value in ("", None) for value in row):
                continue
            yield row_number, row, headers
    finally:
        workbook.close()


def build_sales_issue(row_number: int, message: str, severity: str = "error", column_name: str | None = None, suggestion: str | None = None) -> dict:
    return {
        "severity": severity,
        "check_type": "实际销售检查",
        "message": message,
        "sheet_name": "Sheet1",
        "row_number": row_number,
        "column_name": column_name,
        "suggestion": suggestion or "请检查实际销售表对应行的数据。",
    }


def build_expense_issue(row_number: int, message: str, severity: str = "error", column_name: str | None = None, suggestion: str | None = None) -> dict:
    return {
        "severity": severity,
        "check_type": "实际费用检查",
        "message": message,
        "sheet_name": "Sheet1",
        "row_number": row_number,
        "column_name": column_name,
        "suggestion": suggestion or "请检查实际费用表对应行的数据。",
    }


def check_actual_batch(batch_id: str, db: Session) -> dict:
    batch = get_batch(db, batch_id)
    workbook, sheet = load_first_sheet(batch)
    try:
        headers = build_header_map(sheet)
    finally:
        workbook.close()
    expected = SALES_HEADERS if batch.file_type == "actual_sales" else EXPENSE_HEADERS
    issues = validate_headers(headers, expected)
    if issues:
        error_count = len([item for item in issues if item["severity"] == "error"])
        batch.status = "failed"
        batch.error_count = error_count
        batch.warning_count = 0
        batch.row_count = 0
        db.commit()
        return {"batch_id": batch.batch_id, "status": batch.status, "error_count": error_count, "warning_count": 0, "issues": issues}

    row_count = 0
    if batch.file_type == "actual_sales":
        for row_number, row, headers in iter_sales_rows(batch):
            row_count += 1
            month = parse_month(cell_value(row, headers, "月份"))
            product_name = normalize_text(cell_value(row, headers, "产品名称"))
            group_name = batch.group_name or normalize_text(cell_value(row, headers, "运营组"))
            shop_name = batch.shop_name or normalize_text(cell_value(row, headers, "店铺"))
            quantity = parse_number(cell_value(row, headers, "实发数量"))
            sales_amount = parse_number(cell_value(row, headers, "销售金额"))
            cost_amount = parse_number(cell_value(row, headers, "店铺成本金额"))
            if month is None:
                issues.append(build_sales_issue(row_number, "月份无法识别。", column_name="月份"))
            if not product_name:
                issues.append(build_sales_issue(row_number, "产品名称为空，不能入库。", column_name="产品名称"))
            if not group_name or not shop_name:
                issues.append(build_sales_issue(row_number, "运营组或店铺为空，不能入库。", column_name="运营组/店铺"))
            if quantity is None:
                issues.append(build_sales_issue(row_number, "实发数量不是有效数字。", column_name="实发数量"))
            if sales_amount is None:
                issues.append(build_sales_issue(row_number, "销售金额不是有效数字。", column_name="销售金额"))
            if cost_amount is None:
                issues.append(build_sales_issue(row_number, "店铺成本金额不是有效数字。", column_name="店铺成本金额"))
            if quantity == 0 and sales_amount == 0 and cost_amount == 0:
                issues.append(build_sales_issue(row_number, "实发数量为 0，单价和成本单价不具备校验意义；该提醒不阻止入库。", "warning", "实发数量"))
    else:
        for row_number, row, headers in iter_expense_rows(batch):
            reason = normalize_text(cell_value(row, headers, EXPENSE_DETAIL_HEADER))
            amount = parse_number(cell_value(row, headers, "金额"))
            if reason in {"", "0"} and (amount or 0) == 0:
                continue
            row_count += 1
            month = parse_month(cell_value(row, headers, "月份"))
            group_name = batch.group_name or normalize_text(cell_value(row, headers, "运营组"))
            shop_name = batch.shop_name or normalize_text(cell_value(row, headers, "店铺"))
            if month is None:
                issues.append(build_expense_issue(row_number, "月份无法识别。", column_name="月份"))
            if not group_name or not shop_name:
                issues.append(build_expense_issue(row_number, "运营组或店铺为空，不能入库。", column_name="运营组/店铺"))
            if not reason:
                issues.append(build_expense_issue(row_number, "费用明细为空，不能入库。", column_name=EXPENSE_DETAIL_HEADER))
            if amount is None:
                issues.append(build_expense_issue(row_number, "金额不是有效数字。", column_name="金额"))

    error_count = len([item for item in issues if item["severity"] == "error"])
    warning_count = len([item for item in issues if item["severity"] == "warning"])
    if not is_imported_batch(batch):
        batch.status = "failed" if error_count else "checked"
    batch.error_count = error_count
    batch.warning_count = warning_count
    batch.row_count = row_count
    db.commit()
    status = "imported" if is_imported_batch(batch) else batch.status
    return {"batch_id": batch.batch_id, "status": status, "row_count": row_count, "error_count": error_count, "warning_count": warning_count, "issues": issues}


def import_actual_sales(batch: ActualImportBatch, db: Session) -> dict:
    db.query(ActualSalesRawLine).filter(ActualSalesRawLine.batch_id == batch.batch_id).delete()
    db.query(ActualSalesDetail).filter(ActualSalesDetail.source_batch_id == batch.batch_id).delete()
    raw_count = 0
    grouped = defaultdict(lambda: {"quantity": 0.0, "sales": 0.0, "cost": 0.0})
    for row_number, row, headers in iter_sales_rows(batch):
        month = parse_month(cell_value(row, headers, "月份"))
        product_name = normalize_text(cell_value(row, headers, "产品名称"))
        product_code = normalize_text(cell_value(row, headers, "产品长代码")) or f"NAME::{product_name}"
        group_name = batch.group_name or normalize_text(cell_value(row, headers, "运营组"))
        shop_name = batch.shop_name or normalize_text(cell_value(row, headers, "店铺"))
        quantity = parse_number(cell_value(row, headers, "实发数量"))
        sales_amount = parse_number(cell_value(row, headers, "销售金额"))
        cost_amount = parse_number(cell_value(row, headers, "店铺成本金额"))
        if month is None or not product_name or not group_name or not shop_name or quantity is None or sales_amount is None or cost_amount is None:
            continue
        calculated_sales_price = round_money(sales_amount / quantity) if quantity else None
        calculated_cost_price = round_money(cost_amount / quantity) if quantity else None
        warning = "实发数量为 0，单价不具备计算意义。" if quantity == 0 and sales_amount == 0 and cost_amount == 0 else None
        db.add(
            ActualSalesRawLine(
                batch_id=batch.batch_id,
                year=batch.year,
                month=month,
                group_name=group_name,
                shop_name=shop_name,
                product_code=product_code,
                product_name=product_name,
                document_no=normalize_text(cell_value(row, headers, "单据编号")),
                unit=normalize_text(cell_value(row, headers, "单位")),
                warehouse=normalize_text(cell_value(row, headers, "发货仓库")),
                customer_name=normalize_text(cell_value(row, headers, "购货单位")),
                actual_quantity=quantity,
                actual_sales_amount=sales_amount,
                actual_cost_amount=cost_amount,
                raw_sales_unit_price=parse_number(cell_value(row, headers, "销售单价")),
                raw_cost_unit_price=parse_number(cell_value(row, headers, "店铺单位成本")),
                calculated_sales_unit_price=calculated_sales_price,
                calculated_cost_unit_price=calculated_cost_price,
                source_row_number=row_number,
                warning_message=warning,
            )
        )
        raw_count += 1
        key = (batch.year, month, group_name, shop_name, product_code, product_name)
        grouped[key]["quantity"] += quantity
        grouped[key]["sales"] += sales_amount
        grouped[key]["cost"] += cost_amount
    for (year, month, group_name, shop_name, product_code, product_name), values in grouped.items():
        quantity = values["quantity"]
        sales_amount = values["sales"]
        cost_amount = values["cost"]
        db.add(
            ActualSalesDetail(
                year=year,
                month=month,
                group_name=group_name,
                shop_name=shop_name,
                product_code=product_code,
                product_name=product_name,
                actual_quantity=round_money(quantity),
                actual_sales_amount=round_money(sales_amount),
                actual_cost_amount=round_money(cost_amount),
                actual_gross_profit=round_money(sales_amount - cost_amount),
                actual_sales_unit_price=round_money(sales_amount / quantity) if quantity else None,
                actual_cost_unit_price=round_money(cost_amount / quantity) if quantity else None,
                source_batch_id=batch.batch_id,
            )
        )
    return {"raw_rows": raw_count, "detail_rows": len(grouped)}


def import_actual_expense(batch: ActualImportBatch, db: Session) -> dict:
    db.query(ActualExpenseDetail).filter(ActualExpenseDetail.source_batch_id == batch.batch_id).delete()
    count = 0
    for row_number, row, headers in iter_expense_rows(batch):
        reason = normalize_text(cell_value(row, headers, EXPENSE_DETAIL_HEADER))
        amount = parse_number(cell_value(row, headers, "金额"))
        if reason in {"", "0"} and (amount or 0) == 0:
            continue
        month = parse_month(cell_value(row, headers, "月份"))
        group_name = batch.group_name or normalize_text(cell_value(row, headers, "运营组"))
        shop_name = batch.shop_name or normalize_text(cell_value(row, headers, "店铺"))
        if month is None or not group_name or not shop_name or not reason or amount is None:
            continue
        db.add(
            ActualExpenseDetail(
                year=batch.year,
                month=month,
                group_name=group_name,
                shop_name=shop_name,
                expense_category=classify_actual_expense_category(reason),
                expense_item=reason,
                actual_expense_amount=round_money(amount),
                source_batch_id=batch.batch_id,
                source_row_number=row_number,
            )
        )
        count += 1
    return {"expense_rows": count}


def import_actual_batch(batch_id: str, db: Session) -> dict:
    batch = get_batch(db, batch_id)
    check_result = check_actual_batch(batch_id, db)
    if check_result["error_count"]:
        raise HTTPException(status_code=400, detail="实际经营文件检查未通过，不能入库。")
    if batch.file_type == "actual_sales":
        result = import_actual_sales(batch, db)
    else:
        result = import_actual_expense(batch, db)
    batch.status = "imported"
    batch.imported_at = datetime.now()
    db.commit()
    return {"batch_id": batch.batch_id, "status": batch.status, **result}


def delete_actual_batch(batch_id: str, db: Session) -> dict:
    batch = get_batch(db, batch_id)
    file_path = Path(batch.file_path)
    if file_path.exists():
        file_path.unlink()
    db.query(ActualSalesRawLine).filter(ActualSalesRawLine.batch_id == batch.batch_id).delete()
    db.query(ActualSalesDetail).filter(ActualSalesDetail.source_batch_id == batch.batch_id).delete()
    db.query(ActualExpenseDetail).filter(ActualExpenseDetail.source_batch_id == batch.batch_id).delete()
    db.delete(batch)
    db.commit()
    return {"success": True, "message": "实际经营上传批次及对应已入库明细已删除。"}


def infer_batch_group_shop(batch: ActualImportBatch, db: Session | None = None) -> tuple[str | None, str | None]:
    if batch.group_name and batch.shop_name:
        return batch.group_name, batch.shop_name
    if db is None:
        return batch.group_name, batch.shop_name
    detail = None
    if batch.file_type == "actual_sales":
        detail = db.query(ActualSalesDetail).filter(ActualSalesDetail.source_batch_id == batch.batch_id).first()
    if batch.file_type == "actual_expense":
        detail = db.query(ActualExpenseDetail).filter(ActualExpenseDetail.source_batch_id == batch.batch_id).first()
    return (detail.group_name, detail.shop_name) if detail else (batch.group_name, batch.shop_name)


def serialize_batch(batch: ActualImportBatch, db: Session | None = None) -> dict:
    status = "imported" if is_imported_batch(batch) else batch.status
    group_name, shop_name = infer_batch_group_shop(batch, db)
    return {
        "batch_id": batch.batch_id,
        "file_name": batch.file_name,
        "file_type": batch.file_type,
        "year": batch.year,
        "month": batch.month,
        "group_code": batch.group_code,
        "group_name": group_name,
        "shop_code": batch.shop_code,
        "shop_name": shop_name,
        "status": status,
        "status_label": {
            "uploaded": "待检查",
            "checked": "检查通过",
            "failed": "检查失败",
            "imported": "已入库",
            "import_failed": "入库失败",
        }.get(status, status),
        "row_count": batch.row_count,
        "error_count": batch.error_count,
        "warning_count": batch.warning_count,
        "created_at": batch.created_at.isoformat() if batch.created_at else None,
        "imported_at": batch.imported_at.isoformat() if batch.imported_at else None,
    }


def list_actual_batches(db: Session) -> list[dict]:
    return [serialize_batch(batch, db) for batch in db.query(ActualImportBatch).order_by(ActualImportBatch.created_at.desc()).all()]
