from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database.db import Base, get_db
from backend.database.models import ActualExpenseDetail, ActualSalesDetail, ExpenseBudgetDetail, SalesBudgetDetail
from backend.main import app


def build_client(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'read_only.db'}", connect_args={"check_same_thread": False})
    testing_session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    with testing_session() as db:
        db.add_all(
            [
                SalesBudgetDetail(
                    year=2026,
                    budget_version=1,
                    month=4,
                    group_code="G01",
                    group_name="测试运营组6",
                    shop_code="S01",
                    shop_name="测试旗舰店",
                    product_code="P01",
                    product_name="测试产品",
                    category="测试品类",
                    budget_quantity=10,
                    average_price=100,
                    budget_sales_amount=1000,
                    cost_price=60,
                    budget_cost_amount=600,
                    budget_gross_profit=400,
                ),
                ExpenseBudgetDetail(
                    year=2026,
                    budget_version=1,
                    month=4,
                    group_code="G01",
                    shop_code="S01",
                    expense_category="营销费用",
                    expense_item="平台扣点",
                    budget_expense_amount=100,
                ),
                ActualSalesDetail(
                    year=2026,
                    month=4,
                    group_name="测试运营组6",
                    shop_name="测试旗舰店",
                    product_code="P01",
                    product_name="测试产品",
                    category="测试品类",
                    actual_quantity=8,
                    actual_sales_amount=800,
                    actual_cost_amount=480,
                    actual_gross_profit=320,
                    actual_sales_unit_price=100,
                    actual_cost_unit_price=60,
                    source_batch_id="B01",
                ),
                ActualExpenseDetail(
                    year=2026,
                    month=4,
                    group_name="测试运营组6",
                    shop_name="测试旗舰店",
                    expense_category="营销费用",
                    expense_item="平台扣点",
                    actual_expense_amount=80,
                    source_batch_id="B02",
                ),
            ]
        )
        db.commit()

    def override_get_db():
        with testing_session() as db:
            yield db

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app), testing_session


def cleanup_client():
    app.dependency_overrides.clear()


def test_read_only_api_lists_catalog_and_business_data(tmp_path):
    client, _ = build_client(tmp_path)
    try:
        info = client.get("/api/read-only")
        assert info.status_code == 200
        assert info.json()["mode"] == "read_only"
        assert info.json()["mcp_url"].endswith("/mcp")

        budget = client.get("/api/read-only/budget/sales", params={"year": 2026, "page_size": 1})
        assert budget.status_code == 200
        assert budget.json()["total"] == 1
        assert budget.json()["items"][0]["budget_sales_amount"] == 1000

        actual = client.get("/api/read-only/actual/expenses", params={"year": 2026})
        assert actual.status_code == 200
        assert actual.json()["items"][0]["actual_expense_amount"] == 80
    finally:
        cleanup_client()


def test_read_only_summary_uses_same_budget_actual_business_logic(tmp_path):
    client, _ = build_client(tmp_path)
    try:
        response = client.get(
            "/api/read-only/summary",
            params={"year": 2026, "budget_version": 1, "month": 4, "data_view": "comparison"},
        )
        assert response.status_code == 200
        summary = response.json()["summary"]
        assert summary["budget_sales_amount"] == 1000
        assert summary["actual_sales_amount"] == 800
        assert summary["sales_diff"] == -200
        assert response.json()["mode"] == "read_only"
    finally:
        cleanup_client()


def test_read_only_api_has_no_mutating_methods(tmp_path):
    client, _ = build_client(tmp_path)
    try:
        assert client.post("/api/read-only/budget/sales", json={}).status_code == 405
        assert client.put("/api/read-only/actual/sales", json={}).status_code == 405
        assert client.delete("/api/read-only/actual/expenses").status_code == 405
    finally:
        cleanup_client()
