from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database.db import get_db
from backend.services.planning_service import (
    check_product_price_table,
    export_next_year_budget_workbooks,
    get_planning_report_dir,
    import_product_price_table,
    list_planning_options,
)
from backend.utils.open_location import reveal_file_in_system

router = APIRouter(prefix="/api/planning", tags=["planning"])


class PlanningExportRequest(BaseModel):
    reference_year: int
    target_year: int
    budget_version: int | None = 1
    group_name: str | None = None
    shop_name: str | None = None
    target_sales_amount: float | None = None
    target_growth_rate: float | None = 0
    sales_price_adjustment_rate: float | None = 0
    cost_price_adjustment_rate: float | None = 0
    sales_price_source: str | None = "actual"
    cost_price_source: str | None = "actual"
    reference_spring_month: int | None = 2
    target_spring_month: int | None = 2


class PlanningOpenLocationRequest(BaseModel):
    name: str


@router.get("/options")
def planning_options(request: Request, reference_year: int | None = None, db: Session = Depends(get_db)) -> dict:
    return list_planning_options(db, reference_year, request.app.state)


@router.get("/files")
def list_planning_files(request: Request) -> dict:
    output_dir = get_planning_report_dir(request.app.state)
    files = [
        {
            "name": path.name,
            "path": str(path),
            "description": "明年预算编制店铺工作簿，包含主业务表、产品预算调整、费用预算调整和校验汇总。",
        }
        for path in sorted(output_dir.glob("*.xlsx"), key=lambda item: item.stat().st_mtime, reverse=True)
        if path.is_file()
    ]
    return {"files": files}


@router.post("/upload-sales-prices")
async def upload_sales_prices(file: UploadFile = File(...), year: int = Form(...), db: Session = Depends(get_db)) -> dict:
    try:
        return import_product_price_table(db, year, await file.read(), "sales")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/check-sales-prices")
async def check_sales_prices(file: UploadFile = File(...), year: int = Form(...)) -> dict:
    return check_product_price_table(await file.read(), "sales")


@router.post("/upload-cost-prices")
async def upload_cost_prices(file: UploadFile = File(...), year: int = Form(...), db: Session = Depends(get_db)) -> dict:
    try:
        return import_product_price_table(db, year, await file.read(), "cost")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/check-cost-prices")
async def check_cost_prices(file: UploadFile = File(...), year: int = Form(...)) -> dict:
    return check_product_price_table(await file.read(), "cost")


@router.post("/export")
def export_planning_workbook(request_data: PlanningExportRequest, request: Request, db: Session = Depends(get_db)) -> dict:
    try:
        paths = export_next_year_budget_workbooks(db, request_data.model_dump(), request.app.state)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "success": True,
        "files": [
            {
                "name": path.name,
                "path": str(path),
                "description": "明年预算编制店铺工作簿，包含主业务表、产品预算调整、费用预算调整和校验汇总。",
            }
            for path in paths
        ],
    }


def resolve_planning_output_path(name: str, app_state) -> Path:
    if Path(name).name != name:
        raise HTTPException(status_code=400, detail="只能打开系统生成的预算编制文件。")
    base_dir = get_planning_report_dir(app_state).resolve()
    target = (base_dir / name).resolve()
    if not target.exists() or base_dir not in target.parents:
        raise HTTPException(status_code=404, detail="未找到预算编制文件。")
    return target


@router.post("/open-location")
def open_planning_location(request_data: PlanningOpenLocationRequest, request: Request) -> dict:
    target = resolve_planning_output_path(request_data.name, request.app.state)
    reveal_file_in_system(target)
    return {"success": True, "name": target.name}
