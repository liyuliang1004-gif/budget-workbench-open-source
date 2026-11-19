import shutil
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.services.version_backup_service import VersionBackupService  # noqa: E402


def has_database_backup(backup_path: Path) -> bool:
    return any((backup_path / "数据库备份").glob("*.db"))


def main() -> None:
    service = VersionBackupService(PROJECT_ROOT)
    backups = service.list_backups()
    if not backups:
        print("未发现可用备份。请先运行 scripts/创建版本备份.py。")
        return

    print("可用版本备份：")
    for index, backup in enumerate(backups, start=1):
        backup_path = Path(backup["backup_path"])
        database_text = "包含数据库备份" if has_database_backup(backup_path) else "不包含数据库备份"
        print(
            f"{index}. {backup['backup_id']} | {backup.get('created_at', '未知时间')} | "
            f"{backup.get('current_commit_hash') or '未知 commit'} | "
            f"{backup.get('current_commit_message') or '无提交说明'} | {database_text}"
        )

    selected = input("\n请选择要查看的备份编号：").strip()
    if not selected.isdigit() or not 1 <= int(selected) <= len(backups):
        print("选择无效，已退出。")
        return

    backup = backups[int(selected) - 1]
    backup_path = Path(backup["backup_path"])
    database_files = sorted((backup_path / "数据库备份").glob("*.db"))

    print("\n请先停止后端服务，再执行任何回滚动作。")
    print("建议人工确认后执行的 Git 命令：")
    print(f"git reset --hard {backup.get('current_commit_hash') or '<commit_hash>'}")
    print("\n本脚本不会自动执行 git reset --hard。")

    if not database_files:
        print("\n该备份没有数据库文件。")
        print_health_check_suggestion()
        return

    print("\n将要恢复的数据库文件：")
    for db_file in database_files:
        print(f"- {db_file.name}")

    confirm = input("\n是否恢复数据库备份？输入 YES 确认：").strip()
    if confirm != "YES":
        print("未恢复数据库。")
        print_health_check_suggestion()
        return

    target_dir = PROJECT_ROOT / "data" / "database"
    target_dir.mkdir(parents=True, exist_ok=True)
    for db_file in database_files:
        shutil.copy2(db_file, target_dir / db_file.name)
        print(f"已恢复：{target_dir / db_file.name}")

    print_health_check_suggestion()


def print_health_check_suggestion() -> None:
    print("\n回滚后建议检查：")
    print("- 启动后端并访问 /api/health")
    print("- 运行 pytest")
    print("- 运行 npm run build")
    print("- 打开版本管理页面确认 Git 状态")


if __name__ == "__main__":
    main()
