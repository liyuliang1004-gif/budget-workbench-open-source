import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from backend.config import BASE_DIR as PROJECT_BASE_DIR, DATA_DIR
from backend.services.git_version_service import GitVersionService


class VersionBackupService:
    CONFIG_FILES = [".env.example", "backend/config.py", "package.json", "requirements.txt"]
    RULE_DIRS = ["docs/03_校验规则", "docs/04_AI分析规则", "docs/05_升级回滚规则"]
    DOC_DIRS = ["docs/00_系统总纲", "docs/06_使用手册"]

    def __init__(self, base_dir: Path, data_dir: Path | None = None):
        self.base_dir = Path(base_dir)
        self.data_dir = Path(data_dir) if data_dir else DATA_DIR if self.base_dir == PROJECT_BASE_DIR else self.base_dir / "data"
        self.backup_root = self.data_dir / "backup"

    def create_backup(self, remark: str = "升级前备份") -> dict[str, Any]:
        created_at = datetime.now()
        backup_id = self._unique_backup_id(created_at)
        backup_dir = self.backup_root / backup_id
        backup_dir.mkdir(parents=True, exist_ok=False)

        git_status = GitVersionService(self.base_dir).get_status()
        database_files = self._copy_database_files(backup_dir)
        config_files = self._copy_files(self.CONFIG_FILES, backup_dir / "配置备份")
        rule_files = self._copy_dirs(self.RULE_DIRS, backup_dir / "规则备份")
        doc_files = self._copy_dirs(self.DOC_DIRS, backup_dir / "文档备份")

        metadata = {
            "backup_id": backup_id,
            "created_at": created_at.strftime("%Y-%m-%d %H:%M:%S"),
            "current_branch": git_status["current_branch"],
            "current_commit_hash": git_status["current_commit_hash"],
            "current_commit_message": git_status["current_commit_message"],
            "current_tag": git_status["current_tag"],
            "is_dirty": git_status["is_dirty"],
            "database_files": database_files or ["未发现数据库文件"],
            "config_files": config_files,
            "rule_files": rule_files,
            "doc_files": doc_files,
            "remark": remark or "升级前备份",
            "backup_path": str(backup_dir),
        }

        self._write_json(backup_dir / "版本信息.json", metadata)
        self._write_readme(backup_dir / "README_备份说明.md", metadata)
        return metadata

    def list_backups(self) -> list[dict[str, Any]]:
        if not self.backup_root.exists():
            return []

        backups = []
        for backup_dir in self.backup_root.iterdir():
            if not backup_dir.is_dir():
                continue
            metadata_path = backup_dir / "版本信息.json"
            if not metadata_path.exists():
                continue
            metadata = self._read_json(metadata_path)
            metadata["backup_path"] = str(backup_dir)
            backups.append(metadata)
        return sorted(backups, key=lambda item: (item.get("created_at", ""), item.get("backup_id", "")), reverse=True)

    def get_backup(self, backup_id: str) -> dict[str, Any] | None:
        backup_dir = self.backup_root / backup_id
        metadata_path = backup_dir / "版本信息.json"
        if not metadata_path.exists():
            return None
        metadata = self._read_json(metadata_path)
        metadata["backup_path"] = str(backup_dir)
        return metadata

    def _unique_backup_id(self, created_at: datetime) -> str:
        base_id = f"版本备份_{created_at.strftime('%Y%m%d_%H%M%S')}"
        backup_id = base_id
        index = 1
        while (self.backup_root / backup_id).exists():
            backup_id = f"{base_id}_{index:02d}"
            index += 1
        return backup_id

    def _copy_database_files(self, backup_dir: Path) -> list[str]:
        database_dir = self.data_dir / "database"
        target_dir = backup_dir / "数据库备份"
        target_dir.mkdir(parents=True, exist_ok=True)
        copied = []
        for source in sorted(database_dir.glob("*.db")) if database_dir.exists() else []:
            shutil.copy2(source, target_dir / source.name)
            copied.append(source.name)
        return copied

    def _copy_files(self, relative_files: list[str], target_root: Path) -> list[str]:
        copied = []
        for relative_file in relative_files:
            source = self.base_dir / relative_file
            if not source.exists() or not source.is_file():
                continue
            target = target_root / relative_file
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            copied.append(relative_file)
        return copied

    def _copy_dirs(self, relative_dirs: list[str], target_root: Path) -> list[str]:
        copied = []
        for relative_dir in relative_dirs:
            source = self.base_dir / relative_dir
            if not source.exists() or not source.is_dir():
                continue
            target = target_root / relative_dir
            shutil.copytree(source, target)
            copied.extend(str(item.relative_to(self.base_dir)) for item in sorted(source.rglob("*")) if item.is_file())
        return copied

    def _write_json(self, path: Path, data: dict[str, Any]) -> None:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def _read_json(self, path: Path) -> dict[str, Any]:
        return json.loads(path.read_text(encoding="utf-8"))

    def _write_readme(self, path: Path, metadata: dict[str, Any]) -> None:
        path.write_text(
            "\n".join(
                [
                    "# 版本备份说明",
                    "",
                    f"- 备份编号：{metadata['backup_id']}",
                    f"- 创建时间：{metadata['created_at']}",
                    f"- 当前分支：{metadata['current_branch'] or '未知'}",
                    f"- 当前 Commit：{metadata['current_commit_hash'] or '未知'}",
                    f"- 备注：{metadata['remark']}",
                    "",
                    "## 回滚原则",
                    "",
                    "本备份不自动执行 Git 回滚。需要回滚代码时，请管理员人工确认后执行建议命令。",
                    "数据库备份可通过 scripts/回滚上一版本.py 辅助恢复。",
                ]
            ),
            encoding="utf-8",
        )
