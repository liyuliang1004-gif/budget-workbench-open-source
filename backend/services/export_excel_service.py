from datetime import datetime
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter
from sqlalchemy.orm import Session

from backend.config import BASE_DIR, CHECK_REPORT_RELATIVE_PATH, SUMMARY_REPORT_RELATIVE_PATH
from backend.database.models import (
    ActualExpenseDetail,
    ActualSalesDetail,
    DepartmentBudgetSummary,
    ExpenseBudgetDetail,
    GroupBudgetSummary,
    SalesBudgetDetail,
    ShopBudgetSummary,
    UploadCheckResult,
    UploadedFile,
)
from backend.services.aggregate_service import aggregate_summary, model_to_dict
from backend.services.comparison_service import dashboard_overview


def get_summary_report_dir(app_state=None) -> Path:
    override = getattr(app_state, "summary_report_dir_override", None) if app_state else None
    report_dir = Path(override) if override else BASE_DIR / SUMMARY_REPORT_RELATIVE_PATH
    report_dir.mkdir(parents=True, exist_ok=True)
    return report_dir


def get_check_report_dir(app_state=None) -> Path:
    override = getattr(app_state, "report_dir_override", None) if app_state else None
    report_dir = Path(override) if override else BASE_DIR / CHECK_REPORT_RELATIVE_PATH
    report_dir.mkdir(parents=True, exist_ok=True)
    return report_dir


def timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def style_sheet(ws) -> None:
    ws.freeze_panes = "A2"
    if ws.max_row >= 1:
        ws.auto_filter.ref = ws.dimensions
        for cell in ws[1]:
            cell.font = Font(bold=True)
            cell.fill = PatternFill("solid", fgColor="D9EAF7")
    for column in ws.columns:
        width = max((len(str(cell.value)) if cell.value is not None else 0) for cell in column)
        ws.column_dimensions[get_column_letter(column[0].column)].width = min(max(width + 2, 12), 36)
    for row in ws.iter_rows(min_row=2):
        for cell in row:
            if isinstance(cell.value, float):
                if "率" in str(ws.cell(row=1, column=cell.column).value):
                    cell.number_format = "0.00%"
                else:
                    cell.number_format = "0.00"


def append_rows(wb: Workbook, title: str, headers: list[str], rows: list[list]) -> None:
    ws = wb.create_sheet(title)
    ws.append(headers)
    for row in rows:
        ws.append(["" if value is None else value for value in row])
    style_sheet(ws)


def save_workbook(wb: Workbook, path: Path) -> Path:
    if "Sheet" in wb.sheetnames and len(wb.sheetnames) > 1:
        del wb["Sheet"]
    wb.save(path)
    return path


def summary_headers() -> list[str]:
    return ["年度", "月份", "运营组", "店铺", "销售额", "成本额", "毛利", "费用额", "利润额", "成本率", "费用率", "利润率"]


def summary_row(row, include_shop: bool = True) -> list:
    return [
        row.year,
        row.month,
        getattr(row, "group_code", ""),
        getattr(row, "shop_code", "") if include_shop else "",
        row.sales_amount,
        row.cost_amount,
        row.gross_profit,
        row.expense_amount,
        row.profit_amount,
        row.cost_rate,
        row.expense_rate,
        row.profit_rate,
    ]


def totals_from_rows(rows) -> dict:
    total = {"sales": 0, "cost": 0, "expense": 0, "profit": 0}
    for row in rows:
        total["sales"] += row.sales_amount or 0
        total["cost"] += row.cost_amount or 0
        total["expense"] += row.expense_amount or 0
        total["profit"] += row.profit_amount or 0
    return total


def version_label(budget_version: int | None) -> str:
    return f"第{budget_version}版" if budget_version else "全部版本"


def report_filename(prefix: str, budget_version: int | None) -> str:
    return f"{prefix}_{version_label(budget_version)}_{timestamp()}.xlsx"


