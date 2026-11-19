import MetricCard_v2 from "./MetricCard_v2";
import DataTable_v2, { type DataTableColumn } from "./DataTable_v2";
import LineChart from "../charts/LineChart";
import BarChart from "../charts/BarChart";
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
  productOptions = [],
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

  const monthValue = filters.month;
  const monthButtons = [
    { key: "", label: "全年", isYear: true },
    ...Array.from({ length: 12 }, (_, i) => ({
      key: String(i + 1),
      label: `${i + 1}月`,
      isYear: false,
    })),
  ];

  return (
    <div className="v2-filter-bar">
      <div className="v2-filter-row">
        <span className="v2-filter-label">维度：</span>
        <div className="v2-filter-controls">
          <select
            className="v2-capsule-select"
            value={filters.group_code}
            onChange={(event) => onChange({ ...filters, group_code: event.target.value, shop_code: "" })}
          >
            <option value="">全部运营组</option>
            {groups.map((group) => (
              <option key={group.group_code} value={group.group_code}>
                {group.group_name}
              </option>
            ))}
          </select>
          <select
            className="v2-capsule-select"
            value={filters.shop_code}
            onChange={(event) => onChange({ ...filters, shop_code: event.target.value })}
          >
            <option value="">全部店铺</option>
            {shops.map((shop) => (
              <option key={shop.shop_code} value={shop.shop_code}>
                {shop.shop_name}
              </option>
            ))}
          </select>
          <input
            list="v2-product-options"
            style={{
              borderRadius: "var(--v2-radius-pill)",
              minWidth: 180,
              padding: "8px 16px",
            }}
            value={filters.product_name}
            onChange={(event) => onChange({ ...filters, product_name: event.target.value })}
            placeholder="搜索或选择产品"
          />
          <datalist id="v2-product-options">
            {productOptions.map((item, index) => (
              <option
                key={item.product_key || `${item.product_code || "name"}-${item.product_name}-${index}`}
                value={item.product_name}
              />
            ))}
          </datalist>
        </div>
      </div>

      <div className="v2-filter-row">
        <span className="v2-filter-label">数据视角：</span>
        <div className="v2-filter-controls">
          <div className="v2-segmented">
            <button
              type="button"
              className={filters.data_view === "budget" ? "active" : ""}
              onClick={() => onChange({ ...filters, data_view: "budget" })}
            >
              预算
            </button>
            <button
              type="button"
              className={filters.data_view === "actual" ? "active" : ""}
              onClick={() => onChange({ ...filters, data_view: "actual" })}
            >
              实际
            </button>
            <button
              type="button"
              className={filters.data_view === "comparison" ? "active" : ""}
              onClick={() => onChange({ ...filters, data_view: "comparison" })}
            >
              预算对比实际
            </button>
          </div>
        </div>
        <div className="v2-filter-actions">
          <button type="button" onClick={onRefresh}>🔄 刷新</button>
          <button type="button" className="secondary" onClick={onConfigure}>⚙️ 配置首页</button>
          <button type="button" className="secondary" onClick={onExport}>📤 导出当前视角</button>
          <button type="button" className="primary pill" onClick={onAiOpen}>
            🤖 AI分析
          </button>
        </div>
      </div>

      <div className="v2-filter-row">
        <span className="v2-filter-label">时间：</span>
        <div className="v2-month-picker" style={{ flex: 1 }}>
          <div className="v2-month-buttons">
            {monthButtons.map((m) => (
              <button
                key={m.key || "year"}
                type="button"
                className={`v2-month-btn ${m.isYear ? "year" : ""} ${
                  (m.key === "" && monthValue === "") || m.key === monthValue ? "active" : ""
                }`}
                onClick={() => onChange({ ...filters, month: m.key })}
              >
                {m.label}
              </button>
            ))}
          </div>
        </div>
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
  const topInsight =
    overview.health_insights[0]?.message || "暂无需要优先处理的经营提醒。";

  return (
    <section className="v2-hero-card">
      <div>
        <div className="v2-hero-title-row">
          <h2 style={{ fontSize: 20, fontWeight: 700 }}>{overview.title}</h2>
          <span className="v2-view-badge">当前视角</span>
        </div>
        <p style={{ marginTop: 8, color: "var(--v2-muted)", fontSize: 13 }}>
          当前筛选：{overview.breadcrumb.join(" / ")}
        </p>
      </div>
      <div className="v2-hero-summary">
        {summary.map((card) => (
          <div
            className="v2-hero-summary-item"
            key={String(card.id || card.label)}
          >
            <span>{card.label}</span>
            <strong>{formatCardValue(card.value, card.format)}</strong>
            {card.sub_label && (
              <small style={{ fontSize: 11, color: "var(--v2-muted)" }}>
                {card.sub_label} {formatCardValue(card.sub_value, card.format)}
              </small>
            )}
          </div>
        ))}
        <div className="v2-hero-summary-item insight">
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
    <section
      className={`v2-coverage-banner ${coverage.has_actual_data ? "" : "warning"}`}
    >
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
  return format === "percent"
    ? formatPercent(value as number | null)
    : formatAmountWan(value as number | null);
}

function detectMetricKind(label: string): {
  valueColor: "primary" | "success" | "warning" | "danger" | "default";
  footerTrend: "up" | "down" | "warn" | "neutral";
} {
  if (label.includes("销售") || label.includes("利润") || label.includes("毛利")) {
    return { valueColor: "primary", footerTrend: "neutral" };
  }
  if (label.includes("成本") || label.includes("费用")) {
    return { valueColor: "default", footerTrend: "neutral" };
  }
  if (label.includes("完成率") || label.includes("达成率") || label.includes("使用率")) {
    return { valueColor: "success", footerTrend: "neutral" };
  }
  return { valueColor: "default", footerTrend: "neutral" };
}

export function MetricCards2({ overview }: { overview: DashboardOverview }) {
  return (
    <section className="v2-metric-grid">
      {overview.metric_cards.map((card) => {
        const label = String(card.label);
        const kind = detectMetricKind(label);
        const hintText = card.sub_label
          ? `${card.sub_label} ${formatCardValue(card.sub_value, card.format)}`
          : card.rate !== undefined
          ? `比例 ${formatPercent(card.rate as number)}`
          : "";

        let footerTrend = kind.footerTrend;
        let footerText = hintText;
        if (hintText.includes("↓") || hintText.includes("下降") || label.includes("费用")) {
          footerTrend = "down";
        } else if (hintText.includes("↑") || hintText.includes("提升")) {
          footerTrend = "up";
        } else if (hintText.includes("偏低") || hintText.includes("警告")) {
          footerTrend = "warn";
        }

        return (
          <MetricCard_v2
            key={String(card.id)}
            label={label}
            value={formatCardValue(card.value, card.format)}
            valueColor={kind.valueColor}
            footerTrend={footerTrend}
            footerText={footerText}
          />
        );
      })}
    </section>
  );
}

function tooltipExtras(section: DashboardOverview["trend_sections"][number]) {
  if (!section.id.includes("comparison")) return section.rows.map(() => []);
  return section.rows.map((row) => {
    const numberOrNull = (value: unknown) =>
      value === null || value === undefined ? null : Number(value);
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
        {
          label: "差异",
          value:
            (row.sales_diff as number | null) ??
            diff(row.actual_sales_amount, row.budget_sales_amount),
          format: "amount" as const,
        },
        {
          label: "达成率",
          value:
            (row.sales_completion_rate as number | null) ??
            rate(row.actual_sales_amount, row.budget_sales_amount),
          format: "percent" as const,
        },
      ];
    }
    if (section.id.includes("profit"))
      return [
        {
          label: "差异",
          value:
            (row.profit_diff as number | null) ??
            diff(row.actual_profit_amount, row.budget_profit_amount),
          format: "amount" as const,
        },
      ];
    if (section.id.includes("expense")) {
      return [
        {
          label: "差异",
          value:
            (row.expense_diff as number | null) ??
            diff(row.actual_expense_amount, row.budget_expense_amount),
          format: "amount" as const,
        },
        {
          label: "使用率",
          value:
            (row.expense_usage_rate as number | null) ??
            rate(row.actual_expense_amount, row.budget_expense_amount),
          format: "percent" as const,
        },
      ];
    }
    if (section.id.includes("cost")) {
      return [
        {
          label: "差异",
          value:
            (row.cost_diff as number | null) ??
            diff(row.actual_cost_amount, row.budget_cost_amount),
          format: "amount" as const,
        },
        {
          label: "使用率",
          value:
            (row.cost_usage_rate as number | null) ??
            rate(row.actual_cost_amount, row.budget_cost_amount),
          format: "percent" as const,
        },
      ];
    }
    return [];
  });
}

