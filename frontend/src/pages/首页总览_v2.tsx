import { useEffect, useMemo, useState } from "react";
import { exportDashboardView } from "../api/exportApi";
import { getDashboardLayout, getDashboardWidgetCatalog, getDashboardWidgetsData, updateDashboardLayout } from "../api/dashboardApi";
import { getGroupsShops } from "../api/uploadApi";
import ChartCard from "../charts/ChartCard";
import DashboardConfigModal from "../components/DashboardConfigModal";
import EmptyState from "../components/EmptyState";
import {
  ActualCoverageBanner,
  HealthInsightCard,
  LoadingSkeleton,
  MetricCards2,
  ViewModeHeader,
  type DashboardFilters,
} from "../components/Dashboard2";
import {
  ComparisonDetailTable,
  CustomWidgetCard,
  RankingTableCard,
  TrendComparisonChart,
} from "../components_v2/Dashboard2_v2";
import { DashboardFilterBar_v2 } from "../components_v2/DashboardFilterBar_v2";
import decorateChips_v2 from "../components_v2/decorateChips_v2";
import type { DashboardLayoutConfig, DashboardOverview, DashboardWidgetCatalog, DashboardWidgetConfig, DashboardWidgetData } from "../types/dashboard";
import type { OperationGroupOption } from "../types/upload";

const initialFilters: DashboardFilters = {
  year: "2026",
  budget_version: "1",
  month: "",
  group_code: "",
  shop_code: "",
  product_name: "",
  data_view: "comparison",
};