def export_department_report(db: Session, year: int | None, app_state=None, budget_version: int | None = None) -> Path:
    report_path = get_summary_report_dir(app_state) / report_filename("部门预算汇总表", budget_version)
    wb = Workbook()
    department_rows = filter_rows(db.query(DepartmentBudgetSummary).all(), year, budget_version)
    group_rows = filter_rows(db.query(GroupBudgetSummary).all(), year, budget_version)
    shop_rows = filter_rows(db.query(ShopBudgetSummary).all(), year, budget_version)
    sales_rows = filter_rows(db.query(SalesBudgetDetail).all(), year, budget_version)
    expense_rows = filter_rows(db.query(ExpenseBudgetDetail).all(), year, budget_version)
    totals = totals_from_rows(department_rows)

    append_rows(
        wb,
        "部门预算总览",
        ["全年销售额", "全年成本额", "全年费用额", "全年利润额", "成本率", "费用率", "利润率"],
        [[totals["sales"], totals["cost"], totals["expense"], totals["profit"], safe_ratio(totals["cost"], totals["sales"]), safe_ratio(totals["expense"], totals["sales"]), safe_ratio(totals["profit"], totals["sales"])]],
    )
    append_rows(wb, "部门月度趋势", summary_headers(), [summary_row(row, include_shop=False) for row in department_rows])
    append_rows(wb, "运营组汇总", summary_headers(), [summary_row(row, include_shop=False) for row in group_rows])
    append_rows(wb, "店铺汇总", summary_headers(), [summary_row(row) for row in shop_rows])
    append_product_sheet(wb, "产品品类汇总", sales_rows)
    append_expense_sheet(wb, "费用汇总", expense_rows)
    append_rows(
        wb,
        "数据来源说明",
        ["项目", "内容"],
        [
            ["数据生成时间", datetime.now().strftime("%Y-%m-%d %H:%M:%S")],
            ["预算版本", version_label(budget_version)],
            ["纳入汇总文件数量", imported_file_query(db, budget_version).count()],
            ["排除文件数量", db.query(UploadedFile).filter(UploadedFile.import_status != "已入库").count()],
            ["系统版本", "0.1.0"],
        ],
    )
    return save_workbook(wb, report_path)


def filter_rows(rows, year: int | None, budget_version: int | None = None):
    return [
        row
        for row in rows
        if (year is None or getattr(row, "year", None) == year)
        and (budget_version is None or getattr(row, "budget_version", None) == budget_version)
    ]


def imported_file_query(db: Session, budget_version: int | None = None):
    query = db.query(UploadedFile).filter(UploadedFile.import_status == "已入库")
    if budget_version is not None:
        query = query.filter(UploadedFile.budget_version == budget_version)
    return query


def safe_ratio(numerator: float, denominator: float):
    return numerator / denominator if denominator else None


def append_product_sheet(wb: Workbook, title: str, rows) -> None:
    grouped = {}
    for row in rows:
        key = (row.category or "未分类", row.product_code, row.product_name)
        item = grouped.setdefault(key, [row.category or "未分类", row.product_code, row.product_name, 0, 0, 0, 0])
        item[3] += row.budget_quantity or 0
        item[4] += row.budget_sales_amount or 0
        item[5] += row.budget_cost_amount or 0
        item[6] += row.budget_gross_profit or 0
    append_rows(wb, title, ["品类", "产品编码", "产品名称", "销量", "销售额", "成本额", "毛利"], list(grouped.values()))


def append_expense_sheet(wb: Workbook, title: str, rows) -> None:
    grouped = {}
    for row in rows:
        key = (row.expense_category, row.expense_item)
        item = grouped.setdefault(key, [row.expense_category, row.expense_item, 0])
        item[2] += row.budget_expense_amount or 0
    append_rows(wb, title, ["费用大类", "费用小项", "费用金额"], list(grouped.values()))


