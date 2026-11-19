import { apiGet, apiPost } from "./client";
import type { CheckResult } from "../types/check";

export function runFormatCheck(fileId: number) {
  return apiPost<Record<string, unknown>>(`/api/check/format/${fileId}`);
}

export function runFullCheck(fileId: number) {
  return apiPost<Record<string, unknown>>(`/api/check/full/${fileId}`);
}

export function getCheckResults(fileId: number, params: Record<string, string> = {}) {
  const query = new URLSearchParams(Object.entries(params).filter(([, value]) => value !== ""));
  const suffix = query.toString() ? `?${query.toString()}` : "";
  return apiGet<CheckResult[]>(`/api/check/results/${fileId}${suffix}`);
}

export function exportFormatReport() {
  return apiPost<{ report_path: string }>("/api/check/export-format-report");
}

export function exportFormulaReport() {
  return apiPost<{ report_path: string }>("/api/check/export-formula-report");
}

export function exportCalculationReport() {
  return apiPost<{ report_path: string }>("/api/check/export-calculation-report");
}

export function exportErrorReport() {
  return apiPost<{ report_path: string }>("/api/check/export-error-report");
}
