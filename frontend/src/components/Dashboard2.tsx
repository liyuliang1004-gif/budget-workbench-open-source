import BarChart from "../charts/BarChart";
import LineChart from "../charts/LineChart";
import DataTable from "./DataTable";
import MetricCard from "./MetricCard";
import { formatAmountWan, formatPercent } from "../utils/formatters";
import type { OperationGroupOption } from "../types/upload";
import type { DashboardChartType, DashboardOverview, DashboardWidgetData } from "../types/dashboard";

export interface DashboardFilters {
  year: string;
  budget_version: string;
  month: string;
  group_code: string;
  shop_code: string;
  product_name: string;
  data_view: string;
}

export function DashboardFilterBar({
  filters,
  groups,
  onChange,
  onRefresh,
  onExport,
  onAiOpen,
  onConfigure,
  productOptions = []
}: {
  filters: DashboardFilters;
  groups: OperationGroupOption[];
  productOptions?: Array<{ product_key?: string; product_code?: string | null; product_name: string }>;
  onChange: (filters: DashboardFilters) => void;
  onRefresh: () => void;
  onExport: () => void;
  onAiOpen: () => void;
  onConfigure: () => void;
}) {
  const selectedGroup = groups.find((group) => group.group_code === filters.group_code);
  const shops = selectedGroup?.shops || groups.flatMap((group) => group.shops || []);
  return (
    <div className="dashboard-filter-bar">
      <label>年份<select value={filters.year} onChange={(event) => onChange({ ...filters, year: event.target.value })}>{[2026, 2027, 2028].map((year) => <option key={year} value={year}>{year}年</option>)}</select></label>
      <label>预算版本<select value={filters.budget_version} onChange={(event) => onChange({ ...filters, budget_version: event.target.value })}>{[1, 2, 3, 4, 5].map((version) => <option key={version} value={version}>第{version}版</option>)}</select></label>
      <label>月份<select value={filters.month} onChange={(event) => onChange({ ...filters, month: event.target.value })}><option value="">全年(1-12月)</option>{Array.from({ length: 12 }, (_, index) => index + 1).map((month) => <option key={month} value={month}>{month}月</option>)}</select></label>
      <label>运营组<select value={filters.group_code} onChange={(event) => onChange({ ...filters, group_code: event.target.value, shop_code: "" })}><option value="">全部运营组</option>{groups.map((group) => <option key={group.group_code} value={group.group_code}>{group.group_name}</option>)}</select></label>
      <label>店铺<select value={filters.shop_code} onChange={(event) => onChange({ ...filters, shop_code: event.target.value })}><option value="">全部店铺</option>{shops.map((shop) => <option key={shop.shop_code} value={shop.shop_code}>{shop.shop_name}</option>)}</select></label>
      <label>产品
        <input list="dashboard-product-options" value={filters.product_name} onChange={(event) => onChange({ ...filters, product_name: event.target.value })} placeholder="搜索或选择产品" />
        <datalist id="dashboard-product-options">
          {productOptions.map((item, index) => <option key={item.product_key || `${item.product_code || "name"}-${item.product_name}-${index}`} value={item.product_name} />)}
        </datalist>
      </label>
      <label>数据视图<select className="primary-select" value={filters.data_view} onChange={(event) => onChange({ ...filters, data_view: event.target.value })}><option value="comparison">预算 vs 实际</option><option value="budget">预算</option><option value="actual">实际</option></select></label>
      <div className="dashboard-actions">
        <button onClick={onRefresh}>刷新</button>
        <button className="utility-action" onClick={onConfigure}>配置首页</button>
        <button className="utility-action" onClick={onExport}>导出当前视角</button>
        <button className="primary-action" onClick={onAiOpen}>AI分析</button>
      </div>
    </div>
  );
}

function findMetricCard(overview: DashboardOverview, label: string) {
  return overview.metric_cards.find((card) => String(card.label || "").includes(label));
}

function metricSummary(overview: DashboardOverview) {
  return [
    findMetricCard(overview, "销售额"),
    findMetricCard(overview, "利润额"),
    findMetricCard(overview, "同期达成率"),
  ].filter(Boolean) as Array<Record<string, number | string | null>>;
}

