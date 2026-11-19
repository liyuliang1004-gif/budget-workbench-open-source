from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any, Literal

from mcp.server.mcpserver import MCPServer
from mcp_types import ToolAnnotations
from sqlalchemy.orm import Session

from backend.services.read_only_data_service import query_read_only_records, query_read_only_summary, read_only_catalog


READ_ONLY_ANNOTATIONS = ToolAnnotations(
    readOnlyHint=True,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=False,
)


def create_read_only_mcp_server(
    session_factory: Callable[[], Session],
    app_state_factory: Callable[[], Any] | None = None,
) -> MCPServer:
    server = MCPServer(
        "budget-workbench-read-only",
        title="经营工作台只读数据",
        description="读取预算和实际经营数据，不提供任何写入、删除或修改能力。",
        instructions="所有工具均为只读查询。金额字段使用数据库中的人民币元，比例字段使用小数。",
        version="1.0.0",
    )

    def app_state():
        return app_state_factory() if app_state_factory else None

    def filters(
        year: int,
        budget_version: int = 1,
        month: int | None = None,
        group_code: str | None = None,
        group_name: str | None = None,
        shop_code: str | None = None,
        shop_name: str | None = None,
        product_code: str | None = None,
        product_name: str | None = None,
        data_view: str = "comparison",
        top_n: int = 10,
    ) -> dict[str, Any]:
        return {
            "year": year,
            "budget_version": budget_version,
            "month": month,
            "group_code": group_code,
            "group_name": group_name,
            "shop_code": shop_code,
            "shop_name": shop_name,
            "product_code": product_code,
            "product_name": product_name,
            "data_view": data_view,
            "top_n": top_n,
        }

    @server.resource(
        "budget-workbench://read-only/catalog",
        name="经营工作台只读数据目录",
        description="可查询的数据集、分页限制和安全边界。",
        mime_type="application/json",
    )
    def catalog_resource() -> str:
        return json.dumps(read_only_catalog(), ensure_ascii=False, indent=2)

    @server.tool(
        name="get_business_summary",
        title="读取预算实际经营汇总",
        description="按年度、预算版本、月份、运营组、店铺或产品读取预算、实际、差异、趋势和经营提醒。",
        annotations=READ_ONLY_ANNOTATIONS,
    )
    def get_business_summary(
        year: int,
        budget_version: int = 1,
        month: int | None = None,
        group_code: str | None = None,
        group_name: str | None = None,
        shop_code: str | None = None,
        shop_name: str | None = None,
        product_code: str | None = None,
        product_name: str | None = None,
        data_view: Literal["budget", "actual", "comparison"] = "comparison",
        top_n: int = 10,
    ) -> dict[str, Any]:
        with session_factory() as db:
            return query_read_only_summary(
                db,
                filters(year, budget_version, month, group_code, group_name, shop_code, shop_name, product_code, product_name, data_view, top_n),
                app_state(),
            )

    def records_tool(
        dataset,
        year: int,
        budget_version: int,
        month: int | None,
        group_code: str | None,
        group_name: str | None,
        shop_code: str | None,
        shop_name: str | None,
        product_code: str | None,
        product_name: str | None,
        page: int,
        page_size: int,
    ) -> dict[str, Any]:
        with session_factory() as db:
            return query_read_only_records(
                db,
                dataset,
                filters(year, budget_version, month, group_code, group_name, shop_code, shop_name, product_code, product_name),
                page=page,
                page_size=page_size,
                app_state=app_state(),
            )

    @server.tool(name="list_budget_sales", title="读取预算销售明细", description="分页读取预算销量、销售额、成本额和毛利额。", annotations=READ_ONLY_ANNOTATIONS)
    def list_budget_sales(
        year: int,
        budget_version: int = 1,
        month: int | None = None,
        group_code: str | None = None,
        group_name: str | None = None,
        shop_code: str | None = None,
        shop_name: str | None = None,
        product_code: str | None = None,
        product_name: str | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> dict[str, Any]:
        return records_tool("budget_sales", year, budget_version, month, group_code, group_name, shop_code, shop_name, product_code, product_name, page, page_size)

    @server.tool(name="list_budget_expenses", title="读取预算费用明细", description="分页读取预算费用大项、小项和金额。", annotations=READ_ONLY_ANNOTATIONS)
    def list_budget_expenses(
        year: int,
        budget_version: int = 1,
        month: int | None = None,
        group_code: str | None = None,
        group_name: str | None = None,
        shop_code: str | None = None,
        shop_name: str | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> dict[str, Any]:
        return records_tool("budget_expenses", year, budget_version, month, group_code, group_name, shop_code, shop_name, None, None, page, page_size)

    @server.tool(name="list_actual_sales", title="读取实际销售明细", description="分页读取实际销量、销售额、成本额和毛利额。", annotations=READ_ONLY_ANNOTATIONS)
    def list_actual_sales(
        year: int,
        month: int | None = None,
        group_code: str | None = None,
        group_name: str | None = None,
        shop_code: str | None = None,
        shop_name: str | None = None,
        product_code: str | None = None,
        product_name: str | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> dict[str, Any]:
        return records_tool("actual_sales", year, 1, month, group_code, group_name, shop_code, shop_name, product_code, product_name, page, page_size)

    @server.tool(name="list_actual_expenses", title="读取实际费用明细", description="分页读取实际费用大项、小项和金额。", annotations=READ_ONLY_ANNOTATIONS)
    def list_actual_expenses(
        year: int,
        month: int | None = None,
        group_code: str | None = None,
        group_name: str | None = None,
        shop_code: str | None = None,
        shop_name: str | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> dict[str, Any]:
        return records_tool("actual_expenses", year, 1, month, group_code, group_name, shop_code, shop_name, None, None, page, page_size)

    return server
