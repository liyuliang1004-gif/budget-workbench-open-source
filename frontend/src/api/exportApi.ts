import { apiGet, apiPost } from "./client";
import type { ExportFile, ExportFilesResponse } from "../types/export";

export function exportExcel(reportType: string, year?: number, budgetVersion?: number) {
  return apiPost<{ success: boolean; files: ExportFile[] }>("/api/export/excel", {
    report_type: reportType,
    year,
    budget_version: budgetVersion
  });
}

export function exportStaticDashboard(dashboardType: string, year?: number, groupCode?: string, budgetVersion?: number) {
  return apiPost<{ success: boolean; dashboard_path: string; files: ExportFile[] }>("/api/export/static-dashboard", {
    dashboard_type: dashboardType,
    year,
    group_code: groupCode || undefined,
    budget_version: budgetVersion
  });
}

export function exportDashboardView(params: Record<string, string | number | undefined>) {
  return apiPost<{ success: boolean; dashboard_path: string; files: ExportFile[] }>("/api/export/dashboard-view", params);
}

export function exportCustomReport(params: Record<string, string | number | undefined>) {
  return apiPost<{ success: boolean; files: ExportFile[] }>("/api/export/custom", params);
}

export function getExportFiles(budgetVersion?: number) {
  const query = budgetVersion ? `?budget_version=${budgetVersion}` : "";
  return apiGet<ExportFilesResponse>(`/api/export/files${query}`);
}

export function openExportLocation(name: string, kind: "report" | "dashboard" = "report") {
  return apiPost<{ success: boolean; name: string }>("/api/export/open-location", { name, kind });
}
