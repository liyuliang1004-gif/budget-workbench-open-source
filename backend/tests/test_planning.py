import json
from io import BytesIO
from unittest.mock import patch

from openpyxl import load_workbook
from openpyxl import Workbook
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database.db import Base, get_db
from backend.database.models import ActualExpenseDetail, ActualSalesDetail, BudgetPrice, SalesBudgetDetail
from backend.main import app


def build_test_client(tmp_path, seed=True, registry=None):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'planning_test.db'}",
        connect_args={"check_same_thread": False},
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    planning_dir = tmp_path / "planning"
    registry_path = tmp_path / "shop_registry.json"
    planning_dir.mkdir()
    if registry is not None:
        registry_path.write_text(json.dumps(registry, ensure_ascii=False), encoding="utf-8")

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    app.state.planning_report_dir_override = planning_dir
    if registry is not None:
        app.state.shop_registry_path_override = registry_path
    if seed:
        seed_actual_data(TestingSessionLocal)
    return TestClient(app), planning_dir, TestingSessionLocal


def cleanup_test_client():
    app.dependency_overrides.clear()
    if hasattr(app.state, "planning_report_dir_override"):
        delattr(app.state, "planning_report_dir_override")
    if hasattr(app.state, "shop_registry_path_override"):
        delattr(app.state, "shop_registry_path_override")


def seed_actual_data(db_factory):
    with db_factory() as db:
        db.add_all(
            [
                ActualSalesDetail(
                    year=2026,
                    month=1,
                    group_name="测试运营组6",
                    shop_name="测试商铺10",
                    product_code="P001",
                    product_name="A产品",
                    category="肉制品",
                    actual_quantity=80,
                    actual_sales_amount=800,
                    actual_cost_amount=400,
                    actual_gross_profit=400,
                    actual_sales_unit_price=10,
                    actual_cost_unit_price=5,
                    source_batch_id="sales-1",
                ),
                ActualSalesDetail(
                    year=2026,
                    month=1,
                    group_name="测试运营组6",
                    shop_name="测试商铺10",
                    product_code="P002",
                    product_name="B产品",
                    category="肉制品",
                    actual_quantity=10,
                    actual_sales_amount=200,
                    actual_cost_amount=120,
                    actual_gross_profit=80,
                    actual_sales_unit_price=20,
                    actual_cost_unit_price=12,
                    source_batch_id="sales-1",
                ),
                ActualSalesDetail(
                    year=2026,
                    month=2,
                    group_name="测试运营组6",
                    shop_name="测试商铺10",
                    product_code="P001",
                    product_name="A产品",
                    category="肉制品",
                    actual_quantity=10,
                    actual_sales_amount=100,
                    actual_cost_amount=50,
                    actual_gross_profit=50,
                    actual_sales_unit_price=10,
                    actual_cost_unit_price=5,
                    source_batch_id="sales-1",
                ),
                ActualSalesDetail(
                    year=2026,
                    month=2,
                    group_name="测试运营组6",
                    shop_name="测试商铺10",
                    product_code="P002",
                    product_name="B产品",
                    category="肉制品",
                    actual_quantity=45,
                    actual_sales_amount=900,
                    actual_cost_amount=540,
                    actual_gross_profit=360,
                    actual_sales_unit_price=20,
                    actual_cost_unit_price=12,
                    source_batch_id="sales-1",
                ),
                ActualExpenseDetail(
                    year=2026,
                    month=1,
                    group_name="测试运营组6",
                    shop_name="测试商铺10",
                    expense_category="营销费用",
                    expense_item="达人佣金",
                    actual_expense_amount=100,
                    source_batch_id="expense-1",
                ),
                ActualExpenseDetail(
                    year=2026,
                    month=2,
                    group_name="测试运营组6",
                    shop_name="测试商铺10",
                    expense_category="平台费用",
                    expense_item="平台扣点",
                    actual_expense_amount=220,
                    source_batch_id="expense-1",
                ),
            ]
        )
        db.commit()


