import { apiGet, apiPost, apiPut } from "./client";
import type { AggregateSummary, DashboardLayoutConfig, DashboardOverview, DashboardSummary, DashboardWidgetCatalog, DashboardWidgetsDataResponse } from "../types/dashboard";

export function getDashboardSummary() {
  return apiGet<DashboardSummary>("/api/dashboard/summary");
}

export function getDashboardData(params: Record<string, string | number | undefined> = {}) {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== "") query.set(key, String(value));
  });
  const suffix = query.toString() ? `?${query.toString()}` : "";
  return apiGet<{ filters: Record<string, unknown>; summary: DashboardSummary; data: AggregateSummary }>(`/api/dashboard/data${suffix}`);
}

export function getDashboardOverview(params: Record<string, string | number | undefined> = {}) {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== "") query.set(key, String(value));
  });
  const suffix = query.toString() ? `?${query.toString()}` : "";
  return apiGet<DashboardOverview>(`/api/dashboard/overview${suffix}`);
}

export function getDashboardLayout() {
  return apiGet<DashboardLayoutConfig>("/api/dashboard/layout");
}

export function updateDashboardLayout(payload: DashboardLayoutConfig | { reset: true }) {
  return apiPut<DashboardLayoutConfig>("/api/dashboard/layout", payload);
}

export function getDashboardWidgetCatalog() {
  return apiGet<DashboardWidgetCatalog>("/api/dashboard/widget-catalog");
}

export function getDashboardWidgetsData(payload: { filters: Record<string, string | number | undefined>; widgets: DashboardLayoutConfig["widgets"] }) {
  return apiPost<DashboardWidgetsDataResponse>("/api/dashboard/widgets/data", payload);
}
