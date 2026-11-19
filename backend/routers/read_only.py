from typing import Literal

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from backend.database.db import get_db
from backend.services.read_only_data_service import query_read_only_records, query_read_only_summary, read_only_catalog


router = APIRouter(prefix="/api/read-only", tags=["read-only"])


def _filters(
    year: int,
    budget_version: int = 1,
    month: int | None = None,
    group_code: str | None = None,
    group_name: str | None = None,
    shop_code: str | None = None,
    shop_name: str | None = None,
    product_code: str | None = None,
    product_name: str | None = None,
    data_view: str = "comparison",
    top_n: int = 10,
) -> dict:
    return {
        "year": year,
        "budget_version": budget_version,
        "month": month,
        "group_code": group_code,
        "group_name": group_name,
        "shop_code": shop_code,
        "shop_name": shop_name,
        "product_code": product_code,
        "product_name": product_name,
        "data_view": data_view,
        "top_n": top_n,
    }


@router.get("")
def get_read_only_info(request: Request) -> dict:
    base_url = str(request.base_url).rstrip("/")
    return {
        **read_only_catalog(),
        "api_base_url": f"{base_url}/api/read-only",
        "openapi_url": f"{base_url}/openapi.json",
        "docs_url": f"{base_url}/docs",
        "mcp_url": f"{base_url}/mcp",
    }


@router.get("/summary")
def get_read_only_summary(
    request: Request,
    year: int = Query(..., ge=2000, le=2100),
    budget_version: int = Query(1, ge=1, le=99),
    month: int | None = Query(None, ge=1, le=12),
    group_code: str | None = None,
    group_name: str | None = None,
    shop_code: str | None = None,
    shop_name: str | None = None,
    product_code: str | None = None,
    product_name: str | None = None,
    data_view: Literal["budget", "actual", "comparison"] = "comparison",
    top_n: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
) -> dict:
    filters = _filters(year, budget_version, month, group_code, group_name, shop_code, shop_name, product_code, product_name, data_view, top_n)
    return query_read_only_summary(db, filters, request.app.state)


def _records(
    dataset,
    request: Request,
    db: Session,
    year: int,
    budget_version: int,
    month: int | None,
    group_code: str | None,
    group_name: str | None,
    shop_code: str | None,
    shop_name: str | None,
    product_code: str | None,
    product_name: str | None,
    page: int,
    page_size: int,
) -> dict:
    filters = _filters(year, budget_version, month, group_code, group_name, shop_code, shop_name, product_code, product_name)
    return query_read_only_records(db, dataset, filters, page=page, page_size=page_size, app_state=request.app.state)


@router.get("/budget/sales")
def get_budget_sales(
    request: Request,
    year: int = Query(..., ge=2000, le=2100),
    budget_version: int = Query(1, ge=1, le=99),
    month: int | None = Query(None, ge=1, le=12),
    group_code: str | None = None,
    group_name: str | None = None,
    shop_code: str | None = None,
    shop_name: str | None = None,
    product_code: str | None = None,
    product_name: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> dict:
    return _records("budget_sales", request, db, year, budget_version, month, group_code, group_name, shop_code, shop_name, product_code, product_name, page, page_size)


@router.get("/budget/expenses")
def get_budget_expenses(
    request: Request,
    year: int = Query(..., ge=2000, le=2100),
    budget_version: int = Query(1, ge=1, le=99),
    month: int | None = Query(None, ge=1, le=12),
    group_code: str | None = None,
    group_name: str | None = None,
    shop_code: str | None = None,
    shop_name: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> dict:
    return _records("budget_expenses", request, db, year, budget_version, month, group_code, group_name, shop_code, shop_name, None, None, page, page_size)


@router.get("/actual/sales")
def get_actual_sales(
    request: Request,
    year: int = Query(..., ge=2000, le=2100),
    month: int | None = Query(None, ge=1, le=12),
    group_code: str | None = None,
    group_name: str | None = None,
    shop_code: str | None = None,
    shop_name: str | None = None,
    product_code: str | None = None,
    product_name: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> dict:
    return _records("actual_sales", request, db, year, 1, month, group_code, group_name, shop_code, shop_name, product_code, product_name, page, page_size)


@router.get("/actual/expenses")
def get_actual_expenses(
    request: Request,
    year: int = Query(..., ge=2000, le=2100),
    month: int | None = Query(None, ge=1, le=12),
    group_code: str | None = None,
    group_name: str | None = None,
    shop_code: str | None = None,
    shop_name: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> dict:
    return _records("actual_expenses", request, db, year, 1, month, group_code, group_name, shop_code, shop_name, None, None, page, page_size)