def export_group_report(db: Session, year: int | None, app_state=None, budget_version: int | None = None) -> Path:
    path = get_summary_report_dir(app_state) / report_filename("运营组预算汇总表", budget_version)
    wb = Workbook()
    group_rows = filter_rows(db.query(GroupBudgetSummary).all(), year, budget_version)
    shop_rows = filter_rows(db.query(ShopBudgetSummary).all(), year, budget_version)
    expense_rows = filter_rows(db.query(ExpenseBudgetDetail).all(), year, budget_version)
    append_rows(wb, "运营组总览", summary_headers(), [summary_row(row, include_shop=False) for row in group_rows])
    append_rows(wb, "运营组月度趋势", summary_headers(), [summary_row(row, include_shop=False) for row in group_rows])
    append_rows(wb, "运营组店铺明细", summary_headers(), [summary_row(row) for row in shop_rows])
    append_expense_sheet(wb, "运营组费用结构", expense_rows)
    return save_workbook(wb, path)


def export_shop_report(db: Session, year: int | None, app_state=None, budget_version: int | None = None) -> Path:
    path = get_summary_report_dir(app_state) / report_filename("店铺预算汇总表", budget_version)
    wb = Workbook()
    shop_rows = filter_rows(db.query(ShopBudgetSummary).all(), year, budget_version)
    sales_rows = filter_rows(db.query(SalesBudgetDetail).all(), year, budget_version)
    expense_rows = filter_rows(db.query(ExpenseBudgetDetail).all(), year, budget_version)
    append_rows(wb, "店铺总览", summary_headers(), [summary_row(row) for row in shop_rows])
    append_rows(wb, "店铺月度趋势", summary_headers(), [summary_row(row) for row in shop_rows])
    append_rows(
        wb,
        "店铺产品明细",
        ["年度", "月份", "运营组", "店铺", "品类", "产品编码", "产品名称", "销量", "销售额", "成本额", "毛利"],
        [[row.year, row.month, row.group_code, row.shop_code, row.category, row.product_code, row.product_name, row.budget_quantity, row.budget_sales_amount, row.budget_cost_amount, row.budget_gross_profit] for row in sales_rows],
    )
    append_rows(
        wb,
        "店铺费用明细",
        ["年度", "月份", "运营组", "店铺", "费用大类", "费用小项", "费用金额"],
        [[row.year, row.month, row.group_code, row.shop_code, row.expense_category, row.expense_item, row.budget_expense_amount] for row in expense_rows],
    )
    return save_workbook(wb, path)


def export_product_report(db: Session, year: int | None, app_state=None, budget_version: int | None = None) -> Path:
    path = get_summary_report_dir(app_state) / report_filename("产品品类预算汇总表", budget_version)
    wb = Workbook()
    sales_rows = filter_rows(db.query(SalesBudgetDetail).all(), year, budget_version)
    append_category_summary(wb, sales_rows)
    append_product_sheet(wb, "产品汇总", sales_rows)
    append_monthly_product_trend(wb, "月度品类趋势", sales_rows, "category")
    append_monthly_product_trend(wb, "月度产品趋势", sales_rows, "product_code")
    return save_workbook(wb, path)


def append_category_summary(wb: Workbook, rows) -> None:
    grouped = {}
    for row in rows:
        key = row.category or "未分类"
        item = grouped.setdefault(key, [key, 0, 0, 0, 0])
        item[1] += row.budget_quantity or 0
        item[2] += row.budget_sales_amount or 0
        item[3] += row.budget_cost_amount or 0
        item[4] += row.budget_gross_profit or 0
    append_rows(wb, "品类汇总", ["品类", "销量", "销售额", "成本额", "毛利"], list(grouped.values()))


def append_monthly_product_trend(wb: Workbook, title: str, rows, field: str) -> None:
    grouped = {}
    for row in rows:
        key = getattr(row, field) or "未分类"
        item = grouped.setdefault(key, [key] + [0] * 12)
        item[row.month] += row.budget_sales_amount or 0
    append_rows(wb, title, [field, *[f"{month}月" for month in range(1, 13)]], list(grouped.values()))


