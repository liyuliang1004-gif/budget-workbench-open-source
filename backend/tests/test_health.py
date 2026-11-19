from fastapi.testclient import TestClient

from backend.config import CURRENT_STAGE, DATABASE_RELATIVE_PATH, SYSTEM_NAME
from backend.main import app


client = TestClient(app)


def test_health_returns_ok_status():
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "message": "经营工作台后端运行正常",
    }


def test_version_returns_system_name():
    response = client.get("/api/version")

    assert response.status_code == 200
    body = response.json()
    assert body["system_name"] == SYSTEM_NAME
    assert body["stage"] == CURRENT_STAGE
    assert "git_branch" in body
    assert "git_commit" in body


def test_settings_returns_database_path():
    app.state.system_settings_path_override = "/tmp/nonexistent_budget_settings_for_test.json"
    try:
        response = client.get("/api/settings")

        assert response.status_code == 200
        body = response.json()
        assert body["database_path"] == DATABASE_RELATIVE_PATH
        assert body["ai_enabled"] is False
        assert body["onboarding_completed"] is False
        assert body["company_name"] == ""
        assert body["default_year"] >= 2026
        assert body["default_budget_version"] == 1
        assert body["data_mode"] == "formal"
    finally:
        if hasattr(app.state, "system_settings_path_override"):
            delattr(app.state, "system_settings_path_override")


def test_settings_can_save_onboarding_profile(tmp_path):
    app.state.system_settings_path_override = tmp_path / "system_settings.json"
    try:
        local_client = TestClient(app)

        response = local_client.put(
            "/api/settings",
            json={
                "system_name": "经营预算工作台",
                "company_name": "测试公司",
                "default_year": 2027,
                "default_budget_version": 2,
                "data_mode": "demo",
                "onboarding_completed": True,
            },
        )

        assert response.status_code == 200
        body = response.json()
        assert body["system_name"] == "经营预算工作台"
        assert body["company_name"] == "测试公司"
        assert body["default_year"] == 2027
        assert body["default_budget_version"] == 2
        assert body["data_mode"] == "demo"
        assert body["onboarding_completed"] is True

        saved = local_client.get("/api/settings").json()
        assert saved["company_name"] == "测试公司"
        assert saved["default_year"] == 2027
        assert saved["default_budget_version"] == 2
        assert saved["data_mode"] == "demo"
        assert saved["onboarding_completed"] is True
    finally:
        if hasattr(app.state, "system_settings_path_override"):
            delattr(app.state, "system_settings_path_override")


def test_settings_can_save_local_config_without_exposing_api_key(tmp_path):
    app.state.system_settings_path_override = tmp_path / "system_settings.json"
    try:
        local_client = TestClient(app)

        response = local_client.put(
            "/api/settings",
            json={
                "system_name": "预算驾驶舱",
                "ai_config": {
                    "mode": "deepseek",
                    "api_base": "https://api.deepseek.com",
                    "model": "deepseek-chat",
                    "api_key": "sk-test-secret",
                },
                "theme": "dark",
            },
        )

        assert response.status_code == 200
        body = response.json()
        assert body["system_name"] == "预算驾驶舱"
        assert body["ai_config"]["api_key_configured"] is True
        assert body["ai_config"]["api_key_masked"] == "sk-t********cret"
        assert "sk-test-secret" not in response.text

        saved = local_client.get("/api/settings").json()
        assert saved["system_name"] == "预算驾驶舱"
        assert saved["ai_config"]["model"] == "deepseek-chat"
        assert "sk-test-secret" not in str(saved)
    finally:
        if hasattr(app.state, "system_settings_path_override"):
            delattr(app.state, "system_settings_path_override")


def test_settings_can_save_ai_prompt_overrides(tmp_path):
    app.state.system_settings_path_override = tmp_path / "system_settings.json"
    try:
        local_client = TestClient(app)

        response = local_client.put(
            "/api/settings",
            json={
                "ai_prompts": {
                    "general_prompt": "请用老板能快速判断的方式回答，先说结论。",
                    "task_prompts": {
                        "预算平台问答": "回答预算平台问题时，先指出风险，再给下一步检查清单。"
                    },
                }
            },
        )

        assert response.status_code == 200
        body = response.json()
        assert body["ai_prompts"]["general_prompt"] == "请用老板能快速判断的方式回答，先说结论。"
        assert body["ai_prompts"]["task_prompts"]["预算平台问答"] == "回答预算平台问题时，先指出风险，再给下一步检查清单。"
        assert "部门预算分析" in body["ai_prompts"]["task_types"]
        assert body["ai_prompts"]["default_task_prompts"]["预算平台问答"]

        saved = local_client.get("/api/settings").json()
        assert saved["ai_prompts"]["general_prompt"] == "请用老板能快速判断的方式回答，先说结论。"
        assert saved["ai_prompts"]["task_prompts"]["预算平台问答"] == "回答预算平台问题时，先指出风险，再给下一步检查清单。"
    finally:
        if hasattr(app.state, "system_settings_path_override"):
            delattr(app.state, "system_settings_path_override")


def test_dashboard_summary_returns_placeholder_metrics():
    response = client.get("/api/dashboard/summary")

    assert response.status_code == 200
    body = response.json()
    assert body["sales_amount"] == 0
    assert body["cost_amount"] == 0
    assert body["expense_amount"] == 0
    assert body["profit_amount"] == 0
    assert body["uploaded_files"] >= 0
    assert body["error_count"] >= 0
    assert body["warning_count"] == 0
    assert body["message"] == "当前为基础占位数据，后续阶段接入真实汇总结果"
