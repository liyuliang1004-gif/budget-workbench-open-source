from pathlib import Path
import platform
import subprocess


def reveal_file_in_system(target: Path) -> None:
    resolved = target.resolve()
    system = platform.system()
    if system == "Windows":
        subprocess.run(["explorer", "/select,", str(resolved)], check=False)
        return
    if system == "Darwin":
        subprocess.run(["open", "-R", str(resolved)], check=False)
        return
    subprocess.run(["xdg-open", str(resolved.parent)], check=False)
