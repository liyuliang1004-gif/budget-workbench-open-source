import re
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy.orm import Session

from backend.database.models import ExpenseBudgetDetail, SalesBudgetDetail, UploadCheckResult, UploadedFile
from backend.services.file_service import calculate_file_hash
from backend.services.parse_budget_service import ParsedBudget, parse_budget_workbook

CHECK_PASS_STATUSES = {"检查通过", "检查警告", "有警告"}


def infer_year(file_name: str) -> int | None:
    match = re.search(r"(20\d{2})", file_name)
    return int(match.group(1)) if match else None


def infer_codes(uploaded_file: UploadedFile) -> tuple[str | None, str | None]:
    group_code = uploaded_file.group_code
    shop_code = uploaded_file.shop_code
    parts = re.split(r"[_\-\s]+", uploaded_file.file_name)
    if not group_code:
        group_code = next((part for part in parts if part.upper().startswith("G")), None)
    if not shop_code:
        shop_code = next((part for part in parts if part.upper().startswith("S")), None)
    return group_code, shop_code


def ensure_import_allowed(uploaded_file: UploadedFile, db: Session, force: bool = False) -> tuple[int, str, str]:
    if uploaded_file.file_type != "budget":
        raise HTTPException(status_code=400, detail="该文件不是预算表，不允许入库。")
    if uploaded_file.import_status == "已入库" and not force:
        raise HTTPException(status_code=400, detail="该文件已入库，如需重新导入，请使用 force=true。")
    if uploaded_file.check_status not in CHECK_PASS_STATUSES:
        raise HTTPException(status_code=400, detail="该文件未通过检查，不允许入库。")
    error_count = (
        db.query(UploadCheckResult)
        .filter(UploadCheckResult.file_id == uploaded_file.id, UploadCheckResult.severity == "error")
        .count()
    )
    if error_count:
        raise HTTPException(status_code=400, detail="该文件存在 error 级别检查结果，不允许入库。")
    file_path = Path(uploaded_file.file_path)
    if not file_path.exists():
        raise HTTPException(status_code=400, detail="上传文件缺失，不允许入库。")
    if calculate_file_hash(file_path) != uploaded_file.file_hash:
        raise HTTPException(status_code=400, detail="文件 hash 与上传记录不一致，不允许入库。")
    year = uploaded_file.budget_year or infer_year(uploaded_file.file_name)
    if year is None:
        raise HTTPException(status_code=400, detail="无法识别预算年度，不允许入库。")
    group_code, shop_code = infer_codes(uploaded_file)
    if not group_code or not shop_code:
        raise HTTPException(status_code=400, detail="无法识别店铺或运营组，不允许入库。")
    return year, group_code, shop_code


def clear_file_details(file_id: int, db: Session) -> None:
    db.query(SalesBudgetDetail).filter(SalesBudgetDetail.source_file_id == file_id).delete()
    db.query(ExpenseBudgetDetail).filter(ExpenseBudgetDetail.source_file_id == file_id).delete()


def write_parsed_budget(parsed: ParsedBudget, db: Session) -> tuple[int, int]:
    sales_rows = [
        SalesBudgetDetail(
            year=row.year,
            month=row.month,
            group_code=row.group_code,
            group_name=row.group_name,
            shop_code=row.shop_code,
            shop_name=row.shop_name,
            product_code=row.product_code,
            product_name=row.product_name,
            category=row.category,
            budget_quantity=row.budget_quantity,
            average_price=row.average_price,
            budget_sales_amount=row.budget_sales_amount,
            cost_price=row.cost_price,
            budget_cost_amount=row.budget_cost_amount,
            budget_gross_profit=row.budget_gross_profit,
            source_file_id=row.source_file_id,
            budget_version=row.budget_version,
        )
        for row in parsed.sales_rows
    ]
    expense_rows = [
        ExpenseBudgetDetail(
            year=row.year,
            month=row.month,
            group_code=row.group_code,
            shop_code=row.shop_code,
            expense_category=row.expense_category,
            expense_item=row.expense_item,
            budget_expense_amount=row.budget_expense_amount,
            source_file_id=row.source_file_id,
            budget_version=row.budget_version,
        )
        for row in parsed.expense_rows
    ]
    db.add_all(sales_rows + expense_rows)
    return len(sales_rows), len(expense_rows)


def import_budget_file(file_id: int, db: Session, force: bool = False) -> dict:
    uploaded_file = db.get(UploadedFile, file_id)
    if uploaded_file is None:
        raise HTTPException(status_code=404, detail="未找到上传文件记录。")
    try:
        year, group_code, shop_code = ensure_import_allowed(uploaded_file, db, force)
        if force:
            clear_file_details(file_id, db)
        parsed = parse_budget_workbook(
            Path(uploaded_file.file_path),
            file_id=file_id,
            year=year,
            group_code=group_code,
            group_name=uploaded_file.group_name,
            shop_code=shop_code,
            shop_name=uploaded_file.shop_name,
            budget_version=uploaded_file.budget_version,
        )
        sales_count, expense_count = write_parsed_budget(parsed, db)
        uploaded_file.import_status = "已入库"
        db.commit()
        return {
            "file_id": file_id,
            "status": "success",
            "sales_rows": sales_count,
            "expense_rows": expense_count,
            "message": "预算表已成功解析并入库",
        }
    except HTTPException:
        uploaded_file.import_status = "入库失败"
        db.commit()
        raise
    except Exception as exc:
        db.rollback()
        uploaded_file = db.get(UploadedFile, file_id)
        if uploaded_file:
            uploaded_file.import_status = "入库失败"
            db.commit()
        raise HTTPException(status_code=500, detail=f"预算表入库失败：{exc}") from exc


def import_checked_files(db: Session) -> dict:
    files = (
        db.query(UploadedFile)
        .filter(UploadedFile.file_type == "budget", UploadedFile.import_status != "已入库")
        .all()
    )
    success_count = 0
    failed = []
    skipped_count = 0
    for uploaded_file in files:
        try:
            import_budget_file(uploaded_file.id, db)
            success_count += 1
        except HTTPException as exc:
            if uploaded_file.check_status not in CHECK_PASS_STATUSES:
                skipped_count += 1
            else:
                failed.append({"file_id": uploaded_file.id, "reason": exc.detail})
    return {
        "success_count": success_count,
        "failed_count": len(failed),
        "skipped_count": skipped_count,
        "failed": failed,
    }