export function ViewModeHeader({ overview }: { overview: DashboardOverview }) {
  const summary = metricSummary(overview);
  const topInsight = overview.health_insights[0]?.message || "暂无需要优先处理的经营提醒。";
  return (
    <section className="dashboard-hero">
      <div>
        <div className="dashboard-title-row"><h2>{overview.title}</h2><span className="view-mode-badge">当前视角</span></div>
        <p>当前筛选：{overview.breadcrumb.join(" / ")}</p>
      </div>
      <div className="dashboard-hero-summary" aria-label="当前经营摘要">
        {summary.map((card) => (
          <div className="hero-summary-item" key={String(card.id || card.label)}>
            <span>{card.label}</span>
            <strong>{formatCardValue(card.value, card.format)}</strong>
            {card.sub_label && <small>{card.sub_label} {formatCardValue(card.sub_value, card.format)}</small>}
          </div>
        ))}
        <div className="hero-summary-item insight">
          <span>优先提醒</span>
          <strong>{topInsight}</strong>
        </div>
      </div>
    </section>
  );
}

export function ActualCoverageBanner({ overview }: { overview: DashboardOverview }) {
  if (overview.data_view === "budget") return null;
  const coverage = overview.actual_coverage;
  if (!coverage) return null;
  return (
    <section className={`coverage-banner ${coverage.has_actual_data ? "" : "warning"}`}>
      <strong>实际数据覆盖</strong>
      <span>{coverage.message}</span>
      {coverage.has_actual_data && (
        <small>
          销售记录 {coverage.sales_row_count} 条，费用记录 {coverage.expense_row_count} 条
          {coverage.groups.length ? `；运营组：${coverage.groups.join("、")}` : ""}
          {coverage.shops.length ? `；店铺：${coverage.shops.join("、")}` : ""}
        </small>
      )}
    </section>
  );
}

function formatCardValue(value: unknown, format?: unknown) {
  return format === "percent" ? formatPercent(value as number | null) : formatAmountWan(value as number | null);
}

export function MetricCards2({ overview }: { overview: DashboardOverview }) {
  return (
    <section className="metric-grid dashboard-metrics">
      {overview.metric_cards.map((card) => (
        <MetricCard
          key={String(card.id)}
          label={String(card.label)}
          value={formatCardValue(card.value, card.format)}
          hint={card.sub_label ? `${card.sub_label} ${formatCardValue(card.sub_value, card.format)}` : card.rate !== undefined ? `比例 ${formatPercent(card.rate as number)}` : undefined}
        />
      ))}
    </section>
  );
}

function tooltipExtras(section: DashboardOverview["trend_sections"][number]) {
  if (!section.id.includes("comparison")) return section.rows.map(() => []);
  return section.rows.map((row) => {
    const numberOrNull = (value: unknown) => value === null || value === undefined ? null : Number(value);
    const diff = (actual: unknown, budget: unknown) => {
      const actualValue = numberOrNull(actual);
      const budgetValue = numberOrNull(budget);
      return actualValue === null || budgetValue === null ? null : actualValue - budgetValue;
    };
    const rate = (actual: unknown, budget: unknown) => {
      const actualValue = numberOrNull(actual);
      const budgetValue = numberOrNull(budget);
      return actualValue === null || !budgetValue ? null : actualValue / budgetValue;
    };
    if (section.id.includes("sales")) {
      return [
        { label: "差异", value: row.sales_diff as number | null ?? diff(row.actual_sales_amount, row.budget_sales_amount), format: "amount" as const },
        { label: "达成率", value: row.sales_completion_rate as number | null ?? rate(row.actual_sales_amount, row.budget_sales_amount), format: "percent" as const },
      ];
    }
    if (section.id.includes("profit")) return [{ label: "差异", value: row.profit_diff as number | null ?? diff(row.actual_profit_amount, row.budget_profit_amount), format: "amount" as const }];
    if (section.id.includes("expense")) {
      return [
        { label: "差异", value: row.expense_diff as number | null ?? diff(row.actual_expense_amount, row.budget_expense_amount), format: "amount" as const },
        { label: "使用率", value: row.expense_usage_rate as number | null ?? rate(row.actual_expense_amount, row.budget_expense_amount), format: "percent" as const },
      ];
    }
    if (section.id.includes("cost")) {
      return [
        { label: "差异", value: row.cost_diff as number | null ?? diff(row.actual_cost_amount, row.budget_cost_amount), format: "amount" as const },
        { label: "使用率", value: row.cost_usage_rate as number | null ?? rate(row.actual_cost_amount, row.budget_cost_amount), format: "percent" as const },
      ];
    }
    return [];
  });
}

