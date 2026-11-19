export interface DashboardSummary {
  sales_amount: number;
  cost_amount: number;
  expense_amount: number;
  profit_amount: number;
  gross_profit?: number;
  cost_rate?: number | null;
  expense_rate?: number | null;
  profit_rate?: number | null;
  uploaded_files?: number;
  error_count?: number;
  warning_count?: number;
}

export interface AggregateSummary {
  department_total: DashboardSummary;
  monthly_trend: Array<Record<string, number | string | null>>;
  group_summary: Array<Record<string, number | string | null>>;
  shop_summary: Array<Record<string, number | string | null>>;
  product_summary: Array<Record<string, number | string | null>>;
  category_summary: Array<Record<string, number | string | null>>;
  expense_summary: Record<string, Array<Record<string, number | string | null>>>;
}

export interface DashboardOverview {
  filters: Record<string, unknown>;
  view_mode: string;
  data_view: "budget" | "actual" | "comparison";
  title: string;
  breadcrumb: string[];
  summary_cards: Record<string, number | null>;
  metric_cards: Array<Record<string, number | string | null>>;
  trend_sections: Array<{
    id: string;
    title: string;
    type: string;
    x_field: string;
    series: Array<{ name: string; field: string; dashed?: boolean }>;
    rows: Array<Record<string, number | string | null>>;
  }>;
  ranking_sections: Array<{ id: string; title: string; type: string; rows: Array<Record<string, number | string | null>> }>;
  table_sections: Array<{ id: string; title: string; type: string; rows: Array<Record<string, number | string | null>> }>;
  health_insights: Array<{ level: string; message: string }>;
  actual_coverage?: {
    has_actual_data: boolean;
    months: number[];
    month_label: string;
    group_count: number;
    shop_count: number;
    groups: string[];
    shops: string[];
    sales_row_count: number;
    expense_row_count: number;
    message: string;
  };
  filter_options?: {
    products?: Array<{ product_key?: string; product_code?: string | null; product_name: string }>;
  };
  quick_actions: Array<{ id: string; label: string }>;
  ranking_data?: Array<Record<string, number | string | null>>;
}

export type DashboardWidgetKind = "standard" | "custom";
export type DashboardWidgetWidth = "half" | "full";
export type DashboardChartType =
  | "metric"
  | "status"
  | "line"
  | "smooth_line"
  | "area"
  | "step_line"
  | "scatter"
  | "bar"
  | "horizontal_bar"
  | "bar_table"
  | "table"
  | "insight";
export type DashboardDataView = "budget" | "actual" | "comparison";
export type DashboardMetric =
  | "sales_amount"
  | "cost_amount"
  | "gross_profit"
  | "expense_amount"
  | "profit_amount"
  | "profit_rate"
  | "expense_rate"
  | "sales_completion_rate"
  | "expense_usage_rate"
  | "annual_completion_rate"
  | "same_period_completion_rate";
export type DashboardDimension = "month" | "group" | "shop" | "product" | "expense_category";
export type DashboardSortBy = "budget" | "actual" | "diff" | "rate";

export interface DashboardCustomConfig {
  metric: DashboardMetric;
  dimension: DashboardDimension;
  data_view: DashboardDataView;
  sort_by: DashboardSortBy;
  top_n: 5 | 10 | 20 | 50;
}

export interface DashboardWidgetConfig {
  id: string;
  module_id?: string;
  kind: DashboardWidgetKind;
  title: string;
  visible: boolean;
  order: number;
  width: DashboardWidgetWidth;
  chart_type: DashboardChartType;
  expanded?: boolean;
  custom_config?: DashboardCustomConfig;
}

export interface DashboardLayoutConfig {
  version: number;
  widgets: DashboardWidgetConfig[];
}

export interface DashboardWidgetCatalog {
  standard_widgets: Array<{
    id: string;
    title: string;
    kind: "standard";
    category: string;
    allowed_chart_types: DashboardChartType[];
    default_chart_type: DashboardChartType;
    default_width: DashboardWidgetWidth;
  }>;
  metrics: Array<{ id: DashboardMetric; label: string; format: "amount" | "percent" }>;
  dimensions: Array<{ id: DashboardDimension; label: string }>;
  data_views: Array<{ id: DashboardDataView; label: string }>;
  sort_options: Array<{ id: DashboardSortBy; label: string }>;
  chart_types: Array<{ id: DashboardChartType; label: string }>;
  top_n_options: Array<5 | 10 | 20 | 50>;
  forbidden_combinations: Array<{ dimension: DashboardDimension; metrics: DashboardMetric[]; reason: string }>;
}

export interface DashboardWidgetData {
  id: string;
  module_id: string;
  kind: DashboardWidgetKind;
  title?: string;
  chart_type: DashboardChartType;
  width: DashboardWidgetWidth;
  metric?: DashboardMetric;
  metric_label?: string;
  format?: "amount" | "percent";
  dimension?: DashboardDimension;
  dimension_label?: string;
  value_field?: string;
  rows?: Array<Record<string, number | string | null>>;
  data?: unknown;
}

export interface DashboardWidgetsDataResponse {
  overview: DashboardOverview;
  widgets: DashboardWidgetData[];
}
