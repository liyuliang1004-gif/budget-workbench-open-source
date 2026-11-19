from datetime import datetime

from sqlalchemy import Column, DateTime, Float, Integer, String, Text

from backend.database.db import Base


def current_time() -> datetime:
    return datetime.now()


class OperationGroup(Base):
    __tablename__ = "operation_groups"

    id = Column(Integer, primary_key=True, index=True)
    group_code = Column(String, unique=True, nullable=False)
    group_name = Column(String, nullable=False)
    manager = Column(String, nullable=True)
    status = Column(String, nullable=False, default="active")
    created_at = Column(DateTime, nullable=False, default=current_time)
    updated_at = Column(DateTime, nullable=False, default=current_time, onupdate=current_time)


class Shop(Base):
    __tablename__ = "shops"

    id = Column(Integer, primary_key=True, index=True)
    shop_code = Column(String, unique=True, nullable=False)
    shop_name = Column(String, nullable=False)
    group_code = Column(String, index=True, nullable=False)
    platform = Column(String, nullable=True)
    manager = Column(String, nullable=True)
    status = Column(String, nullable=False, default="active")
    created_at = Column(DateTime, nullable=False, default=current_time)
    updated_at = Column(DateTime, nullable=False, default=current_time, onupdate=current_time)


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    product_code = Column(String, unique=True, nullable=False)
    product_name = Column(String, nullable=False)
    category = Column(String, nullable=True)
    status = Column(String, nullable=False, default="active")
    created_at = Column(DateTime, nullable=False, default=current_time)
    updated_at = Column(DateTime, nullable=False, default=current_time, onupdate=current_time)


class BudgetPrice(Base):
    __tablename__ = "budget_prices"

    id = Column(Integer, primary_key=True, index=True)
    year = Column(Integer, index=True, nullable=False)
    product_code = Column(String, index=True, nullable=False)
    average_price = Column(Float, nullable=True)
    cost_price = Column(Float, nullable=True)
    internal_price = Column(Float, nullable=True)
    subsidy_price = Column(Float, nullable=True)
    created_at = Column(DateTime, nullable=False, default=current_time)
    updated_at = Column(DateTime, nullable=False, default=current_time, onupdate=current_time)


class UploadedFile(Base):
    __tablename__ = "uploaded_files"

    id = Column(Integer, primary_key=True, index=True)
    file_name = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    file_type = Column(String, nullable=False)
    file_hash = Column(String, index=True, nullable=False)
    shop_code = Column(String, nullable=True)
    shop_name = Column(String, nullable=True)
    group_code = Column(String, nullable=True)
    group_name = Column(String, nullable=True)
    template_version = Column(String, nullable=True)
    budget_year = Column(Integer, nullable=True)
    budget_version = Column(Integer, nullable=False, default=1)
    upload_time = Column(DateTime, nullable=False, default=current_time)
    check_status = Column(String, nullable=False, default="待检查")
    import_status = Column(String, nullable=False, default="未入库")
    error_count = Column(Integer, nullable=False, default=0)
    warning_count = Column(Integer, nullable=False, default=0)


class UploadCheckResult(Base):
    __tablename__ = "upload_check_results"

    id = Column(Integer, primary_key=True, index=True)
    file_id = Column(Integer, index=True, nullable=False)
    check_type = Column(String, nullable=False)
    severity = Column(String, nullable=False)
    error_code = Column(String, nullable=True)
    error_message = Column(Text, nullable=False)
    sheet_name = Column(String, nullable=True)
    cell_address = Column(String, nullable=True)
    row_number = Column(Integer, nullable=True)
    column_name = Column(String, nullable=True)
    product_code = Column(String, nullable=True)
    product_name = Column(String, nullable=True)
    month = Column(Integer, nullable=True)
    uploaded_value = Column(String, nullable=True)
    expected_value = Column(String, nullable=True)
    diff_value = Column(String, nullable=True)
    suggestion = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=current_time)


class SalesBudgetDetail(Base):
    __tablename__ = "sales_budget_details"

    id = Column(Integer, primary_key=True, index=True)
    year = Column(Integer, index=True, nullable=False)
    month = Column(Integer, index=True, nullable=False)
    group_code = Column(String, index=True, nullable=False)
    group_name = Column(String, nullable=True)
    shop_code = Column(String, index=True, nullable=False)
    shop_name = Column(String, nullable=True)
    product_code = Column(String, index=True, nullable=False)
    product_name = Column(String, nullable=True)
    category = Column(String, nullable=True)
    budget_quantity = Column(Float, nullable=False)
    average_price = Column(Float, nullable=True)
    budget_sales_amount = Column(Float, nullable=False)
    cost_price = Column(Float, nullable=True)
    budget_cost_amount = Column(Float, nullable=True)
    budget_gross_profit = Column(Float, nullable=True)
    source_file_id = Column(Integer, nullable=True)
    budget_version = Column(Integer, index=True, nullable=False, default=1)
    created_at = Column(DateTime, nullable=False, default=current_time)


