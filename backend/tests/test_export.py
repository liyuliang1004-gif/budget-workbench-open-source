import json
import shutil
from unittest.mock import patch

from openpyxl import load_workbook
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database.db import Base, get_db
from backend.database.models import (
    DepartmentBudgetSummary,
    ExpenseBudgetDetail,
    GroupBudgetSummary,
    SalesBudgetDetail,
    ShopBudgetSummary,
    UploadCheckResult,
    UploadedFile,
)
from backend.main import app


def build_test_client(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'export_test.db'}",
        connect_args={"check_same_thread": False},
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    report_dir = tmp_path / "reports"
    check_dir = tmp_path / "checks"
    dashboard_dir = tmp_path / "dashboards"
    report_dir.mkdir()
    check_dir.mkdir()
    dashboard_dir.mkdir()

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    app.state.summary_report_dir_override = report_dir
    app.state.report_dir_override = check_dir
    app.state.static_dashboard_dir_override = dashboard_dir
    seed_data(TestingSessionLocal)
    return TestClient(app), report_dir, check_dir, dashboard_dir


def cleanup_test_client():
    app.dependency_overrides.clear()
    for name in ["summary_report_dir_override", "report_dir_override", "static_dashboard_dir_override"]:
        if hasattr(app.state, name):
            delattr(app.state, name)


def seed_data(db_factory):
    with db_factory() as db:
        uploaded_file = UploadedFile(
            file_name="G001_S001_2026_预算表.xlsx",
            file_path="/tmp/G001_S001_2026_预算表.xlsx",
            file_type="budget",
            file_hash="hash",
            group_code="G001",
            shop_code="S001",
            shop_name="测试店",
            check_status="检查通过",
            import_status="已入库",
        )
        db.add(uploaded_file)
        db.flush()
        db.add(
            UploadCheckResult(
                file_id=uploaded_file.id,
                check_type="format",
                severity="error",
                error_code="MISSING_SHEET",
                error_message="缺少必要工作表",
                sheet_name="任务分解-数量",
            )
        )
        for month, sales, cost, expense in [(1, 1000, 600, 100), (2, 1200, 720, 200)]:
            db.add(
                SalesBudgetDetail(
                    year=2026,
                    month=month,
                    group_code="G001",
                    group_name="一组",
                    shop_code="S001",
                    shop_name="测试店",
                    product_code="P001",
                    product_name="测试产品",
                    category="食品",
                    budget_quantity=100,
                    average_price=10,
                    budget_sales_amount=sales,
                    cost_price=6,
                    budget_cost_amount=cost,
                    budget_gross_profit=sales - cost,
                    source_file_id=uploaded_file.id,
                )
            )
            db.add(
                ExpenseBudgetDetail(
                    year=2026,
                    month=month,
                    group_code="G001",
                    shop_code="S001",
                    expense_category="推广费",
                    expense_item="投流",
                    budget_expense_amount=expense,
                    source_file_id=uploaded_file.id,
                )
            )
            db.add(
                ShopBudgetSummary(
                    year=2026,
                    month=month,
                    group_code="G001",
                    shop_code="S001",
                    sales_amount=sales,
                    cost_amount=cost,
                    gross_profit=sales - cost,
                    expense_amount=expense,
                    profit_amount=sales - cost - expense,
                    cost_rate=cost / sales,
                    expense_rate=expense / sales,
                    profit_rate=(sales - cost - expense) / sales,
                )
            )
            db.add(
                GroupBudgetSummary(
                    year=2026,
                    month=month,
                    group_code="G001",
                    sales_amount=sales,
                    cost_amount=cost,
                    gross_profit=sales - cost,
                    expense_amount=expense,
                    profit_amount=sales - cost - expense,
                    cost_rate=cost / sales,
                    expense_rate=expense / sales,
                    profit_rate=(sales - cost - expense) / sales,
                )
            )
            db.add(
                DepartmentBudgetSummary(
                    year=2026,
                    month=month,
                    sales_amount=sales,
                    cost_amount=cost,
                    gross_profit=sales - cost,
                    expense_amount=expense,
                    profit_amount=sales - cost - expense,
                    cost_rate=cost / sales,
                    expense_rate=expense / sales,
                    profit_rate=(sales - cost - expense) / sales,
                )
            )
        db.commit()


def test_export_all_excel_reports_and_error_report(tmp_path):
    client, report_dir, check_dir, _ = build_test_client(tmp_path)
    try:
        response = client.post("/api/export/excel", json={"report_type": "all", "year": 2026})

        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert len(body["files"]) == 6
        names = {item["name"] for item in body["files"]}
        assert any(name.startswith("部门预算汇总表_") for name in names)
        assert any(name.startswith("运营组预算汇总表_") for name in names)
        assert any(name.startswith("店铺预算汇总表_") for name in names)
        assert any(name.startswith("产品品类预算汇总表_") for name in names)
        assert any(name.startswith("费用预算汇总表_") for name in names)
        assert any(name.startswith("错误定位总表_") for name in names)

        department_file = next(report_dir.glob("部门预算汇总表_*.xlsx"))
        workbook = load_workbook(department_file)
        assert {"部门预算总览", "部门月度趋势", "运营组汇总", "店铺汇总", "产品品类汇总", "费用汇总", "数据来源说明"}.issubset(
            set(workbook.sheetnames)
        )
        assert "授权信息" not in workbook.sheetnames

        error_file = next(check_dir.glob("错误定位总表_*.xlsx"))
        error_workbook = load_workbook(error_file)
        assert {"错误概览", "格式错误", "公式错误", "计算错误", "全部错误明细"}.issubset(set(error_workbook.sheetnames))
    finally:
        cleanup_test_client()


