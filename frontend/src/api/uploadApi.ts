import { apiDelete, apiGet, apiPost } from "./client";
import type { GroupShopRegistry, UploadBudgetPayload, UploadedFileRecord } from "../types/upload";

export function uploadBudgetFile(payload: UploadBudgetPayload) {
  const data = new FormData();
  data.append("file", payload.file);
  data.append("budget_year", String(payload.budgetYear));
  data.append("budget_version", String(payload.budgetVersion));
  data.append("group_code", payload.groupCode);
  data.append("shop_code", payload.shopCode);
  return apiPost<UploadedFileRecord>("/api/upload/budget", data);
}

export function getUploadedFiles() {
  return apiGet<UploadedFileRecord[]>("/api/upload/files");
}

export function deleteUploadedFile(fileId: number) {
  return apiDelete<{ message: string }>(`/api/upload/files/${fileId}`);
}

export function getGroupsShops() {
  return apiGet<GroupShopRegistry>("/api/metadata/groups-shops");
}

export function downloadShopBudgetTemplate() {
  window.location.href = "/api/templates/shop-budget";
}

export function downloadActualSalesTemplate() {
  window.location.href = "/api/templates/actual-sales";
}

export function downloadActualExpenseTemplate() {
  window.location.href = "/api/templates/actual-expense";
}

export function downloadActualBusinessTemplate() {
  window.location.href = "/api/templates/actual-business";
}