class ExpenseBudgetDetail(Base):
    __tablename__ = "expense_budget_details"

    id = Column(Integer, primary_key=True, index=True)
    year = Column(Integer, index=True, nullable=False)
    month = Column(Integer, index=True, nullable=False)
    group_code = Column(String, index=True, nullable=False)
    shop_code = Column(String, index=True, nullable=False)
    expense_category = Column(String, nullable=False)
    expense_item = Column(String, nullable=False)
    budget_expense_amount = Column(Float, nullable=False)
    source_file_id = Column(Integer, nullable=True)
    budget_version = Column(Integer, index=True, nullable=False, default=1)
    created_at = Column(DateTime, nullable=False, default=current_time)


class ShopBudgetSummary(Base):
    __tablename__ = "shop_budget_summary"

    id = Column(Integer, primary_key=True, index=True)
    year = Column(Integer, index=True, nullable=False)
    month = Column(Integer, index=True, nullable=False)
    group_code = Column(String, index=True, nullable=False)
    shop_code = Column(String, index=True, nullable=False)
    budget_version = Column(Integer, index=True, nullable=False, default=1)
    sales_amount = Column(Float, nullable=False)
    cost_amount = Column(Float, nullable=False)
    gross_profit = Column(Float, nullable=False)
    expense_amount = Column(Float, nullable=False)
    profit_amount = Column(Float, nullable=False)
    cost_rate = Column(Float, nullable=True)
    expense_rate = Column(Float, nullable=True)
    profit_rate = Column(Float, nullable=True)
    created_at = Column(DateTime, nullable=False, default=current_time)


class GroupBudgetSummary(Base):
    __tablename__ = "group_budget_summary"

    id = Column(Integer, primary_key=True, index=True)
    year = Column(Integer, index=True, nullable=False)
    month = Column(Integer, index=True, nullable=False)
    group_code = Column(String, index=True, nullable=False)
    budget_version = Column(Integer, index=True, nullable=False, default=1)
    sales_amount = Column(Float, nullable=False)
    cost_amount = Column(Float, nullable=False)
    gross_profit = Column(Float, nullable=False)
    expense_amount = Column(Float, nullable=False)
    profit_amount = Column(Float, nullable=False)
    cost_rate = Column(Float, nullable=True)
    expense_rate = Column(Float, nullable=True)
    profit_rate = Column(Float, nullable=True)
    created_at = Column(DateTime, nullable=False, default=current_time)


class DepartmentBudgetSummary(Base):
    __tablename__ = "department_budget_summary"

    id = Column(Integer, primary_key=True, index=True)
    year = Column(Integer, index=True, nullable=False)
    month = Column(Integer, index=True, nullable=False)
    budget_version = Column(Integer, index=True, nullable=False, default=1)
    sales_amount = Column(Float, nullable=False)
    cost_amount = Column(Float, nullable=False)
    gross_profit = Column(Float, nullable=False)
    expense_amount = Column(Float, nullable=False)
    profit_amount = Column(Float, nullable=False)
    cost_rate = Column(Float, nullable=True)
    expense_rate = Column(Float, nullable=True)
    profit_rate = Column(Float, nullable=True)
    created_at = Column(DateTime, nullable=False, default=current_time)


class ActualImportBatch(Base):
    __tablename__ = "actual_import_batches"

    id = Column(Integer, primary_key=True, index=True)
    batch_id = Column(String, unique=True, index=True, nullable=False)
    file_name = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    file_type = Column(String, index=True, nullable=False)
    year = Column(Integer, index=True, nullable=False)
    month = Column(Integer, nullable=True)
    group_code = Column(String, nullable=True)
    group_name = Column(String, nullable=True)
    shop_code = Column(String, nullable=True)
    shop_name = Column(String, nullable=True)
    status = Column(String, nullable=False, default="uploaded")
    row_count = Column(Integer, nullable=False, default=0)
    error_count = Column(Integer, nullable=False, default=0)
    warning_count = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=current_time)
    imported_at = Column(DateTime, nullable=True)


class ActualSalesRawLine(Base):
    __tablename__ = "actual_sales_raw_lines"

    id = Column(Integer, primary_key=True, index=True)
    batch_id = Column(String, index=True, nullable=False)
    year = Column(Integer, index=True, nullable=False)
    month = Column(Integer, index=True, nullable=False)
    group_name = Column(String, index=True, nullable=False)
    shop_name = Column(String, index=True, nullable=False)
    product_code = Column(String, index=True, nullable=False)
    product_name = Column(String, nullable=False)
    document_no = Column(String, nullable=True)
    unit = Column(String, nullable=True)
    warehouse = Column(String, nullable=True)
    customer_name = Column(String, nullable=True)
    actual_quantity = Column(Float, nullable=False)
    actual_sales_amount = Column(Float, nullable=False)
    actual_cost_amount = Column(Float, nullable=False)
    raw_sales_unit_price = Column(Float, nullable=True)
    raw_cost_unit_price = Column(Float, nullable=True)
    calculated_sales_unit_price = Column(Float, nullable=True)
    calculated_cost_unit_price = Column(Float, nullable=True)
    source_row_number = Column(Integer, nullable=True)
    warning_message = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=current_time)