function selectBarSeries(section: DashboardOverview["trend_sections"][number]) {
  return (
    section.series.find(
      (item) => item.name.includes("实际") && !item.name.includes("未上传")
    ) || section.series[0]
  );
}

function isPendingUploadSeries(
  item: DashboardOverview["trend_sections"][number]["series"][number]
) {
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
      .map(
        (row, index) =>
          row[pendingSeries.field] === null ||
          row[pendingSeries.field] === undefined
            ? -1
            : index
      )
      .filter((index) => index >= 0);
    return compactMissingRanges(indexes);
  }

  const actualSeries = section.series.filter(
    (item) => item.name.includes("实际") && !isPendingUploadSeries(item)
  );
  if (!actualSeries.length) return [];
  const indexes = section.rows
    .map((row, index) =>
      actualSeries.every(
        (item) => row[item.field] === null || row[item.field] === undefined
      )
        ? index
        : -1
    )
    .filter((index) => index >= 0);
  return compactMissingRanges(indexes);
}

const lineLikeChartTypes: DashboardChartType[] = [
  "line",
  "smooth_line",
  "area",
  "step_line",
  "scatter",
];

function isLineLikeChart(
  type: DashboardChartType | undefined
): type is "line" | "smooth_line" | "area" | "step_line" | "scatter" {
  return lineLikeChartTypes.includes(type || "line");
}