def test_export_empty_excel_report_does_not_crash(tmp_path):
    client, report_dir, _, _ = build_test_client(tmp_path)
    try:
        response = client.post("/api/export/excel", json={"report_type": "department", "year": 2030})

        assert response.status_code == 200
        assert response.json()["success"] is True
        workbook = load_workbook(next(report_dir.glob("部门预算汇总表_*.xlsx")))
        assert "部门预算总览" in workbook.sheetnames
    finally:
        cleanup_test_client()


def test_export_files_lists_reports_and_dashboards(tmp_path):
    client, _, _, _ = build_test_client(tmp_path)
    try:
        client.post("/api/export/excel", json={"report_type": "department", "year": 2026})
        client.post("/api/export/static-dashboard", json={"dashboard_type": "department", "year": 2026})
        client.post("/api/export/dashboard-view", json={"year": 2026, "budget_version": 1, "data_view": "budget"})

        response = client.get("/api/export/files")

        assert response.status_code == 200
        body = response.json()
        assert body["reports"]
        assert body["dashboards"]
        assert any("当前视角经营看板" in item["name"] for item in body["dashboards"])
    finally:
        cleanup_test_client()


def test_export_files_return_description_without_public_path_skip_deleted_and_open_location_is_restricted(tmp_path):
    client, report_dir, _, dashboard_dir = build_test_client(tmp_path)
    try:
        export_response = client.post("/api/export/excel", json={"report_type": "department", "year": 2026, "budget_version": 1})
        assert export_response.status_code == 200
        file_name = export_response.json()["files"][0]["name"]
        dashboard_response = client.post("/api/export/static-dashboard", json={"dashboard_type": "department", "year": 2026, "budget_version": 1})
        dashboard_name = dashboard_response.json()["files"][0]["name"]

        files_response = client.get("/api/export/files", params={"budget_version": 1})

        assert files_response.status_code == 200
        report = files_response.json()["reports"][0]
        assert report["name"] == file_name
        assert "description" in report
        assert "path" not in report
        assert report["budget_version"] == 1
        assert any(item["name"] == dashboard_name for item in files_response.json()["dashboards"])

        with patch("backend.utils.open_location.subprocess.run") as run_mock:
            open_response = client.post("/api/export/open-location", json={"name": file_name, "kind": "report"})

        assert open_response.status_code == 200
        assert open_response.json()["success"] is True
        run_mock.assert_called_once()

        blocked = client.post("/api/export/open-location", json={"name": "../../secret.xlsx", "kind": "report"})
        assert blocked.status_code == 400
        assert not any(path.name == "../../secret.xlsx" for path in report_dir.iterdir())

        (report_dir / file_name).unlink()
        shutil.rmtree(dashboard_dir / dashboard_name)
        refreshed = client.get("/api/export/files", params={"budget_version": 1}).json()
        assert all(item["name"] != file_name for item in refreshed["reports"])
        assert all(item["name"] != dashboard_name for item in refreshed["dashboards"])
    finally:
        cleanup_test_client()


def test_export_open_location_uses_windows_file_explorer(tmp_path):
    client, report_dir, _, _ = build_test_client(tmp_path)
    try:
        export_response = client.post("/api/export/excel", json={"report_type": "department", "year": 2026, "budget_version": 1})
        file_name = export_response.json()["files"][0]["name"]

        with patch("backend.utils.open_location.platform.system", return_value="Windows"):
            with patch("backend.utils.open_location.subprocess.run") as run_mock:
                response = client.post("/api/export/open-location", json={"name": file_name, "kind": "report"})

        assert response.status_code == 200
        run_mock.assert_called_once_with(["explorer", "/select,", str((report_dir / file_name).resolve())], check=False)
    finally:
        cleanup_test_client()


def test_export_dashboard_view_and_custom_template(tmp_path):
    client, report_dir, _, dashboard_dir = build_test_client(tmp_path)
    try:
        view_response = client.post(
            "/api/export/dashboard-view",
            json={"year": 2026, "budget_version": 1, "group_code": "G001", "shop_code": "S001", "data_view": "budget"},
        )
        assert view_response.status_code == 200
        view_name = view_response.json()["files"][0]["name"]
        assert view_name.startswith("当前视角经营看板_")
        assert "第1版" in view_name
        index_path = dashboard_dir / view_name / "index.html"
        assert index_path.exists()
        html = index_path.read_text(encoding="utf-8")
        assert "核心指标" in html
        assert "预算销售排名" in html
        assert "经营工作台经营看板" in html
        assert "授权客户" not in html
        dashboard_data = json.loads((index_path.parent / "data" / "dashboard-data.json").read_text(encoding="utf-8"))
        assert "license" not in dashboard_data

        custom_response = client.post(
            "/api/export/custom",
            json={"template": "product_sales_rank", "year": 2026, "budget_version": 1},
        )
        assert custom_response.status_code == 200
        custom_name = custom_response.json()["files"][0]["name"]
        assert custom_name.startswith("自定义导出_product_sales_rank_")
        custom_workbook = load_workbook(report_dir / custom_name)
        assert "产品销售排行榜" in custom_workbook.sheetnames
    finally:
        cleanup_test_client()


def test_dashboard_view_export_accepts_empty_filter_strings_from_frontend(tmp_path):
    client, _, _, dashboard_dir = build_test_client(tmp_path)
    try:
        response = client.post(
            "/api/export/dashboard-view",
            json={
                "year": "2026",
                "budget_version": "1",
                "month": "",
                "group_code": "",
                "shop_code": "",
                "product_name": "",
                "data_view": "comparison",
                "top_n": 10,
            },
        )

        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["files"][0]["name"].startswith("当前视角经营看板_")
        assert (dashboard_dir / body["files"][0]["name"] / "index.html").exists()
    finally:
        cleanup_test_client()