class ActualSalesDetail(Base):
    __tablename__ = "actual_sales_details"

    id = Column(Integer, primary_key=True, index=True)
    year = Column(Integer, index=True, nullable=False)
    month = Column(Integer, index=True, nullable=False)
    group_name = Column(String, index=True, nullable=False)
    shop_name = Column(String, index=True, nullable=False)
    product_code = Column(String, index=True, nullable=False)
    product_name = Column(String, nullable=False)
    category = Column(String, nullable=True)
    actual_quantity = Column(Float, nullable=False)
    actual_sales_amount = Column(Float, nullable=False)
    actual_cost_amount = Column(Float, nullable=False)
    actual_gross_profit = Column(Float, nullable=False)
    actual_sales_unit_price = Column(Float, nullable=True)
    actual_cost_unit_price = Column(Float, nullable=True)
    source_batch_id = Column(String, index=True, nullable=False)
    created_at = Column(DateTime, nullable=False, default=current_time)


class ActualExpenseDetail(Base):
    __tablename__ = "actual_expense_details"

    id = Column(Integer, primary_key=True, index=True)
    year = Column(Integer, index=True, nullable=False)
    month = Column(Integer, index=True, nullable=False)
    group_name = Column(String, index=True, nullable=False)
    shop_name = Column(String, index=True, nullable=False)
    expense_category = Column(String, nullable=False)
    expense_item = Column(String, nullable=False)
    actual_expense_amount = Column(Float, nullable=False)
    source_batch_id = Column(String, index=True, nullable=False)
    source_row_number = Column(Integer, nullable=True)
    created_at = Column(DateTime, nullable=False, default=current_time)


class BudgetActualComparison(Base):
    __tablename__ = "budget_actual_comparison"

    id = Column(Integer, primary_key=True, index=True)
    year = Column(Integer, index=True, nullable=False)
    budget_version = Column(Integer, index=True, nullable=False, default=1)
    month = Column(Integer, index=True, nullable=True)
    group_name = Column(String, index=True, nullable=True)
    shop_name = Column(String, index=True, nullable=True)
    product_code = Column(String, index=True, nullable=True)
    product_name = Column(String, nullable=True)
    category = Column(String, nullable=True)
    budget_quantity = Column(Float, nullable=True)
    actual_quantity = Column(Float, nullable=True)
    quantity_diff = Column(Float, nullable=True)
    quantity_completion_rate = Column(Float, nullable=True)
    budget_sales_amount = Column(Float, nullable=True)
    actual_sales_amount = Column(Float, nullable=True)
    sales_diff = Column(Float, nullable=True)
    sales_completion_rate = Column(Float, nullable=True)
    budget_cost_amount = Column(Float, nullable=True)
    actual_cost_amount = Column(Float, nullable=True)
    cost_diff = Column(Float, nullable=True)
    cost_usage_rate = Column(Float, nullable=True)
    budget_gross_profit = Column(Float, nullable=True)
    actual_gross_profit = Column(Float, nullable=True)
    gross_profit_diff = Column(Float, nullable=True)
    budget_expense_amount = Column(Float, nullable=True)
    actual_expense_amount = Column(Float, nullable=True)
    expense_diff = Column(Float, nullable=True)
    expense_usage_rate = Column(Float, nullable=True)
    budget_profit_amount = Column(Float, nullable=True)
    actual_profit_amount = Column(Float, nullable=True)
    profit_diff = Column(Float, nullable=True)
    budget_profit_rate = Column(Float, nullable=True)
    actual_profit_rate = Column(Float, nullable=True)
    profit_rate_diff = Column(Float, nullable=True)
    comparison_level = Column(String, index=True, nullable=False)
    created_at = Column(DateTime, nullable=False, default=current_time)


class AIAnalysisTask(Base):
    __tablename__ = "ai_analysis_tasks"

    id = Column(Integer, primary_key=True, index=True)
    task_type = Column(String, nullable=False)
    scope_type = Column(String, nullable=False)
    scope_value = Column(String, nullable=True)
    question = Column(Text, nullable=True)
    input_data_snapshot = Column(Text, nullable=True)
    ai_result = Column(Text, nullable=True)
    model_name = Column(String, nullable=True)
    status = Column(String, nullable=False, default="pending")
    created_at = Column(DateTime, nullable=False, default=current_time)
    finished_at = Column(DateTime, nullable=True)


class SystemVersion(Base):
    __tablename__ = "system_versions"

    id = Column(Integer, primary_key=True, index=True)
    version_name = Column(String, nullable=False)
    git_commit_hash = Column(String, nullable=True)
    branch_name = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    status = Column(String, nullable=False)
    created_at = Column(DateTime, nullable=False, default=current_time)
