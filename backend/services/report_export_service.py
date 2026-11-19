from datetime import datetime
from pathlib import Path

from openpyxl import Workbook
from sqlalchemy.orm import Session

from backend.config import BASE_DIR, CHECK_REPORT_RELATIVE_PATH
from backend.database.models import UploadCheckResult, UploadedFile


def get_report_dir(app_state=None) -> Path:
    override = getattr(app_state, "report_dir_override", None) if app_state else None
    report_dir = Path(override) if override else BASE_DIR / CHECK_REPORT_RELATIVE_PATH
    report_dir.mkdir(parents=True, exist_ok=True)
    return report_dir


def export_format_check_report(db: Session, app_state=None) -> Path:
    return export_typed_check_report(db, "format", "上传格式检查报告", "格式错误明细", app_state)


def append_overview(wb: Workbook, db: Session, title: str = "检查概览") -> None:
    wb = Workbook()
    overview = wb.active
    overview.title = title
    overview.append(["文件ID", "文件名", "上传时间", "检查状态", "错误数量", "警告数量", "是否可进入下一阶段"])

    uploaded_files = db.query(UploadedFile).order_by(UploadedFile.upload_time.desc(), UploadedFile.id.desc()).all()
    for uploaded_file in uploaded_files:
        can_continue = "是" if uploaded_file.check_status == "检查通过" else "否"
        overview.append(
            [
                uploaded_file.id,
                uploaded_file.file_name,
                uploaded_file.upload_time,
                uploaded_file.check_status,
                uploaded_file.error_count,
                uploaded_file.warning_count,
                can_continue,
            ]
        )
    return wb


def append_detail_sheet(wb: Workbook, results, sheet_title: str) -> None:
    detail = wb.create_sheet(sheet_title)
    detail.append(
        [
            "文件ID",
            "文件名",
            "检查类型",
            "严重程度",
            "错误编码",
            "错误说明",
            "Sheet",
            "单元格",
            "行号",
            "列名",
            "产品编码",
            "产品名称",
            "月份",
            "上传值",
            "系统计算值或期望值",
            "差异值",
            "修复建议",
            "创建时间",
        ]
    )
    for result, uploaded_file in results:
        detail.append(
            [
                result.file_id,
                uploaded_file.file_name,
                result.check_type,
                result.severity,
                result.error_code,
                result.error_message,
                result.sheet_name,
                result.cell_address,
                result.row_number,
                result.column_name,
                result.product_code,
                result.product_name,
                result.month,
                result.uploaded_value,
                result.expected_value,
                result.diff_value,
                result.suggestion,
                result.created_at,
            ]
        )


def query_results(db: Session, check_type: str | None = None):
    query = db.query(UploadCheckResult, UploadedFile).join(UploadedFile, UploadCheckResult.file_id == UploadedFile.id)
    if check_type:
        query = query.filter(UploadCheckResult.check_type == check_type)
    return query.order_by(UploadCheckResult.file_id, UploadCheckResult.id).all()


def export_typed_check_report(db: Session, check_type: str, filename_prefix: str, detail_sheet: str, app_state=None) -> Path:
    report_dir = get_report_dir(app_state)
    report_path = report_dir / f"{filename_prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    wb = append_overview(Workbook(), db)
    append_detail_sheet(wb, query_results(db, check_type), detail_sheet)
    wb.save(report_path)
    return report_path


def export_formula_check_report(db: Session, app_state=None) -> Path:
    return export_typed_check_report(db, "formula", "上传公式检查报告", "公式错误明细", app_state)


def export_calculation_check_report(db: Session, app_state=None) -> Path:
    return export_typed_check_report(db, "calculation", "计算结果校验报告", "计算错误明细", app_state)


def export_error_location_report(db: Session, app_state=None) -> Path:
    report_dir = get_report_dir(app_state)
    report_path = report_dir / f"错误定位总表_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    wb = append_overview(Workbook(), db, "错误概览")
    all_results = query_results(db)
    append_detail_sheet(wb, all_results, "全部错误明细")

    by_file = wb.create_sheet("按文件汇总")
    by_file.append(["文件ID", "文件名", "错误数量", "警告数量"])
    uploaded_files = db.query(UploadedFile).order_by(UploadedFile.id).all()
    for uploaded_file in uploaded_files:
        error_count = (
            db.query(UploadCheckResult)
            .filter(UploadCheckResult.file_id == uploaded_file.id, UploadCheckResult.severity == "error")
            .count()
        )
        warning_count = (
            db.query(UploadCheckResult)
            .filter(UploadCheckResult.file_id == uploaded_file.id, UploadCheckResult.severity == "warning")
            .count()
        )
        by_file.append([uploaded_file.id, uploaded_file.file_name, error_count, warning_count])

    by_type = wb.create_sheet("按错误类型汇总")
    by_type.append(["检查类型", "错误编码", "严重程度", "数量"])
    summary = {}
    results = (
        db.query(UploadCheckResult, UploadedFile)
        .join(UploadedFile, UploadCheckResult.file_id == UploadedFile.id)
        .order_by(UploadCheckResult.file_id, UploadCheckResult.id)
        .all()
    )
    for result, _ in results:
        key = (result.check_type, result.error_code, result.severity)
        summary[key] = summary.get(key, 0) + 1
    for (check_type, error_code, severity), count in sorted(summary.items()):
        by_type.append([check_type, error_code, severity, count])

    wb.save(report_path)
    return report_path
