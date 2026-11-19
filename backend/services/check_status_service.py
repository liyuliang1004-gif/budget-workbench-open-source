from sqlalchemy.orm import Session

from backend.database.models import UploadCheckResult, UploadedFile


def update_file_check_status(file_id: int, db: Session) -> dict:
    uploaded_file = db.get(UploadedFile, file_id)
    if uploaded_file is None:
        raise ValueError("未找到上传文件记录。")

    error_count = (
        db.query(UploadCheckResult)
        .filter(UploadCheckResult.file_id == file_id, UploadCheckResult.severity == "error")
        .count()
    )
    warning_count = (
        db.query(UploadCheckResult)
        .filter(UploadCheckResult.file_id == file_id, UploadCheckResult.severity == "warning")
        .count()
    )
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
        "check_status": uploaded_file.check_status,
        "error_count": error_count,
        "warning_count": warning_count,
    }
