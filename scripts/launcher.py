from __future__ import annotations

import os
import signal
import socket
import subprocess
import sys
import time
import webbrowser
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
BACKEND_HOST = "127.0.0.1"
DEFAULT_BACKEND_PORT = 8000
DEFAULT_FRONTEND_PORT = 5173
APP_DIR_NAME = "经营工作台"


def default_data_dir() -> Path:
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_DIR_NAME
    if os.name == "nt":
        appdata = os.environ.get("APPDATA")
        return (Path(appdata) if appdata else Path.home() / "AppData" / "Roaming") / APP_DIR_NAME
    return Path.home() / ".local" / "share" / APP_DIR_NAME


def port_is_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.2)
        return sock.connect_ex((BACKEND_HOST, port)) != 0


def find_free_port(start: int) -> int:
    for port in range(start, start + 100):
        if port_is_free(port):
            return port
    raise RuntimeError(f"未找到可用端口：{start}-{start + 99}")


def python_executable() -> str:
    venv_python = ROOT_DIR / ".venv" / "bin" / "python"
    if venv_python.exists():
        return str(venv_python)
    return sys.executable


def npm_command() -> str:
    return "npm.cmd" if os.name == "nt" else "npm"


def start_process(command: list[str], env: dict[str, str]) -> subprocess.Popen:
    return subprocess.Popen(
        command,
        cwd=ROOT_DIR,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


def wait_for_port(port: int, timeout: float = 20) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not port_is_free(port):
            return
        time.sleep(0.3)
    raise RuntimeError(f"服务启动超时，端口 {port} 未响应。")


def stop_process(process: subprocess.Popen | None) -> None:
    if process is None or process.poll() is not None:
        return
    try:
        if os.name == "nt":
            process.terminate()
        else:
            os.killpg(process.pid, signal.SIGTERM)
        process.wait(timeout=5)
    except Exception:
        try:
            process.kill()
        except Exception:
            pass


def main() -> int:
    data_dir = Path(os.environ.get("BUDGET_WORKBENCH_DATA_DIR") or default_data_dir()).expanduser().resolve()
    data_dir.mkdir(parents=True, exist_ok=True)
    backend_port = find_free_port(int(os.environ.get("BUDGET_WORKBENCH_BACKEND_PORT") or DEFAULT_BACKEND_PORT))
    frontend_port = find_free_port(int(os.environ.get("BUDGET_WORKBENCH_FRONTEND_PORT") or DEFAULT_FRONTEND_PORT))

    env = os.environ.copy()
    env["BUDGET_WORKBENCH_DATA_DIR"] = str(data_dir)
    env["VITE_API_BASE_URL"] = f"http://{BACKEND_HOST}:{backend_port}"

    backend = None
    frontend = None
    try:
        backend = start_process(
            [
                python_executable(),
                "-m",
                "uvicorn",
                "backend.main:app",
                "--host",
                BACKEND_HOST,
                "--port",
                str(backend_port),
            ],
            env,
        )
        wait_for_port(backend_port)

        dist_dir = ROOT_DIR / "frontend" / "dist"
        if dist_dir.exists():
            frontend_port = backend_port
        else:
            frontend = start_process([npm_command(), "run", "dev", "--", "--host", BACKEND_HOST, "--port", str(frontend_port)], env)
            wait_for_port(frontend_port)

        url = f"http://{BACKEND_HOST}:{frontend_port}/"
        print("经营工作台已启动")
        print(f"页面地址：{url}")
        print(f"正式数据目录：{data_dir}")
        print("关闭本窗口或按 Ctrl+C 可退出系统。")
        webbrowser.open(url)
        while True:
            time.sleep(1)
            if backend.poll() is not None:
                raise RuntimeError("后端服务已退出。")
            if frontend.poll() is not None:
                raise RuntimeError("前端服务已退出。")
    except KeyboardInterrupt:
        return 0
    except Exception as exc:
        print(f"启动失败：{exc}")
        return 1
    finally:
        stop_process(frontend)
        stop_process(backend)


if __name__ == "__main__":
    raise SystemExit(main())
