from openpyxl import Workbook
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database.db import Base, get_db
from backend.main import app


def build_test_client(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'formula_test.db'}",
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


def create_formula_workbook(path):
    wb = Workbook()
    wb.remove(wb.active)
    month_headers = [f"{month}月" for month in range(1, 13)]
    base_headers = ["产品编码", "品类", "产品名称"] + month_headers

    ws = wb.create_sheet("任务分解-数量")
    ws.append(base_headers)
    ws.append(["P001", "食品", "测试产品"] + [10] * 12)

    ws = wb.create_sheet("任务分解-金额")
    ws.append(base_headers)
    ws.append(["P001", "食品", "测试产品", 100, "=D2*10", "#DIV/0!", "#NAME?", "#REF!"] + ["=D2*10"] * 7)

    ws = wb.create_sheet("任务分解-成本")
    ws.append(["产品编码", "品类", "产品名称", "成本价"] + month_headers)
    ws.append(["P001", "食品", "测试产品", 6, None, "=E2*6"] + ["=E2*6"] * 10)

    ws = wb.create_sheet("费用预算")
    ws.append(["预算项目", "预算小项"] + month_headers)
    ws.append(["推广费", "投流"] + ["=SUM(A1:A1)"] * 12)

    ws = wb.create_sheet("利润分解表")
    ws.append(["项目"] + month_headers)
    ws.append(["利润", 10] + ["=B2"] * 11)

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


def test_formula_check_records_missing_overwritten_and_error_values(tmp_path):
    client, _ = build_test_client(tmp_path)
    try:
        workbook_path = tmp_path / "公式问题.xlsx"
        create_formula_workbook(workbook_path)
        file_id = upload_workbook(client, workbook_path)

        response = client.post(f"/api/check/formula/{file_id}")

        assert response.status_code == 200
        body = response.json()
        assert body["check_type"] == "formula"
        assert body["error_count"] >= 5

        results = client.get(f"/api/check/results/{file_id}", params={"check_type": "formula"}).json()
        error_codes = {item["error_code"] for item in results}
        assert "formula_overwritten" in error_codes
        assert "formula_missing" in error_codes
        assert "formula_error_value" in error_codes
        assert "formula_ref_error" in error_codes

        files = client.get("/api/upload/files").json()
        uploaded_file = next(item for item in files if item["id"] == file_id)
        assert uploaded_file["check_status"] == "检查失败"
        assert uploaded_file["error_count"] == body["error_count"]
    finally:
        cleanup_test_client()


def test_export_formula_check_report(tmp_path):
    client, report_dir = build_test_client(tmp_path)
    try:
        response = client.post("/api/check/export-formula-report")

        assert response.status_code == 200
        assert response.json()["report_path"].endswith(".xlsx")
        assert any(path.name.startswith("上传公式检查报告_") for path in report_dir.iterdir())
    finally:
        cleanup_test_client()
