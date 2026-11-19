import { apiDelete, apiGet, apiPost } from "./client";
import type { CheckResult } from "../types/check";

export interface ActualBatch {
  batch_id: string;
  file_name: string;
  file_type: "actual_sales" | "actual_expense";
  year: number;
  group_code?: string | null;
  group_name?: string | null;
  shop_code?: string | null;
  shop_name?: string | null;
  status: string;
  status_label?: string;
  row_count: number;
  error_count: number;
  warning_count: number;
  created_at?: string;
  imported_at?: string;
}

export function uploadActualFile(file: File, year: number, type: "sales" | "expense", groupCode?: string, shopCode?: string) {
  const data = new FormData();
  data.append("file", file);
  data.append("year", String(year));
  if (groupCode) data.append("group_code", groupCode);
  if (shopCode) data.append("shop_code", shopCode);
  return apiPost<ActualBatch>(`/api/actual/upload-${type}`, data);
}

export function checkActualBatch(batchId: string) {
  return apiPost<Record<string, unknown>>(`/api/actual/check/${batchId}`);
}

export interface ActualCheckResponse {
  batch_id: string;
  status: string;
  row_count?: number;
  error_count: number;
  warning_count: number;
  issues: Array<Partial<CheckResult> & { message?: string }>;
}

export function getActualCheckResults(batchId: string) {
  return apiGet<ActualCheckResponse>(`/api/actual/check-results/${batchId}`);
}

export function importActualBatch(batchId: string) {
  return apiPost<Record<string, unknown>>(`/api/actual/import/${batchId}`);
}

export function getActualBatches() {
  return apiGet<ActualBatch[]>("/api/actual/batches");
}

export function deleteActualBatch(batchId: string) {
  return apiDelete<{ success: boolean; message: string }>(`/api/actual/batches/${batchId}`);
}
