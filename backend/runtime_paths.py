import os
import platform
from pathlib import Path


APP_DIR_NAME = "经营工作台"
DATA_DIR_ENV = "BUDGET_WORKBENCH_DATA_DIR"
FRONTEND_DIST_DIR_ENV = "BUDGET_WORKBENCH_FRONTEND_DIST_DIR"


def default_user_data_dir(home: Path | None = None, system_name: str | None = None) -> Path:
    user_home = home or Path.home()
    system = system_name or platform.system()
    if system == "Darwin":
        return user_home / "Library" / "Application Support" / APP_DIR_NAME
    if system == "Windows":
        appdata = os.environ.get("APPDATA")
        return (Path(appdata) if appdata else user_home / "AppData" / "Roaming") / APP_DIR_NAME
    return user_home / ".local" / "share" / APP_DIR_NAME


def resolve_data_dir(base_dir: Path) -> Path:
    override = os.environ.get(DATA_DIR_ENV)
    if override:
        return Path(override).expanduser().resolve()
    return (base_dir / "data").resolve()


def resolve_frontend_dist_dir(base_dir: Path) -> Path:
    override = os.environ.get(FRONTEND_DIST_DIR_ENV)
    if override:
        return Path(override).expanduser().resolve()
    return (base_dir / "frontend" / "dist").resolve()


def data_reference(base_dir: Path, data_dir: Path, relative_path: str) -> str:
    project_data_dir = (base_dir / "data").resolve()
    if data_dir.resolve() == project_data_dir:
        return (Path("data") / relative_path).as_posix()
    return str(data_dir / relative_path)
