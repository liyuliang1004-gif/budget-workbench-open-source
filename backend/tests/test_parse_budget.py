from openpyxl import Workbook

from backend.services.budget_workbook import load_budget_workbook
from backend.services.parse_budget_service import parse_budget_workbook


def test_budget_workbook_skips_empty_formatting_and_keeps_validation_metadata(tmp_path):
    path = tmp_path / "formatted.xlsx"
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "任务分解-金额"
    sheet["B2"] = 100
    sheet["C2"] = "=B2*2"
    sheet["XFD1048575"].number_format = "0.00"
    sheet.row_dimensions[3].hidden = True
    sheet.column_dimensions["D"].hidden = True
    sheet.merge_cells("A1:B1")
    workbook.create_sheet("额外工作表")["A1"] = "不参与入库"
    workbook.save(path)

    parsed = load_budget_workbook(path, data_only=False)
    result = parsed[sheet.title]
    assert result.max_row == 2
    assert result.max_column == 3
    assert result["B2"].value == 100
    assert result["C2"].value == "=B2*2"
    assert result.row_dimensions[3].hidden and result.column_dimensions["D"].hidden
    assert "A1:B1" in result.merged_cells
    assert "额外工作表" in parsed.sheetnames


def create_budget_workbook(path):
    wb = Workbook()
    wb.remove(wb.active)
    months = [f"{month}月" for month in range(1, 13)]

    ws = wb.create_sheet("任务分解-数量")
    ws.append(["产品编码", "品类", "产品名称", "平均销售单价"] + months)
    ws.append(["P001", "食品", "测试产品", 10] + [100, 120] + [0] * 10)

    ws = wb.create_sheet("任务分解-金额")
    ws.append(["产品编码", "品类", "产品名称"] + months)
    ws.append(["P001", "食品", "测试产品"] + [1000, 1200] + [0] * 10)

    ws = wb.create_sheet("任务分解-成本")
    ws.append(["产品编码", "品类", "产品名称", "成本价"] + months)
    ws.append(["P001", "食品", "测试产品", 6] + [600, 720] + [0] * 10)

    ws = wb.create_sheet("费用预算")
    ws.append(["预算项目", "预算小项"] + months)
    ws.append(["推广费", "投流"] + [0.01, 0.02] + [0] * 10)

    ws = wb.create_sheet("预算价格表")
    ws.append(["产品编码", "品类", "产品名称", "统一出厂价", "补贴标准", "补贴后价格"])
    ws.append(["P001", "食品", "测试产品", 10, 0, 6])
    wb.save(path)


def create_template14_workbook(path, *, product_code="P001", product_name="测试产品"):
    wb = Workbook()
    wb.remove(wb.active)
    months = [f"{month}月" for month in range(1, 13)]

    ws = wb.create_sheet("任务分解-金额")
    ws.append(["预算项目", None, None, None, "2025年（万元）", None, None, "2026年（万元）"])
    ws.append(["序号", "产品编码", "品类", "产品名称", "已完成（1-9）", "预计完成（10-12）", "全年", *months, "合计"])
    ws.append([1, product_code, "食品", product_name, 0, 0, 0, 1.25, 2.5, *([0] * 10), 3.75])

    ws = wb.create_sheet("任务分解-数量")
    ws.append([None, None, None, None, "平均销售单价（元）", None, None, None, None, None, None, None, None, None, None, None, 2025, None, None, "2026年"])
    ws.append(["序号", "产品编码", "品类", "产品名称", *months, "已完成（1-9）", "预计完成（10-12）", "全年", *months, "合计"])
    ws.append([1, product_code, "食品", product_name, 10, *([0] * 11), 0, 0, 0, 3, 4, *([0] * 10), 7])

    ws = wb.create_sheet("任务分解-成本")
    ws.append(["预算项目", None, None, None, None, "2025年（万元）", None, None, "2026年（万元）"])
    ws.append(["序号", "产品编码", "品类", "产品名称", "成本价（元）", "已完成（1-9）", "预计完成（10-12）", "全年", *months, "合计"])
    ws.append([1, product_code, "食品", product_name, 6, 0, 0, 0, 0.0018, 0.0024, *([0] * 10), 0.0042])

    ws = wb.create_sheet("费用预算")
    ws.append([None, "11、营业费用预算"])
    ws.append([None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, "（单位：万元）"])
    ws.append([None, "预算项目", "预算小项", "2025年", None, None, "2026年"])
    ws.append([None, None, None, "已完成（1-9）", "预计完成（10-12）", "全年", *months, "合计"])
    ws.append([None, "推广费", "投流", 0, 0, 0, 0.01, 0.02, *([0] * 10), 0.03])
    ws.append([None, "合计", "合计", 0, 0, 0, 0.01, 0.02, *([0] * 10), 0.03])

    ws = wb.create_sheet("利润分解表")
    ws.append(["预算项目", "2025年", None, None, "2026年"])
    ws.append([None, "已完成", "预计完成", "全年", *months, "合计"])
    ws.append(["利润分解", 0, 0, 0, 1.2382, 2.4776, *([0] * 10), 3.7158])
    wb.save(path)


def test_parse_budget_workbook_turns_month_columns_into_detail_rows(tmp_path):
    workbook_path = tmp_path / "G001_S001_2026_预算表.xlsx"
    create_budget_workbook(workbook_path)

    parsed = parse_budget_workbook(
        workbook_path,
        file_id=1,
        year=2026,
        group_code="G001",
        group_name="一组",
        shop_code="S001",
        shop_name="测试店",
    )

    assert len(parsed.sales_rows) == 12
    assert len(parsed.expense_rows) == 12

    january = next(row for row in parsed.sales_rows if row.month == 1)
    assert january.budget_quantity == 100
    assert january.budget_sales_amount == 1000
    assert january.budget_cost_amount == 600
    assert january.budget_gross_profit == 400

    expense = next(row for row in parsed.expense_rows if row.month == 2)
    assert expense.expense_category == "推广费"
    assert expense.expense_item == "投流"
    assert expense.budget_expense_amount == 200


def test_template14_uses_product_name_and_amount_sheet_as_sales_source(tmp_path):
    workbook_path = tmp_path / "1.4预算表.xlsx"
    create_template14_workbook(workbook_path, product_code=None, product_name="无编码产品")

    parsed = parse_budget_workbook(
        workbook_path,
        file_id=1,
        year=2026,
        group_code="G001",
        group_name="一组",
        shop_code="S001",
        shop_name="测试店",
    )

    january = next(row for row in parsed.sales_rows if row.month == 1)
    february = next(row for row in parsed.sales_rows if row.month == 2)
    assert january.product_name == "无编码产品"
    assert january.product_code == "NAME::无编码产品"
    assert january.budget_quantity == 3
    assert january.budget_sales_amount == 12500
    assert january.budget_cost_amount == 18
    assert february.budget_quantity == 4
    assert february.budget_sales_amount == 25000
    assert len(parsed.expense_rows) == 12
