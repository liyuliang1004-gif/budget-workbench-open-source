from pathlib import Path

from fastapi.testclient import TestClient
from openpyxl import Workbook
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database.db import Base, get_db
from backend.database.models import ExpenseBudgetDetail, SalesBudgetDetail, UploadCheckResult, UploadedFile
from backend.main import app


def build_test_client(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'import_test.db'}",
        connect_args={"check_same_thread": False},
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    upload_dir = tmp_path / "upload"
    standard_dir = tmp_path / "standard"
    registry_path = tmp_path / "shop_registry.json"
    upload_dir.mkdir()
    standard_dir.mkdir()
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
    app.state.standard_dir_override = standard_dir
    app.state.shop_registry_path_override = registry_path
    return TestClient(app), TestingSessionLocal, upload_dir, standard_dir


def cleanup_test_client():
    app.dependency_overrides.clear()
    for name in ["upload_dir_override", "standard_dir_override", "shop_registry_path_override"]:
        if hasattr(app.state, name):
            delattr(app.state, name)


def create_budget_workbook(path: Path):
    wb = Workbook()
    wb.remove(wb.active)
    months = [f"{month}月" for month in range(1, 13)]
    ws = wb.create_sheet("任务分解-数量")
    ws.append(["产品编码", "品类", "产品名称", "平均销售单价"] + months)
    ws.append(["P001", "食品", "测试产品", 10] + [100, 120] + [0] * 10)
    ws = wb.create_sheet("任务分解-金额")
    ws.append(["产品编码", "品类", "产品名称"] + months)
    ws.append(["P001", "食品", "测试产品"] + [1000, 1200] + [0] * 10)
    ws = wb.create_sheet("任务分解-成本")
    ws.append(["产品编码", "品类", "产品名称", "成本价"] + months)
    ws.append(["P001", "食品", "测试产品", 6] + [600, 720] + [0] * 10)
    ws = wb.create_sheet("费用预算")
    ws.append(["预算项目", "预算小项"] + months)
    ws.append(["推广费", "投流"] + [0.01, 0.02] + [0] * 10)
    ws.append(["合计", "合计"] + [0.01, 0.02] + [0] * 10)
    ws = wb.create_sheet("预算价格表")
    ws.append(["产品编码", "品类", "产品名称", "统一出厂价", "补贴标准", "补贴后价格"])
    ws.append(["P001", "食品", "测试产品", 10, 0, 6])
    wb.save(path)


