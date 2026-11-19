from pathlib import Path

from fastapi.testclient import TestClient
from openpyxl import Workbook
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database.db import Base, get_db
from backend.database.models import ActualExpenseDetail, ActualImportBatch, ActualSalesDetail, ExpenseBudgetDetail, SalesBudgetDetail
from backend.main import app


def build_test_client(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'actual_test.db'}", connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    upload_dir = tmp_path / "upload"
    upload_dir.mkdir()

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    app.state.upload_dir_override = upload_dir
    return TestClient(app), TestingSessionLocal


def cleanup_test_client():
    app.dependency_overrides.clear()
    if hasattr(app.state, "upload_dir_override"):
        delattr(app.state, "upload_dir_override")


def create_actual_sales_workbook(path: Path):
    wb = Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    ws.append(["月份", "产品长代码", "产品名称", "单据编号", "单位", "发货仓库", "购货单位", "实发数量", "销售单价", "销售金额", "出厂价", "补贴点数", "店铺单位成本", "店铺成本金额", "店铺", "运营组"])
    ws.append([4, "P001", "测试产品", "D001", "袋", "测试仓库", "测试采购方", 10, 999, 1200, 0, 0, 999, 700, "测试商铺10", "测试运营组6"])
    ws.append([4, "P001", "测试产品", "D002", "袋", "测试仓库", "测试采购方", -2, 999, -240, 0, 0, 999, -140, "测试商铺10", "测试运营组6"])
    ws.append([4, "P002", "零数量产品", "D003", "袋", "测试仓库", "测试采购方", 0, 10, 0, 0, 0, 5, 0, "测试商铺10", "测试运营组6"])
    wb.save(path)


def create_actual_expense_workbook(path: Path):
    wb = Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    ws.append(["月份", "运营组", "店铺", "费用明细", "金额"])
    ws.append(["4月", "测试运营组6", "测试商铺10", "平台扣点", 100])
    ws.append(["4月", "测试运营组6", "测试商铺10", "平台扣点", 50])
    ws.append(["4月", "测试运营组6", "测试商铺10", 0, 0])
    wb.save(path)


def create_legacy_actual_expense_workbook(path: Path):
    wb = Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    ws.append(["月份", "运营组", "店铺", "事由", "金额"])
    ws.append(["4月", "测试运营组6", "测试商铺10", "平台扣点", 100])
    wb.save(path)