export default function 首页总览_v2({
  onAiOpen = () => undefined,
  onHeaderFiltersChange,
  refCapture,
}: {
  onAiOpen?: () => void;
  onHeaderFiltersChange?: (year: string, budgetVersion: string) => void;
  refCapture?: (setter: (next: Partial<{ year: string; budget_version: string }>) => void) => void;
}) {
  const [filters, setFilters] = useState<DashboardFilters>(initialFilters);
  const [groups, setGroups] = useState<OperationGroupOption[]>([]);
  const [catalog, setCatalog] = useState<DashboardWidgetCatalog | null>(null);
  const [layout, setLayout] = useState<DashboardLayoutConfig | null>(null);
  const [widgetData, setWidgetData] = useState<DashboardWidgetData[]>([]);
  const [overview, setOverview] = useState<DashboardOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState<React.ReactNode>("");
  const [refreshKey, setRefreshKey] = useState(0);
  const [detailExpanded, setDetailExpanded] = useState(false);
  const [configOpen, setConfigOpen] = useState(false);

  useEffect(() => {
    if (onHeaderFiltersChange) onHeaderFiltersChange(filters.year, filters.budget_version);
  }, [filters.year, filters.budget_version, onHeaderFiltersChange]);

  useEffect(() => {
    if (refCapture) {
      refCapture((next) => {
        setFilters((prev) => ({ ...prev, ...next }));
      });
    }
    return () => {
      if (refCapture) refCapture(() => undefined);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [refCapture]);

  useEffect(() => {
    getGroupsShops().then((registry) => setGroups(registry.operation_groups || [])).catch(() => setGroups([]));
  }, []);

  useEffect(() => decorateChips_v2(document.body), []);

  function buildDefaultLayout(nextCatalog: DashboardWidgetCatalog): DashboardLayoutConfig {
    const visible = new Set(["metric_cards", "actual_coverage", "sales_trend", "profit_trend", "sales_ranking", "expense_overrun", "comparison_detail", "expense_category_detail", "health_insights"]);
    return {
      version: 1,
      widgets: nextCatalog.standard_widgets.map((item, index) => ({
        id: item.id,
        module_id: item.id,
        kind: "standard",
        title: item.title,
        visible: visible.has(item.id),
        order: (index + 1) * 10,
        width: item.default_width,
        chart_type: item.default_chart_type,
        expanded: false,
      }))
    };
  }

  useEffect(() => {
    let alive = true;
    Promise.all([getDashboardWidgetCatalog(), getDashboardLayout().catch(() => null)])
      .then(([nextCatalog, nextLayout]) => {
        if (!alive) return;
        setCatalog(nextCatalog);
        if (nextLayout) {
          setLayout(nextLayout);
        } else {
          setLayout(buildDefaultLayout(nextCatalog));
          setMessage("首页配置异常，已使用默认布局。");
        }
      })
      .catch((error) => setMessage(error instanceof Error ? error.message : "首页配置加载失败"));
    return () => {
      alive = false;
    };
  }, []);

  const overviewParams = useMemo(() => ({
    year: filters.year,
    budget_version: filters.budget_version,
    month: filters.month,
    group_code: filters.group_code,
    shop_code: filters.shop_code,
    product_name: filters.product_name,
    data_view: filters.data_view,
    top_n: 10,
  }), [filters]);

  useEffect(() => {
    if (!layout) return;
    let alive = true;
    setLoading(true);
    setMessage("");
    getDashboardWidgetsData({ filters: overviewParams, widgets: layout.widgets })
      .then((data) => {
        if (!alive) return;
        setOverview(data.overview);
        setWidgetData(data.widgets);
      })
      .catch((error) => {
        if (!alive) return;
        setOverview(null);
        setWidgetData([]);
        setMessage(error instanceof Error ? error.message : "首页数据加载失败");
      })
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, [overviewParams, refreshKey, layout]);

  async function exportCurrentView() {
    try {
      const result = await exportDashboardView(buildExportParams(filters));
      const file = result.files[0];
      const fileName = file?.name || result.dashboard_path?.split("/").slice(-2, -1)[0] || "当前视角经营看板";
      const folderPath = result.dashboard_path ? result.dashboard_path.replace(/\/index\.html$/, "") : "报表导出中心 → 导出历史";
      localStorage.setItem("budget-latest-export", JSON.stringify({ name: fileName, kind: "dashboard" }));
      setMessage(
        <div className="export-success-message">
          <strong>当前视角 HTML 看板已导出。</strong>
          <span>文件名：{fileName}</span>
          <span>位置：{folderPath}</span>
          <a href="#/export">去报表导出中心的"导出历史"查看并定位文件</a>
        </div>
      );
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "导出当前视角失败");
    }
  }

  async function saveLayout(nextLayout: DashboardLayoutConfig) {
    const saved = await updateDashboardLayout(nextLayout);
    setLayout(saved);
    setRefreshKey((value) => value + 1);
  }

  async function resetLayout() {
    const saved = await updateDashboardLayout({ reset: true });
    setLayout(saved);
    setRefreshKey((value) => value + 1);
  }

  function findWidgetData(widget: DashboardWidgetConfig) {
    return widgetData.find((item) => item.id === widget.id || item.module_id === widget.module_id);
  }

  function renderConfiguredWidget(widget: DashboardWidgetConfig) {
    if (!overview || !widget.visible) return null;
    const className = `dashboard-widget-shell ${widget.width === "full" ? "widget-full" : "widget-half"}`;
    if (widget.kind === "custom") {
      const data = findWidgetData(widget);
      if (!data) return null;
      return <section className={className} key={widget.id}><ChartCard title={data.title || widget.title}><CustomWidgetCard widget={data} /></ChartCard></section>;
    }
    if (widget.module_id === "metric_cards") return <section className={className} key={widget.id}><MetricCards2 overview={overview} /></section>;
    if (widget.module_id === "actual_coverage") return <section className={className} key={widget.id}><ActualCoverageBanner overview={overview} /></section>;
    if (widget.module_id?.endsWith("_trend")) {
      const keyword = widget.module_id.split("_")[0];
      const section = overview.trend_sections.find((item) => item.id.includes(keyword));
      if (!section) return null;
      return <section className={className} key={widget.id}><ChartCard title={section.title}><TrendComparisonChart section={section} chartType={widget.chart_type} /></ChartCard></section>;
    }
    if (widget.module_id === "sales_ranking" || widget.module_id === "expense_overrun") {
      const section = overview.ranking_sections.find((item) => item.id === widget.module_id);
      if (!section) return null;
      return <section className={className} key={widget.id}><ChartCard title={section.title}><RankingTableCard section={section} chartType={widget.chart_type} /></ChartCard></section>;
    }
    if (widget.module_id === "comparison_detail" || widget.module_id === "expense_category_detail") {
      const section = overview.table_sections.find((item) => item.id === widget.module_id);
      if (!section) return null;
      const rows = widget.expanded || detailExpanded ? section.rows : section.rows.slice(0, 8);
      return (
        <section className={className} key={widget.id}>
          <div className="panel dashboard-detail-panel">
            <div className="detail-heading-row">
              <h3>{section.title}</h3>
              {section.rows.length > 8 && <button className="secondary compact-button" onClick={() => setDetailExpanded((value) => !value)}>{detailExpanded ? "收起明细" : `展开 ${section.rows.length} 条`}</button>}
            </div>
            <ComparisonDetailTable section={{ ...section, rows }} />
          </div>
        </section>
      );
    }
    if (widget.module_id === "health_insights") return <section className={className} key={widget.id}><HealthInsightCard overview={overview} /></section>;
    return null;
  }

  const visibleWidgets = layout ? [...layout.widgets].filter((item) => item.visible).sort((a, b) => a.order - b.order) : [];
  const masonryBlocks = splitDashboardWidgets(visibleWidgets);

  const changeYearOrVersion = (next: Partial<DashboardFilters>) => {
    setFilters((prev) => ({ ...prev, ...next }));
  };

  // 把year/budgetVersion变更回传，同时顶栏的year/V修改也要同步到filters
  (首页总览_v2 as any)._changeYearOrVersion = changeYearOrVersion;

  return (
    <div className="dashboard-page">
      {!loading && overview && <ViewModeHeader overview={overview} />}
      <DashboardFilterBar_v2
        filters={filters}
        groups={groups}
        productOptions={overview?.filter_options?.products || []}
        onChange={setFilters}
        onRefresh={() => setRefreshKey((value) => value + 1)}
        onExport={exportCurrentView}
        onAiOpen={onAiOpen}
        onConfigure={() => setConfigOpen(true)}
      />
      {configOpen && catalog && layout && <DashboardConfigModal catalog={catalog} layout={layout} onClose={() => setConfigOpen(false)} onSave={saveLayout} onReset={resetLayout} />}
      {message && <div className="notice">{message}</div>}
      {loading && <LoadingSkeleton />}
      {!loading && !overview && <EmptyState text="暂无经营总览数据。" />}
      {!loading && overview && (
        <section className="dashboard-configured-stack">
          {masonryBlocks.map((block, index) => block.kind === "full" ? (
            <div className="dashboard-masonry-full" key={`full-${block.widget.id}-${index}`}>
              {renderConfiguredWidget(block.widget)}
            </div>
          ) : (
            <div className="dashboard-masonry-grid" key={`columns-${index}`}>
              <div className="dashboard-masonry-column">{block.left.map(renderConfiguredWidget)}</div>
              <div className="dashboard-masonry-column">{block.right.map(renderConfiguredWidget)}</div>
            </div>
          ))}
        </section>
      )}
    </div>
  );
}

function buildExportParams(filters: DashboardFilters) {
  return {
    year: Number(filters.year) || undefined,
    budget_version: Number(filters.budget_version) || undefined,
    month: filters.month ? Number(filters.month) : undefined,
    group_code: filters.group_code || undefined,
    shop_code: filters.shop_code || undefined,
    product_name: filters.product_name || undefined,
    data_view: filters.data_view,
    top_n: 10,
  };
}

function widgetWeight(widget: DashboardWidgetConfig) {
  if (widget.module_id?.includes("detail")) return 6;
  if (widget.module_id === "sales_ranking" || widget.module_id === "expense_overrun") return 5;
  if (widget.module_id?.endsWith("_trend")) return 4;
  if (widget.module_id === "metric_cards") return 3;
  if (widget.module_id === "health_insights") return 3;
  if (widget.kind === "custom") return 4;
  return 2;
}

function splitDashboardWidgets(widgets: DashboardWidgetConfig[]) {
  const blocks: Array<
    | { kind: "full"; widget: DashboardWidgetConfig }
    | { kind: "columns"; left: DashboardWidgetConfig[]; right: DashboardWidgetConfig[] }
  > = [];
  let left: DashboardWidgetConfig[] = [];
  let right: DashboardWidgetConfig[] = [];
  let leftWeight = 0;
  let rightWeight = 0;

  function flushColumns() {
    if (!left.length && !right.length) return;
    blocks.push({ kind: "columns", left, right });
    left = [];
    right = [];
    leftWeight = 0;
    rightWeight = 0;
  }

  widgets.forEach((widget) => {
    if (widget.width === "full") {
      flushColumns();
      blocks.push({ kind: "full", widget });
      return;
    }
    const weight = widgetWeight(widget);
    if (leftWeight <= rightWeight) {
      left.push(widget);
      leftWeight += weight;
    } else {
      right.push(widget);
      rightWeight += weight;
    }
  });
  flushColumns();
  return blocks;
}
