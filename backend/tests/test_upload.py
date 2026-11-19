import io

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
        f"sqlite:///{tmp_path / 'upload_test.db'}",
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


def test_health_still_returns_ok():
    client = TestClient(app)

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_upload_rejects_non_xlsx_file(tmp_path):
    client, _, _ = build_test_client(tmp_path)
    try:
        response = client.post(
            "/api/upload/budget",
            files={"file": ("budget.txt", b"not excel", "text/plain")},
            data={"budget_year": "2026", "budget_version": "1", "group_code": "G001", "shop_code": "S001"},
        )

        assert response.status_code == 400
        assert "仅支持" in response.json()["detail"]
    finally:
        cleanup_test_client()


def test_upload_rejects_macos_metadata_xlsx_file(tmp_path):
    client, _, _ = build_test_client(tmp_path)
    try:
        response = client.post(
            "/api/upload/budget",
            files={"file": ("._预算表.xlsx", b"metadata", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            data={"budget_year": "2026", "budget_version": "1", "group_code": "G001", "shop_code": "S001"},
        )

        assert response.status_code == 400
        assert "系统元数据" in response.json()["detail"]
    finally:
        cleanup_test_client()


def test_upload_xlsx_records_uploaded_file(tmp_path):
    client, upload_dir, _ = build_test_client(tmp_path)
    try:
        response = client.post(
            "/api/upload/budget",
            files={
                "file": (
                    "预算表.xlsx",
                    io.BytesIO(b"placeholder xlsx bytes"),
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            },
            data={"budget_year": "2026", "budget_version": "1", "group_code": "G001", "shop_code": "S001"},
        )

        assert response.status_code == 200
        body = response.json()
        assert body["id"] > 0
        assert body["file_name"] == "预算表.xlsx"
        assert body["budget_year"] == 2026
        assert body["group_name"] == "示例运营组"
        assert body["shop_name"] == "示例店铺"
        assert body["check_status"] == "待检查"
        assert body["import_status"] == "未入库"
        assert (upload_dir / body["saved_file_name"]).exists()

        list_response = client.get("/api/upload/files")
        assert list_response.status_code == 200
        assert list_response.json()[0]["file_name"] == "预算表.xlsx"
    finally:
        cleanup_test_client()


def test_delete_unimported_uploaded_file(tmp_path):
    client, upload_dir, _ = build_test_client(tmp_path)
    try:
        upload_response = client.post(
            "/api/upload/budget",
            files={"file": ("预算表.xlsx", io.BytesIO(b"excel bytes"), "application/octet-stream")},
            data={"budget_year": "2026", "budget_version": "1", "group_code": "G001", "shop_code": "S001"},
        )
        file_id = upload_response.json()["id"]
        saved_file_name = upload_response.json()["saved_file_name"]

        response = client.delete(f"/api/upload/files/{file_id}")

        assert response.status_code == 200
        assert response.json()["message"] == "上传文件已删除"
        assert not (upload_dir / saved_file_name).exists()
        assert client.get("/api/upload/files").json() == []
    finally:
        cleanup_test_client()


def test_delete_imported_file_removes_imported_rows_checks_and_reaggregates(tmp_path):
    client, upload_dir, _ = build_test_client(tmp_path)
    try:
        upload_response = client.post(
            "/api/upload/budget",
            files={"file": ("G001_S001_2026_预算表.xlsx", io.BytesIO(b"excel bytes"), "application/octet-stream")},
            data={"budget_year": "2026", "budget_version": "1", "group_code": "G001", "shop_code": "S001"},
        )
        file_id = upload_response.json()["id"]
        saved_file_name = upload_response.json()["saved_file_name"]

        db_generator = app.dependency_overrides[get_db]()
        db = next(db_generator)
        try:
            uploaded_file = db.get(UploadedFile, file_id)
            uploaded_file.import_status = "已入库"
            uploaded_file.budget_year = 2026
            db.add(UploadCheckResult(file_id=file_id, check_type="format", severity="error", error_message="测试错误"))
            db.add(
                SalesBudgetDetail(
                    year=2026,
                    month=1,
                    group_code="G001",
                    shop_code="S001",
                    product_code="P001",
                    budget_quantity=10,
                    average_price=100,
                    budget_sales_amount=1000,
                    cost_price=60,
                    budget_cost_amount=600,
                    budget_gross_profit=400,
                    source_file_id=file_id,
                )
            )
            db.add(
                ExpenseBudgetDetail(
                    year=2026,
                    month=1,
                    group_code="G001",
                    shop_code="S001",
                    expense_category="推广费",
                    expense_item="投流",
                    budget_expense_amount=100,
                    source_file_id=file_id,
                )
            )
            db.add(
                DepartmentBudgetSummary(
                    year=2026,
                    month=1,
                    sales_amount=1000,
                    cost_amount=600,
                    gross_profit=400,
                    expense_amount=100,
                    profit_amount=300,
                )
            )
            db.commit()
        finally:
            try:
                next(db_generator)
            except StopIteration:
                pass

        response = client.delete(f"/api/upload/files/{file_id}")

        assert response.status_code == 200
        assert response.json()["message"] == "上传文件及已入库数据已删除"
        assert not (upload_dir / saved_file_name).exists()
        db_generator = app.dependency_overrides[get_db]()
        db = next(db_generator)
        try:
            assert db.get(UploadedFile, file_id) is None
            assert db.query(UploadCheckResult).filter(UploadCheckResult.file_id == file_id).count() == 0
            assert db.query(SalesBudgetDetail).filter(SalesBudgetDetail.source_file_id == file_id).count() == 0
            assert db.query(ExpenseBudgetDetail).filter(ExpenseBudgetDetail.source_file_id == file_id).count() == 0
            assert db.query(DepartmentBudgetSummary).count() == 0
            assert db.query(GroupBudgetSummary).count() == 0
            assert db.query(ShopBudgetSummary).count() == 0
        finally:
            try:
                next(db_generator)
            except StopIteration:
                pass
    finally:
        cleanup_test_client()


def test_metadata_and_shop_template_endpoints(tmp_path):
    client, _, _ = build_test_client(tmp_path)
    try:
        metadata = client.get("/api/metadata/groups-shops")
        assert metadata.status_code == 200
        assert metadata.json()["operation_groups"][0]["group_name"] == "示例运营组"

        template = client.get("/api/templates/shop-budget")
        assert template.status_code == 200
        assert template.headers["content-type"].startswith(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        assert template.content.startswith(b"PK")
    finally:
        cleanup_test_client()


def test_groups_shops_registry_can_be_saved_and_hides_inactive_items(tmp_path):
    client, _, _ = build_test_client(tmp_path)
    registry_path = tmp_path / "shop_registry.json"
    app.state.shop_registry_path_override = registry_path
    try:
        response = client.put(
            "/api/metadata/groups-shops",
            json={
                "operation_groups": [
                    {
                        "group_code": "G001",
                        "group_name": "示例运营组",
                        "status": "active",
                        "shops": [
                            {"shop_code": "S001", "shop_name": "示例店铺", "status": "active"},
                            {"shop_code": "S002", "shop_name": "已停用店铺", "status": "inactive"},
                        ],
                    },
                    {"group_code": "G002", "group_name": "停用运营组", "status": "inactive", "shops": []},
                ]
            },
        )

        assert response.status_code == 200
        body = response.json()
        assert len(body["operation_groups"]) == 1
        assert body["operation_groups"][0]["shops"] == [
            {"shop_code": "S001", "shop_name": "示例店铺", "group_code": "G001", "status": "active"}
        ]
        assert "已停用店铺" in registry_path.read_text(encoding="utf-8")
    finally:
        cleanup_test_client()
        if hasattr(app.state, "shop_registry_path_override"):
            delattr(app.state, "shop_registry_path_override")