function selectBarSeries(section: DashboardOverview["trend_sections"][number]) {
  return section.series.find((item) => item.name.includes("实际") && !item.name.includes("未上传")) || section.series[0];
}

function isPendingUploadSeries(item: DashboardOverview["trend_sections"][number]["series"][number]) {
  return item.name.includes("未上传");
}

function compactMissingRanges(indexes: number[]) {
  if (!indexes.length) return [];
  const ranges: Array<{ start: number; end: number; label: string }> = [];
  let start = indexes[0];
  let previous = indexes[0];
  indexes.slice(1).forEach((index) => {
    if (index === previous + 1) {
      previous = index;
      return;
    }
    ranges.push({ start, end: previous, label: "未上传实际数据" });
    start = index;
    previous = index;
  });
  ranges.push({ start, end: previous, label: "未上传实际数据" });
  return ranges;
}

function missingActualRanges(section: DashboardOverview["trend_sections"][number]) {
  const pendingSeries = section.series.find(isPendingUploadSeries);
  if (pendingSeries) {
    const indexes = section.rows
      .map((row, index) => row[pendingSeries.field] === null || row[pendingSeries.field] === undefined ? -1 : index)
      .filter((index) => index >= 0);
    return compactMissingRanges(indexes);
  }

  const actualSeries = section.series.filter((item) => item.name.includes("实际") && !isPendingUploadSeries(item));
  if (!actualSeries.length) return [];
  const indexes = section.rows
    .map((row, index) => actualSeries.every((item) => row[item.field] === null || row[item.field] === undefined) ? index : -1)
    .filter((index) => index >= 0);
  return compactMissingRanges(indexes);
}

function amountRankValue(row: Record<string, number | string | null>, sectionId: string) {
  if (sectionId === "expense_overrun") {
    return [Number(row.actual_expense_amount || 0), Number(row.budget_expense_amount || 0)];
  }
  return [Number(row.actual_sales_amount || 0), Number(row.budget_sales_amount || 0)];
}

function sortAmountRows(rows: Array<Record<string, number | string | null>>, sectionId: string) {
  return [...rows].sort((a, b) => {
    const [aActual, aBudget] = amountRankValue(a, sectionId);
    const [bActual, bBudget] = amountRankValue(b, sectionId);
    return (bActual - aActual) || (bBudget - aBudget);
  });
}

const lineLikeChartTypes: DashboardChartType[] = ["line", "smooth_line", "area", "step_line", "scatter"];

function isLineLikeChart(type: DashboardChartType | undefined): type is "line" | "smooth_line" | "area" | "step_line" | "scatter" {
  return lineLikeChartTypes.includes(type || "line");
}

export function TrendComparisonChart({ section, chartType = "line" }: { section: DashboardOverview["trend_sections"][number]; chartType?: DashboardChartType }) {
  const labels = section.rows.map((row) => `${row[section.x_field]}月`);
  const visibleSeries = section.series.filter((item) => !isPendingUploadSeries(item));
  if (chartType === "bar" || chartType === "horizontal_bar") {
    const item = selectBarSeries({ ...section, series: visibleSeries });
    const rawValues = section.rows.map((row) => row[item.field] === null || row[item.field] === undefined ? null : Number(row[item.field]));
    const values = rawValues.map((value) => Number(value || 0) / 10000);
    return <BarChart labels={labels} values={values} rawValues={rawValues} name={item.name} horizontal={chartType === "horizontal_bar"} format="amount" />;
  }
  const series = visibleSeries.map((item) => ({
    name: item.name,
    dashed: item.dashed,
    format: "amount" as const,
    rawData: section.rows.map((row) => row[item.field] === null || row[item.field] === undefined ? null : Number(row[item.field])),
    data: section.rows.map((row) => row[item.field] === null || row[item.field] === undefined ? null : Number(row[item.field]) / 10000)
  }));
  return (
    <LineChart
      labels={labels}
      series={series}
      valueFormatter={(value) => `${value.toFixed(2)} 万元`}
      extraTooltipRows={tooltipExtras(section)}
      variant={isLineLikeChart(chartType) ? chartType : "line"}
      missingRanges={missingActualRanges(section)}
    />
  );
}

