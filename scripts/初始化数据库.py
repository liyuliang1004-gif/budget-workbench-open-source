from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.config import DATABASE_PATH
from backend.database.init_db import init_database


def main() -> None:
    table_names = init_database()
    print(f"数据库路径：{DATABASE_PATH}")
    print("已创建或确认存在的数据表：")
    for table_name in table_names:
        print(f"- {table_name}")


if __name__ == "__main__":
    main()
