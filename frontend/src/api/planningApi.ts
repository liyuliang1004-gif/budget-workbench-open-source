import { apiGet, apiPost } from "./client";
import type { CheckResult } from "../types/check";

export interface PlanningShopOption {
  shop_code?: string;
  shop_name: string;
  group_name?: string;
}

export interface PlanningGroupOption {
  group_code?: string;
  group_name: string;
}

export interface PlanningOptions {
  reference_year: number;
  groups: PlanningGroupOption[];
  shops: PlanningShopOption[];
}

export interface PlanningExportPayload {
  reference_year: number;
  target_year: number;
  budget_version?: number;
  group_name?: string;
  shop_name?: string;
  target_sales_amount?: number;
  target_growth_rate?: number;
  sales_price_adjustment_rate?: number;
  cost_price_adjustment_rate?: number;
  sales_price_source?: "actual" | "budget" | "uploaded";
  cost_price_source?: "actual" | "budget" | "uploaded";
  reference_spring_month?: number;
  target_spring_month?: number;
}

export interface PlanningExportFile {
  name: string;
  path: string;
  description: string;
}

export interface PlanningExportResponse {
  success: boolean;
  files: PlanningExportFile[];
}

export function getPlanningOptions(referenceYear: number) {
  return apiGet<PlanningOptions>(`/api/planning/options?reference_year=${referenceYear}`);
}

export function exportPlanningWorkbook(payload: PlanningExportPayload) {
  return apiPost<PlanningExportResponse>("/api/planning/export", payload);
}

export function getPlanningFiles() {
  return apiGet<PlanningExportResponse>("/api/planning/files");
}

export function openPlanningLocation(name: string) {
  return apiPost<{ success: boolean; name: string }>("/api/planning/open-location", { name });
}

export interface PlanningPriceUploadResponse {
  success: boolean;
  year: number;
  price_type: string;
  imported_count: number;
}

export interface PlanningPriceCheckResponse {
  status: string;
  price_type: string;
  row_count: number;
  valid_count: number;
  error_count: number;
  warning_count: number;
  issues: Array<Partial<CheckResult> & { message?: string }>;
}

export function checkPlanningSalesPrices(file: File, year: number) {
  const data = new FormData();
  data.append("file", file);
  data.append("year", String(year));
  return apiPost<PlanningPriceCheckResponse>("/api/planning/check-sales-prices", data);
}

export function checkPlanningCostPrices(file: File, year: number) {
  const data = new FormData();
  data.append("file", file);
  data.append("year", String(year));
  return apiPost<PlanningPriceCheckResponse>("/api/planning/check-cost-prices", data);
}

export function uploadPlanningSalesPrices(file: File, year: number) {
  const data = new FormData();
  data.append("file", file);
  data.append("year", String(year));
  return apiPost<PlanningPriceUploadResponse>("/api/planning/upload-sales-prices", data);
}

export function uploadPlanningCostPrices(file: File, year: number) {
  const data = new FormData();
  data.append("file", file);
  data.append("year", String(year));
  return apiPost<PlanningPriceUploadResponse>("/api/planning/upload-cost-prices", data);
}
