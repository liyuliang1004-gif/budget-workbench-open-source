from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from backend.database.db import get_db
from backend.database.models import UploadCheckResult
from backend.services.calculation_check_service import run_calculation_check
from backend.services.format_check_service import run_format_check, serialize_check_result
from backend.services.formula_check_service import run_formula_check
from backend.services.report_export_service import (
    export_calculation_check_report,
    export_error_location_report,
    export_format_check_report,
    export_formula_check_report,
)

router = APIRouter(prefix="/api/check", tags=["check"])


@router.post("/format/{file_id}")
def check_file_format(file_id: int, db: Session = Depends(get_db)) -> dict:
    try:
        return run_format_check(file_id, db)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/formula/{file_id}")
def check_file_formula(file_id: int, db: Session = Depends(get_db)) -> dict:
    try:
        return run_formula_check(file_id, db)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/calculation/{file_id}")
def check_file_calculation(file_id: int, db: Session = Depends(get_db)) -> dict:
    try:
        return run_calculation_check(file_id, db)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/full/{file_id}")
def check_file_full(file_id: int, db: Session = Depends(get_db)) -> dict:
    steps = []
    for check_name, runner in [
        ("format", run_format_check),
        ("formula", run_formula_check),
        ("calculation", run_calculation_check),
    ]:
        try:
            steps.append(runner(file_id, db))
        except Exception as exc:
            steps.append(
                {
                    "file_id": file_id,
                    "check_type": check_name,
                    "status": "检查异常",
                    "message": str(exc),
                }
            )
    return {"file_id": file_id, "status": "全流程检查完成", "steps": steps}


@router.get("/results/{file_id}")
def get_check_results(
    file_id: int,
    check_type: str | None = None,
    severity: str | None = None,
    sheet_name: str | None = None,
    error_code: str | None = None,
    db: Session = Depends(get_db),
) -> list[dict]:
    query = db.query(UploadCheckResult).filter(UploadCheckResult.file_id == file_id)
    if check_type:
        query = query.filter(UploadCheckResult.check_type == check_type)
    if severity:
        query = query.filter(UploadCheckResult.severity == severity)
    if sheet_name:
        query = query.filter(UploadCheckResult.sheet_name == sheet_name)
    if error_code:
        query = query.filter(UploadCheckResult.error_code == error_code)
    return [serialize_check_result(result) for result in query.order_by(UploadCheckResult.id).all()]


@router.post("/export-format-report")
def export_report(request: Request, db: Session = Depends(get_db)) -> dict[str, str]:
    report_path = export_format_check_report(db, request.app.state)
    return {
        "message": "上传格式检查报告已导出",
        "report_path": str(report_path),
    }


@router.post("/export-formula-report")
def export_formula_report(request: Request, db: Session = Depends(get_db)) -> dict[str, str]:
    report_path = export_formula_check_report(db, request.app.state)
    return {
        "message": "上传公式检查报告已导出",
        "report_path": str(report_path),
    }


@router.post("/export-calculation-report")
def export_calculation_report(request: Request, db: Session = Depends(get_db)) -> dict[str, str]:
    report_path = export_calculation_check_report(db, request.app.state)
    return {
        "message": "计算结果校验报告已导出",
        "report_path": str(report_path),
    }


@router.post("/export-error-report")
def export_error_report(request: Request, db: Session = Depends(get_db)) -> dict[str, str]:
    report_path = export_error_location_report(db, request.app.state)
    return {
        "message": "错误定位总表已导出",
        "report_path": str(report_path),
    }