export function RankingTableCard({ section, chartType = "bar_table" }: { section: DashboardOverview["ranking_sections"][number]; chartType?: DashboardChartType }) {
  const rows = sortAmountRows(section.rows, section.id).slice(0, 10);
  const chartRows = chartType === "bar" ? rows : [...rows].reverse();
  const labels = chartRows.map((row) => String(row.name || row.expense_item || row.expense_category || "未命名"));
  const isExpenseRank = section.id === "expense_overrun";
  const chartName =
    section.name ||
    (isExpenseRank
      ? "费用项目使用情况（实际）"
      : chartType === "horizontal_bar"
        ? "排名（横向柱状）"
        : "销售额排名（实际）");
  const rawValues = chartRows.map((row) =>
    Number(
      isExpenseRank
        ? row.actual_expense_amount || 0
        : row.actual_sales_amount || row.budget_sales_amount || 0
    )
  );
  const values = rawValues.map((value) => value / 10000);
  const showChart = chartType !== "table";
  const showTable = chartType === "bar_table" || chartType === "table";
  return (
    <div className="ranking-card-body">
      {showChart && <div className="ranking-chart-wrap"><BarChart labels={labels} values={values} rawValues={rawValues} name={chartName} horizontal={chartType !== "bar"} format="amount" valueFormatter={(value) => `${value.toFixed(2)} 万元`} /></div>}
      {showTable && <div className="ranking-table-wrap"><DataTable rows={rows as Record<string, unknown>[]} columns={rankingColumns(section.id)} /></div>}
    </div>
  );
}

function rankingColumns(sectionId: string) {
  if (sectionId === "expense_overrun") {
    return [
      { key: "expense_category", title: "费用大项" },
      { key: "expense_item", title: "费用小项" },
      { key: "actual_expense_amount", title: "实际（万元）", render: (row: Record<string, unknown>) => formatAmountWan(row.actual_expense_amount as number) },
      { key: "budget_expense_amount", title: "预算（万元）", render: (row: Record<string, unknown>) => formatAmountWan(row.budget_expense_amount as number) },
      { key: "expense_diff", title: "差异（万元）", render: (row: Record<string, unknown>) => formatAmountWan(row.expense_diff as number) },
    ];
  }
  return [
    { key: "name", title: "名称" },
    { key: "actual_sales_amount", title: "实际销售额", render: (row: Record<string, unknown>) => formatAmountWan(row.actual_sales_amount as number) },
    { key: "budget_sales_amount", title: "预算销售额", render: (row: Record<string, unknown>) => formatAmountWan(row.budget_sales_amount as number) },
    { key: "sales_completion_rate", title: "完成率", render: (row: Record<string, unknown>) => formatPercent(row.sales_completion_rate as number) },
  ];
}

