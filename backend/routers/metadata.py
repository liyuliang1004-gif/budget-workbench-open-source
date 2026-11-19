from fastapi import APIRouter, Request

from backend.services.metadata_service import list_groups_shops, list_groups_shops_for_edit, write_shop_registry
from backend.services.template_service import (
    actual_business_template_response,
    actual_expense_template_response,
    actual_sales_template_response,
    shop_budget_template_response,
)

router = APIRouter(tags=["metadata"])


@router.get("/api/metadata/groups-shops")
def get_groups_shops(request: Request) -> dict:
    return list_groups_shops(request.app.state)


@router.get("/api/metadata/groups-shops/edit")
def get_groups_shops_for_edit(request: Request) -> dict:
    return list_groups_shops_for_edit(request.app.state)


@router.put("/api/metadata/groups-shops")
def update_groups_shops(payload: dict, request: Request) -> dict:
    return write_shop_registry(payload, request.app.state)


@router.get("/api/templates/shop-budget")
def download_shop_budget_template(request: Request):
    return shop_budget_template_response(request.app.state)


@router.get("/api/templates/actual-sales")
def download_actual_sales_template():
    return actual_sales_template_response()


@router.get("/api/templates/actual-expense")
def download_actual_expense_template():
    return actual_expense_template_response()


@router.get("/api/templates/actual-business")
def download_actual_business_template():
    return actual_business_template_response()