def test_planning_export_generates_shop_budget_workbook_with_formulas(tmp_path):
    client, planning_dir, _ = build_test_client(tmp_path)
    try:
        response = client.post(
            "/api/planning/export",
            json={
                "reference_year": 2026,
                "target_year": 2027,
                "group_name": "测试运营组6",
                "shop_name": "测试商铺10",
                "target_sales_amount": 2400,
                "sales_price_adjustment_rate": 0.1,
                "cost_price_adjustment_rate": -0.05,
            },
        )

        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["files"][0]["name"].startswith("2027年预算编制_测试商铺10")

        workbook = load_workbook(planning_dir / body["files"][0]["name"], data_only=False)
        assert {
            "任务分解-金额",
            "任务分解-数量",
            "任务分解-成本",
            "费用预算",
            "利润分解表",
            "预算编制参数",
            "产品预算调整",
            "费用预算调整",
            "校验汇总",
        }.issubset(set(workbook.sheetnames))

        product_adjust = workbook["产品预算调整"]
        assert product_adjust["F2"].value == 0.8
        assert product_adjust["F4"].value == 0.1
        assert product_adjust["H2"].value == "=IF(G2=\"\",F2,G2)"
        assert product_adjust["I2"].value.startswith("='预算编制参数'!")
        assert product_adjust["M2"].value == "=IF(L2=0,0,I2/L2)"
        assert product_adjust["Q2"].value == "=M2*P2"

        expense_adjust = workbook["费用预算调整"]
        assert expense_adjust["F2"].value == 0.1
        assert expense_adjust["H2"].value == "=IF(G2=\"\",F2,G2)"
        assert expense_adjust["I2"].value.startswith("='预算编制参数'!")

        amount_sheet = workbook["任务分解-金额"]
        quantity_sheet = workbook["任务分解-数量"]
        cost_sheet = workbook["任务分解-成本"]
        expense_sheet = workbook["费用预算"]
        profit_sheet = workbook["利润分解表"]
        assert "SUMIFS('产品预算调整'!" in amount_sheet["C2"].value
        assert "SUMIFS('产品预算调整'!" in quantity_sheet["C2"].value
        assert "SUMIFS('产品预算调整'!" in cost_sheet["C2"].value
        assert "SUMIFS('费用预算调整'!" in expense_sheet["C2"].value
        assert profit_sheet["C4"].value == "=C2-C3-SUM('费用预算'!C2:C200)"
    finally:
        cleanup_test_client()


def test_planning_options_include_maintained_groups_and_shops_without_detail_data(tmp_path):
    registry = {
        "operation_groups": [
            {
                "group_code": "G100",
                "group_name": "测试运营组2",
                "status": "active",
                "shops": [
                    {"shop_code": "S100", "shop_name": "测试商铺2", "status": "active"},
                    {"shop_code": "S101", "shop_name": "测试商铺3店", "status": "active"},
                ],
            }
        ]
    }
    client, _, _ = build_test_client(tmp_path, seed=False, registry=registry)
    try:
        response = client.get("/api/planning/options", params={"reference_year": 2026})

        assert response.status_code == 200
        body = response.json()
        assert body["groups"] == [{"group_code": "G100", "group_name": "测试运营组2"}]
        assert {"shop_code": "S100", "shop_name": "测试商铺2", "group_name": "测试运营组2"} in body["shops"]
        assert {"shop_code": "S101", "shop_name": "测试商铺3店", "group_name": "测试运营组2"} in body["shops"]
    finally:
        cleanup_test_client()


def create_price_workbook(path, header, value):
    wb = Workbook()
    ws = wb.active
    ws.append(["产品编码", "产品名称", header])
    ws.append(["P001", "A产品", value])
    ws.append(["P002", "B产品", value * 2])
    wb.save(path)


