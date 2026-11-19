from openpyxl import Workbook
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database.db import Base, get_db
from backend.main import app


def build_test_client(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'calculation_test.db'}",
        connect_args={"check_same_thread": False},
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    upload_dir = tmp_path / "upload"
    report_dir = tmp_path / "reports"
    registry_path = tmp_path / "shop_registry.json"
    upload_dir.mkdir()
    report_dir.mkdir()
    registry_path.write_text(
        '{"operation_groups":[{"group_code":"G001","group_name":"示例运营组","status":"active","shops":[{"shop_code":"S001","shop_name":"示例店铺","status":"active"}]}]}',
        encoding="utf-8",
    )

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    app.state.upload_dir_override = upload_dir
    app.state.report_dir_override = report_dir
    app.state.shop_registry_path_override = registry_path
    return TestClient(app), report_dir


def cleanup_test_client():
    app.dependency_overrides.clear()
    if hasattr(app.state, "upload_dir_override"):
        delattr(app.state, "upload_dir_override")
    if hasattr(app.state, "report_dir_override"):
        delattr(app.state, "report_dir_override")
    if hasattr(app.state, "shop_registry_path_override"):
        delattr(app.state, "shop_registry_path_override")


def create_calculation_workbook(path):
    wb = Workbook()
    wb.remove(wb.active)
    month_headers = [f"{month}月" for month in range(1, 13)]

    ws = wb.create_sheet("任务分解-数量")
    ws.append(["产品编码", "品类", "产品名称", "平均销售单价"] + month_headers)
    ws.append(["P001", "食品", "测试产品", 10] + [10] * 12)

    ws = wb.create_sheet("任务分解-金额")
    ws.append(["产品编码", "品类", "产品名称"] + month_headers + ["年度合计"])
    ws.append(["P001", "食品", "测试产品", 99] + [100] * 11 + [1000])

    ws = wb.create_sheet("任务分解-成本")
    ws.append(["产品编码", "品类", "产品名称", "成本价"] + month_headers + ["年度合计"])
    ws.append(["P001", "食品", "测试产品", 6, 50] + [60] * 11 + [720])

    ws = wb.create_sheet("费用预算")
    ws.append(["预算项目", "预算小项"] + month_headers + ["年度合计"])
    ws.append([None, "投流", 20] + [20] * 11 + [240])
    ws.append(["推广费", "投流", "abc"] + [0] * 11 + [0])

    ws = wb.create_sheet("利润分解表")
    ws.append(["项目"] + month_headers + ["年度合计"])
    ws.append(["利润", 999] + [20] * 11 + [1220])
    ws.append(["利润率", "#DIV/0!"] + [0.2] * 11 + [0.2])

    ws = wb.create_sheet("预算价格表")
    ws.append(["产品编码", "品类", "产品名称", "统一出厂价", "补贴标准", "补贴后价格"])
    ws.append(["P001", "食品", "测试产品", 10, 1, 9])
    wb.save(path)