export function ComparisonDetailTable({ section }: { section: DashboardOverview["table_sections"][number] }) {
  if (section.id === "expense_category_detail") {
    return (
      <DataTable
        rows={section.rows as Record<string, unknown>[]}
        columns={[
          { key: "expense_category", title: "费用大项" },
          { key: "expense_item", title: "费用小项" },
          { key: "actual_expense_amount", title: "实际费用", render: (row) => formatAmountWan(row.actual_expense_amount as number) },
          { key: "budget_expense_amount", title: "预算费用", render: (row) => formatAmountWan(row.budget_expense_amount as number) },
          { key: "expense_diff", title: "费用差异", render: (row) => formatAmountWan(row.expense_diff as number) },
          { key: "expense_usage_rate", title: "使用率", render: (row) => formatPercent(row.expense_usage_rate as number) },
        ]}
      />
    );
  }
  return (
    <DataTable
      rows={section.rows as Record<string, unknown>[]}
      columns={[
        { key: "group_name", title: "运营组" },
        { key: "shop_name", title: "店铺" },
        { key: "product_name", title: "产品" },
        { key: "actual_sales_amount", title: "实际销售额", render: (row) => formatAmountWan(row.actual_sales_amount as number) },
        { key: "budget_sales_amount", title: "预算销售额", render: (row) => formatAmountWan(row.budget_sales_amount as number) },
        { key: "sales_diff", title: "销售差异", render: (row) => formatAmountWan(row.sales_diff as number) },
        { key: "annual_completion_rate", title: "全年达成率", render: (row) => formatPercent(row.annual_completion_rate as number) },
        { key: "same_period_completion_rate", title: "同期达成率", render: (row) => formatPercent(row.same_period_completion_rate as number) },
      ]}
    />
  );
}

export function HealthInsightCard({ overview }: { overview: DashboardOverview }) {
  return (
    <section className="dashboard-health">
      <div className="health-score">B</div>
      <div>
        <h3>主要经营提醒</h3>
        <ul>{overview.health_insights.map((item, index) => <li key={index} className={`insight-${item.level}`}>{item.message}</li>)}</ul>
      </div>
    </section>
  );
}

export function CustomWidgetCard({ widget }: { widget: DashboardWidgetData }) {
  const rows = ((widget.rows || []) as Record<string, unknown>[]).sort((a, b) => {
    if ((widget.format || "amount") !== "amount") return 0;
    return (Number(b.actual_sales_amount || 0) - Number(a.actual_sales_amount || 0)) || (Number(b.budget_sales_amount || 0) - Number(a.budget_sales_amount || 0));
  });
  const valueField = widget.value_field || "actual_sales_amount";
  const chartRows = widget.chart_type === "bar" || isLineLikeChart(widget.chart_type) ? rows : [...rows].reverse();
  const labels = chartRows.map((row) => String(row.name || "未命名"));
  const rawValues = chartRows.map((row) => row[valueField] === null || row[valueField] === undefined ? null : Number(row[valueField]));
  const values = rawValues.map((value) => widget.format === "percent" ? Number(value || 0) : Number(value || 0) / 10000);
  const lineValues = rawValues.map((value) => widget.format === "percent" ? Number(value || 0) : Number(value || 0) / 10000);
  const showChart = widget.chart_type !== "table";
  const showTable = widget.chart_type === "bar_table" || widget.chart_type === "table";
  const columns = [
    { key: "name", title: widget.dimension_label || "维度" },
    {
      key: valueField,
      title: widget.metric_label || "指标",
      render: (row: Record<string, unknown>) => widget.format === "percent" ? formatPercent(row[valueField] as number) : formatAmountWan(row[valueField] as number)
    },
    { key: "budget_sales_amount", title: "预算销售额", render: (row: Record<string, unknown>) => formatAmountWan(row.budget_sales_amount as number) },
    { key: "actual_sales_amount", title: "实际销售额", render: (row: Record<string, unknown>) => formatAmountWan(row.actual_sales_amount as number) },
    { key: "sales_completion_rate", title: "达成率", render: (row: Record<string, unknown>) => formatPercent(row.sales_completion_rate as number) },
  ];
  return (
    <div className="ranking-card-body">
      {showChart && (
        <div className="ranking-chart-wrap">
          {isLineLikeChart(widget.chart_type) ? (
            <LineChart
              labels={labels}
              series={[{ name: widget.metric_label || "指标", data: lineValues, rawData: rawValues, format: widget.format || "amount" }]}
              variant={widget.chart_type}
            />
          ) : (
            <BarChart labels={labels} values={values} rawValues={rawValues} horizontal={widget.chart_type !== "bar"} format={widget.format || "amount"} name={widget.metric_label || "指标"} />
          )}
        </div>
      )}
      {showTable && <div className="ranking-table-wrap"><DataTable rows={rows} columns={columns} /></div>}
    </div>
  );
}

export function LoadingSkeleton() {
  return <div className="dashboard-skeleton"><div /><div /><div /><div /><div /><div /></div>;
}