def upload_workbook(client, path, budget_version=1):
    with path.open("rb") as file_obj:
        response = client.post(
            "/api/upload/budget",
            files={"file": (path.name, file_obj, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            data={"budget_year": "2026", "budget_version": str(budget_version), "group_code": "G001", "shop_code": "S001"},
        )
    assert response.status_code == 200
    return response.json()["id"]


def mark_checked(db_factory, file_id, status="检查通过"):
    with db_factory() as db:
        uploaded_file = db.get(UploadedFile, file_id)
        uploaded_file.check_status = status
        uploaded_file.group_code = "G001"
        uploaded_file.group_name = "示例运营组"
        uploaded_file.shop_code = "S001"
        uploaded_file.shop_name = "示例店铺"
        uploaded_file.budget_year = 2026
        db.commit()


def test_failed_check_file_cannot_be_imported(tmp_path):
    client, db_factory, _, _ = build_test_client(tmp_path)
    try:
        workbook_path = tmp_path / "G001_S001_2026_预算表.xlsx"
        create_budget_workbook(workbook_path)
        file_id = upload_workbook(client, workbook_path)
        mark_checked(db_factory, file_id, "检查失败")
        with db_factory() as db:
            db.add(UploadCheckResult(file_id=file_id, check_type="format", severity="error", error_message="测试错误"))
            db.commit()

        response = client.post(f"/api/import/{file_id}")

        assert response.status_code == 400
        assert "不允许入库" in response.json()["detail"]
    finally:
        cleanup_test_client()


def test_checked_file_can_be_imported_and_duplicate_is_rejected(tmp_path):
    client, db_factory, _, _ = build_test_client(tmp_path)
    try:
        workbook_path = tmp_path / "G001_S001_2026_预算表.xlsx"
        create_budget_workbook(workbook_path)
        file_id = upload_workbook(client, workbook_path)
        mark_checked(db_factory, file_id)

        response = client.post(f"/api/import/{file_id}")

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "success"
        assert body["sales_rows"] == 12
        assert body["expense_rows"] == 12

        with db_factory() as db:
            assert db.query(SalesBudgetDetail).filter(SalesBudgetDetail.source_file_id == file_id).count() == 12
            uploaded_file = db.get(UploadedFile, file_id)
            assert uploaded_file.import_status == "已入库"
            assert uploaded_file.budget_version == 1
            assert db.query(SalesBudgetDetail).filter(SalesBudgetDetail.source_file_id == file_id).first().budget_version == 1

        duplicate = client.post(f"/api/import/{file_id}")
        assert duplicate.status_code == 400
        assert "已入库" in duplicate.json()["detail"]
        with db_factory() as db:
            assert db.get(UploadedFile, file_id).import_status == "已入库"
            assert db.query(SalesBudgetDetail).filter_by(source_file_id=file_id).count() == 12
    finally:
        cleanup_test_client()


def test_upload_records_selected_budget_version(tmp_path):
    client, db_factory, _, _ = build_test_client(tmp_path)
    try:
        workbook_path = tmp_path / "G001_S001_2026_预算表.xlsx"
        create_budget_workbook(workbook_path)
        file_id = upload_workbook(client, workbook_path, budget_version=2)
        mark_checked(db_factory, file_id)

        response = client.post(f"/api/import/{file_id}")

        assert response.status_code == 200
        with db_factory() as db:
            uploaded_file = db.get(UploadedFile, file_id)
            assert uploaded_file.budget_version == 2
            assert {
                row.budget_version
                for row in db.query(SalesBudgetDetail).filter(SalesBudgetDetail.source_file_id == file_id).all()
            } == {2}
    finally:
        cleanup_test_client()


def test_manual_metadata_allows_import_without_filename_codes(tmp_path):
    client, db_factory, _, _ = build_test_client(tmp_path)
    try:
        workbook_path = tmp_path / "预算表.xlsx"
        create_budget_workbook(workbook_path)
        file_id = upload_workbook(client, workbook_path)
        mark_checked(db_factory, file_id)

        response = client.post(f"/api/import/{file_id}")

        assert response.status_code == 200
        with db_factory() as db:
            detail = db.query(SalesBudgetDetail).filter(SalesBudgetDetail.source_file_id == file_id).first()
            assert detail.year == 2026
            assert detail.group_code == "G001"
            assert detail.group_name == "示例运营组"
            assert detail.shop_code == "S001"
            assert detail.shop_name == "示例店铺"
    finally:
        cleanup_test_client()


def test_expense_total_rows_are_not_imported(tmp_path):
    client, db_factory, _, _ = build_test_client(tmp_path)
    try:
        workbook_path = tmp_path / "预算表.xlsx"
        create_budget_workbook(workbook_path)
        file_id = upload_workbook(client, workbook_path)
        mark_checked(db_factory, file_id)

        response = client.post(f"/api/import/{file_id}")

        assert response.status_code == 200
        with db_factory() as db:
            assert db.query(ExpenseBudgetDetail).filter(ExpenseBudgetDetail.expense_category == "合计").count() == 0
            assert db.query(ExpenseBudgetDetail).count() == 12
    finally:
        cleanup_test_client()


def test_batch_import_checked_files(tmp_path):
    client, db_factory, _, _ = build_test_client(tmp_path)
    try:
        workbook_path = tmp_path / "G001_S001_2026_预算表.xlsx"
        create_budget_workbook(workbook_path)
        file_id = upload_workbook(client, workbook_path)
        mark_checked(db_factory, file_id)

        response = client.post("/api/import/checked-files")

        assert response.status_code == 200
        assert response.json()["success_count"] == 1
    finally:
        cleanup_test_client()