def export_expense_report(db: Session, year: int | None, app_state=None, budget_version: int | None = None) -> Path:
    path = get_summary_report_dir(app_state) / report_filename("费用预算汇总表", budget_version)
    wb = Workbook()
    expense_rows = filter_rows(db.query(ExpenseBudgetDetail).all(), year, budget_version)
    total = sum(row.budget_expense_amount or 0 for row in expense_rows)
    append_rows(wb, "费用总览", ["总费用", "说明"], [[total, "费用率需结合销售汇总查看"]])
    append_expense_grouped(wb, "费用大类汇总", expense_rows, "expense_category")
    append_expense_grouped(wb, "费用小项汇总", expense_rows, "expense_item")
    append_expense_monthly(wb, expense_rows)
    append_rows(
        wb,
        "店铺费用明细",
        ["年度", "月份", "运营组", "店铺", "费用大类", "费用小项", "费用金额"],
        [[row.year, row.month, row.group_code, row.shop_code, row.expense_category, row.expense_item, row.budget_expense_amount] for row in expense_rows],
    )
    return save_workbook(wb, path)


def append_expense_grouped(wb: Workbook, title: str, rows, field: str) -> None:
    grouped = {}
    for row in rows:
        key = getattr(row, field) or "未分类"
        grouped[key] = grouped.get(key, 0) + (row.budget_expense_amount or 0)
    append_rows(wb, title, ["项目", "费用金额"], [[key, value] for key, value in grouped.items()])


def append_expense_monthly(wb: Workbook, rows) -> None:
    monthly = {month: 0 for month in range(1, 13)}
    for row in rows:
        monthly[row.month] = monthly.get(row.month, 0) + (row.budget_expense_amount or 0)
    append_rows(wb, "月度费用趋势", ["月份", "费用金额"], [[month, monthly[month]] for month in range(1, 13)])


def export_error_report(db: Session, app_state=None) -> Path:
    path = get_check_report_dir(app_state) / f"错误定位总表_{timestamp()}.xlsx"
    wb = Workbook()
    results = db.query(UploadCheckResult, UploadedFile).join(UploadedFile, UploadCheckResult.file_id == UploadedFile.id).all()
    overview = {}
    for result, uploaded_file in results:
        overview[result.severity] = overview.get(result.severity, 0) + 1
    append_rows(wb, "错误概览", ["严重程度", "数量"], [[key, value] for key, value in overview.items()])
    append_error_detail(wb, "格式错误", [item for item in results if item[0].check_type == "format"])
    append_error_detail(wb, "公式错误", [item for item in results if item[0].check_type == "formula"])
    append_error_detail(wb, "计算错误", [item for item in results if item[0].check_type == "calculation"])
    append_error_detail(wb, "全部错误明细", results)
    return save_workbook(wb, path)


def append_error_detail(wb: Workbook, title: str, rows) -> None:
    headers = ["文件名", "检查类型", "严重程度", "错误编码", "错误说明", "Sheet", "单元格", "行号", "字段名", "产品编码", "产品名称", "月份", "上传值", "期望值", "差异值", "修复建议", "创建时间"]
    data = []
    for result, uploaded_file in rows:
        data.append([uploaded_file.file_name, result.check_type, result.severity, result.error_code, result.error_message, result.sheet_name, result.cell_address, result.row_number, result.column_name, result.product_code, result.product_name, result.month, result.uploaded_value, result.expected_value, result.diff_value, result.suggestion, result.created_at])
    append_rows(wb, title, headers, data)


REPORT_EXPORTERS = {
    "department": export_department_report,
    "group": export_group_report,
    "shop": export_shop_report,
    "product": export_product_report,
    "expense": export_expense_report,
}


def export_excel_reports(db: Session, report_type: str, year: int | None, app_state=None, budget_version: int | None = None) -> list[Path]:
    if report_type == "all":
        paths = [exporter(db, year, app_state, budget_version) for exporter in REPORT_EXPORTERS.values()]
        paths.append(export_error_report(db, app_state))
        return paths
    if report_type == "error":
        return [export_error_report(db, app_state)]
    exporter = REPORT_EXPORTERS.get(report_type)
    if exporter is None:
        raise ValueError("不支持的报表类型。")
    return [exporter(db, year, app_state, budget_version)]


