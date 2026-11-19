import { useEffect, useState } from "react";
import { getDashboardData } from "../api/dashboardApi";
import BarChart from "../charts/BarChart";
import ChartCard from "../charts/ChartCard";
import LineChart from "../charts/LineChart";
import PieChart from "../charts/PieChart";
import EmptyState from "../components/EmptyState";
import MetricCard from "../components/MetricCard";
import type { AggregateSummary, DashboardSummary } from "../types/dashboard";

export default function 经营分析看板() {
  const [filters, setFilters] = useState({ year: "2026", month: "", group_code: "", shop_code: "", category: "", product_code: "" });
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [data, setData] = useState<AggregateSummary | null>(null);

  useEffect(() => {
    getDashboardData(filters).then((result) => {
      setSummary(result.summary);
      setData(result.data);
    }).catch(() => {
      setSummary(null);
      setData(null);
    });
  }, [filters]);

  const trend = data?.monthly_trend || [];
  const labels = trend.map((row) => `${row.month}月`);
  return (
    <div className="page-stack">
      <div className="toolbar">
        {Object.keys(filters).map((key) => (
          <input key={key} placeholder={key} value={filters[key as keyof typeof filters]} onChange={(event) => setFilters({ ...filters, [key]: event.target.value })} />
        ))}
      </div>
      <section className="metric-grid">
        <MetricCard label="销售额" value={(summary?.sales_amount || 0).toLocaleString()} />
        <MetricCard label="成本额" value={(summary?.cost_amount || 0).toLocaleString()} />
        <MetricCard label="费用额" value={(summary?.expense_amount || 0).toLocaleString()} />
        <MetricCard label="利润额" value={(summary?.profit_amount || 0).toLocaleString()} />
      </section>
      {trend.length ? (
        <section className="chart-grid">
          <ChartCard title="月度销售额 / 成本 / 费用 / 利润趋势">
            <LineChart labels={labels} series={[
              { name: "销售额", data: trend.map((row) => Number(row.sales_amount || 0)) },
              { name: "成本", data: trend.map((row) => Number(row.cost_amount || 0)) },
              { name: "费用", data: trend.map((row) => Number(row.expense_amount || 0)) },
              { name: "利润", data: trend.map((row) => Number(row.profit_amount || 0)) }
            ]} />
          </ChartCard>
          <ChartCard title="运营组销售额对比"><BarChart labels={data?.group_summary.map((row) => String(row.group_code)) || []} values={data?.group_summary.map((row) => Number(row.sales_amount || 0)) || []} /></ChartCard>
          <ChartCard title="运营组利润对比"><BarChart labels={data?.group_summary.map((row) => String(row.group_code)) || []} values={data?.group_summary.map((row) => Number(row.profit_amount || 0)) || []} name="利润" /></ChartCard>
          <ChartCard title="店铺销售额排名"><BarChart labels={data?.shop_summary.map((row) => String(row.shop_code)) || []} values={data?.shop_summary.map((row) => Number(row.sales_amount || 0)) || []} /></ChartCard>
          <ChartCard title="店铺利润排名"><BarChart labels={data?.shop_summary.map((row) => String(row.shop_code)) || []} values={data?.shop_summary.map((row) => Number(row.profit_amount || 0)) || []} name="利润" /></ChartCard>
          <ChartCard title="品类销售结构"><PieChart data={(data?.category_summary || []).map((row) => ({ name: String(row.key), value: Number(row.sales_amount || 0) }))} /></ChartCard>
          <ChartCard title="费用结构"><PieChart data={(data?.expense_summary?.by_category || []).map((row) => ({ name: String(row.key), value: Number(row.amount || 0) }))} /></ChartCard>
          <ChartCard title="利润率趋势"><LineChart labels={labels} series={[{ name: "利润率", data: trend.map((row) => Number(row.profit_rate || 0)) }]} /></ChartCard>
        </section>
      ) : <EmptyState text="暂无看板数据。请先完成入库和汇总。" />}
    </div>
  );
}
