from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from backend.database.db import get_db
from backend.services.aggregate_service import aggregate_summary, dashboard_data, run_aggregate
from backend.services.comparison_service import dashboard_overview

router = APIRouter(tags=["aggregate"])


@router.post("/api/aggregate/run")
def run_budget_aggregate(request: Request, payload: dict | None = None, db: Session = Depends(get_db)) -> dict:
    budget_version = payload.get("budget_version") if payload else None
    return run_aggregate(db, request.app.state, budget_version=budget_version)


@router.get("/api/aggregate/summary")
def get_budget_summary(budget_version: int | None = None, db: Session = Depends(get_db)) -> dict:
    return aggregate_summary(db, budget_version)


@router.get("/api/dashboard/data")
def get_dashboard_data(
    year: int | None = None,
    month: int | None = None,
    group_code: str | None = None,
    shop_code: str | None = None,
    category: str | None = None,
    product_code: str | None = None,
    budget_version: int | None = None,
    db: Session = Depends(get_db),
) -> dict:
    filters = {
        "year": year,
        "month": month,
        "group_code": group_code,
        "shop_code": shop_code,
        "category": category,
        "product_code": product_code,
        "budget_version": budget_version,
    }
    return dashboard_data(db, filters)


@router.get("/api/dashboard/overview")
def get_dashboard_overview(
    year: int | None = None,
    month: int | None = None,
    group_code: str | None = None,
    group_name: str | None = None,
    shop_code: str | None = None,
    shop_name: str | None = None,
    product_code: str | None = None,
    product_name: str | None = None,
    budget_version: int | None = None,
    data_view: str | None = "comparison",
    top_n: int | None = 8,
    request: Request = None,
    db: Session = Depends(get_db),
) -> dict:
    filters = {
        "year": year,
        "month": month,
        "group_code": group_code,
        "group_name": group_name,
        "shop_code": shop_code,
        "shop_name": shop_name,
        "product_code": product_code,
        "product_name": product_name,
        "budget_version": budget_version,
        "data_view": data_view,
        "top_n": top_n,
    }
    app_state = request.app.state if request else None
    return dashboard_overview(db, filters, app_state)
