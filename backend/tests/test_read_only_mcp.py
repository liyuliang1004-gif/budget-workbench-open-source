import asyncio

from mcp.client.client import Client
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database.db import Base
from backend.database.models import ActualSalesDetail, SalesBudgetDetail
from backend.read_only_mcp import create_read_only_mcp_server


def build_mcp_server(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'read_only_mcp.db'}", connect_args={"check_same_thread": False})
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    with session_factory() as db:
        db.add_all(
            [
                SalesBudgetDetail(
                    year=2026, budget_version=1, month=4,
                    group_code="G01", group_name="测试运营组6",
                    shop_code="S01", shop_name="测试旗舰店",
                    product_code="P01", product_name="测试产品",
                    budget_quantity=10, budget_sales_amount=1000,
                    budget_cost_amount=600, budget_gross_profit=400,
                ),
                ActualSalesDetail(
                    year=2026, month=4,
                    group_name="测试运营组6", shop_name="测试旗舰店",
                    product_code="P01", product_name="测试产品",
                    actual_quantity=8, actual_sales_amount=800,
                    actual_cost_amount=480, actual_gross_profit=320,
                    source_batch_id="B01",
                ),
            ]
        )
        db.commit()
    return create_read_only_mcp_server(session_factory)


def test_mcp_exposes_only_read_only_tools_and_catalog(tmp_path):
    server = build_mcp_server(tmp_path)

    async def run():
        async with Client(server) as client:
            tools = await client.list_tools()
            tool_names = {tool.name for tool in tools.tools}
            assert tool_names == {
                "get_business_summary",
                "list_budget_sales",
                "list_budget_expenses",
                "list_actual_sales",
                "list_actual_expenses",
            }
            assert all(tool.annotations.read_only_hint is True for tool in tools.tools)
            assert all(tool.annotations.destructive_hint is False for tool in tools.tools)

            resources = await client.list_resources()
            assert [str(resource.uri) for resource in resources.resources] == ["budget-workbench://read-only/catalog"]

            result = await client.call_tool("list_actual_sales", {"year": 2026, "month": 4})
            assert result.structured_content["total"] == 1
            assert result.structured_content["items"][0]["actual_sales_amount"] == 800

    asyncio.run(run())
