import subprocess
from pathlib import Path
from shutil import which
from typing import Any


NOT_GIT_MESSAGE = "当前目录不是 Git 仓库，请先执行 git init。"
NO_GIT_COMMAND_MESSAGE = "未检测到 git 命令，请检查本机 Git 安装。"


class GitVersionService:
    def __init__(self, base_dir: Path):
        self.base_dir = Path(base_dir)

    def get_status(self) -> dict[str, Any]:
        if which("git") is None:
            return self._empty_status(False, NO_GIT_COMMAND_MESSAGE)

        if not self._is_git_repository():
            return self._empty_status(False, NOT_GIT_MESSAGE)

        uncommitted_files = self._status_lines()
        return {
            "is_git_repository": True,
            "message": "Git 状态读取成功",
            "current_branch": self._run(["git", "branch", "--show-current"]),
            "current_commit_hash": self._run(["git", "rev-parse", "HEAD"]),
            "current_commit_message": self._run(["git", "log", "-1", "--pretty=%s"]),
            "current_commit_time": self._run(["git", "log", "-1", "--pretty=%ci"]),
            "current_tag": self._current_tag(),
            "is_dirty": bool(uncommitted_files),
            "uncommitted_files": uncommitted_files,
            "recent_commits": self._recent_commits(),
        }

    def _is_git_repository(self) -> bool:
        try:
            subprocess.run(
                ["git", "rev-parse", "--is-inside-work-tree"],
                cwd=self.base_dir,
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError:
            return False
        return True

    def _run(self, command: list[str], default: str = "") -> str:
        try:
            result = subprocess.run(
                command,
                cwd=self.base_dir,
                check=True,
                capture_output=True,
                text=True,
            )
        except (FileNotFoundError, subprocess.CalledProcessError):
            return default
        return result.stdout.strip() or default

    def _status_lines(self) -> list[str]:
        output = self._run(["git", "status", "--short"])
        return [line.strip() for line in output.splitlines() if line.strip()]

    def _current_tag(self) -> str:
        return self._run(["git", "describe", "--tags", "--exact-match"], default="")

    def _recent_commits(self) -> list[dict[str, str]]:
        output = self._run(["git", "log", "-10", "--pretty=%H%x1f%h%x1f%ci%x1f%s"])
        commits: list[dict[str, str]] = []
        for line in output.splitlines():
            parts = line.split("\x1f")
            if len(parts) != 4:
                continue
            commits.append(
                {
                    "hash": parts[0],
                    "short_hash": parts[1],
                    "time": parts[2],
                    "message": parts[3],
                }
            )
        return commits

    def _empty_status(self, is_git_repository: bool, message: str) -> dict[str, Any]:
        return {
            "is_git_repository": is_git_repository,
            "message": message,
            "current_branch": "",
            "current_commit_hash": "",
            "current_commit_message": "",
            "current_commit_time": "",
            "current_tag": "",
            "is_dirty": False,
            "uncommitted_files": [],
            "recent_commits": [],
        }
