from backend.tests.test_import_budget import build_test_client, cleanup_test_client, create_budget_workbook, mark_checked, upload_workbook


def test_aggregate_summaries_and_csv_export(tmp_path):
    client, db_factory, _, standard_dir = build_test_client(tmp_path)
    try:
        workbook_path = tmp_path / "G001_S001_2026_预算表.xlsx"
        create_budget_workbook(workbook_path)
        file_id = upload_workbook(client, workbook_path)
        mark_checked(db_factory, file_id)
        assert client.post(f"/api/import/{file_id}").status_code == 200

        response = client.post("/api/aggregate/run")

        assert response.status_code == 200
        body = response.json()
        assert body["shop_rows"] == 12
        assert body["group_rows"] == 12
        assert body["department_rows"] == 12

        summary = client.get("/api/aggregate/summary").json()
        assert summary["department_total"]["sales_amount"] == 2200
        assert summary["department_total"]["cost_amount"] == 1320
        assert summary["department_total"]["expense_amount"] == 300
        assert summary["department_total"]["profit_amount"] == 580
        assert summary["group_summary"][0]["sales_amount"] == summary["shop_summary"][0]["sales_amount"]
        assert summary["group_summary"][0]["group_name"] == "示例运营组"
        assert summary["shop_summary"][0]["shop_name"] == "示例店铺"
        assert summary["product_summary"][0]["product_name"] == "测试产品"

        dashboard = client.get("/api/dashboard/data", params={"year": 2026}).json()
        assert dashboard["filters"]["year"] == 2026
        assert dashboard["summary"]["sales_amount"] == 2200
        filtered_dashboard = client.get("/api/dashboard/data", params={"year": 2026, "month": 1, "product_name": "测试产品"}).json()
        assert filtered_dashboard["summary"]["sales_amount"] == 1000

        csv_files = {path.name for path in standard_dir.iterdir()}
        assert any(name.startswith("销售预算明细_") for name in csv_files)
        assert any(name.startswith("费用预算明细_") for name in csv_files)
        assert any(name.startswith("店铺预算汇总_") for name in csv_files)
        assert any(name.startswith("运营组预算汇总_") for name in csv_files)
        assert any(name.startswith("部门预算汇总_") for name in csv_files)
    finally:
        cleanup_test_client()


def test_aggregate_keeps_budget_versions_separate(tmp_path):
    client, db_factory, _, _ = build_test_client(tmp_path)
    try:
        first_path = tmp_path / "G001_S001_2026_第一版.xlsx"
        second_path = tmp_path / "G001_S001_2026_第二版.xlsx"
        create_budget_workbook(first_path)
        create_budget_workbook(second_path)
        first_id = upload_workbook(client, first_path, budget_version=1)
        second_id = upload_workbook(client, second_path, budget_version=2)
        mark_checked(db_factory, first_id)
        mark_checked(db_factory, second_id)
        assert client.post(f"/api/import/{first_id}").status_code == 200
        assert client.post(f"/api/import/{second_id}").status_code == 200

        response = client.post("/api/aggregate/run")

        assert response.status_code == 200
        first_summary = client.get("/api/aggregate/summary", params={"budget_version": 1}).json()
        second_summary = client.get("/api/aggregate/summary", params={"budget_version": 2}).json()
        all_summary = client.get("/api/aggregate/summary").json()
        assert first_summary["department_total"]["sales_amount"] == 2200
        assert second_summary["department_total"]["sales_amount"] == 2200
        assert all_summary["department_total"]["sales_amount"] == 4400
        assert {row["budget_version"] for row in first_summary["monthly_trend"]} == {1}
        assert {row["budget_version"] for row in second_summary["monthly_trend"]} == {2}
    finally:
        cleanup_test_client()


def test_zero_sales_rates_do_not_crash(tmp_path):
    client, db_factory, _, _ = build_test_client(tmp_path)
    try:
        workbook_path = tmp_path / "G001_S001_2026_零销售.xlsx"
        create_budget_workbook(workbook_path)
        file_id = upload_workbook(client, workbook_path)
        mark_checked(db_factory, file_id)
        assert client.post(f"/api/import/{file_id}").status_code == 200

        response = client.post("/api/aggregate/run")

        assert response.status_code == 200
    finally:
        cleanup_test_client()


def test_aggregate_rejects_empty_selected_version(tmp_path):
    client, _, _, standard_dir = build_test_client(tmp_path)
    try:
        response = client.post("/api/aggregate/run", json={"budget_version": 1})

        assert response.status_code == 400
        assert "暂无已入库预算数据" in response.json()["detail"]
        assert list(standard_dir.iterdir()) == []
    finally:
        cleanup_test_client()
