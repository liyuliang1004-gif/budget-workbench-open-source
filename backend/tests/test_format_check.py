from openpyxl import Workbook
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database.db import Base, get_db
from backend.main import app


REQUIRED_SHEETS = [
    "任务分解-数量",
    "任务分解-金额",
    "任务分解-成本",
    "费用预算",
    "利润分解表",
    "预算价格表",
]


def build_test_client(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'format_test.db'}",
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
    return TestClient(app), upload_dir, report_dir


def cleanup_test_client():
    app.dependency_overrides.clear()
    if hasattr(app.state, "upload_dir_override"):
        delattr(app.state, "upload_dir_override")
    if hasattr(app.state, "report_dir_override"):
        delattr(app.state, "report_dir_override")
    if hasattr(app.state, "shop_registry_path_override"):
        delattr(app.state, "shop_registry_path_override")


def save_workbook(path, sheet_headers):
    wb = Workbook()
    default_sheet = wb.active
    wb.remove(default_sheet)
    for sheet_name, headers in sheet_headers.items():
        ws = wb.create_sheet(sheet_name)
        for column_index, header in enumerate(headers, start=1):
            ws.cell(row=1, column=column_index, value=header)
    wb.save(path)


def upload_existing_file(client, path):
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


def test_missing_required_sheet_writes_check_result(tmp_path):
    client, _, _ = build_test_client(tmp_path)
    try:
        workbook_path = tmp_path / "缺少sheet.xlsx"
        save_workbook(workbook_path, {"任务分解-数量": ["产品编码", "品类", "产品名称"]})
        file_id = upload_existing_file(client, workbook_path)

        response = client.post(f"/api/check/format/{file_id}")

        assert response.status_code == 200
        body = response.json()
        assert body["check_status"] == "检查失败"
        assert body["error_count"] >= 1

        results = client.get(f"/api/check/results/{file_id}").json()
        assert any(item["error_code"] == "MISSING_SHEET" for item in results)
    finally:
        cleanup_test_client()


def test_missing_month_column_writes_format_error(tmp_path):
    client, _, _ = build_test_client(tmp_path)
    try:
        workbook_path = tmp_path / "缺少月份.xlsx"
        headers = {
            sheet: ["产品编码", "品类", "产品名称", "1月", "2月"]
            for sheet in ["任务分解-数量", "任务分解-金额"]
        }
        headers["任务分解-成本"] = ["产品编码", "品类", "产品名称", "成本价", "1月", "2月"]
        headers["费用预算"] = ["预算项目", "预算小项", "1月", "2月"]
        headers["利润分解表"] = ["项目"]
        headers["预算价格表"] = ["产品编码", "品类", "产品名称", "统一出厂价", "补贴标准", "补贴后价格"]
        save_workbook(workbook_path, headers)
        file_id = upload_existing_file(client, workbook_path)

        response = client.post(f"/api/check/format/{file_id}")

        assert response.status_code == 200
        results = client.get(f"/api/check/results/{file_id}", params={"error_code": "MONTH_COLUMN_MISSING"}).json()
        assert any("缺少 3月 列" in item["error_message"] for item in results)
    finally:
        cleanup_test_client()


def test_missing_product_code_with_budget_data_updates_status_counts(tmp_path):
    client, _, _ = build_test_client(tmp_path)
    try:
        workbook_path = tmp_path / "缺少产品编码.xlsx"
        headers = {
            "任务分解-数量": ["产品编码", "品类", "产品名称"] + [f"{month}月" for month in range(1, 13)],
            "任务分解-金额": ["产品编码", "品类", "产品名称"] + [f"{month}月" for month in range(1, 13)],
            "任务分解-成本": ["产品编码", "品类", "产品名称", "成本价"] + [f"{month}月" for month in range(1, 13)],
            "费用预算": ["预算项目", "预算小项"] + [f"{month}月" for month in range(1, 13)],
            "利润分解表": ["项目"],
            "预算价格表": ["产品编码", "品类", "产品名称", "统一出厂价", "补贴标准", "补贴后价格"],
        }
        save_workbook(workbook_path, headers)
        wb = Workbook()
        wb = __import__("openpyxl").load_workbook(workbook_path)
        ws = wb["任务分解-数量"]
        ws["C2"] = "测试产品"
        ws["D2"] = 10
        wb.save(workbook_path)
        file_id = upload_existing_file(client, workbook_path)

        response = client.post(f"/api/check/format/{file_id}")

        assert response.status_code == 200
        body = response.json()
        assert body["check_status"] == "检查通过"
        assert body["error_count"] == 0
        assert body["warning_count"] == 0

        files = client.get("/api/upload/files").json()
        uploaded_file = next(item for item in files if item["id"] == file_id)
        assert uploaded_file["check_status"] == "检查通过"
        assert uploaded_file["error_count"] == 0

        results = client.get(f"/api/check/results/{file_id}").json()
        product_code_issue = next(item for item in results if item["error_code"] == "REQUIRED_PRODUCT_CODE_MISSING")
        assert product_code_issue["severity"] == "info"
    finally:
        cleanup_test_client()


