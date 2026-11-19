import { useEffect, useState } from "react";
import { getAggregateSummary, importCheckedFiles, runAggregate } from "../api/aggregateApi";
import { getDashboardData } from "../api/dashboardApi";
import DataTable from "../components/DataTable";
import MetricCard from "../components/MetricCard";
import type { AggregateSummary } from "../types/dashboard";
import { formatAmountWan } from "../utils/formatters";

export default function 汇总处理中心() {
  const [summary, setSummary] = useState<AggregateSummary | null>(null);
  const [budgetVersion, setBudgetVersion] = useState(1);
  const [message, setMessage] = useState("");

  const refresh = () => getAggregateSummary(budgetVersion).then(setSummary).catch((error) => setMessage(error.message));
  useEffect(() => { refresh(); }, [budgetVersion]);

  async function run(label: string, task: () => Promise<unknown>) {
    if (!window.confirm(`确认执行${label}？`)) return;
    try {
      const result = await task();
      setMessage(`${label}完成：${JSON.stringify(result)}`);
      await refresh();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : `${label}失败`);
    }
  }

  const total = summary?.department_total;
  return (
    <div className="page-stack workbench-page">
      <section className="page-hero">
        <div>
          <h2>第 {budgetVersion} 版汇总</h2>
          <p>汇总只处理当前预算版本。没有已入库明细时，系统会阻止生成空汇总。</p>
        </div>
        <div className="hero-stat-strip">
          <span><strong>{formatAmountWan(total?.sales_amount || 0)}</strong>销售额</span>
          <span><strong>{formatAmountWan(total?.expense_amount || 0)}</strong>费用额</span>
          <span><strong>{summary?.monthly_trend?.length || 0}</strong>月份记录</span>
        </div>
      </section>

      <section className="panel task-panel">
        <div className="section-heading">
          <div>
            <h2>汇总操作</h2>
            <p className="muted">先导入检查通过的预算表，再运行当前版本汇总计算。</p>
          </div>
        </div>
        <div className="button-row workbench-toolbar">
          <select value={budgetVersion} onChange={(event) => setBudgetVersion(Number(event.target.value))}>
            {[1, 2, 3, 4, 5].map((version) => <option key={version} value={version}>第 {version} 版</option>)}
          </select>
          <button onClick={() => run("批量导入", importCheckedFiles)}>批量导入检查通过文件</button>
          <button onClick={() => run(`第 ${budgetVersion} 版汇总计算`, () => runAggregate(budgetVersion))}>运行汇总计算</button>
          <button className="secondary" onClick={() => getDashboardData().then(() => setMessage("看板数据接口正常"))}>检查看板数据</button>
        </div>
      </section>
      {message && <div className="notice">{message}</div>}
      <section className="metric-grid">
        <MetricCard label="销售额" value={formatAmountWan(total?.sales_amount || 0)} />
        <MetricCard label="成本额" value={formatAmountWan(total?.cost_amount || 0)} />
        <MetricCard label="费用额" value={formatAmountWan(total?.expense_amount || 0)} />
        <MetricCard label="利润额" value={formatAmountWan(total?.profit_amount || 0)} />
      </section>
      <section className="panel data-section">
        <div className="section-heading">
          <div>
            <h2>月度汇总明细</h2>
            <p className="muted">按当前预算版本展示，金额单位统一为万元。</p>
          </div>
        </div>
        <DataTable rows={(summary?.monthly_trend || []) as Record<string, unknown>[]} columns={[
          { key: "year", title: "年度" },
          { key: "month", title: "月份" },
          { key: "budget_version", title: "预算版本", render: (row) => `第 ${row.budget_version || budgetVersion} 版` },
          { key: "sales_amount", title: "销售额（万元）", render: (row) => formatAmountWan(Number(row.sales_amount || 0)) },
          { key: "cost_amount", title: "成本额（万元）", render: (row) => formatAmountWan(Number(row.cost_amount || 0)) },
          { key: "expense_amount", title: "费用额（万元）", render: (row) => formatAmountWan(Number(row.expense_amount || 0)) },
          { key: "profit_amount", title: "利润额（万元）", render: (row) => formatAmountWan(Number(row.profit_amount || 0)) }
        ]} />
      </section>
    </div>
  );
}
