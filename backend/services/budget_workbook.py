from pathlib import Path

from openpyxl.reader.excel import ExcelReader
from openpyxl.workbook import Workbook
from openpyxl.worksheet._reader import WorkSheetParser, WorksheetReader

BUDGET_SHEETS = {
    "任务分解-数量", "任务分解-金额", "任务分解-成本",
    "费用预算", "利润分解表", "预算价格表",
}


class BudgetSheetParser(WorkSheetParser):
    def parse_row(self, row):
        # Excel can serialize millions of empty, styled cells. Preserve the
        # positions of real cells and hidden-row metadata without loading them.
        contents = [cell for cell in row if len(cell)]
        if all(cell.get("r") for cell in contents):
            row[:] = contents
        if row.get("hidden") not in {"1", "true"}:
            for name in list(row.attrib):
                if name != "r":
                    del row.attrib[name]
        return super().parse_row(row)


class BudgetWorkbookReader(ExcelReader):
    def read_worksheets(self):
        for sheet, relationship in self.parser.find_sheets():
            if relationship.target not in self.valid_files:
                continue
            ws = self.wb.create_sheet(sheet.name)
            ws.sheet_state = sheet.state
            if sheet.name not in BUDGET_SHEETS or "chartsheet" in relationship.Type:
                continue
            with self.archive.open(relationship.target) as source:
                reader = WorksheetReader(ws, source, self.shared_strings, self.data_only, False)
                reader.parser = BudgetSheetParser(
                    source, self.shared_strings, self.data_only, self.wb.epoch,
                    self.wb._date_formats, self.wb._timedelta_formats,
                )
                reader.bind_cells()
                reader.bind_merged_cells()
                reader.bind_col_dimensions()
                reader.bind_row_dimensions()


def load_budget_workbook(path: Path, *, data_only: bool, cache: dict[bool, Workbook] | None = None) -> Workbook:
    if cache is not None and data_only in cache:
        return cache[data_only]
    reader = BudgetWorkbookReader(path, data_only=data_only, keep_links=False)
    try:
        reader.read()
        if cache is not None:
            cache[data_only] = reader.wb
        return reader.wb
    finally:
        reader.archive.close()