def upload_workbook(client, path):
    with path.open("rb") as file_obj:
        response = client.post(
            "/api/upload/budget",
            files={
                "file": (
                    path.name,
                    file_obj,
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            },
            data={"budget_year": "2026", "budget_version": "1", "group_code": "G001", "shop_code": "S001"},
        )
    assert response.status_code == 200
    return response.json()["id"]


def test_calculation_check_records_mismatches_and_updates_status(tmp_path):
    client, _ = build_test_client(tmp_path)
    try:
        workbook_path = tmp_path / "计算错误.xlsx"
        create_calculation_workbook(workbook_path)
        file_id = upload_workbook(client, workbook_path)

        response = client.post(f"/api/check/calculation/{file_id}")

        assert response.status_code == 200
        body = response.json()
        assert body["check_type"] == "calculation"
        assert body["error_count"] >= 6

        results = client.get(f"/api/check/results/{file_id}", params={"check_type": "calculation"}).json()
        error_codes = {item["error_code"] for item in results}
        assert "sales_amount_mismatch" not in error_codes
        assert "cost_amount_mismatch" in error_codes
        assert "expense_item_missing" in error_codes
        assert "expense_amount_not_number" in error_codes
        assert "profit_amount_mismatch" in error_codes
        assert "yearly_total_mismatch" in error_codes
        assert "rate_div_zero_error" in error_codes

        files = client.get("/api/upload/files").json()
        uploaded_file = next(item for item in files if item["id"] == file_id)
        assert uploaded_file["check_status"] == "检查失败"
        assert uploaded_file["error_count"] == body["error_count"]
    finally:
        cleanup_test_client()


def create_zero_sales_rate_workbook(path):
    wb = Workbook()
    wb.remove(wb.active)
    month_headers = [f"{month}月" for month in range(1, 13)]

    ws = wb.create_sheet("任务分解-数量")
    ws.append(["产品编码", "品类", "产品名称", "平均销售单价"] + month_headers)
    ws.append(["P001", "食品", "测试产品", 10] + [0] * 12)

    ws = wb.create_sheet("任务分解-金额")
    ws.append(["产品编码", "品类", "产品名称"] + month_headers)
    ws.append(["P001", "食品", "测试产品"] + [0] * 12)

    ws = wb.create_sheet("任务分解-成本")
    ws.append(["产品编码", "品类", "产品名称", "成本价"] + month_headers)
    ws.append(["P001", "食品", "测试产品", 6] + [0] * 12)

    ws = wb.create_sheet("费用预算")
    ws.append(["预算项目", "预算小项"] + month_headers)
    ws.append(["推广费", "投流"] + [0] * 12)

    ws = wb.create_sheet("利润分解表")
    ws.append(["项目"] + month_headers)
    ws.append(["利润"] + [0] * 12)
    ws.append(["利润率", "#DIV/0!"] + [0] * 11)

    ws = wb.create_sheet("预算价格表")
    ws.append(["产品编码", "品类", "产品名称", "统一出厂价", "补贴标准", "补贴后价格"])
    ws.append(["P001", "食品", "测试产品", 10, 0, 6])
    wb.save(path)


def test_zero_sales_div_zero_is_warning_and_does_not_block_import(tmp_path):
    client, _ = build_test_client(tmp_path)
    try:
        workbook_path = tmp_path / "G001_S001_2026_零销售.xlsx"
        create_zero_sales_rate_workbook(workbook_path)
        file_id = upload_workbook(client, workbook_path)

        response = client.post(f"/api/check/calculation/{file_id}")

        assert response.status_code == 200
        body = response.json()
        assert body["error_count"] == 0
        assert body["warning_count"] == 1
        assert body["check_status"] == "检查警告"
        results = client.get(f"/api/check/results/{file_id}", params={"check_type": "calculation"}).json()
        assert results[0]["error_code"] == "rate_div_zero_reminder"
        assert results[0]["severity"] == "warning"
        assert "不阻止入库" in results[0]["suggestion"]
    finally:
        cleanup_test_client()


def test_full_check_and_export_calculation_error_reports(tmp_path):
    client, report_dir = build_test_client(tmp_path)
    try:
        workbook_path = tmp_path / "全量检查.xlsx"
        create_calculation_workbook(workbook_path)
        file_id = upload_workbook(client, workbook_path)

        response = client.post(f"/api/check/full/{file_id}")

        assert response.status_code == 200
        assert response.json()["file_id"] == file_id

        calculation_report = client.post("/api/check/export-calculation-report")
        error_report = client.post("/api/check/export-error-report")

        assert calculation_report.status_code == 200
        assert error_report.status_code == 200
        names = {path.name for path in report_dir.iterdir()}
        assert any(name.startswith("计算结果校验报告_") for name in names)
        assert any(name.startswith("错误定位总表_") for name in names)
    finally:
        cleanup_test_client()


def create_formula_workbook(path):
    wb = Workbook()
    wb.remove(wb.active)
    month_headers = [f"{month}月" for month in range(1, 13)]

    ws = wb.create_sheet("任务分解-数量")
    ws.append(["产品编码", "品类", "产品名称", "平均销售单价"] + month_headers)
    ws.append(["P001", "食品", "测试产品", 10] + [100] * 12)

    ws = wb.create_sheet("任务分解-金额")
    ws.append(["产品编码", "品类", "产品名称"] + month_headers)
    ws.append(["P001", "食品", "测试产品"] + [f"='任务分解-数量'!{chr(68 + index)}2*'任务分解-数量'!D2" for index in range(12)])

    ws = wb.create_sheet("任务分解-成本")
    ws.append(["产品编码", "品类", "产品名称", "成本价"] + month_headers)
    ws.append(["P001", "食品", "测试产品", 6] + [f"='任务分解-数量'!{chr(68 + index)}2*D2" for index in range(12)])

    ws = wb.create_sheet("费用预算")
    ws.append(["预算项目", "预算小项"] + month_headers)
    ws.append(["推广费", "投流", *([100] * 12)])

    ws = wb.create_sheet("利润分解表")
    ws.append(["项目"] + month_headers)
    ws.append(
        ["利润"]
        + [
            f"='任务分解-金额'!{chr(68 + index)}2-'任务分解-成本'!{chr(68 + index)}2-'费用预算'!{chr(67 + index)}2"
            for index in range(12)
        ]
    )

    ws = wb.create_sheet("预算价格表")
    ws.append(["产品编码", "品类", "产品名称", "统一出厂价", "补贴标准", "补贴后价格"])
    ws.append(["P001", "食品", "测试产品", 10, 0, 6])
    wb.save(path)


def test_calculation_check_accepts_formula_cells_without_cached_values(tmp_path):
    client, _ = build_test_client(tmp_path)
    try:
        workbook_path = tmp_path / "G001_S001_2026_公式预算表.xlsx"
        create_formula_workbook(workbook_path)
        file_id = upload_workbook(client, workbook_path)

        response = client.post(f"/api/check/calculation/{file_id}")

        assert response.status_code == 200
        body = response.json()
        assert body["error_count"] == 0
        assert body["check_status"] == "检查通过"
    finally:
        cleanup_test_client()
