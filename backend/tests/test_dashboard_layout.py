from pathlib import Path

from backend.database.models import ActualSalesDetail, SalesBudgetDetail
from backend.main import app
from backend.tests.test_actual import build_test_client, cleanup_test_client


def set_layout_override(path: Path) -> None:
    app.state.dashboard_layout_path_override = path


def clear_layout_override() -> None:
    if hasattr(app.state, "dashboard_layout_path_override"):
        delattr(app.state, "dashboard_layout_path_override")


def test_dashboard_layout_returns_default_when_file_missing(tmp_path):
    client, _ = build_test_client(tmp_path)
    set_layout_override(tmp_path / "dashboard_layout.json")
    try:
        response = client.get("/api/dashboard/layout")
        assert response.status_code == 200
        body = response.json()
        assert body["version"] == 1
        assert any(item["module_id"] == "metric_cards" and item["visible"] for item in body["widgets"])
        assert any(item["module_id"] == "sales_trend" for item in body["widgets"])
    finally:
        clear_layout_override()
        cleanup_test_client()


def test_dashboard_layout_can_save_visibility_order_width_and_chart_type(tmp_path):
    client, _ = build_test_client(tmp_path)
    set_layout_override(tmp_path / "dashboard_layout.json")
    try:
        payload = {
            "version": 1,
            "widgets": [
                {
                    "id": "sales_trend",
                    "module_id": "sales_trend",
                    "kind": "standard",
                    "title": "销售额趋势",
                    "visible": True,
                    "order": 20,
                    "width": "full",
                    "chart_type": "bar",
                },
                {
                    "id": "metric_cards",
                    "module_id": "metric_cards",
                    "kind": "standard",
                    "title": "核心指标卡",
                    "visible": False,
                    "order": 10,
                    "width": "full",
                    "chart_type": "metric",
                },
            ],
        }
        response = client.put("/api/dashboard/layout", json=payload)
        assert response.status_code == 200
        saved = client.get("/api/dashboard/layout").json()
        assert saved["widgets"][0]["module_id"] == "sales_trend"
        assert saved["widgets"][0]["chart_type"] == "bar"
        assert saved["widgets"][0]["width"] == "full"
        assert saved["widgets"][1]["visible"] is False
    finally:
        clear_layout_override()
        cleanup_test_client()


def test_dashboard_layout_accepts_extra_trend_chart_types(tmp_path):
    client, _ = build_test_client(tmp_path)
    set_layout_override(tmp_path / "dashboard_layout.json")
    try:
        response = client.put(
            "/api/dashboard/layout",
            json={
                "version": 1,
                "widgets": [
                    {
                        "id": "profit_trend",
                        "module_id": "profit_trend",
                        "kind": "standard",
                        "title": "利润额趋势",
                        "visible": True,
                        "order": 10,
                        "width": "half",
                        "chart_type": "area",
                    }
                ],
            },
        )
        assert response.status_code == 200
        assert response.json()["widgets"][0]["chart_type"] == "area"
    finally:
        clear_layout_override()
        cleanup_test_client()


def test_dashboard_layout_accepts_extra_custom_chart_types(tmp_path):
    client, _ = build_test_client(tmp_path)
    set_layout_override(tmp_path / "dashboard_layout.json")
    try:
        response = client.put(
            "/api/dashboard/layout",
            json={
                "version": 1,
                "widgets": [
                    {
                        "id": "custom_scatter",
                        "kind": "custom",
                        "title": "按产品的实际销售额 TOP10",
                        "visible": True,
                        "order": 10,
                        "width": "half",
                        "chart_type": "scatter",
                        "custom_config": {
                            "metric": "sales_amount",
                            "dimension": "product",
                            "data_view": "actual",
                            "sort_by": "actual",
                            "top_n": 10,
                        },
                    }
                ],
            },
        )
        assert response.status_code == 200
        assert response.json()["widgets"][0]["chart_type"] == "scatter"
    finally:
        clear_layout_override()
        cleanup_test_client()


def test_dashboard_layout_rejects_product_expense_rate_custom_widget(tmp_path):
    client, _ = build_test_client(tmp_path)
    set_layout_override(tmp_path / "dashboard_layout.json")
    try:
        response = client.put(
            "/api/dashboard/layout",
            json={
                "version": 1,
                "widgets": [
                    {
                        "id": "custom_bad",
                        "kind": "custom",
                        "title": "产品费用率",
                        "visible": True,
                        "order": 10,
                        "width": "half",
                        "chart_type": "bar",
                        "custom_config": {
                            "metric": "expense_rate",
                            "dimension": "product",
                            "data_view": "comparison",
                            "sort_by": "rate",
                            "top_n": 10,
                        },
                    }
                ],
            },
        )
        assert response.status_code == 400
        assert "产品维度暂未建立费用分摊规则" in response.json()["detail"]
    finally:
        clear_layout_override()
        cleanup_test_client()


def test_dashboard_widgets_data_returns_custom_product_actual_sales(tmp_path):
    client, db_factory = build_test_client(tmp_path)
    set_layout_override(tmp_path / "dashboard_layout.json")
    try:
        with db_factory() as db:
            db.add_all(
                [
                    SalesBudgetDetail(year=2026, month=1, group_code="G001", group_name="测试运营组6", shop_code="S001", shop_name="测试商铺10", product_code="P001", product_name="产品A", budget_quantity=10, budget_sales_amount=1000, budget_cost_amount=500, budget_gross_profit=500, budget_version=1),
                    SalesBudgetDetail(year=2026, month=1, group_code="G001", group_name="测试运营组6", shop_code="S001", shop_name="测试商铺10", product_code="P002", product_name="产品B", budget_quantity=10, budget_sales_amount=2000, budget_cost_amount=1000, budget_gross_profit=1000, budget_version=1),
                    ActualSalesDetail(year=2026, month=1, group_name="测试运营组6", shop_name="测试商铺10", product_code="P001", product_name="产品A", actual_quantity=8, actual_sales_amount=800, actual_cost_amount=400, actual_gross_profit=400, source_batch_id="b1"),
                    ActualSalesDetail(year=2026, month=1, group_name="测试运营组6", shop_name="测试商铺10", product_code="P002", product_name="产品B", actual_quantity=5, actual_sales_amount=500, actual_cost_amount=250, actual_gross_profit=250, source_batch_id="b1"),
                ]
            )
            db.commit()

        response = client.post(
            "/api/dashboard/widgets/data",
            json={
                "filters": {"year": 2026, "budget_version": 1, "month": 1, "data_view": "comparison"},
                "widgets": [
                    {
                        "id": "custom_product_sales",
                        "kind": "custom",
                        "title": "按产品的实际销售额 TOP10",
                        "visible": True,
                        "order": 10,
                        "width": "half",
                        "chart_type": "bar_table",
                        "custom_config": {
                            "metric": "sales_amount",
                            "dimension": "product",
                            "data_view": "actual",
                            "sort_by": "actual",
                            "top_n": 10,
                        },
                    }
                ],
            },
        )
        assert response.status_code == 200
        widget = response.json()["widgets"][0]
        assert widget["value_field"] == "actual_sales_amount"
        assert widget["rows"][0]["name"] == "产品A"
        assert widget["rows"][0]["actual_sales_amount"] == 800
    finally:
        clear_layout_override()
        cleanup_test_client()
