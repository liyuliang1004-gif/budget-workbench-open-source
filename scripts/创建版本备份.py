from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.services.git_version_service import GitVersionService  # noqa: E402
from backend.services.version_backup_service import VersionBackupService  # noqa: E402


def main() -> None:
    git_status = GitVersionService(PROJECT_ROOT).get_status()
    print("当前 Git 状态：")
    print(f"- 分支：{git_status['current_branch'] or '未知'}")
    print(f"- Commit：{git_status['current_commit_hash'] or '未知'}")
    print(f"- 工作区：{'有未提交修改' if git_status['is_dirty'] else '干净'}")

    if git_status["is_dirty"]:
        print("\n提示：当前工作区有未提交修改，备份会记录该风险，但不会强制退出。")
        for item in git_status["uncommitted_files"]:
            print(f"- {item}")

    remark = input("\n请输入备份备注，直接回车使用“升级前备份”：").strip() or "升级前备份"
    backup = VersionBackupService(PROJECT_ROOT).create_backup(remark)

    print("\n备份已创建：")
    print(backup["backup_path"])
    print("版本信息文件：")
    print(Path(backup["backup_path"]) / "版本信息.json")


if __name__ == "__main__":
    main()
