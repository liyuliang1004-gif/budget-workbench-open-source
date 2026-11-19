from datetime import datetime
from hashlib import sha256
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile
from sqlalchemy.orm import Session

from backend.config import BASE_DIR, UPLOAD_RELATIVE_PATH
from backend.database.models import ExpenseBudgetDetail, SalesBudgetDetail, UploadCheckResult, UploadedFile
from backend.services.aggregate_service import run_aggregate
from backend.services.metadata_service import find_group_shop

SUPPORTED_BUDGET_EXTENSIONS = {".xlsx"}


def get_upload_dir(app_state=None) -> Path:
    override = getattr(app_state, "upload_dir_override", None) if app_state else None
    upload_dir = Path(override) if override else BASE_DIR / UPLOAD_RELATIVE_PATH
    upload_dir.mkdir(parents=True, exist_ok=True)
    return upload_dir


def validate_budget_file_name(file_name: str) -> None:
    path = Path(file_name)
    name = path.name
    parts = set(path.parts)
    if name.startswith("~$"):
        raise HTTPException(status_code=400, detail="临时文件不能上传，请关闭表格后重新选择正式文件。")
    if name.startswith("._") or name == ".DS_Store" or "__MACOSX" in parts:
        raise HTTPException(status_code=400, detail="系统元数据文件不能上传，请选择正式预算表。")
    extension = Path(file_name).suffix.lower()
    if extension not in SUPPORTED_BUDGET_EXTENSIONS:
        raise HTTPException(status_code=400, detail="仅支持上传 .xlsx 格式的预算表。")


def calculate_file_hash(file_path: Path) -> str:
    digest = sha256()
    with file_path.open("rb") as file_obj:
        for chunk in iter(lambda: file_obj.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_saved_file_name(original_file_name: str) -> str:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{timestamp}_{uuid4().hex[:8]}_{Path(original_file_name).name}"


def normalize_budget_version(value: int | str | None) -> int:
    try:
        version = int(value or 1)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="预算版本必须是正整数。") from None
    if version < 1:
        raise HTTPException(status_code=400, detail="预算版本必须从第 1 版开始。")
    return version


def normalize_budget_year(value: int | str | None) -> int:
    try:
        year = int(value or 0)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="预算年度必须是 2000 年以后的年份。") from None
    if year < 2000 or year > 2100:
        raise HTTPException(status_code=400, detail="预算年度必须是 2000 到 2100 之间的年份。")
    return year


async def save_budget_upload(
    file: UploadFile,
    db: Session,
    app_state=None,
    budget_version: int | str | None = 1,
    budget_year: int | str | None = None,
    group_code: str | None = None,
    shop_code: str | None = None,
) -> UploadedFile:
    original_file_name = file.filename or ""
    validate_budget_file_name(original_file_name)
    normalized_version = normalize_budget_version(budget_version)
    normalized_year = normalize_budget_year(budget_year)
    group_name, shop_name = find_group_shop(group_code or "", shop_code or "", app_state)

    upload_dir = get_upload_dir(app_state)
    saved_file_name = build_saved_file_name(original_file_name)
    saved_path = upload_dir / saved_file_name

    with saved_path.open("wb") as output:
        while chunk := await file.read(1024 * 1024):
            output.write(chunk)

    file_hash = calculate_file_hash(saved_path)
    uploaded_file = UploadedFile(
        file_name=original_file_name,
        file_path=str(saved_path),
        file_type="budget",
        file_hash=file_hash,
        budget_year=normalized_year,
        group_code=str(group_code).strip(),
        group_name=group_name,
        shop_code=str(shop_code).strip(),
        shop_name=shop_name,
        budget_version=normalized_version,
        check_status="待检查",
        import_status="未入库",
        error_count=0,
        warning_count=0,
    )
    db.add(uploaded_file)
    db.commit()
    db.refresh(uploaded_file)
    return uploaded_file


def list_uploaded_files(db: Session) -> list[UploadedFile]:
    return db.query(UploadedFile).order_by(UploadedFile.upload_time.desc(), UploadedFile.id.desc()).all()


def delete_unimported_file(file_id: int, db: Session) -> str:
    uploaded_file = db.get(UploadedFile, file_id)
    if uploaded_file is None:
        raise HTTPException(status_code=404, detail="未找到上传文件记录。")
    was_imported = uploaded_file.import_status == "已入库"
    file_path = Path(uploaded_file.file_path)
    if not was_imported and not file_path.exists():
        raise HTTPException(status_code=400, detail="本地文件不存在，已停止删除以避免数据库和文件状态不一致。")

    try:
        if file_path.exists():
            file_path.unlink()
        if was_imported:
            db.query(SalesBudgetDetail).filter(SalesBudgetDetail.source_file_id == file_id).delete()
            db.query(ExpenseBudgetDetail).filter(ExpenseBudgetDetail.source_file_id == file_id).delete()
        db.query(UploadCheckResult).filter(UploadCheckResult.file_id == file_id).delete()
        db.delete(uploaded_file)
        db.commit()
        if was_imported:
            run_aggregate(db, budget_version=None, allow_empty=True)
        return "上传文件及已入库数据已删除" if was_imported else "上传文件已删除"
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"删除上传文件失败：{exc}") from exc


def serialize_uploaded_file(uploaded_file: UploadedFile) -> dict:
    saved_file_name = Path(uploaded_file.file_path).name
    return {
        "id": uploaded_file.id,
        "file_name": uploaded_file.file_name,
        "saved_file_name": saved_file_name,
        "file_path": uploaded_file.file_path,
        "file_type": uploaded_file.file_type,
        "file_hash": uploaded_file.file_hash,
        "shop_code": uploaded_file.shop_code,
        "shop_name": uploaded_file.shop_name,
        "group_code": uploaded_file.group_code,
        "group_name": uploaded_file.group_name,
        "template_version": uploaded_file.template_version,
        "budget_year": uploaded_file.budget_year,
        "budget_version": uploaded_file.budget_version,
        "upload_time": uploaded_file.upload_time.isoformat() if uploaded_file.upload_time else None,
        "check_status": uploaded_file.check_status,
        "import_status": uploaded_file.import_status,
        "error_count": uploaded_file.error_count,
        "warning_count": uploaded_file.warning_count,
    }
