import re
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import insert, update
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
    if parsed.sales_rows:
        db.execute(insert(SalesBudgetDetail), [vars(row) for row in parsed.sales_rows], execution_options={"render_nulls": True})
    if parsed.expense_rows:
        db.execute(insert(ExpenseBudgetDetail), [vars(row) for row in parsed.expense_rows])
    return len(parsed.sales_rows), len(parsed.expense_rows)


def import_budget_file(file_id: int, db: Session, force: bool = False) -> dict:
    uploaded_file = db.get(UploadedFile, file_id)
    if uploaded_file is None:
        raise HTTPException(status_code=404, detail="未找到上传文件记录。")
    try:
        year, group_code, shop_code = ensure_import_allowed(uploaded_file, db, force)
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
        claim = update(UploadedFile).where(
            UploadedFile.id == file_id,
            UploadedFile.check_status.in_(CHECK_PASS_STATUSES),
        )
        if not force:
            claim = claim.where(UploadedFile.import_status != "已入库")
        if db.execute(claim.values(import_status="已入库")).rowcount != 1:
            raise HTTPException(status_code=409, detail="文件的检查或入库状态已变化，请刷新列表。")
        if force:
            clear_file_details(file_id, db)
        sales_count, expense_count = write_parsed_budget(parsed, db)
        db.commit()
        return {
            "file_id": file_id,
            "status": "success",
            "sales_rows": sales_count,
            "expense_rows": expense_count,
            "message": "预算表已成功解析并入库",
        }
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        uploaded_file = db.get(UploadedFile, file_id)
        if uploaded_file and uploaded_file.import_status != "已入库":
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
