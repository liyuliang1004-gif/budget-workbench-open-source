import json
import subprocess
from pathlib import Path

from fastapi.testclient import TestClient

from backend.main import app
from backend.services.git_version_service import GitVersionService
from backend.services.version_backup_service import VersionBackupService


def init_repo(path: Path) -> None:
    subprocess.run(["git", "init"], cwd=path, check=True, capture_output=True, text=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=path, check=True)
    (path / "README.md").write_text("test repo\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=path, check=True)
    subprocess.run(["git", "commit", "-m", "initial commit"], cwd=path, check=True, capture_output=True, text=True)


def test_git_status_reads_branch_commit_and_dirty_files(tmp_path):
    init_repo(tmp_path)
    (tmp_path / "changed.txt").write_text("dirty\n", encoding="utf-8")

    status = GitVersionService(tmp_path).get_status()

    assert status["current_branch"] in {"main", "master"}
    assert len(status["current_commit_hash"]) >= 7
    assert status["current_commit_message"] == "initial commit"
    assert status["is_dirty"] is True
    assert any("changed.txt" in item for item in status["uncommitted_files"])
    assert status["recent_commits"][0]["message"] == "initial commit"


def test_git_status_non_git_directory_returns_message(tmp_path):
    status = GitVersionService(tmp_path).get_status()

    assert status["is_git_repository"] is False
    assert status["message"] == "当前目录不是 Git 仓库，请先执行 git init。"


def test_create_backup_writes_metadata_and_excludes_env(tmp_path):
    init_repo(tmp_path)
    (tmp_path / ".env").write_text("DEEPSEEK_API_KEY=secret\n", encoding="utf-8")
    (tmp_path / ".env.example").write_text("DEEPSEEK_API_KEY=\n", encoding="utf-8")
    (tmp_path / "backend").mkdir()
    (tmp_path / "backend" / "config.py").write_text("VERSION = 'test'\n", encoding="utf-8")
    (tmp_path / "package.json").write_text("{}\n", encoding="utf-8")
    (tmp_path / "requirements.txt").write_text("fastapi\n", encoding="utf-8")
    (tmp_path / "data" / "database").mkdir(parents=True)
    (tmp_path / "data" / "database" / "budget.db").write_text("sqlite placeholder\n", encoding="utf-8")
    (tmp_path / "docs" / "03_校验规则").mkdir(parents=True)
    (tmp_path / "docs" / "03_校验规则" / "rule.md").write_text("rule\n", encoding="utf-8")

    service = VersionBackupService(tmp_path)
    backup = service.create_backup("升级前备份")

    backup_dir = Path(backup["backup_path"])
    assert backup_dir.exists()
    assert (backup_dir / "版本信息.json").exists()
    assert (backup_dir / "README_备份说明.md").exists()
    assert not list(backup_dir.rglob(".env"))

    metadata = json.loads((backup_dir / "版本信息.json").read_text(encoding="utf-8"))
    assert metadata["remark"] == "升级前备份"
    assert metadata["database_files"] == ["budget.db"]
    assert "backend/config.py" in metadata["config_files"]


def test_list_backups_returns_latest_first(tmp_path):
    service = VersionBackupService(tmp_path)
    first = service.create_backup("first")
    second = service.create_backup("second")

    backups = service.list_backups()

    assert backups[0]["backup_id"] == second["backup_id"]
    assert backups[1]["backup_id"] == first["backup_id"]


def test_version_api_status_and_backups_return_success(tmp_path):
    app.state.version_backup_base_dir_override = tmp_path
    init_repo(tmp_path)
    try:
        client = TestClient(app)

        status = client.get("/api/version/status")
        assert status.status_code == 200
        assert status.json()["current_branch"] in {"main", "master"}

        created = client.post("/api/version/create-backup", json={"remark": "api backup"})
        assert created.status_code == 200
        backup_id = created.json()["backup_id"]

        backups = client.get("/api/version/backups")
        assert backups.status_code == 200
        assert backups.json()[0]["backup_id"] == backup_id

        detail = client.get(f"/api/version/backups/{backup_id}")
        assert detail.status_code == 200
        assert detail.json()["remark"] == "api backup"
    finally:
        if hasattr(app.state, "version_backup_base_dir_override"):
            delattr(app.state, "version_backup_base_dir_override")
