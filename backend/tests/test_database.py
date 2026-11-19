from sqlalchemy import create_engine, inspect

from backend.database import models
from backend.database.db import Base


EXPECTED_TABLES = {
    "operation_groups",
    "shops",
    "products",
    "budget_prices",
    "uploaded_files",
    "upload_check_results",
    "sales_budget_details",
    "expense_budget_details",
    "shop_budget_summary",
    "group_budget_summary",
    "department_budget_summary",
    "ai_analysis_tasks",
    "system_versions",
}


def test_database_file_can_be_created(tmp_path):
    db_path = tmp_path / "budget_system.db"
    engine = create_engine(f"sqlite:///{db_path}")

    Base.metadata.create_all(bind=engine)

    assert db_path.exists()


def test_sqlalchemy_models_create_expected_tables(tmp_path):
    db_path = tmp_path / "budget_system.db"
    engine = create_engine(f"sqlite:///{db_path}")

    Base.metadata.create_all(bind=engine)
    table_names = set(inspect(engine).get_table_names())

    assert EXPECTED_TABLES.issubset(table_names)
    assert models.OperationGroup.__tablename__ == "operation_groups"