def upload(client, endpoint: str, path: Path, year=2026):
    with path.open("rb") as file_obj:
        response = client.post(
            endpoint,
            files={"file": (path.name, file_obj, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            data={"year": str(year)},
        )
    assert response.status_code == 200
    return response.json()["batch_id"]


def test_actual_sales_import_uses_trusted_amounts_and_calculates_unit_prices(tmp_path):
    client, db_factory = build_test_client(tmp_path)
    try:
        path = tmp_path / "实际销售.xlsx"
        create_actual_sales_workbook(path)
        batch_id = upload(client, "/api/actual/upload-sales", path)

        check = client.post(f"/api/actual/check/{batch_id}").json()
        assert check["error_count"] == 0
        assert check["warning_count"] >= 1

        imported = client.post(f"/api/actual/import/{batch_id}").json()
        assert imported["raw_rows"] == 3
        assert imported["detail_rows"] == 2
        with db_factory() as db:
            detail = db.query(ActualSalesDetail).filter(ActualSalesDetail.product_code == "P001").one()
            assert detail.actual_quantity == 8
            assert detail.actual_sales_amount == 960
            assert detail.actual_cost_amount == 560
            assert detail.actual_sales_unit_price == 120
            assert detail.actual_cost_unit_price == 70
    finally:
        cleanup_test_client()


def test_actual_expense_import_skips_zero_reason_and_aggregates_items(tmp_path):
    client, db_factory = build_test_client(tmp_path)
    try:
        path = tmp_path / "实际费用.xlsx"
        create_actual_expense_workbook(path)
        batch_id = upload(client, "/api/actual/upload-expense", path)

        assert client.post(f"/api/actual/check/{batch_id}").json()["error_count"] == 0
        imported = client.post(f"/api/actual/import/{batch_id}").json()
        assert imported["expense_rows"] == 2
        with db_factory() as db:
            assert db.query(ActualExpenseDetail).count() == 2
            assert sum(row.actual_expense_amount for row in db.query(ActualExpenseDetail).all()) == 150
            assert {row.expense_category for row in db.query(ActualExpenseDetail).all()} == {"营销费用"}
            assert db.query(ActualImportBatch).filter(ActualImportBatch.batch_id == batch_id).one().status == "imported"
    finally:
        cleanup_test_client()


def test_actual_expense_import_accepts_legacy_reason_header(tmp_path):
    client, db_factory = build_test_client(tmp_path)
    try:
        path = tmp_path / "旧实际费用.xlsx"
        create_legacy_actual_expense_workbook(path)
        batch_id = upload(client, "/api/actual/upload-expense", path)

        check = client.post(f"/api/actual/check/{batch_id}").json()
        assert check["error_count"] == 0
        imported = client.post(f"/api/actual/import/{batch_id}").json()
        assert imported["expense_rows"] == 1
        with db_factory() as db:
            detail = db.query(ActualExpenseDetail).one()
            assert detail.expense_item == "平台扣点"
    finally:
        cleanup_test_client()


def test_actual_check_results_endpoint_uses_expense_detail_label(tmp_path):
    client, _ = build_test_client(tmp_path)
    try:
        path = tmp_path / "实际费用缺字段.xlsx"
        wb = Workbook()
        ws = wb.active
        ws.append(["月份", "运营组", "店铺", "金额"])
        ws.append(["4月", "测试运营组6", "测试商铺10", 100])
        wb.save(path)
        batch_id = upload(client, "/api/actual/upload-expense", path)

        response = client.get(f"/api/actual/check-results/{batch_id}")
        assert response.status_code == 200
        issues = response.json()["issues"]
        assert any(issue["column_name"] == "费用明细" for issue in issues)
        assert any("费用明细" in issue["message"] for issue in issues)
    finally:
        cleanup_test_client()


def test_actual_check_does_not_downgrade_imported_batch_status(tmp_path):
    client, db_factory = build_test_client(tmp_path)
    try:
        path = tmp_path / "实际费用.xlsx"
        create_actual_expense_workbook(path)
        batch_id = upload(client, "/api/actual/upload-expense", path)

        assert client.post(f"/api/actual/import/{batch_id}").json()["status"] == "imported"
        checked = client.post(f"/api/actual/check/{batch_id}").json()
        assert checked["status"] == "imported"

        with db_factory() as db:
            assert db.query(ActualImportBatch).filter(ActualImportBatch.batch_id == batch_id).one().status == "imported"
    finally:
        cleanup_test_client()


def test_imported_actual_batch_delete_removes_imported_details(tmp_path):
    client, db_factory = build_test_client(tmp_path)
    try:
        path = tmp_path / "实际销售.xlsx"
        create_actual_sales_workbook(path)
        batch_id = upload(client, "/api/actual/upload-sales", path)
        assert client.post(f"/api/actual/import/{batch_id}").json()["status"] == "imported"

        deleted = client.delete(f"/api/actual/batches/{batch_id}")
        assert deleted.status_code == 200
        with db_factory() as db:
            assert db.query(ActualImportBatch).count() == 0
            assert db.query(ActualSalesDetail).count() == 0
    finally:
        cleanup_test_client()


def test_dashboard_overview_compares_budget_and_actual_for_product_shop_scope(tmp_path):
    client, db_factory = build_test_client(tmp_path)
    try:
        sales_path = tmp_path / "实际销售.xlsx"
        expense_path = tmp_path / "实际费用.xlsx"
        create_actual_sales_workbook(sales_path)
        create_actual_expense_workbook(expense_path)
        sales_batch = upload(client, "/api/actual/upload-sales", sales_path)
        expense_batch = upload(client, "/api/actual/upload-expense", expense_path)
        client.post(f"/api/actual/check/{sales_batch}")
        client.post(f"/api/actual/import/{sales_batch}")
        client.post(f"/api/actual/check/{expense_batch}")
        client.post(f"/api/actual/import/{expense_batch}")
        with db_factory() as db:
            db.add(
                SalesBudgetDetail(
                    year=2026,
                    month=4,
                    group_code="G001",
                    group_name="测试运营组6",
                    shop_code="S001",
                    shop_name="测试商铺10",
                    product_code="P001",
                    product_name="测试产品",
                    category="食品",
                    budget_quantity=10,
                    budget_sales_amount=1000,
                    budget_cost_amount=600,
                    budget_gross_profit=400,
                    budget_version=1,
                )
            )
            db.commit()

        overview = client.get(
            "/api/dashboard/overview",
            params={"year": 2026, "budget_version": 1, "month": 4, "shop_name": "测试商铺10", "product_code": "P001"},
        ).json()
        assert overview["view_mode"] == "product_month"
        assert overview["summary_cards"]["budget_sales_amount"] == 1000
        assert overview["summary_cards"]["actual_sales_amount"] == 960
        assert overview["summary_cards"]["sales_diff"] == -40
        assert overview["summary_cards"]["actual_profit_amount"] == 400
        assert overview["ranking_data"]
    finally:
        cleanup_test_client()


def test_dashboard_overview_filters_expenses_and_data_view_fields(tmp_path):
    client, db_factory = build_test_client(tmp_path)
    try:
        with db_factory() as db:
            db.add_all(
                [
                    SalesBudgetDetail(year=2026, month=1, group_code="G001", group_name="测试运营组6", shop_code="S001", shop_name="测试商铺10", product_code="P001", product_name="测试产品", budget_quantity=10, budget_sales_amount=1000, budget_cost_amount=500, budget_gross_profit=500, budget_version=1),
                    SalesBudgetDetail(year=2026, month=1, group_code="G002", group_name="测试运营组2", shop_code="S002", shop_name="测试平台店", product_code="P002", product_name="其他产品", budget_quantity=10, budget_sales_amount=2000, budget_cost_amount=1000, budget_gross_profit=1000, budget_version=1),
                    ExpenseBudgetDetail(year=2026, month=1, group_code="G001", shop_code="S001", expense_category="推广费", expense_item="达人佣金", budget_expense_amount=100, budget_version=1),
                    ExpenseBudgetDetail(year=2026, month=1, group_code="G002", shop_code="S002", expense_category="推广费", expense_item="直通车", budget_expense_amount=900, budget_version=1),
                    ActualSalesDetail(year=2026, month=1, group_name="测试运营组6", shop_name="测试商铺10", product_code="P001", product_name="测试产品", actual_quantity=8, actual_sales_amount=800, actual_cost_amount=400, actual_gross_profit=400, source_batch_id="b1"),
                    ActualExpenseDetail(year=2026, month=1, group_name="测试运营组6", shop_name="测试商铺10", expense_category="推广费", expense_item="达人佣金", actual_expense_amount=120, source_batch_id="b2"),
                    ActualExpenseDetail(year=2026, month=1, group_name="测试运营组2", shop_name="测试平台店", expense_category="推广费", expense_item="直通车", actual_expense_amount=800, source_batch_id="b3"),
                ]
            )
            db.commit()

        group_view = client.get("/api/dashboard/overview", params={"year": 2026, "budget_version": 1, "month": 1, "group_name": "测试运营组6", "data_view": "comparison"}).json()
        assert group_view["summary_cards"]["budget_expense_amount"] == 100
        assert group_view["summary_cards"]["actual_expense_amount"] == 120
        assert group_view["summary_cards"]["expense_diff"] == 20

        budget_view = client.get("/api/dashboard/overview", params={"year": 2026, "budget_version": 1, "month": 1, "group_name": "测试运营组6", "data_view": "budget"}).json()
        assert "sales_diff" not in budget_view["summary_cards"]
        assert "actual_sales_amount" not in budget_view["summary_cards"]
        assert budget_view["summary_cards"]["budget_sales_amount"] == 1000

        actual_view = client.get("/api/dashboard/overview", params={"year": 2026, "budget_version": 1, "month": 1, "group_name": "测试运营组6", "data_view": "actual"}).json()
        assert "sales_diff" not in actual_view["summary_cards"]
        assert "budget_sales_amount" not in actual_view["summary_cards"]
        assert actual_view["summary_cards"]["actual_sales_amount"] == 800
    finally:
        cleanup_test_client()


def test_dashboard_expense_tables_keep_actual_only_expense_detail(tmp_path):
    client, db_factory = build_test_client(tmp_path)
    try:
        with db_factory() as db:
            db.add_all(
                [
                    ExpenseBudgetDetail(year=2026, month=1, group_code="G001", shop_code="S001", expense_category="营销费用", expense_item="达人佣金", budget_expense_amount=100, budget_version=1),
                    ExpenseBudgetDetail(year=2026, month=1, group_code="G001", shop_code="S001", expense_category="管理费", expense_item="公司管理费用", budget_expense_amount=300, budget_version=1),
                    ActualExpenseDetail(year=2026, month=1, group_name="测试运营组6", shop_name="测试商铺10", expense_category="未分类实际费用", expense_item="公司管理费用", actual_expense_amount=120, source_batch_id="b1"),
                    ActualExpenseDetail(year=2026, month=1, group_name="测试运营组6", shop_name="测试商铺10", expense_category="营销费用", expense_item="达人佣金", actual_expense_amount=80, source_batch_id="b1"),
                ]
            )
            db.commit()

        overview = client.get("/api/dashboard/overview", params={"year": 2026, "budget_version": 1, "month": 1, "data_view": "comparison"}).json()
        expense_overrun = next(section for section in overview["ranking_sections"] if section["id"] == "expense_overrun")
        expense_detail = next(section for section in overview["table_sections"] if section["id"] == "expense_category_detail")

        assert any(row["expense_item"] == "公司管理费用" for row in expense_overrun["rows"])
        assert any(row["expense_item"] == "公司管理费用" for row in expense_detail["rows"])
        actual_only_row = next(row for row in expense_detail["rows"] if row["expense_item"] == "公司管理费用")
        assert actual_only_row["expense_category"] == "管理费"
        assert actual_only_row["budget_expense_amount"] == 300
        assert actual_only_row["actual_expense_amount"] == 120
        assert not any(row["expense_item"] == "未分类实际费用" for row in expense_overrun["rows"])
        assert not any(row["expense_item"] == "未分类实际费用" for row in expense_detail["rows"])
    finally:
        cleanup_test_client()


def test_dashboard_overview_profit_trend_product_options_and_completion_rates(tmp_path):
    client, db_factory = build_test_client(tmp_path)
    try:
        with db_factory() as db:
            db.add_all(
                [
                    SalesBudgetDetail(year=2026, month=1, group_code="G001", group_name="测试运营组6", shop_code="S001", shop_name="测试商铺10", product_code="P001", product_name="测试产品", budget_quantity=10, budget_sales_amount=1000, budget_cost_amount=500, budget_gross_profit=500, budget_version=1),
                    SalesBudgetDetail(year=2026, month=2, group_code="G001", group_name="测试运营组6", shop_code="S001", shop_name="测试商铺10", product_code="P001", product_name="测试产品", budget_quantity=10, budget_sales_amount=1000, budget_cost_amount=500, budget_gross_profit=500, budget_version=1),
                    ExpenseBudgetDetail(year=2026, month=1, group_code="G001", shop_code="S001", expense_category="推广费", expense_item="达人佣金", budget_expense_amount=700, budget_version=1),
                    ExpenseBudgetDetail(year=2026, month=2, group_code="G001", shop_code="S001", expense_category="推广费", expense_item="达人佣金", budget_expense_amount=100, budget_version=1),
                    ActualSalesDetail(year=2026, month=1, group_name="测试运营组6", shop_name="测试商铺10", product_code="P001", product_name="测试产品", actual_quantity=8, actual_sales_amount=800, actual_cost_amount=400, actual_gross_profit=400, source_batch_id="b1"),
                    ActualSalesDetail(year=2026, month=2, group_name="测试运营组6", shop_name="测试商铺10", product_code="P001", product_name="测试产品", actual_quantity=4, actual_sales_amount=400, actual_cost_amount=200, actual_gross_profit=200, source_batch_id="b1"),
                ]
            )
            db.commit()

        overview = client.get("/api/dashboard/overview", params={"year": 2026, "budget_version": 1, "group_name": "测试运营组6", "data_view": "comparison"}).json()
        profit_trend = next(section for section in overview["trend_sections"] if section["id"] == "profit_comparison_trend")
        month_one = next(row for row in profit_trend["rows"] if row["month"] == 1)
        assert month_one["budget_profit_amount"] == -200
        assert overview["summary_cards"]["annual_sales_completion_rate"] == 0.6
        assert overview["summary_cards"]["same_period_sales_completion_rate"] == 0.6
        assert overview["table_sections"][0]["rows"][0]["annual_completion_rate"] == 0.6
        assert overview["table_sections"][0]["rows"][0]["same_period_completion_rate"] == 0.6
        assert any(item["product_name"] == "测试产品" for item in overview["filter_options"]["products"])
        assert overview["actual_coverage"]["months"] == [1, 2]
        assert overview["actual_coverage"]["month_label"] == "1-2月"
        assert overview["actual_coverage"]["group_count"] == 1
        assert overview["actual_coverage"]["shop_count"] == 1
        assert any(section["id"] == "expense_category_detail" for section in overview["table_sections"])
    finally:
        cleanup_test_client()


def test_dashboard_comparison_uses_actual_covered_months_for_budget_baseline(tmp_path):
    client, db_factory = build_test_client(tmp_path)
    try:
        with db_factory() as db:
            db.add_all(
                [
                    SalesBudgetDetail(year=2026, month=1, group_code="G001", group_name="测试运营组6", shop_code="S001", shop_name="测试商铺10", product_code="P001", product_name="产品A", budget_quantity=10, budget_sales_amount=1000, budget_cost_amount=500, budget_gross_profit=500, budget_version=1),
                    SalesBudgetDetail(year=2026, month=2, group_code="G001", group_name="测试运营组6", shop_code="S001", shop_name="测试商铺10", product_code="P001", product_name="产品A", budget_quantity=10, budget_sales_amount=1000, budget_cost_amount=500, budget_gross_profit=500, budget_version=1),
                    SalesBudgetDetail(year=2026, month=3, group_code="G001", group_name="测试运营组6", shop_code="S001", shop_name="测试商铺10", product_code="P001", product_name="产品A", budget_quantity=10, budget_sales_amount=1000, budget_cost_amount=500, budget_gross_profit=500, budget_version=1),
                    ActualSalesDetail(year=2026, month=1, group_name="测试运营组6", shop_name="测试商铺10", product_code="P001", product_name="产品A", actual_quantity=8, actual_sales_amount=800, actual_cost_amount=400, actual_gross_profit=400, source_batch_id="b1"),
                ]
            )
            db.commit()

        overview = client.get("/api/dashboard/overview", params={"year": 2026, "budget_version": 1, "data_view": "comparison"}).json()
        assert overview["summary_cards"]["budget_sales_amount"] == 1000
        assert overview["summary_cards"]["actual_sales_amount"] == 800
        assert overview["summary_cards"]["sales_completion_rate"] == 0.8
        assert overview["summary_cards"]["annual_sales_completion_rate"] == 0.266667
        assert overview["summary_cards"]["same_period_sales_completion_rate"] == 0.8
        sales_trend = next(section for section in overview["trend_sections"] if section["id"] == "sales_comparison_trend")
        month_two = next(row for row in sales_trend["rows"] if row["month"] == 2)
        assert month_two["actual_sales_amount"] is None
        assert month_two["actual_sales_pending_amount"] == 0
    finally:
        cleanup_test_client()


def test_actual_upload_accepts_metadata_and_unimported_delete(tmp_path):
    client, db_factory = build_test_client(tmp_path)
    try:
        registry = tmp_path / "shop_registry.json"
        registry.write_text('{"operation_groups":[{"group_code":"G001","group_name":"测试运营组6","status":"active","shops":[{"shop_code":"S001","shop_name":"测试商铺10","status":"active"}]}]}', encoding="utf-8")
        from backend.main import app

        app.state.shop_registry_path_override = registry
        path = tmp_path / "实际销售.xlsx"
        create_actual_sales_workbook(path)
        with path.open("rb") as file_obj:
            response = client.post(
                "/api/actual/upload-sales",
                files={"file": (path.name, file_obj, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
                data={"year": "2026", "group_code": "G001", "shop_code": "S001"},
            )
        assert response.status_code == 200
        body = response.json()
        assert body["group_name"] == "测试运营组6"
        assert body["shop_name"] == "测试商铺10"
        deleted = client.delete(f"/api/actual/batches/{body['batch_id']}")
        assert deleted.status_code == 200
        with db_factory() as db:
            assert db.query(ActualImportBatch).count() == 0
    finally:
        if hasattr(app.state, "shop_registry_path_override"):
            delattr(app.state, "shop_registry_path_override")
        cleanup_test_client()
