import { apiGet, apiPost } from "./client";
import type { AggregateSummary } from "../types/dashboard";

export function importCheckedFiles() {
  return apiPost<Record<string, unknown>>("/api/import/checked-files");
}

export function importBudgetFile(fileId: number, force = false) {
  return apiPost<Record<string, unknown>>(`/api/import/${fileId}${force ? "?force=true" : ""}`);
}

export function runAggregate(budgetVersion?: number) {
  return apiPost<Record<string, unknown>>("/api/aggregate/run", budgetVersion ? { budget_version: budgetVersion } : undefined);
}

export function getAggregateSummary(budgetVersion?: number) {
  const query = budgetVersion ? `?budget_version=${budgetVersion}` : "";
  return apiGet<AggregateSummary>(`/api/aggregate/summary${query}`);
}