def test_template14_expense_month_header_is_not_treated_as_missing_expense_item(tmp_path):
    client, _, _ = build_test_client(tmp_path)
    try:
        workbook_path = tmp_path / "1.4费用表头.xlsx"
        wb = Workbook()
        wb.remove(wb.active)
        months = [f"{month}月" for month in range(1, 13)]

        ws = wb.create_sheet("任务分解-金额")
        ws.append(["预算项目", None, None, None, "2025年（万元）", None, None, "2026年（万元）"])
        ws.append(["序号", "产品编码", "品类", "产品名称", "已完成（1-9）", "预计完成（10-12）", "全年", *months, "合计"])
        ws.append([1, "P001", "食品", "测试产品", 0, 0, 0, 1, *([0] * 11), 1])

        ws = wb.create_sheet("任务分解-数量")
        ws.append([None, None, None, None, "平均销售单价（元）", None, None, None, None, None, None, None, None, None, None, None, 2025, None, None, "2026年"])
        ws.append(["序号", "产品编码", "品类", "产品名称", *months, "已完成（1-9）", "预计完成（10-12）", "全年", *months, "合计"])
        ws.append([1, "P001", "食品", "测试产品", 0, *([0] * 11), 0, 0, 0, 10, *([0] * 11), 10])

        ws = wb.create_sheet("任务分解-成本")
        ws.append(["预算项目", None, None, None, None, "2025年（万元）", None, None, "2026年（万元）"])
        ws.append(["序号", "产品编码", "品类", "产品名称", "成本价（元）", "已完成（1-9）", "预计完成（10-12）", "全年", *months, "合计"])
        ws.append([1, "P001", "食品", "测试产品", 6, 0, 0, 0, 0.006, *([0] * 11), 0.006])

        ws = wb.create_sheet("费用预算")
        ws.append([None, "11、营业费用预算"])
        ws.append([None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, "（单位：万元）"])
        ws.append([None, "预算项目", "预算小项", "2025年", None, None, "2026年"])
        ws.append([None, None, None, "已完成（1-9）", "预计完成（10-12）", "全年", *months, "合计"])
        ws.append([None, "推广费", "投流", 0, 0, 0, 0.01, *([0] * 11), 0.01])

        ws = wb.create_sheet("利润分解表")
        ws.append(["预算项目", "2025年", None, None, "2026年"])
        ws.append([None, "已完成", "预计完成", "全年", *months, "合计"])
        ws.append(["利润分解", 0, 0, 0, 0.984, *([0] * 11), 0.984])
        wb.save(workbook_path)
        file_id = upload_existing_file(client, workbook_path)

        response = client.post(f"/api/check/format/{file_id}")

        assert response.status_code == 200
        results = client.get(f"/api/check/results/{file_id}", params={"error_code": "REQUIRED_EXPENSE_ITEM_MISSING"}).json()
        assert results == []
    finally:
        cleanup_test_client()


def test_template_version_mismatch_writes_format_error(tmp_path):
    client, _, _ = build_test_client(tmp_path)
    try:
        workbook_path = tmp_path / "模板版本错误.xlsx"
        headers = {
            "任务分解-数量": ["产品编码", "品类", "产品名称"] + [f"{month}月" for month in range(1, 13)],
            "任务分解-金额": ["产品编码", "品类", "产品名称"] + [f"{month}月" for month in range(1, 13)],
            "任务分解-成本": ["产品编码", "品类", "产品名称", "成本价"] + [f"{month}月" for month in range(1, 13)],
            "费用预算": ["预算项目", "预算小项"] + [f"{month}月" for month in range(1, 13)],
            "利润分解表": ["项目"],
            "预算价格表": ["产品编码", "品类", "产品名称", "统一出厂价", "补贴标准", "补贴后价格"],
        }
        save_workbook(workbook_path, headers)
        wb = __import__("openpyxl").load_workbook(workbook_path)
        wb.properties.keywords = "模板版本:V0.9"
        wb.save(workbook_path)
        file_id = upload_existing_file(client, workbook_path)

        response = client.post(f"/api/check/format/{file_id}")

        assert response.status_code == 200
        results = client.get(f"/api/check/results/{file_id}", params={"error_code": "TEMPLATE_VERSION_MISMATCH"}).json()
        assert results
        assert results[0]["severity"] == "info"
        assert results[0]["uploaded_value"] == "V0.9"
        assert results[0]["expected_value"] == "V1.0"
    finally:
        cleanup_test_client()


def test_export_format_check_report(tmp_path):
    client, _, report_dir = build_test_client(tmp_path)
    try:
        response = client.post("/api/check/export-format-report")

        assert response.status_code == 200
        body = response.json()
        assert body["report_path"].endswith(".xlsx")
        assert any(path.name.startswith("上传格式检查报告_") for path in report_dir.iterdir())
    finally:
        cleanup_test_client()