export function TrendComparisonChart({
  section,
  chartType = "line",
}: {
  section: DashboardOverview["trend_sections"][number];
  chartType?: DashboardChartType;
}) {
  const labels = section.rows.map((row) => `${row[section.x_field]}月`);
  const visibleSeries = section.series.filter((item) => !isPendingUploadSeries(item));
  if (chartType === "bar" || chartType === "horizontal_bar") {
    const item = selectBarSeries({ ...section, series: visibleSeries });
    const rawValues = section.rows.map((row) =>
      row[item.field] === null || row[item.field] === undefined
        ? null
        : Number(row[item.field])
    );
    const values = rawValues.map((value) => Number(value || 0) / 10000);
    return (
      <BarChart
        labels={labels}
        values={values}
        rawValues={rawValues}
        name={item.name}
        horizontal={chartType === "horizontal_bar"}
        format="amount"
      />
    );
  }
  const series = visibleSeries.map((item) => ({
    name: item.name,
    dashed: item.dashed,
    format: "amount" as const,
    rawData: section.rows.map((row) =>
      row[item.field] === null || row[item.field] === undefined
        ? null
        : Number(row[item.field])
    ),
    data: section.rows.map((row) =>
      row[item.field] === null || row[item.field] === undefined
        ? null
        : Number(row[item.field]) / 10000
    ),
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

function amountRankValue(
  row: Record<string, number | string | null>,
  sectionId: string
) {
  if (sectionId === "expense_overrun") {
    return [Number(row.actual_expense_amount || 0), Number(row.budget_expense_amount || 0)];
  }
  return [Number(row.actual_sales_amount || 0), Number(row.budget_sales_amount || 0)];
}

function sortAmountRows(
  rows: Array<Record<string, number | string | null>>,
  sectionId: string
) {
  return [...rows].sort((a, b) => {
    const [aActual, aBudget] = amountRankValue(a, sectionId);
    const [bActual, bBudget] = amountRankValue(b, sectionId);
    return bActual - aActual || bBudget - aBudget;
  });
}

function rankingColumns(sectionId: string): DataTableColumn[] {
  if (sectionId === "expense_overrun") {
    return [
      { key: "expense_category", title: "费用大项" },
      { key: "expense_item", title: "费用小项" },
      {
        key: "actual_expense_amount",
        title: "实际（万元）",
        render: (row) => formatAmountWan(row.actual_expense_amount as number),
      },
      {
        key: "budget_expense_amount",
        title: "预算（万元）",
        render: (row) => formatAmountWan(row.budget_expense_amount as number),
      },
      {
        key: "expense_diff",
        title: "差异（万元）",
        render: (row) => formatAmountWan(row.expense_diff as number),
      },
    ];
  }
  return [
    { key: "name", title: "名称" },
    {
      key: "actual_sales_amount",
      title: "实际销售额",
      render: (row) => formatAmountWan(row.actual_sales_amount as number),
    },
    {
      key: "budget_sales_amount",
      title: "预算销售额",
      render: (row) => formatAmountWan(row.budget_sales_amount as number),
    },
    {
      key: "sales_completion_rate",
      title: "完成率",
      render: (row) => formatPercent(row.sales_completion_rate as number),
    },
  ];
}

export function RankingTableCard({
  section,
  chartType = "bar_table",
}: {
  section: DashboardOverview["ranking_sections"][number];
  chartType?: DashboardChartType;
}) {
  const rows = sortAmountRows(section.rows, section.id).slice(0, 10);
  const chartRows = chartType === "bar" ? rows : [...rows].reverse();
  const labels = chartRows.map(
    (row) =>
      String(row.name || row.expense_item || row.expense_category || "未命名")
  );
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
    <div className="ranking-card-body" style={{ display: "grid", gap: 14 }}>
      {showChart && (
        <div className="ranking-chart-wrap" style={{ minWidth: 0 }}>
          <BarChart
            labels={labels}
            values={values}
            rawValues={rawValues}
            name={chartName}
            horizontal={chartType !== "bar"}
            format="amount"
            valueFormatter={(value) => `${value.toFixed(2)} 万元`}
          />
        </div>
      )}
      {showTable && (
        <div className="ranking-table-wrap" style={{ minWidth: 0 }}>
          <DataTable_v2
            rows={rows as Record<string, unknown>[]}
            columns={rankingColumns(section.id)}
          />
        </div>
      )}
    </div>
  );
}

export function ComparisonDetailTable({
  section,
}: {
  section: DashboardOverview["table_sections"][number];
}) {
  if (section.id === "expense_category_detail") {
    return (
      <DataTable_v2
        rows={section.rows as Record<string, unknown>[]}
        columns={[
          { key: "expense_category", title: "费用大项" },
          { key: "expense_item", title: "费用小项" },
          {
            key: "actual_expense_amount",
            title: "实际费用",
            render: (row) => formatAmountWan(row.actual_expense_amount as number),
          },
          {
            key: "budget_expense_amount",
            title: "预算费用",
            render: (row) => formatAmountWan(row.budget_expense_amount as number),
          },
          {
            key: "expense_diff",
            title: "费用差异",
            render: (row) => formatAmountWan(row.expense_diff as number),
          },
          {
            key: "expense_usage_rate",
            title: "使用率",
            render: (row) => formatPercent(row.expense_usage_rate as number),
          },
        ]}
      />
    );
  }
  return (
    <DataTable_v2
      rows={section.rows as Record<string, unknown>[]}
      columns={[
        { key: "group_name", title: "运营组" },
        { key: "shop_name", title: "店铺" },
        { key: "product_name", title: "产品" },
        {
          key: "actual_sales_amount",
          title: "实际销售额",
          render: (row) => formatAmountWan(row.actual_sales_amount as number),
        },
        {
          key: "budget_sales_amount",
          title: "预算销售额",
          render: (row) => formatAmountWan(row.budget_sales_amount as number),
        },
        {
          key: "sales_diff",
          title: "销售差异",
          render: (row) => formatAmountWan(row.sales_diff as number),
        },
        {
          key: "annual_completion_rate",
          title: "全年达成率",
          render: (row) => formatPercent(row.annual_completion_rate as number),
        },
        {
          key: "same_period_completion_rate",
          title: "同期达成率",
          render: (row) => formatPercent(row.same_period_completion_rate as number),
        },
      ]}
    />
  );
}

export function HealthInsightCard({ overview }: { overview: DashboardOverview }) {
  return (
    <section
      className="v2-card"
      style={{
        display: "grid",
        gridTemplateColumns: "auto minmax(0,1fr)",
        gap: 24,
        alignItems: "center",
      }}
    >
      <div
        style={{
          width: 96,
          height: 96,
          borderRadius: "50%",
          display: "grid",
          placeItems: "center",
          border: "10px solid var(--v2-success)",
          color: "var(--v2-success)",
          fontSize: 36,
          fontWeight: 900,
        }}
      >
        B
      </div>
      <div>
        <h3 style={{ margin: "0 0 12px" }}>主要经营提醒</h3>
        <ul style={{ margin: 0, paddingLeft: 20, display: "grid", gap: 8 }}>
          {overview.health_insights.map((item, index) => (
            <li key={index} className={`insight-${item.level}`}>
              {item.level === "danger" && (
                <span style={{ color: "var(--v2-danger)" }} />
              )}
              {item.level === "warning" && (
                <span style={{ color: "var(--v2-warning)" }} />
              )}
              {item.level === "success" && (
                <span style={{ color: "var(--v2-success)" }} />
              )}
              <span
                style={{
                  color:
                    item.level === "danger"
                      ? "var(--v2-danger)"
                      : item.level === "warning"
                      ? "var(--v2-warning)"
                      : item.level === "success"
                      ? "var(--v2-success)"
                      : "var(--v2-text-2)",
                }}
              >
                {item.message}
              </span>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}

export function CustomWidgetCard({ widget }: { widget: DashboardWidgetData }) {
  const rows = ((widget.rows || []) as Record<string, unknown>[]).sort((a, b) => {
    if ((widget.format || "amount") !== "amount") return 0;
    return (
      Number(b.actual_sales_amount || 0) - Number(a.actual_sales_amount || 0) ||
      Number(b.budget_sales_amount || 0) - Number(a.budget_sales_amount || 0)
    );
  });
  const valueField = widget.value_field || "actual_sales_amount";
  const chartRows =
    widget.chart_type === "bar" || isLineLikeChart(widget.chart_type)
      ? rows
      : [...rows].reverse();
  const labels = chartRows.map((row) => String(row.name || "未命名"));
  const rawValues = chartRows.map((row) =>
    row[valueField] === null || row[valueField] === undefined
      ? null
      : Number(row[valueField])
  );
  const values = rawValues.map((value) =>
    widget.format === "percent"
      ? Number(value || 0)
      : Number(value || 0) / 10000
  );
  const lineValues = rawValues.map((value) =>
    widget.format === "percent"
      ? Number(value || 0)
      : Number(value || 0) / 10000
  );
  const showChart = widget.chart_type !== "table";
  const showTable =
    widget.chart_type === "bar_table" || widget.chart_type === "table";
  const columns: DataTableColumn[] = [
    { key: "name", title: widget.dimension_label || "维度" },
    {
      key: valueField,
      title: widget.metric_label || "指标",
      render: (row) =>
        widget.format === "percent"
          ? formatPercent(row[valueField] as number)
          : formatAmountWan(row[valueField] as number),
    },
    {
      key: "budget_sales_amount",
      title: "预算销售额",
      render: (row) => formatAmountWan(row.budget_sales_amount as number),
    },
    {
      key: "actual_sales_amount",
      title: "实际销售额",
      render: (row) => formatAmountWan(row.actual_sales_amount as number),
    },
    {
      key: "sales_completion_rate",
      title: "达成率",
      render: (row) => formatPercent(row.sales_completion_rate as number),
    },
  ];
  return (
    <div className="ranking-card-body" style={{ display: "grid", gap: 14 }}>
      {showChart && (
        <div className="ranking-chart-wrap" style={{ minWidth: 0 }}>
          {isLineLikeChart(widget.chart_type) ? (
            <LineChart
              labels={labels}
              series={[
                {
                  name: widget.metric_label || "指标",
                  data: lineValues,
                  rawData: rawValues,
                  format: widget.format || "amount",
                },
              ]}
              variant={widget.chart_type}
            />
          ) : (
            <BarChart
              labels={labels}
              values={values}
              rawValues={rawValues}
              horizontal={widget.chart_type !== "bar"}
              format={widget.format || "amount"}
              name={widget.metric_label || "指标"}
            />
          )}
        </div>
      )}
      {showTable && (
        <div className="ranking-table-wrap" style={{ minWidth: 0 }}>
          <DataTable_v2 rows={rows} columns={columns} />
        </div>
      )}
    </div>
  );
}

export function LoadingSkeleton() {
  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "repeat(3, 1fr)",
        gap: 16,
      }}
    >
      {[0, 1, 2, 3, 4, 5].map((i) => (
        <div
          key={i}
          style={{
            minHeight: 130,
            borderRadius: "var(--v2-radius-lg)",
            background:
              "linear-gradient(90deg, #f3f4f6, #f9fafb, #f3f4f6)",
            backgroundSize: "200% 100%",
            animation: "v2-skeleton 1.2s linear infinite",
            border: "1px solid var(--v2-border)",
          }}
        />
      ))}
      <style>{`@keyframes v2-skeleton { from { background-position: 200% 0; } to { background-position: -200% 0; } }`}</style>
    </div>
  );
}