def export_dashboard_view_report(db: Session, filters: dict, app_state=None) -> Path:
    overview = dashboard_overview(db, filters, app_state)
    path = get_summary_report_dir(app_state) / f"当前视角经营总览_{overview['view_mode']}_{timestamp()}.xlsx"
    wb = Workbook()
    append_rows(
        wb,
        "当前视角",
        ["项目", "内容"],
        [
            ["标题", overview["title"]],
            ["视角", overview["view_mode"]],
            ["数据视图", overview["data_view"]],
            ["筛选", " / ".join(overview["breadcrumb"])],
        ],
    )
    append_rows(wb, "核心指标", ["指标", "数值"], [[card["label"], card.get("value")] for card in overview["metric_cards"]])
    for section in overview["ranking_sections"]:
        append_rows_from_dicts(wb, section["title"][:31], section["rows"])
    for section in overview["table_sections"]:
        append_rows_from_dicts(wb, section["title"][:31], section["rows"])
    append_rows(wb, "经营提醒", ["级别", "提醒"], [[item["level"], item["message"]] for item in overview["health_insights"]])
    return save_workbook(wb, path)


def append_rows_from_dicts(wb: Workbook, title: str, rows: list[dict]) -> None:
    if not rows:
        append_rows(wb, title, ["说明"], [["暂无数据"]])
        return
    headers = list(rows[0].keys())
    append_rows(wb, title, headers, [[row.get(header) for header in headers] for row in rows])


def export_custom_report(db: Session, payload: dict, app_state=None) -> Path:
    template = payload.get("template") or "budget_actual_detail"
    year = payload.get("year")
    budget_version = payload.get("budget_version")
    path = get_summary_report_dir(app_state) / f"自定义导出_{template}_{version_label(budget_version)}_{timestamp()}.xlsx"
    wb = Workbook()
    if template == "product_sales_rank":
        rows = filter_rows(db.query(SalesBudgetDetail).all(), year, budget_version)
        grouped = {}
        for row in rows:
            key = row.product_name or row.product_code
            item = grouped.setdefault(key, {"产品": key, "预算销售额": 0.0, "预算销量": 0.0})
            item["预算销售额"] += row.budget_sales_amount or 0
            item["预算销量"] += row.budget_quantity or 0
        append_rows_from_dicts(wb, "产品销售排行榜", sorted(grouped.values(), key=lambda item: item["预算销售额"], reverse=True))
    elif template == "shop_product_detail":
        rows = filter_rows(db.query(SalesBudgetDetail).all(), year, budget_version)
        append_rows_from_dicts(
            wb,
            "店铺产品销售明细",
            [
                {"年度": row.year, "月份": row.month, "运营组": row.group_name or row.group_code, "店铺": row.shop_name or row.shop_code, "产品": row.product_name, "预算销量": row.budget_quantity, "预算销售额": row.budget_sales_amount}
                for row in rows
            ],
        )
    elif template == "group_shop_summary":
        export_rows = filter_rows(db.query(ShopBudgetSummary).all(), year, budget_version)
        append_rows_from_dicts(wb, "运营组店铺汇总", [model_to_dict(row) for row in export_rows])
    elif template == "expense_detail":
        rows = filter_rows(db.query(ExpenseBudgetDetail).all(), year, budget_version)
        append_rows_from_dicts(wb, "费用结构明细", [model_to_dict(row) for row in rows])
    elif template == "error_detail":
        return export_error_report(db, app_state)
    else:
        filters = {
            "year": year,
            "budget_version": budget_version,
            "month": payload.get("month"),
            "group_code": payload.get("group_code"),
            "shop_code": payload.get("shop_code"),
            "product_code": payload.get("product_code"),
            "data_view": payload.get("data_view") or "comparison",
            "top_n": payload.get("top_n") or 20,
        }
        return export_dashboard_view_report(db, filters, app_state)
    return save_workbook(wb, path)
