from pathlib import Path

from backend.services.static_dashboard_service import render_overview_html
from backend.tests.test_export import build_test_client, cleanup_test_client


def test_export_department_static_dashboard(tmp_path):
    client, _, _, dashboard_dir = build_test_client(tmp_path)
    try:
        response = client.post("/api/export/static-dashboard", json={"dashboard_type": "department", "year": 2026})

        assert response.status_code == 200
        body = response.json()
        index_path = Path(body["dashboard_path"])
        assert index_path.exists()
        assert (index_path.parent / "README_查看说明.txt").exists()
        assert (index_path.parent / "data" / "dashboard-data.json").exists()
        html = index_path.read_text(encoding="utf-8")
        assert "部门预算总览" in html
        assert "预算销售额" in html
        assert ".db" not in html
        assert ".xlsx" not in html
        assert ".env" not in html
        assert "API Key" not in html
    finally:
        cleanup_test_client()


def test_export_group_static_dashboard_and_empty_dashboard(tmp_path):
    client, _, _, dashboard_dir = build_test_client(tmp_path)
    try:
        response = client.post(
            "/api/export/static-dashboard",
            json={"dashboard_type": "group", "year": 2026, "group_code": "G001"},
        )

        assert response.status_code == 200
        index_path = Path(response.json()["dashboard_path"])
        html = index_path.read_text(encoding="utf-8")
        assert "运营组预算总览" in html
        assert "G001" in html

        empty_response = client.post("/api/export/static-dashboard", json={"dashboard_type": "department", "year": 2030})
        assert empty_response.status_code == 200
        empty_html = Path(empty_response.json()["dashboard_path"]).read_text(encoding="utf-8")
        assert "暂无汇总数据" in empty_html
    finally:
        cleanup_test_client()


def test_static_dashboard_report_modules_are_full_width_collapsible_and_not_truncated():
    ranking_rows = [{"name": f"排名第{index}项", "budget_sales_amount": index * 10000} for index in range(1, 14)]
    detail_rows = [{"name": f"明细第{index}项", "budget_sales_amount": index * 10000} for index in range(1, 32)]
    payload = {
        "export_title": "当前视角经营看板",
        "generated_at": "2026-06-16 10:00:00",
        "overview": {
            "breadcrumb": ["2026年", "第1版"],
            "metric_cards": [{"label": "销售额", "value": 1000000, "format": "amount"}],
            "trend_sections": [
                {
                    "id": "sales_trend",
                    "title": "销售额趋势",
                    "x_field": "month",
                    "rows": [{"month": 1, "budget_sales_amount": 100000}],
                    "series": [{"name": "预算销售额", "field": "budget_sales_amount"}],
                }
            ],
            "ranking_sections": [{"id": "sales_ranking", "title": "预算销售排名", "rows": ranking_rows}],
            "table_sections": [{"id": "comparison_detail", "title": "预算实际对比明细", "rows": detail_rows}],
            "health_insights": [{"level": "info", "message": "需要关注费用使用情况。"}],
        },
    }

    html = render_overview_html(payload)

    assert "trend-grid" in html
    assert "report-stack" in html
    assert "<details class='report-module' open>" in html
    assert "预算销售排名（13 行）" in html
    assert "预算实际对比明细（31 行）" in html
    assert "排名第13项" in html
    assert "明细第31项" in html


def test_static_dashboard_table_columns_are_chinese_and_values_are_formatted():
    payload = {
        "export_title": "当前视角经营看板",
        "generated_at": "2026-06-16 10:00:00",
        "overview": {
            "breadcrumb": ["2026年", "第1版"],
            "metric_cards": [],
            "trend_sections": [],
            "ranking_sections": [
                {
                    "id": "sales_ranking",
                    "title": "预算销售排名",
                    "rows": [
                        {
                            "name": "测试运营组6",
                            "budget_quantity": 2092662.53,
                            "budget_sales_amount": 14327900,
                            "budget_cost_amount": 71393700,
                            "budget_gross_profit": 22000506,
                        }
                    ],
                }
            ],
            "table_sections": [],
            "health_insights": [],
        },
    }

    html = render_overview_html(payload)
    visible_html = html.split("<script", 1)[0]

    assert "预算数量" in visible_html
    assert "预算成本额" in visible_html
    assert "预算毛利额" in visible_html
    assert "budget_quantity" not in visible_html
    assert "budget_cost_amount" not in visible_html
    assert "budget_gross_profit" not in visible_html
    assert "7,139.37 万元" in visible_html
