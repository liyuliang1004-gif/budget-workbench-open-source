from pathlib import Path

from backend.runtime_paths import data_reference, default_user_data_dir, resolve_data_dir, resolve_frontend_dist_dir


def test_default_user_data_dir_uses_macos_application_support():
    path = default_user_data_dir(home=Path("/Users/demo"), system_name="Darwin")

    assert path == Path("/Users/demo/Library/Application Support/经营工作台")


def test_resolve_data_dir_keeps_project_data_by_default(monkeypatch, tmp_path):
    monkeypatch.delenv("BUDGET_WORKBENCH_DATA_DIR", raising=False)

    assert resolve_data_dir(tmp_path) == (tmp_path / "data").resolve()


def test_resolve_data_dir_uses_explicit_data_dir(monkeypatch, tmp_path):
    target = tmp_path / "正式数据"
    monkeypatch.setenv("BUDGET_WORKBENCH_DATA_DIR", str(target))

    assert resolve_data_dir(tmp_path) == target.resolve()


def test_resolve_frontend_dist_dir_uses_explicit_packaged_frontend_dir(monkeypatch, tmp_path):
    frontend_dist = tmp_path / "app" / "frontend" / "dist"
    monkeypatch.setenv("BUDGET_WORKBENCH_FRONTEND_DIST_DIR", str(frontend_dist))

    assert resolve_frontend_dist_dir(tmp_path) == frontend_dist.resolve()


def test_resolve_frontend_dist_dir_defaults_to_project_frontend_dist(monkeypatch, tmp_path):
    monkeypatch.delenv("BUDGET_WORKBENCH_FRONTEND_DIST_DIR", raising=False)

    assert resolve_frontend_dist_dir(tmp_path) == (tmp_path / "frontend" / "dist").resolve()


def test_data_reference_stays_relative_for_project_data_and_absolute_for_external_data(tmp_path):
    assert data_reference(tmp_path, tmp_path / "data", "database/budget_system.db") == "data/database/budget_system.db"
    assert data_reference(tmp_path, tmp_path / "正式数据", "database/budget_system.db") == str(tmp_path / "正式数据" / "database/budget_system.db")
