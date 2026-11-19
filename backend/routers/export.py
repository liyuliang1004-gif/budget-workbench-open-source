from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from backend.database.db import get_db
from backend.services.export_excel_service import export_custom_report, export_excel_reports, get_check_report_dir, get_summary_report_dir
from backend.services.static_dashboard_service import export_dashboard_overview, export_static_dashboard, get_static_dashboard_dir
from backend.utils.open_location import reveal_file_in_system

router = APIRouter(prefix="/api/export", tags=["export"])


class ExcelExportRequest(BaseModel):
    report_type: str = "all"
    year: int | None = None
    budget_version: int | None = None

    @field_validator("year", "budget_version", mode="before")
    @classmethod
    def empty_numeric_to_none(cls, value):
        return None if value == "" else value


class StaticDashboardRequest(BaseModel):
    dashboard_type: str = "department"
    year: int | None = None
    group_code: str | None = None
    budget_version: int | None = None

    @field_validator("year", "budget_version", mode="before")
    @classmethod
    def empty_numeric_to_none(cls, value):
        return None if value == "" else value

    @field_validator("group_code", mode="before")
    @classmethod
    def empty_text_to_none(cls, value):
        return None if value == "" else value


class OpenLocationRequest(BaseModel):
    name: str
    kind: str = "report"


class DashboardViewExportRequest(BaseModel):
    year: int | None = None
    budget_version: int | None = None
    month: int | None = None
    group_code: str | None = None
    shop_code: str | None = None
    product_code: str | None = None
    product_name: str | None = None
    data_view: str | None = "comparison"
    top_n: int | None = 20

    @field_validator("year", "budget_version", "month", "top_n", mode="before")
    @classmethod
    def empty_numeric_to_none(cls, value):
        return None if value == "" else value

    @field_validator("group_code", "shop_code", "product_code", "product_name", "data_view", mode="before")
    @classmethod
    def empty_text_to_none(cls, value):
        return None if value == "" else value


class CustomExportRequest(BaseModel):
    template: str = "budget_actual_detail"
    year: int | None = None
    budget_version: int | None = None
    month: int | None = None
    group_code: str | None = None
    shop_code: str | None = None
    product_code: str | None = None
    product_name: str | None = None
    data_view: str | None = "comparison"
    top_n: int | None = 20

    @field_validator("year", "budget_version", "month", "top_n", mode="before")
    @classmethod
    def empty_numeric_to_none(cls, value):
        return None if value == "" else value

    @field_validator("group_code", "shop_code", "product_code", "product_name", "data_view", mode="before")
    @classmethod
    def empty_text_to_none(cls, value):
        return None if value == "" else value


@router.post("/excel")
def export_excel(request_data: ExcelExportRequest, request: Request, db: Session = Depends(get_db)) -> dict:
    try:
        paths = export_excel_reports(db, request_data.report_type, request_data.year, request.app.state, request_data.budget_version)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "success": True,
        "files": [serialize_export_file(path) for path in paths],
    }


@router.post("/static-dashboard")
def export_dashboard(request_data: StaticDashboardRequest, request: Request, db: Session = Depends(get_db)) -> dict:
    try:
        index_path = export_static_dashboard(
            db,
            request_data.dashboard_type,
            request_data.year,
            request_data.group_code,
            request.app.state,
            request_data.budget_version,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"success": True, "dashboard_path": str(index_path), "files": [serialize_dashboard_file(index_path)]}


@router.post("/dashboard-view")
def export_current_dashboard_view(request_data: DashboardViewExportRequest, request: Request, db: Session = Depends(get_db)) -> dict:
    path = export_dashboard_overview(db, request_data.model_dump(), request.app.state)
    return {"success": True, "dashboard_path": str(path), "files": [serialize_dashboard_file(path)]}


@router.post("/custom")
def export_custom(request_data: CustomExportRequest, request: Request, db: Session = Depends(get_db)) -> dict:
    path = export_custom_report(db, request_data.model_dump(), request.app.state)
    return {"success": True, "files": [serialize_export_file(path)]}


def extract_budget_version(name: str) -> int | None:
    import re

    match = re.search(r"第(\d+)版", name)
    return int(match.group(1)) if match else None


