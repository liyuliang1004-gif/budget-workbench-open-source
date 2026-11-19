from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from backend.database.db import Base, get_db
from backend.database.models import DepartmentBudgetSummary, UploadCheckResult, UploadedFile
from backend.main import app


def build_test_client(tmp_path, monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setenv("AI_ANALYSIS_MODE", "mock")
    engine = create_engine(
        f"sqlite:///{tmp_path / 'ai_test.db'}",
        connect_args={"check_same_thread": False},
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    report_dir = tmp_path / "ai_reports"
    report_dir.mkdir()

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    app.state.ai_report_dir_override = report_dir
    app.state.system_settings_path_override = tmp_path / "system_settings.json"
    seed_data(TestingSessionLocal)
    return TestClient(app), report_dir


def cleanup_test_client():
    app.dependency_overrides.clear()
    if hasattr(app.state, "ai_report_dir_override"):
        delattr(app.state, "ai_report_dir_override")
    if hasattr(app.state, "system_settings_path_override"):
        delattr(app.state, "system_settings_path_override")


def seed_data(db_factory):
    with db_factory() as db:
        db.add(
            DepartmentBudgetSummary(
                year=2026,
                month=1,
                sales_amount=1000,
                cost_amount=600,
                gross_profit=400,
                expense_amount=100,
                profit_amount=300,
                cost_rate=0.6,
                expense_rate=0.1,
                profit_rate=0.3,
            )
        )
        uploaded = UploadedFile(
            file_name="预算表.xlsx",
            file_path="/secret/raw/预算表.xlsx",
            file_type="budget",
            file_hash="abc",
            check_status="检查失败",
            import_status="未入库",
        )
        db.add(uploaded)
        db.flush()
        db.add(
            UploadCheckResult(
                file_id=uploaded.id,
                check_type="format",
                severity="error",
                error_code="MISSING_SHEET",
                error_message="缺少必要工作表",
            )
        )
        db.commit()


def test_mock_analysis_creates_task_and_structured_result(tmp_path, monkeypatch):
    client, _ = build_test_client(tmp_path, monkeypatch)
    try:
        response = client.post(
            "/api/ai/analyze",
            json={
                "task_type": "部门预算分析",
                "scope_type": "department",
                "scope_value": "示例运营组",
                "question": "请分析当前预算结构和主要风险",
                "use_mock": True,
            },
        )

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "success"
        assert body["model_name"] == "mock"
        assert "# 分析结论摘要" in body["result"]
        assert "# 关键数据依据" in body["result"]

        tasks = client.get("/api/ai/tasks").json()
        assert len(tasks) == 1
        assert tasks[0]["task_type"] == "部门预算分析"
    finally:
        cleanup_test_client()


def test_task_detail_export_and_snapshot_do_not_include_excel_path(tmp_path, monkeypatch):
    client, report_dir = build_test_client(tmp_path, monkeypatch)
    try:
        task_id = client.post(
            "/api/ai/analyze",
            json={
                "task_type": "错误检查解释",
                "scope_type": "department",
                "scope_value": "示例运营组",
                "question": "解释检查错误",
            },
        ).json()["task_id"]

        detail = client.get(f"/api/ai/tasks/{task_id}")
        assert detail.status_code == 200
        body = detail.json()
        assert body["status"] == "success"
        assert ".xlsx" not in body["input_data_snapshot"]
        assert "/secret/raw" not in body["input_data_snapshot"]

        export = client.post(f"/api/ai/export/{task_id}")
        assert export.status_code == 200
        path = export.json()["report_path"]
        assert path.endswith(".md")
        assert any(item.name.startswith("AI分析报告_") for item in report_dir.iterdir())
    finally:
        cleanup_test_client()


def test_task_filters_and_latest_summary(tmp_path, monkeypatch):
    client, _ = build_test_client(tmp_path, monkeypatch)
    try:
        client.post(
            "/api/ai/analyze",
            json={
                "task_type": "利润风险分析",
                "scope_type": "group",
                "scope_value": "G001",
                "question": "分析利润风险",
            },
        )

        filtered = client.get("/api/ai/tasks", params={"task_type": "利润风险分析", "scope_type": "group", "status": "success"})
        assert filtered.status_code == 200
        assert len(filtered.json()) == 1

        latest = client.get("/api/ai/latest-summary")
        assert latest.status_code == 200
        assert "summary" in latest.json()
    finally:
        cleanup_test_client()


def test_delete_ai_task_removes_history_record(tmp_path, monkeypatch):
    client, _ = build_test_client(tmp_path, monkeypatch)
    try:
        task_id = client.post(
            "/api/ai/analyze",
            json={
                "task_type": "预算平台问答",
                "scope_type": "platform",
                "scope_value": "整个预算平台",
                "question": "测试删除历史记录",
            },
        ).json()["task_id"]

        response = client.delete(f"/api/ai/tasks/{task_id}")

        assert response.status_code == 200
        assert response.json()["success"] is True
        assert client.get(f"/api/ai/tasks/{task_id}").status_code == 404
        assert client.get("/api/ai/tasks").json() == []
    finally:
        cleanup_test_client()


def test_rename_ai_task_updates_history_title(tmp_path, monkeypatch):
    client, _ = build_test_client(tmp_path, monkeypatch)
    try:
        task_id = client.post(
            "/api/ai/analyze",
            json={
                "task_type": "预算平台问答",
                "scope_type": "platform",
                "scope_value": "整个预算平台",
                "question": "原始问题",
            },
        ).json()["task_id"]

        response = client.put(f"/api/ai/tasks/{task_id}/rename", json={"title": "平台风险检查"})

        assert response.status_code == 200
        body = response.json()
        assert body["question"] == "平台风险检查"
        tasks = client.get("/api/ai/tasks").json()
        assert tasks[0]["question"] == "平台风险检查"
    finally:
        cleanup_test_client()


def test_deepseek_settings_are_used_by_default(tmp_path, monkeypatch):
    client, _ = build_test_client(tmp_path, monkeypatch)
    monkeypatch.delenv("AI_ANALYSIS_MODE", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    app.state.system_settings_path_override = tmp_path / "system_settings.json"

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"choices": [{"message": {"content": "# 分析结论摘要\n\n正式模式回复"}}]}

    calls = []

    def fake_post(url, headers, json, timeout):
        calls.append({"url": url, "headers": headers, "json": json, "timeout": timeout})
        return FakeResponse()

    monkeypatch.setattr("backend.services.ai_analysis_service.requests.post", fake_post)
    try:
        client.put(
            "/api/settings",
            json={
                "ai_config": {
                    "mode": "deepseek",
                    "api_base": "https://api.deepseek.com",
                    "model": "deepseek-chat",
                    "api_key": "sk-test-secret",
                }
            },
        )

        response = client.post(
            "/api/ai/analyze",
            json={
                "task_type": "预算平台问答",
                "scope_type": "platform",
                "scope_value": "整个预算平台",
                "question": "正式模式测试",
            },
        )

        assert response.status_code == 200
        body = response.json()
        assert body["model_name"] == "deepseek-chat"
        assert "正式模式回复" in body["result"]
        assert calls[0]["headers"]["Authorization"] == "Bearer sk-test-secret"
    finally:
        cleanup_test_client()
        if hasattr(app.state, "system_settings_path_override"):
            delattr(app.state, "system_settings_path_override")


def test_deepseek_prompt_uses_user_overrides_and_keeps_safety_rules(tmp_path, monkeypatch):
    client, _ = build_test_client(tmp_path, monkeypatch)
    monkeypatch.delenv("AI_ANALYSIS_MODE", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    app.state.system_settings_path_override = tmp_path / "system_settings.json"

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"choices": [{"message": {"content": "# 分析结论摘要\n\n自定义提示词回复"}}]}

    calls = []

    def fake_post(url, headers, json, timeout):
        calls.append({"url": url, "headers": headers, "json": json, "timeout": timeout})
        return FakeResponse()

    monkeypatch.setattr("backend.services.ai_analysis_service.requests.post", fake_post)
    try:
        client.put(
            "/api/settings",
            json={
                "ai_config": {
                    "mode": "deepseek",
                    "api_base": "https://api.deepseek.com",
                    "model": "deepseek-chat",
                    "api_key": "sk-test-secret",
                },
                "ai_prompts": {
                    "general_prompt": "用户通用提示：用经营负责人的语言回答。",
                    "task_prompts": {
                        "预算平台问答": "用户平台问答提示：先列风险，再列检查步骤。"
                    },
                },
            },
        )

        response = client.post(
            "/api/ai/analyze",
            json={
                "task_type": "预算平台问答",
                "scope_type": "platform",
                "scope_value": "整个预算平台",
                "question": "平台现在最应该关注什么？",
            },
        )

        assert response.status_code == 200
        prompt = calls[0]["json"]["messages"][0]["content"]
        assert "用户通用提示：用经营负责人的语言回答。" in prompt
        assert "用户平台问答提示：先列风险，再列检查步骤。" in prompt
        assert "AI 只能问答，不能代替人工操作" in prompt
        assert "不得输出或推断 API Key" in prompt
    finally:
        cleanup_test_client()
        if hasattr(app.state, "system_settings_path_override"):
            delattr(app.state, "system_settings_path_override")