def test_uploaded_sales_and_cost_prices_are_used_only_when_selected(tmp_path):
    client, planning_dir, db_factory = build_test_client(tmp_path)
    sales_price_path = tmp_path / "销售价格表.xlsx"
    cost_price_path = tmp_path / "产品成本表.xlsx"
    create_price_workbook(sales_price_path, "销售价", 15)
    create_price_workbook(cost_price_path, "成本价", 7)
    try:
        with sales_price_path.open("rb") as file_obj:
            sales_response = client.post(
                "/api/planning/upload-sales-prices",
                files={"file": (sales_price_path.name, file_obj, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
                data={"year": "2027"},
            )
        with cost_price_path.open("rb") as file_obj:
            cost_response = client.post(
                "/api/planning/upload-cost-prices",
                files={"file": (cost_price_path.name, file_obj, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
                data={"year": "2027"},
            )

        assert sales_response.status_code == 200
        assert cost_response.status_code == 200
        assert sales_response.json()["imported_count"] == 2
        assert cost_response.json()["imported_count"] == 2
        with db_factory() as db:
            price = db.query(BudgetPrice).filter(BudgetPrice.year == 2027, BudgetPrice.product_code == "P001").one()
            assert price.average_price == 15
            assert price.cost_price == 7

        export_response = client.post(
            "/api/planning/export",
            json={
                "reference_year": 2026,
                "target_year": 2027,
                "group_name": "测试运营组6",
                "shop_name": "测试商铺10",
                "target_sales_amount": 2400,
                "sales_price_source": "actual",
                "cost_price_source": "actual",
            },
        )
        workbook = load_workbook(planning_dir / export_response.json()["files"][0]["name"], data_only=False)
        product_adjust = workbook["产品预算调整"]
        assert product_adjust["J2"].value == 10
        assert product_adjust["N2"].value == 5

        selected_response = client.post(
            "/api/planning/export",
            json={
                "reference_year": 2026,
                "target_year": 2027,
                "group_name": "测试运营组6",
                "shop_name": "测试商铺10",
                "target_sales_amount": 2400,
                "sales_price_source": "uploaded",
                "cost_price_source": "uploaded",
            },
        )
        selected_workbook = load_workbook(planning_dir / selected_response.json()["files"][0]["name"], data_only=False)
        product_adjust = selected_workbook["产品预算调整"]
        assert product_adjust["J2"].value == 15
        assert product_adjust["N2"].value == 7
    finally:
        cleanup_test_client()


def test_planning_export_can_reference_budget_prices(tmp_path):
    client, planning_dir, db_factory = build_test_client(tmp_path)
    with db_factory() as db:
        db.add(
            SalesBudgetDetail(
                year=2026,
                month=1,
                budget_version=1,
                group_code="G001",
                group_name="测试运营组6",
                shop_code="S001",
                shop_name="测试商铺10",
                product_code="P001",
                product_name="A产品",
                category="肉制品",
                budget_sales_amount=1800,
                budget_quantity=100,
                budget_cost_amount=900,
                average_price=18,
                cost_price=9,
                source_file_id=1,
            )
        )
        db.commit()
    try:
        response = client.post(
            "/api/planning/export",
            json={
                "reference_year": 2026,
                "target_year": 2027,
                "group_name": "测试运营组6",
                "shop_name": "测试商铺10",
                "target_sales_amount": 2400,
                "sales_price_source": "budget",
                "cost_price_source": "budget",
            },
        )

        assert response.status_code == 200
        workbook = load_workbook(planning_dir / response.json()["files"][0]["name"], data_only=False)
        product_adjust = workbook["产品预算调整"]
        assert product_adjust["J2"].value == 18
        assert product_adjust["N2"].value == 9
    finally:
        cleanup_test_client()


def test_planning_export_blocks_uploaded_price_source_without_uploaded_prices(tmp_path):
    client, _, _ = build_test_client(tmp_path)
    try:
        response = client.post(
            "/api/planning/export",
            json={
                "reference_year": 2026,
                "target_year": 2028,
                "group_name": "测试运营组6",
                "shop_name": "测试商铺10",
                "target_sales_amount": 2400,
                "sales_price_source": "uploaded",
                "cost_price_source": "uploaded",
            },
        )

        assert response.status_code == 400
        assert "未上传销售价表" in response.json()["detail"]
        assert "未上传成本价表" in response.json()["detail"]
    finally:
        cleanup_test_client()


def test_planning_result_can_open_file_location(tmp_path):
    client, _, _ = build_test_client(tmp_path)
    try:
        export_response = client.post(
            "/api/planning/export",
            json={
                "reference_year": 2026,
                "target_year": 2027,
                "group_name": "测试运营组6",
                "shop_name": "测试商铺10",
                "target_sales_amount": 2400,
            },
        )
        file_name = export_response.json()["files"][0]["name"]

        with patch("backend.utils.open_location.subprocess.run") as mocked_run:
            open_response = client.post("/api/planning/open-location", json={"name": file_name})

        assert open_response.status_code == 200
        assert open_response.json()["name"] == file_name
        mocked_run.assert_called_once()

        blocked = client.post("/api/planning/open-location", json={"name": "../../secret.xlsx"})
        assert blocked.status_code == 400
    finally:
        cleanup_test_client()


def test_planning_open_location_uses_windows_file_explorer(tmp_path):
    client, planning_dir, _ = build_test_client(tmp_path)
    try:
        export_response = client.post(
            "/api/planning/export",
            json={
                "reference_year": 2026,
                "target_year": 2027,
                "group_name": "测试运营组6",
                "shop_name": "测试商铺10",
                "target_sales_amount": 2400,
            },
        )
        file_name = export_response.json()["files"][0]["name"]

        with patch("backend.utils.open_location.platform.system", return_value="Windows"):
            with patch("backend.utils.open_location.subprocess.run") as mocked_run:
                response = client.post("/api/planning/open-location", json={"name": file_name})

        assert response.status_code == 200
        mocked_run.assert_called_once_with(["explorer", "/select,", str((planning_dir / file_name).resolve())], check=False)
    finally:
        cleanup_test_client()


def test_planning_generated_files_list_only_existing_workbooks(tmp_path):
    client, planning_dir, _ = build_test_client(tmp_path)
    try:
        export_response = client.post(
            "/api/planning/export",
            json={
                "reference_year": 2026,
                "target_year": 2027,
                "group_name": "测试运营组6",
                "shop_name": "测试商铺10",
                "target_sales_amount": 2400,
            },
        )
        file_name = export_response.json()["files"][0]["name"]

        list_response = client.get("/api/planning/files")
        assert list_response.status_code == 200
        assert [item["name"] for item in list_response.json()["files"]] == [file_name]

        (planning_dir / file_name).unlink()
        after_delete = client.get("/api/planning/files")
        assert after_delete.status_code == 200
        assert after_delete.json()["files"] == []
    finally:
        cleanup_test_client()


def test_actual_business_templates_can_be_downloaded(tmp_path):
    client, _, _ = build_test_client(tmp_path, seed=False)
    try:
        sales_response = client.get("/api/templates/actual-sales")
        expense_response = client.get("/api/templates/actual-expense")
        business_response = client.get("/api/templates/actual-business")

        assert sales_response.status_code == 200
        sales_wb = load_workbook(BytesIO(sales_response.content), read_only=True)
        sales_headers = [cell.value for cell in next(sales_wb.active.iter_rows(max_row=1))]
        assert {"月份", "产品名称", "实发数量", "销售金额", "店铺成本金额"}.issubset(set(sales_headers))

        assert expense_response.status_code == 200
        expense_wb = load_workbook(BytesIO(expense_response.content), read_only=True)
        expense_headers = [cell.value for cell in next(expense_wb.active.iter_rows(max_row=1))]
        assert ["月份", "运营组", "店铺", "费用明细", "金额"] == expense_headers[:5]

        assert business_response.status_code == 200
        business_wb = load_workbook(BytesIO(business_response.content), read_only=True)
        assert {"实际销售模板", "实际费用模板"}.issubset(set(business_wb.sheetnames))
        combined_sales_headers = [cell.value for cell in next(business_wb["实际销售模板"].iter_rows(max_row=1))]
        combined_expense_headers = [cell.value for cell in next(business_wb["实际费用模板"].iter_rows(max_row=1))]
        assert {"月份", "产品名称", "实发数量", "销售金额", "店铺成本金额"}.issubset(set(combined_sales_headers))
        assert ["月份", "运营组", "店铺", "费用明细", "金额"] == combined_expense_headers[:5]
    finally:
        cleanup_test_client()


def test_planning_price_table_check_reports_missing_columns(tmp_path):
    client, _, _ = build_test_client(tmp_path, seed=False)
    try:
        workbook = Workbook()
        sheet = workbook.active
        sheet.append(["产品名称", "备注"])
        sheet.append(["A产品", "缺销售价"])
        buffer = BytesIO()
        workbook.save(buffer)
        buffer.seek(0)

        response = client.post(
            "/api/planning/check-sales-prices",
            files={"file": ("销售价格表.xlsx", buffer, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            data={"year": "2027"},
        )

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "failed"
        assert body["error_count"] >= 1
        assert any("销售价列" in issue["message"] for issue in body["issues"])
    finally:
        cleanup_test_client()