def describe_export(name: str) -> str:
    version = extract_budget_version(name)
    version_text = f"第 {version} 版" if version else "未标注版本"
    if "部门预算" in name:
        return f"{version_text}部门预算汇总表，包含部门总览、月度趋势、运营组、店铺、品类和费用汇总。"
    if "运营组" in name:
        return f"{version_text}运营组预算汇总表，包含运营组趋势、店铺明细和费用结构。"
    if "店铺" in name:
        return f"{version_text}店铺预算汇总表，包含店铺趋势、产品明细和费用明细。"
    if "产品品类" in name:
        return f"{version_text}产品品类预算汇总表，包含品类、产品和月度趋势。"
    if "费用" in name:
        return f"{version_text}费用预算汇总表，包含费用总览、大类、小项和月度趋势。"
    if "当前视角经营总览" in name:
        return "当前首页筛选视角导出，包含核心指标、排名、明细和经营提醒。"
    if "当前视角经营看板" in name:
        return "当前首页筛选视角 HTML 可视化看板，可离线发给同事查看。"
    if "静态看板" in name or "预算看板" in name:
        return "HTML 可视化静态看板，可离线查看。"
    if "自定义导出" in name:
        return "用户自定义导出模板结果。"
    if "错误" in name:
        return "上传检查错误定位表。"
    return f"{version_text}导出文件。"


def serialize_export_file(path: Path) -> dict:
    return {
        "name": path.name,
        "path": str(path),
        "description": describe_export(path.name),
        "budget_version": extract_budget_version(path.name),
        "exported_at": datetime_from_path(path),
        "kind": "report",
    }


def datetime_from_path(path: Path) -> str:
    from datetime import datetime

    return datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")


def serialize_dashboard_file(index_path: Path) -> dict:
    return {
        "name": index_path.parent.name,
        "path": str(index_path),
        "description": describe_export(index_path.parent.name),
        "budget_version": extract_budget_version(index_path.parent.name),
        "exported_at": datetime_from_path(index_path),
        "kind": "dashboard",
    }


def serialize_export_list_file(path: Path) -> dict:
    item = serialize_export_file(path)
    item.pop("path", None)
    return item


def serialize_dashboard_list_file(path: Path) -> dict:
    item = serialize_dashboard_file(path)
    item.pop("path", None)
    return item


@router.get("/files")
def list_export_files(request: Request, budget_version: int | None = None) -> dict:
    report_dirs = [get_summary_report_dir(request.app.state), get_check_report_dir(request.app.state)]
    reports = []
    for report_dir in report_dirs:
        for path in sorted(report_dir.glob("*.xlsx")):
            item = serialize_export_list_file(path)
            if budget_version is None or item["budget_version"] == budget_version:
                reports.append(item)
    dashboard_dir = get_static_dashboard_dir(request.app.state)
    dashboards = [
        serialize_dashboard_list_file(path)
        for path in sorted(dashboard_dir.glob("*/index.html"))
        if budget_version is None or serialize_dashboard_file(path)["budget_version"] == budget_version
    ]
    reports.sort(key=lambda item: item.get("exported_at") or "", reverse=True)
    dashboards.sort(key=lambda item: item.get("exported_at") or "", reverse=True)
    return {"reports": reports, "dashboards": dashboards}


def resolve_export_path(name: str, kind: str, app_state) -> Path:
    if Path(name).name != name:
        raise HTTPException(status_code=400, detail="只能打开系统导出列表中的文件名。")
    if kind == "dashboard":
        base_dir = get_static_dashboard_dir(app_state).resolve()
        target = (base_dir / name / "index.html").resolve()
    else:
        candidates = [get_summary_report_dir(app_state).resolve(), get_check_report_dir(app_state).resolve()]
        for base_dir in candidates:
            target = (base_dir / name).resolve()
            if target.exists() and base_dir in target.parents:
                return target
        raise HTTPException(status_code=404, detail="未找到导出文件。")
    if not target.exists() or base_dir not in target.parents:
        raise HTTPException(status_code=404, detail="未找到导出文件。")
    return target


@router.post("/open-location")
def open_export_location(request_data: OpenLocationRequest, request: Request) -> dict:
    target = resolve_export_path(request_data.name, request_data.kind, request.app.state)
    reveal_file_in_system(target)
    return {"success": True, "name": target.name}
