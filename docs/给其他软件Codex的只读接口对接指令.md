# 给其他软件 Codex 的只读接口对接指令

## 使用前由用户填写

先启动「经营工作台」，在顶部菜单选择：

`经营工作台 → 只读数据接口 → 复制 API 地址`

以及：

`经营工作台 → 只读数据接口 → 复制 MCP 地址`

把复制结果填到下面：

```text
API_BASE_URL=<粘贴复制的 API 地址，例如 http://127.0.0.1:8000/api/read-only>
MCP_URL=<粘贴复制的 MCP 地址，例如 http://127.0.0.1:8000/mcp>
```

端口由经营工作台启动时选择，不能假定永远是 `8000`。经营工作台必须保持运行，当前接口只允许同一台电脑上的软件访问。

---

## 可直接复制给另一个软件 Codex 的指令

```text
你正在开发的软件需要接入「经营工作台」的预算与实际经营数据。请直接完成只读数据接入、错误处理和验证，不要直接读取或复制 SQLite 数据库文件，也不要实现任何写入、修改、删除、上传或入库操作。

运行时地址：
- API_BASE_URL=<由用户粘贴「经营工作台 → 只读数据接口 → 复制 API 地址」得到的完整地址>
- MCP_URL=<由用户粘贴「经营工作台 → 只读数据接口 → 复制 MCP 地址」得到的完整地址>

接入原则：
1. 普通业务数据读取优先使用 REST API；如果本软件包含支持 MCP 的 AI/Agent，再接入 Streamable HTTP MCP。
2. 地址只在本机有效，经营工作台必须保持运行。不要把端口硬编码为 8000，把 API_BASE_URL/MCP_URL 做成运行配置或用户设置。
3. 当前接口没有 API Key，且仅绑定 127.0.0.1。不要把它改成局域网或互联网地址。
4. 所有明细都要处理分页：page 从 1 开始，page_size 默认 50、最大 200；持续请求直到 has_more=false。
5. 金额单位为人民币元；比例字段按接口原始数值使用，不要自行乘除或改单位，除非展示层明确格式化。
6. 连接失败时向用户明确提示：「请启动经营工作台，并从菜单重新复制当前接口地址」。

第一步：发现和验证接口
- GET {API_BASE_URL}
- 期望 HTTP 200，响应 mode="read_only"。
- OpenAPI 地址是把 API_BASE_URL 中的 /api/read-only 替换为 /openapi.json。
- Swagger 文档地址是把 API_BASE_URL 中的 /api/read-only 替换为 /docs。

REST API：

1. 经营汇总
GET {API_BASE_URL}/summary
必填：year（2000-2100）
可选：budget_version（默认1）、month（1-12）、group_code、group_name、shop_code、shop_name、product_code、product_name、data_view（budget|actual|comparison，默认comparison）、top_n（1-50，默认10）

2. 预算销售明细
GET {API_BASE_URL}/budget/sales
必填：year
可选：budget_version、month、group_code、group_name、shop_code、shop_name、product_code、product_name、page、page_size

3. 预算费用明细
GET {API_BASE_URL}/budget/expenses
必填：year
可选：budget_version、month、group_code、group_name、shop_code、shop_name、page、page_size

4. 实际销售明细
GET {API_BASE_URL}/actual/sales
必填：year
可选：month、group_code、group_name、shop_code、shop_name、product_code、product_name、page、page_size

5. 实际费用明细
GET {API_BASE_URL}/actual/expenses
必填：year
可选：month、group_code、group_name、shop_code、shop_name、page、page_size

明细响应统一结构：
{
  "mode": "read_only",
  "dataset": "budget_sales | budget_expenses | actual_sales | actual_expenses",
  "filters": {},
  "page": 1,
  "page_size": 50,
  "total": 0,
  "has_more": false,
  "items": []
}

主要明细字段：
- 预算销售：year、budget_version、month、group_code、group_name、shop_code、shop_name、product_code、product_name、category、budget_quantity、average_price、budget_sales_amount、cost_price、budget_cost_amount、budget_gross_profit
- 预算费用：year、budget_version、month、group_code、shop_code、expense_category、expense_item、budget_expense_amount
- 实际销售：year、month、group_name、shop_name、product_code、product_name、category、actual_quantity、actual_sales_amount、actual_cost_amount、actual_gross_profit、actual_sales_unit_price、actual_cost_unit_price
- 实际费用：year、month、group_name、shop_name、expense_category、expense_item、actual_expense_amount

MCP（仅在本软件需要 AI/Agent 工具调用时接入）：
- 传输方式：Streamable HTTP
- URL：MCP_URL
- 工具：get_business_summary、list_budget_sales、list_budget_expenses、list_actual_sales、list_actual_expenses
- 资源：budget-workbench://read-only/catalog
- 所有工具均声明为 readOnlyHint=true、destructiveHint=false。

实现要求：
- 新建一个独立的只读客户端层，不要把 HTTP 请求散落在 UI 组件中。
- 支持配置 API_BASE_URL；如果支持 MCP，也独立配置 MCP_URL。
- 设置合理的连接超时，并区分：未启动/地址失效、参数错误（422）、接口错误和无数据。
- 保留服务返回的原始字段，在展示层再做人民币、百分比和小数位格式化。
- 不要调用经营工作台其他 /api 路由，不要绕过接口访问数据库文件。

验收标准：
1. 经营工作台运行时，GET {API_BASE_URL} 返回 200 和 mode=read_only。
2. 使用 year=2026 调用 summary，能够显示预算、实际或对比汇总；没有数据时正确显示空状态而不是崩溃。
3. 至少完成四类明细的分页读取，并验证 page_size=200。
4. 停止经营工作台后，另一个软件显示可理解的连接提示；重新启动并更新地址后可恢复。
5. 对接口尝试 POST/PUT/DELETE 时不得实现或依赖成功结果；本软件自身也不得提供向该接口写入的代码路径。
6. 如果接入 MCP，能够列出上述 5 个工具，并成功调用 get_business_summary 或任一明细工具。

完成后请向我报告：修改文件、配置位置、REST/MCP 实际连接结果、分页验证结果，以及失败时用户会看到的提示。
```

## 手工连通性测试

把示例地址替换成菜单复制出的实际地址：

```bash
curl "http://127.0.0.1:8000/api/read-only"
curl "http://127.0.0.1:8000/api/read-only/summary?year=2026&budget_version=1&data_view=comparison"
curl "http://127.0.0.1:8000/api/read-only/budget/sales?year=2026&budget_version=1&page=1&page_size=200"
```

第一个请求应返回 `mode: read_only`。如果连接失败，先确认经营工作台仍在运行，再从菜单重新复制地址。
