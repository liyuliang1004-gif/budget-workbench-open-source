from sqlalchemy import inspect
from sqlalchemy.engine import Engine
from sqlalchemy import text

from backend.config import DATABASE_PATH
from backend.database import models
from backend.database.db import Base, engine


def init_database(target_engine: Engine = engine) -> list[str]:
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=target_engine)
    ensure_budget_version_columns(target_engine)
    ensure_uploaded_file_metadata_columns(target_engine)
    ensure_actual_batch_metadata_columns(target_engine)
    return inspect(target_engine).get_table_names()


def ensure_budget_version_columns(target_engine: Engine = engine) -> None:
    inspector = inspect(target_engine)
    versioned_tables = {
        "uploaded_files": "INTEGER NOT NULL DEFAULT 1",
        "sales_budget_details": "INTEGER NOT NULL DEFAULT 1",
        "expense_budget_details": "INTEGER NOT NULL DEFAULT 1",
        "shop_budget_summary": "INTEGER NOT NULL DEFAULT 1",
        "group_budget_summary": "INTEGER NOT NULL DEFAULT 1",
        "department_budget_summary": "INTEGER NOT NULL DEFAULT 1",
    }
    with target_engine.begin() as connection:
        for table_name, column_def in versioned_tables.items():
            if table_name not in inspector.get_table_names():
                continue
            columns = {column["name"] for column in inspector.get_columns(table_name)}
            if "budget_version" not in columns:
                connection.execute(text(f"ALTER TABLE {table_name} ADD COLUMN budget_version {column_def}"))


def ensure_uploaded_file_metadata_columns(target_engine: Engine = engine) -> None:
    inspector = inspect(target_engine)
    if "uploaded_files" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("uploaded_files")}
    with target_engine.begin() as connection:
        if "budget_year" not in columns:
            connection.execute(text("ALTER TABLE uploaded_files ADD COLUMN budget_year INTEGER"))
        if "group_name" not in columns:
            connection.execute(text("ALTER TABLE uploaded_files ADD COLUMN group_name VARCHAR"))


def ensure_actual_batch_metadata_columns(target_engine: Engine = engine) -> None:
    inspector = inspect(target_engine)
    if "actual_import_batches" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("actual_import_batches")}
    with target_engine.begin() as connection:
        if "group_code" not in columns:
            connection.execute(text("ALTER TABLE actual_import_batches ADD COLUMN group_code VARCHAR"))
        if "shop_code" not in columns:
            connection.execute(text("ALTER TABLE actual_import_batches ADD COLUMN shop_code VARCHAR"))


def main() -> None:
    table_names = init_database()
    print(f"数据库路径：{DATABASE_PATH}")
    print("已创建或确认存在的数据表：")
    for table_name in table_names:
        print(f"- {table_name}")


if __name__ == "__main__":
    main()
