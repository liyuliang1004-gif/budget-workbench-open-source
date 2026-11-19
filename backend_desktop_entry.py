import argparse

import uvicorn

import backend.main  # noqa: F401


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="预算工作台桌面端后端服务")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    uvicorn.run("backend.main:app", host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
