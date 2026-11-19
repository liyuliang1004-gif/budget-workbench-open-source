from io import BytesIO
from pathlib import Path

from fastapi.responses import StreamingResponse
from openpyxl import Workbook, load_workbook

from backend.config import BASE_DIR, SHOP_TEMPLATE_RELATIVE_PATH


ACTUAL_SALES_TEMPLATE_HEADERS = [
    "月份",
    "产品长代码",
    "产品名称",
    "单据编号",
    "单位",
    "发货仓库",
    "购货单位",
    "实发数量",
    "销售单价",
    "销售金额",
    "店铺单位成本",
    "店铺成本金额",
    "店铺",
    "运营组",
]

ACTUAL_EXPENSE_TEMPLATE_HEADERS = ["月份", "运营组", "店铺", "费用明细", "金额"]


def get_shop_template_path(app_state=None) -> Path:
    override = getattr(app_state, "shop_template_path_override", None) if app_state else None
    return Path(override) if override else BASE_DIR / SHOP_TEMPLATE_RELATIVE_PATH


def create_blank_shop_budget_template() -> bytes:
    wb = Workbook()
    wb.properties.keywords = "模板版本:V1.0"
    wb.remove(wb.active)
    months = [f"{month}月" for month in range(1, 13)]

    ws = wb.create_sheet("任务分解-数量")
    ws.append(["产品编码", "品类", "产品名称", "平均销售单价", *months, "年度合计"])

    ws = wb.create_sheet("任务分解-金额")
    ws.append(["产品编码", "品类", "产品名称", *months, "年度合计"])

    ws = wb.create_sheet("任务分解-成本")
    ws.append(["产品编码", "品类", "产品名称", "成本价", *months, "年度合计"])

    ws = wb.create_sheet("费用预算")
    ws.append(["预算项目", "预算小项", *months, "年度合计"])

    ws = wb.create_sheet("利润分解表")
    ws.append(["项目", *months, "年度合计"])
    for item in ["销售额", "成本额", "费用额", "利润", "利润率"]:
        ws.append([item, *([None] * 13)])

    ws = wb.create_sheet("预算价格表")
    ws.append(["产品编码", "品类", "产品名称", "统一出厂价", "补贴标准", "补贴后价格"])

    for ws in wb.worksheets:
        for column_cells in ws.columns:
            ws.column_dimensions[column_cells[0].column_letter].width = 14
        ws.freeze_panes = "A2"

    buffer = BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def read_shop_budget_template(app_state=None) -> bytes:
    template_path = get_shop_template_path(app_state)
    if template_path.exists():
        return template_path.read_bytes()
    return create_blank_shop_budget_template()


def shop_budget_template_response(app_state=None) -> StreamingResponse:
    content = read_shop_budget_template(app_state)
    headers = {"Content-Disposition": 'attachment; filename*=UTF-8\'\'%E5%BA%97%E9%93%BA%E9%A2%84%E7%AE%97%E6%A8%A1%E6%9D%BF_V1.0.xlsx'}
    return StreamingResponse(
        BytesIO(content),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers=headers,
    )


def create_actual_sales_template() -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "实际销售表"
    ws.append(ACTUAL_SALES_TEMPLATE_HEADERS)
    ws.append([1, "P001", "示例产品", "SO20270101001", "件", "默认仓", "示例客户", 100, 19.9, 1990, 11.2, 1120, "示例店铺", "示例运营组"])
    apply_template_style(ws)
    buffer = BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def create_actual_expense_template() -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "实际费用表"
    ws.append(ACTUAL_EXPENSE_TEMPLATE_HEADERS)
    ws.append([1, "示例运营组", "示例店铺", "平台推广费", 3000])
    apply_template_style(ws)
    buffer = BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def create_actual_business_template() -> bytes:
    wb = Workbook()
    sales_ws = wb.active
    sales_ws.title = "实际销售模板"
    sales_ws.append(ACTUAL_SALES_TEMPLATE_HEADERS)
    sales_ws.append([1, "P001", "示例产品", "SO20270101001", "件", "默认仓", "示例客户", 100, 19.9, 1990, 11.2, 1120, "示例店铺", "示例运营组"])

    expense_ws = wb.create_sheet("实际费用模板")
    expense_ws.append(ACTUAL_EXPENSE_TEMPLATE_HEADERS)
    expense_ws.append([1, "示例运营组", "示例店铺", "平台推广费", 3000])

    for ws in wb.worksheets:
        apply_template_style(ws)

    buffer = BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def apply_template_style(ws) -> None:
    ws.freeze_panes = "A2"
    for column_cells in ws.columns:
        ws.column_dimensions[column_cells[0].column_letter].width = max(12, min(18, len(str(column_cells[0].value)) + 4))


def actual_sales_template_response() -> StreamingResponse:
    headers = {"Content-Disposition": "attachment; filename*=UTF-8''%E5%AE%9E%E9%99%85%E9%94%80%E5%94%AE%E8%A1%A8%E6%A8%A1%E6%9D%BF.xlsx"}
    return StreamingResponse(
        BytesIO(create_actual_sales_template()),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers=headers,
    )


def actual_expense_template_response() -> StreamingResponse:
    headers = {"Content-Disposition": "attachment; filename*=UTF-8''%E5%AE%9E%E9%99%85%E8%B4%B9%E7%94%A8%E8%A1%A8%E6%A8%A1%E6%9D%BF.xlsx"}
    return StreamingResponse(
        BytesIO(create_actual_expense_template()),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers=headers,
    )


def actual_business_template_response() -> StreamingResponse:
    headers = {"Content-Disposition": "attachment; filename*=UTF-8''%E5%AE%9E%E9%99%85%E7%BB%8F%E8%90%A5%E6%8A%A5%E8%A1%A8%E6%A8%A1%E6%9D%BF.xlsx"}
    return StreamingResponse(
        BytesIO(create_actual_business_template()),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers=headers,
    )


def validate_template_file(path: Path) -> bool:
    try:
        load_workbook(path, read_only=True)
        return True
    except Exception:
        return False
